import pandas as pd
from typing import Dict, Any
import re

class TreeCreation:
    """
    The TreeCreation class is designed to manage and organize data related to publications, patents, or applications, 
    likely within a legal or patent-related context. 
    It initializes various lists that will store different types of information, and optionally, 
    it can be initialized with a DataFrame (pd.DataFrame) that will populate the class attributes upon initialization.
    """
    def __init__(self, db="EPODOC", df: pd.DataFrame = None):
        """
        Initialize the Tree object.
        
        Args:
        - db (str): The database type. Defaults to "EPODOC".
        - df (pd.DataFrame, optional): DataFrame containing initial data. Defaults to None.
        """
        # Initialize attributes
        self.db = db  # Database type, likely used to identify which database schema to interact with
        self.df = df  # Optional DataFrame passed during initialization

        # Default values for various properties
        self.orapNb =  "<no data>"  # Placeholder for 'orapNb' attribute (possibly a reference or identifier)
        
        # Initialize various lists that will hold data, these lists will be populated as needed
        self.an = []  # 'an' represents accessions number
        self.ap = []  # 'ap' represents an application number
        self.pn = []  # 'pn' represents a publication number
        self.pr = []  # 'pr' represents a priority number
        self.orap = []  # 'orap' represents an original application number
        self.orpr = []  # 'orpr' represents an original priority number
        self.evnt = []  # 'evnt' represents legal events information
        self.recInp = []  # 'recInp' represents records or inputs being processed

        # If a DataFrame is passed, populate the class from it
        if df is not None:
            self.populate_from_dataframe(df)  # Populate the attributes using the DataFrame
        
    def clean_doc_number(self, doc_number):
        """
        Clean a document number by removing trailing alphabetic and numeric kind codes.
        
        Args:
        - doc_number (str): The document number to be cleaned.
        
        Returns:
        - str: Cleaned document number.
        """        
        # Regular expression to remove trailing alphabetic and numeric kind codes
        cleaned_doc_number = re.sub(r'[A-Za-z]{1,2}[0-9]*$', '', doc_number).strip()
        return cleaned_doc_number

    def populate_from_dataframe(self, df: pd.DataFrame):
        """
        Populate the Tree object with data from a DataFrame.
        
        Args:
        - df (pd.DataFrame): DataFrame containing initial data.
        """        
        self.orapNb = str(df.shape[0])
        self.an = df['accession_number'].tolist()
        self.ap = df['app_number'].tolist()
        self.pn = (df['pub_number'].astype(str) + df['pub_kind'].astype(str)).tolist()
        self.pr = df['priority_numbers'].tolist()
        self.orap = df['orap'].tolist()
        # print("self.orap:", self.orap)
        self.orpr = [''] * df.shape[0]  # Initializing orpr with empty strings
        self.evnt = df['legal_events'].tolist()  # Populate legal events
        self.recInp = self.clean_doc_number(df.source_doc_number[0])  # Access source_doc_number
        # print("Final DataFrame columns:", df.columns)
    
    def create_nested_dict(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Create a nested dictionary from a DataFrame.
    
        Args:
        - df (pd.DataFrame): The DataFrame containing data.
    
        Returns:
        - Dict[str, Any]: Nested dictionary with hierarchical data.
        """        
        # Reset index to ensure continuous integer indexing
        df = df.reset_index(drop=True)

        # Print DataFrame head and columns for debugging
        # print("DataFrame head and tail:")
        # print(df.head(13))
        # print(df.tail())
        # print("\nDataFrame Columns:")
        # print(df.columns)

        # Initialize tree with the DataFrame
        self.populate_from_dataframe(df)

        self.orapNb = df.shape[0]
        # print("self.orapNb:", self.orapNb)
        # print()
    
        listAPs = df['app_number'].tolist() # check listAPs from df dataframe before deleting values later
        # print("listAPs:", listAPs)
        # print()
    
        # Generate listORAPs
        # print("df['orap']:", df['orap'])
        listORAPs = df['orap'].apply(
            lambda x: (
                # print(f"x: {x}, type: {type(x)}") or
                (x.split()[0] if isinstance(x, str) and x.strip() else None)
            )
        ).dropna().tolist()

        # listORAPs = df['orap'].apply(lambda x: x.split()[0] if isinstance(x, str) and x.strip() else None).dropna().tolist()

        # listORAPs contains all oldest applications with potential redundancies
        # print("listORAPs:", listORAPs) 

        if self.orapNb is not None and int(self.orapNb) > 0:            
            if self.db in ["EPODOC", "DOCDB"]:                
                for i in range(len(self.df)):
                    current_row = df.iloc[i]
                    # print(f"Row {i}: {current_row}")  # Print the row to check its content

                    # Safely handle 'accession_number'
                    accession_number = current_row['accession_number'].split(' ')[0] if pd.notna(current_row['accession_number']) else ''
                    # print("accession_number:", accession_number)
                    # Safely handle 'app_number'
                    app_number = current_row['app_number'].split(' ')[0] if pd.notna(current_row['app_number']) else ''
                    # print("app_number:", app_number)
                    # Safely handle 'pub_number'
                    pub_number = str(current_row['pub_number']) + str(current_row['pub_kind']) # current_row['pub_number']
                    # print("pub_number:", pub_number)                    
                    # Safely handle 'orap'
                    orap = current_row['orap'].split(' ')[0] if pd.notna(current_row['orap']) and current_row['orap'] else ''
                    # print("orap:", orap)
                    if (orap == '') and (accession_number != app_number) and ('EP' in accession_number) and ('EP' not in app_number):
                        for j in range(len(df)):
                            if df.iloc[j]['accession_number'] == accession_number:
                                df.iloc[i, df.columns.get_loc('orap')] = df.iloc[j]['orap']
                                break  # Stop searching after finding the match
                                
            # Initialize root dictionary
            root = {'0': 0} # Ensure root['0'] is initialized
            for i in range(len(df), 0, -1):
                prior_row = df.iloc[i-1]
                if i-1 < len(df) and prior_row['app_number'] is not None:                    
                    # Skip rows where 'accession_number' or 'app_number' is None or invalid
                    if pd.isna(prior_row['accession_number']) or pd.isna(prior_row['app_number']) or prior_row['app_number'] == "Unknown0000000":
                        # print(f"Skipping row {i} due to None or invalid values")
                        continue
                    
                    if (pd.notna(prior_row['orap']) and (prior_row['orap'].split(' ')[0] not in listAPs)) or pd.isna(prior_row['orap']) or pd.isnull(prior_row['orap']):                        
                        r = root['0'] + 1  # Increment root index
                        root[r] = {
                            'root_an': prior_row['accession_number'].split(' ')[0] if pd.notna(prior_row['accession_number']) else '',                        
                            'root_ap': prior_row['app_number'].split(' ')[0] if pd.notna(prior_row['app_number']) else '',
                            'root_pn': str(prior_row['pub_number']) + str(prior_row['pub_kind']),
                            'root_pr': prior_row['priority_numbers'],
                            'root_orap': prior_row['orap'].split(' ')[0] if pd.notna(prior_row['orap']) and prior_row['orap'] else '',
                            'root_evnt': prior_row['legal_events']  # Include legal events
                            }

                        # print("i and r:", i-1, r)
                        # print("prior_row['orap']", prior_row['orap'])
                        
                        # Ensure i-1 is within the bounds
                        if i > 0 and prior_row['orap'] == '':
                            # Use .at for positional access
                            if df.at[i-1, 'orap'] == '':
                                # print()
                                # print("df.at[i-1, 'orap']:", df.at[i-1, 'orap'])
                                df.at[i-1, 'orap'] = "noOrap" + str(r)  # Using .at for direct label-based assignment
                                # print("df.at[i-1, 'orap']:", df.at[i-1, 'orap'])
                                prior_row['orap'] = df.at[i-1, 'orap']  # Update the prior_orap if needed
                                # print("prior_orap:", prior_orap)
                                self.orap = df['orap'].tolist()  # Ensure the tree's orap is updated from the DataFrame
                                
                        # Update the dictionary with the latest orap value from DataFrame
                        root[r]['root_orap'] = df.at[i - 1, 'orap'].split(' ')[0] if df.at[i - 1, 'orap'] else ''
                        root['0'] = r
        
        return root, listAPs, listORAPs, df        

class TreeNode:
    def __init__(self, name=None, children=None, **kwargs): 
        self.name = name
        self.children = children or []
        for key, value in kwargs.items():
            setattr(self, key, value)

    def dict_to_object(data):
        if isinstance(data, list):
            return [TreeNode.dict_to_object(item) for item in data]
        elif isinstance(data, dict):
            return TreeNode(**{key: dict_to_object(value) for key, value in data.items()})
        else:
            return data
        