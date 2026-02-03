"""
Report tab container for list, audit, and aggregate reports.
"""

from __future__ import annotations

import streamlit as st

from .list_tab import render_list_reports_tab
from .audit_tab import render_audit_reports_tab
from .aggregate_tab import render_aggregate_reports_tab


def render_reports_tab(*_args, **_kwargs) -> None:
    tab_list, tab_audit, tab_aggregate = st.tabs([
        "List Reports",
        "Audit Reports",
        "Aggregate Reports",
    ])

    with tab_list:
        render_list_reports_tab()

    with tab_audit:
        render_audit_reports_tab()

    with tab_aggregate:
        render_aggregate_reports_tab()
