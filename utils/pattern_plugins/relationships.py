"""
Linked criteria / relationship pattern detectors.
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
        id="linked_relationship",
        version="1.0.0",
        description="Detects linked criteria relationships between columns",
        priority=PluginPriority.NORMAL,
        tags=["relationship", "linked-criteria"],
    )
)
def detect_linked_relationship(ctx: PatternContext):
    if tag_local(ctx.element) != "criterion":
        return None
    ns = ctx.namespaces
    relationship = find_first(ctx.element, ns, ".//relationship", ".//emis:relationship")
    if relationship is None:
        return None

    parent_col = find_first(relationship, ns, ".//parentColumn", ".//emis:parentColumn")
    child_col = find_first(relationship, ns, ".//childColumn", ".//emis:childColumn")
    parent_display = find_first(
        relationship, ns, ".//parentColumnDisplayName", ".//emis:parentColumnDisplayName"
    )
    child_display = find_first(
        relationship, ns, ".//childColumnDisplayName", ".//emis:childColumnDisplayName"
    )
    range_value = find_first(relationship, ns, ".//rangeValue", ".//emis:rangeValue")

    parent_text = (parent_col.text or "").strip() if parent_col is not None else ""
    child_text = (child_col.text or "").strip() if child_col is not None else ""
    relationship_type = _infer_relationship_type(parent_text, child_text, range_value is not None)

    flags = {
        "relationship_type": relationship_type,
        "parent_column": parent_text,
        "child_column": child_text,
    }
    if parent_display is not None and parent_display.text:
        flags["parent_column_display_name"] = parent_display.text.strip()
    if child_display is not None and child_display.text:
        flags["child_column_display_name"] = child_display.text.strip()

    if range_value is not None:
        # Use shared helper to extract temporal range data
        range_flags = extract_range_value_flags(relationship, ns)
        if range_flags:
            flags.update(range_flags)

    return PatternResult(
        id="linked_relationship",
        description="Linked criteria relationship detected",
        flags=flags,
        confidence="medium",
    )


def _infer_relationship_type(parent_col: str, child_col: str, has_range: bool) -> str:
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
