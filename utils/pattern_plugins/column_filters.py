"""
Column filter pattern detector to extract filter metadata (plugin-driven).
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, List

from .registry import register_pattern
from .base import (
    PatternContext,
    PatternResult,
    PluginMetadata,
    PluginPriority,
    find_first,
)


def _text(node: ET.Element, tag: str, namespaces: Dict[str, str]) -> str:
    found = find_first(node, namespaces, tag, f"emis:{tag}")
    return found.text.strip() if found is not None and found.text else ""


def _collect_columns(cv: ET.Element, namespaces: Dict[str, str]) -> List[str]:
    cols: List[str] = []
    for col in cv.findall(".//column", namespaces) + cv.findall(".//emis:column", namespaces):
        if col.text:
            cols.append(col.text.strip())
    return cols


def _infer_filter_type(column: str) -> str:
    text = (column or "").upper()
    if "AGE" in text:
        return "age"
    if "DATE" in text or "DOB" in text:
        return "date"
    if "NUMERIC" in text or "VALUE" in text:
        return "numeric"
    if "READCODE" in text or "SNOMED" in text:
        return "readcode"
    if "DRUGCODE" in text:
        return "drugcode"
    if "EMISINTERNAL" in text:
        return "emisinternal"
    return ""


def _parse_single_value(cv: ET.Element, namespaces: Dict[str, str]) -> Dict[str, Any]:
    """Parse singleValue with variable into range_info format."""
    single_node = find_first(cv, namespaces, ".//singleValue", ".//emis:singleValue")
    if single_node is None:
        return {}

    variable_node = find_first(single_node, namespaces, ".//variable", ".//emis:variable")
    if variable_node is None:
        return {}

    value_text = _text(variable_node, "value", namespaces)
    unit_text = _text(variable_node, "unit", namespaces)
    relation_text = _text(variable_node, "relation", namespaces) or "RELATIVE"

    if not value_text:
        return {}

    # Convert single value to range_info format (treat as "from" boundary)
    from_dict = {"value": value_text}
    if unit_text:
        from_dict["unit"] = unit_text
    if relation_text:
        from_dict["relation"] = relation_text

    return {"from": from_dict}


def _parse_range(cv: ET.Element, namespaces: Dict[str, str]) -> Dict[str, Any]:
    range_info: Dict[str, Any] = {}
    range_node = find_first(cv, namespaces, ".//rangeValue", ".//emis:rangeValue")
    if range_node is None:
        range_node = find_first(cv, namespaces, ".//range", ".//emis:range")
    if range_node is None:
        # Check for singleValue as fallback
        return _parse_single_value(cv, namespaces)

    def _boundary(name: str) -> Dict[str, Any]:
        bound: Dict[str, Any] = {}
        node = find_first(range_node, namespaces, f".//{name}", f".//emis:{name}")
        if node is None:
            return bound
        bound["operator"] = _text(node, "operator", namespaces)
        value_node = find_first(node, namespaces, ".//value", ".//emis:value")
        if value_node is not None:
            # Check for nested value/unit/relation structure
            nested_value = _text(value_node, "value", namespaces)
            if nested_value:
                bound["value"] = nested_value
            nested_unit = _text(value_node, "unit", namespaces)
            if nested_unit:
                bound["unit"] = nested_unit
            nested_relation = _text(value_node, "relation", namespaces)
            if nested_relation:
                bound["relation"] = nested_relation

            # Fallback: check if value_node itself has text (flat structure)
            if not nested_value and value_node.text:
                bound["value"] = value_node.text.strip()
            if not nested_unit and value_node.get("unit"):
                bound["unit"] = value_node.get("unit")
            if not nested_relation and value_node.get("relation"):
                bound["relation"] = value_node.get("relation")

        # Fallback: check for unit/relation as direct children of node
        if "unit" not in bound:
            unit_child = _text(node, "unit", namespaces)
            if unit_child:
                bound["unit"] = unit_child
        if "relation" not in bound:
            relation_child = _text(node, "relation", namespaces)
            if relation_child:
                bound["relation"] = relation_child
        return bound

    range_from = _boundary("rangeFrom")
    range_to = _boundary("rangeTo")
    if range_from:
        range_info["from"] = range_from
    if range_to:
        range_info["to"] = range_to
    return range_info


def _parse_value_sets(cv: ET.Element, namespaces: Dict[str, str]) -> List[Dict[str, Any]]:
    """Parse inline value sets for EMISINTERNAL filters."""
    value_sets: List[Dict[str, Any]] = []
    for vs in cv.findall(".//valueSet", namespaces) + cv.findall(".//emis:valueSet", namespaces):
        code_system_node = find_first(vs, namespaces, ".//codeSystem", ".//emis:codeSystem")
        code_system = code_system_node.text.strip() if code_system_node is not None and code_system_node.text else ""
        values: List[Dict[str, Any]] = []
        for values_container in vs.findall(".//values", namespaces) + vs.findall(".//emis:values", namespaces):
            # Extract value, displayName, and includeChildren as siblings under <values>
            entry: Dict[str, Any] = {}
            # Don't use namespaces for direct child lookups
            val_node = find_first(values_container, namespaces, "value", "emis:value")
            if val_node is not None and val_node.text:
                entry["value"] = val_node.text.strip()

            disp_node = find_first(values_container, namespaces, "displayName", "emis:displayName")
            if disp_node is not None and disp_node.text:
                entry["displayName"] = disp_node.text.strip()

            if entry:
                values.append(entry)

        value_sets.append(
            {
                "code_system": code_system,
                "values": values,
            }
        )
    return value_sets


@register_pattern(
    PluginMetadata(
        id="column_filters",
        version="1.0.0",
        description="Extracts column filters with range/value set metadata",
        priority=PluginPriority.LOW,
        tags=["column", "filter", "range"],
    )
)
def detect_column_filters(ctx: PatternContext):
    """
    Extract column filters from columnValue/filterAttribute blocks.
    """
    ns = ctx.namespaces
    column_filters: List[Dict[str, Any]] = []

    column_value_nodes = ctx.element.findall(".//columnValue", ns) + ctx.element.findall(".//emis:columnValue", ns)
    if not column_value_nodes:
        return None

    for cv in column_value_nodes:
        cols = _collect_columns(cv, ns)
        if not cols:
            continue
        disp = _text(cv, "displayName", ns)
        in_not_in = _text(cv, "inNotIn", ns)
        range_info = _parse_range(cv, ns)
        value_sets = _parse_value_sets(cv, ns)

        for col in cols:
            filter_type = _infer_filter_type(col)
            column_filters.append(
                {
                    "columns": cols,
                    "column": col,
                    "column_name": col,
                    "column_display": disp or col,
                    "display_name": disp,
                    "in_not_in": in_not_in,
                    "range_info": range_info,
                    "filter_type": filter_type,
                    "value_sets": value_sets,
                }
            )

    if not column_filters:
        return None

    return PatternResult(
        id="column_filters",
        description="Column filters detected",
        flags={"column_filters": column_filters},
        confidence="medium",
    )
