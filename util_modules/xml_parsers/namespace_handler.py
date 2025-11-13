"""
Universal Namespace Handler for EMIS XML
Handles all mixed namespace patterns in one centralized location.
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any


class NamespaceHandler:
    """
    Centralized namespace handling for EMIS XML files.
    Handles mixed namespace structures where elements can be either namespaced or non-namespaced.
    """
    
    def __init__(self, namespaces: Optional[Dict[str, str]] = None):
        """
        Initialize namespace handler.
        
        Args:
            namespaces: Namespace dictionary (defaults to EMIS namespace)
        """
        self.namespaces = namespaces or {'emis': 'http://www.e-mis.com/emisopen'}
    
    def find(self, parent: ET.Element, element_name: str) -> Optional[ET.Element]:
        """
        Find a single element handling both namespaced and non-namespaced variants.
        
        Args:
            parent: Parent element to search within
            element_name: Element name (without namespace prefix)
            
        Returns:
            Element if found, None otherwise
        """
        # Try non-namespaced first
        element = parent.find(element_name)
        if element is None:
            # Try namespaced
            element = parent.find(f'emis:{element_name}', self.namespaces)
        return element
    
    def find_with_path(self, parent: ET.Element, xpath: str) -> Optional[ET.Element]:
        """
        Find a single element using XPath, handling both namespaced and non-namespaced variants.
        
        Args:
            parent: Parent element to search within
            xpath: XPath expression (without namespace prefixes)
            
        Returns:
            Element if found, None otherwise
        """
        # Try non-namespaced first
        element = parent.find(xpath)
        if element is None:
            # Convert xpath to namespaced version
            namespaced_xpath = self._add_namespace_to_xpath(xpath)
            element = parent.find(namespaced_xpath, self.namespaces)
        return element
    
    def findall(self, parent: ET.Element, element_name: str) -> List[ET.Element]:
        """
        Find all elements handling both namespaced and non-namespaced variants.
        
        Args:
            parent: Parent element to search within
            element_name: Element name (without namespace prefix)
            
        Returns:
            List of elements (may be empty)
        """
        # Get non-namespaced elements first
        elements = parent.findall(element_name)
        # Add namespaced elements (avoiding duplicates)
        namespaced_elements = parent.findall(f'emis:{element_name}', self.namespaces)
        elements.extend([elem for elem in namespaced_elements if elem not in elements])
        return elements
    
    def findall_with_path(self, parent: ET.Element, xpath: str) -> List[ET.Element]:
        """
        Find all elements using XPath, handling both namespaced and non-namespaced variants.
        
        Args:
            parent: Parent element to search within
            xpath: XPath expression (without namespace prefixes)
            
        Returns:
            List of elements (may be empty)
        """
        # Get non-namespaced elements first
        elements = parent.findall(xpath)
        # Add namespaced elements (avoiding duplicates)
        namespaced_xpath = self._add_namespace_to_xpath(xpath)
        namespaced_elements = parent.findall(namespaced_xpath, self.namespaces)
        elements.extend([elem for elem in namespaced_elements if elem not in elements])
        return elements
    
    def get_text(self, element: Optional[ET.Element], default: str = "") -> str:
        """
        Safely get text from an element.
        
        Args:
            element: Element to get text from
            default: Default value if element is None or has no text
            
        Returns:
            Element text or default value
        """
        if element is not None and element.text:
            return element.text.strip()
        return default
    
    def get_text_from_child(self, parent: ET.Element, child_name: str, default: str = "") -> str:
        """
        Get text from a child element, handling both namespaced and non-namespaced variants.
        
        Args:
            parent: Parent element
            child_name: Child element name (without namespace prefix)
            default: Default value if child not found or has no text
            
        Returns:
            Child element text or default value
        """
        child = self.find(parent, child_name)
        return self.get_text(child, default)
    
    def _add_namespace_to_xpath(self, xpath: str) -> str:
        """
        Convert a non-namespaced XPath to a namespaced one.
        
        Args:
            xpath: XPath expression without namespace prefixes
            
        Returns:
            XPath expression with emis: namespace prefixes
        """
        # Handle different XPath patterns
        if xpath.startswith('.//'):
            # Descendant search: .//element -> .//emis:element
            element_part = xpath[3:]
            return f'.//emis:{element_part}'
        elif xpath.startswith('./'):
            # Child search: ./element -> ./emis:element
            element_part = xpath[2:]
            return f'./emis:{element_part}'
        elif '/' in xpath:
            # Complex path: convert each element
            parts = xpath.split('/')
            namespaced_parts = []
            for part in parts:
                if part and not part.startswith('emis:') and part != '.' and part != '..':
                    namespaced_parts.append(f'emis:{part}')
                else:
                    namespaced_parts.append(part)
            return '/'.join(namespaced_parts)
        else:
            # Simple element name
            return f'emis:{xpath}'


# Convenience functions for backward compatibility
def find_element_mixed(parent: ET.Element, element_name: str, namespaces: Optional[Dict[str, str]] = None) -> Optional[ET.Element]:
    """
    Convenience function to find an element handling mixed namespaces.
    
    Args:
        parent: Parent element to search within
        element_name: Element name (without namespace prefix)
        namespaces: Optional namespace dictionary
        
    Returns:
        Element if found, None otherwise
    """
    handler = NamespaceHandler(namespaces)
    return handler.find(parent, element_name)


def findall_elements_mixed(parent: ET.Element, element_name: str, namespaces: Optional[Dict[str, str]] = None) -> List[ET.Element]:
    """
    Convenience function to find all elements handling mixed namespaces.
    
    Args:
        parent: Parent element to search within
        element_name: Element name (without namespace prefix)
        namespaces: Optional namespace dictionary
        
    Returns:
        List of elements (may be empty)
    """
    handler = NamespaceHandler(namespaces)
    return handler.findall(parent, element_name)


def get_text_mixed(parent: ET.Element, element_name: str, default: str = "", namespaces: Optional[Dict[str, str]] = None) -> str:
    """
    Convenience function to get text from a child element handling mixed namespaces.
    
    Args:
        parent: Parent element
        element_name: Child element name (without namespace prefix)
        default: Default value if child not found or has no text
        namespaces: Optional namespace dictionary
        
    Returns:
        Child element text or default value
    """
    handler = NamespaceHandler(namespaces)
    return handler.get_text_from_child(parent, element_name, default)
