"""
Aggregate report viewer tab.
"""

from __future__ import annotations

from typing import Dict, List
import streamlit as st

from .common import (
    render_report_selector,
    render_report_metadata,
    render_report_export_controls,
    render_report_status_box,
)
from ...theme import ThemeColours, create_info_box_style
from ..search_browser.search_criteria_viewer import render_criterion_detail
from ....metadata.report_filtering import build_aggregate_criteria_groups, has_embedded_report_code_rules


def _collect_group_columns(aggregate: Dict) -> List[str]:
    columns: List[str] = []
    for group in aggregate.get("groups") or []:
        display = group.get("display_name") or ""
        if display:
            columns.append(display)
        for col in group.get("grouping_columns") or []:
            if col:
                columns.append(col)
    return columns


def _format_result_label(result: Dict) -> str:
    calculation = (result.get("calculation_type") or "").strip()
    source = (result.get("source") or "").strip()
    if not calculation and not source:
        return ""
    calculation_label = calculation.replace("_", " ").title() if calculation else "Result"
    source_label = source.replace("_", " ").title() if source else ""
    if source_label.lower() == "record":
        source_label = "Records"
    if source_label:
        return f"Result: {calculation_label} of {source_label}"
    return f"Result: {calculation_label}"


def _render_statistical_configuration(aggregate: Dict) -> None:
    statistical = aggregate.get("statistical_groups") or []
    result = aggregate.get("result") or {}
    if not statistical and not result:
        return

    rows_label = ""
    columns_label = ""
    for item in statistical:
        label = item.get("group_name") or item.get("group_id") or ""
        if not label:
            continue
        if item.get("type") == "rows" and not rows_label:
            rows_label = label
        if item.get("type") == "columns" and not columns_label:
            columns_label = label

    result_label = _format_result_label(result)
    if not rows_label and not columns_label and not result_label:
        return

    with st.container(border=True):
        st.markdown("##### 📈 Statistical Configuration")
        col1, col2, col3 = st.columns(3)
        if rows_label:
            with col1:
                st.markdown(
                    create_info_box_style(ThemeColours.BLUE, f"Rows: {rows_label}"),
                    unsafe_allow_html=True,
                )
        if columns_label:
            with col2:
                st.markdown(
                    create_info_box_style(ThemeColours.BLUE, f"Columns: {columns_label}"),
                    unsafe_allow_html=True,
                )
        if result_label:
            with col3:
                st.markdown(
                    create_info_box_style(ThemeColours.GREEN, result_label),
                    unsafe_allow_html=True,
                )


def _render_built_in_criteria(criteria: List[Dict], report_name: str, report_id: str) -> None:
    groups = build_aggregate_criteria_groups(criteria)
    if not groups:
        return

    for group in groups:
        operator = group.get("operator") or "AND"
        st.markdown(f"#### {group.get('title') or 'Built-in Criteria'}")
        group_criteria = group.get("criteria") or []
        for criterion in group_criteria:
            criterion["_group_criteria"] = group_criteria
        for idx, criterion in enumerate(group_criteria):
            render_criterion_detail(criterion, idx, report_name, report_id, 0)
            if idx < len(group_criteria) - 1:
                st.markdown(
                    f"<div style='text-align: center; margin: 4px 0 16px 0; color: #666; font-weight: bold;'>─── <code>{operator}</code> ───</div>",
                    unsafe_allow_html=True,
                )


def render_aggregate_reports_tab(*_args, **_kwargs) -> None:
    @st.fragment
    def _render() -> None:
        selected_report, metadata, status_text = render_report_selector("aggregate", "Aggregate Report", "aggregate_report")
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
            render_report_export_controls(selected_report, "aggregate_report_export", id_to_name)

        render_report_metadata(selected_report, id_to_name)
        _render_statistical_configuration(selected_report.get("aggregate") or {})

        aggregate = selected_report.get("aggregate") or {}
        if not aggregate:
            st.markdown(create_info_box_style(ThemeColours.BLUE, "No aggregate configuration found."), unsafe_allow_html=True)
            return

        st.markdown("### 📊 Aggregate Configuration")
        logical_table = aggregate.get("logical_table") or ""
        groups = aggregate.get("groups") or []
        if groups:
            title = "Aggregate Groups"
            if logical_table:
                title = f"{title} (Logical Table: {logical_table})"
            with st.expander(title, expanded=True):
                for idx, group in enumerate(groups, start=1):
                    group_title = group.get("display_name") or group.get("id") or f"Group {idx}"
                    with st.expander(f"Group {idx}: {group_title}", expanded=True):
                        grouping_columns = ", ".join(group.get("grouping_columns") or []) or "None"
                        sub_totals = "Yes" if bool(group.get("sub_totals")) else "No"
                        repeat_header = "Yes" if bool(group.get("repeat_header")) else "No"
                        st.markdown(f"Grouping Columns: {grouping_columns}")
                        st.markdown(f"Sub Totals: {sub_totals}")
                        st.markdown(f"Repeat Header: {repeat_header}")

        criteria = selected_report.get("aggregate_criteria") or []
        if criteria:
            st.markdown("### 🔍 Built-in Report Filters")
            if has_embedded_report_code_rules(criteria):
                st.markdown(
                    create_info_box_style(
                        ThemeColours.PURPLE,
                        "This aggregate report has its own built-in criteria that filters the data before aggregation.",
                    ),
                    unsafe_allow_html=True,
                )
            _render_built_in_criteria(criteria, selected_report.get("name") or "Aggregate Report", selected_report.get("id") or "")

    _render()
