from collections import Counter, defaultdict
import os
from typing import Optional, Dict, Tuple, List, Set
import xml.etree.ElementTree as ET
import pandas as pd
from epo.tipdata.ops import OPSClient, models, exceptions
import re
from IPython.display import display
from patent_analysis.helpers import convert_japanese_priority_number, sort_orap
from pprint import pprint
import logging
# logging.basicConfig(level=logging.DEBUG)

class FamilyRecord:
    """
    Represents family record in the European Patent Office (EPO) database.
    Provides methods to fetch, parse, and process patent family data.
    """
    # Put more fundamental/lower-level methods earlier in the class definition:
    def __init__(self, reference_type: str, doc_number: str, country: Optional[str] = None, kind: Optional[str] = None, constituents: Optional[str] = None, countrySelection=None, output_type: Optional[str] = None, ):  # xml_tree: Optional[str] = None, 
        self.reference_type: str = reference_type        
        """
        Initialize the FamilyRecord object.
        
        Args:
        - reference_type (str): The type of reference (e.g., 'publication', 'application').
        - doc_number (str): The document number.
        - country (str): The country code (e.g., 'EP' for Europe).
        - kind (Optional[str]): The kind code (e.g., 'A' for application, 'B' for publication).
        """        
        self.client: OPSClient = OPSClient(key=os.getenv("OPS_KEY"), secret=os.getenv("OPS_SECRET"))
        self.reference_type: str = reference_type
        self.doc_number: str = doc_number        
        self.source_doc_number: Optional[str] = self.compute_source_doc_number(doc_number, country, kind)
        self.country: Optional[str] = country
        self.kind: Optional[str] = kind
        self.constituents: Optional[List[str]] = ["legal", "biblio"] if constituents is None else (
            [constituents] if isinstance(constituents, str) else constituents
        )
        self.countrySelection = countrySelection if isinstance(countrySelection, list) else [countrySelection]
        self.output_type: str = output_type
        self.ccw_to_wo_mapping = {}
        self.familyRoot = None
        self.xml_tree = None
        self.data = {}  # Initialize the data attribute
        self.df, self.DropdownCC = self._initialize_dataframe()
        if self.df is not None:
            self.df['source_doc_number'] = self.source_doc_number
        else:
            print("Error: DataFrame is empty or failed to initialize.")
            
    def compute_source_doc_number(self, doc_number: str, country: str, kind: Optional[str]) -> str:
        """
        Compute the source document number by concatenating country code, document number, and kind code.
        
        Args:
        - doc_number (str): The document number.
        - country (str): The country code.
        - kind (Optional[str]): The kind code.

        Returns:
        - str: The computed source document number.
        """        
        source_doc_number = f"{country}{doc_number}"  # Start with concatenating country code and doc_number
        if kind:
            source_doc_number = f"{country}{doc_number}{kind}"
        return source_doc_number

    def _fetch_xml_tree(self, reference_type: str, doc_number: str, country: str, kind: Optional[str] = None, constituents: Optional[str] = None, output_type: Optional[str] = None) -> Optional[str]:
        """_fetch_xml_tree
        Fetch the XML data from the EPO database.
        
        Args:
        - reference_type (str): The type of reference.
        - doc_number (str): The document number.
        - country (str): The country code.
        - kind (Optional[str]): The kind code.

        Returns:
        - str: The fetched XML data as a string.
        """        
        try:
            input_model = models.Docdb(doc_number, country, kind) if kind else models.Epodoc(f"{country}{doc_number}")
            # print("reference_type:", reference_type)
            # print("input_model, doc_number, country, kind:", input_model, doc_number, country, kind)
            # print("constituents:", constituents)
            # print("output_type:", output_type)
            self.xml_tree = self.client.family(reference_type=reference_type, input=input_model, constituents=constituents, output_type=output_type)
            return self.xml_tree
        except exceptions.HTTPError as e:
            print(f"HTTPError: {e}")
            return None

    # This is a core data-fetching method. It should come before methods that depend on the XML data.
    def get_family_root(self) -> Optional[ET.Element]:
        if self.xml_tree is None:
            print("Error: self.xml_tree is not initialized.")
            return None
        return ET.fromstring(self.xml_tree)

    def _parse_xml(self) -> Optional[ET.Element]:
        """Parses XML from self.xml_tree and returns the root element."""
        if self.xml_tree is None:
            print("Error: self.xml_tree is None.")
            return None
        try:
            return ET.fromstring(self.xml_tree)  # Parse the XML string
        except ET.ParseError as e:
            print(f"XML parsing failed: {e}")
            return None

    def _get_namespace_map(self) -> Dict[str, str]:
        """Returns the namespace map for XML parsing."""
        return {
            'ops': 'http://ops.epo.org',
            'exchange': 'http://www.epo.org/exchange'
        }
        
    def get_ns_prefix(self, tag, nsmap):
        """
        Resolves the namespace prefix and builds a fully qualified tag.

        Args:
            tag (str): The tag with a namespace prefix (e.g., "ops:family-member").
            nsmap (dict): A dictionary mapping namespace prefixes to their URIs.

        Returns:
            str: The fully qualified tag with the namespace URI.
    
        Raises:
            ValueError: If the tag does not contain a prefix or the prefix is not found in nsmap.
        """
        parts = tag.split(':')
        if len(parts) != 2:
            raise ValueError(f"Invalid tag format: {tag}. Expected format 'prefix:tag'.")
    
        prefix, local_name = parts
        namespace_uri = nsmap.get(prefix)
        if not namespace_uri:
            raise ValueError(f"Namespace prefix '{prefix}' not found in nsmap.")
    
        return f"{{{namespace_uri}}}{local_name}"

    # Utility for XML parsing. Parses the XML tree and returns a list of family members.
    def _extract_family_members(self):
        """Extracts family members from the XML tree."""
        return self.familyRoot.findall(".//{http://ops.epo.org}family-member")

    def _parse_application_data(self, family_member, nsmap) -> Tuple[str, Dict]:
        """Extracts application details such as country, kind, number, and date."""
        app_number_full = None
        app_data = {}

        for application_reference in family_member.findall(f".//{self.get_ns_prefix('exchange:application-reference', nsmap)}"):
            app_doc_number = application_reference.find(f".//{self.get_ns_prefix('exchange:doc-number', nsmap)}")
            app_country = application_reference.find(f".//{self.get_ns_prefix('exchange:country', nsmap)}")
            app_kind = application_reference.find(f".//{self.get_ns_prefix('exchange:kind', nsmap)}")
            app_date = application_reference.find(f".//{self.get_ns_prefix('exchange:date', nsmap)}")

            app_number = app_doc_number.text if app_doc_number is not None else None
            app_country_text = app_country.text if app_country is not None else 'Unknown'
            app_kind_text = app_kind.text if app_kind is not None else 'Unknown'
            app_date_text = app_date.text if app_date is not None else None
            app_number_full = f"{app_country_text}{app_number}"

            if app_number_full.startswith('EP'):
                year_prefix = '19' if int(app_number_full[2:4]) > 50 else '20'
                app_number_full = f"EP{year_prefix}{app_number_full[2:11]}"

            accession_number = app_number_full
        
            # Handle WO (PCT) mappings
            if app_kind_text == 'W':
                accession_number = f"{app_country_text}{app_kind_text}{app_number}"
                year_prefix = '19' if int(app_number[:2]) > 50 else '20'
                app_number_full = f"WO{year_prefix}{app_number[:2]}{app_country_text}{app_number[2:]}"
                self.ccw_to_wo_mapping[accession_number] = (app_number_full, app_date_text)

            # Include additional fields
            app_data = {
                'accession_number': accession_number,
                'app_number': app_number_full,
                'app_country': app_country_text,
                'app_kind': app_kind_text,
                'app_date': app_date_text,
                'priority_numbers': set(),  # Placeholder for priority numbers
                'orap': set(),               # Placeholder for other application references
                'priority_dates': {},        # Placeholder for priority dates
                'pub_number': '',
                'pub_country': '',
                'pub_kind': '',
                'pub_date': '',
                'legal_events': []
            }

        return app_number_full, app_data, app_kind_text
        
    # Sorting function
    def custom_sort_key(self, item):
        if 'W' in item:
            return (0, item)  # Highest priority
        elif 'EP' in item:
            return (1, item)  # Second priority
        else:
            return (2, item)  # Lowest priority
            
    def _parse_priority_claims(self, family_member, nsmap, data, app_number_full, app_data, app_kind_text):
        for priority_claim in family_member.findall(f".//{self.get_ns_prefix('exchange:priority-claim', nsmap)}"):
            elements = { 
                key: priority_claim.find(f".//{self.get_ns_prefix(f'exchange:{key}', nsmap)}")
                for key in ['doc-number', 'country', 'kind', 'date']
            }

            if elements['doc-number'] is not None:
                priority_doc_number = elements['doc-number'].text
                priority_country = elements['country'].text if elements['country'] is not None else 'Unknown'
                priority_kind = elements['kind'].text if elements['kind'] is not None else ''
                priority_date = elements['date'].text if elements['date'] is not None else ''

                priority_doc_number_full = f"{priority_country}{priority_doc_number}"
                if priority_doc_number_full.startswith('EP'):
                    year_prefix = '19' if int(priority_doc_number_full[2:4]) > 50 else '20'
                    priority_doc_number_full = f"EP{year_prefix}{priority_doc_number_full[2:11]}"
                if priority_kind == 'W':
                    priority_doc_number_full = f"{priority_country}{priority_kind}{priority_doc_number}"
            
                priority_doc_number_full = convert_japanese_priority_number(priority_doc_number_full)

                if app_number_full in data:
                    # Ensure 'orap' and 'priority_numbers' are sets
                    if not isinstance(app_data.get('orap'), set):
                        app_data['orap'] = set(app_data.get('orap', []))
                    if not isinstance(app_data.get('priority_numbers'), set):
                        app_data['priority_numbers'] = set(app_data.get('priority_numbers', []))
                    if 'priority_dates' not in app_data:
                        app_data['priority_dates'] = {}
                        
                    if priority_doc_number_full not in app_data['orap']:
                        if app_kind_text == 'W' or priority_country == 'EP' or (
                            len(priority_doc_number_full) >= 3 and priority_doc_number_full[2] == 'W'
                        ):
                            app_data['priority_numbers'].add(priority_doc_number_full)
                            app_data['priority_dates'][priority_doc_number_full] = priority_date

                            if priority_country == 'EP' or (
                                len(priority_doc_number_full) >= 3 and priority_doc_number_full[2] == 'W'
                            ):
                                app_data['orap'].add(priority_doc_number_full)
                            elif app_kind_text == 'W':
                                app_data['orap'].add(app_number_full)

                            app_data['priority_numbers'] = sorted(app_data['priority_numbers'], key=self.custom_sort_key)
                            app_data['orap'] = sorted(app_data['orap'], key=self.custom_sort_key)

    def _parse_publication_data(self, family_member, nsmap, data, app_number_full, app_data, country_codes):            
        for publication_reference in family_member.findall(f".//{self.get_ns_prefix('exchange:publication-reference', nsmap)}"):
            pub_attrs = {
                "pub_number": publication_reference.find(f".//{self.get_ns_prefix('exchange:doc-number', nsmap)}"),
                "pub_country": publication_reference.find(f".//{self.get_ns_prefix('exchange:country', nsmap)}"),
                "pub_kind": publication_reference.find(f".//{self.get_ns_prefix('exchange:kind', nsmap)}"),
                "pub_date": publication_reference.find(f".//{self.get_ns_prefix('exchange:date', nsmap)}")
            }
        
            # Extract text values, ensuring defaults where necessary
            pub_data = {key: (elem.text if elem is not None else None) for key, elem in pub_attrs.items()}
            pub_data["pub_country"] = pub_data["pub_country"] or "Unknown"
        
            if pub_data["pub_number"]:
                pub_data["pub_number"] = f"{pub_data['pub_country']}{pub_data['pub_number']}"

            if app_number_full in data:
                app_data.update({k: v for k, v in pub_data.items() if v})  # Update only non-empty values
                country_codes.add(pub_data["pub_country"])
    
    def _parse_legal_events(self, family_member, nsmap, data, app_number_full, app_data): 
        for legal_event in family_member.findall(f".//{self.get_ns_prefix('ops:legal', nsmap)}"):
            legal_event_data = {
                'legal_event_code': legal_event.attrib.get('code', ''),
                'legal_event_desc': legal_event.attrib.get('desc', ''),
                'legal_event_date_migr': legal_event.attrib.get('dateMigr', ''),
                'legal_event_infl': legal_event.attrib.get('infl', ''),
                'legal_event_texts': [pre.text.strip() for pre in legal_event.findall('.//{http://ops.epo.org}pre') if pre.text],
                'nested_data': None  # Ensures 'nested_data' exists
            }

            if app_number_full in data:
                app_data['legal_events'].append(legal_event_data)

    def _process_family_member(self, family_member: ET.Element, nsmap: Dict[str, str], data: Dict, country_codes: Set[str]):
        """Parses and processes data for a single family member."""
        app_number_full, app_data, app_kind_text = self._extract_application_data(family_member, nsmap)
    
        if not app_number_full:
            return  # Skip processing if no valid application data

        data[app_number_full] = app_data
        country_codes.add(app_data['app_country'])
        data[app_number_full]['priority_numbers'].update(app_data.get('priority_numbers', set()))
        data[app_number_full]['orap'].update(app_data.get('orap', set()))
    
        self._parse_priority_claims(family_member, nsmap, data, app_number_full, app_data, app_kind_text)
        self._parse_publication_data(family_member, nsmap, data, app_number_full, app_data, country_codes)
        self._parse_legal_events(family_member, nsmap, data, app_number_full, app_data)

    def _add_missing_countries(self, data: Dict[str, Dict], country_codes: Set[str]):
        """Ensures all selected countries are represented in the data."""
        missing_countries = set(self.countrySelection) - country_codes
        for country in missing_countries:
            data[f"{country or 'Unknown'}0000000"] = {
                'accession_number': '',
                'app_number': f"{country or 'Unknown'}0000000",
                'app_country': country,
                'app_kind': None,
                'app_date': None,
                'priority_numbers': set(),
                'orap': set(),
                'orap_history': [],
                'priority_dates': {},
                'legal_events': []
            }

    def _create_dataframe(self, data: Dict[str, Dict]) -> pd.DataFrame:
        """Flattens extracted data into a pandas DataFrame."""
        flattened_data = [
            {
                **value,
                'priority_numbers': sorted(value['priority_numbers'], key=self.custom_sort_key),
                'orap': sorted(value['orap'], key=self.custom_sort_key),
                'legal_events': [
                    {
                        'code': event.get('legal_event_code', ''),
                        'desc': event.get('legal_event_desc', ''),
                        'dateMigr': event.get('legal_event_date_migr', ''),
                        'infl': event.get('legal_event_infl', ''),
                        'texts': ' | '.join(event.get('legal_event_texts', [])),
                        'nested_data': event.get('nested_data', None)
                    }
                    for event in value['legal_events']
                ]
            }
            for value in data.values()
        ]
    
        df = pd.DataFrame(flattened_data)
        df = df[df['app_number'] != "Unknown0000000"]  # Remove placeholders
    
        if df.empty:
            print("Warning: DataFrame is empty after filtering out 'Unknown0000000'.")
    
        return df

    def _parse_xml_to_dataframe(self) -> Optional[pd.DataFrame]:
        """Parses the XML, processes family members, and returns a DataFrame."""
        self.familyRoot = self._parse_xml()
        if self.familyRoot is None:
            return None, []

        nsmap = self._get_namespace_map()
        data = defaultdict(lambda: {
            'accession_number': '',
            'app_number': '',
            'app_country': '',
            'app_kind': None,
            'app_date': None,
            'priority_numbers': set(),
            'orap': set(),
            'orap_history': [],
            'priority_dates': {},
            'legal_events': []
        })
        country_codes = set()
    
        family_members = self._get_family_members()
        print(f"Extracted {len(family_members)} family members.")

        for family_member in family_members:
            self._process_family_member(family_member, nsmap, data, country_codes)

        self._add_missing_countries(data, country_codes)
        df = self._create_dataframe(data)
    
        return df, sorted(country_codes)

    def _initialize_dataframe(self, country: Optional[str] = None, xml_tree: Optional[str] = None, ) -> pd.DataFrame:
        country = country if country else self.country
        try:
            self.xml_tree = self._fetch_xml_tree(self.reference_type, self.doc_number, self.country, self.kind, self.constituents, self.output_type)
            if self.xml_tree is None:
                return pd.DataFrame(), []
            # pprint(self.xml_tree[:20000])
            df, dropdown_cc = self._parse_xml_to_dataframe()
            
            # Populate the `data` attribute based on `self.df`
            if df is not None and not df.empty:
                # Populate the `data` attribute based on `df`
                for _, row in df.iterrows():
                    app_number_full = row['app_number']
                    if app_number_full not in self.data:
                        self.data[app_number_full] = {
                            'orap': set(),
                            'priority_numbers': set(),
                            'priority_dates': {}
                        }
            else:
                print("Error: DataFrame is empty after parsing XML.")
                    
            # display(df) # to use in priority for df display
            return df, dropdown_cc
        except Exception as e:
            print(f"Error initializing DataFrame: {e}")
            return pd.DataFrame(), []
            
    def _get_family_members(self) -> List[ET.Element]:
        """Extracts and returns a list of family members from the parsed XML."""
        return list(self._extract_family_members())

    def _extract_application_data(self, family_member: ET.Element, nsmap: Dict[str, str]) -> Tuple[Optional[str], Dict, Optional[str]]:
        """Extracts application data and returns a tuple (app_number_full, app_data, app_kind_text)."""
        app_number_full, app_data, app_kind_text = self._parse_application_data(family_member, nsmap)
    
        if not app_number_full:
            print("Skipping family member: No app_number_full")
            return None, {}, None
    
        app_data['app_country'] = app_data.get('app_country', 'Unknown')  # Ensure app_country is set  
        return app_number_full, app_data, app_kind_text            

    def get_filtered_application_numbers(self, additional_countries: Optional[str] = None) -> Optional[pd.DataFrame]:
        # print("get_filtered_application_numbers was called with:", additional_countries)
        if self.df is not None:
            if additional_countries is None:
                additional_countries = []                
            if 'app_country' not in self.df.columns:
                 print("Column 'app_country' is missing from the DataFrame.")
                 return pd.DataFrame()  # or handle appropriately
            else:
                condition_ep = (self.df['app_country'] == 'EP') & (self.df['app_kind'] == 'A')
                condition_jp = (self.df['app_country'] == 'JP') & (
                    (self.df['app_kind'] == 'W') | self.df['app_number'].str.contains(r'W$|W.*$')
                )
                condition_us = (self.df['app_country'] == 'US') & (
                    (self.df['app_kind'] == 'W') | self.df['app_number'].str.contains(r'W$|W.*$')
                )                
                condition_xx = self.df['app_country'].isin(self.countrySelection) if self.countrySelection else False
                
                # Apply filters
                filtered_df = self.df[condition_ep | condition_jp | condition_us | condition_xx]
                if not filtered_df.empty:
                    # Ensure orap columns are added to the DataFrame
                    if 'orap' not in filtered_df.columns:
                        filtered_df['orap'] = None
                    if 'orap_history' not in filtered_df.columns:
                        filtered_df['orap_history'] = None
                        
                    filtered_df = filtered_df.apply(
                        lambda row: sort_orap(row, self.ccw_to_wo_mapping, self.data), 
                        axis=1
                    )
                    # display(filtered_df)
                return filtered_df          
        return None
    
    def process_fami_record(self, additional_countries: Optional[str] = None) -> None:
        """
        Process and display the family record.
        Retrieves filtered application numbers and prints them.

        Returns:
        - Optional[Tuple[pd.DataFrame, str]]: Tuple containing the filtered DataFrame and the source type, or None if no data.
        """        
        # print("process_fami_record with additional_countries:", additional_countries)
        source = 'Epodoc' if self.kind is None else 'Docdb'

        # Example usage:
        # Use the method to get filtered publication numbers
        result = self.get_filtered_application_numbers(additional_countries)
        if result is not None and not result.empty:
            # print(f"Filtered Publication numbers (Source: {source}):")
            # display(result)
            return result, source
        else:
            print("DataFrame is empty. No data to process.")
            return None

    def convert_to_hashable(self, value):
        """
        Convert the given value to a hashable type.
        """
        if isinstance(value, dict):
            # Convert dictionary to a sorted tuple of (key, value) tuples
            return tuple(sorted((k, self.convert_to_hashable(v)) for k, v in value.items()))
        elif isinstance(value, (list, set)):
            # Convert list or set to a sorted tuple
            return tuple(sorted(self.convert_to_hashable(x) for x in value))
        else:
            # Return the value as is if it's already hashable
            return value

    def updateFamily(self) -> None:
        """
        Update the FamilyRecord with new data.
        """     
        # print("Update FamilyRecord")
        try:
            # Fetch XML Tree
            self.reference_type, self.doc_number, self.country, self.kind, self.constituents
            self.xml_tree = self._fetch_xml_tree(self.reference_type, self.doc_number, self.country, self.kind, self.constituents)
            # self.xml_tree = xml_tree
            if self.xml_tree is None:
                return pd.DataFrame(), []

            # Parse XML to DataFrame
            df, dropdown_cc = self._parse_xml_to_dataframe()  # xml_tree
            display(df)
            if not df.empty:
                print("DataFrame is not empty. Processing DataFrame...")
                self.df = df
                self.df['source_doc_number'] = self.source_doc_number
                self.DropdownCC = dropdown_cc

                # Convert all non-hashable types in the DataFrame to hashable types
                for col in self.df.columns:
                    self.df[col] = self.df[col].apply(self.convert_to_hashable)

                # Verify if any unhashable objects still exist in the DataFrame
                for col in self.df.columns:
                    unhashable_count = self.df[col].apply(lambda x: isinstance(x, dict) or isinstance(x, (list, set))).sum()
                    if unhashable_count > 0:
                        print(f"Warning: Column '{col}' still contains {unhashable_count} unhashable items.")
                        print("Here are some examples:")
                        print(self.df[col][self.df[col].apply(lambda x: isinstance(x, dict) or isinstance(x, (list, set)))].head())

                # Attempt to drop duplicates
                print("Dropping duplicates...")
                self.df = self.df.drop_duplicates()

        except Exception as e:
            print(f"Error updating FamilyRecord: {e}")
            import traceback
            print("Traceback:")
            traceback.print_exc()  # This will print the full traceback including the line number

