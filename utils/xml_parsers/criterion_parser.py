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
from ..common.error_handling import (
    handle_xml_parsing_error, safe_execute, create_error_context,
    ParseResult, XMLParsingContext, create_xml_parsing_context,
    safe_xml_parse, get_error_handler
)


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
    
    @staticmethod
    def safe_detect_demographics_column(column_name: str, context: str = "") -> Dict[str, Any]:
        """
        Defensively detect patient demographics columns with multiple fallback patterns
        
        Returns detailed information about the detection process including:
        - Whether it's a demographics column
        - What type of demographics 
        - Confidence level
        - Matched patterns
        - Potential issues
        """
        result = {
            'is_demographics': False,
            'demographics_type': None,
            'confidence': 'none',
            'matched_patterns': [],
            'warnings': [],
            'context': context
        }
        
        # Handle None or empty input
        if not column_name:
            result['warnings'].append("Column name is None or empty")
            return result
        
        if not isinstance(column_name, str):
            result['warnings'].append(f"Column name is not a string: {type(column_name)}")
            try:
                column_name = str(column_name)
            except Exception as e:
                result['warnings'].append(f"Failed to convert column name to string: {str(e)}")
                return result
        
        column_upper = column_name.upper().strip()
        
        if not column_upper:
            result['warnings'].append("Column name is empty after processing")
            return result
        
        # Primary LSOA patterns (high confidence)
        lsoa_patterns = [
            # Standard year patterns
            r'.*LOWER_AREA.*20\d{2}.*',  # Any year 2000-2099
            r'.*LONDON_LOWER_AREA.*',    # London specific
            r'.*LSOA.*20\d{2}.*',        # Direct LSOA reference
            r'.*LOWER_SUPER_OUTPUT_AREA.*'  # Full form
        ]
        
        for pattern in lsoa_patterns:
            import re
            if re.match(pattern, column_upper):
                result['is_demographics'] = True
                result['demographics_type'] = 'LSOA'
                result['confidence'] = 'high'
                result['matched_patterns'].append(pattern)
        
        # Secondary geographical patterns (medium confidence)
        geo_patterns = [
            r'.*MSOA.*',           # Middle Layer Super Output Area
            r'.*WARD.*',           # Electoral wards
            r'.*POSTCODE.*AREA.*', # Postcode areas
            r'.*CCG.*',            # Clinical Commissioning Group
            r'.*STP.*',            # Sustainability and Transformation Partnership
            r'.*ICS.*',            # Integrated Care System
            r'.*PRACTICE.*AREA.*'  # Practice area codes
        ]
        
        if not result['is_demographics']:  # Only check if not already found
            for pattern in geo_patterns:
                import re
                if re.match(pattern, column_upper):
                    result['is_demographics'] = True
                    result['demographics_type'] = 'geographical'
                    result['confidence'] = 'medium'
                    result['matched_patterns'].append(pattern)
                    break
        
        # Tertiary patient demographic patterns (low confidence)
        patient_patterns = [
            r'.*PATIENT.*AGE.*',
            r'.*PATIENT.*GENDER.*',
            r'.*PATIENT.*SEX.*',
            r'.*AGE_GROUP.*',
            r'.*ETHNICITY.*',
            r'.*DEMOGRAPHIC.*'
        ]
        
        if not result['is_demographics']:  # Only check if not already found
            for pattern in patient_patterns:
                import re
                if re.match(pattern, column_upper):
                    result['is_demographics'] = True
                    result['demographics_type'] = 'patient_attributes'
                    result['confidence'] = 'low'
                    result['matched_patterns'].append(pattern)
                    result['warnings'].append("Low confidence match - manual verification recommended")
                    break
        
        # Fallback: keyword-based detection (very low confidence)
        if not result['is_demographics']:
            demographic_keywords = [
                'DEPRIVATION', 'INCOME', 'RURAL', 'URBAN', 'POPULATION',
                'CENSUS', 'AREA_CODE', 'BOUNDARY', 'REGION'
            ]
            
            matched_keywords = [kw for kw in demographic_keywords if kw in column_upper]
            if matched_keywords:
                result['is_demographics'] = True
                result['demographics_type'] = 'potential_geographic'
                result['confidence'] = 'very_low'
                result['matched_patterns'] = matched_keywords
                result['warnings'].append("Very low confidence keyword match - manual review required")
        
        # Additional validation warnings
        if result['is_demographics']:
            # Check for unusual characters that might indicate parsing issues
            if any(char in column_name for char in ['<', '>', '&', '"', "'"]):
                result['warnings'].append("Column name contains XML/HTML characters")
            
            # Check for very long names that might be concatenated
            if len(column_name) > 50:
                result['warnings'].append("Column name is unusually long - possible concatenation")
            
            # Check for multiple underscores that might indicate compound fields
            if column_name.count('_') > 3:
                result['warnings'].append("Column name has many underscores - might be compound field")
        
        return result
    
    @staticmethod
    def get_demographics_classification_summary(columns: List[str]) -> Dict[str, Any]:
        """
        Analyse multiple columns to provide a summary of demographics classification
        
        Useful for validating bulk column processing and identifying patterns
        """
        if not columns:
            return {
                'total_columns': 0,
                'demographics_columns': 0,
                'classification_summary': {},
                'warnings': ['No columns provided for analysis']
            }
        
        summary = {
            'total_columns': len(columns),
            'demographics_columns': 0,
            'by_type': {},
            'by_confidence': {'high': 0, 'medium': 0, 'low': 0, 'very_low': 0, 'none': 0},
            'warnings': [],
            'detailed_results': []
        }
        
        for column in columns:
            if column is None:
                summary['warnings'].append("Encountered None column in list")
                continue
            
            result = CriterionParser.safe_detect_demographics_column(column)
            summary['detailed_results'].append({
                'column': column,
                'result': result
            })
            
            if result['is_demographics']:
                summary['demographics_columns'] += 1
                
                # Count by type
                demo_type = result.get('demographics_type', 'unknown')
                summary['by_type'][demo_type] = summary['by_type'].get(demo_type, 0) + 1
                
                # Count by confidence
                confidence = result.get('confidence', 'none')
                summary['by_confidence'][confidence] += 1
            else:
                summary['by_confidence']['none'] += 1
            
            # Collect warnings
            if result.get('warnings'):
                summary['warnings'].extend(result['warnings'])
        
        # Calculate percentages
        if summary['total_columns'] > 0:
            summary['demographics_percentage'] = (summary['demographics_columns'] / summary['total_columns']) * 100
        else:
            summary['demographics_percentage'] = 0
        
        return summary
    
    def safe_parse_criterion(self, criterion_elem: ET.Element) -> ParseResult:
        """Safely parse individual search criterion with comprehensive error handling"""
        xml_context = create_xml_parsing_context(
            element_name="criterion",
            element_path="searchCriterion",
            parsing_stage="criterion_parsing"
        )
        
        if criterion_elem is None:
            return ParseResult.failure_result(
                ["Criterion element is None"], 
                xml_context
            )
        
        # Track parsing errors and warnings for this criterion
        errors = []
        warnings = []
        
        try:
            # Safely extract basic properties with null checking
            criterion_id_result = self.safe_get_text(
                self.find_element_both(criterion_elem, 'id'),
                element_name="id",
                expected_format="string"
            )
            
            if not criterion_id_result.success:
                criterion_id = "Unknown"
                warnings.extend(criterion_id_result.warnings or [])
            else:
                criterion_id = criterion_id_result.data or "Unknown"
            
            table_result = self.safe_get_text(
                self.find_element_both(criterion_elem, 'table'),
                element_name="table",
                expected_format="string"
            )
            
            if not table_result.success:
                table = "Unknown"
                warnings.extend(table_result.warnings or [])
            else:
                table = table_result.data or "Unknown"
            
            display_name_result = self.safe_get_text(
                self.find_element_both(criterion_elem, 'displayName'),
                element_name="displayName",
                expected_format="string"
            )
            
            if not display_name_result.success:
                display_name = "Unknown"
                warnings.extend(display_name_result.warnings or [])
            else:
                display_name = display_name_result.data or "Unknown"
            
            # Parse optional fields safely
            description_elem = self.find_element_both(criterion_elem, 'description')
            description = self.get_text(description_elem) if description_elem is not None else None
            
            exception_code_elem = self.find_element_both(criterion_elem, 'exceptionCode')
            exception_code = self.get_text(exception_code_elem) if exception_code_elem is not None else None
            
            # Parse negation with validation
            negation_elem = self.find_element_both(criterion_elem, 'negation')
            if negation_elem is not None:
                negation_text = self.get_text(negation_elem).lower()
                if negation_text not in ('true', 'false', '1', '0', 'yes', 'no', ''):
                    warnings.append(f"Invalid negation value: '{negation_text}', defaulting to false")
                    negation = False
                else:
                    negation = negation_text in ('true', '1', 'yes')
            else:
                negation = False
            
            # Parse components with error collection
            value_sets = []
            column_filters = []
            restrictions = []
            linked_criteria = []
            
            # Parse value sets with validation
            try:
                value_sets = self._safe_parse_value_sets(criterion_elem, errors, warnings)
            except Exception as e:
                errors.append(f"Failed to parse value sets: {str(e)}")
            
            # Parse column filters with validation
            try:
                column_filters = self._safe_parse_column_filters(criterion_elem, errors, warnings)
            except Exception as e:
                errors.append(f"Failed to parse column filters: {str(e)}")
            
            # Parse restrictions with validation
            try:
                restrictions = self._safe_parse_restrictions(criterion_elem, errors, warnings)
            except Exception as e:
                errors.append(f"Failed to parse restrictions: {str(e)}")
            
            # Parse linked criteria with validation
            try:
                linked_criteria = self._safe_parse_linked_criteria(criterion_elem, errors, warnings)
            except Exception as e:
                errors.append(f"Failed to parse linked criteria: {str(e)}")
            
            # Create criterion object
            criterion = SearchCriterion(
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
            
            if errors:
                return ParseResult.failure_result(errors, xml_context)
            elif warnings:
                return ParseResult.partial_result(criterion, warnings, xml_context)
            else:
                return ParseResult.success_result(criterion)
                
        except Exception as e:
            error_msg = f"Unexpected error parsing criterion: {str(e)}"
            return ParseResult.failure_result([error_msg], xml_context)
    
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
    
    def safe_parse_range_value(self, range_elem: ET.Element) -> ParseResult:
        """Safely parse range value information with comprehensive error handling"""
        xml_context = create_xml_parsing_context(
            element_name="rangeValue",
            parsing_stage="range_parsing"
        )
        
        if range_elem is None:
            return ParseResult.failure_result(
                ["Range element is None"],
                xml_context
            )
        
        errors = []
        warnings = []
        result = {}
        
        try:
            # Parse relative_to attribute with validation
            relative_to_result = self.safe_get_attribute(
                range_elem, 'relativeTo', 
                expected_format=None, 
                required=False
            )
            
            if relative_to_result.success and relative_to_result.data:
                result['relative_to'] = relative_to_result.data
                
                # Validate relative_to value
                valid_relative_values = ['baseline', 'encounter', 'current', 'previous']
                if relative_to_result.data not in valid_relative_values:
                    warnings.append(f"Unrecognised relativeTo value: '{relative_to_result.data}'")
            elif relative_to_result.warnings:
                warnings.extend(relative_to_result.warnings)
            
            # Parse range from with validation
            range_from_result = self.safe_find_element(range_elem, 'rangeFrom', 'rangeFrom')
            if range_from_result.success and range_from_result.data:
                boundary_result = self.safe_parse_range_boundary(range_from_result.data)
                if boundary_result.success:
                    result['from'] = boundary_result.data
                    if boundary_result.warnings:
                        warnings.extend(boundary_result.warnings)
                else:
                    errors.extend(boundary_result.errors or [])
            elif range_from_result.warnings:
                warnings.extend(range_from_result.warnings)
            
            # Parse range to with validation
            range_to_result = self.safe_find_element(range_elem, 'rangeTo', 'rangeTo')
            if range_to_result.success and range_to_result.data:
                boundary_result = self.safe_parse_range_boundary(range_to_result.data)
                if boundary_result.success:
                    result['to'] = boundary_result.data
                    if boundary_result.warnings:
                        warnings.extend(boundary_result.warnings)
                else:
                    errors.extend(boundary_result.errors or [])
            elif range_to_result.warnings:
                warnings.extend(range_to_result.warnings)
            
            # Validate range logic
            if 'from' in result and 'to' in result:
                validation_warnings = self._validate_range_boundaries(result['from'], result['to'])
                warnings.extend(validation_warnings)
            
            if errors:
                return ParseResult.failure_result(errors, xml_context)
            elif warnings:
                return ParseResult.partial_result(result, warnings, xml_context)
            else:
                return ParseResult.success_result(result)
                
        except Exception as e:
            error_msg = f"Unexpected error parsing range value: {str(e)}"
            return ParseResult.failure_result([error_msg], xml_context)
    
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
    
    def safe_parse_range_boundary(self, boundary_elem: ET.Element) -> ParseResult:
        """Safely parse range boundary with comprehensive validation"""
        xml_context = create_xml_parsing_context(
            element_name="rangeBoundary",
            parsing_stage="range_boundary_parsing"
        )
        
        if boundary_elem is None:
            return ParseResult.failure_result(
                ["Range boundary element is None"],
                xml_context
            )
        
        errors = []
        warnings = []
        result = {}
        
        try:
            # Parse operator with validation
            operator_result = self.safe_get_text(
                self.find_element_both(boundary_elem, 'operator'),
                element_name="operator",
                expected_format="string"
            )
            
            if operator_result.success:
                operator = operator_result.data
                
                # Validate operator
                valid_operators = ['EQ', 'NE', 'LT', 'LE', 'GT', 'GE', 'IN', 'NOT_IN', 'BETWEEN', 'NOT_BETWEEN']
                if operator and operator not in valid_operators:
                    warnings.append(f"Unrecognised operator: '{operator}', using as-is")
                
                result['operator'] = operator
            else:
                errors.extend(operator_result.errors or [])
                warnings.extend(operator_result.warnings or [])
            
            # Parse value with comprehensive handling
            value_result = self._safe_parse_boundary_value(boundary_elem, warnings)
            if value_result:
                result.update(value_result)
            
            # Validate numeric values if present
            if 'value' in result:
                try:
                    # Try to validate numeric format for numeric operators
                    numeric_operators = ['LT', 'LE', 'GT', 'GE', 'EQ', 'NE']
                    if result.get('operator') in numeric_operators:
                        try:
                            float(result['value'])
                        except (ValueError, TypeError):
                            # Not numeric - might be valid for text fields
                            pass
                except Exception:
                    pass
            
            if errors:
                return ParseResult.failure_result(errors, xml_context)
            elif warnings:
                return ParseResult.partial_result(result, warnings, xml_context)
            else:
                return ParseResult.success_result(result)
                
        except Exception as e:
            error_msg = f"Unexpected error parsing range boundary: {str(e)}"
            return ParseResult.failure_result([error_msg], xml_context)
    
    def _safe_parse_boundary_value(self, boundary_elem: ET.Element, warnings: list) -> Optional[Dict]:
        """Safely parse boundary value with multiple fallback strategies"""
        if boundary_elem is None:
            warnings.append("Boundary element is None for value parsing")
            return None
        
        result = {}
        
        try:
            # Strategy 1: Look for value element
            value_elem_result = self.safe_find_element(boundary_elem, 'value', 'value')
            if value_elem_result.success and value_elem_result.data is not None:
                value_elem = value_elem_result.data
                
                # Check for nested structure
                nested_value_result = self.safe_get_text(
                    self.find_element_both(value_elem, 'value'),
                    element_name="nested_value"
                )
                
                if nested_value_result.success and nested_value_result.data:
                    # Nested structure pattern
                    result['value'] = nested_value_result.data
                    
                    unit_elem = self.find_element_both(value_elem, 'unit')
                    if unit_elem is not None:
                        result['unit'] = self.get_text(unit_elem)
                    
                    relation_elem = self.find_element_both(value_elem, 'relation')
                    if relation_elem is not None:
                        result['relation'] = self.get_text(relation_elem)
                else:
                    # Direct text content
                    direct_value = self.get_text(value_elem)
                    if direct_value:
                        result['value'] = direct_value
                    else:
                        # Look for multiple nested values
                        nested_values = self._safe_extract_multiple_values(value_elem, warnings)
                        if nested_values:
                            result['values'] = nested_values
            
            # Strategy 2: Look for singleValue element
            if not result:
                single_value_result = self.safe_find_element(boundary_elem, 'singleValue', 'singleValue')
                if single_value_result.success and single_value_result.data is not None:
                    single_value = self.get_text(single_value_result.data)
                    if single_value:
                        result['value'] = single_value
            
            # Strategy 3: Direct text content of boundary element
            if not result:
                direct_text = self.get_text(boundary_elem)
                if direct_text:
                    result['value'] = direct_text
                    warnings.append("Used direct text content as boundary value")
            
            return result if result else None
            
        except Exception as e:
            warnings.append(f"Error parsing boundary value: {str(e)}")
            return None
    
    def _safe_extract_multiple_values(self, value_elem: ET.Element, warnings: list) -> Optional[List[str]]:
        """Safely extract multiple values from nested structure"""
        if value_elem is None:
            return None
        
        try:
            values = []
            
            # Find all nested value elements
            ns_values_result = self.safe_find_elements(value_elem, 'emis:value')
            if ns_values_result.success:
                for val_elem in ns_values_result.data:
                    text = self.get_text(val_elem)
                    if text:
                        values.append(text)
            
            non_ns_values_result = self.safe_find_elements(value_elem, 'value')
            if non_ns_values_result.success:
                for val_elem in non_ns_values_result.data:
                    text = self.get_text(val_elem)
                    if text and text not in values:
                        values.append(text)
            
            return values if values else None
            
        except Exception as e:
            warnings.append(f"Error extracting multiple values: {str(e)}")
            return None
    
    def _validate_range_boundaries(self, from_boundary: Dict, to_boundary: Dict) -> List[str]:
        """Validate range boundary logic and consistency"""
        warnings = []
        
        try:
            # Check for conflicting operators
            from_op = from_boundary.get('operator', '')
            to_op = to_boundary.get('operator', '')
            
            # Validate numeric range consistency
            from_value = from_boundary.get('value')
            to_value = to_boundary.get('value')
            
            if from_value and to_value:
                try:
                    from_num = float(from_value)
                    to_num = float(to_value)
                    
                    # Check logical consistency
                    if from_op in ['GE', 'GT'] and to_op in ['LE', 'LT']:
                        if from_num >= to_num:
                            warnings.append(f"Range logic issue: from value {from_num} >= to value {to_num}")
                    
                except (ValueError, TypeError):
                    # Not numeric values - skip numeric validation
                    pass
            
            # Check unit consistency
            from_unit = from_boundary.get('unit')
            to_unit = to_boundary.get('unit')
            
            if from_unit and to_unit and from_unit != to_unit:
                warnings.append(f"Unit mismatch in range: from='{from_unit}', to='{to_unit}'")
            
        except Exception as e:
            warnings.append(f"Error validating range boundaries: {str(e)}")
        
        return warnings
    
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
    
    # Helper methods for safe parsing
    def _safe_parse_value_sets(self, criterion_elem: ET.Element, errors: list, warnings: list) -> List[Dict]:
        """Safely parse value sets with error collection"""
        value_sets = []
        all_valuesets = []
        
        if criterion_elem is None:
            errors.append("Cannot parse value sets from None element")
            return value_sets
        
        try:
            # Find filterAttribute elements with null checking
            filter_attrs_result = self.safe_find_elements(criterion_elem, 'filterAttribute')
            if filter_attrs_result.success:
                filter_attrs = filter_attrs_result.data
            else:
                filter_attrs = []
                warnings.extend(filter_attrs_result.warnings or [])
            
            # Also check namespaced versions
            ns_filter_attrs_result = self.safe_find_elements(criterion_elem, 'emis:filterAttribute')
            if ns_filter_attrs_result.success:
                filter_attrs.extend(ns_filter_attrs_result.data)
            
            for filter_attr in filter_attrs:
                if filter_attr is None:
                    warnings.append("Encountered None filterAttribute element")
                    continue
                    
                try:
                    # Find columnValue elements with validation
                    column_values = self._safe_find_column_values(filter_attr, warnings)
                    
                    for col_elem in column_values:
                        if col_elem is None:
                            continue
                            
                        # Find value sets within columnValue with validation
                        vs_result = self.safe_find_elements(col_elem, 'valueSet')
                        if vs_result.success:
                            for vs in vs_result.data:
                                if vs not in all_valuesets:
                                    all_valuesets.append(vs)
                        
                        # Check namespaced versions
                        ns_vs_result = self.safe_find_elements(col_elem, 'emis:valueSet')
                        if ns_vs_result.success:
                            for vs in ns_vs_result.data:
                                if vs not in all_valuesets:
                                    all_valuesets.append(vs)
                
                except Exception as e:
                    warnings.append(f"Error processing filterAttribute: {str(e)}")
            
            # Parse collected value set elements
            for valueset_elem in all_valuesets:
                if valueset_elem is None:
                    warnings.append("Encountered None valueSet element")
                    continue
                    
                try:
                    value_set = parse_value_set(valueset_elem, self.namespaces)
                    if value_set:
                        value_sets.append(value_set)
                    else:
                        warnings.append("Failed to parse valueSet - returned None")
                except Exception as e:
                    warnings.append(f"Error parsing individual valueSet: {str(e)}")
            
        except Exception as e:
            errors.append(f"Unexpected error in value set parsing: {str(e)}")
        
        return value_sets
    
    def _safe_parse_column_filters(self, criterion_elem: ET.Element, errors: list, warnings: list) -> List[Dict]:
        """Safely parse column filters with error collection"""
        column_filters = []
        
        if criterion_elem is None:
            errors.append("Cannot parse column filters from None element")
            return column_filters
        
        try:
            # Find all columnValue elements with validation
            column_values = []
            
            # Check both namespaced and non-namespaced paths
            ns_columns_result = self.safe_find_elements(criterion_elem, './/emis:columnValue')
            if ns_columns_result.success:
                column_values.extend(ns_columns_result.data)
            
            non_ns_columns_result = self.safe_find_elements(criterion_elem, './/columnValue')
            if non_ns_columns_result.success:
                for col in non_ns_columns_result.data:
                    if col not in column_values:  # Avoid duplicates
                        column_values.append(col)
            
            for column_elem in column_values:
                if column_elem is None:
                    warnings.append("Encountered None columnValue element")
                    continue
                
                try:
                    column_filter = self.parse_column_filter(column_elem)
                    if column_filter:
                        column_filters.append(column_filter)
                    else:
                        warnings.append("Column filter parsing returned None")
                except Exception as e:
                    warnings.append(f"Error parsing individual column filter: {str(e)}")
            
        except Exception as e:
            errors.append(f"Unexpected error in column filter parsing: {str(e)}")
        
        return column_filters
    
    def _safe_parse_restrictions(self, criterion_elem: ET.Element, errors: list, warnings: list) -> List[Any]:
        """Safely parse restrictions with error collection"""
        restrictions = []
        
        if criterion_elem is None:
            errors.append("Cannot parse restrictions from None element")
            return restrictions
        
        try:
            # Find restrictions in multiple locations with validation
            all_restrictions = []
            
            # Direct restrictions under criterion
            direct_rest_result = self.safe_find_elements(criterion_elem, 'restriction')
            if direct_rest_result.success:
                all_restrictions.extend(direct_rest_result.data)
            
            ns_direct_rest_result = self.safe_find_elements(criterion_elem, 'emis:restriction')
            if ns_direct_rest_result.success:
                all_restrictions.extend(ns_direct_rest_result.data)
            
            # Parse each restriction with error handling
            for restriction_elem in all_restrictions:
                if restriction_elem is None:
                    warnings.append("Encountered None restriction element")
                    continue
                
                try:
                    restriction = parse_restriction(restriction_elem, self.namespaces)
                    if restriction:
                        restrictions.append(restriction)
                    else:
                        warnings.append("Restriction parsing returned None")
                except Exception as e:
                    warnings.append(f"Error parsing individual restriction: {str(e)}")
            
        except Exception as e:
            errors.append(f"Unexpected error in restriction parsing: {str(e)}")
        
        return restrictions
    
    def _safe_parse_linked_criteria(self, criterion_elem: ET.Element, errors: list, warnings: list) -> List['SearchCriterion']:
        """Safely parse linked criteria with error collection"""
        linked_criteria = []
        
        if criterion_elem is None:
            errors.append("Cannot parse linked criteria from None element")
            return linked_criteria
        
        try:
            # Find linked criterion elements with validation
            linked_elements = []
            
            ns_linked_result = self.safe_find_elements(criterion_elem, './/emis:linkedCriterion')
            if ns_linked_result.success:
                linked_elements.extend(ns_linked_result.data)
            
            non_ns_linked_result = self.safe_find_elements(criterion_elem, './/linkedCriterion')
            if non_ns_linked_result.success:
                for elem in non_ns_linked_result.data:
                    if elem not in linked_elements:
                        linked_elements.append(elem)
            
            for linked_elem in linked_elements:
                if linked_elem is None:
                    warnings.append("Encountered None linkedCriterion element")
                    continue
                
                try:
                    linked_criterion = parse_linked_criterion(linked_elem, self.namespaces)
                    if linked_criterion:
                        linked_criteria.append(linked_criterion)
                    else:
                        warnings.append("Linked criterion parsing returned None")
                except Exception as e:
                    warnings.append(f"Error parsing individual linked criterion: {str(e)}")
            
        except Exception as e:
            errors.append(f"Unexpected error in linked criteria parsing: {str(e)}")
        
        return linked_criteria
    
    def _safe_find_column_values(self, parent_elem: ET.Element, warnings: list) -> List[ET.Element]:
        """Safely find columnValue elements with comprehensive error handling"""
        column_values = []
        
        if parent_elem is None:
            warnings.append("Cannot find columnValue in None parent element")
            return column_values
        
        try:
            # Find both namespaced and non-namespaced columnValue elements
            ns_result = self.safe_find_elements(parent_elem, 'emis:columnValue')
            if ns_result.success:
                column_values.extend(ns_result.data)
            elif ns_result.warnings:
                warnings.extend(ns_result.warnings)
            
            non_ns_result = self.safe_find_elements(parent_elem, 'columnValue')
            if non_ns_result.success:
                for elem in non_ns_result.data:
                    if elem not in column_values:  # Avoid duplicates
                        column_values.append(elem)
            elif non_ns_result.warnings:
                warnings.extend(non_ns_result.warnings)
            
        except Exception as e:
            warnings.append(f"Error finding columnValue elements: {str(e)}")
        
        return column_values


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
