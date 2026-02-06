"""
JSON export functionality for searches.
Generates comprehensive JSON representations of search structures.
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import streamlit as st

from .search_data_provider import (
    get_search_by_id,
    get_search_dependencies,
    get_search_folder_path,
    extract_rule_criteria,
    extract_criterion_codes,
    extract_date_restrictions,
    extract_event_restrictions,
    extract_value_restrictions,
    extract_parameters,
    get_population_references,
    format_rule_action,
)
from ..metadata.emisinternal_describer import describe_emisinternal_filter
from ..metadata.value_set_resolver import resolve_value_sets
from ..system.session_state import SessionStateKeys


EMOJI_RANGES = (
    (0x2600, 0x26FF),    # misc symbols
    (0x2700, 0x27BF),    # dingbats
    (0x1F1E6, 0x1F1FF),  # flags
    (0x1F300, 0x1F5FF),  # symbols & pictographs
    (0x1F600, 0x1F64F),  # emoticons
    (0x1F680, 0x1F6FF),  # transport & map symbols
    (0x1F900, 0x1FAFF),  # supplemental symbols and pictographs
)
EMOJI_CODEPOINTS = {
    0xFE0F,  # variation selector
    0x200D,  # zero width joiner
}


def _strip_emojis(text: str) -> str:
    """Remove emojis and other pictographs from text."""
    cleaned_chars: List[str] = []
    for ch in str(text):
        codepoint = ord(ch)
        if codepoint in EMOJI_CODEPOINTS:
            continue
        if any(start <= codepoint <= end for start, end in EMOJI_RANGES):
            continue
        cleaned_chars.append(ch)
    return "".join(cleaned_chars).strip()


def _get_version() -> str:
    """Get ClinXML version from Version.py."""
    try:
        from Version import __version__
        return __version__
    except ImportError:
        return "Unknown"


def _format_parameters_with_scope(criterion: Dict, flags: Dict) -> List[Dict]:
    """Format parameters with scope information, deduplicated."""
    params = criterion.get("parameters") or flags.get("parameter_names") or []
    if not params:
        return []

    # Determine default scope
    scope_bits = []
    if flags.get("has_global_parameters"):
        scope_bits.append("Global")
    if flags.get("has_local_parameters"):
        scope_bits.append("Local")
    default_scope = " & ".join(scope_bits) if scope_bits else "Unknown"

    # Build formatted parameter list
    param_list = []
    seen = set()
    for p in params:
        if isinstance(p, dict):
            name = p.get("name") or str(p)
            # Check if this parameter has its own scope info
            p_scope_bits = []
            if p.get("allowGlobal") or p.get("is_global"):
                p_scope_bits.append("Global")
            if p.get("allowLocal") or p.get("is_local"):
                p_scope_bits.append("Local")
            p_scope = " & ".join(p_scope_bits) if p_scope_bits else default_scope
        else:
            name = str(p)
            p_scope = default_scope

        # Deduplicate by name
        if name not in seen:
            param_list.append({
                "name": name,
                "scope": p_scope
            })
            seen.add(name)

    return param_list


def _serialize_criterion(
    criterion_info: Dict,
    group: Dict,
    id_to_name: Dict,
    all_searches: List[Dict],
) -> Dict[str, Any]:
    """Serialize a single criterion with all metadata."""
    criterion = criterion_info["criterion"]
    flags = criterion.get("flags", {})

    # Extract all codes for this criterion
    codes = extract_criterion_codes(
        criterion,
        criterion_info["criterion_number"],
    )

    # Extract restrictions
    date_restrictions = extract_date_restrictions(criterion)
    event_restrictions = extract_event_restrictions(criterion)
    value_restrictions = extract_value_restrictions(criterion)

    # Extract EMISINTERNAL filters - get column display names from column_filters
    emisinternal_filters = []
    seen_filter_keys = set()

    # Build map of column name to display name from column_filters
    column_display_map = {}
    for cf in criterion.get("column_filters", []):
        col_name = (cf.get("column") or cf.get("column_name") or "").strip().upper()
        col_display = cf.get("column_display") or cf.get("display_name") or cf.get("column_name") or ""
        if col_name:
            column_display_map[col_name] = col_display

    # Prefer enriched entries from flags (these are processed by pattern plugins)
    emisinternal_entries = flags.get("emisinternal_entries") or []
    if emisinternal_entries:
        for entry in emisinternal_entries:
            entry_values = entry.get("values") or []
            # Skip empty filters
            if not entry_values:
                continue

            raw_column = entry.get("column") or ""
            # Handle column as string or array (from multi-column patterns)
            if isinstance(raw_column, list):
                raw_column = raw_column[-1] if raw_column else ""  # Use last column (most specific)
            raw_column = str(raw_column).strip().upper()

            # Get display name from column_filters map
            column_display = column_display_map.get(raw_column) or raw_column
            in_not_in = str(entry.get("in_not_in", "IN")).upper()

            # Get values with displayNames
            values = []
            for val in entry_values:
                if isinstance(val, dict):
                    values.append({
                        "code": val.get("value", ""),
                        "display": val.get("displayName", val.get("value", ""))
                    })

            # Create deduplication key
            values_key = tuple(sorted([v["code"] for v in values]))
            dedup_key = (raw_column, in_not_in, values_key)

            # Skip if we've already added this filter
            if dedup_key in seen_filter_keys:
                continue
            seen_filter_keys.add(dedup_key)

            filter_entry = {
                "column": raw_column,
                "display_name": column_display,
                "operator": in_not_in,
                "values": values
            }

            if entry.get("has_all_values"):
                filter_entry["all_values"] = True

            emisinternal_filters.append(filter_entry)
    else:
        # Fallback to value_sets if no enriched entries
        for vs in resolve_value_sets(criterion):
            code_system = (vs.get("code_system") or "").upper()
            if code_system == "EMISINTERNAL":
                column = vs.get("column_name") or vs.get("column", "")
                column_display = vs.get("column_display_name") or column_display_map.get(column.upper()) or column
                in_not_in = vs.get("in_not_in", "IN")

                # Get values with displayNames
                values = []
                for val in vs.get("values", []):
                    if isinstance(val, dict):
                        values.append({
                            "code": val.get("value", ""),
                            "display": val.get("displayName", val.get("value", ""))
                        })

                # Skip empty filters
                if not values:
                    continue

                # Create deduplication key
                values_key = tuple(sorted([v["code"] for v in values]))
                dedup_key = (column.upper(), in_not_in, values_key)

                if dedup_key in seen_filter_keys:
                    continue
                seen_filter_keys.add(dedup_key)

                emisinternal_filters.append({
                    "column": column,
                    "display_name": column_display,
                    "operator": in_not_in,
                    "values": values
                })

    # Extract demographics (including LSOA)
    demographics = {}

    # LSOA demographics
    if flags.get("demographics_type") == "LSOA":
        lsoa_codes = flags.get("consolidated_lsoa_codes", [])
        demographics = {
            "type": "LSOA",
            "column_display": flags.get("column_display_name") or "Lower Layer Area",
            "lsoa_codes": lsoa_codes,
            "count": flags.get("consolidated_count", len(lsoa_codes))
        }
    # Standard demographics (age/sex/status)
    elif flags.get("has_demographic_filters"):
        demographics = {
            "type": "standard",
            "age_min": flags.get("age_min"),
            "age_max": flags.get("age_max"),
            "age_parameter": flags.get("age_parameter"),
            "sex": flags.get("sex_filter"),
            "patient_status": flags.get("patient_status")
        }
    # Other demographics types
    elif flags.get("is_patient_demographics") or flags.get("demographics_type"):
        demographics = {
            "type": flags.get("demographics_type") or "patient_demographics"
        }

    # Build linked relationship description if this is a nested criterion
    linked_relationship = None
    relationship = criterion_info.get("relationship")
    if relationship:
        from ..parsing.node_parsers.linked_criteria_parser import get_temporal_relationship_description

        parent_col = relationship.get("parent_column_display_name") or relationship.get("parent_column") or ""
        child_col = relationship.get("child_column_display_name") or relationship.get("child_column") or ""
        temporal_desc = get_temporal_relationship_description(relationship)

        linked_relationship = {
            "parent_column": parent_col,
            "child_column": child_col,
            "temporal_description": temporal_desc or "relates to"
        }

    return {
        "criterion_number": criterion_info["criterion_number"],
        "parent_criterion": criterion_info["parent_number"] or None,
        "nesting_level": criterion_info["nesting_level"],
        "table": flags.get("logical_table_name") or criterion.get("table", "Unknown"),
        "action": "Exclude" if flags.get("negation") else "Include",
        "score_weight": flags.get("score_weightage") or None,
        "clinical_codes": codes,
        "restrictions": {
            "date_restrictions": date_restrictions,
            "event_restrictions": event_restrictions,
            "value_restrictions": value_restrictions
        },
        "emisinternal_filters": emisinternal_filters,
        "demographics": demographics if demographics else None,
        "parameters_used": _format_parameters_with_scope(criterion, flags),
        "notes": flags.get("exception_code", ""),
        "linked_relationship": linked_relationship
    }


def export_search_json(
    search_id: str,
    all_searches: List[Dict],
    folders: List[Dict],
    id_to_name: Dict
) -> str:
    """
    Export a single search to JSON format.

    Returns JSON string with complete search structure including:
    - All metadata and flags
    - All rules with criteria
    - All clinical codes with terms
    - All restrictions and parameters
    - Nested criteria with proper hierarchy
    """
    search = get_search_by_id(search_id, all_searches)
    if not search:
        raise ValueError(f"Search not found: {search_id}")

    # Get dependencies
    dependencies = get_search_dependencies(search_id, all_searches)

    # Resolve dependency names (with emojis stripped)
    dependant_names = []
    for dep_id in dependencies["dependants"]:
        dep_search = get_search_by_id(dep_id, all_searches)
        if dep_search:
            dependant_names.append({
                "id": dep_id,
                "name": _strip_emojis(dep_search.get("name", dep_id))
            })

    parent_names = []
    for parent_id in dependencies["parents"]:
        parent_search = get_search_by_id(parent_id, all_searches)
        if parent_search:
            parent_names.append({
                "id": parent_id,
                "name": _strip_emojis(parent_search.get("name", parent_id))
            })

    # Extract parameters
    parameters = extract_parameters(search)

    # Build rules array
    rules = []
    for rule_idx, group in enumerate(search.get("criteria_groups", []), start=1):
        group_flags = group.get("group_flags", {})
        operator = group_flags.get("operator") or group.get("operator") or group_flags.get("member_operator") or "AND"

        # Build rule structure
        action_if_true_raw = group_flags.get("action_if_true") or "SELECT"
        action_if_false_raw = group_flags.get("action_if_false") or "REJECT"

        rule = {
            "rule_number": rule_idx,
            "operator": operator.upper(),
            "actions": {
                "if_rule_passed": format_rule_action(action_if_true_raw),
                "if_rule_failed": format_rule_action(action_if_false_raw)
            }
        }

        # Add score threshold if SCORE rule
        if operator.upper() == "SCORE":
            score_range = group_flags.get("score_range", {})
            if score_range:
                rule["score_threshold"] = {
                    "operator": score_range.get("operator", "GTEQ"),
                    "min_score": score_range.get("min_score", "")
                }

        # Extract all criteria (including nested)
        criteria_list = []
        for criterion_info in extract_rule_criteria(group):
            serialized = _serialize_criterion(
                criterion_info,
                group,
                id_to_name,
                all_searches,
            )
            criteria_list.append(serialized)

        rule["criteria"] = criteria_list

        # Add population references (with emojis stripped)
        pop_refs = get_population_references(group, id_to_name, all_searches)
        if pop_refs:
            # Strip emojis from search names
            cleaned_refs = []
            for ref in pop_refs:
                cleaned_ref = ref.copy()
                cleaned_ref["search_name"] = _strip_emojis(ref["search_name"])
                cleaned_refs.append(cleaned_ref)
            rule["population_references"] = cleaned_refs

        rules.append(rule)

    # Build final structure
    output = {
        "metadata": {
            "export_timestamp": datetime.now().isoformat(),
            "clinxml_version": _get_version(),
            "search_id": search_id,
            "search_name": search.get("name", ""),
            "folder_path": get_search_folder_path(search_id, folders, all_searches),
            "export_type": "single_search",
            "generated_by": "ClinXML™ EMIS XML Toolkit (https://clinxml.streamlit.app)"
        },
        "search": {
            "id": search_id,
            "name": search.get("name", ""),
            "description": search.get("description", ""),
            "parameters": parameters if parameters else None,
            "dependencies": {
                "parent_populations": parent_names,
                "dependants": dependant_names
            },
            "rules": rules
        }
    }

    return json.dumps(output, indent=2, ensure_ascii=False)


def export_full_structure_json(all_searches: List[Dict], folders: List[Dict]) -> str:
    """
    Export entire XML structure to JSON.

    Includes:
    - All searches with complete metadata
    - Folder hierarchy (as list with parent_id relationships)
    - Dependency graph
    - Full search structures
    """
    # Build ID to name mapping
    id_to_name = {}
    for search in all_searches:
        search_id = search.get("id")
        if search_id:
            id_to_name[search_id] = search.get("name", search_id)

    # Build dependency graph
    dependency_graph = {}
    for search in all_searches:
        search_id = search.get("id")
        if search_id:
            deps = get_search_dependencies(search_id, all_searches)
            dependency_graph[search_id] = {
                "uses": deps["parents"],
                "used_by": deps["dependants"]
            }

    # Serialize all searches
    searches_array = []
    for search in all_searches:
        search_id = search.get("id")
        if not search_id:
            continue

        try:
            # Export individual search
            search_json_str = export_search_json(search_id, all_searches, folders, id_to_name)
            search_data = json.loads(search_json_str)

            # Extract just the search portion
            searches_array.append(search_data["search"])

        except Exception as e:
            # Log error but continue with other searches
            if st.session_state.get(SessionStateKeys.DEBUG_MODE):
                st.warning(f"Failed to export search {search.get('name', search_id)}: {str(e)}")
            continue

    # Get source filename
    source_filename = st.session_state.get(SessionStateKeys.XML_FILENAME, "Unknown")

    # Build final structure
    output = {
        "metadata": {
            "export_timestamp": datetime.now().isoformat(),
            "clinxml_version": _get_version(),
            "total_searches": len(searches_array),
            "source_filename": source_filename,
            "export_type": "full_structure",
            "generated_by": "ClinXML™ EMIS XML Toolkit (https://clinxml.streamlit.app)"
        },
        "folders": folders,  # List of folder dicts with id, name, parent_id
        "searches": searches_array,
        "dependency_graph": dependency_graph
    }

    return json.dumps(output, indent=2, ensure_ascii=False)
