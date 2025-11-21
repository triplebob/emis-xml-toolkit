"""
Criterion parsing utilities for EMIS XML
Handles parsing of search criteria and column filters
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from .base_parser import XMLParserBase, get_namespaces
from .value_set_parser import parse_value_set
from .restriction_parser import parse_restriction
from .linked_criteria_parser import parse_linked_criterion
from ..common.error_handling import handle_xml_parsing_error, safe_execute, create_error_context


@dataclass
class SearchCriterion:
    """Individual search criterion with its conditions"""
    id: str
    table: str
    display_name: str
    description: Optional[str]
    negation: bool
    value_sets: List[Dict]
    column_filters: List[Dict]
    restrictions: List[Any]  # SearchRestriction objects
    exception_code: Optional[str] = None
    linked_criteria: List['SearchCriterion'] = field(default_factory=list)


class CriterionParser(XMLParserBase):
    """Parser for search criteria elements"""
    
    @staticmethod
    def is_patient_demographics_column(column_name: str) -> bool:
        """
        Detect patient demographics/LSOA columns in a future-proof way.
        
        Handles patterns like:
        - LONDON_LOWER_AREA_2011 (current)
        - LONDON_LOWER_AREA_2019 (potential)
        - LONDON_LOWER_AREA_2021 (future)

        """
        if not column_name:
            return False
        
        column_upper = column_name.upper()
        
        # LSOA pattern: contains LOWER_AREA followed by a year
        if 'LOWER_AREA' in column_upper and any(year in column_upper for year in ['2011', '2015', '2021', '2031']):
            return True
            
        # Future patient demographics patterns can be added here
        # e.g., 'MSOA_', 'WARD_', 'POSTCODE_AREA_' etc.
        
        return False
    
    def parse_criterion(self, criterion_elem: ET.Element) -> Optional[SearchCriterion]:
        """Parse individual search criterion"""
        try:
            criterion_id = self.parse_child_text(criterion_elem, 'id', 'Unknown')
            table = self.parse_child_text(criterion_elem, 'table', 'Unknown')
            display_name = self.parse_child_text(criterion_elem, 'displayName', 'Unknown')
            description = self.parse_child_text(criterion_elem, 'description') or None
            exception_code = self.parse_child_text(criterion_elem, 'exceptionCode') or None
            
            # Parse negation - handle both namespaced and non-namespaced
            negation_elem = self.find_element_both(criterion_elem, 'negation')
            negation = self.get_text(negation_elem).lower() == 'true'
            
            # Parse value sets - only from main filterAttribute, not from restrictions
            value_sets = []
            all_valuesets = []
            
            # Find filterAttribute elements first
            filter_attrs = self.find_elements(criterion_elem, 'filterAttribute') + self.find_elements(criterion_elem, 'emis:filterAttribute')
            
            for filter_attr in filter_attrs:
                # Find value sets within filterAttribute, but be more specific about the path
                # Look for value sets under columnValue elements, but not under restriction elements
                
                # Find columnValue elements that are direct children of filterAttribute (not under restrictions)
                namespaced_columns = self.find_elements(filter_attr, 'emis:columnValue')
                non_namespaced_columns = filter_attr.findall('columnValue')
                all_columns = non_namespaced_columns + [c for c in namespaced_columns if c not in non_namespaced_columns]
                
                for col_elem in all_columns:
                    # Find value sets within this columnValue
                    namespaced_vs = self.find_elements(col_elem, 'emis:valueSet')
                    non_namespaced_vs = col_elem.findall('valueSet')
                    col_valuesets = non_namespaced_vs + [v for v in namespaced_vs if v not in non_namespaced_vs]
                    
                    for vs in col_valuesets:
                        if vs not in all_valuesets:
                            all_valuesets.append(vs)
            
            for valueset_elem in all_valuesets:
                value_set = parse_value_set(valueset_elem, self.namespaces)
                if value_set:
                    value_sets.append(value_set)
            
            # Parse value sets from baseCriteriaGroup structures
            # Handle both namespaced and non-namespaced baseCriteriaGroup elements
            namespaced_base_groups = self.find_elements(criterion_elem, 'emis:baseCriteriaGroup')
            non_namespaced_base_groups = criterion_elem.findall('baseCriteriaGroup')
            all_base_groups = non_namespaced_base_groups + [bg for bg in namespaced_base_groups if bg not in non_namespaced_base_groups]
            
            
            for base_group in all_base_groups:
                # Find definition element within baseCriteriaGroup
                definition_elem = self.find_element_both(base_group, 'definition')
                if definition_elem is not None:
                    # Find criteria element within definition
                    criteria_elem = self.find_element_both(definition_elem, 'criteria')
                    if criteria_elem is not None:
                        # Find all nested criterion elements
                        nested_criteria = self.find_elements(criteria_elem, 'criterion') + self.find_elements(criteria_elem, 'emis:criterion')
                        
                        for nested_criterion in nested_criteria:
                            # Extract value sets from nested criterion
                            nested_filter_attrs = self.find_elements(nested_criterion, 'filterAttribute') + self.find_elements(nested_criterion, 'emis:filterAttribute')
                            
                            for nested_filter_attr in nested_filter_attrs:
                                # Find columnValue elements in nested filterAttribute
                                nested_columns = self.find_elements(nested_filter_attr, 'columnValue') + self.find_elements(nested_filter_attr, 'emis:columnValue')
                                
                                for nested_col_elem in nested_columns:
                                    # Find value sets within nested columnValue
                                    nested_namespaced_vs = self.find_elements(nested_col_elem, 'emis:valueSet')
                                    nested_non_namespaced_vs = nested_col_elem.findall('valueSet')
                                    nested_valuesets = nested_non_namespaced_vs + [v for v in nested_namespaced_vs if v not in nested_non_namespaced_vs]
                                    
                                    for nested_vs in nested_valuesets:
                                        if nested_vs not in all_valuesets:  # Avoid duplicates
                                            all_valuesets.append(nested_vs)  # Track the element
                                            nested_value_set = parse_value_set(nested_vs, self.namespaces)
                                            if nested_value_set:
                                                value_sets.append(nested_value_set)
            
            # Parse value sets from testAttribute sections within restrictions
            # This handles the pattern: <restriction><testAttribute><columnValue><valueSet>
            for filter_attr in filter_attrs:
                namespaced_restrictions = self.find_elements(filter_attr, 'emis:restriction')
                non_namespaced_restrictions = filter_attr.findall('restriction')
                all_restrictions = non_namespaced_restrictions + [r for r in namespaced_restrictions if r not in non_namespaced_restrictions]
                
                for restriction_elem in all_restrictions:
                    # Find testAttribute elements within restrictions
                    namespaced_test_attrs = self.find_elements(restriction_elem, 'emis:testAttribute')
                    non_namespaced_test_attrs = restriction_elem.findall('testAttribute')
                    all_test_attrs = non_namespaced_test_attrs + [t for t in namespaced_test_attrs if t not in non_namespaced_test_attrs]
                    
                    for test_attr_elem in all_test_attrs:
                        # Find columnValue elements within testAttribute
                        namespaced_cols = self.find_elements(test_attr_elem, 'emis:columnValue')
                        non_namespaced_cols = test_attr_elem.findall('columnValue')
                        all_cols = non_namespaced_cols + [c for c in namespaced_cols if c not in non_namespaced_cols]
                        
                        for col_elem in all_cols:
                            # Find value sets within these columnValue elements
                            namespaced_vs = self.find_elements(col_elem, 'emis:valueSet')
                            non_namespaced_vs = col_elem.findall('valueSet')
                            col_valuesets = non_namespaced_vs + [v for v in namespaced_vs if v not in non_namespaced_vs]
                            
                            for vs in col_valuesets:
                                if vs not in all_valuesets:  # Avoid duplicates
                                    all_valuesets.append(vs)
                                    test_attr_value_set = parse_value_set(vs, self.namespaces)
                                    if test_attr_value_set:
                                        value_sets.append(test_attr_value_set)
            # Parse library items (internal EMIS libraries) - handle both namespaced and non-namespaced
            namespaced_library = self.find_elements(criterion_elem, './/emis:libraryItem')
            non_namespaced_library = criterion_elem.findall('.//libraryItem')
            all_library = non_namespaced_library + [l for l in namespaced_library if l not in non_namespaced_library]
            
            for library_elem in all_library:
                library_item = self._parse_library_item(library_elem)
                if library_item:
                    value_sets.append(library_item)  # Add to value_sets for compatibility
            
            # Parse column filters - handle both namespaced and non-namespaced
            column_filters = []
            namespaced_columns = self.find_elements(criterion_elem, './/emis:columnValue')
            non_namespaced_columns = criterion_elem.findall('.//columnValue')
            all_columns = non_namespaced_columns + [c for c in namespaced_columns if c not in non_namespaced_columns]
            
            for column_elem in all_columns:
                column_filter = self.parse_column_filter(column_elem)
                if column_filter:
                    column_filters.append(column_filter)
            
            
            # Parse restrictions - handle both namespaced and non-namespaced
            # Look for restrictions in multiple paths: direct under criterion AND under filterAttribute > columnValue
            restrictions = []
            
            # Direct restrictions under criterion
            namespaced_restrictions = self.find_elements(criterion_elem, 'emis:restriction')
            non_namespaced_restrictions = criterion_elem.findall('restriction')
            direct_restrictions = non_namespaced_restrictions + [r for r in namespaced_restrictions if r not in non_namespaced_restrictions]
            
            # Restrictions under filterAttribute (for List Reports) - handle both patterns:
            # Pattern 1: filterAttribute > columnValue > restriction
            # Pattern 2: filterAttribute > restriction (as sibling to columnValue)
            nested_restrictions = []
            for filter_attr in filter_attrs:
                # Pattern 1: restrictions under columnValue
                namespaced_columns = self.find_elements(filter_attr, 'emis:columnValue')
                non_namespaced_columns = filter_attr.findall('columnValue')
                all_columns = non_namespaced_columns + [c for c in namespaced_columns if c not in non_namespaced_columns]
                
                for col_elem in all_columns:
                    namespaced_rest = self.find_elements(col_elem, 'emis:restriction')
                    non_namespaced_rest = col_elem.findall('restriction')
                    col_restrictions = non_namespaced_rest + [r for r in namespaced_rest if r not in non_namespaced_rest]
                    nested_restrictions.extend(col_restrictions)
                
                # Pattern 2: restrictions directly under filterAttribute (as siblings to columnValue)
                namespaced_filter_rest = self.find_elements(filter_attr, 'emis:restriction')
                non_namespaced_filter_rest = filter_attr.findall('restriction')
                filter_restrictions = non_namespaced_filter_rest + [r for r in namespaced_filter_rest if r not in non_namespaced_filter_rest]
                nested_restrictions.extend(filter_restrictions)
            
            # Parse all found restrictions
            all_restrictions = direct_restrictions + nested_restrictions
            for restriction_elem in all_restrictions:
                restriction = parse_restriction(restriction_elem, self.namespaces)
                if restriction:
                    restrictions.append(restriction)
            
            # Parse linked criteria (for complex relationships) - handle both namespaced and non-namespaced
            linked_criteria = []
            namespaced_linked = self.find_elements(criterion_elem, './/emis:linkedCriterion')
            non_namespaced_linked = criterion_elem.findall('.//linkedCriterion')
            all_linked = non_namespaced_linked + [l for l in namespaced_linked if l not in non_namespaced_linked]
            
            for linked_elem in all_linked:
                linked_criterion = parse_linked_criterion(linked_elem, self.namespaces)
                if linked_criterion:
                    linked_criteria.append(linked_criterion)
            
            return SearchCriterion(
                id=criterion_id,
                table=table,
                display_name=display_name,
                description=description,
                negation=negation,
                value_sets=value_sets,
                column_filters=column_filters,
                restrictions=restrictions,
                exception_code=exception_code,
                linked_criteria=linked_criteria
            )
        except Exception as e:
            error = handle_xml_parsing_error("parse_criterion", e, "criterion")
            # Log error but don't raise to maintain backward compatibility
            return None
    
    def parse_column_filter(self, column_elem: ET.Element) -> Optional[Dict]:
        """Parse column filter information"""
        try:
            # Parse multiple columns if present (EMISINTERNAL pattern: AUTHOR + CURRENTLY_CONTRACTED)
            # Handle both namespaced and non-namespaced column elements
            namespaced_col_elements = self.find_elements(column_elem, 'emis:column')
            non_namespaced_col_elements = column_elem.findall('column')
            column_elements = non_namespaced_col_elements + [c for c in namespaced_col_elements if c not in non_namespaced_col_elements]
            
            if len(column_elements) > 1:
                # Multiple columns - create list
                columns = [self.get_text(col_elem) for col_elem in column_elements if self.get_text(col_elem)]
                column_value = columns
            else:
                # Single column - use string for backward compatibility
                column_value = self.parse_child_text(column_elem, 'column')
            
            result = {
                'id': self.parse_child_text(column_elem, 'id'),
                'column': column_value,
                'display_name': self.parse_child_text(column_elem, 'displayName'),
                'in_not_in': self.parse_child_text(column_elem, 'inNotIn')
            }
            
            # Tag patient demographics columns for special handling
            if isinstance(column_value, str) and self.is_patient_demographics_column(column_value):
                result['column_type'] = 'patient_demographics'
                result['demographics_type'] = 'LSOA'  # Currently only LSOA, can expand for MSOA, etc.
            elif isinstance(column_value, list):
                # Handle multiple columns (check if any are patient demographics)
                demographics_columns = [col for col in column_value if self.is_patient_demographics_column(col)]
                if demographics_columns:
                    result['column_type'] = 'patient_demographics'
                    result['demographics_type'] = 'LSOA'
            
            # Parse range values - handle both namespaced and non-namespaced
            range_elem = self.find_element_both(column_elem, 'rangeValue')
            if range_elem is not None:
                result['range'] = self._parse_range_value(range_elem)
            
            # Parse singleValue for temporal variable patterns and geographical values
            single_value_elem = self.find_element_both(column_elem, 'singleValue')
            if single_value_elem is not None:
                variable_elem = self.find_element_both(single_value_elem, 'variable')
                if variable_elem is not None:
                    value = self.parse_child_text(variable_elem, 'value')
                    unit = self.parse_child_text(variable_elem, 'unit')
                    relation = self.parse_child_text(variable_elem, 'relation')
                    
                    # Check if this is a patient demographics value (no unit/relation, just a string value)
                    if value and not unit and not relation and result.get('column_type') == 'patient_demographics':
                        result['range'] = {
                            'from': {
                                'operator': 'IN',
                                'value': value,
                                'value_type': 'demographics_code'  # Tag for special handling
                            }
                        }
                    else:
                        # Standard temporal variable pattern
                        result['range'] = {
                            'from': {
                                'operator': 'IN',  # Default operator for temporal variables
                                'value': value,
                                'unit': unit,
                                'relation': relation
                            }
                        }
                else:
                    # Fallback: treat singleValue content directly as value
                    value = self.get_text(single_value_elem)
                    range_data = {
                        'from': {
                            'operator': 'IN',
                            'value': value
                        }
                    }
                    # Tag patient demographics values for special handling
                    if result.get('column_type') == 'patient_demographics':
                        range_data['from']['value_type'] = 'demographics_code'
                    result['range'] = range_data
            
            # Parse parameter information - handle both namespaced and non-namespaced
            param_elem = self.find_element_both(column_elem, 'parameter')
            if param_elem is not None:
                result['parameter'] = self._parse_parameter(param_elem)
            
            # Parse value sets within column filters - handle both namespaced and non-namespaced
            value_sets = []
            namespaced_vs = self.find_elements(column_elem, './/emis:valueSet')
            non_namespaced_vs = column_elem.findall('.//valueSet')
            all_vs = non_namespaced_vs + [v for v in namespaced_vs if v not in non_namespaced_vs]
            
            for valueset_elem in all_vs:
                value_set = parse_value_set(valueset_elem, self.namespaces)
                if value_set:
                    value_sets.append(value_set)
            
            # Parse library items within column filters - handle both namespaced and non-namespaced
            namespaced_lib = self.find_elements(column_elem, './/emis:libraryItem')
            non_namespaced_lib = column_elem.findall('.//libraryItem')
            all_lib = non_namespaced_lib + [l for l in namespaced_lib if l not in non_namespaced_lib]
            
            for library_elem in all_lib:
                library_item = self._parse_library_item(library_elem)
                if library_item:
                    value_sets.append(library_item)  # Add to value_sets for compatibility
            
            if value_sets:
                result['value_sets'] = value_sets
            
            return result
        except Exception as e:
            error = handle_xml_parsing_error("parse_column_filter", e, "columnValue")
            return None
    
    def _parse_range_value(self, range_elem: ET.Element) -> Dict:
        """Parse range value information"""
        try:
            result = {}
            
            # Parse relative_to attribute
            relative_to = self.get_attribute(range_elem, 'relativeTo')
            if relative_to:
                result['relative_to'] = relative_to
            
            # Parse range from - handle both namespaced and non-namespaced
            range_from = self.find_element_both(range_elem, 'rangeFrom')
            if range_from is not None:
                result['from'] = self._parse_range_boundary(range_from)
            
            # Parse range to - handle both namespaced and non-namespaced
            range_to = self.find_element_both(range_elem, 'rangeTo')
            if range_to is not None:
                result['to'] = self._parse_range_boundary(range_to)
            
            return result
        except Exception as e:
            error = handle_xml_parsing_error("parse_range_value", e, "rangeValue")
            return {}
    
    def _parse_range_boundary(self, boundary_elem: ET.Element) -> Dict:
        """Parse range boundary (from/to) information"""
        try:
            operator_text = self.parse_child_text(boundary_elem, 'operator')
            result = {
                'operator': operator_text
            }
            
            # Parse value element - handle nested structure that can contain multiple values
            # Handle both namespaced and non-namespaced
            value_elem = self.find_element_both(boundary_elem, 'value')
            singleValue_elem = self.find_element_both(boundary_elem, 'singleValue')
            
            if value_elem is not None:
                # Check if we have the nested structure: <value><value>...</value><unit>...</unit><relation>...</relation></value>
                nested_value_elem = self.find_element_both(value_elem, 'value')
                nested_unit_elem = self.find_element_both(value_elem, 'unit')
                nested_relation_elem = self.find_element_both(value_elem, 'relation')
                
                if nested_value_elem is not None:
                    # Nested structure pattern: parse from nested elements
                    result['value'] = self.get_text(nested_value_elem)
                    result['unit'] = self.get_text(nested_unit_elem) if nested_unit_elem is not None else None
                    result['relation'] = self.get_text(nested_relation_elem) if nested_relation_elem is not None else None
                else:
                    # Original pattern: try to get direct text first
                    value_text = self.get_text(value_elem)
                    
                    # If direct text is empty, look for nested value elements (can be multiple for ranges)
                    if not value_text or not value_text.strip():
                        # Handle both namespaced and non-namespaced nested values
                        namespaced_nested = self.find_elements(value_elem, 'emis:value')
                        non_namespaced_nested = value_elem.findall('value')
                        nested_values = non_namespaced_nested + [v for v in namespaced_nested if v not in non_namespaced_nested]
                        
                        if nested_values:
                            value_texts = [self.get_text(nv) for nv in nested_values if self.get_text(nv)]
                            if value_texts:
                                # For single value, use just the value; for multiple, join with comma
                                value_text = value_texts[0] if len(value_texts) == 1 else ', '.join(value_texts)
                    
                    result['value'] = value_text
                    result['values'] = value_texts if 'value_texts' in locals() and len(value_texts) > 1 else None
                    # Parse unit and relation as child elements (not attributes)
                    result['unit'] = self.parse_child_text(value_elem, 'unit')
                    result['relation'] = self.parse_child_text(value_elem, 'relation')
            
            elif singleValue_elem is not None:
                # Handle singleValue/variable pattern for temporal date patterns
                variable_elem = self.find_element_both(singleValue_elem, 'variable')
                if variable_elem is not None:
                    result['value'] = self.parse_child_text(variable_elem, 'value')
                    result['unit'] = self.parse_child_text(variable_elem, 'unit')
                    result['relation'] = self.parse_child_text(variable_elem, 'relation')
                else:
                    # Fallback: treat singleValue content directly as value
                    result['value'] = self.get_text(singleValue_elem)
            
            return result
        except Exception as e:
            error = handle_xml_parsing_error("parse_range_boundary", e, "rangeBoundary")
            return {}
    
    def _parse_library_item(self, library_elem: ET.Element) -> Optional[Dict]:
        """Parse library item information"""
        try:
            library_guid = self.get_text(library_elem)
            if not library_guid:
                return None
            
            # Create a value set-like structure for library items
            result = {
                'id': library_guid,
                'code_system': 'LIBRARY_ITEM',
                'description': f'EMIS Library Item {library_guid}',
                'values': [{
                    'value': library_guid,
                    'display_name': f'Library Item: {library_guid}',
                    'include_children': False,
                    'is_refset': False,
                    'is_library_item': True
                }]
            }
            return result
        except Exception as e:
            error = handle_xml_parsing_error("parse_library_item", e, "libraryItem")
            return None
    
    def _parse_parameter(self, param_elem: ET.Element) -> Dict:
        """Parse parameter information for runtime user input"""
        try:
            result = {
                'name': self.parse_child_text(param_elem, 'name'),
                'allow_global': self._parse_boolean_child(param_elem, 'allowGlobal')
            }
            return result
        except Exception as e:
            error = handle_xml_parsing_error("parse_parameter", e, "parameter")
            return {}
    
    def _parse_boolean_child(self, parent: ET.Element, child_name: str) -> bool:
        """Parse boolean value from child element - handle both namespaced and non-namespaced"""
        child_elem = self.find_element_both(parent, child_name)
        if child_elem is not None:
            return self.get_text(child_elem).lower() == 'true'
        return False


# Convenience functions for backward compatibility
def parse_criterion(criterion_elem: ET.Element, namespaces: Optional[Dict[str, str]] = None) -> Optional[SearchCriterion]:
    """Parse individual search criterion"""
    parser = CriterionParser(namespaces)
    return parser.parse_criterion(criterion_elem)


def parse_column_filter(column_elem: ET.Element, namespaces: Optional[Dict[str, str]] = None) -> Optional[Dict]:
    """Parse column filter information"""
    parser = CriterionParser(namespaces)
    return parser.parse_column_filter(column_elem)


def check_criterion_parameters(criterion: SearchCriterion) -> Dict[str, Any]:
    """
    Check if criterion contains parameters and return parameter info
    
    Args:
        criterion: SearchCriterion object to analyze
        
    Returns:
        Dict: Parameter analysis information including names, types, and counts
    """
    parameter_names = []
    has_global = False
    has_local = False
    
    # Check column filters for parameters
    for column_filter in criterion.column_filters:
        if 'parameter' in column_filter:
            param_info = column_filter['parameter']
            param_name = param_info.get('name', 'Unknown')
            parameter_names.append(param_name)
            
            if param_info.get('allow_global', False):
                has_global = True
            else:
                has_local = True
    
    # Check linked criteria for parameters recursively
    for linked_criterion in criterion.linked_criteria:
        if hasattr(linked_criterion, 'column_filters'):
            for column_filter in linked_criterion.column_filters:
                if 'parameter' in column_filter:
                    param_info = column_filter['parameter']
                    param_name = param_info.get('name', 'Unknown')
                    if param_name not in parameter_names:  # Avoid duplicates
                        parameter_names.append(param_name)
                        
                        if param_info.get('allow_global', False):
                            has_global = True
                        else:
                            has_local = True
    
    return {
        'has_parameters': len(parameter_names) > 0,
        'parameter_names': parameter_names,
        'has_global': has_global,
        'has_local': has_local,
        'parameter_count': len(parameter_names)
    }
