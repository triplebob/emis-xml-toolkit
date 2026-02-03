"""
Describe restriction blocks in friendly text.
"""

from typing import Any, Dict, List


def _format_column_order(restriction: Dict[str, Any]) -> str:
    column_order = restriction.get("columnOrder") or restriction.get("column_order") or {}
    record_count = column_order.get("recordCount")

    # Direction can be in columns sub-object or directly in columnOrder
    columns = column_order.get("columns") or {}
    direction = columns.get("direction") if isinstance(columns, dict) else None
    if not direction:
        direction = column_order.get("direction")

    if record_count:
        # Determine qualifier based on direction
        if direction:
            dir_upper = direction.upper()
            if dir_upper == "DESC":
                qualifier = "Latest"
            elif dir_upper == "ASC":
                qualifier = "Earliest"
            else:
                qualifier = "First"
        else:
            # No direction specified = First
            qualifier = "First"
        return f"{qualifier} {record_count}"
    return ""


def _format_test_attribute(restriction: Dict[str, Any]) -> str:
    test_attr = restriction.get("testAttribute") or restriction.get("test_attribute") or {}
    column_value = test_attr.get("columnValue") or test_attr.get("column_value") or {}
    column = column_value.get("column")
    display = column_value.get("displayName")
    in_not_in = column_value.get("inNotIn")
    value_sets = column_value.get("valueSet") or column_value.get("value_sets") or []
    values = []
    for vs in value_sets:
        for val in vs.get("values") or vs.get("allValues") or []:
            if isinstance(val, dict):
                values.append(val.get("displayName") or val.get("value"))
            else:
                values.append(val)
    value_text = ", ".join([v for v in values if v]) if values else ""
    if column or display or value_text:
        col_label = display or column or "value"
        if value_text:
            if in_not_in and in_not_in.upper() == "NOTIN":
                return f"Exclude {col_label}: {value_text}"
            return f"Include {col_label}: {value_text}"
        return f"Filter on {col_label}"
    return ""


def describe_restrictions(restrictions: List[Any]) -> List[str]:
    """
    Convert restriction objects to readable bullet points.
    """
    friendly: List[str] = []
    for restr in restrictions or []:
        if isinstance(restr, dict):
            parts = []
            column_order_desc = _format_column_order(restr)
            if column_order_desc:
                parts.append(column_order_desc)
            test_attr_desc = _format_test_attribute(restr)
            if test_attr_desc:
                parts.append(test_attr_desc)
            if not parts and (restr.get("isCurrent") or restr.get("is_current")):
                parts.append("Current records only")
            if not parts and restr.get("limit"):
                parts.append(f"Limit {restr.get('limit')} records")
            if parts:
                friendly.append("; ".join(parts))
            else:
                friendly.append(str(restr))
        else:
            friendly.append(str(restr))
    return friendly
