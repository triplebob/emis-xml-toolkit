"""
Data access layer for search exports.
Extracts and normalises search data from session state for Excel and JSON exports.
"""

from typing import Dict, List, Any, Optional, Tuple
import streamlit as st
from ..metadata.value_set_resolver import resolve_value_sets


def get_search_by_id(search_id: str, all_searches: List[Dict]) -> Optional[Dict]:
    """Get single search with all parsed metadata by ID."""
    for search in all_searches:
        if search.get("id") == search_id:
            return search
    return None


def get_search_dependencies(search_id: str, all_searches: List[Dict]) -> Dict[str, List[str]]:
    """
    Returns dictionary with dependants and parents.

    Returns:
        {
            'dependants': [search_ids that use this search],
            'parents': [search_ids this search uses]
        }
    """
    dependants = set()
    parents = set()

    # Find searches this search uses (parents)
    current_search = get_search_by_id(search_id, all_searches)
    if current_search:
        parent_guid = current_search.get("parent_guid") or current_search.get("parent_search_guid")
        if parent_guid:
            parents.add(parent_guid)
        for dep in current_search.get("dependencies") or []:
            if dep:
                parents.add(dep)
        for dep in current_search.get("dependents") or []:
            if dep:
                dependants.add(dep)
        for group in current_search.get("criteria_groups", []):
            pop_refs = group.get("population_criteria", [])
            for ref in pop_refs:
                ref_guid = ref.get("report_guid") or ref.get("guid") or ref.get("id")
                if ref_guid:
                    parents.add(ref_guid)

    # Find searches that use this search (dependants)
    for other_search in all_searches:
        other_id = other_search.get("id")
        if not other_id or other_id == search_id:
            continue

        if other_search.get("parent_guid") == search_id:
            dependants.add(other_id)
            continue

        if search_id in (other_search.get("dependencies") or []):
            dependants.add(other_id)
            continue

        for group in other_search.get("criteria_groups", []):
            pop_refs = group.get("population_criteria", [])
            for ref in pop_refs:
                ref_guid = ref.get("report_guid") or ref.get("guid") or ref.get("id")
                if ref_guid == search_id:
                    dependants.add(other_id)
                    break

    return {
        "dependants": list(dependants),
        "parents": list(parents)
    }


def get_search_folder_path(search_id: str, folders: List[Dict], all_searches: List[Dict]) -> str:
    """
    Returns full folder path like 'QOF/Diabetes/Register'.
    Returns empty string if not in any folder.

    Args:
        search_id: Search GUID
        folders: List of folder dicts with id, name, parent_id
        all_searches: List of all searches to find folder_id
    """
    if not isinstance(folders, list):
        return ""

    # Build mapping of folder ID to folder data
    id_to_folder = {
        f.get("id"): f
        for f in folders
        if isinstance(f, dict) and f.get("id") is not None
    }

    # Find which folder contains this search
    search_folder_id = None
    for search in all_searches:
        if search.get("id") == search_id:
            search_folder_id = search.get("folder_id")
            break

    if not search_folder_id or search_folder_id not in id_to_folder:
        return ""

    # Build path by traversing parent chain
    parts = []
    current = id_to_folder.get(search_folder_id)
    while current:
        folder_name = current.get("name") or ""
        if folder_name:
            parts.append(folder_name)
        parent_id = current.get("parent_id")
        current = id_to_folder.get(parent_id) if parent_id else None

    # Reverse to get root -> leaf order
    return " / ".join(reversed(parts))


def _number_criteria_recursive(
    criteria: List[Dict],
    parent_number: str = "",
    level: int = 0
) -> List[Tuple[str, Dict, int, Optional[Dict]]]:
    """
    Recursively number criteria including nested ones.

    Returns list of tuples: (criterion_number, criterion_dict, nesting_level, relationship_info)
    Example numbers: "1", "1.1", "1.2", "2", "2.1"
    """
    numbered = []

    for idx, criterion in enumerate(criteria, start=1):
        # Build criterion number
        if parent_number:
            number = f"{parent_number}.{idx}"
        else:
            number = str(idx)

        numbered.append((number, criterion, level, None))

        # Recursively process linked criteria
        # linked_criteria has structure: [{"relationship": {...}, "criterion": {...}}]
        linked = criterion.get("linked_criteria", [])
        if linked:
            nested_criteria = []
            for linked_item in linked:
                # Extract the child criterion and relationship
                child_criterion = linked_item.get("criterion")
                relationship = linked_item.get("relationship")

                if child_criterion:
                    # Create a intermediate list with just the criterion for recursion
                    child_numbered = _number_criteria_recursive([child_criterion], number, level + 1)
                    # Update the relationship info for this child
                    if child_numbered:
                        num, crit, lvl, _ = child_numbered[0]
                        nested_criteria.append((num, crit, lvl, relationship))

                        # Also add any nested children of this child
                        if len(child_numbered) > 1:
                            nested_criteria.extend(child_numbered[1:])

            numbered.extend(nested_criteria)

    return numbered


def extract_rule_criteria(group: Dict) -> List[Dict]:
    """
    Extract numbered criteria with all metadata per criterion.
    Includes nested criteria with numbering like 1.1, 1.2 for linked criteria.

    Returns list of dicts with keys:
        - criterion_number: str (e.g., "1", "1.1", "2.1")
        - parent_number: str (e.g., "1" for "1.1", empty for top-level)
        - nesting_level: int (0 for top-level, 1 for first nested, etc.)
        - criterion: Dict (original criterion data)
        - relationship: Dict (temporal relationship info for linked criteria, None for top-level)
    """
    from ..ui.tabs.search_browser.search_criteria_viewer import filter_top_level_criteria

    # Get top-level criteria (non-nested)
    top_level = filter_top_level_criteria(group)

    # Number all criteria recursively
    numbered = _number_criteria_recursive(top_level)

    result = []
    for number, criterion, level, relationship in numbered:
        # Parse parent number
        parent = ""
        if "." in number:
            parent = number.rsplit(".", 1)[0]

        result.append({
            "criterion_number": number,
            "parent_number": parent,
            "nesting_level": level,
            "criterion": criterion,
            "relationship": relationship
        })

    return result


def extract_criterion_codes(
    criterion: Dict,
    criterion_number: str,
    lookup_df=None
) -> List[Dict]:
    """
    Extract all clinical codes from a criterion with source info.
    Returns codes with criterion_number attached (e.g., '1', '1.1', '2').

    Filters out EMISINTERNAL codes (column filters, not clinical codes).
    """
    codes = []
    value_sets = resolve_value_sets(criterion)

    for vs in value_sets:
        code_system = (vs.get("code_system") or "").upper()

        # Skip EMISINTERNAL - these are column filters, not clinical codes
        if code_system == "EMISINTERNAL":
            continue

        code_value = vs.get("code_value")
        if not code_value:
            continue

        # Get display name from VS or lookup
        display_name = vs.get("display_name") or vs.get("display")

        # Try SNOMED lookup if no display name
        if not display_name and lookup_df is not None and code_system in ["SCT_CONST", "SNOMED"]:
            try:
                emis_guid_col = st.session_state.get("emis_guid_column", "EMIS_GUID")
                snomed_term_col = st.session_state.get("snomed_term_column", "SNOMED_Preferred_Term")

                matches = lookup_df[lookup_df[emis_guid_col] == code_value]
                if not matches.empty:
                    display_name = matches.iloc[0][snomed_term_col]
            except Exception:
                pass  # Lookup failed, use code as fallback

        # Fallback to code value if no term
        if not display_name:
            display_name = code_value

        pseudo_member = (
            vs.get("is_pseudomember")
            if vs.get("is_pseudomember") is not None
            else vs.get("is_pseudo_member")
        )
        if pseudo_member is None:
            pseudo_member = vs.get("is_pseudo_refset_member")
        if isinstance(pseudo_member, str):
            pseudo_member = pseudo_member.strip().lower() in ["true", "1", "yes"]

        codes.append({
            "criterion_number": criterion_number,
            "code_system": code_system,
            "code": code_value,
            "term": display_name,
            "valueset_name": vs.get("valueSet_description", ""),
            "valueset_guid": vs.get("valueSet_guid", ""),
            "is_refset": vs.get("is_refset", False),
            "include_children": vs.get("include_children", False),
            "pseudo_refset_member": bool(pseudo_member),
            "negation": criterion.get("flags", {}).get("negation", False)
        })

    return codes


def extract_date_restrictions(criterion: Dict) -> List[Dict]:
    """Extract all date filters from column filters and flags."""
    from ..metadata.temporal_describer import describe_date_filter, describe_age_filter

    restrictions = []
    seen_keys = set()

    # Extract date/age filters from column_filters (same as UI)
    column_filters = criterion.get("column_filters", [])
    for cf in column_filters:
        range_info = cf.get("range") or cf.get("range_info") or {}
        filter_type = cf.get("type") or cf.get("filter_type") or ""
        column_display = cf.get("column_display") or cf.get("display_name") or cf.get("column_name") or ""
        column_name = cf.get("column") or cf.get("column_name") or ""

        # Deduplicate filters (same as UI logic)
        column_name_norm = str(column_name).strip().upper().replace("-", "_")
        key = (filter_type, column_name_norm, str(range_info))
        if key in seen_keys:
            continue
        seen_keys.add(key)

        if filter_type == "date" and range_info:
            desc = describe_date_filter(range_info, column_display, column_name, cf.get("relative_to"))
            if desc:
                restrictions.append({
                    "type": "date_filter",
                    "description": desc
                })

        elif filter_type == "age" and range_info:
            desc = describe_age_filter(range_info, column_name)
            if desc:
                restrictions.append({
                    "type": "age_filter",
                    "description": desc
                })

    return restrictions


def extract_event_restrictions(criterion: Dict) -> List[Dict]:
    """Extract event-based restrictions (first/last/nth record, ordering)."""
    from ..metadata.restriction_describer import describe_restrictions

    event_restrictions = []
    flags = criterion.get("flags", {})

    # Build restrictions from flags data (same as UI does)
    if flags.get("has_restriction"):
        restrictions = []
        if flags.get("record_count") or flags.get("ordering_direction"):
            restriction_data = {
                "columnOrder": {
                    "recordCount": flags.get("record_count"),
                    "direction": flags.get("ordering_direction", "DESC"),
                }
            }
            restrictions.append(restriction_data)

        # Use the same describer as the UI
        if restrictions:
            friendly = describe_restrictions(restrictions)
            for desc in friendly:
                event_restrictions.append({
                    "type": "record_restriction",
                    "description": desc
                })

    # Also check for other occurrence restrictions
    if flags.get("first_occurrence"):
        event_restrictions.append({
            "type": "first_occurrence",
            "applies_to_date_range": flags.get("first_in_date_range", True)
        })

    if flags.get("last_occurrence"):
        event_restrictions.append({
            "type": "last_occurrence",
            "applies_to_date_range": flags.get("last_in_date_range", True)
        })

    if flags.get("nth_occurrence"):
        event_restrictions.append({
            "type": "nth_occurrence",
            "occurrence_number": flags.get("occurrence_number", 1)
        })

    return event_restrictions


def extract_value_restrictions(criterion: Dict) -> List[Dict]:
    """Extract value-based restrictions (ranges, comparisons) from column filters and flags."""
    from ..metadata.temporal_describer import describe_numeric_filter

    restrictions = []
    seen_keys = set()

    # Extract numeric filters from column_filters (same as UI)
    column_filters = criterion.get("column_filters", [])
    for cf in column_filters:
        range_info = cf.get("range") or cf.get("range_info") or {}
        filter_type = cf.get("type") or cf.get("filter_type") or ""
        column_name = cf.get("column") or cf.get("column_name") or ""

        # Deduplicate filters (same as UI logic)
        column_name_norm = str(column_name).strip().upper().replace("-", "_")
        key = (filter_type, column_name_norm, str(range_info))
        if key in seen_keys:
            continue
        seen_keys.add(key)

        if filter_type == "numeric" and range_info:
            desc = describe_numeric_filter(range_info)
            if desc:
                restrictions.append({
                    "type": "numeric_filter",
                    "description": desc
                })

    # Also check flags for value restrictions
    flags = criterion.get("flags", {})

    # Value comparisons
    if flags.get("has_value_restriction"):
        operator = flags.get("value_operator", "=")
        value = flags.get("value_threshold")
        unit = flags.get("value_unit", "")
        is_param = flags.get("value_is_parameter", False)

        if value is not None:
            restrictions.append({
                "operator": operator,
                "value": value,
                "unit": unit,
                "is_parameter": is_param
            })

    # Value ranges
    if flags.get("has_value_range"):
        restrictions.append({
            "operator": "in_range",
            "min_value": flags.get("value_range_min"),
            "max_value": flags.get("value_range_max"),
            "unit": flags.get("value_unit", "")
        })

    return restrictions


def extract_parameters(search: Dict) -> List[Dict]:
    """Extract all parameters with scope and data type."""
    parameters = []
    flags = search.get("flags", {})

    if not flags.get("has_parameter"):
        return parameters

    param_names = flags.get("parameter_names", [])
    param_metadata = flags.get("parameter_metadata", {})

    for param_name in param_names:
        metadata = param_metadata.get(param_name, {})

        parameters.append({
            "name": param_name,
            "data_type": metadata.get("data_type", "Unknown"),
            "scope": metadata.get("scope", "Search"),
            "description": metadata.get("description", "")
        })

    return parameters


def get_population_references(
    group: Dict,
    id_to_name: Dict,
    all_searches: List[Dict]
) -> List[Dict]:
    """Get all linked searches with display names."""
    from ..ui.tabs.search_browser.search_criteria_viewer import format_population_reference

    pop_refs = group.get("population_criteria", [])
    results = []

    seen_guids = set()
    for ref in pop_refs:
        ref_guid = ref.get("report_guid") or ref.get("guid") or ref.get("id")

        if ref_guid in seen_guids:
            continue
        seen_guids.add(ref_guid)

        label = format_population_reference(ref_guid, id_to_name, all_searches)
        weight = ref.get("score_weightage", "")

        results.append({
            "search_id": ref_guid,
            "search_name": label,
            "score_weight": weight if weight else None
        })

    return results


def format_date_restriction(restriction: Dict) -> str:
    """Format date restriction for human-readable export."""
    # Structured format with description
    if restriction.get("description"):
        return restriction["description"]

    # Compatibility format (kept for backwards compatibility)
    if restriction.get("type") == "earliest":
        value = restriction["value"]
        if restriction.get("is_parameter"):
            return f"Earliest: [{value}] (parameter)"
        return f"Earliest: {value}"

    elif restriction.get("type") == "latest":
        value = restriction["value"]
        if restriction.get("is_parameter"):
            return f"Latest: [{value}] (parameter)"
        return f"Latest: {value}"

    elif restriction.get("type") == "relative":
        anchor = restriction.get("anchor", "event_date")
        years = restriction.get("offset_years", 0)
        months = restriction.get("offset_months", 0)
        days = restriction.get("offset_days", 0)

        parts = []
        if years:
            parts.append(f"{years}y")
        if months:
            parts.append(f"{months}m")
        if days:
            parts.append(f"{days}d")

        offset_str = " ".join(parts) if parts else "0d"
        return f"Relative: {anchor} + {offset_str}"

    return str(restriction)


def format_event_restriction(restriction: Dict) -> str:
    """Format event restriction for human-readable export."""
    # Structured format with description
    if restriction.get("description"):
        return restriction["description"]

    # Compatibility format (kept for backwards compatibility)
    if restriction.get("type") == "first_occurrence":
        if restriction.get("applies_to_date_range"):
            return "First occurrence in date range"
        return "First occurrence only"

    elif restriction.get("type") == "last_occurrence":
        if restriction.get("applies_to_date_range"):
            return "Last occurrence in date range"
        return "Last occurrence only"

    elif restriction.get("type") == "nth_occurrence":
        n = restriction.get("occurrence_number", 1)
        return f"Occurrence #{n}"

    return str(restriction)


def format_rule_action(action: str) -> str:
    """Format rule action from raw value to user-friendly text."""
    action_upper = str(action or "").upper()
    mapping = {
        "SELECT": "Include in final result",
        "REJECT": "Exclude from final result",
        "NEXT": "Goto next rule"
    }
    return mapping.get(action_upper, action)


def format_value_restriction(restriction: Dict) -> str:
    """Format value restriction for human-readable export."""
    # Structured format with description
    if restriction.get("description"):
        return restriction["description"]

    # Compatibility format (kept for backwards compatibility)
    operator = restriction.get("operator", "=")
    unit = restriction.get("unit", "")
    unit_str = f" {unit}" if unit else ""

    if operator == "in_range":
        min_val = restriction.get("min_value")
        max_val = restriction.get("max_value")
        return f"Value in range [{min_val}-{max_val}]{unit_str}"

    else:
        value = restriction.get("value")
        is_param = restriction.get("is_parameter", False)

        if is_param:
            return f"Value {operator} [{value}] (parameter){unit_str}"
        return f"Value {operator} {value}{unit_str}"
