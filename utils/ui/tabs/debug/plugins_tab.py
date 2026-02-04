"""
Plugin Manager Tab - Debug mode only.
Displays all registered pattern plugins with enable/disable controls.
"""

import streamlit as st
from typing import Dict

from ....pattern_plugins.registry import pattern_registry
from ....pattern_plugins.base import PluginPriority


# Map priority values to human-readable names
PRIORITY_NAMES: Dict[int, str] = {
    PluginPriority.CRITICAL: "CRITICAL",
    PluginPriority.HIGH: "HIGH",
    PluginPriority.NORMAL: "NORMAL",
    PluginPriority.DEFAULT: "DEFAULT",
    PluginPriority.LOW: "LOW",
}


def _priority_label(priority: int) -> str:
    """Convert priority integer to human-readable tier name."""
    if priority in PRIORITY_NAMES:
        return PRIORITY_NAMES[priority]
    for threshold, name in sorted(PRIORITY_NAMES.items()):
        if priority <= threshold:
            return name
    return "LOW"


def _priority_colour(priority: int) -> str:
    """Return text colour for priority tier."""
    if priority <= PluginPriority.CRITICAL:
        return "#ff4b4b"
    if priority <= PluginPriority.HIGH:
        return "#ffa500"
    if priority <= PluginPriority.NORMAL:
        return "#00cc00"
    if priority <= PluginPriority.DEFAULT:
        return "#6c757d"
    if priority <= PluginPriority.LOW:
        return "#4da6ff"
    return "#6c757d"


def _compact_divider() -> None:
    """Render a tighter divider than Streamlit's default."""
    st.markdown(
        "<hr style='margin:0.05rem 0 1.2rem 0;border:none;border-top:1px solid rgba(128,128,128,0.35);'>",
        unsafe_allow_html=True,
    )


def render_plugins_content():
    """Render plugin manager interface."""
    st.subheader("Pattern Plugins")

    # Ensure plugins are loaded
    pattern_registry.load_all_modules("utils.pattern_plugins")

    status = pattern_registry.get_plugin_status()
    if not status:
        st.info("No plugins registered.")
        return

    # Summary metrics
    enabled_count = sum(1 for p in status.values() if p["enabled"])
    total_count = len(status)

    col1, col2, col3, col4 = st.columns([2,2,2,1])
    with col1:
        with st.container(border=True):
            st.metric("Total Plugins", total_count)
    with col2:
        with st.container(border=True):
            st.metric("Enabled", enabled_count)
    with col3:
        with st.container(border=True):
            st.metric("Disabled", total_count - enabled_count)
    with col4:
        st.markdown("")
        st.markdown("")
        # Reset button
        if st.button("Reset All to Defaults", help="Re-enable all plugins"):
            for pid in status:
                pattern_registry.enable_plugin(pid)
            st.success(f"All {total_count} plugins enabled")
            st.rerun()

    st.markdown("")
    st.markdown("")

    st.markdown("#### Registered Plugins")
    st.caption("Sorted by execution priority (lower values run first)")
    st.markdown("")

    sorted_plugins = sorted(
        status.items(),
        key=lambda x: (x[1]["priority"], x[0])
    )

    # Table header
    header_cols = st.columns([2, 3, 1.5, 1, 0.7, 0.8, 0.6])
    header_cols[0].markdown("**Name**")
    header_cols[1].markdown("**Description**")
    header_cols[2].markdown("**Tags**")
    header_cols[3].markdown("<div style='text-align:center'><strong>Priority</strong></div>", unsafe_allow_html=True)
    header_cols[4].markdown("<div style='text-align:center'><strong>Score</strong></div>", unsafe_allow_html=True)
    header_cols[5].markdown("<div style='text-align:center'><strong>Version</strong></div>", unsafe_allow_html=True)
    header_cols[6].markdown("<div style='text-align:center'><strong>Enabled</strong></div>", unsafe_allow_html=True)

    _compact_divider()

    # Table rows
    for plugin_id, info in sorted_plugins:
        priority = info["priority"]
        priority_colour = _priority_colour(priority)

        cols = st.columns([2, 3, 1.5, 1, 0.7, 0.8, 0.6])

        cols[0].markdown(f"<code style='font-size:0.85em'>{plugin_id}</code>", unsafe_allow_html=True)
        cols[1].markdown(f"<span style='font-size:0.85em;font-style:italic'>{info['description'] or '-'}</span>", unsafe_allow_html=True)
        cols[2].markdown(f"<span style='font-size:0.8em'>{', '.join(info['tags']) if info['tags'] else '-'}</span>", unsafe_allow_html=True)
        cols[3].markdown(
            (
                f"<div style='width:100%;text-align:center'>"
                f"<span style='font-size:0.85em;color:{priority_colour};font-weight:600'>{_priority_label(priority)}</span>"
                f"</div>"
            ),
            unsafe_allow_html=True,
        )
        cols[4].markdown(
            f"<div style='width:100%;text-align:center'><span style='font-size:0.9em'>{priority}</span></div>",
            unsafe_allow_html=True,
        )
        cols[5].markdown(
            f"<div style='width:100%;text-align:center'><span style='font-size:0.85em'>{info['version'] or '-'}</span></div>",
            unsafe_allow_html=True,
        )

        enabled_cols = cols[6].columns([1, 1, 1])
        new_enabled = enabled_cols[1].checkbox(
            "Enabled",
            value=info["enabled"],
            key=f"plugin_enabled_{plugin_id}",
            label_visibility="collapsed"
        )

        if new_enabled != info["enabled"]:
            if new_enabled:
                pattern_registry.enable_plugin(plugin_id)
            else:
                pattern_registry.disable_plugin(plugin_id)
            st.rerun()
