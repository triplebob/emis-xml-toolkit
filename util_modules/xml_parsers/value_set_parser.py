"""
Value set parsing utilities for EMIS XML
Handles parsing of clinical code value sets and code systems
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
from .base_parser import XMLParserBase, get_namespaces


class ValueSetParser(XMLParserBase):
    """Parser for value set elements"""
    
    def _is_medication_from_context(self, code_system, table_context='', column_context=''):
        """
        Determine if a code is a medication based on code system and table/column context.
        Uses the same logic as xml_utils.is_medication_code_system.
        """
        from .xml_utils import is_medication_code_system
        return is_medication_code_system(code_system, table_context, column_context)
    
    def parse_value_set(self, valueset_elem: ET.Element) -> Optional[Dict]:
        """Parse value set information"""
        try:
            code_system = self.parse_child_text(valueset_elem, 'codeSystem')
            result = {
                'id': self.parse_child_text(valueset_elem, 'id'),
                'code_system': code_system,
                'description': self.parse_child_text(valueset_elem, 'description'),
                'values': []
            }
            
            # Parse individual values
            # Handle both namespaced and non-namespaced values elements
            namespaced_values = self.find_elements(valueset_elem, './/emis:values')
            non_namespaced_values = valueset_elem.findall('.//values')
            all_values_elems = non_namespaced_values + [v for v in namespaced_values if v not in non_namespaced_values]
            for values_elem in all_values_elems:
                value_data = self._parse_value_entry(values_elem, code_system)
                if value_data:
                    result['values'].append(value_data)
            
            # Parse allValues if present (alternative structure) - handle both namespaced and non-namespaced
            all_values_elem = self.find_element_both(valueset_elem, 'allValues')
            if all_values_elem is not None:
                result['all_values'] = self._parse_all_values(all_values_elem, code_system)
            
            # If no description at valueSet level, try to get displayName from first values element
            if not result['description'] and result['values']:
                for value_item in result['values']:
                    if value_item.get('display_name'):
                        result['description'] = value_item['display_name']
                        break
            
            # Clean up the description to extract just the meaningful name
            if result['description']:
                result['description'] = self._clean_refset_description(result['description'])
            
            return result if result['values'] or result.get('all_values') else None
            
        except Exception as e:
            print(f"Error parsing value set: {e}")
            return None
    
    def _parse_value_entry(self, values_elem: ET.Element, code_system: str = '') -> Optional[Dict]:
        """Parse individual value entry within a value set"""
        try:
            # Handle both namespaced and non-namespaced displayName elements
            display_name_elem = values_elem.find('displayName')
            if display_name_elem is None:
                display_name_elem = values_elem.find('emis:displayName', self.namespaces)
            display_name = self.get_text(display_name_elem) if display_name_elem is not None else ""
            
            return {
                'value': self.parse_child_text(values_elem, 'value'),
                'display_name': display_name,
                'include_children': self._parse_boolean_child(values_elem, 'includeChildren'),
                'is_refset': self._parse_boolean_child(values_elem, 'isRefset'),
                'is_medication': self._is_medication_from_context(code_system, '', ''),  # Basic medication detection based on code system
                'code_system': code_system
            }
        except Exception as e:
            print(f"Error parsing value entry: {e}")
            return None
    
    def _parse_all_values(self, all_values_elem: ET.Element, parent_code_system: str = '') -> Dict:
        """Parse allValues structure (alternative to individual values)"""
        try:
            # allValues can have its own codeSystem or inherit from parent
            all_values_code_system = self.parse_child_text(all_values_elem, 'codeSystem') or parent_code_system
            result = {
                'code_system': all_values_code_system,
                'values': []
            }
            
            # Parse nested values within allValues - handle both namespaced and non-namespaced
            namespaced_values = self.find_elements(all_values_elem, './/emis:values')
            non_namespaced_values = all_values_elem.findall('.//values')
            all_nested_values = non_namespaced_values + [v for v in namespaced_values if v not in non_namespaced_values]
            for values_elem in all_nested_values:
                value_data = self._parse_value_entry(values_elem, all_values_code_system)
                if value_data:
                    result['values'].append(value_data)
            
            return result
        except Exception as e:
            print(f"Error parsing all values: {e}")
            return {}
    
    def _parse_boolean_child(self, parent: ET.Element, child_name: str) -> bool:
        """Parse boolean value from child element - handles both namespaced and non-namespaced"""
        child_elem = self.find_element_both(parent, child_name)
        if child_elem is not None:
            return self.get_text(child_elem).lower() == 'true'
        return False
    
    def _clean_refset_description(self, description: str) -> str:
        """Clean up refset descriptions to extract just the meaningful name"""
        if not description:
            return description
        
        import re
        
        # Handle pattern: "Refset: ETHNALL_COD[999022611000230100]" -> "ETHNALL_COD"
        match = re.match(r'Refset:\s*([^[\]]+)\[.*\]', description)
        if match:
            return match.group(1).strip()
        
        # Handle pattern: "Refset: ETHNALL_COD" (no brackets) -> "ETHNALL_COD" 
        match = re.match(r'Refset:\s*(.+)', description)
        if match:
            return match.group(1).strip()
        
        # If no pattern matches, return original (handles cases like "ETH2016WB_COD")
        return description


# Convenience function for backward compatibility
def parse_value_set(valueset_elem: ET.Element, namespaces: Optional[Dict[str, str]] = None) -> Optional[Dict]:
    """Parse value set information"""
    parser = ValueSetParser(namespaces)
    return parser.parse_value_set(valueset_elem)
