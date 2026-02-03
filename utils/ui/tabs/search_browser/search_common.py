"""
Shared helpers for the search browser tabs (search-only, pipeline).
"""

from typing import List, Dict
import pandas as pd
import streamlit as st
from ...theme import info_box
from ...tab_helpers import (
    natural_sort_key,
    build_folder_groups,
    build_folder_option_list,
)


def build_search_dataframe(searches: List[Dict[str, any]]) -> pd.DataFrame:
    """
    Build a reusable dataframe for search listings.
    """
    rows = []
    for s in searches:
        rows.append(
            {
                "Name": s.get("name") or "",
                "GUID": s.get("id") or "",
                "Folder": " \\ ".join(s.get("folder_path") or []),
                "Parent GUID": s.get("parent_guid") or "",
                "Dependencies": ", ".join(s.get("dependency_names") or []),
                "Dependents": ", ".join(s.get("dependent_names") or []),
                "Criteria Groups": len(s.get("criteria_groups") or []),
                "Description": s.get("description") or "",
            }
        )
    return pd.DataFrame(rows)


def render_empty_state(message: str):
    st.markdown(info_box(message), unsafe_allow_html=True)


def clean_search_name(name: str) -> str:
    """
    Clean search name for display (currently trims whitespace).
    """
    return (name or "").strip()


def sort_searches_by_name(searches: List[Dict]) -> List[Dict]:
    """
    Sort searches using natural sort (numeric-aware).
    """
    return sorted(searches or [], key=lambda s: natural_sort_key(s.get("name") or ""))


def build_folder_hierarchy(folders: List[Dict], searches: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Build folder hierarchy for dropdown navigation.
    """
    folders = folders if isinstance(folders, list) else []
    searches = searches if isinstance(searches, list) else []
    return build_folder_groups(searches, folders, all_label="All Folders inc Root")


def build_folder_options(searches: List[Dict], folders: List[Dict]) -> List[Dict]:
    """
    Build folder options for dropdown with value/label structure.
    Returns list of dicts with 'value' (folder_id) and 'label' (folder name).
    """
    return build_folder_option_list(searches, folders, all_label="All Folders inc Root")


def build_search_options(searches: List[Dict]) -> List[Dict]:
    """
    Build search options for dropdown with value/label structure.
    Returns list of dicts with 'value' (search_id) and 'label' (search name).
    """
    sorted_searches = sort_searches_by_name(searches)
    return [
        {
            "value": s.get("id") or "",
            "label": s.get("name") or s.get("id") or "Unnamed"
        }
        for s in sorted_searches
    ]
