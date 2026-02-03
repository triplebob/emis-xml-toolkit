"""
Resolve value sets from stored keys with CodeStore when available.
"""

from typing import Any, Dict, List, Optional
import streamlit as st

from ..system.session_state import SessionStateKeys
from ..caching.code_store import CodeStore


def _get_code_store(code_store: Optional[CodeStore] = None) -> Optional[CodeStore]:
    if code_store is not None:
        return code_store
    return st.session_state.get(SessionStateKeys.CODE_STORE)


def resolve_value_set_keys(
    value_set_keys: List[tuple],
    code_store: Optional[CodeStore] = None,
) -> List[Dict[str, Any]]:
    if not value_set_keys:
        return []
    store = _get_code_store(code_store)
    if store is None:
        return []
    resolved: List[Dict[str, Any]] = []
    for key in value_set_keys:
        code_data = store.get_code(key)
        if code_data:
            resolved.append(code_data)
    return resolved


def resolve_value_sets(
    criterion: Dict[str, Any],
    code_store: Optional[CodeStore] = None,
) -> List[Dict[str, Any]]:
    if not isinstance(criterion, dict):
        return []
    existing = criterion.get("value_sets") or []
    if existing:
        return existing
    keys = criterion.get("value_set_keys") or []
    resolved = resolve_value_set_keys(keys, code_store=code_store)
    if not resolved:
        return []
    flags = criterion.get("flags") or {}
    column_name = flags.get("column_name")
    column_display = flags.get("column_display_name")
    logical_table = flags.get("logical_table_name")
    in_not_in = flags.get("in_not_in")
    output: List[Dict[str, Any]] = []
    for entry in resolved:
        entry_copy = dict(entry)
        if column_name and "column_name" not in entry_copy:
            entry_copy["column_name"] = column_name
        if column_display and "column_display_name" not in entry_copy:
            entry_copy["column_display_name"] = column_display
        if logical_table and "logical_table_name" not in entry_copy:
            entry_copy["logical_table_name"] = logical_table
        if in_not_in and "in_not_in" not in entry_copy:
            entry_copy["in_not_in"] = in_not_in
        output.append(entry_copy)
    return output
