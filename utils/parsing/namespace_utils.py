"""
Namespace-agnostic helpers for XML parsing.
Supports mixed/absent prefixes and attributes with varying namespaces.
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Optional


def _to_emis_path(tag: str) -> str:
    """Convert a bare XPath tag/path to its emis-namespaced equivalent.

    Handles simple tags (``criteria``), nested paths (``allValues/values``),
    and descendant axes (``.//population``)."""
    prefix = ""
    rest = tag
    if rest.startswith(".//"):
        prefix = ".//"
        rest = rest[3:]
    elif rest.startswith("./"):
        prefix = "./"
        rest = rest[2:]
    segments = rest.split("/")
    emis_segments = [f"emis:{s}" if s and not s.startswith("emis:") else s for s in segments]
    return prefix + "/".join(emis_segments)


def findall_ns(elem: ET.Element, tag: str, namespaces: Optional[Dict[str, str]] = None) -> List[ET.Element]:
    """Find all matching elements using both bare and emis-namespaced tags.

    Returns a deduplicated list preserving discovery order.
    Replaces the common ``findall(tag, ns) + findall("emis:"+tag, ns)`` pattern."""
    namespaces = namespaces or {}
    results = list(elem.findall(tag, namespaces))
    if "emis" in namespaces:
        emis_tag = _to_emis_path(tag)
        if emis_tag != tag:
            results.extend(elem.findall(emis_tag, namespaces))
    # Deduplicate by memory id
    seen: set = set()
    unique: List[ET.Element] = []
    for e in results:
        eid = id(e)
        if eid not in seen:
            seen.add(eid)
            unique.append(e)
    return unique


def find_ns(elem: ET.Element, tag: str, namespaces: Optional[Dict[str, str]] = None) -> Optional[ET.Element]:
    """Find first matching element using both bare and emis-namespaced tags."""
    namespaces = namespaces or {}
    node = elem.find(tag, namespaces)
    if node is None and "emis" in namespaces:
        node = elem.find(_to_emis_path(tag), namespaces)
    return node


def get_text_ns(elem: Optional[ET.Element], tag: str, namespaces: Optional[Dict[str, str]] = None) -> str:
    """Find a child element by tag (namespace-aware) and return its stripped text."""
    if elem is None:
        return ""
    node = find_ns(elem, tag, namespaces)
    return node.text.strip() if node is not None and node.text else ""


def unique_elements(elements: List[ET.Element]) -> List[ET.Element]:
    """Deduplicate XML elements by memory identity, preserving order."""
    seen: set = set()
    unique: List[ET.Element] = []
    for elem in elements:
        eid = id(elem)
        if eid not in seen:
            seen.add(eid)
            unique.append(elem)
    return unique


def get_child_text_any(elem: ET.Element, candidate_tags: List[str], namespaces: Optional[Dict[str, str]] = None) -> str:
    """
    Find the first matching child by tag (supports namespaced and bare tags) and return stripped text.
    """
    namespaces = namespaces or {}
    for tag in candidate_tags:
        node = elem.find(tag, namespaces)
        if node is not None and node.text:
            return node.text.strip()
        # Only try emis namespace if it exists in namespaces
        if "emis" in namespaces:
            node = elem.find(f"emis:{tag}", namespaces)
            if node is not None and node.text:
                return node.text.strip()
    # Fallback: scan children by localname
    for child in elem:
        local = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if local in candidate_tags and child.text:
            return child.text.strip()
    return ""


def get_attr_any(elem: ET.Element, candidate_attrs: List[str]) -> str:
    """
    Fetch attribute value by trying candidate names and localname matching.
    """
    for attr in candidate_attrs:
        if attr in elem.attrib and elem.attrib[attr]:
            return elem.attrib[attr]
    # Localname match (handles namespaced attributes)
    for attr_key, attr_val in elem.attrib.items():
        local = attr_key.split('}')[-1] if '}' in attr_key else attr_key
        if local in candidate_attrs and attr_val:
            return attr_val
    return ""


def find_child_any(parent: ET.Element, candidate_tags: List[str], namespaces: Optional[Dict[str, str]] = None) -> Optional[ET.Element]:
    """
    Find the first matching child element by tag name.
    """
    namespaces = namespaces or {}
    for tag in candidate_tags:
        node = parent.find(tag, namespaces)
        if node is not None:
            return node
        # Only try emis namespace if it exists in namespaces
        if "emis" in namespaces:
            node = parent.find(f"emis:{tag}", namespaces) 
            if node is not None:
                return node
    # Fallback: scan children by localname
    for child in parent:
        local = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if local in candidate_tags:
            return child
    return None
