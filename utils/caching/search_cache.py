"""
Search-specific caching helpers for selection and expansion state.
"""

import streamlit as st
from typing import Optional

from ..system.session_state import SessionStateKeys


def get_selected_search_id() -> Optional[str]:
    """Get currently selected search ID from session state."""
    return st.session_state.get(SessionStateKeys.SELECTED_SEARCH_ID)


def set_selected_search_id(search_id: str) -> None:
    """Set selected search ID in session state."""
    st.session_state[SessionStateKeys.SELECTED_SEARCH_ID] = search_id


def get_selected_folder_id() -> Optional[str]:
    """Get currently selected folder ID from session state."""
    return st.session_state.get(SessionStateKeys.SELECTED_FOLDER_ID)


def set_selected_folder_id(folder_id: str) -> None:
    """Set selected folder ID in session state."""
    st.session_state[SessionStateKeys.SELECTED_FOLDER_ID] = folder_id


def _expanded_key(search_id: str, group_idx: int, crit_idx: int) -> str:
    """Compose dynamic key for criterion expansion state."""
    return f"{SessionStateKeys.CRITERIA_EXPANDED_PREFIX}{search_id}_{group_idx}_{crit_idx}"


def get_criteria_expanded(search_id: str, group_idx: int, crit_idx: int) -> bool:
    """
    Check if a criterion expander is open; defaults to False.
    """
    key = _expanded_key(search_id, group_idx, crit_idx)
    return bool(st.session_state.get(key, False))


def set_criteria_expanded(search_id: str, group_idx: int, crit_idx: int, expanded: bool) -> None:
    """
    Set criterion expander state.
    """
    key = _expanded_key(search_id, group_idx, crit_idx)
    st.session_state[key] = expanded


def clear_search_cache() -> None:
    """
    Clear search selection and expansion cache entries.
    """
    keys_to_clear = {
        SessionStateKeys.SELECTED_SEARCH_ID,
        SessionStateKeys.SELECTED_FOLDER_ID,
    }

    for key in list(st.session_state.keys()):
        if (
            key in keys_to_clear
            or key.startswith(SessionStateKeys.CRITERIA_EXPANDED_PREFIX)
            or key.startswith(SessionStateKeys.SEARCH_EXPORT_READY_PREFIX)
            or key.startswith(SessionStateKeys.SEARCH_EXPORT_PATH_PREFIX)
        ):
            del st.session_state[key]
