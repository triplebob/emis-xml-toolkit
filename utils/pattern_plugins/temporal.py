"""
Temporal pattern detectors based on documented EMIS XML patterns.
"""

from .registry import register_pattern
from .base import (
    PatternContext,
    PatternResult,
    PluginMetadata,
    PluginPriority,
    find_first,
    tag_local,
    extract_range_value_flags,
)


@register_pattern(
    PluginMetadata(
        id="temporal_single_value",
        version="1.0.0",
        description="Detects single-value temporal filters (Last/This/Next periods)",
        priority=PluginPriority.NORMAL,
        tags=["temporal", "date-filter"],
    )
)
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


@register_pattern(
    PluginMetadata(
        id="temporal_range",
        version="1.0.0",
        description="Detects range-based temporal filters (rangeFrom/rangeTo)",
        priority=PluginPriority.NORMAL,
        tags=["temporal", "date-filter", "range"],
    )
)
def detect_temporal_range(ctx: PatternContext):
    """
    Detects rangeValue temporal filters with rangeFrom/rangeTo, including variable-based values.
    """
    if tag_local(ctx.element) != "criterion":
        return None

    flags = extract_range_value_flags(ctx.element, ctx.namespaces)
    if flags is None:
        return None

    return PatternResult(
        id="temporal_range",
        description="Temporal range filter with rangeFrom/rangeTo",
        flags=flags,
        confidence="high",
    )
