"""
Pattern plugin definitions for the parsing pipeline.
Patterns are callable detectors that return structured results.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, Any, Optional, List
import xml.etree.ElementTree as ET


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
