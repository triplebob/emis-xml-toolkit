"""
Restriction parsing utilities for EMIS XML
Handles parsing of search restrictions like 'Latest 1' with conditional logic
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from .base_parser import XMLParserBase, get_namespaces


@dataclass
class SearchRestriction:
    """Represents filtering restrictions like 'Latest 1' or 'Is Current'"""
    type: str  # 'latest_records', 'date_range', 'test_condition', 'conditional_latest'
    description: str
    record_count: Optional[int] = None
    direction: Optional[str] = None  # ASC/DESC
    conditions: Optional[List[Dict]] = None


class RestrictionParser(XMLParserBase):
    """Parser for restriction elements"""
    
    def parse_restriction(self, restriction_elem: ET.Element) -> Optional[SearchRestriction]:
        """Parse restriction elements like 'Latest 1' with conditional logic"""
        try:
            # Handle both namespaced and non-namespaced elements
            column_order_elem = self.find_element_both(restriction_elem, 'columnOrder')
            test_attr_elem = self.find_element_both(restriction_elem, 'testAttribute')
            
            # Parse basic record count and ordering
            record_count, direction = self._parse_column_order(column_order_elem)
            
            # Parse test conditions if present
            test_conditions = self._parse_test_conditions(test_attr_elem)
            
            # Build appropriate restriction based on complexity
            return self._build_restriction(record_count, direction, test_conditions)
            
        except Exception as e:
            print(f"Error parsing restriction: {e}")
            return SearchRestriction(
                type="unknown",
                description="Unknown restriction type"
            )
    
    def _parse_column_order(self, column_order_elem: Optional[ET.Element]) -> tuple[Optional[int], Optional[str]]:
        """Parse record count and direction from columnOrder element"""
        if column_order_elem is None:
            return None, None
        
        record_count = None
        direction = None
        
        # Parse record count - handle both namespaced and non-namespaced
        record_count_elem = self.find_element_both(column_order_elem, 'recordCount')
        if record_count_elem is not None:
            try:
                record_count = int(self.get_text(record_count_elem))
            except ValueError:
                record_count = None
        
        # Parse direction - handle both namespaced and non-namespaced
        columns_elem = self.find_element_both(column_order_elem, 'columns')
        if columns_elem is not None:
            direction_elem = self.find_element_both(columns_elem, 'direction')
            direction = self.get_text(direction_elem) if direction_elem is not None else None
        
        return record_count, direction
    
    def _parse_test_conditions(self, test_attr_elem: Optional[ET.Element]) -> List[Dict]:
        """Parse test conditions from testAttribute element"""
        if test_attr_elem is None:
            return []
        
        test_conditions = []
        
        # Parse column values within test attribute - handle both namespaced and non-namespaced
        namespaced_cols = self.find_elements(test_attr_elem, 'emis:columnValue')
        non_namespaced_cols = test_attr_elem.findall('columnValue')
        all_cols = non_namespaced_cols + [c for c in namespaced_cols if c not in non_namespaced_cols]
        
        for col_val_elem in all_cols:
            condition = self._parse_test_condition(col_val_elem)
            if condition:
                test_conditions.append(condition)
        
        return test_conditions
    
    def _parse_test_condition(self, col_val_elem: ET.Element) -> Optional[Dict]:
        """Parse individual test condition"""
        try:
            column = self.parse_child_text(col_val_elem, 'column')
            in_not_in = self.parse_child_text(col_val_elem, 'inNotIn', 'IN')
            
            # Parse value sets within test conditions - handle both namespaced and non-namespaced
            value_set_descriptions = []
            value_set_elements = []  # Store the actual elements for proper parsing
            namespaced_vs = self.find_elements(col_val_elem, 'emis:valueSet')
            non_namespaced_vs = col_val_elem.findall('valueSet')
            all_vs = non_namespaced_vs + [v for v in namespaced_vs if v not in non_namespaced_vs]
            
            for vs_elem in all_vs:
                desc = self.parse_child_text(vs_elem, 'description')
                if desc:
                    value_set_descriptions.append(desc)
                    value_set_elements.append(vs_elem)  # Store the full element
            
            # Parse range values if present - handle both namespaced and non-namespaced
            range_values = []
            namespaced_ranges = self.find_elements(col_val_elem, 'emis:rangeValue')
            non_namespaced_ranges = col_val_elem.findall('rangeValue')
            all_ranges = non_namespaced_ranges + [r for r in namespaced_ranges if r not in non_namespaced_ranges]
            
            for range_elem in all_ranges:
                range_desc = self._parse_range_description(range_elem)
                if range_desc:
                    range_values.append(range_desc)
            
            if column:
                return {
                    'column': column,
                    'operator': in_not_in,
                    'value_sets': value_set_descriptions,
                    'value_set_elements': value_set_elements,  # Include the actual XML elements
                    'range_values': range_values
                }
        except Exception as e:
            print(f"Error parsing test condition: {e}")
        
        return None
    
    def _parse_range_description(self, range_elem: ET.Element) -> str:
        """Parse range element into human-readable description"""
        try:
            parts = []
            
            # Parse range from - handle both namespaced and non-namespaced
            range_from = self.find_element_both(range_elem, 'rangeFrom')
            if range_from is not None:
                operator = self.parse_child_text(range_from, 'operator')
                value_elem = self.find_element_both(range_from, 'value')
                if value_elem is not None:
                    value = self.get_text(value_elem)
                    unit = self.get_attribute(value_elem, 'unit')
                    if operator and value:
                        parts.append(f"{operator} {value} {unit}".strip())
            
            # Parse range to - handle both namespaced and non-namespaced
            range_to = self.find_element_both(range_elem, 'rangeTo')
            if range_to is not None:
                operator = self.parse_child_text(range_to, 'operator')
                value_elem = self.find_element_both(range_to, 'value')
                if value_elem is not None:
                    value = self.get_text(value_elem)
                    unit = self.get_attribute(value_elem, 'unit')
                    if operator and value:
                        parts.append(f"{operator} {value} {unit}".strip())
            
            return " AND ".join(parts) if parts else ""
        except Exception:
            return ""
    
    def _build_restriction(self, record_count: Optional[int], direction: Optional[str], test_conditions: List[Dict]) -> SearchRestriction:
        """Build appropriate restriction based on parsed components"""
        
        if record_count and test_conditions:
            # Complex restriction with conditional logic
            base_desc = self._build_record_description(record_count, direction)
            condition_desc = self._build_conditions_description(test_conditions)
            
            description = f"{base_desc} where {condition_desc}" if condition_desc else base_desc
            
            return SearchRestriction(
                type="conditional_latest",
                description=description,
                record_count=record_count,
                direction=direction,
                conditions=test_conditions
            )
        
        elif record_count:
            # Simple record count restriction
            description = self._build_record_description(record_count, direction)
            
            return SearchRestriction(
                type="latest_records",
                description=description,
                record_count=record_count,
                direction=direction
            )
        
        elif test_conditions:
            # Test conditions without record count
            condition_desc = self._build_conditions_description(test_conditions)
            description = f"where {condition_desc}" if condition_desc else "Additional filtering conditions"
            
            return SearchRestriction(
                type="test_condition",
                description=description,
                conditions=test_conditions
            )
        
        else:
            return SearchRestriction(
                type="unknown",
                description="Unknown restriction type"
            )
    
    def _build_record_description(self, record_count: int, direction: Optional[str]) -> str:
        """Build description for record count restrictions"""
        if record_count == 1:
            return "Latest 1" if direction == "DESC" else "First 1"
        else:
            return f"Latest {record_count}" if direction == "DESC" else f"First {record_count}"
    
    def _build_conditions_description(self, test_conditions: List[Dict]) -> str:
        """Build description for test conditions"""
        condition_parts = []
        
        for cond in test_conditions:
            parts = []
            
            # Translate legacy column names to user-friendly terms
            column_name = self._translate_column_name(cond['column'])
            operator = cond['operator'].lower()  # Make operator lowercase
            
            # Add value set conditions - don't list the codes, just show the operator
            if cond.get('value_sets'):
                parts.append(f"{column_name} {operator}:")
            
            # Add range conditions
            if cond.get('range_values'):
                range_text = ' and '.join(cond['range_values'])  # Use lowercase 'and'
                if parts:
                    parts.append(f"and {range_text}")
                else:
                    parts.append(f"{column_name} {range_text}")
            
            if parts:
                condition_parts.append(' '.join(parts))
        
        return ' and '.join(condition_parts)  # Use lowercase 'and'
    
    def _translate_column_name(self, column: str) -> str:
        """Translate legacy EMIS column names to user-friendly terms"""
        translations = {
            'READCODE': 'SNOMED code',
            'SNOMEDCODE': 'SNOMED code',
            'CONCEPT_ID': 'SNOMED concept',
            'DRUGCODE': 'medication code',
            'CODE_DESCRIPTION': 'code description',
            'NUMERIC_VALUE': 'numeric value',
            'DATE': 'date',
            'AGE': 'age',
            'AGE_AT_EVENT': 'age at event'
        }
        return translations.get(column, column.lower())


# Convenience function for backward compatibility
def parse_restriction(restriction_elem: ET.Element, namespaces: Optional[Dict[str, str]] = None) -> Optional[SearchRestriction]:
    """Parse restriction elements like 'Latest 1' with conditional logic"""
    parser = RestrictionParser(namespaces)
    return parser.parse_restriction(restriction_elem)
