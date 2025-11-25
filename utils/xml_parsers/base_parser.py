"""
Base XML parsing utilities and common functions
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, Union, List
from .namespace_handler import NamespaceHandler
from ..common.error_handling import (
    ParseResult, XMLParsingContext, XMLParsingError,
    create_xml_parsing_context, safe_xml_parse,
    ErrorHandler
)


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
        self.error_handler = ErrorHandler(logger_name=f"{__name__}.{self.__class__.__name__}")
        self._parsing_errors = []  # Collect errors during parsing
        self._parsing_warnings = []  # Collect warnings during parsing
    
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
    
    # New structured parsing methods
    def safe_find_element(self, parent: ET.Element, xpath: str, element_name: str = None) -> ParseResult:
        """Safely find element with structured error reporting"""
        xml_context = create_xml_parsing_context(
            element_name=element_name or xpath,
            element_path=xpath,
            parent_element=parent.tag if parent is not None else None,
            parsing_stage="element_lookup"
        )
        
        if parent is None:
            return ParseResult.failure_result(
                ["Parent element is None"], 
                xml_context
            )
        
        try:
            element = parent.find(xpath, self.namespaces)
            if element is None:
                warning = f"Element '{xpath}' not found in parent '{parent.tag}'"
                return ParseResult.partial_result(None, [warning], xml_context)
            
            return ParseResult.success_result(element)
            
        except Exception as e:
            error_msg = f"XPath query failed for '{xpath}': {str(e)}"
            return ParseResult.failure_result([error_msg], xml_context)
    
    def safe_find_elements(self, parent: ET.Element, xpath: str, element_name: str = None) -> ParseResult:
        """Safely find multiple elements with structured error reporting"""
        xml_context = create_xml_parsing_context(
            element_name=element_name or xpath,
            element_path=xpath,
            parent_element=parent.tag if parent is not None else None,
            parsing_stage="elements_lookup"
        )
        
        if parent is None:
            return ParseResult.failure_result(
                ["Parent element is None"], 
                xml_context
            )
        
        try:
            elements = parent.findall(xpath, self.namespaces)
            if not elements:
                warning = f"No elements found for '{xpath}' in parent '{parent.tag}'"
                return ParseResult.partial_result([], [warning], xml_context)
            
            return ParseResult.success_result(elements)
            
        except Exception as e:
            error_msg = f"XPath query failed for '{xpath}': {str(e)}"
            return ParseResult.failure_result([error_msg], xml_context)
    
    def safe_get_text(self, element: ET.Element, element_name: str = None, 
                      expected_format: str = None) -> ParseResult:
        """Safely get element text with validation"""
        xml_context = create_xml_parsing_context(
            element_name=element_name or (element.tag if element is not None else "unknown"),
            expected_format=expected_format,
            parsing_stage="text_extraction"
        )
        
        if element is None:
            return ParseResult.failure_result(
                ["Element is None - cannot extract text"], 
                xml_context
            )
        
        try:
            text = self.ns.get_text(element)
            if not text and expected_format:
                warning = f"Empty text for element '{element.tag}' (expected format: {expected_format})"
                return ParseResult.partial_result(text, [warning], xml_context)
            
            return ParseResult.success_result(text)
            
        except Exception as e:
            error_msg = f"Failed to extract text from element '{element.tag}': {str(e)}"
            return ParseResult.failure_result([error_msg], xml_context)
    
    def safe_get_attribute(self, element: ET.Element, attr: str, 
                          expected_format: str = None, required: bool = False) -> ParseResult:
        """Safely get element attribute with validation"""
        xml_context = create_xml_parsing_context(
            element_name=element.tag if element is not None else "unknown",
            attribute_name=attr,
            expected_format=expected_format,
            parsing_stage="attribute_extraction"
        )
        
        if element is None:
            return ParseResult.failure_result(
                ["Element is None - cannot extract attribute"], 
                xml_context
            )
        
        try:
            value = element.get(attr)
            
            if value is None and required:
                error_msg = f"Required attribute '{attr}' missing from element '{element.tag}'"
                return ParseResult.failure_result([error_msg], xml_context)
            
            if value is None:
                warning = f"Optional attribute '{attr}' not found in element '{element.tag}'"
                return ParseResult.partial_result("", [warning], xml_context)
            
            if expected_format and not self._validate_format(value, expected_format):
                warning = f"Attribute '{attr}' value '{value}' doesn't match expected format '{expected_format}'"
                return ParseResult.partial_result(value, [warning], xml_context)
            
            return ParseResult.success_result(value)
            
        except Exception as e:
            error_msg = f"Failed to extract attribute '{attr}' from element '{element.tag}': {str(e)}"
            return ParseResult.failure_result([error_msg], xml_context)
    
    def _validate_format(self, value: str, expected_format: str) -> bool:
        """Basic format validation"""
        if expected_format == "numeric":
            try:
                float(value)
                return True
            except ValueError:
                return False
        elif expected_format == "boolean":
            return value.lower() in ("true", "false", "1", "0", "yes", "no")
        elif expected_format == "date":
            # Basic date format check - can be enhanced
            import re
            date_pattern = r'\d{4}-\d{2}-\d{2}'
            return bool(re.match(date_pattern, value))
        
        return True  # Unknown format, assume valid
    
    def clear_errors(self):
        """Clear accumulated parsing errors and warnings"""
        self._parsing_errors.clear()
        self._parsing_warnings.clear()
    
    def get_parsing_summary(self) -> Dict[str, Any]:
        """Get summary of parsing errors and warnings"""
        return {
            "errors": self._parsing_errors.copy(),
            "warnings": self._parsing_warnings.copy(),
            "error_count": len(self._parsing_errors),
            "warning_count": len(self._parsing_warnings)
        }
    
    def add_parsing_error(self, error: str, context: XMLParsingContext = None):
        """Add a parsing error to the collection"""
        error_entry = {"message": error}
        if context:
            error_entry["context"] = context
        self._parsing_errors.append(error_entry)
    
    def add_parsing_warning(self, warning: str, context: XMLParsingContext = None):
        """Add a parsing warning to the collection"""
        warning_entry = {"message": warning}
        if context:
            warning_entry["context"] = context
        self._parsing_warnings.append(warning_entry)
    
    # XML Structure validation methods
    def validate_xml_structure(self, root_element: ET.Element, expected_schema: Dict[str, Any]) -> ParseResult:
        """
        Validate XML structure against expected schema patterns
        
        Args:
            root_element: Root XML element to validate
            expected_schema: Dictionary defining expected structure
                {
                    'required_elements': ['element1', 'element2'],
                    'optional_elements': ['element3'],
                    'required_attributes': {'element1': ['attr1', 'attr2']},
                    'namespaces': ['emis'],
                    'max_depth': 10
                }
        """
        xml_context = create_xml_parsing_context(
            element_name=root_element.tag if root_element is not None else "unknown",
            parsing_stage="structure_validation"
        )
        
        if root_element is None:
            return ParseResult.failure_result(
                ["Root element is None - cannot validate structure"],
                xml_context
            )
        
        errors = []
        warnings = []
        validation_results = {}
        
        try:
            # Validate required elements
            if 'required_elements' in expected_schema:
                required_results = self._validate_required_elements(
                    root_element, 
                    expected_schema['required_elements'],
                    errors, 
                    warnings
                )
                validation_results['required_elements'] = required_results
            
            # Validate element depth
            if 'max_depth' in expected_schema:
                depth_result = self._validate_element_depth(
                    root_element,
                    expected_schema['max_depth'],
                    warnings
                )
                validation_results['depth_check'] = depth_result
            
            # Validate namespace usage
            if 'namespaces' in expected_schema:
                namespace_result = self._validate_namespace_usage(
                    root_element,
                    expected_schema['namespaces'],
                    warnings
                )
                validation_results['namespace_check'] = namespace_result
            
            # Validate required attributes
            if 'required_attributes' in expected_schema:
                attr_result = self._validate_required_attributes(
                    root_element,
                    expected_schema['required_attributes'],
                    errors,
                    warnings
                )
                validation_results['attribute_check'] = attr_result
            
            # Check for malformed XML patterns
            malformed_result = self._check_malformed_patterns(root_element, warnings)
            validation_results['malformed_check'] = malformed_result
            
            if errors:
                return ParseResult.failure_result(errors, xml_context)
            elif warnings:
                return ParseResult.partial_result(validation_results, warnings, xml_context)
            else:
                return ParseResult.success_result(validation_results)
                
        except Exception as e:
            error_msg = f"Unexpected error during structure validation: {str(e)}"
            return ParseResult.failure_result([error_msg], xml_context)
    
    def _validate_required_elements(self, root: ET.Element, required: List[str], 
                                   errors: list, warnings: list) -> Dict[str, bool]:
        """Validate that required elements are present"""
        results = {}
        
        for req_element in required:
            # Check both namespaced and non-namespaced versions
            found_elements = (
                root.findall(f".//{req_element}") + 
                root.findall(f".//emis:{req_element}", self.namespaces)
            )
            
            if not found_elements:
                errors.append(f"Required element '{req_element}' not found")
                results[req_element] = False
            else:
                results[req_element] = True
                
                # Check for duplicates where they shouldn't exist
                if len(found_elements) > 1:
                    warnings.append(f"Multiple instances of '{req_element}' found ({len(found_elements)})")
        
        return results
    
    def _validate_element_depth(self, root: ET.Element, max_depth: int, warnings: list) -> Dict[str, Any]:
        """Validate XML element depth to detect unusually deep nesting"""
        def get_depth(element, current_depth=0):
            if not list(element):
                return current_depth
            return max(get_depth(child, current_depth + 1) for child in element)
        
        actual_depth = get_depth(root)
        
        result = {
            'actual_depth': actual_depth,
            'max_allowed': max_depth,
            'within_limits': actual_depth <= max_depth
        }
        
        if actual_depth > max_depth:
            warnings.append(f"XML depth ({actual_depth}) exceeds recommended maximum ({max_depth})")
        elif actual_depth > max_depth * 0.8:  # Warn at 80% of limit
            warnings.append(f"XML depth ({actual_depth}) approaching maximum ({max_depth})")
        
        return result
    
    def _validate_namespace_usage(self, root: ET.Element, expected_namespaces: List[str], 
                                 warnings: list) -> Dict[str, Any]:
        """Validate namespace usage patterns"""
        # Find all unique namespaces in use
        used_namespaces = set()
        
        def extract_namespaces(element):
            # Extract namespace from element tag
            if '}' in element.tag:
                namespace = element.tag.split('}')[0].strip('{')
                used_namespaces.add(namespace)
            
            # Check attributes
            for attr_name in element.attrib:
                if '}' in attr_name:
                    namespace = attr_name.split('}')[0].strip('{')
                    used_namespaces.add(namespace)
            
            # Process children
            for child in element:
                extract_namespaces(child)
        
        extract_namespaces(root)
        
        # Check against expected namespaces
        expected_namespace_uris = []
        for ns_prefix in expected_namespaces:
            if ns_prefix in self.namespaces:
                expected_namespace_uris.append(self.namespaces[ns_prefix])
        
        unexpected_namespaces = used_namespaces - set(expected_namespace_uris)
        missing_expected = set(expected_namespace_uris) - used_namespaces
        
        if unexpected_namespaces:
            warnings.append(f"Unexpected namespaces found: {list(unexpected_namespaces)}")
        
        if missing_expected:
            warnings.append(f"Expected namespaces not found: {list(missing_expected)}")
        
        return {
            'used_namespaces': list(used_namespaces),
            'expected_namespaces': expected_namespace_uris,
            'unexpected_namespaces': list(unexpected_namespaces),
            'missing_expected': list(missing_expected)
        }
    
    def _validate_required_attributes(self, root: ET.Element, required_attrs: Dict[str, List[str]], 
                                     errors: list, warnings: list) -> Dict[str, Dict[str, bool]]:
        """Validate required attributes on specific elements"""
        results = {}
        
        for element_name, required_attr_list in required_attrs.items():
            # Find all matching elements
            elements = (
                root.findall(f".//{element_name}") + 
                root.findall(f".//emis:{element_name}", self.namespaces)
            )
            
            if not elements:
                warnings.append(f"No elements found for attribute validation: '{element_name}'")
                results[element_name] = {}
                continue
            
            element_results = {}
            for attr_name in required_attr_list:
                found_with_attr = [elem for elem in elements if attr_name in elem.attrib]
                
                if not found_with_attr:
                    errors.append(f"Required attribute '{attr_name}' missing from all '{element_name}' elements")
                    element_results[attr_name] = False
                elif len(found_with_attr) < len(elements):
                    warnings.append(f"Attribute '{attr_name}' missing from some '{element_name}' elements")
                    element_results[attr_name] = True  # Partial success
                else:
                    element_results[attr_name] = True
            
            results[element_name] = element_results
        
        return results
    
    def _check_malformed_patterns(self, root: ET.Element, warnings: list) -> Dict[str, Any]:
        """Check for common malformed XML patterns"""
        issues = {
            'empty_elements': 0,
            'very_long_text': 0,
            'suspicious_characters': 0,
            'unusual_tag_names': []
        }
        
        def check_element(element):
            # Check for empty elements that should have content
            if element.text is None and len(element) == 0 and len(element.attrib) == 0:
                issues['empty_elements'] += 1
            
            # Check for very long text content
            if element.text and len(element.text) > 1000:
                issues['very_long_text'] += 1
            
            # Check for suspicious characters
            if element.text:
                suspicious_chars = ['<', '>', '&amp;amp;', '&lt;', '&gt;']
                if any(char in element.text for char in suspicious_chars):
                    issues['suspicious_characters'] += 1
            
            # Check for unusual tag names
            tag_name = element.tag.split('}')[-1] if '}' in element.tag else element.tag
            if not tag_name.replace('_', '').replace('-', '').isalnum():
                if tag_name not in issues['unusual_tag_names']:
                    issues['unusual_tag_names'].append(tag_name)
            
            # Process children
            for child in element:
                check_element(child)
        
        check_element(root)
        
        # Generate warnings for significant issues
        if issues['empty_elements'] > 10:
            warnings.append(f"High number of empty elements detected ({issues['empty_elements']})")
        
        if issues['very_long_text'] > 0:
            warnings.append(f"Elements with very long text content detected ({issues['very_long_text']})")
        
        if issues['suspicious_characters'] > 0:
            warnings.append(f"Elements with suspicious characters detected ({issues['suspicious_characters']})")
        
        if issues['unusual_tag_names']:
            warnings.append(f"Unusual tag names detected: {issues['unusual_tag_names'][:5]}")  # Limit to first 5
        
        return issues
