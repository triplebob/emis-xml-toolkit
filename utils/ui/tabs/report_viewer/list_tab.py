"""
List report viewer tab.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from .common import (
    render_report_selector,
    render_report_metadata,
    render_report_export_controls,
    render_criteria_list,
    get_enriched_snomed_lookup,
    render_report_status_box,
)
from ...theme import ThemeColours, create_info_box_style
from ....metadata.report_filtering import (
    build_report_filter_items,
    describe_group_criteria,
    split_report_value_sets,
)
from ..search_browser.search_criteria_viewer import render_linked_criteria


def _code_system_label(code_system: str) -> str:
    if not code_system:
        return ""
    key = str(code_system).upper()
    if "SCT" in key or "SNOMED" in key:
        return "SNOMED CT"
    if "DRUG" in key:
        return "Drug code"
    if "EMISINTERNAL" in key:
        return "EMIS Internal Classification"
    if "LIBRARY" in key:
        return "EMIS Library Item"
    return code_system


def _lookup_snomed(emis_guid: str) -> str:
    """Look up SNOMED code from pre-enriched pipeline data (no heavy dictionary building)."""
    if not emis_guid:
        return ""
    lookup = get_enriched_snomed_lookup()
    return lookup.get(emis_guid, "")


def _build_codes_table_rows(value_sets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for entry in value_sets:
        emis_guid = entry.get("code_value") or entry.get("EMIS GUID") or entry.get("emis_guid") or ""
        is_refset = bool(entry.get("is_refset"))
        is_library_item = bool(entry.get("is_library_item"))
        include_children = bool(entry.get("include_children"))
        snomed_code = emis_guid if is_refset or is_library_item else _lookup_snomed(emis_guid) or emis_guid
        if is_library_item:
            scope = "📚 Library"
        elif is_refset:
            scope = "🎯 Refset"
        else:
            scope = "👪 + Children" if include_children else "🎯 Exact"
        rows.append(
            {
                "EMIS Code": emis_guid,
                "SNOMED Code": snomed_code,
                "Description": entry.get("display_name") or entry.get("valueSet_description") or "",
                "Scope": scope,
                "Refset": "Yes" if is_refset else "No",
            }
        )
    return rows


def _render_group_criteria(
    criteria: List[Dict[str, Any]],
) -> None:
    if not criteria:
        return

    count = len(criteria)
    col1, col2 = st.columns([0.8, 3])
    with col1:
        st.markdown(
            create_info_box_style(
                ThemeColours.PURPLE,
                "🔍 <strong>Column Group Criteria:</strong>",
            ),
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            create_info_box_style(
                ThemeColours.BLUE,
                describe_group_criteria(criteria),
            ),
            unsafe_allow_html=True,
        )

    for idx, criterion in enumerate(criteria, start=1):
        flags = criterion.get("flags") or {}
        if count > 1:
            name = flags.get("display_name") or f"Criterion {idx}"
            st.markdown(f"**Criterion {idx}: {name}**")

        negation = flags.get("negation")
        action_text = "✅ Include" if negation is not True else "❌ Exclude"
        st.markdown(f"Action: {action_text}")

        clinical_value_sets, emisinternal_value_sets = split_report_value_sets(criterion)
        code_count = len(clinical_value_sets)
        if code_count:
            label = "Code" if code_count == 1 else "Codes"
            with st.expander(f"📋 Clinical Codes ({code_count} {label})", expanded=False):
                system_labels = []
                for entry in clinical_value_sets:
                    label_text = _code_system_label(entry.get("code_system") or "")
                    if label_text and label_text not in system_labels:
                        system_labels.append(label_text)
                if system_labels:
                    if len(system_labels) == 1:
                        st.caption(f"**System:** {system_labels[0]}")
                    else:
                        st.caption(f"**System:** {', '.join(system_labels)}")

                rows = _build_codes_table_rows(clinical_value_sets)
                df = pd.DataFrame(rows, columns=["EMIS Code", "SNOMED Code", "Description", "Scope", "Refset"])
                st.dataframe(
                    df,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "EMIS Code": st.column_config.TextColumn("🔍 EMIS Code", width="medium"),
                        "SNOMED Code": st.column_config.TextColumn("⚕️ SNOMED Code", width="medium"),
                        "Description": st.column_config.TextColumn("📝 Description", width="large"),
                        "Scope": st.column_config.TextColumn("🔗 Scope", width="small"),
                        "Refset": st.column_config.TextColumn("🎯 Refset", width="small"),
                    },
                )
        elif not emisinternal_value_sets and not flags.get("emisinternal_entries"):
            st.caption("No clinical codes attached to this criterion.")

        filters = build_report_filter_items(criterion, clinical_value_sets, emisinternal_value_sets)
        if filters:
            st.markdown("**⚙️ Filters:**")
            for item in filters:
                st.caption(f"• {item}")

        render_linked_criteria(criterion, flags.get("display_name") or "Criterion")


def render_list_reports_tab(*_args, **_kwargs) -> None:
    @st.fragment
    def _render() -> None:
        selected_report, metadata, status_text = render_report_selector("list", "List Report", "list_report")
        if not selected_report:
            return

        st.markdown("""
            <style>
            div[data-testid="stExpander"] > details > summary {
                min-height: 48px;
                display: flex;
                align-items: center;
                }
            </style>
        """, unsafe_allow_html=True) 
        id_to_name = metadata.get("id_to_name", {})
        status_col1, status_col2 = st.columns([3, 4])
        with status_col1:
            if status_text:
                render_report_status_box(status_text)
        with status_col2:
            render_report_export_controls(selected_report, "list_report_export", id_to_name)

        render_report_metadata(selected_report, id_to_name)

        column_groups = selected_report.get("column_groups") or []
        if not column_groups:
            st.markdown(create_info_box_style(ThemeColours.BLUE, "No column groups found."), unsafe_allow_html=True)
            return

        st.markdown("### 📋 Column Structure")
        for idx, group in enumerate(column_groups, start=1):
            group_name = group.get("display_name") or f"Group {idx}"
            logical_table = group.get("logical_table") or ""
            summary = group.get("criteria_summary") or {}
            summary_label = summary.get("label") if isinstance(summary, dict) else ""

            display_name = f"{summary_label} {group_name}".strip() if summary_label else group_name
            title = f"Group {idx}: {display_name}"
            if logical_table:
                title += f" (Logical Table: {logical_table})"

            with st.expander(title, expanded=False):
                columns = group.get("columns") or []
                if columns:
                    table_rows = []
                    for col in columns:
                        table_rows.append({"Display Name": col.get("display_name") or ""})
                    st.markdown("**📊 Columns:**")
                    st.dataframe(table_rows, hide_index=True, width="stretch")
                else:
                    st.markdown(create_info_box_style(ThemeColours.BLUE, "No columns defined."), unsafe_allow_html=True)

                sort_config = group.get("sort_configuration") or {}
                if sort_config:
                    column_id = sort_config.get("column_id") or ""
                    direction = sort_config.get("direction") or ""
                    if column_id or direction:
                        st.caption(f"Sort: {column_id} {direction}".strip())

                group_criteria = group.get("criteria") or []
                if group_criteria:
                    _render_group_criteria(group_criteria)
                else:
                    st.markdown("Has Criteria: No")

        report_criteria = selected_report.get("report_criteria") or []
        if report_criteria:
            render_criteria_list(report_criteria, "Report Criteria", "list_report")

    _render()
