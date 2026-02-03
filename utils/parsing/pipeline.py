"""
Parsing pipeline entrypoints.
Produces canonical ParsedDocument and optional pattern results.
Uses CodeStore for early deduplication of clinical codes across entities.
"""

from typing import Optional, List, Dict, Any
import xml.etree.ElementTree as ET
from .document_loader import load_document
from .element_classifier import ElementClassifier
from ..metadata.models import ParsedDocument
from ..pattern_plugins.registry import pattern_registry
from ..pattern_plugins.base import PatternContext, PatternResult
from .node_parsers.search_parser import parse_search
from .node_parsers.report_parser import parse_report
from ..caching.code_store import CodeStore


class ParsingPipelineError(Exception):
    pass


def parse_xml(xml_content: str, source_name: Optional[str] = None, run_patterns: bool = False) -> Dict[str, Any]:
    """
    Parse XML into canonical buckets and optionally run pattern detectors.

    Returns a dict with:
    - parsed_document: ParsedDocument
    - entities: list of parsed entities (searches, reports)
    - code_store: CodeStore instance with deduplicated codes
    - pattern_results: list[PatternResult] (optional)
    """
    root, namespaces, metadata = load_document(xml_content, source_name=source_name)
    classifier = ElementClassifier(namespaces)
    buckets = classifier.classify(root)
    parsed = ParsedDocument(metadata=metadata, buckets=buckets, namespaces=namespaces)

    results: List[PatternResult] = []
    parsed_entities: List[Dict[str, Any]] = []

    # Create code store for early deduplication (if enabled)
    code_store = CodeStore()

    # Ensure all pattern modules are loaded
    pattern_registry.load_all_modules("utils.pattern_plugins")

    # Parse searches with code store
    for search_elem in buckets.searches:
        parsed_entities.append(parse_search(search_elem, namespaces, code_store=code_store))

    # Parse reports with code store
    for report_elem in buckets.list_reports:
        parsed_entities.append(parse_report(report_elem, namespaces, "list_report", code_store=code_store))
    for report_elem in buckets.audit_reports:
        parsed_entities.append(parse_report(report_elem, namespaces, "audit_report", code_store=code_store))
    for report_elem in buckets.aggregate_reports:
        parsed_entities.append(parse_report(report_elem, namespaces, "aggregate_report", code_store=code_store))

    if run_patterns:
        targets: List[ET.Element] = (
            buckets.searches
            + buckets.list_reports
            + buckets.audit_reports
            + buckets.aggregate_reports
        )
        for element in targets:
            ctx = PatternContext(element=element, namespaces=namespaces, path=element.tag)
            results.extend(pattern_registry.run_all(ctx))

    output: Dict[str, Any] = {"parsed_document": parsed, "entities": parsed_entities}

    # Include code store in output (already populated during parsing)
    output["code_store"] = code_store

    if run_patterns:
        output["pattern_results"] = results
    return output
