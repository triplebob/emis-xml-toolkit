"""
Pytest configuration for test compatibility helpers.
"""

import streamlit as st


def _patch_streamlit_cache_scope() -> None:
    """
    Make Streamlit cache decorators tolerant of unknown 'scope' kwarg.

    Some local environments may run a Streamlit build that doesn't yet
    support the `scope` argument on `st.cache_data` / `st.cache_resource`.
    This shim keeps tests importable across versions.
    """

    if hasattr(st, "cache_data"):
        original_cache_data = st.cache_data

        def cache_data_compat(*args, **kwargs):
            kwargs.pop("scope", None)
            return original_cache_data(*args, **kwargs)

        st.cache_data = cache_data_compat

    if hasattr(st, "cache_resource"):
        original_cache_resource = st.cache_resource

        def cache_resource_compat(*args, **kwargs):
            kwargs.pop("scope", None)
            return original_cache_resource(*args, **kwargs)

        st.cache_resource = cache_resource_compat


_patch_streamlit_cache_scope()

