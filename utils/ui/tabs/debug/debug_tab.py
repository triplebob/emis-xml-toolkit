"""
Debug Tab - Main wrapper with subtabs for Memory and Plugins.
Only visible when debug mode is enabled.
"""

import streamlit as st


def render_debug_tab():
    """Render the Debug tab with Memory and Plugins subtabs."""
    memory_tab, plugins_tab = st.tabs(["💾 Memory", "🧩 Plugins"])

    with memory_tab:
        from .memory_tab import render_memory_content
        render_memory_content()

    with plugins_tab:
        from .plugins_tab import render_plugins_content
        render_plugins_content()
