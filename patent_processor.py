import os
import pandas as pd
import xml.etree.ElementTree as ET
import ipywidgets as widgets
from IPython.display import clear_output
from collections import Counter
from epo.tipdata.ops import OPSClient, models, exceptions

from patent_analysis.family_record import FamilyRecord  # Custom module for handling patent family records
from patent_analysis.tree_creation import TreeCreation, TreeNode  # Custom module for tree creation logic
from patent_analysis.tree_processor import TreeProcessor  # Custom module to process tree structure of patents
from patent_analysis.install_dependencies import InstallDependencies  # Custom module to process dependencies

class PatentProcessor:
    def __init__(self, OPSClient, models, exceptions):
        """
        Initializes the PatentProcessor class by setting up the client, tree structure, 
        input widgets, and buttons.
        """
        # Initialize OPSClient with API key and secret, which are loaded from environment variables
        self.client: OPSClient = OPSClient(key=os.getenv("OPS_KEY"), secret=os.getenv("OPS_SECRET"))

        # Initialize attributes for tree structure and patent processing logic
        self.tree = None  # To hold the generated tree structure
        self.root = None  # To hold the root node of the tree
        self.listAPs = None  # Application numbers list
        self.listORAPs = None  # Original Application numbers list
        self.filtered_app_numbers = None  # Filtered list of application numbers
        self.familyRoot = None  # Root of the patent family
        self.record1 = None  # Instance of FamilyRecord for patent family processing
        self.initFlag = None  # Flag to track the current action (showing priorities, applications, etc.)
        self.is_button_clicked = False  # To check whether a button was clicked
        self.country_checkboxes = []  # To store checkboxes for selecting countries

        # Define a function to update the doc_number based on the selected reference type
        def update_doc_number(change):
            """
            Updates the doc_number widget based on the selected reference type.
            This function is triggered when the user selects a different reference type.
            """            
            if change['new'] == 'application':
                self.doc_number_widget.value = '09164213'  # Example for application
                self.country_widget.value = 'EP'
                self.kind_widget.value = 'A'
                self.constituents_widget.value = None
                self.output_type_widget.value = 'raw'
            elif change['new'] == 'publication':
                self.doc_number_widget.value = '2101496' # Example for publication
                self.country_widget.value = 'EP'
                self.kind_widget.value = 'B1'
                self.constituents_widget.value = 'legal'
                self.output_type_widget.value = 'dataframe'
            else:
                # Reset fields if none of the known reference types are selected
                self.doc_number_widget.value = ''
                self.country_widget.value = ''
                self.kind_widget.value = ''
                self.constituents_widget.value = ''
                self.output_type_widget.value = ''

        # Create input widgets
        self.reference_type_widget = widgets.Dropdown(
            options=['application', 'publication'],  # The available reference types , 'priority'
            value='application',  # Default value
            description='Reference Type:',
        )

        self.doc_number_widget = widgets.Text(
            value='09164213',  # Default document number
            description='Doc Number:',
        )

        self.country_widget = widgets.Text(
            value='EP',  # Default country code (EP = European Patent)
           description='Country:',
        )

        self.kind_widget = widgets.Text(
            value='A',  # Default kind code (A = application publication)
            description='Kind:',
        )

        self.constituents_widget = widgets.Dropdown(
            options=[None, 'biblio', 'legal'],  # Available constituents for patent data
            value=None,
            description='Constituents:',
        )

        self.input_widget = widgets.Dropdown(
            options=[models.Docdb, models.Epodoc],  # Input model types for patent data retrieval
            value=models.Docdb,
            description='Input Model:',
        )

        self.output_type_widget = widgets.Dropdown(
            options=['raw', 'dataframe'],  # Output format types
            value='raw',
            description='Output Type:',
        )

        # Attach the update_doc_number function to the 'value' change event of reference_type_widget
        self.reference_type_widget.observe(update_doc_number, names='value')

         # Create a submit button for submitting the input data
        self.submit_button = widgets.Button(description="Submit")        

        # Link the submit button to the on_submit_button_clicked function
        self.submit_button.on_click(self.on_submit_button_clicked)

        # Create action buttons for different operations (e.g., show priorities, show applications)
        self.action_buttons = [
            widgets.Button(description="Show Priorities"),
            widgets.Button(description="Show Applications"),
            widgets.Button(description="Show Parents"),
            widgets.Button(description="Show Publications"),
            widgets.Button(description="Show Citations"),        
            widgets.Button(description="Show Classifications"),
            widgets.Button(description="Show Parties"),
            widgets.Button(description="Show Legal Events"),
            widgets.Button(description="Show Images")        
        ]
        
        # Button to process selected countries
        self.process_button = widgets.Button(description="Process Selected Countries")
        self.process_button.on_click(self.on_process_button_clicked)
        
        # Initialize action buttons by linking each to its handler function
        def create_button_handler(initFlag):
            """
            Returns a function that handles button clicks for the given initFlag.
            This dynamically binds each button to its specific functionality.
            """
            def handler(b):
                self.initFlag = initFlag  # Set the flag to determine which action to take
                self.process_with_initFlag() # Process the tree based on the action
            return handler
            
        # Attach the handler function to each action button with its respective initFlag   
        for btn, initFlag in zip(self.action_buttons, ['Show_priorities', 
                                                       'Show_applications', 
                                                       'Show_parents', 
                                                       'Show_publications', 
                                                       'Show_citations', 
                                                       'Show_classifications', 
                                                       'Show_parties', 
                                                       'Show_legal_events', 
                                                       'Show_images']):
            btn.on_click(create_button_handler(initFlag))
            
        # Output widget to display results in the Jupyter notebook
        self.output = widgets.Output()
        
        # Display the widgets in the notebook
        display(self.reference_type_widget, self.doc_number_widget, self.country_widget, self.kind_widget, 
                self.constituents_widget, self.input_widget, self.output_type_widget, self.submit_button, self.output)

    def process_with_initFlag(self):
        """
        This method processes the patent tree data using a specific initFlag, 
        which represents different actions (e.g., showing priorities, publications, etc.).
        """
        # Directs the output of the following code to the widget's output display.
        with self.output:
            # Clears the output from previous actions to provide a clean view.
            clear_output(wait=True)
            try:
                # Initializes the TreeProcessor object with the tree, root node, and relevant application data.
                tree_processor = TreeProcessor(
                    tree=self.tree, 
                    root=self.root, 
                    initFlag=self.initFlag, 
                    listAPs=self.listAPs, 
                    listORAPs=self.listORAPs, 
                    df=self.filtered_app_numbers,
                    familyRoot=self.familyRoot
                )
                # Checks if a file exists at the given path where the tree file will be saved. If it does, it deletes the file to ensure fresh processing.
                if os.path.exists(tree_processor.tree_file_path):
                    os.remove(tree_processor.tree_file_path)

                # Processes the tree file and returns the root node.
                current_root = tree_processor.process_tree_file()

                # Reads and prints the contents of the processed tree file if it exists.
                if os.path.exists(tree_processor.tree_file_path):
                    with open(tree_processor.tree_file_path, 'r') as f:
                        print(f.read())
                
                if self.tree is not None:
                    self.display_checkboxes()
                    display(*self.action_buttons) 
                else:
                    print("Failed to process the tree.")
            
            except Exception as e:
                print(f"Error processing tree with initFlag {self.initFlag}: {e}")
                import traceback
                traceback.print_exc()
                
    def display_checkboxes(self):
        """
        This method displays checkboxes for country selection based on the FamilyRecord object,
        with country counts next to each checkbox.
        """
        # Checks if record1 exists; if not, it creates a new FamilyRecord object using the current widget values (reference type, document number, country, kind, constituents).
        if not hasattr(self, 'record1') or self.record1 is None:
            reference_type = self.reference_type_widget.value
            doc_number = self.doc_number_widget.value
            country = self.country_widget.value
            kind = self.kind_widget.value
            if self.reference_type_widget.value == 'application' or self.reference_type_widget.value == 'publication':
                constituents = [self.constituents_widget.value] or []
            else:
                constituents = self.constituents_widget.value or []    
            # constituents = [self.constituents_widget.value] or []
            
            # Initializes the FamilyRecord object to manage patent family data.           
            self.record1 = FamilyRecord(reference_type, doc_number, country, kind, constituents)

        # # Fetch family data
        # family_data = self.record1.client.family(
        #     reference_type=self.record1.reference_type,
        #     input=models.Docdb(self.record1.doc_number, self.record1.country, self.record1.kind),
        #     constituents=None,
        #     output_type="Dataframe"
        # )

        # # Handle missing data
        # if family_data.empty:
        #     print("No family data found for this publication number.")
        #     return

        # # Extract country occurrences
        # country_codes = []
        # for pub_ref in family_data["ops:family-member|publication-reference"]:
        #     if isinstance(pub_ref, dict) and "document-id" in pub_ref:
        #         for doc in pub_ref["document-id"]:
        #             if "@document-id-type" in doc and doc["@document-id-type"] == "docdb":
        #                 country_codes.append(doc.get("country", "Unknown"))

        # # Count occurrences
        # country_counts = Counter(country_codes)
    
        # Checks if record1 is initialized and has the DropdownCC attribute (which contains available country codes).
        if self.record1 and hasattr(self.record1, 'DropdownCC'):
            # Creates a checkbox for each country in the list, excluding "EP" and "WO".
            self.country_checkboxes = [
                widgets.Checkbox(value=False, description=c)
                # widgets.Checkbox(value=False, description=f"{c} ({country_counts.get(c, 0)})")
                for c in self.record1.DropdownCC if c not in ["EP", "WO"]
            ]
        else:
            # If record1 is not properly initialized or DropdownCC is missing, an error message is printed.
            print("Error: record1 is not properly initialized or DropdownCC is missing.")
            return
            
        # Displays the checkboxes for country selection.
        display(*self.country_checkboxes)
        display(self.process_button)

    def create_and_process_tree(self):
        """
        This method creates a patent tree using the TreeCreation class and processes it with the TreeProcessor.
        """
        try:
            # Creates a TreeCreation object using the patent data.
            self.tree = TreeCreation(db="EPODOC", df=self.filtered_app_numbers)

            # Calls the method to create a nested dictionary structure representing the patent tree, and extracts relevant lists of applications and filtered application numbers.
            self.root, self.listAPs, self.listORAPs, self.filtered_app_numbers = self.tree.create_nested_dict(self.filtered_app_numbers)

            # Converts the nested dictionary to a tree structure using TreeNode objects.
            tree_object = TreeNode.dict_to_object(self.tree)

            # Initializes a TreeProcessor object to handle tree processing.
            tree_processor = TreeProcessor(
                tree=tree_object, 
                root=self.root, 
                initFlag=self.initFlag, 
                listAPs=self.listAPs, 
                listORAPs=self.listORAPs, 
                df=self.filtered_app_numbers, 
                familyRoot=self.familyRoot
            )
            
            # Processes the tree and creates a tree file that represents the patent family structure.
            tree_processor.process_tree_file()
            
            # Reads and prints the content of the processed tree file.
            with open(tree_processor.tree_file_path, 'r') as f:
                print(f.read())
            
            # If the tree is successfully created, it displays the checkboxes and action buttons for further actions.    
            if self.tree is not None:
                self.display_checkboxes()       
                display(*self.action_buttons)     
            else:
                # Catches exceptions during tree processing and returns None values if the process fails.
                print("Failed to process the tree.")           
                
            return self.tree, self.root, self.listAPs, self.listORAPs, self.filtered_app_numbers
            
        except Exception as e:
            print(f"Error processing tree: {e}")
            return None, None, None, None, None

    def on_submit_button_clicked(self, b):
        """
        This method is triggered when the submit button is clicked. It processes the form input and creates a patent family record.
        """
        with self.output:
            # Clears the output display.
            clear_output(wait=True)

            # Retrieves values from the input widgets (e.g., reference type, document number, country, kind, constituents).
            reference_type = self.reference_type_widget.value
            doc_number = self.doc_number_widget.value
            country = self.country_widget.value
            kind = self.kind_widget.value       
            if self.reference_type_widget.value == 'publication':
                constituents = [self.constituents_widget.value] or []
            else:
                constituents = self.constituents_widget.value or []
            
            try:
                # Initializes a FamilyRecord object using the input values.
                self.record1 = FamilyRecord(reference_type, doc_number, country, kind, constituents)
                # Processes the patent family record and retrieves a filtered list of application numbers.
                result1 = self.record1.process_fami_record()

                if result1 and isinstance(result1, tuple):
                    # Assigns the filtered application numbers from the result of process_fami_record().
                    self.filtered_app_numbers, _ = result1 
                    self.familyRoot = self.record1.get_family_root()
                    # Calls the method to create and process the patent tree.
                    self.create_and_process_tree()
                else:
                    # Handles potential TypeError and generic exceptions, printing error messages and stack traces.
                    print("Result from process_fami_record is None or invalid. Unable to proceed with tree creation.")
                    
            except TypeError as te:
                print(f"TypeError occurred: {te}")
                import traceback
                traceback.print_exc()
        
            except Exception as e:
                print(f"Error during submission process: {e}")
                import traceback
                traceback.print_exc()

    def on_process_button_clicked(self, b):
        """
        This method processes the data for the selected countries when the "Process Selected Countries" button is clicked.
        """
        with self.output:
            clear_output(wait=True)

            selected_countries = [checkbox.description for checkbox in self.country_checkboxes if checkbox.value]
            print(f"Selected countries: {selected_countries}")

            # Gathers the countries selected by the user from the checkboxes.
            if selected_countries:
                # Retrieves input values from the widgets.
                reference_type = self.reference_type_widget.value
                doc_number = self.doc_number_widget.value
                country = self.country_widget.value
                kind = self.kind_widget.value
                if self.reference_type_widget.value == 'publication':
                    constituents = [self.constituents_widget.value] or []
                else:
                    constituents = self.constituents_widget.value or []
                    
                try:
                    # Creates a new FamilyRecord object for the selected countries.
                    new_record = FamilyRecord(
                        reference_type=reference_type,
                        doc_number=doc_number,
                        country=country,
                        kind=kind,
                        constituents=constituents,
                        countrySelection=selected_countries
                    )
                    
                    # Updates the patent family record with the selected countries.
                    new_record.updateFamily()

                    # Processes the family record for the selected countries.
                    new_result = new_record.process_fami_record(selected_countries)
                    
                    if new_result:
                        new_filtered_app_numbers, source = new_result
                        # If there is valid data for the selected countries, it updates the patent family tree.
                        if not new_filtered_app_numbers.empty:
                            self.familyRoot = new_record.get_family_root()
                            self.filtered_app_numbers = new_filtered_app_numbers
                            # Calls the method to create and process the tree for the new selection.
                            self.create_and_process_tree()
                        else:
                            print("No data to display for selected countries")
                    else:
                        print("No data found for selected countries.")

                # Catches any errors during the country selection processing and provides detailed error messages with stack traces.
                except Exception as e:
                    print(f"Error processing data for selected country: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("No countries selected.")