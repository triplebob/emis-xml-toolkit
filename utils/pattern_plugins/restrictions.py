"""
Restriction pattern detectors for latest/earliest/test-attribute patterns.
"""

from .registry import register_pattern
from .base import (
    PatternContext,
    PatternResult,
    PluginMetadata,
    PluginPriority,
    find_first,
    tag_local,
)


@register_pattern(
    PluginMetadata(
        id="restriction_latest_earliest",
        version="1.0.0",
        description="Detects latest/earliest record restrictions with ordering",
        priority=PluginPriority.NORMAL,
        tags=["restriction", "ordering"],
    )
)
def detect_latest_earliest(ctx: PatternContext):
    if tag_local(ctx.element) != "criterion":
        return None
    ns = ctx.namespaces
    restriction = find_first(ctx.element, ns, ".//restriction", ".//emis:restriction")
    if restriction is None:
        return None

    column_order = find_first(restriction, ns, ".//columnOrder", ".//emis:columnOrder")
    if column_order is None:
        return None

    record_count = find_first(column_order, ns, ".//recordCount", ".//emis:recordCount")
    direction = find_first(column_order, ns, ".//direction", ".//emis:direction")
    column = find_first(column_order, ns, ".//column", ".//emis:column")

    flags = {
        "has_restriction": True,
        "restriction_type": "latest_records",
        "record_count": int(record_count.text) if record_count is not None and record_count.text and record_count.text.isdigit() else None,
        "ordering_direction": (direction.text or "DESC").strip() if direction is not None else "DESC",
        "ordering_column": (column.text or "").strip() if column is not None else "",
    }

    if flags["record_count"] and flags["ordering_direction"] == "ASC":
        flags["restriction_type"] = "earliest_records"

    return PatternResult(
        id="restriction_latest_earliest",
        description="Latest/Earliest record restriction",
        flags=flags,
        confidence="medium",
    )


@register_pattern(
    PluginMetadata(
        id="restriction_test_attribute",
        version="1.0.0",
        description="Detects test attribute restrictions with column conditions",
        priority=PluginPriority.NORMAL,
        tags=["restriction", "test-attribute"],
    )
)
def detect_test_attribute(ctx: PatternContext):
    if tag_local(ctx.element) != "criterion":
        return None
    ns = ctx.namespaces
    restriction = find_first(ctx.element, ns, ".//restriction", ".//emis:restriction")
    if restriction is None:
        return None

    test_attr = find_first(restriction, ns, ".//testAttribute", ".//emis:testAttribute")
    if test_attr is None:
        return None

    column_value = find_first(test_attr, ns, ".//columnValue", ".//emis:columnValue")
    if column_value is None:
        return None

    column = find_first(column_value, ns, ".//column", ".//emis:column")
    in_not_in = find_first(column_value, ns, ".//inNotIn", ".//emis:inNotIn")
    operator = find_first(column_value, ns, ".//operator", ".//emis:operator")

    flags = {
        "has_restriction": True,
        "has_test_conditions": True,
        "test_condition_column": (column.text or "").strip() if column is not None else "",
        "test_condition_operator": (operator.text or "").strip() if operator is not None else (in_not_in.text.strip() if in_not_in is not None else ""),
    }

    return PatternResult(
        id="restriction_test_attribute",
        description="Restriction with testAttribute",
        flags=flags,
        confidence="medium",
    )
