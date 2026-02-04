"""
Detect EMISINTERNAL classifications and emit friendly flags.
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
    tag_local,
)


def _iter_value_sets_with_context(elem: ET.Element, namespaces: Dict[str, str]) -> List[Dict[str, Any]]:
    """Collect EMISINTERNAL value sets with column/inNotIn context."""
    collected: List[Dict[str, Any]] = []
    for column_value in elem.findall(".//columnValue", namespaces) + elem.findall(".//emis:columnValue", namespaces):
        columns = _multi_column_context(column_value, namespaces)
        column = columns[0] if columns else ""
        in_not_in_node = find_first(column_value, namespaces, ".//inNotIn", ".//emis:inNotIn")
        in_not_in = in_not_in_node.text.strip() if in_not_in_node is not None and in_not_in_node.text else ""

        for vs in column_value.findall(".//valueSet", namespaces) + column_value.findall(".//emis:valueSet", namespaces):
            collected.append(
                {
                    "column": column,
                    "in_not_in": in_not_in,
                    "value_set": vs,
                    "parent_column_value": column_value,
                }
            )
    # Capture valueSets that sit directly under filterAttribute (no columnValue wrapper).
    for filter_attr in elem.findall(".//filterAttribute", namespaces) + elem.findall(".//emis:filterAttribute", namespaces):
        for child in list(filter_attr):
            if tag_local(child) != "valueSet":
                continue
            collected.append(
                {
                    "column": "",
                    "in_not_in": "",
                    "value_set": child,
                    "parent_column_value": None,
                }
            )
    return collected


def _extract_values(vs_elem: ET.Element, namespaces: Dict[str, str]) -> List[Dict[str, str]]:
    """Extract value and displayName from EMISINTERNAL value sets."""
    values: List[Dict[str, str]] = []
    for values_container in vs_elem.findall(".//values", namespaces) or vs_elem.findall(".//emis:values", namespaces) or []:
        # Extract value and displayName as siblings under <values>
        val_node = find_first(values_container, namespaces, "value", "emis:value")
        disp_node = find_first(values_container, namespaces, "displayName", "emis:displayName")

        if val_node is not None and val_node.text:
            entry = {"value": val_node.text.strip()}
            if disp_node is not None and disp_node.text:
                entry["displayName"] = disp_node.text.strip()
            values.append(entry)
    return values


def _multi_column_context(parent_cv: ET.Element, namespaces: Dict[str, str]) -> List[str]:
    """Capture sibling columns for multi-column EMISINTERNAL patterns."""
    extras: List[str] = []
    if parent_cv is None:
        return extras
    for col in parent_cv.findall(".//column", namespaces) + parent_cv.findall(".//emis:column", namespaces):
        if col.text:
            extras.append(col.text.strip())
    return extras


@register_pattern(
    PluginMetadata(
        id="emisinternal_classification",
        version="1.0.0",
        description="Detects EMISINTERNAL code system filters and classifications",
        priority=PluginPriority.HIGH,
        tags=["emisinternal", "classification", "filtering"],
    )
)
def detect_emisinternal(ctx: PatternContext):
    if tag_local(ctx.element) != "criterion":
        return None
    ns = ctx.namespaces
    value_sets_ctx = _iter_value_sets_with_context(ctx.element, ns)
    emisinternal_values: List[str] = []
    entries: List[Dict[str, Any]] = []

    for item in value_sets_ctx:
        vs = item["value_set"]
        code_system_node = find_first(vs, ns, ".//codeSystem", ".//emis:codeSystem")
        code_system_text = code_system_node.text.strip() if code_system_node is not None and code_system_node.text else ""
        if code_system_text.upper() == "EMISINTERNAL":
            vals = _extract_values(vs, ns)  # Now returns List[Dict[str, str]] with value and displayName
            # For the flat list, extract just the values
            emisinternal_values.extend([v["value"] for v in vals])
            entries.append(
                {
                    "column": item["column"],
                    "values": vals,  # Store the full dict structure with displayName
                    "in_not_in": item.get("in_not_in"),
                    "has_all_values": find_first(vs, ns, ".//allValues", ".//emis:allValues") is not None,
                    "multi_columns": _multi_column_context(item.get("parent_column_value"), ns),
                }
            )

    if not emisinternal_values and not entries:
        return None

    return PatternResult(
        id="emisinternal_classification",
        description="EMISINTERNAL classification detected",
        flags={
            "has_emisinternal_filters": True,
            "emisinternal_values": emisinternal_values,
            "emisinternal_entries": entries,
            "emisinternal_all_values": any(e.get("has_all_values") for e in entries),
        },
        confidence="high",
    )
