"""
Enhanced rendering for search criteria with EMIS-style wording.
Supports nested linked criteria, value sets, and filters in the search browser.
"""

import streamlit as st
import pandas as pd
from typing import Dict, List, Any, Optional

from ....system.session_state import SessionStateKeys
from ....caching.search_cache import get_criteria_expanded, set_criteria_expanded
from ....metadata.description_generators import (
    format_action_indicator,
    format_rule_name,
    format_member_operator,
    format_emis_style_description,
)
from ....metadata.temporal_describer import (
    describe_date_filter,
    describe_age_filter,
    describe_numeric_filter,
)
from ....metadata.emisinternal_describer import describe_emisinternal_filter
from ....metadata.restriction_describer import describe_restrictions
from ....metadata.population_describer import format_population_reference
from ....metadata.value_set_resolver import resolve_value_sets
from ....parsing.node_parsers.linked_criteria_parser import (
    filter_top_level_criteria,
    has_linked_criteria,
    filter_linked_value_sets_from_main,
    filter_linked_column_filters_from_main,
    get_temporal_relationship_description,
)
from ....metadata.column_name_mapper import get_column_display_name

def _get_snomed_cache() -> Dict[str, Any]:
    """Fetch the SNOMED cache from session state."""
    return st.session_state.get(SessionStateKeys.MATCHED_EMIS_SNOMED_CACHE, {}) or {}


@st.cache_data(ttl=600, max_entries=1, scope="session")
def _build_clinical_codes_cache(file_hash: str, codes_count: int) -> Dict[str, Dict[str, Any]]:
    """Cached clinical codes lookup builder - invalidates on file change."""
    pipeline_codes = st.session_state.get(SessionStateKeys.PIPELINE_CODES, []) or []
    cache = {}
    for code in pipeline_codes:
        emis_guid = code.get("EMIS GUID") or code.get("emis_guid") or ""
        if emis_guid:
            cache[emis_guid] = code
    return cache


def _get_clinical_codes_cache() -> Dict[str, Dict[str, Any]]:
    """
    Get clinical codes cache from PIPELINE_CODES, indexed by EMIS GUID.
    Returns a dict mapping EMIS GUID to code data with fields like:
    - 'ValueSet Description' (value set name)
    - 'SNOMED Description' (SNOMED term)
    - 'SNOMED Code'
    - 'EMIS GUID'
    - etc.
    """
    file_hash = st.session_state.get("last_processed_hash") or st.session_state.get("current_file_hash") or ""
    codes = st.session_state.get(SessionStateKeys.PIPELINE_CODES, []) or []
    return _build_clinical_codes_cache(file_hash, len(codes))


def _code_system_label(code_system: str) -> str:
    """Return a friendly label for common code systems."""
    if not code_system:
        return ""
    key = str(code_system).upper()
    if "SCT" in key or "SNOMED" in key:
        return "SNOMED Clinical Terminology"
    if "DRUG" in key:
        return "Drug code"
    if "EMISINTERNAL" in key:
        return "EMIS Internal Classification"
    if "LIBRARY" in key:
        return "EMIS Library Item"
    return code_system


def _normalise_column_name(value: Any) -> str:
    """Normalise a column name for comparison."""
    return (str(value or "").strip()) if value is not None else ""


def _criterion_title(criterion: Dict, crit_idx: int) -> str:
    """Build expander title for a criterion."""
    flags = criterion.get("flags") or {}
    title = ""

    # Try explicit name first
    name = criterion.get("display_name") or criterion.get("name")
    if name:
        title = f"{crit_idx + 1}. {name}"
    # Infer from content
    elif (value_sets := resolve_value_sets(criterion)):
        title = f"Criterion {crit_idx + 1}: Clinical Codes"
    # Check for demographics flags
    elif flags.get("is_patient_demographics") or flags.get("demographics_type"):
        title = f"Criterion {crit_idx + 1}: Demographics"
    else:
        # Check column filters for demographic columns
        column_filters = criterion.get("column_filters") or []
        demographic_cols = {"DOB", "AGE", "AGE_AT_EVENT", "SEX", "PATIENT"}
        for col_filter in column_filters:
            col_name = col_filter.get("column_name") or ""
            col_name_upper = str(col_name).upper().strip()
            if col_name_upper in demographic_cols or "AGE" in col_name_upper or "DOB" in col_name_upper:
                title = f"Criterion {crit_idx + 1}: Demographics"
                break

        # Fallback if still no title
        if not title:
            title = f"Criterion {crit_idx + 1}"

    return title


def _render_criterion_metadata(criterion: Dict) -> None:
    """Render core metadata for a criterion."""
    table_name = criterion.get("table_name") or criterion.get("logical_table_name")
    column_name = criterion.get("column") or criterion.get("column_name")
    container = (criterion.get("flags") or {}).get("container_type")
    if table_name:
        st.caption(f"Table: {table_name}")
    if column_name:
        st.caption(f"Column: {column_name}")

    flags = criterion.get("flags") or {}

    # Demographics / EMISINTERNAL flags surfaced from pattern plugins
    if flags.get("is_patient_demographics") or flags.get("demographics_type"):
        demo_label = flags.get("demographics_type") or "Patient demographics"
        st.caption(f"Demographics: {demo_label}")
    if flags.get("has_emisinternal_filters"):
        pass

    action_true = format_action_indicator(flags.get("action_if_true"))
    action_false = format_action_indicator(flags.get("action_if_false"))
    if action_true or action_false:
        _render_actions(action_true, action_false)

    notes = criterion.get("notes") or flags.get("notes")
    if notes:
        st.caption(f"Notes: {notes}")


def _find_child_criterion(parent: Dict, child_column: str) -> Optional[Dict]:
    """Locate a child criterion within the same group by column name."""
    if not child_column:
        return None
    group_criteria = parent.get("_group_criteria") or []
    for candidate in group_criteria:
        column_name = _normalise_column_name(candidate.get("column") or candidate.get("column_name"))
        if column_name and column_name == child_column:
            return candidate
    return None


def _render_actions(action_true: str, action_false: str) -> None:
    """Render action indicators for group branching."""
    parts = []
    if action_true:
        parts.append(f"If true: {action_true}")
    if action_false:
        parts.append(f"If false: {action_false}")
    if parts:
        st.caption(" | ".join(parts))


def _render_population_references(population_refs: List[Dict], id_to_name: Dict, all_searches: List[Dict], operator: str = "AND") -> None:
    """Render linked population references in blue info boxes with operator dividers."""
    if not population_refs:
        return

    from ...theme import ThemeColours, create_info_box_style

    seen_guids = set()
    rendered_count = 0

    for ref in population_refs:
        ref_guid = ref.get("report_guid") or ref.get("guid") or ref.get("id")

        # Skip duplicates
        if ref_guid in seen_guids:
            continue
        seen_guids.add(ref_guid)

        label = format_population_reference(ref_guid, id_to_name, all_searches)
        if label:
            # Show operator divider between references (but not before first one)
            if rendered_count > 0:
                st.markdown(
                    f"<div style='text-align: center; margin: 4px 0 16px 0; color: #666; font-weight: bold;'>─── <code>{operator.upper()}</code> ───</div>",
                    unsafe_allow_html=True,
                )

            rendered_count += 1

            # Check if this reference has a weight (SCORE groups)
            weight = ref.get("score_weightage", "")

            if weight:
                # Render as two columns: search reference + weight
                col1, col2 = st.columns([7, 1])
                with col1:
                    st.markdown(
                        create_info_box_style(
                            ThemeColours.BLUE,
                            f"🔗 <strong>Using Another Search:</strong> {label}",
                        ),
                        unsafe_allow_html=True,
                    )
                with col2:
                    st.markdown(
                        create_info_box_style(
                            ThemeColours.PURPLE,
                            f"<strong>Score</strong> is set to <strong>{weight}</strong>",
                        ),
                        unsafe_allow_html=True,
                    )
            else:
                # No weight - render full-width blue box
                st.markdown(
                    create_info_box_style(
                        ThemeColours.BLUE,
                        f"🔗 <strong>Using Another Search:</strong> {label}",
                    ),
                    unsafe_allow_html=True,
                )


def _render_restrictions(restrictions: List[Any]) -> None:
    """Render restriction notes."""
    if not restrictions:
        return
    st.markdown("**🎯 Restrictions:**")
    friendly = describe_restrictions(restrictions)
    for restr in friendly:
        st.caption(f"⚙️ {restr}")


def _render_criterion_badges(main_value_sets: List[Dict], renderable_filter_count: int, linked_count: int) -> None:
    """Render compact summary badges for a criterion."""
    parts = []
    if main_value_sets:
        parts.append(f"{len(main_value_sets)} value set(s)")
    if renderable_filter_count:
        parts.append(f"{renderable_filter_count} filter(s)")
    if linked_count:
        parts.append(f"{linked_count} linked")
    if parts:
        st.caption(" | ".join(parts))


def _count_renderable_filters(criterion: Dict) -> int:
    """Count filters that would actually be rendered (excluding redundant code filters)."""
    column_filters = filter_linked_column_filters_from_main(criterion)
    value_sets = filter_linked_value_sets_from_main(criterion)

    count = 0
    seen_keys = set()
    for column_filter in column_filters:
        column_name_raw = column_filter.get("column_name") or ""
        column_name_norm = _normalise_column_name(column_name_raw)
        filter_type = (column_filter.get("filter_type") or "").lower()
        key = (filter_type, column_name_norm, str(column_filter.get("range_info")))

        if key in seen_keys:
            continue
        seen_keys.add(key)

        # Skip redundant clinical code filters already represented by value sets
        if filter_type in {"readcode", "drugcode"} and _code_matches_for_column(column_name_norm, value_sets) > 0:
            continue

        count += 1
    return count


def _render_group_summary(group: Dict) -> None:
    """Render a high-level summary for a criteria group."""
    criteria = group.get("criteria") or []
    value_set_count = sum(len(filter_linked_value_sets_from_main(c) or []) for c in criteria)
    filter_count = sum(_count_renderable_filters(c) for c in criteria)
    linked_count = sum(len((c.get("flags") or {}).get("linked_criteria") or []) for c in criteria)

    bits = [
        f"{len(criteria)} criterion/criteria",
        f"{value_set_count} value set(s)",
        f"{filter_count} filter(s)",
    ]
    if linked_count:
        bits.append(f"{linked_count} linked")
    if bits:
        st.caption("Summary: " + " | ".join(bits))
    else:
        st.caption("Summary: No criteria detected.")


def _code_matches_for_column(column_name_norm: str, clinical_value_sets: List[Dict]) -> int:
    """Count codes in value sets for the given column."""
    code_matches = 0
    for vs in clinical_value_sets or []:
        vs_column = vs.get("column_name") or vs.get("column")

        # Handle column as list
        match = False
        if isinstance(vs_column, list):
            match = column_name_norm in [_normalise_column_name(c) for c in vs_column]
        else:
            match = _normalise_column_name(vs_column) == column_name_norm

        if match:
            codes = vs.get("codes") or []
            # Handle single code at value set level
            if not codes and vs.get("code_value"):
                codes = [vs]
            code_matches += len(codes)
    return code_matches


def render_criteria_group(group: Dict, group_idx: int, search: Dict, id_to_name: Dict):
    """
    Render a criteria group with EMIS-style formatting.
    """
    if not group:
        return

    group_flags = group.get("group_flags") or {}
    operator = group_flags.get("operator") or group.get("operator") or group_flags.get("member_operator") or "AND"

    # Action indicators in 2-column layout (EMIS standard format)
    # Only 3 valid actions: SELECT, REJECT, NEXT
    col1, col2 = st.columns(2)
    with col1:
        action_if_true = (group_flags.get("action_if_true") or "SELECT").upper()
        if action_if_true == "SELECT":
            action_colour = "🟢"
            action_text = "Include in final result"
        elif action_if_true == "NEXT":
            action_colour = "🔀"
            action_text = "Goto next rule"
        elif action_if_true == "REJECT":
            action_colour = "🔴"
            action_text = "Exclude from final result"
        else:
            # Invalid action - this shouldn't happen in valid EMIS XML
            action_colour = "⚠️"
            action_text = f"ERROR: Invalid action '{action_if_true}'"
        st.markdown(f"{action_colour} If rule passed: **{action_text}**")

    with col2:
        action_if_false = (group_flags.get("action_if_false") or "REJECT").upper()
        if action_if_false == "SELECT":
            action_colour = "🟢"
            action_text = "Include in final result"
        elif action_if_false == "NEXT":
            action_colour = "🔀"
            action_text = "Goto next rule"
        elif action_if_false == "REJECT":
            action_colour = "🔴"
            action_text = "Exclude from final result"
        else:
            # Invalid action - this shouldn't happen in valid EMIS XML
            action_colour = "⚠️"
            action_text = f"ERROR: Invalid action '{action_if_false}'"
        st.markdown(f"{action_colour} If rule failed: **{action_text}**")

    # Show SCORE threshold if this is a SCORE-based group
    if operator.upper() == "SCORE":
        score_range = group_flags.get("score_range", {})
        if score_range:
            from ...theme import ThemeColours, create_info_box_style
            min_score = score_range.get("min_score", "")
            operator_sym = score_range.get("operator", "GTEQ")

            # Map operator to EMIS-style text
            op_display = {
                "GTEQ": "Greater than or equal to",
                "GT": "Greater than",
                "LTEQ": "Less than or equal to",
                "LT": "Less than",
                "EQ": "Equal to",
            }.get(operator_sym.upper(), operator_sym)

            threshold_text = f"Only include patients who occur in <strong>{op_display.lower()} {min_score}</strong> of the following:"
            st.markdown(
                create_info_box_style(ThemeColours.PURPLE, threshold_text),
                unsafe_allow_html=True,
            )

    population_refs = group.get("population_criteria") or []
    all_searches = search.get("all_searches") or []
    _render_population_references(population_refs, id_to_name, all_searches, operator)

    criteria = group.get("criteria") or []
    top_level = filter_top_level_criteria(group)
    has_linked = has_linked_criteria(group)
    if has_linked:
        st.caption("Linked criteria detected; child items are shown under their parent rule.")

    # Check if there are any clinical code criteria (value sets with EMIS GUIDs)
    has_clinical_codes = any(resolve_value_sets(crit) for crit in criteria)

    if operator.upper() == "SCORE" and population_refs and (top_level or has_clinical_codes):
        st.markdown(
            "<div style='text-align: center; margin: 4px 0 16px 0; color: #666; font-weight: bold;'>"
            "─── <code>SCORE</code> ───</div>",
            unsafe_allow_html=True,
        )

    # Only show "no criteria" message if there are truly no criteria to display
    # (no top-level criteria, no clinical codes, and no population references)
    if not top_level and not has_clinical_codes and not population_refs:
        from ...theme import ThemeColours, create_info_box_style
        st.markdown(
            create_info_box_style(
                ThemeColours.AMBER,
                "No standalone criteria to display in this group.",
            ),
            unsafe_allow_html=True,
        )
        return

    for idx, criterion in enumerate(top_level):
        criterion["_group_criteria"] = criteria
        render_criterion_detail(
            criterion,
            idx,
            search.get("name") or "Search",
            search.get("id"),
            group_idx,
        )

        # Add operator divider between criteria (not after the last one)
        if idx < len(top_level) - 1:
            st.markdown(
                f"<div style='text-align: center; margin: 4px 0 16px 0; color: #666; font-weight: bold;'>─── <code>{operator.upper()}</code> ───</div>",
                unsafe_allow_html=True,
            )


def _render_consolidated_lsoa(criterion: Dict, flags: Dict[str, Any]) -> None:
    """Render consolidated LSOA codes in a code block with filter beneath."""
    lsoa_codes = flags.get("consolidated_lsoa_codes", [])
    count = flags.get("consolidated_count", len(lsoa_codes))

    # Show table and action
    col1, col2 = st.columns(2)
    with col1:
        table = flags.get("logical_table_name") or criterion.get("table") or "Unknown"
        st.markdown(f"**Table:** `{table}`")
    with col2:
        negation_text = "🚫 Not" if flags.get("negation") else "✅ Include"
        st.markdown(f"**Action:** {negation_text}")

    # Render all codes in an expandable demographics frame
    total_lsoa = len(lsoa_codes)
    if lsoa_codes:
        with st.expander(f"Demographics ({total_lsoa})", expanded=False):
            # Show consolidated code count inside expander
            from ...theme import ThemeColours, create_info_box_style
            st.markdown(
                create_info_box_style(
                    ThemeColours.BLUE,
                    f"Consolidated {count} LSOA criteria into unified output",
                ),
                unsafe_allow_html=True,
            )
            codes_text = "\n".join(lsoa_codes)
            st.code(codes_text, language="text")

    # Show filter beneath
    st.markdown("**⚙️ Filters:**")
    column_display = flags.get("column_display_name") or "Lower Layer Area"
    st.caption(f"• {column_display} filter (demographics)")


def render_criterion_detail(
    criterion: Dict,
    crit_idx: int,
    search_name: str,
    search_id: Optional[str],
    group_idx: int,
):
    """
    Render an individual criterion with detailed context.
    """
    if not criterion:
        return

    flags = criterion.get("flags") or {}
    expanded_state = get_criteria_expanded(search_id or "", group_idx, crit_idx)

    with st.expander(_criterion_title(criterion, crit_idx), expanded=expanded_state):
        # Handle consolidated LSOA criteria specially
        if flags.get("is_consolidated") and flags.get("consolidated_lsoa_codes"):
            _render_consolidated_lsoa(criterion, flags)
            return

        # Show table, action, and score (if present) in columns
        weight = flags.get("score_weightage", "")
        if weight:
            col1, col2, col3 = st.columns([3.5, 3.5, 1])
        else:
            col1, col2 = st.columns(2)

        with col1:
            table = flags.get("logical_table_name") or criterion.get("table") or "Unknown"
            st.markdown(f"**Table:** `{table}`")
        with col2:
            negation_text = "🚫 Not" if flags.get("negation") else "✅ Include"
            st.markdown(f"**Action:** {negation_text}")
            if flags.get("exception_code"):
                st.markdown(f"**EMIS Internal Flag:** `{flags.get('exception_code')}`")
        if weight:
            with col3:
                from ...theme import ThemeColours, create_info_box_style
                st.markdown(
                    create_info_box_style(
                        ThemeColours.PURPLE,
                        f"<strong>Score</strong> is set to <strong>{weight}</strong>",
                    ),
                    unsafe_allow_html=True,
                )

        if flags.get("has_parameter"):
            st.write("⚠️ This criterion contains parameters")
            params = criterion.get("parameters") or flags.get("parameter_names") or []
            if params:
                # Determine scope for display
                scope_bits = []
                if flags.get("has_global_parameters"):
                    scope_bits.append("Global")
                if flags.get("has_local_parameters"):
                    scope_bits.append("Local")
                scope_text = " & ".join(scope_bits) if scope_bits else "Unknown"

                # Build formatted parameter strings with scope
                param_strings = []
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
                        p_scope = " & ".join(p_scope_bits) if p_scope_bits else scope_text
                        param_str = f"[Name: {name}, Scope: {p_scope}]"
                    else:
                        name = str(p)
                        param_str = f"[Name: {name}, Scope: {scope_text}]"

                    # Deduplicate
                    if param_str not in seen:
                        param_strings.append(param_str)
                        seen.add(param_str)

                st.caption("Parameters: " + ", ".join(param_strings))

        main_value_sets = filter_linked_value_sets_from_main(criterion)
        if main_value_sets:
            st.markdown("**🔍 Clinical Codes:**")
        render_value_sets(main_value_sets, criterion.get("display_name") or search_name)
        if not main_value_sets:
            st.caption("No clinical codes attached to this criterion.")

        column_filters = filter_linked_column_filters_from_main(criterion)
        render_column_filters(column_filters, main_value_sets, flags)
        if not column_filters:
            st.caption("No column filters for this criterion.")

        # Build restrictions from flags data
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
            _render_restrictions(restrictions)

        if flags.get("linked_criteria") or criterion.get("linked_criteria"):
            render_linked_criteria(criterion, criterion.get("display_name") or search_name)

    # Persist the last known expanded state (Streamlit expander does not expose state without a key)
    set_criteria_expanded(search_id or "", group_idx, crit_idx, expanded_state)


def _render_value_set_metadata(vs: Dict) -> None:
    """Render metadata for a value set."""
    column_name = vs.get("column_name") or vs.get("column")
    scope = vs.get("scope") or ""
    source = vs.get("source") or ""
    code_system = vs.get("code_system") or ""
    vs_guid = vs.get("valueSet_guid") or vs.get("id") or ""
    meta_bits = []
    if column_name:
        meta_bits.append(f"Column: {column_name}")
    if source:
        meta_bits.append(f"Source: {source}")
    if scope:
        meta_bits.append(f"Scope: {scope}")
    if code_system:
        meta_bits.append(f"System: {_code_system_label(code_system)}")
    if vs_guid:
        meta_bits.append(f"Value set ID: {vs_guid}")
    if meta_bits:
        st.caption(" | ".join(meta_bits))


def _render_value_set_codes(vs: Dict, codes: List[Dict], codes_cache: Dict, source: str) -> None:
    """Render codes table for a single value set."""
    code_system = vs.get("code_system") or ""
    is_library = source.lower() == "library" or code_system.upper() == "LIBRARY_ITEM"

    # System and ID inside expander
    system_display = _code_system_label(code_system)
    if system_display:
        st.caption(f"**System:** {system_display}")
    vs_id = vs.get("valueSet_guid") or vs.get("id") or ""
    if vs_id:
        st.caption(f"**ID:** {vs_id}")

    # Build rows
    rows: List[Dict[str, Any]] = []
    for code in codes:
        emis_guid = code.get("EMIS GUID") or code.get("emis_guid") or code.get("code_value") or ""
        cached_code = codes_cache.get(emis_guid, {})

        is_library_item = code.get("is_library_item") or cached_code.get("is_library_item") or is_library
        is_refset = code.get("is_refset") or cached_code.get("is_refset") or False
        include_children = code.get("include_children") or cached_code.get("include_children") or False

        if cached_code:
            vs_name = cached_code.get("ValueSet Description") or cached_code.get("value_set_description") or ""
            snomed_term = cached_code.get("SNOMED Description") or cached_code.get("snomed_description") or ""
            snomed_code = cached_code.get("SNOMED Code") or cached_code.get("snomed_code") or emis_guid or ""
        else:
            vs_name = code.get("Display Name") or code.get("xml_display_name") or code.get("display_name") or ""
            snomed_term = ""
            snomed_code = emis_guid or ""

        if is_library_item:
            scope = "📚 Library"
            description = vs_name
        elif is_refset:
            scope = "🎯 Refset"
            description = vs_name
        else:
            description = snomed_term if snomed_term else vs_name
            scope = "👪 + Children" if include_children else "🎯 Exact"

        rows.append({
            "EMIS Code": emis_guid,
            "SNOMED Code": snomed_code,
            "Description": description,
            "Scope": scope,
            "Is Refset": "Yes" if is_refset else "No",
        })

    df = pd.DataFrame(rows, columns=["EMIS Code", "SNOMED Code", "Description", "Scope", "Is Refset"])
    st.markdown("""<style>[data-testid="stElementToolbar"]{display: none;}</style>""", unsafe_allow_html=True)
    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "EMIS Code": st.column_config.TextColumn("🔍 EMIS Code", width="medium"),
            "SNOMED Code": st.column_config.TextColumn("⚕️ SNOMED Code", width="medium"),
            "Description": st.column_config.TextColumn("📝 Description", width="large"),
            "Scope": st.column_config.TextColumn("🔗 Scope", width="small"),
            "Is Refset": st.column_config.TextColumn("🎯 Refset", width="small"),
        }
    )


def _render_combined_unnamed_codes(code_tuples: List[tuple], codes_cache: Dict) -> None:
    """Render all unnamed value set codes in a single table."""
    rows: List[Dict[str, Any]] = []

    for code, vs, is_library in code_tuples:
        emis_guid = code.get("EMIS GUID") or code.get("emis_guid") or code.get("code_value") or ""
        cached_code = codes_cache.get(emis_guid, {})

        is_library_item = code.get("is_library_item") or cached_code.get("is_library_item") or is_library
        is_refset = code.get("is_refset") or cached_code.get("is_refset") or False
        include_children = code.get("include_children") or cached_code.get("include_children") or False

        if cached_code:
            vs_name = cached_code.get("ValueSet Description") or cached_code.get("value_set_description") or ""
            snomed_term = cached_code.get("SNOMED Description") or cached_code.get("snomed_description") or ""
            snomed_code = cached_code.get("SNOMED Code") or cached_code.get("snomed_code") or emis_guid or ""
        else:
            vs_name = code.get("Display Name") or code.get("xml_display_name") or code.get("display_name") or ""
            snomed_term = ""
            snomed_code = emis_guid or ""

        if is_library_item:
            scope = "📚 Library"
            description = vs_name
        elif is_refset:
            scope = "🎯 Refset"
            description = vs_name
        else:
            description = snomed_term if snomed_term else vs_name
            scope = "👪 + Children" if include_children else "🎯 Exact"

        rows.append({
            "EMIS Code": emis_guid,
            "SNOMED Code": snomed_code,
            "Description": description,
            "Scope": scope,
            "Is Refset": "Yes" if is_refset else "No",
        })

    df = pd.DataFrame(rows, columns=["EMIS Code", "SNOMED Code", "Description", "Scope", "Is Refset"])
    st.markdown("""<style>[data-testid="stElementToolbar"]{display: none;}</style>""", unsafe_allow_html=True)
    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "EMIS Code": st.column_config.TextColumn("🔍 EMIS Code", width="medium"),
            "SNOMED Code": st.column_config.TextColumn("⚕️ SNOMED Code", width="medium"),
            "Description": st.column_config.TextColumn("📝 Description", width="large"),
            "Scope": st.column_config.TextColumn("🔗 Scope", width="small"),
            "Is Refset": st.column_config.TextColumn("🎯 Refset", width="small"),
        }
    )


def render_value_sets(value_sets: List[Dict], criterion_name: str):
    """
    Render clinical code value sets in a single expandable table.
    All codes shown together regardless of value set names.
    Library items are shown in amber info boxes.
    """
    if not value_sets:
        return

    codes_cache = _get_clinical_codes_cache()

    # Collect all codes and library items
    unnamed_codes_all = []  # All codes from all value sets
    library_items = []  # List of library item IDs
    is_medication_any = False

    for vs in value_sets:
        code_system = str(vs.get("code_system") or "").upper()
        if code_system == "EMISINTERNAL":
            continue

        # Check if this is a library item
        source = (vs.get("source") or "").lower()
        is_library = source == "library" or code_system == "LIBRARY_ITEM"
        library_item_id = vs.get("library_item") or vs.get("libraryItem") or vs.get("library_item_id")

        if is_library or library_item_id:
            # This is a library item - collect for separate display
            # Try multiple fields to extract the library item ID
            lib_id = (
                library_item_id
                or vs.get("code_value")
                or vs.get("valueSet_guid")
                or vs.get("valueSetGuid")
                or vs.get("id")
            )

            # If still no ID, try to get it from the first code
            if not lib_id:
                codes = vs.get("codes") or []
                if codes:
                    lib_id = codes[0].get("EMIS GUID") or codes[0].get("emis_guid") or codes[0].get("code_value")

            library_items.append(lib_id or "Unknown")
            continue

        # Get codes
        codes = vs.get("codes") or []
        if not codes and vs.get("code_value"):
            codes = [vs]

        if not codes:
            continue

        # Determine if medication
        is_medication = "DRUG" in code_system or vs.get("is_medication")
        if is_medication:
            is_medication_any = True

        # Add all codes to the combined list
        for code in codes:
            unnamed_codes_all.append((code, vs, False))

    # Render library items in amber info boxes
    if library_items:
        from ...theme import ThemeColours, create_info_box_style
        for lib_id in library_items:
            st.markdown(
                create_info_box_style(
                    ThemeColours.AMBER,
                    f"📚 <strong>Library Item:</strong> {lib_id}",
                ),
                unsafe_allow_html=True,
            )

    # Render all codes together in a single table
    if unnamed_codes_all:
        total_codes = len(unnamed_codes_all)
        code_word = "Code" if total_codes == 1 else "Codes"
        title = "Medication Codes" if is_medication_any else "Clinical Codes"
        with st.expander(f"📋 {title} ({total_codes} {code_word})", expanded=False):
            _render_combined_unnamed_codes(unnamed_codes_all, codes_cache)


def render_column_filters(column_filters: List[Dict], clinical_value_sets: List[Dict], criterion_flags: Dict[str, Any]):
    """
    Render column filters with user-friendly descriptions.
    """
    if not column_filters:
        return
    header_shown = False
    rendered_any = False
    seen_keys = set()

    # Count total clinical codes across all value sets
    total_codes = sum(len(vs.get("codes") or []) + (1 if vs.get("code_value") else 0) for vs in clinical_value_sets or [])

    # Group filters by type to keep related filters together
    # Priority order: age, date, numeric, other
    type_priority = {"age": 0, "date": 1, "numeric": 2}
    sorted_filters = sorted(
        column_filters,
        key=lambda f: (type_priority.get((f.get("filter_type") or "").lower(), 99), f.get("column_name", ""))
    )

    seen_descriptions = set()
    seen_extras = set()
    for column_filter in sorted_filters:
        column_name_raw = column_filter.get("column_name") or ""
        column_name_norm = _normalise_column_name(column_name_raw)
        column_display_raw = column_filter.get("column_display") or column_name_raw or "Filter"
        # Clean column names using the centralised mapper (e.g., ISSUE_DATE -> Date of Issue)
        column_display = get_column_display_name(column_display_raw)
        filter_type = (column_filter.get("filter_type") or "").lower()
        key = (filter_type, column_name_norm, str(column_filter.get("range_info")))
        if key in seen_keys:
            continue
        seen_keys.add(key)

        description = _build_filter_description(
            column_filter,
            column_display,
            column_name_raw,
            column_name_norm,
            filter_type,
            clinical_value_sets,
            criterion_flags,
        )

        # Skip redundant clinical code filters already represented by value sets
        code_columns = {"CODE", "CLINICAL_CODE", "READ_CODE", "READCODE", "DRUGCODE", "DRUG_CODE"}
        is_code_column = filter_type in {"readcode", "drugcode"} or column_name_norm in code_columns
        # If it's a code column and there are ANY value sets, skip (even if column matching fails for library items)
        if is_code_column and (clinical_value_sets and len(clinical_value_sets) > 0):
            continue

        if description and description not in seen_descriptions:
            seen_descriptions.add(description)
            if not header_shown:
                st.markdown("**⚙️ Filters:**")
                header_shown = True
                # Show clinical codes summary first
                if total_codes > 0:
                    st.caption(f"• Include {total_codes} specified clinical codes")
                    rendered_any = True
            st.caption(f"• {description}")
            rendered_any = True
            multi_cols = criterion_flags.get("emisinternal_entries") or []
            if multi_cols:
                for entry in multi_cols:
                    if entry.get("column") and _normalise_column_name(entry.get("column")) == column_name_norm:
                        extras = []
                        seen_columns = set()
                        column_display_text = str(column_display or "").lower()
                        for col in entry.get("multi_columns") or []:
                            if not col or col == entry.get("column") or col in seen_columns:
                                continue
                            if col == _normalise_column_name(column_name_raw):
                                continue
                            display_name = get_column_display_name(col) or col
                            if display_name and str(display_name).lower() in column_display_text:
                                continue
                            if str(display_name).strip().upper() == str(col).strip().upper():
                                continue
                            seen_columns.add(col)
                            extras.append(display_name)
                        if extras:
                            key = (column_name_norm, tuple(extras))
                            if key not in seen_extras:
                                seen_extras.add(key)
                                st.caption(f"Additional columns: {', '.join(extras)}")
                rendered_any = True
    if not rendered_any and not header_shown:
        st.caption("No column filters for this criterion.")


def _build_filter_description(
    column_filter: Dict,
    column_display: str,
    column_name_raw: str,
    column_name_norm: str,
    filter_type: str,
    clinical_value_sets: List[Dict],
    criterion_flags: Dict[str, Any],
) -> str:
    """Build a descriptive string for a column filter."""
    range_info = column_filter.get("range_info") or {}

    emisinternal_value_sets = [
        vs for vs in (column_filter.get("value_sets") or []) if str(vs.get("code_system") or "").upper() == "EMISINTERNAL"
    ]

    if filter_type == "age":
        return describe_age_filter(range_info, column_name_raw)
    if filter_type == "date":
        return describe_date_filter(range_info, column_display, column_name_raw, column_filter.get("relative_to"))
    if filter_type == "numeric":
        return describe_numeric_filter(range_info)
    if filter_type == "emisinternal" or emisinternal_value_sets or criterion_flags.get("has_emisinternal_filters"):
        # Try to use enriched entries from pattern flags for this column
        entries = criterion_flags.get("emisinternal_entries") or []
        matching_entry = next(
            (
                e
                for e in entries
                if _normalise_column_name(e.get("column")) == column_name_norm or not e.get("column")
            ),
            None,
        )
        if matching_entry:
            values = matching_entry.get("values") or []
            if values:
                # Values are now dicts with 'value' and 'displayName' keys
                vs_like = [{"values": values}]
                in_not_in = str(matching_entry.get("in_not_in", "")).upper()
                desc = describe_emisinternal_filter(column_display or column_name_raw, vs_like, in_not_in=in_not_in)
                if matching_entry.get("has_all_values"):
                    return f"{desc} (all values)"
                return desc
        return describe_emisinternal_filter(
            column_display or column_name_raw, emisinternal_value_sets or column_filter.get("value_sets") or [], column_filter.get("in_not_in", "")
        )
    if filter_type in {"readcode", "drugcode"}:
        code_matches = 0
        for vs in clinical_value_sets or []:
            code_column = _normalise_column_name(vs.get("column_name") or vs.get("column"))
            if code_column and code_column == column_name_norm:
                code_matches += len(vs.get("codes") or [])
        return f"{column_display} matches {code_matches} clinical codes"
    demographic_cols = {"AGE", "AGE_AT_EVENT", "SEX", "PATIENT", "DOB"}
    is_lsoa = criterion_flags.get("demographics_type") == "LSOA" or "_LOWER_AREA_" in column_name_norm
    is_demographics_flag = criterion_flags.get("is_patient_demographics") or criterion_flags.get("demographics_type")
    if column_name_norm in demographic_cols or is_lsoa or is_demographics_flag:
        return f"{column_display} filter (demographics)"
    # Fallback for date-like columns without explicit type
    if not filter_type and range_info and ("DATE" in column_name_norm or "DOB" in column_name_norm):
        return describe_date_filter(range_info, column_display, column_name_raw, column_filter.get("relative_to"))
    return f"{column_display} filter"


def _render_linked_child_details(child: Dict, child_label: str) -> None:
    """Render details for a linked child criterion."""
    _render_criterion_metadata(child)
    # For linked children, show ALL their value sets and filters (don't filter out nested linked criteria)
    child_value_sets = resolve_value_sets(child)
    render_value_sets(child_value_sets, child_label)
    child_filters = child.get("column_filters") or []
    render_column_filters(child_filters, child_value_sets, child.get("flags") or {})


def render_linked_criteria(criterion: Dict, parent_name: str):
    """
    Render linked criteria with purple info bar and rich details below.
    """
    # Get full linked criteria data (includes both relationship and criterion)
    full_linked_list = criterion.get("linked_criteria") or []
    if not full_linked_list:
        return

    from ...theme import ThemeColours, create_info_box_style

    for linked_item in full_linked_list:
        # linked_item has structure: {"relationship": {...}, "criterion": {...}}
        relationship = linked_item.get("relationship") or {}
        child = linked_item.get("criterion")

        # Build descriptive title for the linked feature
        parent_col_display = relationship.get("parent_column_display_name") or relationship.get("parent_column") or "the field"
        child_col_display = relationship.get("child_column_display_name") or relationship.get("child_column") or "the linked field"

        # Get temporal description
        temporal_desc = get_temporal_relationship_description(relationship)
        if temporal_desc:
            # Extract just the relationship part (e.g., "more than or equal to 1 years after")
            title = f"🔗 <strong>Linked Feature:</strong> {parent_col_display} is {temporal_desc} {child_col_display} from the above feature and where:"
        else:
            title = (
                "🔗 <strong>Linked Feature:</strong> "
                f"{parent_col_display} is equal to the {child_col_display} from the above feature and where:"
            )

        # Purple info bar with relationship description
        st.markdown(
            create_info_box_style(ThemeColours.PURPLE, title),
            unsafe_allow_html=True
        )

        # Bordered frame with linked criterion details
        with st.container(border=True):
            if child:
                child_flags = child.get("flags") or {}
                child_label = child_flags.get("display_name") or child.get("display_name") or relationship.get("child_column") or "Linked Criterion"
                _render_linked_child_details(child, child_label)
            else:
                # Fallback if no criterion data
                child_column = relationship.get("child_column") or "Linked Criterion"
                st.write(f"No details available for: {child_column}")
