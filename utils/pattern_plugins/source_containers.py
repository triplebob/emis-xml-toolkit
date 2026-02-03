"""
Container pattern heuristics for assigning detailed source containers.

These mirror `_determine_proper_container_type` behaviour so
container rules can be extended modularly.
"""

import xml.etree.ElementTree as ET
from .registry import register_pattern
from .base import PatternResult, PatternContext, find_first


def _has_child(elem: ET.Element, names: list[str], namespaces: dict[str, str]) -> bool:
    for name in names:
        if elem.find(name, namespaces) is not None or elem.find(f"emis:{name}", namespaces) is not None:
            return True
    return False


def _tag_lower(elem: ET.Element) -> str:
    """Return the local name of an element in lowercase."""
    return elem.tag.split("}")[-1].lower()


@register_pattern("container_heuristics")
def container_heuristics(ctx: PatternContext):
    """
    Assign container_type flag based on criterion/report patterns.
    """
    elem = ctx.element
    elem_tag = _tag_lower(elem)
    namespaces = ctx.namespaces

    # Report-level hints (apply on report nodes)
    if elem_tag in {"listreport", "auditreport", "aggregatereport"}:
        return PatternResult(
            id="container_heuristics",
            description="Report-level container hint",
            flags={"container_type": "Report Main Criteria"},
            confidence="low",
        )

    if elem_tag != "criterion":
        return None

    container_type = None

    # Restriction / date / latest records
    if _has_child(elem, ["restriction", "dateRestriction", "latestRecords"], namespaces):
        container_type = "Search Rule Restriction"
    # Linked criteria patterns
    elif _has_child(elem, ["linkedCriteria", "linkedCriterion"], namespaces):
        container_type = "Search Rule Linked Criteria"
    # Population references
    elif _has_child(elem, ["population", "populationCriterion"], namespaces):
        container_type = "Search Rule Population Reference"
    # Test attribute patterns
    elif _has_child(elem, ["testAttribute", "testAttributes"], namespaces):
        container_type = "Search Rule Test Attribute"
    # Table-based hints
    else:
        table_elem = find_first(elem, namespaces, "table", "emis:table")
        if table_elem is not None and table_elem.text:
            table_text = table_elem.text.upper()
            if "MEDICATION" in table_text:
                container_type = "Search Rule Medication Issues"
            elif "PATIENT" in table_text:
                container_type = "Search Rule Patient Demographics"
            elif "EVENT" in table_text:
                container_type = "Search Rule Clinical Events"

    if container_type:
        return PatternResult(
            id="container_heuristics",
            description="Container heuristics for criterion nodes",
            flags={"container_type": container_type},
            confidence="medium",
        )
    return None
