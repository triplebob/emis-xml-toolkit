"""
Temporal pattern detectors based on documented EMIS XML patterns.
"""

from .registry import register_pattern
from .base import PatternContext, PatternResult, find_first, tag_local


@register_pattern("temporal_single_value")
def detect_temporal_single_value(ctx: PatternContext):
    """
    Detects named temporal variables and numeric offsets in singleValue constructs.
    Patterns: <singleValue><variable><value>Last|This|Next|N</value><unit>...<relation>RELATIVE|ABSOLUTE</relation></variable></singleValue>
    """
    if tag_local(ctx.element) != "criterion":
        return None
    ns = ctx.namespaces
    single_value = find_first(ctx.element, ns, ".//singleValue", ".//emis:singleValue")
    if single_value is None:
        return None

    variable = find_first(single_value, ns, ".//variable", ".//emis:variable")
    if variable is None:
        return None

    val_elem = find_first(variable, ns, ".//value", ".//emis:value")
    unit_elem = find_first(variable, ns, ".//unit", ".//emis:unit")
    relation_elem = find_first(variable, ns, ".//relation", ".//emis:relation")

    if val_elem is None or unit_elem is None:
        return None

    value_text = (val_elem.text or "").strip()
    unit_text = (unit_elem.text or "").strip()
    relation_text = (relation_elem.text or "").strip() if relation_elem is not None else "RELATIVE"

    if not value_text or not unit_text:
        return None

    return PatternResult(
        id="temporal_single_value",
        description="Temporal singleValue with variable/offset",
        flags={
            "has_temporal_filter": True,
            "temporal_variable_value": value_text,
            "temporal_unit": unit_text,
            "temporal_relation": relation_text,
        },
        confidence="high",
    )


@register_pattern("temporal_range")
def detect_temporal_range(ctx: PatternContext):
    """
    Detects rangeValue temporal filters with rangeFrom/rangeTo, including variable-based values.
    """
    if tag_local(ctx.element) != "criterion":
        return None
    ns = ctx.namespaces
    range_value = find_first(ctx.element, ns, ".//rangeValue", ".//emis:rangeValue")
    if range_value is None:
        return None

    def _child_text(elem, tag):
        if elem is None:
            return ""
        node = find_first(elem, ns, tag, f"emis:{tag}")
        return node.text.strip() if node is not None and node.text else ""

    def _extract_boundary(node_name: str):
        node = find_first(range_value, ns, f".//{node_name}", f".//emis:{node_name}")
        if node is None:
            return None

        value_block = find_first(node, ns, "value", "emis:value")
        if value_block is None:
            value_block = find_first(node, ns, ".//value", ".//emis:value")

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

    range_from = _extract_boundary("rangeFrom")
    range_to = _extract_boundary("rangeTo")

    if not range_from and not range_to:
        return None

    flags = {
        "has_temporal_filter": True,
    }
    relative_to = range_value.get("relativeTo") or range_value.get("relative_to")
    if relative_to:
        flags["relative_to"] = relative_to
    if range_from:
        flags.update(
            {
                "range_from_value": range_from["value"],
                "range_from_unit": range_from["unit"],
                "range_from_relation": range_from["relation"] or "RELATIVE",
                "range_from_operator": range_from["operator"] or "GTEQ",
            }
        )
    if range_to:
        flags.update(
            {
                "range_to_value": range_to["value"],
                "range_to_unit": range_to["unit"],
                "range_to_relation": range_to["relation"] or "RELATIVE",
                "range_to_operator": range_to["operator"] or "LTEQ",
            }
        )

    return PatternResult(
        id="temporal_range",
        description="Temporal range filter with rangeFrom/rangeTo",
        flags=flags,
        confidence="high",
    )
