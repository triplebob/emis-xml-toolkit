"""
Criterion parser for the pipeline.
Extracts table, filters, linked criteria presence, and value sets.
Supports early deduplication via CodeStore for performance optimisation.
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from .value_set_parser import parse_value_sets, parse_library_items
from ...pattern_plugins.registry import pattern_registry
from ...pattern_plugins.base import PatternContext
from ...metadata.flag_mapper import map_element_flags
from ..namespace_utils import findall_ns, find_ns, get_text_ns

if TYPE_CHECKING:
    from ...caching.code_store import CodeStore


def parse_criterion(
    criterion_elem: ET.Element,
    namespaces: Dict[str, str],
    code_store: "CodeStore",
    parent_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Parse a criterion into flags and value sets."""
    # Run patterns scoped to this criterion
    pattern_registry.load_all_modules("utils.pattern_plugins")
    pattern_results = pattern_registry.run_all(PatternContext(element=criterion_elem, namespaces=namespaces, path=criterion_elem.tag))

    flags = map_element_flags(criterion_elem, namespaces, pattern_results)
    parent_context = parent_context or {}

    # Table and display name
    table = get_text_ns(criterion_elem, "table", namespaces)
    display_name = get_text_ns(criterion_elem, "displayName", namespaces)
    description = get_text_ns(criterion_elem, "description", namespaces)
    exception_code = get_text_ns(criterion_elem, "exceptionCode", namespaces)
    if table:
        flags["logical_table_name"] = table
    if display_name:
        flags["display_name"] = display_name
    if description:
        flags["description"] = description
    if exception_code:
        flags["exception_code"] = exception_code
    if parent_context.get("container_type"):
        flags["container_type"] = parent_context["container_type"]
    if parent_context.get("source_name"):
        flags["source_name"] = parent_context["source_name"]
    if parent_context.get("source_guid"):
        flags["source_guid"] = parent_context["source_guid"]

    # Column filters (direct filterAttribute children only to avoid duplication)
    column_filters = []
    column_values = _collect_column_values(criterion_elem)

    for cv in column_values:
        cols = _get_text_list(cv, "column", namespaces)
        disp = get_text_ns(cv, "displayName", namespaces)
        in_not_in = get_text_ns(cv, "inNotIn", namespaces)

        # Extract range information if present
        range_value = find_ns(cv, "rangeValue", namespaces)
        range_info = {}
        if range_value is not None:
            range_from = _extract_range_boundary(range_value, "rangeFrom", namespaces)
            range_to = _extract_range_boundary(range_value, "rangeTo", namespaces)
            if range_from:
                range_info["from"] = range_from
            if range_to:
                range_info["to"] = range_to

        if cols:
            filter_entry = {
                "columns": cols,
                "column": cols[0],
                "display_name": disp,
                "in_not_in": in_not_in,
            }
            if range_info:
                filter_entry["range_info"] = range_info
            column_filters.append(filter_entry)
    # Prefer plugin-supplied column_filters if present
    plugin_filters = flags.pop("column_filters", None)
    active_filters = plugin_filters if plugin_filters is not None else column_filters
    if active_filters:
        all_cols: List[str] = []
        seen_cols: set[str] = set()
        for entry in active_filters:
            for col in entry.get("columns") or [entry.get("column")]:
                if col and col not in seen_cols:
                    seen_cols.add(col)
                    all_cols.append(col)
        flags["column_name"] = all_cols
        flags["column_display_name"] = (active_filters[0].get("display_name") or active_filters[0].get("column") or "")
        if active_filters[0].get("in_not_in"):
            flags["in_not_in"] = active_filters[0]["in_not_in"]

    # Value sets (only for the direct columnValues above, plus direct valueSet children when present)
    direct_vs = _collect_direct_value_sets(criterion_elem)

    # Build entity context for code store
    entity_context = None
    if code_store is not None:
        entity_context = {
            "entity_id": parent_context.get("source_guid", "") if parent_context else "",
            "entity_type": parent_context.get("source_type", "") if parent_context else "",
            "entity_name": parent_context.get("source_name", "") if parent_context else "",
            "criterion_context": {
                "table": flags.get("logical_table_name"),
                "column": flags.get("column_name"),
                "container": flags.get("container_type"),
            },
        }

    value_sets_result = parse_value_sets(
        column_values,
        namespaces,
        value_sets_direct=direct_vs,
        parent_flags=flags,
        code_store=code_store,
        entity_context=entity_context,
    )

    library_items_result = parse_library_items(
        criterion_elem,
        namespaces,
        code_store=code_store,
        entity_context=entity_context,
    )

    if not isinstance(value_sets_result, dict) or not value_sets_result.get("store_mode"):
        raise ValueError("Expected CodeStore value set keys.")
    if not isinstance(library_items_result, dict) or not library_items_result.get("store_mode"):
        raise ValueError("Expected CodeStore library item keys.")

    value_set_keys = value_sets_result.get("keys", [])
    library_item_keys = library_items_result.get("keys", [])
    value_sets: List[Dict[str, Any]] = []
    library_items: List[Dict[str, Any]] = []

    linked_criteria = _parse_linked_criteria(criterion_elem, namespaces, parent_context, code_store)
    if linked_criteria:
        flags["linked_criteria"] = [entry["relationship"] for entry in linked_criteria if entry.get("relationship")]

    result = {
        "flags": flags,
        "value_sets": value_sets + library_items,
        "column_filters": active_filters,
        "linked_criteria": linked_criteria,
    }

    # Include keys if using store mode
    result["value_set_keys"] = value_set_keys + library_item_keys

    return result


def _collect_column_values(criterion_elem: ET.Element) -> List[ET.Element]:
    """
    Collect columnValue nodes within this criterion but skip nested criterion subtrees
    to avoid double counting.
    """
    collected = []
    stack = list(criterion_elem)
    while stack:
        node = stack.pop()
        tag_local = _tag_local(node)
        if tag_local == "criterion" and node is not criterion_elem:
            # skip nested criteria
            continue
        if tag_local == "columnValue":
            collected.append(node)
            continue
        # traverse children
        stack.extend(list(node))
    return collected


def _collect_direct_value_sets(criterion_elem: ET.Element) -> List[ET.Element]:
    """Collect valueSet nodes directly under this criterion (non-nested criteria only)."""
    collected = []
    for child in criterion_elem:
        tag_local = _tag_local(child)
        if tag_local == "criterion":
            continue
        if tag_local == "valueSet":
            collected.append(child)
        # also check immediate children of filterAttribute
        if tag_local == "filterAttribute":
            for gchild in child:
                tag_child = _tag_local(gchild)
                if tag_child == "valueSet":
                    collected.append(gchild)
    return collected


def _parse_linked_criteria(
    criterion_elem: ET.Element,
    namespaces: Dict[str, str],
    parent_context: Dict[str, Any],
    code_store: Optional["CodeStore"] = None,
) -> List[Dict[str, Any]]:
    linked_items: List[Dict[str, Any]] = []
    for child in list(criterion_elem):
        if _tag_local(child) != "linkedCriterion":
            continue

        relationship_elem = find_ns(child, "relationship", namespaces)
        relationship_flags = _parse_relationship(relationship_elem, namespaces) if relationship_elem is not None else {}

        linked_criterion = find_ns(child, "criterion", namespaces)
        linked_data = None
        if linked_criterion is not None:
            linked_context = dict(parent_context or {})
            linked_context.setdefault("container_type", "Search Rule Linked Criteria")
            linked_data = parse_criterion(linked_criterion, namespaces, parent_context=linked_context, code_store=code_store)

        if relationship_flags or linked_data:
            linked_items.append({"relationship": relationship_flags, "criterion": linked_data})

    return linked_items


def _parse_relationship(relationship_elem: ET.Element, namespaces: Dict[str, str]) -> Dict[str, Any]:
    if relationship_elem is None:
        return {}

    def _child_text(elem: ET.Element, tag: str) -> str:
        node = find_ns(elem, tag, namespaces)
        return node.text.strip() if node is not None and node.text else ""

    parent_col = _child_text(relationship_elem, "parentColumn")
    child_col = _child_text(relationship_elem, "childColumn")
    parent_display = _child_text(relationship_elem, "parentColumnDisplayName")
    child_display = _child_text(relationship_elem, "childColumnDisplayName")

    range_value = find_ns(relationship_elem, "rangeValue", namespaces)
    relationship_type = _infer_relationship_type(parent_col, child_col, range_value is not None)

    flags: Dict[str, Any] = {
        "relationship_type": relationship_type,
        "parent_column": parent_col,
        "child_column": child_col,
    }
    if parent_display:
        flags["parent_column_display_name"] = parent_display
    if child_display:
        flags["child_column_display_name"] = child_display

    if range_value is not None:
        temporal_range: Dict[str, Any] = {}
        range_from = _extract_range_boundary(range_value, "rangeFrom", namespaces)
        range_to = _extract_range_boundary(range_value, "rangeTo", namespaces)
        if range_from:
            flags.update(
                {
                    "range_from_value": range_from.get("value", ""),
                    "range_from_unit": range_from.get("unit", ""),
                    "range_from_relation": range_from.get("relation", ""),
                    "range_from_operator": range_from.get("operator", ""),
                }
            )
            temporal_range["from"] = range_from
        if range_to:
            flags.update(
                {
                    "range_to_value": range_to.get("value", ""),
                    "range_to_unit": range_to.get("unit", ""),
                    "range_to_relation": range_to.get("relation", ""),
                    "range_to_operator": range_to.get("operator", ""),
                }
            )
            temporal_range["to"] = range_to
        if temporal_range:
            flags["temporal_range"] = temporal_range

    return flags


def _infer_relationship_type(parent_col: str, child_col: str, has_range: bool) -> str:
    """Best-effort relationship typing based on column hints."""
    combined = f"{parent_col or ''} {child_col or ''}".upper()
    date_terms = ["DATE", "DOB", "AGE", "AGE_AT_EVENT"]
    med_terms = ["DRUG", "MEDICATION", "ISSUE", "COURSE"]
    demo_terms = ["PATIENT", "SEX", "GENDER", "ETHNIC", "POSTCODE", "AREA", "WARD", "LSOA", "MSOA"]
    clinical_terms = ["READ", "SNOMED", "CODE", "CONCEPT", "EVENT", "DIAGNOS", "PROBLEM"]

    if has_range or any(term in combined for term in date_terms):
        return "date_based"
    if any(term in combined for term in med_terms):
        return "medication_based"
    if any(term in combined for term in demo_terms):
        return "demographic_based"
    if any(term in combined for term in clinical_terms):
        return "clinical_based"
    return "date_based"


def _extract_range_boundary(range_value: ET.Element, node_name: str, namespaces: Dict[str, str]) -> Dict[str, Any]:
    node = find_ns(range_value, node_name, namespaces)
    if node is None:
        return {}

    def _child_text(elem: ET.Element, tag: str) -> str:
        if elem is None:
            return ""
        inner_node = find_ns(elem, tag, namespaces)
        return inner_node.text.strip() if inner_node is not None and inner_node.text else ""

    value_block = find_ns(node, "value", namespaces)
    if value_block is None:
        value_block = find_ns(node, ".//value", namespaces)

    value_text = _child_text(value_block, "value") or ((value_block.text or "").strip() if value_block is not None else "")
    unit_text = _child_text(value_block, "unit") or _child_text(node, "unit")
    relation_text = _child_text(value_block, "relation") or _child_text(node, "relation")
    operator_text = _child_text(node, "operator")

    return {
        "value": value_text,
        "unit": unit_text,
        "relation": relation_text,
        "operator": operator_text,
    }


def _get_text_list(elem: ET.Element, tag: str, namespaces: Dict[str, str]) -> List[str]:
    if elem is None:
        return []
    return [n.text.strip() for n in findall_ns(elem, tag, namespaces) if n is not None and n.text]


def _tag_local(elem: ET.Element) -> str:
    return elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
