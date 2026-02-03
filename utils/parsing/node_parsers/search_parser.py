"""
Search parser for search reports (population logic only).
Includes criteria groups, dependencies, and population references.
Supports early deduplication via CodeStore for performance optimisation.
"""

import xml.etree.ElementTree as ET
import re
from typing import Dict, Any, List, TYPE_CHECKING
from ...pattern_plugins.registry import pattern_registry
from ...pattern_plugins.base import PatternContext
from ...metadata.flag_mapper import map_element_flags
from .criterion_parser import parse_criterion
from ..namespace_utils import findall_ns, find_ns, get_text_ns

if TYPE_CHECKING:
    from ...caching.code_store import CodeStore

# LSOA pattern matching
LSOA_REGEX = re.compile(r"_LOWER_AREA_|LSOA", re.IGNORECASE)


def _consolidate_lsoa_criteria(criteria_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Consolidate multiple LSOA criteria with same table/column into single criterion.

    When multiple criteria share:
    - Same logical_table_name
    - Same column_name (matching LSOA pattern)
    - Each with single values

    They are merged into one criterion with combined LSOA codes.
    """
    # Identify LSOA criteria by column name
    lsoa_groups: Dict[tuple, List[Dict[str, Any]]] = {}
    non_lsoa: List[Dict[str, Any]] = []

    for crit in criteria_list:
        flags = crit.get("flags", {})
        table = flags.get("logical_table_name", "")
        column_names = flags.get("column_name", [])

        # Normalise to list
        if isinstance(column_names, str):
            column_names = [column_names]

        # Check if any column matches LSOA pattern
        is_lsoa = any(LSOA_REGEX.search(col) for col in column_names if col)

        if is_lsoa and column_names:
            # Group by (table, first column)
            key = (table, column_names[0])
            lsoa_groups.setdefault(key, []).append(crit)
        else:
            non_lsoa.append(crit)

    # Consolidate each LSOA group
    consolidated: List[Dict[str, Any]] = []
    for (table, column), group in lsoa_groups.items():
        if len(group) == 1:
            # No consolidation needed
            consolidated.append(group[0])
        else:
            # Extract all LSOA codes from the group
            seen_codes: set = set()
            lsoa_codes: List[str] = []
            for crit in group:
                # Get column_filters from criterion dict (not flags)
                column_filters = crit.get("column_filters", [])

                # Extract value from range_info
                for cf in column_filters:
                    range_info = cf.get("range_info", {})
                    from_val = range_info.get("from", {})
                    value = from_val.get("value", "")
                    if value and value not in seen_codes:
                        seen_codes.add(value)
                        lsoa_codes.append(value)

            # Create merged criterion with consolidated codes
            merged = group[0].copy()
            merged_flags = merged.get("flags", {}).copy()
            merged_flags["is_consolidated"] = True
            merged_flags["consolidated_count"] = len(group)
            merged_flags["consolidated_lsoa_codes"] = lsoa_codes
            merged["flags"] = merged_flags

            consolidated.append(merged)

    # Return consolidated + non-LSOA criteria
    return consolidated + non_lsoa


def parse_search(
    search_elem: ET.Element,
    namespaces: Dict[str, str],
    code_store: "CodeStore",
) -> Dict[str, Any]:
    pattern_registry.load_all_modules("utils.pattern_plugins")
    pattern_results = pattern_registry.run_all(PatternContext(element=search_elem, namespaces=namespaces, path=search_elem.tag))
    flags = map_element_flags(search_elem, namespaces, pattern_results)
    flags["element_type"] = "search"

    name = get_text_ns(search_elem, "name", namespaces)
    desc = get_text_ns(search_elem, "description", namespaces)
    folder_id = get_text_ns(search_elem, "folder", namespaces)
    search_date = get_text_ns(search_elem, "searchDate", namespaces)
    search_id = get_text_ns(search_elem, "id", namespaces)
    if search_id:
        flags["element_id"] = search_id
    if folder_id:
        flags["folder_id"] = folder_id
    if search_date:
        flags["search_date"] = search_date

    # Parent linkage (search/report dependencies)
    parent_elem = find_ns(search_elem, "parent", namespaces)
    if parent_elem is not None:
        # Extract parentType attribute
        parent_type = parent_elem.get("parentType") or parent_elem.get("parent_type")
        if parent_type:
            flags["parent_type"] = parent_type

        search_identifier = find_ns(parent_elem, "SearchIdentifier", namespaces)
        if search_identifier is not None:
            parent_guid = search_identifier.get("reportGuid") or search_identifier.get("searchGuid") or search_identifier.get("reportguid")
            if parent_guid:
                flags["parent_search_guid"] = parent_guid

    if name:
        flags["display_name"] = name
    if desc:
        flags["description"] = desc

    criteria_groups: List[Dict[str, Any]] = []
    population_links: List[Dict[str, Any]] = []

    for group in _find_direct_groups(search_elem, namespaces):
        group_id = get_text_ns(group, "id", namespaces)
        definition = find_ns(group, "definition", namespaces)
        member_op = ""
        action_true = ""
        action_false = ""
        score_range = {}
        if definition is not None:
            member_op = get_text_ns(definition, "memberOperator", namespaces) or "AND"

            # Extract score range if member_operator is SCORE
            if member_op.upper() == "SCORE":
                score_elem = find_ns(definition, "score", namespaces)
                if score_elem is not None:
                    score_range = _parse_score_range(score_elem, namespaces)

        # Actions are siblings of definition, not children
        action_true = get_text_ns(group, "actionIfTrue", namespaces)
        action_false = get_text_ns(group, "actionIfFalse", namespaces)

        group_flags: Dict[str, Any] = {}
        if group_id:
            group_flags["criteria_group_id"] = group_id
        if member_op:
            group_flags["member_operator"] = member_op
        if action_true:
            group_flags["action_if_true"] = action_true
        if action_false:
            group_flags["action_if_false"] = action_false
        if score_range:
            group_flags["score_range"] = score_range

        pop_criteria = _find_population_criteria(group, namespaces)
        if pop_criteria:
            population_links.extend(pop_criteria)

        parsed_group_criteria: List[Dict[str, Any]] = []
        criteria_with_weights = _find_criteria_with_weights(group, namespaces)

        for crit, score_weightage in criteria_with_weights:
            parsed = parse_criterion(
                crit,
                namespaces,
                parent_context={
                    "container_type": "Search Rule Main Criteria",
                    "source_name": name,
                    "criteria_group_id": group_id,
                    "member_operator": member_op,
                    "action_if_true": action_true,
                    "action_if_false": action_false,
                    "source_guid": flags.get("element_id"),
                    "source_type": "search",
                },
                code_store=code_store,
            )

            # Add scoreWeightage to parsed criterion if present
            if score_weightage:
                parsed["flags"]["score_weightage"] = score_weightage

            parsed_group_criteria.append(parsed)

        # Consolidate LSOA criteria before storing
        consolidated_criteria = _consolidate_lsoa_criteria(parsed_group_criteria)

        # Add to overall criteria flags
        criteria_groups.append(
            {
                "group_flags": group_flags,
                "criteria": consolidated_criteria,
                "population_criteria": pop_criteria,
            }
        )

    dependencies = []
    if flags.get("parent_search_guid"):
        dependencies.append(flags["parent_search_guid"])
    for pop in population_links:
        guid = pop.get("report_guid")
        if guid:
            dependencies.append(guid)

    return {
        "id": flags.get("element_id") or search_id or "",
        "flags": flags,
        "criteria_groups": criteria_groups,
        "dependencies": dependencies,
        "parent_type": flags.get("parent_type"),
        "description": desc,
        "name": name,
    }


def _parse_score_range(score_elem: ET.Element, namespaces: Dict[str, str]) -> Dict[str, Any]:
    """Parse score range from SCORE-based criteria group."""
    score_range: Dict[str, Any] = {}
    range_value = find_ns(score_elem, "rangeValue", namespaces)
    if range_value is None:
        return {}

    # Parse rangeFrom
    range_from = find_ns(range_value, "rangeFrom", namespaces)
    if range_from is not None:
        value_node = find_ns(range_from, "value", namespaces)
        if value_node is not None:
            value_text = get_text_ns(value_node, "value", namespaces)
            if value_text:
                score_range["min_score"] = value_text
        operator = get_text_ns(range_from, "operator", namespaces)
        if operator:
            score_range["operator"] = operator

    # Parse rangeTo if present
    range_to = find_ns(range_value, "rangeTo", namespaces)
    if range_to is not None:
        value_node = find_ns(range_to, "value", namespaces)
        if value_node is not None:
            value_text = get_text_ns(value_node, "value", namespaces)
            if value_text:
                score_range["max_score"] = value_text

    return score_range


def _find_direct_groups(search_elem: ET.Element, namespaces: Dict[str, str]) -> List[ET.Element]:
    """Find top-level criteriaGroup nodes to avoid double counting nested groups."""
    # Look for criteriaGroup under population element first, then directly
    groups = findall_ns(search_elem, "population/criteriaGroup", namespaces)
    # Only look for direct criteriaGroups if none found under population
    if not groups:
        groups = findall_ns(search_elem, "criteriaGroup", namespaces)
    return groups


def _find_criteria_with_weights(group_elem: ET.Element, namespaces: Dict[str, str]) -> List[tuple]:
    """Find criterion elements and their scoreWeightage from parent <criteria> wrappers.

    Returns list of tuples: (criterion_element, score_weightage_value)
    """
    results: List[tuple] = []
    seen_criteria = set()

    definition = find_ns(group_elem, "definition", namespaces)
    if definition is None:
        return results

    # Find all <criteria> blocks (wrappers that may contain criterion + scoreWeightage)
    for criteria_block in findall_ns(definition, "criteria", namespaces):
        # Find criterion elements within this block
        for crit in findall_ns(criteria_block, "criterion", namespaces):
            if id(crit) not in seen_criteria:
                seen_criteria.add(id(crit))
                results.append((crit, get_text_ns(criteria_block, "scoreWeightage", namespaces)))

    # Also check for direct criterion children of definition (no criteria wrapper)
    for crit in findall_ns(definition, "criterion", namespaces):
        if id(crit) not in seen_criteria:
            seen_criteria.add(id(crit))
            results.append((crit, ""))

    return results


def _find_population_criteria(group_elem: ET.Element, namespaces: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Find population criteria and extract scoreWeightage from parent <criteria> wrapper if present.

    Handles two structures:
    1. Wrapped in <criteria> with scoreWeightage:
        <criteria>
            <populationCriterion reportGuid="..."/>
            <scoreWeightage>1</scoreWeightage>
        </criteria>
    2. Direct child (no scoreWeightage):
        <populationCriterion reportGuid="..."/>
    """
    results: List[Dict[str, Any]] = []
    seen_guids = set()

    # First: Find population criteria wrapped in <criteria> blocks (may have scoreWeightage)
    criteria_blocks = findall_ns(group_elem, ".//criteria", namespaces)

    for criteria_block in criteria_blocks:
        # Look for populationCriterion within this criteria block
        pop_node = find_ns(criteria_block, "populationCriterion", namespaces)

        if pop_node is not None:
            report_guid = pop_node.get("reportGuid") or ""
            crit_id = pop_node.get("id") or get_text_ns(pop_node, "id", namespaces)

            # Skip if already processed
            if report_guid and report_guid in seen_guids:
                continue

            entry: Dict[str, Any] = {}
            if crit_id:
                entry["criterion_id"] = crit_id
            if report_guid:
                entry["report_guid"] = report_guid
                seen_guids.add(report_guid)

            # Extract scoreWeightage from the same criteria block
            score_weight = get_text_ns(criteria_block, "scoreWeightage", namespaces)
            if score_weight:
                entry["score_weightage"] = score_weight

            if entry:
                results.append(entry)

    # Second: Find any direct populationCriterion elements not already processed
    all_pop_nodes = findall_ns(group_elem, ".//populationCriterion", namespaces)

    for pop_node in all_pop_nodes:
        report_guid = pop_node.get("reportGuid") or ""

        # Skip if already processed from criteria block
        if report_guid and report_guid in seen_guids:
            continue

        crit_id = pop_node.get("id") or get_text_ns(pop_node, "id", namespaces)
        entry: Dict[str, Any] = {}

        if crit_id:
            entry["criterion_id"] = crit_id
        if report_guid:
            entry["report_guid"] = report_guid
            seen_guids.add(report_guid)

        if entry:
            results.append(entry)

    return results
