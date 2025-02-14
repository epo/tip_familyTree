# patent_analysis/tree_processor.pyFamilyRecord

from collections import Counter
import os
import re
import io
import pandas as pd
from typing import List, Dict, Any
from epo.tipdata.ops import OPSClient, models, exceptions
import xml.etree.ElementTree as ET
from IPython.display import Markdown, display
from PIL import Image
import requests
from pprint import pprint
import logging

class TreeProcessor:
    """
    The TreeProcessor class is designed to process a hierarchical tree of patent application data, 
    generate a text-based summary, and manage the interaction with the OPSClient API to retrieve detailed information about the patent family.
    The TreeProcessor class is responsible for writing results to a file, and handling different patent-related entities such as applications, 
    publications, and legal events. It uses the OPSClient to interact with the European Patent Office API.
    """
    def __init__(self, tree: Dict[str, Any], root: Dict[str, Any], initFlag: str, listAPs: List[str], listORAPs: List[str], df: pd.DataFrame, familyRoot):
        """
        Initialize a TreeProcessor instance with the necessary data structures and configurations.
        It checks for the correct structure of the tree and initializes several attributes, including setting up the file path for saving the tree output.

        Args:
            tree (dict): Tree structure containing patent data.
            root (dict): Root node of the tree.
            initFlag (str): A flag to indicate specific processing methods.
            listAPs (list): List of application identifiers.
            listORAPs (list): List of original application identifiers.
            df (pd.DataFrame): DataFrame containing relevant publication data.
            familyRoot: Additional family-related data.
        
        Raises:
            TypeError: If 'tree' is a list instead of a dictionary-like object.
            AttributeError: If the 'tree' object doesn't have a 'recInp' attribute.
        """           
        self.tree = tree  # A dictionary representing the tree structure.
        self.root = root  # A dictionary containing root elements of the tree.
        self.initFlag = initFlag  # A string used to control which data is processed.
        self.listAPs = listAPs  # A list of application identifiers (APs).
        self.listORAPs = listORAPs  # A list of original application identifiers (ORAPs).
        self.df = df  # A pandas DataFrame containing filtered publication numbers.
        # An instance of OPSClient, initialized with API credentials.
        self.client: OPSClient = OPSClient(key=os.getenv("OPS_KEY"), secret=os.getenv("OPS_SECRET"))        
        self.familyRoot = familyRoot  # Represents the root of the patent family.
        
        self.tree_file_path = self.tree.recInp + '.txt'  # The file path to save the output tree data.
        self.workdir = '/home/jovyan/tip-data-ops/docs/patent_analysis/'  # The directory where files will be stored.
        os.makedirs(self.workdir, exist_ok=True)
        self.tree_file_path = os.path.join(self.workdir, self.tree_file_path)
    
    def process_tree_file(self):
        """
        This method generates a text file summarizing divisional patent applications from the tree data.
        It counts occurrences of country codes in the application list (listAPs),
        writes a tree file that iterates through each level of the root structure.
        calls the tree_generation() method recursively to build the tree structure for each application.
        logs warnings and errors if any issues are encountered.
        This method processes the patent tree structure and generates a summary text file detailing divisional applications.
        The method iterates over the root elements, processes the root nodes, and recursively generates tree 
        structures for application nodes.

        Returns:
            dict: The last processed root node.
        """       
        try:
            # If listORAPs is None, it returns early to avoid errors.
            if self.listORAPs is None:
                print("Error: listORAPs is None")
                return

            if not self.listORAPs:
                print("Warning: listORAPs is empty")

            listApCCs = ['WO' if len(word) > 2 and word[2] == 'W' else word[:2] for word in self.listAPs]

            # Count occurrences of each country code        
            country_code_counts = Counter(listApCCs)
            
            # creates a formatted comment for divisional applications, including the number of applications per country code.
            applicationComment = 'including: ' + ' + '.join(
                f'{count} {code}{"s" if count > 1 else ""}' for code, count in country_code_counts.items()
            )
            tree_comment = f'Divisional Applications ({self.df.shape[0]}) {applicationComment}'

            # The method writes this information to a tree file for later inspection.
            with open(self.tree_file_path, 'w') as tree_file:
                tree_file.write(f'Starting Divitree with {self.tree.recInp}\n')       
                # tree_file.write(f'{tree_comment}\n')

                processed_apps = set()
                for r in range(len(self.root) + 1, 0, -1):
                    current_root = self.root.get(r, {})
                    # print(f"root[{r}] =", current_root)
                    # print("root.an[{r}] =", current_root.get('root_an', ''))            
                    # print("root.ap[{r}] =", current_root.get('root_ap', ''))
                    # print("root.pn[{r}] =", current_root.get('root_pn', ''))                
                    # print("root.pr[{r}] =", current_root.get('root_pr', ''))
                    # print("root.orap[{r}] =", current_root.get('root_orap', ''))               
                    # print("root.evnt[{r}] =", current_root.get('root_evnt', ''))
                
                    if not isinstance(current_root, dict):
                        print(f"Warning: Expected dict for root at {r}, got {type(current_root)}")
                        continue
                    
                    self.process_root(current_root, tree_file)

                    if self.listORAPs:
                        my_node = current_root.get('root_ap', '')
                        # print("my_node:", my_node)
                        if my_node.strip() and my_node not in processed_apps:
                            # print(f"Generating tree for: {my_node} at level 1")
                            self.tree_generation(my_node, 1, tree_file, processed_apps)
        except Exception as e:
            print(f"Error during process_tree_file: {e}")

        return current_root
        
    def process_root(self, current_root, tree_file):
        """
        This method processes the current root node of the tree and writes its information into the tree file:
        it identifies key attributes like root_an (application number) and root_ap (application ID).
        Depending on the initFlag, it invokes specialized methods (process_priorities(), process_applications(), etc.) to process different aspects of the node.
        The method checks the last 6 characters of the application to see if it matches the recInp value and formats it accordingly.
        Process a single root node, extracting relevant information and writing it to the tree file.
        Also invokes specific methods depending on the value of the 'initFlag' to further process
        entities like priorities, applications, and legal events.

        Args:
            current_root (dict): Current root node containing application and patent data.
            tree_file (file): The file object to which the processed tree information is written.
        """
        
        root_an = current_root.get('root_an', '')
        root_r_word_1 = current_root.get('root_ap', '')
        rec_inp_right_6 = self.tree.recInp[-6:]  # Get the last 6 characters of recInp
        
        # The method processes root attributes and writes them to the tree file in a hierarchical format.
        if root_r_word_1.strip():            
            if root_r_word_1.endswith(rec_inp_right_6):
                # print("{root_r_word_1}:", {root_r_word_1})
                tree_file.write(f', **{root_r_word_1}** \n')
            elif 'EP' not in root_an and root_an.endswith(rec_inp_right_6):
                if root_an:
                    # print("{root_an}, {root_r_word_1}:", {root_an}, {root_r_word_1})
                    tree_file.write(f', {root_an} / {root_r_word_1} \n') # Write with a leading comma
                else:
                    # print("{root_r_word_1}:", {root_r_word_1})
                    tree_file.write(f', {root_r_word_1} \n') # Write with a leading comma
            else:
                if root_an:
                    # print("{root_an}, {root_r_word_1}:", {root_an}, {root_r_word_1})                    
                    tree_file.write(f', {root_an} / {root_r_word_1} \n') # Write with a leading comma
                else:
                    # print("{root_r_word_1}:", {root_r_word_1})                    
                    tree_file.write(f', {root_r_word_1} \n') # Write with a leading comma

            # Mapping initFlag values to corresponding methods
            process_methods = {
                'Show_priorities': self.process_priorities,
                'Show_applications': self.process_applications,
                'Show_parents': self.process_parents,
                'Show_publications': self.process_publications,
                'Show_citations': self.process_citations,
                'Show_classifications': self.process_classifications,
                'Show_parties': self.process_parties,                
                'Show_legal_events': self.process_legal_events,
                'Show_images': self.process_images
            }

            # The initFlag is used to control the type of information processed (e.g., citations, classifications, parties).            
            if self.initFlag in process_methods:
                # print("self.initFlag in process_root:", self.initFlag)
                process_methods[self.initFlag](current_root, 1, tree_file)

    def clean_orap_list(self, orap_list):
        """
        Clean and remove duplicates from a list of original application identifiers.
        It removes date strings (in the format YYYYMMDD) using a regular expression.
        This method also strips any date information from the entries and splits multi-entry strings.

        Args:
            orap_list (list): List of original application identifiers (orap).

        Returns:
            list: A cleaned and deduplicated list of original application identifiers.
        """
        # The regular expression ensures that dates are removed from the original application list for cleaner output.
        date_pattern = re.compile(r'\(\d{8}\)')
        cleaned_orap_list = []
        for orap_entry in orap_list:
            # Remove dates from the orap entries
            cleaned_entry = date_pattern.sub('', orap_entry).strip()
            # It splits entries on commas or semicolons to handle multiple entries in a single string.
            parts = re.split(r'[,;]', cleaned_entry)
            for part in parts:
                part = part.strip()
                if part and part not in cleaned_orap_list:
                    cleaned_orap_list.append(part)
        # The cleaned entries are returned as a de-duplicated list.
        return cleaned_orap_list

    def tree_generation(self, my_node, level, tree_file, processed_apps):
        """
        This recursive method generates the tree structure for a given node:
        It adds each node to a processed_apps set to prevent reprocessing.
        For each level in the tree, it writes the node’s data to the tree file, including sibling nodes.
        It also invokes methods like process_priorities() or process_publications() depending on the initFlag.
        If a child node is found, it recursively calls itself to generate the tree for that child.
        
        Recursively generate a tree structure by navigating through nodes and writing them to the tree file.
        This method tracks processed applications and ensures no duplicates are included.

        Args:
            my_node (str): Identifier of the current node.
            level (int): Depth level for indentation.
            tree_file (file): File object for writing tree structure.
            processed_apps (set): Set of already processed application nodes.
        """
        # Check if the current node has already been processed, avoid reprocessing.
        if my_node in processed_apps:
            return  # Exit the function early if node has been processed.

        # Mark the current node as processed to avoid revisiting.
        processed_apps.add(my_node)
        
        # Increment the level for indentation purposes (one level deeper).
        level += 1
        
        # Dictionary to track sibling nodes at this level, starting with an index '0'.
        sibling = {'0': 0}

        # Loop through the nodes in reverse order.
        for t in range(int(self.tree.orapNb) - 1, -1, -1):
            # print(f"t: {t} self.tree.ap[t]: {self.tree.ap[t]}, self.tree.pn[t] {self.tree.pn[t]}, tree.orap[t] {self.tree.orap[t]}, my_node: {my_node}")
            # Check if the current node is a child in the tree data.
            if my_node in self.tree.orap[t]:
                if self.tree.orap[t] != '':
                    # # Check the type and value of self.tree.pr[t]
                    # print(f"Type of self.tree.pr[{t}]:", type(self.tree.pr[t]))
                    # print(f"Value of self.tree.pr[{t}]:", self.tree.pr[t])

                    # if self.tree.pr[t] != []:
                    #     print("self.tree.ap[t]:", self.tree.ap[t])
                    #     print("self.tree.pr[t]:", self.tree.pr[t])
                    
                    # Collect sibling data (application number, publication number, priorities, etc.)
                    s = sibling['0'] + 1  # Increment sibling index for each valid sibling node.
                    sibling[s] = {
                        'an': '',  # Application number (not directly used here)
                        'ap': self.tree.ap[t].split()[0] if isinstance(self.tree.ap[t], str) else '',
                        'pn': self.tree.pn[t].split()[0] if isinstance(self.tree.ap[t], str) else '', 
                        'pr': list(self.tree.pr[t]) if hasattr(self.tree, 'pr') and isinstance(self.tree.pr[t], (list,tuple)) else '',
                        'orap': self.tree.orap[t],
                        's': self.tree.ap[t].split()[0] if isinstance(self.tree.ap[t], str) else '',
                        'evnt': self.tree.evnt[t] if hasattr(self.tree, 'evnt') and isinstance(self.tree.evnt[t], list) else []
                    }
                    # print("sibling[s]:", sibling[s])
                    # print("t:", t)
                    # print(f"Found child: {sibling[s]['ap']}")
                    # print(f"Found publication: {sibling[s]['pn']}")
                    # print(f"Found prio: {sibling[s]['pr']}")
                    # print(f"Found parent: {sibling[s]['orap']}")
                    # print(f"Found evnt: {sibling[s]['evnt']}")
                    # print()
                    sibling['0'] = s  # Update sibling count.

        # If siblings are found, process them.
        if sibling['0'] > 0:
            rec_inp_right_6 = self.tree.recInp[-6:]
            
            # Loop through all siblings found at the current level.
            for s in range(1, sibling['0'] + 1):
                # Write sibling data to the file with appropriate indentation.
                if 's' in sibling[s] and sibling[s]['s'].find(rec_inp_right_6) >= 0:
                    tree_file.write(', ' * level + f'{sibling[s]["s"]}' + '\n')
                elif 's' in sibling[s] and 'EP' not in sibling[s]['s'] and sibling[s]['an'].find(rec_inp_right_6) >= 0:
                    tree_file.write(', ' * level + f'{sibling[s]["an"]}' + '\n')
                else:
                    tree_file.write(', ' * level + f'{sibling[s]["s"]}' + '\n')

                # Mapping initFlag values to corresponding methods
                process_methods = {
                    'Show_publications': self.process_publications, 
                    'Show_citations': self.process_citations,
                    'Show_classifications': self.process_classifications,
                    'Show_parties': self.process_parties,
                    'Show_images': self.process_images                    
                }

                # Call specific methods based on the initFlag.
                if self.initFlag == 'Show_priorities':
                    self.process_priorities(sibling[s]['pr'], level, tree_file)
                elif self.initFlag == 'Show_applications':
                    self.process_applications(sibling[s]['ap'], level, tree_file)
                elif self.initFlag == 'Show_parents':
                    self.process_parents(sibling[s]['orap'], level, tree_file)
                elif self.initFlag == 'Show_legal_events' and sibling[s]['evnt']: # and sibling[s]['evnt'] != []
                    # tree_file.write(', ' * (level + 1) + "legal_events:\n")  # Add header for legal events
                    
                    # for event in sibling[s]['evnt']:
                    #     event_code = event.get('code', 'N/A')
                    #     event_desc = event.get('desc', 'No Description')
                    #     event_date = event.get('dateMigr', 'Unknown Date')
                    #     event_texts = event.get('texts', '').split('|')  # Split multiple texts if needed

                    #    # Write formatted event information
                    #    tree_file.write(', ' * (level + 2) + f"- {event_code}: {event_desc} ({event_date})\n")
        
                    #    # Write additional text information if available
                    #    for text in event_texts:
                    #        tree_file.write(', ' * (level + 3) + f"{text.strip()}\n")
            
                    self.process_legal_events({'legal_events': sibling[s]['evnt']}, level, tree_file)
                    
                elif self.initFlag in process_methods:
                    sibling_dict = {'root_pn': sibling[s]['pn']}
                    process_methods[self.initFlag](sibling_dict, level, tree_file)                
   
                # Recursive call with depth control           
                child_node = sibling[s]['ap']
                # print("child_node:", child_node)
                # print("processed_apps:", processed_apps)
                # It recursively processes children nodes until all nodes are processed.
                if child_node.strip() and child_node not in processed_apps:
                    # print(f"Generating tree for: {child_node} at level {level}")
                    # Recursively call tree_generation for the child node.
                    self.tree_generation(child_node, level, tree_file, processed_apps)
        
        level -= 1
        return level, sibling
    
    def process_generic(self, current_root, level, tree_file, key, formatter=None):
        """
        Process and write data from the current root node to the tree file.

        Args:
            current_root (dict): Current root node data containing various attributes.
            level (int): The current depth in the tree structure, used for indentation in the output file.
            tree_file (file object): File object where the processed data will be written.
            key (str): The key in current_root that holds the data to process (e.g., 'root_ap', 'root_an').
            formatter (function, optional): A function to format the output data before writing.
               The formatter should handle individual items (e.g., strings or dictionaries) as
               the method applies it to each element in lists or nested structures.
        """
        def write_data(data, level, myKey, formatter=None):
            """
            Helper function to recursively write data to the tree file.
            It handles different data types (str, list, dict) and applies formatting if a formatter is provided.

            Args:
                data: The data to write, which can be a string, list, or dictionary.
                level: The current level of recursion used to control the depth (indentation) of the output.
                formatter: A function used to format the data before writing. If not provided, raw data is written.                
            """
            indent = ". " * (level + 1)
            # print("dataType:", type(data))
            # print(data)
            # print()
            # Handle string data
            if isinstance(data, str):              
                tree_file.write(f'{indent}{formatter(data) if formatter else data}\n')
            # Handle list data (process each item recursively)
            elif isinstance(data, list):
                for index, item in enumerate(data):
                    # print("formatter:", formatter)
                    # print("myKey:", myKey)
                    if myKey == 'root_pr':
                        tree_file.write(f'{indent}- Prio {index + 1}:\n')
                        write_data(item, level + 1, formatter)
                    elif myKey == 'root_evnt':
                        tree_file.write(f'{indent}- Event {index + 1}:\n')
                        write_data(item, level + 1, formatter)                        
                    else:
                        # print("item:", item)                        
                        # tree_file.write(f'{indent}- Item {index + 1}:\n')
                        write_data(item, level + 1, formatter)
            # Handle dictionary data (formatting option provided)
            elif isinstance(data, dict):
                for key, value in data.items():
                    if key in {'code', 'desc'}:
                        # print("key:", key)
                        # print("value:", value)                        
                        # tree_file.write(f'{indent}{key}:\n')
                        write_data(f'{indent}{key}:{value}', level + 1, formatter)
                    elif key not in {'nested_data', 'dateMigr', 'infl', 'texts'}:
                        # print("key:", key)
                        # print("value:", value)
                        # tree_file.write(f'{indent}{key}:\n')
                        write_data(f'{indent}{key}:{value}', level + 1, formatter)                        
            else:
                tree_file.write(f'{indent}{formatter(data) if formatter else str(data)}\n')    
            return
            
        # Main logic to extract the relevant data from current_root and process it
        if isinstance(current_root, dict): # instead of dict only
            # Retrieve the data corresponding to the provided key from current_root
            data = current_root.get(key, None)
            if data is not None:
                write_data(data, level, key, formatter)
            else:
                write_data(current_root, level, key, formatter)
                
        # If current_root is already a string or list, process it directly
        elif isinstance(current_root, (str, list)):
            write_data(current_root, level, key, formatter)

        # Handle unexpected data types
        else:
            logging.warning(f"Unexpected current_root format: {type(current_root)}")
        
    def process_priorities(self, current_root, level, tree_file):
        """
        Process and write priority data from the current root node to the tree file.

        Args:
            current_root (dict): Current root node data, containing information about priorities.
            level (int): The current depth in the tree structure, used for indentation in the output file.
            tree_file (file object): The file object for writing tree structure or priority information.
        """
        # Use the process_generic method to handle priority data processing.
        # It passes 'root_pr' as the key, which contains the priority data in the current_root node.
        self.process_generic(current_root, level, tree_file, key='root_pr')

    def process_applications(self, current_root, level, tree_file):
        """
        Process and write application data from the current root node to the tree file.

        Args:
            current_root (str or dict): Current root node data or application identifier.
            level (int): The current depth in the tree structure, used for indentation in the output file.
            tree_file (file object): The file object for writing tree structure or application information.
        """
        # Use the process_generic method to handle application data processing.
        # It passes 'root_ap' as the key, which contains the application data in the current_root node.      
        self.process_generic(current_root, level, tree_file, key='root_ap')

    def process_parents(self, current_root, level, tree_file):
        """
        Process and write parent data from the current root node to the tree file.

        Args:
            current_root (str or dict): Current root node data or parent identifier.
            level (int): The current depth in the tree structure, used for indentation in the output file.
            tree_file (file object): The file object for writing tree structure or parent information.
        """        
        # Use the process_generic method to handle parent data processing.
        # It passes 'root_orap' as the key, which contains the parent data in the current_root node.     
        self.process_generic(current_root, level, tree_file, key='root_orap')

    def process_publications(self, current_root, level, tree_file):
        """
        Process and write publication data from the current root node to the tree file.

        Args:
            current_root (str or dict): Current root node data or publication identifier.
            level (int): The current depth in the tree structure, used for indentation in the output file.
            tree_file (file object): The file object for writing publication information.
        """        
        # Use the process_generic method to handle publication data processing.
        # It passes 'root_pn' as the key, which contains the publication data in the current_root node.        
        self.process_generic(current_root, level, tree_file, key='root_pn')

    def format_legal_events(self, event_data):
        """
        Format legal event data into a readable string.

        Args:
            event_data (dict or any): Data containing legal event information.

        Returns:
            str: A formatted string representing the legal event data, or a default message if no data is available.
        """
        # If event_data is empty or None, return a default message  
        if not event_data or (isinstance(event_data, dict) and 'legal_events' in event_data and not event_data['legal_events']): 
            # return None  # Skip adding this field if it's empty
            event_data = 'No legal events available.'
            return event_data
            

        # If event_data is a dictionary, format each legal event in the list
        if isinstance(event_data, dict) and 'legal_events' in event_data:
            formatted_events = []
            for event in event_data['legal_events']:
                event_type = event.get('legal_event_code', 'Unknown Event')
                event_date = event.get('legal_event_date_migr', 'Unknown Date')
                event_desc = event.get('legal_event_desc', 'No Description')
                event_infl = event.get('legal_event_infl', 'No Influence')

                # Construct the formatted string for each event
                formatted_events.append(f"{event_type} on {event_date}: {event_desc} ({event_infl}) [{event_texts}]")
            return '\n'.join(formatted_events)
        
        # For other types of data, convert them to a string representation
        return str(event_data)

                    # tree_file.write(', ' * (level + 1) + "legal_events:\n")  # Add header for legal events
                    
                    # for event in sibling[s]['evnt']:
                    #     event_code = event.get('code', 'N/A')
                    #     event_desc = event.get('desc', 'No Description')
                    #     event_date = event.get('dateMigr', 'Unknown Date')
                    #     event_texts = event.get('texts', '').split('|')  # Split multiple texts if needed

                    #    # Write formatted event information
                    #    tree_file.write(', ' * (level + 2) + f"- {event_code}: {event_desc} ({event_date})\n")
        
                    #    # Write additional text information if available
                    #    for text in event_texts:
                    #        tree_file.write(', ' * (level + 3) + f"{text.strip()}\n")
                           
    def process_legal_events(self, current_root, level, tree_file):
        """
        Process and write legal event data from the current root node to the tree file.

        Args:
            current_root (str or dict): Current root node data or application identifier.
            level (int): The current depth in the tree structure for indentation.
            tree_file (file object): File object for the tree file where data will be written.
        """
        # Calls the generic processing method with a formatter specific to legal events
        self.process_generic(current_root, level, tree_file, key='root_evnt', formatter=self.format_legal_events)
                
    def retrieve_biblio_data(self, current_root, level, tree_file, data_type, extraction_func=None, output_format_func=None):
        """
        A unified method to process different types of data (e.g., citations, classifications, parties, images) 
        from the current root node and write it to a tree file.

        Args:
            - current_root (dict): The document number or dictionary containing document number information.
            - level (int): The level in the tree for formatting output.
            - tree_file (File): The file object to write the processed data.
            - data_type (str): The type of data to process ('citations', 'classifications', 'parties', 'images').
            - extraction_func (callable): A function to extract specific data from the retrieved bibliographic information.
            - output_format_func (callable): A function to format the extracted data before writing to the file.
        """
        
        # Check if the current_root is valid and contains the expected key 'root_pn'
        if not isinstance(current_root, dict) or 'root_pn' not in current_root:
            print(f"Invalid 'current_root': {current_root}")
            return

        # Extract the publication number from the current_root
        pub_number = current_root.get('root_pn', '')

        # Initialize biblio_data to handle the case where retrieval fails
        biblio_data = None  # Initialize biblio_data to handle the case where retrieval fails
        try:
            # Determine the endpoint and output type based on the data_type
            endpoint = "biblio"
            output_type = "Dataframe"
            if data_type == 'images':
                endpoint = "images"
                output_type = "Raw"
            
            # Retrieve the bibliographic, image, or legal data for the document
            biblio_data = self.client.published_data(
                reference_type="publication",
                input=models.Docdb(pub_number[2:-2], pub_number[:2], pub_number[-2:], date=None),
                endpoint=endpoint,
                constituents=[],
                output_type=output_type,
            )
        except requests.exceptions.RequestException as e:  # Catch any request exception
            print(f"HTTP error occurred: {e}")
            if hasattr(e, 'response'):  # Check if the exception has a response attribute (likely in newer versions)
                if e.response.status_code == 404:
                    print(f"Publication number {pub_number} not found. Skipping.")
                else:
                    raise  # Re-raise other errors
            else:  # For older versions, assume it's a 404 based on the message
                print(f"Publication number {pub_number} not found. Skipping.")

        # display(biblio_data)
        
        # If biblio_data is not retrieved, skip the rest of the process
        if biblio_data is None:
            return
        
        # Extract and process the relevant data        
        extracted_data = extraction_func(biblio_data) if extraction_func else None
        # print("extracted_data:", extracted_data)
        
        # Format the output and write to file if data exists
        if extracted_data:
            formatted_output = output_format_func(extracted_data) if output_format_func else str(extracted_data)
            # print("formatted_output:", formatted_output)
            if tree_file:
                tree_file.write(f'{". " * (level + 1)}{formatted_output}\n')

    def extract_citations(self, biblio_df):
        """
        Extracts citation information from a bibliographic DataFrame.

        Args:
            biblio_df (pandas.DataFrame): DataFrame containing bibliographic data.

        Returns:
            list: A list of citations extracted from the DataFrame.
        """
        citations_list = []
        
        # Check if the DataFrame contains the expected column
        if 'bibliographic-data|references-cited' in biblio_df.columns:
            # Iterate over each entry in the 'bibliographic-data|references-cited' column
            for citations_data in biblio_df['bibliographic-data|references-cited']:
                # Check if the entry is a dictionary and contains 'citation'
                if isinstance(citations_data, dict) and 'citation' in citations_data:
                    citations = citations_data['citation']
                    # If 'citation' is a list, extend citations_list with its elements
                    if isinstance(citations, list):
                        citations_list.extend(citations)                        
                    # If 'citation' is a dictionary, append it to citations_list
                    elif isinstance(citations, dict):
                        citations_list.append(citations)
        return citations_list

    def format_citations(self, citations_list):
        """
        Format a list of citations into a readable string.

        Args:
            citations_list (list): List of citations to format, each citation is expected to be a dictionary.

        Returns:
            str: A formatted string representation of the citations.
        """
        # Convert the list of citation dictionaries into a DataFrame for easier manipulation
        citations_df = pd.json_normalize(citations_list)
        
        # Check for the presence of key 'patcit.@dnum-type' and filter citations based on this column
        if 'patcit.@dnum-type' in citations_df.columns:
            citation_filter = (citations_df['patcit.@dnum-type'] == 'publication number')
        else:
            citation_filter = pd.Series([False] * len(citations_df))

        # Add additional filter for non-null values in 'nplcit.@num' if it exists
        if 'nplcit.@num' in citations_df.columns:
            citation_filter |= citations_df['nplcit.@num'].notna()

        # Apply the filters and drop duplicate citations based on specific columns
        citations_df = citations_df[citation_filter].drop_duplicates(subset=['@sequence', 'patcit.@num'], keep='first')
    
        # Define a helper function to extract the document number from the 'patcit.document-id'
        def extract_doc_number(doc_ids):
            if isinstance(doc_ids, list):
                epodoc_doc_number = None
                docdb_doc_number = None
                for doc in doc_ids:
                    if doc.get('@document-id-type') == 'epodoc':
                        epodoc_doc_number = doc.get('doc-number')
                    elif doc.get('@document-id-type') == 'docdb':
                        docdb_doc_number = doc.get('doc-number')
                return epodoc_doc_number or docdb_doc_number
            elif isinstance(doc_ids, dict):
                # Handle the case where doc_ids is a single dictionary (unlikely, but just in case)
                if doc_ids.get('@document-id-type') == 'epodoc':
                    return doc_ids.get('doc-number')
                elif doc_ids.get('@document-id-type') == 'docdb':
                    return doc_ids.get('doc-number')
            return None

        # Define a helper function to extract 'XP' number from 'nplcit.text'
        def extract_xp_number(npl_text):
            if isinstance(npl_text, str) and 'XP' in npl_text:
                return 'XP' + npl_text.split('XP')[-1].split()[0]
            return None
    
        # Extract document numbers and 'XP' numbers if corresponding columns are present
        if 'patcit.document-id' in citations_df.columns:
            citations_df['extracted_doc_number'] = citations_df['patcit.document-id'].apply(lambda x: extract_doc_number(x))
        else:
            citations_df['extracted_doc_number'] = None

        if 'nplcit.text' in citations_df.columns:
            citations_df['extracted_xp_number'] = citations_df['nplcit.text'].apply(lambda x: extract_xp_number(x))
        else:
            citations_df['extracted_xp_number'] = None

        # Combine extracted document numbers and 'XP' numbers into a single column
        citations_df['formatted_citation'] = citations_df['extracted_doc_number'].combine_first(citations_df['extracted_xp_number'])

        # Collect unique cited phases and append it to the formatted citation if present
        cited_phase = citations_df['@cited-phase'].dropna().unique()
        cited_phase_comment = f" (cited-phase: {cited_phase[0]})" if len(cited_phase) == 1 else ""
        
        return f"{str(citations_df['formatted_citation'].dropna().tolist())}{cited_phase_comment}"

    def process_citations(self, current_root, level=None, tree_file=None):
        """
        Process and write citation data from the current root node to the tree file.

        Args:
            current_root (dict): The document number or dictionary containing document number information.
            level (int, optional): The level in the tree for formatting output. Defaults to None.
            tree_file (file object, optional): File object for writing the processed data. Defaults to None.
        """
        # Call the retrieve_biblio_data method with specific parameters for processing citations
        self.retrieve_biblio_data(
            current_root=current_root,  # Document number or dictionary with document number information
            level=level,                # Level for formatting output
            tree_file=tree_file,        # File object to write the formatted data
            data_type='citations',      # Type of data to process
            extraction_func=self.extract_citations,  # Function to extract citation data from the retrieved bibliographic information
            output_format_func=self.format_citations  # Function to format the extracted citation data before writing to the file
        )

    def extract_classifications(self, biblio_df):
        """
        Extracts and processes patent classification data from a DataFrame containing bibliographic information.

        Args:
            biblio_df (pd.DataFrame): DataFrame containing bibliographic data, including patent classifications.

        Returns:
            list: A list of unique patent classification strings.
        """
        classification_data = []

         # Check if 'bibliographic-data|patent-classifications' column exists in the DataFrame
        if 'bibliographic-data|patent-classifications' in biblio_df.columns:
            # Iterate through each row of the DataFrame
            for index, row in biblio_df.iterrows():
                classification_info = row['bibliographic-data|patent-classifications']
                # Debugging output
                # print(f"Processing classifications for row {index}: {classification_info}")

                # Ensure the classification information is a dictionary and contains 'patent-classification'
                if isinstance(classification_info, dict) and 'patent-classification' in classification_info:
                    classifications = classification_info['patent-classification']

                    # If classifications are in list format, process each classification
                    if isinstance(classifications, list):
                        for classification in classifications:
                            section = classification.get('section', 'Unknown')
                            _class = classification.get('class', 'Unknown')
                            subclass = classification.get('subclass', 'Unknown')
                            main_group = classification.get('main-group', 'Unknown')
                            subgroup = classification.get('subgroup', 'Unknown')

                            # Create a CPC (Cooperative Patent Classification) item string
                            cpc_item = f"{section}{_class}{subclass}{main_group}/{subgroup}"
                            # Debugging output
                            # print("Extracted CPC item:", cpc_item)

                            # Append unique CPC items to the classification_data list
                            if cpc_item not in classification_data:
                                classification_data.append(cpc_item)
                    else:
                        print("No classifications found in this entry.")
                else:
                    print(f"No patent classifications found in row {index}.")

        return classification_data
    
    def format_classifications(self, classification_data):
        """
        Formats the list of patent classification strings into a single string representation.

        Args:
            classification_data (list): A list of patent classification strings.

        Returns:
            str: A string representation of the classification data.
        """
        # Debugging output
        # print(f"Formatting classification data: {classification_data}")
        
        # Convert the list of classifications to a string
        return str(classification_data)

    def process_classifications(self, current_root, level=None, tree_file=None):
        """
        Process and write classification data from the current root node to the tree file.

        Args:
            current_root (dict): The document number or dictionary containing document number information.
            level (int, optional): The level in the tree for formatting output. Defaults to None.
            tree_file (file object, optional): The file object to write the processed data. Defaults to None.
        """
        # Debugging output
        # print(f"Processing classifications for {current_root}")
        
        # Retrieve and process bibliographic data
        self.retrieve_biblio_data(
            current_root,                  # The root data (document number or dictionary)
            level,                         # The indentation level for output formatting
            tree_file,                     # The file object to write the output
            'classifications',            # Type of data to retrieve (classifications)
            self.extract_classifications, # Function to extract classification data
            self.format_classifications   # Function to format the extracted classification data
        )

    def extract_party_names(self, biblio_df):
        """
        Extract names of parties (applicants, inventors, representatives) from the bibliographic DataFrame.

        Args:
            biblio_df (pd.DataFrame): DataFrame containing bibliographic data, including party information.

        Returns:
            list: A list of party names extracted from the DataFrame.
        """
        def extract_names(party_list, role):
            """
            Extract names of parties based on their role.

            Args:
                party_list (list): List of party dictionaries.
                role (str): Role of the party (e.g., 'applicant', 'inventor', 'representative').

            Returns:
                list: A list of party names.
            """            
            return [party.get(f'{role}-name', {}).get('name', '').replace('\u2002', ' ').strip(', ')
                    for party in party_list if f'{role}-name' in party]
            
        if biblio_df is None:
            return []

        # Extract relevant rows from the DataFrame
        indexes_to_iterate = list(biblio_df.head(5).index) + list(biblio_df.tail(5).index)
        indexes_to_iterate = list(set(indexes_to_iterate))  # Remove duplicates if any

        result = []
        for index in indexes_to_iterate:
            row = biblio_df.loc[index]
            parties_info = row.get('bibliographic-data|parties', {})

            if isinstance(parties_info, dict):
                applicants = parties_info.get('applicants', {}).get('applicant', [])
                inventors = parties_info.get('inventors', {}).get('inventor', [])
                representatives = parties_info.get('representatives', {}).get('representative', [])

                applicant_names = extract_names(applicants, 'applicant')
                inventor_names = extract_names(inventors, 'inventor')
                representative_names = extract_names(representatives, 'representative')

                result.extend(applicant_names)
                result.extend(inventor_names)
                result.extend(representative_names)
    
        return result

    def process_parties(self, current_root, level, tree_file):
        """
        Process and write party data (applicants, inventors, representatives) from the current root node to the tree file.

        Args:
            current_root (str or dict): Current root node data or application identifier.
            level (int): The level in the tree for formatting output.
            tree_file (file object): File object for writing the processed data.
        """
        def format_party_output(data):
            """
            Format the extracted party names into a comma-separated string.

            Args:
                data (list): List of party names.

            Returns:
                str: A comma-separated string of party names.
            """
            return ', '.join(data)

        # This method is used to retrieve the bibliographic data, extract relevant party names, and then format the extracted data for output.
        self.retrieve_biblio_data(
            current_root, 
            level, 
            tree_file, 
            'biblio', 
            extraction_func=self.extract_party_names, 
            output_format_func=format_party_output
        )
    
    def process_images(self, current_root, level, tree_file):
        """
        Process and write image data from the current root node to the tree file.

        Args:
            current_root (str or dict): Current root node data or application identifier.
            level (int): The level in the tree for formatting output.
            tree_file (file object): File object for writing the processed data.
        """
        
        def extract_image_data(image_xml):
            """
            Extracts the image path from the XML data.

            Args:
                image_xml (str): XML data containing image information.

            Returns:
                str or None: Path to the image if found, otherwise None.
            """
            root = ET.fromstring(image_xml)
            namespace = {'ops': 'http://ops.epo.org'}

            # Extract the path from the 'FirstPageClipping' document instance
            first_page_clipping = root.find('.//ops:document-instance[@desc="FirstPageClipping"]', namespace)
            if first_page_clipping is not None:
                path = first_page_clipping.get('link')
                # print(f"Extracted image path: {path}")
                return path
            # print("No FirstPageClipping found")
            return None

        def format_image_output(image_path):
            """
            Formats and saves the image, then writes a Markdown link to the image to the tree file.

            Args:
                image_path (str or None): Path to the image.

            Returns:
                str: Markdown formatted image link or a message if no image is found.
            """
            if image_path:
                # print(f"Formatting image path: {image_path}")
                fp_image_data = self.client.image(
                    path=image_path,
                    range=1,
                    document_format='application/tiff',
                )
                # print("fp_image_data:", fp_image_data)
                fp_image = Image.open(io.BytesIO(fp_image_data))
                # print("fp_image:", fp_image)
                display(fp_image)
                
                image_filename = f"image_level_{level}.tiff"
                print("image_filename:", image_filename)
                fp_image.save(image_filename)

                formatted_output = f"![Image at level {level}]({image_filename})"
                # print(f"Formatted output: {formatted_output}")
                if formatted_output:
                    tree_file.write(f"{'. ' * (level + 1)}{formatted_output}\n")          
                return formatted_output        
            return "No image found."
            
        # Initialize formatted_output to None
        formatted_output = None

        # Retrieve and format image data
        formatted_output = self.retrieve_biblio_data(
            current_root, 
            level, 
            None, 
            'images',
            extraction_func=extract_image_data,
            output_format_func=format_image_output
        )
