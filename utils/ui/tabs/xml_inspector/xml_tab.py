"""
Main XML Browser tab: wraps the file browser view of XML folder/report/search structure.
"""

import streamlit as st
from .file_browser import render_file_browser
from .raw_viewer import render_raw_viewer
from .dependencies_tab import render_dependencies_tab
from ....metadata.structure_provider import get_structure_metadata
from ....parsing.encoding import decode_xml_bytes
from ...theme import info_box
from ....system.session_state import SessionStateKeys


def render_xml_tab(*_args, **_kwargs):
    @st.fragment
    def xml_tab_fragment():
        metadata = get_structure_metadata()
        folder_tree = metadata.get("folder_tree", {})

        if not folder_tree or not folder_tree.get("roots"):
            st.markdown(info_box("No folder structure found in this XML."), unsafe_allow_html=True)
            return

        uploaded_file = st.session_state.get(SessionStateKeys.UPLOADED_FILE)
        xml_content = ""
        if uploaded_file is not None:
            try:
                uploaded_file.seek(0)
            except Exception:
                pass
            raw_bytes = uploaded_file.read()
            try:
                uploaded_file.seek(0)
            except Exception:
                pass
            if raw_bytes:
                xml_content, _, _, _ = decode_xml_bytes(raw_bytes)

        tab1, tab2, tab3 = st.tabs(["📁 File Browser", "🔗 Dependencies", "</> XML Browser"])

        with tab1:
            render_file_browser(folder_tree)

        with tab2:
            nodes = metadata.get("nodes", [])
            deps = metadata.get("dependencies", {})
            dependents = metadata.get("dependents", {})
            id_to_name = metadata.get("id_to_name", {})
            render_dependencies_tab(nodes, deps, dependents, id_to_name)

        with tab3:
            nodes = metadata.get("nodes", [])
            folders = metadata.get("folders", [])
            render_raw_viewer(xml_content, nodes, folders)

    xml_tab_fragment()
