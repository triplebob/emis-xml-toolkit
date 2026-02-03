"""
Search analysis tab powered by the parsing pipeline.
Currently scoped to searches only; report tabs remain disabled.
"""

from typing import Dict, Any, List
import streamlit as st
import json
from ...theme import info_box, error_box
from .metadata_provider import get_search_metadata
from ....metadata.value_set_resolver import resolve_value_sets


def render_search_analysis_tab(xml_content: str, xml_filename: str):
    """
    Render the Search Analysis tab: folder browser, search details, dependencies.
    """
    if not xml_content:
        st.markdown(info_box("📋 Upload and process an XML file to see search analysis"), unsafe_allow_html=True)
        return

    try:
        metadata = get_search_metadata()
        searches = metadata.get("searches", [])
        folder_tree = metadata.get("folder_tree", {})
        deps = metadata.get("dependencies", {})
        id_to_name = metadata.get("id_to_name", {})

        search_count = len(searches)
        folder_count = folder_tree.get("total_folders", 0)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("🔍 Searches", search_count)
        with col2:
            st.metric("📁 Folders", folder_count)

        if search_count == 0:
            st.markdown(info_box("No searches detected in this XML."), unsafe_allow_html=True)
            return

        tab1, tab2 = st.tabs(["📁 Folder Browser", "🔧 Search Details"])

        with tab1:
            _render_folder_tree(folder_tree)

        with tab2:
            _render_search_details(searches, deps, id_to_name)
            _render_search_export(searches, deps, id_to_name)

    except Exception as e:
        st.markdown(error_box(f"❌ Error analysing search structure: {str(e)}"), unsafe_allow_html=True)



def _render_folder_tree(folder_tree: Dict[str, Any]):
    roots = folder_tree.get("roots") or []
    if not roots:
        st.markdown(info_box("No folders found in this XML."), unsafe_allow_html=True)
        return

    def _render_node(node: Dict[str, Any], depth: int = 0):
        indent = "&nbsp;" * (depth * 4)
        name = node.get("name") or node.get("id") or "Unnamed"
        st.markdown(f"{indent}📁 **{name}**", unsafe_allow_html=True)
        for search_ref in node.get("searches") or []:
            st.markdown(f"{indent}&nbsp;&nbsp;🔍 {search_ref.get('name') or search_ref.get('id')} (`{search_ref.get('id')}`)", unsafe_allow_html=True)
        for child in node.get("children") or []:
            _render_node(child, depth + 1)

    for root in roots:
        _render_node(root, 0)


def _render_search_details(searches: List[Dict[str, Any]], deps: Dict[str, List[str]], id_to_name: Dict[str, str]):
    options = {s.get("name") or s.get("id") or "Unnamed": s for s in searches}
    if not options:
        st.markdown(info_box("No searchable items found."), unsafe_allow_html=True)
        return

    selected_label = st.selectbox("Select a search", sorted(options.keys()))
    search = options[selected_label]

    st.markdown(f"**Name:** {search.get('name') or 'Unknown'}")
    st.markdown(f"**GUID:** `{search.get('id') or 'N/A'}`")
    folder_path = " / ".join(search.get("folder_path") or [])
    if folder_path:
        st.markdown(f"**Folder:** {folder_path}")
    if search.get("parent_guid"):
        st.markdown(f"**Parent Search/Report GUID:** `{search['parent_guid']}`")

    dep_list = deps.get(search.get("id"), [])
    if dep_list:
        st.markdown("**Dependencies:**")
        for dep in dep_list:
            label = id_to_name.get(dep, dep)
            st.markdown(f"- `{dep}` — {label}")
    else:
        st.markdown("**Dependencies:** None")

    dependents = search.get("dependent_names") or []
    if dependents:
        st.markdown("**Dependents:**")
        for dep in dependents:
            st.markdown(f"- {dep}")
    else:
        st.markdown("**Dependents:** None")

    st.markdown("---")
    st.subheader("Criteria Groups")
    for idx, group in enumerate(search.get("criteria_groups") or [], start=1):
        gf = group.get("group_flags") or {}
        st.markdown(f"**Group {idx}** – Operator: `{gf.get('member_operator','AND')}`")
        if gf.get("criteria_group_id"):
            st.caption(f"Group ID: `{gf['criteria_group_id']}`")
        if group.get("population_criteria"):
            refs = []
            for ref in group["population_criteria"]:
                gid = ref.get("report_guid")
                if gid:
                    refs.append(f"{gid} ({id_to_name.get(gid, 'Unknown')})")
            if refs:
                st.caption(f"Population references: {', '.join(refs)}")
        criteria = group.get("criteria") or []
        st.caption(f"Criteria count: {len(criteria)}")
        if criteria:
            with st.expander("View criteria", expanded=False):
                for c_idx, crit in enumerate(criteria, start=1):
                    cflags = crit.get("flags", {}) or {}
                    table = cflags.get("logical_table_name", "")
                    container = cflags.get("container_type") or "Main Criteria"
                    st.markdown(f"- **Criterion {c_idx}** ({container}) – table `{table}`")
                    if cflags.get("display_name"):
                        st.caption(f"  Name: {cflags['display_name']}")
                    if cflags.get("column_name"):
                        st.caption(f"  Columns: {cflags['column_name']}")
                    if cflags.get("member_operator"):
                        st.caption(f"  Operator: {cflags['member_operator']}")
                    if cflags.get("action_if_true") or cflags.get("action_if_false"):
                        st.caption(f"  Actions: true={cflags.get('action_if_true') or 'SELECT'} false={cflags.get('action_if_false') or 'REJECT'}")
                    if cflags.get("has_temporal_filter"):
                        st.caption("  Temporal: present")
                    vs_list = resolve_value_sets(crit)
                    if vs_list:
                        st.caption(f"  Value sets ({len(vs_list)}):")
                        for vs in vs_list:
                            label = vs.get("display_name") or vs.get("valueSet_description") or ""
                            st.write(f"    • {vs.get('code_value','')} — {label}")
                    else:
                        st.caption("  Value sets: none")


def _render_search_export(searches: List[Dict[str, Any]], deps: Dict[str, List[str]], id_to_name: Dict[str, str]):
    if not searches:
        return
    if st.button("📥 Download search structure (JSON)", key="search_structure_export"):
        payload = []
        for s in searches:
            entry = dict(s)
            entry["dependency_names"] = [id_to_name.get(d, d) for d in deps.get(s.get("id"), [])]
            payload.append(entry)
        st.download_button(
            label="Save JSON",
            data=json.dumps(payload, indent=2),
            file_name="search_structure.json",
            mime="application/json",
            key="search_structure_download",
        )
