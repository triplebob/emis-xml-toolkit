"""
Structure-only parser: extracts folders, searches, reports, and dependency links.
No clinical content; intended for UI structure browsing.

Note: This parser returns metadata-only entities. Criteria details (criteria_groups,
value_sets) are merged from pipeline entities in xml_cache.py to avoid duplicate parsing.
"""

from typing import Dict, Any, List, Set
import xml.etree.ElementTree as ET
from ..document_loader import load_document
from ..element_classifier import ElementClassifier
from ..namespace_utils import get_child_text_any, find_child_any, findall_ns, find_ns
from ...metadata.flag_mapper import validate_flags


def parse_structure(xml_content: str, source_name: str | None = None) -> Dict[str, Any]:
    root, namespaces, _ = load_document(xml_content, source_name=source_name)
    classifier = ElementClassifier(namespaces)
    buckets = classifier.classify(root)

    folders = _parse_folders(buckets.folders, namespaces)
    entities: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    def _add(entity: Dict[str, Any]):
        eid = entity.get("id")
        if eid and eid in seen:
            return
        if eid:
            seen.add(eid)
        entities.append(entity)

    for elem in buckets.searches:
        entity = _base_entity(elem, namespaces, "search")
        deps = _population_dependencies(elem, namespaces)
        if deps:
            entity["dependencies"] = deps
        # Note: criteria_groups merged from pipeline entities in xml_cache.py
        _add(entity)

    for elem in buckets.list_reports:
        entity = _base_entity(elem, namespaces, "list_report")
        deps = _report_dependencies(elem, namespaces)
        if deps:
            entity["dependencies"] = deps
        _add(entity)
    for elem in buckets.audit_reports:
        entity = _base_entity(elem, namespaces, "audit_report")
        pop_guid = _find_population_guid(elem, namespaces)
        if pop_guid:
            entity["dependencies"] = [pop_guid]
        deps = _report_dependencies(elem, namespaces)
        if deps:
            entity.setdefault("dependencies", [])
            for d in deps:
                if d not in entity["dependencies"]:
                    entity["dependencies"].append(d)
        _add(entity)
    for elem in buckets.aggregate_reports:
        entity = _base_entity(elem, namespaces, "aggregate_report")
        pop_guid = _find_population_guid(elem, namespaces)
        if pop_guid:
            entity["dependencies"] = [pop_guid]
        deps = _report_dependencies(elem, namespaces)
        if deps:
            entity.setdefault("dependencies", [])
            for d in deps:
                if d not in entity["dependencies"]:
                    entity["dependencies"].append(d)
        _add(entity)

    return {"folders": folders, "entities": entities}


def _parse_folders(folder_elems: List[ET.Element], namespaces: Dict[str, str]) -> List[Dict[str, Any]]:
    folders: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for f in folder_elems:
        fid = get_child_text_any(f, ["id"], namespaces)
        if fid in seen:
            continue
        seen.add(fid)
        author_elem = find_child_any(f, ["author"], namespaces)
        author_name = get_child_text_any(author_elem, ["authorName"], namespaces) if author_elem is not None else ""
        folders.append(
            {
                "id": fid or "",
                "name": get_child_text_any(f, ["name"], namespaces) or "",
                "parent_id": get_child_text_any(f, ["parentFolder", "parentFolderId", "parentId"], namespaces) or "",
                "author_name": author_name or "",
            }
        )
    return folders


def _base_entity(elem: ET.Element, namespaces: Dict[str, str], etype: str) -> Dict[str, Any]:
    flags: Dict[str, Any] = {}
    eid = get_child_text_any(elem, ["id"], namespaces) or (elem.get("id") or "")
    name = get_child_text_any(elem, ["name"], namespaces)
    folder_id = get_child_text_any(elem, ["folder"], namespaces)
    parent_guid = ""
    parent_elem = find_ns(elem, "parent", namespaces)
    if parent_elem is not None:
        search_identifier = find_ns(parent_elem, "SearchIdentifier", namespaces)
        if search_identifier is not None:
            parent_guid = search_identifier.get("reportGuid") or search_identifier.get("searchGuid") or ""

    flags["element_id"] = eid
    flags["display_name"] = name
    flags["folder_id"] = folder_id
    flags["parent_search_guid"] = parent_guid
    flags["element_type"] = etype

    return {
        "id": eid,
        "name": name or "",
        "folder_id": folder_id or "",
        "parent_guid": parent_guid or "",
        "source_type": etype,
        "dependencies": [],
        "flags": validate_flags(flags),
    }


def _population_dependencies(elem: ET.Element, namespaces: Dict[str, str]) -> List[str]:
    deps: List[str] = []
    for node in findall_ns(elem, ".//populationCriterion", namespaces):
        guid = node.get("reportGuid")
        if guid:
            deps.append(guid)
    return deps


def _report_dependencies(elem: ET.Element, namespaces: Dict[str, str]) -> List[str]:
    """Capture dependencies inside report criteria via populationCriterion references."""
    deps: List[str] = []
    for node in findall_ns(elem, ".//populationCriterion", namespaces):
        guid = node.get("reportGuid")
        if guid:
            deps.append(guid)
    return deps


def _find_population_guid(elem: ET.Element, namespaces: Dict[str, str]) -> str:
    """Find population GUID used by audit/aggregate reports."""
    direct = get_child_text_any(elem, ["population"], namespaces)
    if direct:
        return direct
    for node in findall_ns(elem, ".//population", namespaces):
        if node.text and node.text.strip():
            return node.text.strip()
    return ""
