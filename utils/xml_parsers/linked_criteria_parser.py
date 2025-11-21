"""
Linked criteria parsing utilities for EMIS XML
Handles parsing of linked criteria and their relationships
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
from .base_parser import XMLParserBase, get_namespaces


class LinkedCriteriaParser(XMLParserBase):
    """Parser for linked criteria elements"""
    
    def parse_linked_criterion(self, linked_elem: ET.Element) -> Optional[Any]:
        """Parse linked criteria for complex relationships"""
        try:
            # Parse relationship information - handle both namespaced and non-namespaced
            relationship_elem = self.find_element_both(linked_elem, 'relationship')
            relationship_info = self._parse_relationship(relationship_elem) if relationship_elem else {}
            
            # Parse the actual criterion within the linked element - handle both namespaced and non-namespaced
            criterion_elem = self.find_element_both(linked_elem, 'criterion')
            if criterion_elem is not None:
                # Import here to avoid circular imports
                from .criterion_parser import CriterionParser
                criterion_parser = CriterionParser(self.namespaces)
                criterion = criterion_parser.parse_criterion(criterion_elem)
                
                # Add relationship info to the criterion if parsed successfully
                if criterion and relationship_info:
                    # Store relationship info in the criterion's metadata
                    if not hasattr(criterion, 'relationship'):
                        criterion.relationship = relationship_info
                
                return criterion
        except Exception as e:
            print(f"Error parsing linked criterion: {e}")
        
        return None
    
    def _parse_relationship(self, relationship_elem: ET.Element) -> Dict[str, Any]:
        """Parse relationship information between linked criteria"""
        try:
            relationship = {
                'parent_column': self.parse_child_text(relationship_elem, 'parentColumn'),
                'parent_column_display_name': self.parse_child_text(relationship_elem, 'parentColumnDisplayName'),
                'child_column': self.parse_child_text(relationship_elem, 'childColumn'),
                'child_column_display_name': self.parse_child_text(relationship_elem, 'childColumnDisplayName')
            }
            
            # Parse range value for the relationship - handle both namespaced and non-namespaced
            range_value_elem = self.find_element_both(relationship_elem, 'rangeValue')
            if range_value_elem is not None:
                relationship['range_value'] = self._parse_relationship_range(range_value_elem)
            
            return relationship
        except Exception as e:
            print(f"Error parsing relationship: {e}")
            return {}
    
    def _parse_relationship_range(self, range_value_elem: ET.Element) -> Dict[str, Any]:
        """Parse range value within a relationship"""
        try:
            range_info = {}
            
            # Parse range from - handle both namespaced and non-namespaced
            range_from_elem = self.find_element_both(range_value_elem, 'rangeFrom')
            if range_from_elem is not None:
                range_info['from'] = self._parse_range_boundary(range_from_elem)
            
            # Parse range to - handle both namespaced and non-namespaced
            range_to_elem = self.find_element_both(range_value_elem, 'rangeTo')
            if range_to_elem is not None:
                range_info['to'] = self._parse_range_boundary(range_to_elem)
            
            return range_info
        except Exception as e:
            print(f"Error parsing relationship range: {e}")
            return {}
    
    def _parse_range_boundary(self, boundary_elem: ET.Element) -> Dict[str, Any]:
        """Parse range boundary information"""
        try:
            boundary = {
                'operator': self.parse_child_text(boundary_elem, 'operator')
            }
            
            # Parse value element - handle both namespaced and non-namespaced
            value_elem = self.find_element_both(boundary_elem, 'value')
            if value_elem is not None:
                boundary.update({
                    'value': self.get_text(value_elem),
                    'unit': self.get_attribute(value_elem, 'unit'),
                    'relation': self.get_attribute(value_elem, 'relation')
                })
            
            return boundary
        except Exception as e:
            print(f"Error parsing range boundary: {e}")
            return {}
    
    def parse_relationship_description(self, relationship: Dict[str, Any]) -> str:
        """Generate human-readable description of a relationship"""
        try:
            parent_col = relationship.get('parent_column_display_name') or relationship.get('parent_column', '')
            child_col = relationship.get('child_column_display_name') or relationship.get('child_column', '')
            
            base_desc = f"Link {parent_col} to {child_col}"
            
            # Add range information if present
            range_value = relationship.get('range_value', {})
            if range_value:
                range_parts = []
                
                if 'from' in range_value:
                    from_info = range_value['from']
                    operator = from_info.get('operator', '')
                    value = from_info.get('value', '')
                    unit = from_info.get('unit', '')
                    
                    if operator and value:
                        range_parts.append(f"{operator} {value} {unit}".strip())
                
                if 'to' in range_value:
                    to_info = range_value['to']
                    operator = to_info.get('operator', '')
                    value = to_info.get('value', '')
                    unit = to_info.get('unit', '')
                    
                    if operator and value:
                        range_parts.append(f"{operator} {value} {unit}".strip())
                
                if range_parts:
                    range_desc = " AND ".join(range_parts)
                    base_desc += f" where {range_desc}"
            
            return base_desc
        except Exception:
            return "Complex relationship"


# Convenience function for backward compatibility
def parse_linked_criterion(linked_elem: ET.Element, namespaces: Optional[Dict[str, str]] = None) -> Optional[Any]:
    """Parse linked criteria for complex relationships"""
    parser = LinkedCriteriaParser(namespaces)
    return parser.parse_linked_criterion(linked_elem)
