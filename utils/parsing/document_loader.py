"""
Document loader for the parsing pipeline.
Handles XML parsing and namespace capture with defensive error handling.
"""

import xml.etree.ElementTree as ET
from typing import Dict, Tuple, Optional
import io
from ..metadata.models import DocumentMetadata


class DocumentLoadError(Exception):
    pass


def load_document(xml_content: str, source_name: Optional[str] = None) -> Tuple[ET.Element, Dict[str, str], DocumentMetadata]:
    if not xml_content or not xml_content.strip():
        raise DocumentLoadError("Empty XML content provided")

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        raise DocumentLoadError(f"XML parse failed: {exc}") from exc

    namespaces = _extract_namespaces(xml_content)
    metadata = DocumentMetadata.from_root(root, xml_content, source_name=source_name)
    return root, namespaces, metadata


def _extract_namespaces(xml_content: str) -> Dict[str, str]:
    namespaces: Dict[str, str] = {}
    try:
        for event, elem in ET.iterparse(
            io.StringIO(xml_content), events=("start-ns",)  # type: ignore[name-defined]
        ):
            prefix, uri = elem
            namespaces[prefix if prefix is not None else ""] = uri
    except Exception:
        # Fallback to default EMIS namespace if parsing of namespaces fails
        namespaces = {"emis": "http://www.e-mis.com/emisopen"}
    if "emis" not in namespaces:
        namespaces["emis"] = "http://www.e-mis.com/emisopen"
    return namespaces
