"""
Maps XML nodes and pattern results to canonical flags.
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, List
from .flag_registry import validate_flags
from ..pattern_plugins.base import PatternResult
from ..parsing.namespace_utils import get_child_text_any, get_attr_any, find_child_any


def map_element_flags(element: ET.Element, namespaces: Dict[str, str], pattern_results: List[PatternResult]) -> Dict[str, Any]:
    """
    Combine pattern flags and basic structural flags for an element.
    """
    flags: Dict[str, Any] = {}

    # Basic structure flags
    flags["xml_tag_name"] = element.tag.split("}")[-1] if "}" in element.tag else element.tag
    
    # Get element ID from child element or attribute
    elem_id_text = get_child_text_any(element, ["id"], namespaces)
    if not elem_id_text:
        elem_id_text = get_attr_any(element, ["id"])
    if elem_id_text:
        flags["element_id"] = elem_id_text

    # Aggregate pattern flags
    for result in pattern_results:
        flags.update(result.flags)

    return validate_flags(flags)


def map_value_set_flags(value_elem: ET.Element, namespaces: Dict[str, str], parent_flags: Dict[str, Any], values_container: ET.Element = None) -> Dict[str, Any]:
    """
    Map flags for individual value/code within a valueSet.
    
    Args:
        value_elem: The <value> element
        namespaces: XML namespaces
        parent_flags: Flags from parent context
        values_container: The <values> container element (optional, for sibling access)
    """
    flags = dict(parent_flags)

    code_val = value_elem.text or ""
    if code_val:
        flags["code_value"] = code_val.strip()

    # The displayName is a sibling of <value> within the <values> container
    display_name = ""
    if values_container is not None:
        # Look for displayName as direct child of values container
        display_name = get_child_text_any(values_container, ["displayName"], namespaces)
    
    # Fallback: check if displayName is somehow a child of the value element
    if not display_name:
        display_name = get_child_text_any(value_elem, ["displayName"], namespaces)
    
    if display_name:
        flags["display_name"] = display_name

    legacy_value = ""
    if values_container is not None:
        legacy_value = get_child_text_any(values_container, ["legacyValue"], namespaces)
    if not legacy_value:
        legacy_value = get_child_text_any(value_elem, ["legacyValue"], namespaces)
    if legacy_value:
        flags["legacy_value"] = legacy_value

    cluster_code = ""
    if values_container is not None:
        cluster_code = get_child_text_any(values_container, ["clusterCode"], namespaces)
    if not cluster_code:
        cluster_code = get_child_text_any(value_elem, ["clusterCode"], namespaces)
    if cluster_code:
        flags["cluster_code"] = cluster_code

    # Check for includeChildren - can be in values container or value element
    include_children_text = ""
    if values_container is not None:
        include_children_text = get_child_text_any(values_container, ["includeChildren"], namespaces)
    if not include_children_text:
        include_children_text = get_child_text_any(value_elem, ["includeChildren"], namespaces)
        
    if include_children_text:
        flags["include_children"] = include_children_text.lower() == "true"
    elif "include_children" not in flags:
        flags["include_children"] = False

    # Check for inactive flag
    inactive_text = get_child_text_any(value_elem, ["inactive"], namespaces)
    if inactive_text:
        flags["inactive"] = inactive_text.lower() == "true"

    # is_emisinternal flag is now set during XML parsing stage in value_set_parser.py

    return validate_flags(flags)
