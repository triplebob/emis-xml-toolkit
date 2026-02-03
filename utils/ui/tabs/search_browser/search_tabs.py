"""
Wrapper for search browser tabs (search-only, pipeline).
"""

import streamlit as st
from .search_common import render_empty_state
from .search_detail_tab import render_search_detail_tab
from ....metadata.structure_provider import get_structure_metadata


def render_search_tabs(*_args, **_kwargs):
    """
    Entry point for search browser tabs.
    """
    metadata = get_structure_metadata()
    searches = metadata.get("searches", [])
    deps = metadata.get("dependencies", {})
    id_to_name = metadata.get("id_to_name", {})
    folders = metadata.get("folders", [])

    if not searches:
        render_empty_state("No searches detected in this XML.")
        return

    # Keep Search Logic as a subtab for future expansion
    (tab1,) = st.tabs(["🔍 Search Logic"])
    with tab1:
        render_search_detail_tab(searches, folders, id_to_name)
