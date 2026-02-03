"""
Enhanced search viewer with folder navigation, selection persistence, and criteria rendering.
"""

import streamlit as st
from typing import List, Dict, Optional, Any, Tuple

from ...theme import info_box, create_info_box_style, ThemeColours, ThemeSpacing
from ....caching.search_cache import (
    get_selected_search_id,
    set_selected_search_id,
    get_selected_folder_id,
    set_selected_folder_id,
)
from ....metadata.description_generators import format_base_population
from .search_common import (
    build_folder_hierarchy,
    sort_searches_by_name,
    render_empty_state,
)
from .search_criteria_viewer import render_criteria_group

def _render_export_buttons(
    current_search: Dict,
    all_searches: List[Dict],
    folders: List[Dict],
    id_to_name: Dict,
) -> None:
    """Render active export buttons for current search."""
    import gc
    from datetime import datetime
    from ....exports import generate_search_excel, export_search_json, export_full_structure_json
    from ....system.session_state import SessionStateKeys

    def _safe_name(text: str, fallback: str) -> str:
        safe = (text or fallback).replace(" ", "_").replace("/", "-")
        return safe[:50] if safe else fallback

    def _build_export_searches(searches: List[Dict]) -> Tuple[List[Dict], Dict]:
        entities = st.session_state.get(SessionStateKeys.PIPELINE_ENTITIES) or []
        entity_map = {
            ent.get("id"): ent
            for ent in entities
            if (ent.get("flags") or {}).get("element_type") == "search" and ent.get("id")
        }
        export_searches = []
        current_export = {}
        for search in searches or []:
            export_search = dict(search or {})
            ent = entity_map.get(export_search.get("id"))
            if ent:
                export_search["criteria_groups"] = ent.get("criteria_groups") or []
                if ent.get("parent_type"):
                    export_search["parent_type"] = ent.get("parent_type")
                if ent.get("description") is not None:
                    export_search["description"] = ent.get("description")
            export_searches.append(export_search)
            if search.get("id") == current_search.get("id"):
                current_export = export_search
        return export_searches, current_export

    def _init_export_state(state_key: str, context_id: str) -> Dict[str, Any]:
        state = st.session_state.get(state_key, {})
        if state.get("context") != context_id:
            state = {
                "context": context_id,
                "ready": False,
                "filename": "",
                "payload": None,
                "size_mb": None,
            }
            st.session_state[state_key] = state
        return state

    def _payload_size_mb(payload: Any) -> float:
        if payload is None:
            return 0.0
        if isinstance(payload, bytes):
            size = len(payload)
        else:
            size = len(str(payload).encode("utf-8"))
        return size / (1024 * 1024)

    def _render_lazy_export(
        *,
        state_key: str,
        context_id: str,
        generate_label: str,
        download_label: str,
        filename: str,
        mime: str,
        build_payload,
        spinner_text: str,
        full_width: bool = False,
    ) -> None:
        state = _init_export_state(state_key, context_id)
        generate_key = f"{state_key}_generate"
        download_key = f"{state_key}_download"
        width = "stretch" if full_width else "content"

        if state.get("ready"):
            if state.get("size_mb") and state["size_mb"] > 50:
                st.warning(f"Large file: {state['size_mb']:.1f}MB. Download may take time.")
            download_help = f"Start Download: {state.get('filename') or filename}"
            downloaded = st.download_button(
                download_label,
                data=state.get("payload") or "",
                file_name=state.get("filename") or filename,
                mime=mime,
                help=download_help,
                key=download_key,
                width=width,
            )
            if downloaded:
                if state_key in st.session_state:
                    del st.session_state[state_key]
                gc.collect()
                st.rerun()
            return

        generate_help = f"Generate: {filename}"
        generate_clicked = st.button(
            generate_label,
            help=generate_help,
            key=generate_key,
            width=width,
        )
        if generate_clicked:
            with st.spinner(spinner_text):
                try:
                    payload = build_payload()
                    st.session_state[state_key] = {
                        "context": context_id,
                        "ready": True,
                        "filename": filename,
                        "payload": payload,
                        "size_mb": _payload_size_mb(payload),
                    }
                    st.rerun()
                except Exception as e:
                    st.error(f"Export failed: {str(e)}")
                    if st.session_state.get(SessionStateKeys.DEBUG_MODE):
                        st.exception(e)

    export_searches, export_search = _build_export_searches(all_searches or [])

    export_excel, export_json, export_all = st.columns([1.2, 1.2, 2])
    with export_excel:
        search_name_safe = _safe_name(current_search.get("name") or "search", "search")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{search_name_safe}_{timestamp}.xlsx"
        _render_lazy_export(
            state_key="search_export_excel_state",
            context_id=f"excel|{current_search.get('id')}",
            generate_label="🔄 Export Current Ruleset (XLSX)",
            download_label="📥 Download Current Ruleset (XLSX)",
            filename=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            build_payload=lambda: generate_search_excel(export_search, export_searches, folders, id_to_name),
            spinner_text="Generating Excel file...",
            full_width=True,
        )

    with export_json:
        search_name_safe = _safe_name(current_search.get("name") or "search", "search")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{search_name_safe}_{timestamp}.json"
        _render_lazy_export(
            state_key="search_export_json_state",
            context_id=f"json|{current_search.get('id')}",
            generate_label="🔄 Export Current Ruleset (JSON)",
            download_label="📥 Download Current Ruleset (JSON)",
            filename=filename,
            mime="application/json",
            build_payload=lambda: export_search_json(export_search["id"], export_searches, folders, id_to_name),
            spinner_text="Generating JSON...",
            full_width=True,
        )

    with export_all:
        filename_base = st.session_state.get(SessionStateKeys.XML_FILENAME, "searches")
        filename_safe = _safe_name(filename_base.replace(".xml", ""), "searches")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_safe}_full_structure_{timestamp}.json"
        _render_lazy_export(
            state_key="search_export_all_json_state",
            context_id=f"all_json|{filename_safe}",
            generate_label="🔄 Export Complete Ruleset - ALL Searches (JSON)",
            download_label="📥 Download Complete Ruleset - ALL Searches (JSON)",
            filename=filename,
            mime="application/json",
            build_payload=lambda: export_full_structure_json(export_searches, folders),
            spinner_text="Generating full structure JSON...",
            full_width=True,
        )

def _render_search_metadata(search: Dict, id_to_name: Dict[str, str]) -> None:

    st.markdown("")
    
    """Render high-level search metadata."""
    st.subheader(f"📋 {search.get('name') or 'Unnamed Search'}")

    if search.get("description"):
        with st.container(border=True):
            st.markdown(f"<i>{search['description']}</i>", unsafe_allow_html=True)

    # Child search OR base population (mutually exclusive)
    parent_guid = search.get("parent_guid")
    if parent_guid:
        parent_name = id_to_name.get(parent_guid, "Unknown")
        population_text = f"🟠 <strong>Child Search!</strong> Parent Search: {parent_name}"
    else:
        parent_type = search.get("parent_type") or search.get("parentType")
        base_pop_text = format_base_population(parent_type)
        population_text = f"<strong>Base Population:</strong> {base_pop_text}"

    info_col1, info_col2 = st.columns([3, 1.5])
    with info_col1:
        st.markdown(
            create_info_box_style(
                ThemeColours.BLUE,
                population_text,
                margin_bottom=ThemeSpacing.MARGIN_EXTENDED,
            ),
            unsafe_allow_html=True,
        )
    with info_col2:
        search_id = search.get("id") or "Unknown"
        st.markdown(
            create_info_box_style(
                ThemeColours.PURPLE,
                f"<strong>Search GUID:</strong> {search_id}",
                margin_bottom=ThemeSpacing.MARGIN_EXTENDED,
            ),
            unsafe_allow_html=True,
        )
    st.markdown('<div class="spacer-xxs">&nbsp;</div>', unsafe_allow_html=True)

    # Dependencies (hidden if no dependents)
    dependents = search.get("dependent_names") or []
    if dependents:
        search_word = "search" if len(dependents) == 1 else "searches"
        with st.expander(f"👥 Has {len(dependents)} dependent {search_word}", expanded=False):
            for dep in dependents:
                st.caption(f"• {dep}")


def _resolve_current_search_label(
    search_options: Dict[str, Dict], current_search_id: Optional[str]
) -> Optional[str]:
    """Find the label matching the cached search id."""
    if not current_search_id:
        return None
    for label, search in search_options.items():
        if search.get("id") == current_search_id:
            return label
    return None


def render_search_detail_tab(
    searches: List[Dict],
    folders: List[Dict],
    id_to_name: Dict[str, str],
):

    st.markdown("""
        <style>
        .spacer-xxs {
        height: 0.1rem;
        display: block;
        }
        </style>
    """, unsafe_allow_html=True)

    """
    Enhanced search viewer with folder navigation, selection persistence, and criteria rendering.
    """
    @st.fragment
    def search_detail_fragment():
        if not searches:
            render_empty_state("No searches available.")
            return

        # Folder hierarchy and selection
        folder_hierarchy = build_folder_hierarchy(folders, searches)
        folder_options = list(folder_hierarchy.keys())

        current_folder = get_selected_folder_id() or "All Folders inc Root"
        if current_folder not in folder_options:
            current_folder = "All Folders inc Root"
        
        # Two-column layout for dropdowns
        col1, col2 = st.columns([3, 4])

        with col1:
            selected_folder = st.selectbox(
                "📁 Folder",
                folder_options,
                index=folder_options.index(current_folder) if current_folder in folder_options else 0,
                key="folder_selector",
            )

        if selected_folder != current_folder:
            set_selected_folder_id(selected_folder)

        folder_searches = folder_hierarchy.get(selected_folder, [])
        if not folder_searches:
            render_empty_state(f"No searches in folder: {selected_folder}")
            return

        # Search selection with persistence
        sorted_searches = sort_searches_by_name(folder_searches)
        search_options = {s.get("name") or s.get("id") or "Unnamed": s for s in sorted_searches}
        search_labels = list(search_options.keys())

        current_search_id = get_selected_search_id()
        current_label = _resolve_current_search_label(search_options, current_search_id)

        # If current search not in folder, clear it and default to first
        if current_label not in search_labels:
            current_label = None
            current_search_id = None

        with col2:
            selected_label = st.selectbox(
                "🔍 Search",
                search_labels,
                index=search_labels.index(current_label) if current_label else 0,
                key="search_selector",
            )

        search = search_options[selected_label]
        selected_id = search.get("id")

        # Always update session state to maintain sync
        if selected_id != current_search_id:
            set_selected_search_id(selected_id)

        if selected_folder and selected_folder != "All Folders inc Root":
            status_text = f"📋 Showing {len(folder_searches)} searches in selected folder."
        else:
            status_text = f"📋 Showing {len(folder_searches)} searches across all folders."

        status_col1, status_col2 = st.columns([3, 4])
        with status_col1:
            st.markdown(create_info_box_style(ThemeColours.BLUE, status_text), unsafe_allow_html=True)
        with status_col2:
            with st.expander("📥 Export Options", expanded=False):
                _render_export_buttons(search, searches, folders, id_to_name)

        # Search metadata (name, description, parent info, dependencies)
        _render_search_metadata(search, id_to_name)

        # Rules section
        st.subheader("🔍 Rules")

        criteria_groups = search.get("criteria_groups") or []
        if not criteria_groups:
            st.markdown(info_box("No criteria groups defined in this search."), unsafe_allow_html=True)
            return

        # Each rule in its own expandable frame
        for group_idx, group in enumerate(criteria_groups):
            rule_number = group_idx + 1
            with st.expander(f"🔍 Rule {rule_number}", expanded=True):
                render_criteria_group(group, group_idx, search, id_to_name)

    search_detail_fragment()
