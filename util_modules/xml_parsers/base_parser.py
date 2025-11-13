"""
Base XML parsing utilities and common functions
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional
from .namespace_handler import NamespaceHandler


def get_namespaces() -> Dict[str, str]:
    """Get standard EMIS XML namespaces"""
    return {
        'emis': 'http://www.e-mis.com/emisopen'
    }


class XMLParserBase:
    """Base class for XML parsers with common utilities"""
    
    def __init__(self, namespaces: Optional[Dict[str, str]] = None):
        self.namespaces = namespaces or get_namespaces()
        self.ns = NamespaceHandler(self.namespaces)  # Add namespace handler
    
    def find_element(self, parent: ET.Element, xpath: str) -> Optional[ET.Element]:
        """Find a single element using XPath with namespaces"""
        try:
            return parent.find(xpath, self.namespaces)
        except Exception:
            return None
    
    def find_element_both(self, parent: ET.Element, element_name: str) -> Optional[ET.Element]:
        """Find element handling both namespaced (emis:name) and non-namespaced (name)"""
        return self.ns.find(parent, element_name)
    
    def find_elements(self, parent: ET.Element, xpath: str) -> list:
        """Find multiple elements using XPath with namespaces"""
        try:
            return parent.findall(xpath, self.namespaces)
        except Exception:
            return []
    
    def find_elements_both(self, parent: ET.Element, element_name: str) -> list:
        """Find elements handling both namespaced (emis:name) and non-namespaced (name)"""
        return self.ns.findall(parent, element_name)
    
    def get_text(self, element: Optional[ET.Element], default: str = "") -> str:
        """Safely get text from an element"""
        return self.ns.get_text(element, default)
    
    def get_attribute(self, element: Optional[ET.Element], attr: str, default: str = "") -> str:
        """Safely get attribute from an element"""
        if element is not None:
            return element.get(attr, default)
        return default
    
    def get_bool_attribute(self, element: Optional[ET.Element], attr: str, default: bool = False) -> bool:
        """Get boolean attribute from an element"""
        if element is not None:
            value = element.get(attr, "").lower()
            return value in ("true", "1", "yes")
        return default
    
    def get_child_text(self, parent: ET.Element, child_name: str, default: str = "") -> str:
        """Get text from a child element, handling mixed namespaces"""
        return self.ns.get_text_from_child(parent, child_name, default)
    
    def find_with_path(self, parent: ET.Element, xpath: str) -> Optional[ET.Element]:
        """Find element using XPath, handling mixed namespaces"""
        return self.ns.find_with_path(parent, xpath)
    
    def findall_with_path(self, parent: ET.Element, xpath: str) -> list:
        """Find all elements using XPath, handling mixed namespaces"""
        return self.ns.findall_with_path(parent, xpath)
    
    def parse_child_text(self, parent: ET.Element, child_name: str, default: str = "") -> str:
        """Parse text from a child element - handles both namespaced and non-namespaced"""
        # Try non-namespaced first, then namespaced
        child = parent.find(child_name) or self.find_element(parent, f"emis:{child_name}")
        return self.get_text(child, default)
    
    def parse_child_attribute(self, parent: ET.Element, child_name: str, attr: str, default: str = "") -> str:
        """Parse attribute from a child element - handles both namespaced and non-namespaced"""
        # Try non-namespaced first, then namespaced
        child = parent.find(child_name) or self.find_element(parent, f"emis:{child_name}")
        return self.get_attribute(child, attr, default)
