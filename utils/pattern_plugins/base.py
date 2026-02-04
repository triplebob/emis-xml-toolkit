"""
Pattern plugin definitions for the parsing pipeline.
Patterns are callable detectors that return structured results.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, Any, Optional, List
import xml.etree.ElementTree as ET


class PluginPriority:
    """Standard priority tiers for plugin execution order.

    Lower values run first. Use these constants for consistency.
    """
    CRITICAL = 10    # Must run first (e.g., classification that affects others)
    HIGH = 30        # Core structural patterns
    NORMAL = 50      # Standard pattern detection
    DEFAULT = 100    # Unspecified priority (backwards compatibility)
    LOW = 150        # Supplementary patterns


@dataclass
class PluginMetadata:
    """Metadata for a pattern plugin.

    Attributes:
        id: Unique identifier for the plugin (required)
        version: Semantic version string (default "1.0.0")
        description: Human-readable description
        author: Plugin author
        priority: Execution priority (lower runs first, default 100)
        min_app_version: Minimum ClinXML version required
        tags: Categorisation tags for filtering/grouping
    """
    id: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    priority: int = PluginPriority.DEFAULT
    min_app_version: str = "3.0.0"
    tags: List[str] = field(default_factory=list)


@dataclass
class PatternContext:
    element: ET.Element
    namespaces: Dict[str, str]
    path: Optional[str] = None
    container_info: Optional[Dict[str, Any]] = None


@dataclass
class PatternResult:
    id: str
    description: str
    flags: Dict[str, Any]
    confidence: str = "medium"
    notes: List[str] = field(default_factory=list)


PatternDetector = Callable[[PatternContext], Optional[PatternResult]]


def tag_local(elem: ET.Element) -> str:
    """Return the local name of an element, stripping any namespace."""
    return elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag


def find_first(elem: ET.Element, namespaces: Optional[Dict[str, str]], *queries: str) -> Optional[ET.Element]:
    """Return the first element found for the given query list without truthiness checks."""
    ns = namespaces or {}
    for query in queries:
        node = elem.find(query, ns)
        if node is not None:
            return node
    return None


def extract_range_value_flags(
    parent_elem: ET.Element,
    namespaces: Optional[Dict[str, str]]
) -> Optional[Dict[str, Any]]:
    """Extract temporal range flags from an element containing rangeValue.

    This is shared logic used by temporal and relationship plugins to avoid
    cross-plugin imports. Returns None if no rangeValue is found.

    Args:
        parent_elem: Element to search for rangeValue within
        namespaces: Namespace dict for XPath queries

    Returns:
        Dict of temporal flags if rangeValue found, None otherwise
    """
    ns = namespaces or {}
    range_value = find_first(parent_elem, ns, ".//rangeValue", ".//emis:rangeValue")
    if range_value is None:
        return None

    def _child_text(elem: Optional[ET.Element], tag: str) -> str:
        if elem is None:
            return ""
        node = find_first(elem, ns, tag, f"emis:{tag}")
        return node.text.strip() if node is not None and node.text else ""

    def _extract_boundary(node_name: str) -> Optional[Dict[str, str]]:
        node = find_first(range_value, ns, f".//{node_name}", f".//emis:{node_name}")
        if node is None:
            return None

        value_block = find_first(node, ns, "value", "emis:value")
        if value_block is None:
            value_block = find_first(node, ns, ".//value", ".//emis:value")

        value_text = _child_text(value_block, "value") or (
            (value_block.text or "").strip() if value_block is not None else ""
        )
        unit_text = _child_text(value_block, "unit") or _child_text(node, "unit")
        relation_text = _child_text(value_block, "relation") or _child_text(node, "relation")
        operator_text = _child_text(node, "operator")

        return {
            "value": value_text,
            "unit": unit_text,
            "relation": relation_text,
            "operator": operator_text,
        }

    range_from = _extract_boundary("rangeFrom")
    range_to = _extract_boundary("rangeTo")

    if not range_from and not range_to:
        return None

    flags: Dict[str, Any] = {"has_temporal_filter": True}

    relative_to = range_value.get("relativeTo") or range_value.get("relative_to")
    if relative_to:
        flags["relative_to"] = relative_to

    if range_from:
        flags.update({
            "range_from_value": range_from["value"],
            "range_from_unit": range_from["unit"],
            "range_from_relation": range_from["relation"] or "RELATIVE",
            "range_from_operator": range_from["operator"] or "GTEQ",
        })
    if range_to:
        flags.update({
            "range_to_value": range_to["value"],
            "range_to_unit": range_to["unit"],
            "range_to_relation": range_to["relation"] or "RELATIVE",
            "range_to_operator": range_to["operator"] or "LTEQ",
        })

    return flags
