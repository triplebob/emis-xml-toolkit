"""
Audit report viewer tab.
"""

from __future__ import annotations

from typing import Dict, List
import streamlit as st

from .common import (
    render_report_selector,
    render_report_metadata,
    render_report_export_controls,
    render_report_criteria_blocks,
    render_report_status_box,
)
from ...theme import ThemeColours, create_info_box_style
from ....metadata.report_filtering import build_audit_criteria_overview


def _collect_group_columns(aggregate: Dict) -> List[str]:
    columns: List[str] = []
    for group in aggregate.get("groups") or []:
        display = group.get("display_name") or ""
        if display:
            columns.append(display)
    return columns


def _infer_grouping_type(columns: List[str]) -> str:
    text = " ".join(columns).lower()
    if any(token in text for token in ["practice", "organisation", "organisation", "ccg", "gp"]):
        return "📋 Organisational Grouping"
    if any(token in text for token in ["age", "birth", "dob"]):
        return "Age Group Analysis"
    if any(token in text for token in ["medication", "drug", "prescription"]):
        return "Medication Grouping"
    if any(token in text for token in ["clinical", "diagnosis", "condition", "snomed", "code"]):
        return "Clinical Code Grouping"
    if any(token in text for token in ["gender", "sex"]):
        return "Demographic Grouping"
    if any(token in text for token in ["date", "time", "year", "month"]):
        return "Temporal Grouping"
    return "Data Grouping"


def render_audit_reports_tab(*_args, **_kwargs) -> None:
    @st.fragment
    def _render() -> None:
        selected_report, metadata, status_text = render_report_selector("audit", "Audit Report", "audit_report")
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
            render_report_export_controls(selected_report, "audit_report_export", id_to_name)

        render_report_metadata(selected_report, id_to_name)

        aggregate = selected_report.get("aggregate") or {}
        if aggregate:
            st.markdown("### 📊 Audit Configuration")
            with st.container(border=True):
                col1, col2 = st.columns(2)
                with col1:
                    logical_table = aggregate.get("logical_table") or ""
                    if logical_table:
                        st.caption(f"Logical Table: {logical_table}")
                    result = aggregate.get("result") or {}
                    if result.get("source"):
                        st.caption(f"Result Source: {(result.get('source') or '').replace('_', ' ').title()}")
                    if result.get("calculation_type"):
                        st.caption(f"Calculation Type: {(result.get('calculation_type') or '').replace('_', ' ').title()}")
                with col2:
                    pop_refs = selected_report.get("population_references") or []
                    st.caption(f"Member Searches: {len(pop_refs)}")
                    if selected_report.get("report_criteria"):
                        st.caption("Type: Complex (Additional Criteria)")
                    else:
                        st.caption("Type: Organisational Only")

            group_columns = _collect_group_columns(aggregate)
            if group_columns:
                grouping_type = _infer_grouping_type(group_columns)
                st.markdown(f"### {grouping_type}")
                st.markdown(
                    create_info_box_style(
                        ThemeColours.PURPLE,
                        f"Results grouped by: {', '.join(group_columns)}",
                    ),
                    unsafe_allow_html=True,
                )

        pop_refs = selected_report.get("population_references") or []
        if pop_refs:
            id_to_name = metadata.get("id_to_name", {})
            search_count = len(pop_refs)
            search_label = "search" if search_count == 1 else "searches"
            st.markdown(f"### 🧑‍🤝‍🧑 Member Searches ({search_count} {search_label})")
            st.markdown(
                create_info_box_style(
                    ThemeColours.BLUE,
                    "This Audit Report combines results from the following base searches:",
                ),
                unsafe_allow_html=True,
            )
            with st.expander("📋 View All Member Searches", expanded=False):
                for idx, guid in enumerate(pop_refs, start=1):
                    name = id_to_name.get(guid) or guid
                    st.markdown(
                        create_info_box_style(
                            ThemeColours.BLUE,
                            f"{idx}. {name}",
                        ),
                        unsafe_allow_html=True,
                    )
            st.caption(
                "Each base search defines a patient population. The Audit Report shows aggregated results across all these populations."
            )

        criteria = selected_report.get("report_criteria") or []

        if criteria:
            overview = build_audit_criteria_overview(criteria)
            render_report_criteria_blocks(
                overview.get("criteria") or [],
                selected_report.get("name") or "Report",
                selected_report.get("id"),
                overview.get("title") or "🔍 Additional Report Criteria",
                overview.get("summary") or "",
            )
        else:
            st.markdown("#### ℹ️ Simple Organisational Report")
            st.markdown(
                create_info_box_style(
                    ThemeColours.PURPLE,
                    "This Audit Report performs pure organisational aggregation without additional clinical criteria.",
                ),
                unsafe_allow_html=True,
            )

    _render()
