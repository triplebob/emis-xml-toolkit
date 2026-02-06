"""
NHS Terminology Server Expansion UI

Integrated within Clinical Codes tab as sub-tab for expanding SNOMED codes with includechildren=true.

Three-tier display:
1. Expansion controls (top fragment)
2. Parent codes summary table (middle fragment)
3. Child codes detail table (bottom fragment)
"""

import gc
import streamlit as st
import pandas as pd
from typing import List, Dict, Optional

from ...theme import ThemeColours, info_box, success_box, warning_box, error_box
from ....system.session_state import SessionStateKeys
from ....terminology_server import (
    prepare_expansion_selection,
    run_expansion,
    prepare_child_codes_view,
    trace_full_lineage,
    FullLineageTraceResult,
)
from ....exports import (
    get_child_code_export_options,
    get_child_code_export_preview,
    build_child_code_export_filename,
    build_child_code_export_csv,
    render_lookup_hierarchy_export_controls,
)

EXPANSION_HIERARCHY_DEPTH_CAP = 12
EXPANSION_HIERARCHY_NODE_CAP_PER_PARENT = 5000


def render_expansion_tab_content(clinical_data: List[Dict]):
    """
    Main expansion tab renderer - matches archived UI structure

    Args:
        clinical_data: Clinical codes from unified pipeline
    """
    st.subheader("🏥 Terminology Server Child Code Expansion")
    st.markdown(
        "Use the NHS Terminology Server to expand SNOMED codes with "
        "`<includeChildren>true</includeChildren>` to return a comprehensive list of all child codes"
    )
    
    st.markdown("""<style>[data-testid="stElementToolbar"]{display: none;}</style>""", unsafe_allow_html=True)
    
    st.markdown("---")

    # Fragment 1: Expansion Controls
    @st.fragment
    def expansion_controls_fragment():
        expansion_data = render_expansion_controls(clinical_data)
        if expansion_data:
            st.session_state.expansion_results_data = expansion_data
            st.rerun()

    expansion_controls_fragment()

    # Fragment 2: Parent Summary (if data exists)
    if hasattr(st.session_state, 'expansion_results_data') and st.session_state.expansion_results_data:
        st.markdown("")

        @st.fragment
        def expansion_results_fragment():
            render_expansion_results(st.session_state.expansion_results_data)

        expansion_results_fragment()

        st.markdown("")
        st.markdown("")

        # Fragment 3: Child Codes Detail
        @st.fragment
        def child_codes_detail_fragment():
            render_child_codes_detail(st.session_state.expansion_results_data)

        child_codes_detail_fragment()

        st.markdown("")
        st.markdown("")

        # Fragment 4: Hierarchy View
        @st.fragment
        def hierarchy_view_fragment():
            render_hierarchy_view(st.session_state.expansion_results_data)

        hierarchy_view_fragment()


def render_expansion_controls(clinical_data: List[Dict]) -> Optional[Dict]:
    """
    Render expansion controls and perform expansion

    Args:
        clinical_data: Clinical codes list

    Returns:
        Expansion data dict or None
    """
    selection_all = prepare_expansion_selection(clinical_data, filter_zero_descendants=False)
    if not selection_all.all_expandable_codes:
        st.info("📍 No codes with includechildren=true found in this XML")
        st.markdown("""
        **Note**: The NHS Terminology Server expansion feature requires codes flagged with
        `<includeChildren>true</includeChildren>` in your EMIS XML search criteria.
        """)
        return None

    st.markdown("### ⚕️ SNOMED Code Expansion")

    info_col = st.container()
    filter_zero_descendants = st.session_state.get("expand_filter_zero_descendants", True)

    selection = prepare_expansion_selection(clinical_data, filter_zero_descendants=filter_zero_descendants)
    stats = selection.stats
    original_count = stats["original_count"]
    unique_count = stats["unique_count"]
    dedupe_savings = stats["dedupe_savings"]
    zero_descendant_count = stats["zero_descendant_count"]
    remaining_codes = stats["remaining_count"]

    # Show info message in full width
    with info_col:
        if filter_zero_descendants:
            if zero_descendant_count > 0:
                if dedupe_savings > 0:
                    st.markdown(f"""
                    <div style="
                        background-color: #28546B;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1.0rem;
                    ">
                        Found {original_count} expandable codes → {unique_count} unique codes (saved {dedupe_savings} duplicate API calls) → {remaining_codes} after filtering 0-descendant codes
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="
                        background-color: #28546B;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1.0rem;
                    ">
                        Found {unique_count} codes that can be expanded - filtered out {zero_descendant_count} codes with 0 descendants (saves API calls), {remaining_codes} codes will be processed
                    </div>
                    """, unsafe_allow_html=True)
            else:
                if dedupe_savings > 0:
                    st.markdown(f"""
                    <div style="
                        background-color: #28546B;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1.0rem;
                    ">
                        Found {original_count} expandable codes → {unique_count} unique codes (saved {dedupe_savings} duplicate API calls)
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="
                        background-color: #28546B;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1.0rem;
                    ">
                        Found {unique_count} codes that can be expanded to include child concepts
                    </div>
                    """, unsafe_allow_html=True)
        else:
            if dedupe_savings > 0:
                st.markdown(f"""
                <div style="
                    background-color: #5B2758;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 0.5rem;
                ">
                    Found {original_count} expandable codes → {unique_count} unique codes (saved {dedupe_savings} duplicate API calls)
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="
                    background-color: #5B2758;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 0.5rem;
                ">
                    Found {unique_count} codes that can be expanded to include child concepts
                </div>
                """, unsafe_allow_html=True)

    # Controls row: button + checkboxes
    button_col, cb_col1, cb_col2, cb_col3 = st.columns([0.6, 0.8, 0.6, 1])

    with button_col:
        expand_clicked = st.button(
            "🌳 Expand Child Codes",
            type="secondary",
            disabled=not selection.expandable_codes
        )

    with cb_col1:
        st.markdown("")
        include_inactive = st.checkbox(
            "Include inactive concepts",
            value=False,
            help="Include concepts that are inactive/deprecated in SNOMED CT"
        )

    with cb_col2:
        st.markdown("")
        use_cache = st.checkbox(
            "Use cached results",
            value=True,
            help="Use previously cached expansion results (90-day expiry)"
        )

    with cb_col3:
        st.markdown("")
        filter_zero_descendants = st.checkbox(
            "Skip codes with 0 descendants",
            value=True,
            help="Filter out codes already known to have no child concepts (saves API calls)",
            key="expand_filter_zero_descendants"
        )

    # Expand button
    if expand_clicked:
        # Progress tracking
        progress_bar = st.progress(0.0)
        status_text = st.empty()

        try:
            # Load EMIS lookup cache from session state
            lookup_df = getattr(st.session_state, 'lookup_df', None)
            snomed_code_col = getattr(st.session_state, 'snomed_code_col', 'SNOMED Code')
            emis_guid_col = getattr(st.session_state, 'emis_guid_col', 'EMIS GUID')
            version_info = getattr(st.session_state, 'lookup_version_info', None)

            # Check if credentials are configured
            try:
                client_id = st.secrets["NHSTSERVER_ID"]
                client_secret = st.secrets["NHSTSERVER_TOKEN"]
            except KeyError:
                st.error("❌ NHS Terminology Server credentials not configured. Please add NHSTSERVER_ID and NHSTSERVER_TOKEN to secrets.")
                return None

            # Progress callback
            def on_progress(completed, total):
                progress = completed / total if total > 0 else 0
                progress_bar.progress(progress)
                status_text.text(f"Expanding: {completed}/{total} codes")

            status_text.text("Preparing expansion...")
            result = run_expansion(
                selection,
                lookup_df,
                snomed_code_col,
                emis_guid_col,
                version_info,
                include_inactive=include_inactive,
                use_cache=use_cache,
                max_workers=10,
                progress_callback=on_progress,
                client_id=client_id,
                client_secret=client_secret,
            )

            progress_bar.empty()
            status_text.empty()

            if result.error:
                st.error(f"❌ Expansion failed: {result.error}")
                return None

            # Success message
            st.success(
                f"✅ Successfully expanded {result.successful_expansions}/{len(result.expansion_results)} parent codes "
                f"→ {result.total_child_codes} child codes"
            )

            # Store results
            return {
                'expansion_results': result.expansion_results,
                'summary_rows': result.summary_rows,
                'total_child_codes': result.total_child_codes,
                'successful_expansions': result.successful_expansions,
                'include_inactive': result.include_inactive,
                'original_codes': selection.expandable_codes,
                'processed_children': result.processed_children,
                'lookup_stats': result.lookup_stats,
            }

        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"❌ Expansion failed: {str(e)}")
            return None

    return None


def render_expansion_results(expansion_data: Dict):
    """
    Render parent codes summary table

    Args:
        expansion_data: Expansion results dictionary
    """
    with st.expander("📊 Expansion Results", expanded=True):
        summary_rows = expansion_data.get("summary_rows", [])
        if not summary_rows:
            st.info("No expansion summary available")
            return

        summary_df = pd.DataFrame(summary_rows)
        if "SNOMED Code" in summary_df.columns:
            summary_df["SNOMED Code"] = "⚕️ " + summary_df["SNOMED Code"].astype(str)

        # Style by status
        def style_status(row):
            status = row['Result Status']
            if status.startswith('Matched'):
                return ['background-color: #1F4E3D; color: #FAFAFA'] * len(row)  # Green
            elif status.startswith('Unmatched'):
                return ['background-color: #7A5F0B; color: #FAFAFA'] * len(row)  # Amber
            else:  # Error
                return ['background-color: #660022; color: #FAFAFA'] * len(row)  # Wine red

        styled_summary = summary_df.style.apply(style_status, axis=1)
        st.dataframe(styled_summary, width='stretch', hide_index=True)

        # Summary metrics
        statuses = summary_df["Result Status"].fillna("").tolist()
        matched_count = sum(1 for status in statuses if status.startswith("Matched"))
        unmatched_count = sum(1 for status in statuses if status.startswith("Unmatched") or status.startswith("Error"))
        total_count = len(statuses)
        child_count = expansion_data['total_child_codes']

        col1, col2 = st.columns(2)
        with col1:
            if total_count == 0:
                status_box = warning_box("⚠️ No expansions were run")
            elif matched_count == total_count:
                status_box = success_box(
                    f"✅ Expansion complete: {matched_count}/{total_count} codes expanded successfully"
                )
            elif unmatched_count == total_count:
                status_box = error_box(
                    f"❌ Expansion failed: {matched_count}/{total_count} codes expanded successfully"
                )
            else:
                status_box = warning_box(
                    f"⚠️ Expansion complete: {matched_count}/{total_count} codes expanded successfully"
                )
            st.markdown(status_box, unsafe_allow_html=True)
        with col2:
            st.markdown(
                info_box(f"📊 Total child codes discovered: {child_count}"),
                unsafe_allow_html=True
            )
        
        st.markdown("")


def render_child_codes_detail(expansion_data: Dict):
    """
    Render child codes detail table with filtering and export

    Args:
        expansion_data: Expansion results dictionary
    """
    st.markdown("### 👪 Child Codes Detail")

    all_child_codes = expansion_data.get('processed_children', [])
    lookup_stats = expansion_data.get("lookup_stats", {}) or {}

    if not all_child_codes:
        st.info("No child codes to display")
        return

    st.caption("🌳 Expanded hierarchy includes ALL descendants (children, grandchildren, etc.) from NHS Terminology Server")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search_term = st.text_input(
            "Search child codes",
            placeholder="Enter code or description to filter...",
            label_visibility="visible",
            icon="🔍",
            key="child_codes_search"
        )
    with col2:
        st.markdown("")
        st.markdown("")
        show_inactive = st.checkbox(
            "Include inactive concepts",
            value=False,
            help="Include concepts that are inactive/deprecated in SNOMED CT",
            key="show_inactive_children"
        )
    with col3:
        view_mode_label = st.selectbox(
            "Code Display Mode:",
            ["🔀 Unique Codes", "📍 Per Source"],
            index=0,
            key="child_view_mode",
            help="🔀 Unique Codes: show distinct parent-child combinations only. "
                 "📍 Per Source: show duplicates across sources."
        )

    mode_key = "unique" if view_mode_label == "🔀 Unique Codes" else "per_source"
    view_data = prepare_child_codes_view(
        all_child_codes,
        search_term=search_term,
        show_inactive=show_inactive,
        view_mode=mode_key
    )
    filtered_rows = view_data["rows"]

    if filtered_rows:
        child_df = pd.DataFrame(filtered_rows)
        if mode_key == "unique":
            for col in ["Source Type", "Source Name", "Source Container"]:
                if col in child_df.columns:
                    child_df = child_df.drop(columns=[col])
        if "Parent Code" in child_df.columns:
            child_df["Parent Code"] = child_df["Parent Code"].apply(
                lambda v: v if str(v).startswith("⚕️") else f"⚕️ {v}"
            )
        if "Child Code" in child_df.columns:
            child_df["Child Code"] = child_df["Child Code"].apply(
                lambda v: v if str(v).startswith("⚕️") else f"⚕️ {v}"
            )
        if "EMIS GUID" in child_df.columns:
            def _format_emis_guid(value):
                text = str(value)
                if text == "Not in EMIS lookup table":
                    return text if text.startswith("❌") else f"❌ {text}"
                return text if text.startswith("🔍") else f"🔍 {text}"
            child_df["EMIS GUID"] = child_df["EMIS GUID"].apply(_format_emis_guid)
        if "Inactive" in child_df.columns:
            child_df["Inactive"] = child_df["Inactive"].apply(lambda v: "True" if v else "False")

        def _style_guid(row):
            guid_text = str(row.get("EMIS GUID", ""))
            if "Not in EMIS lookup table" in guid_text:
                return [f"background-color: {ThemeColours.RED}; color: {ThemeColours.TEXT}"] * len(row)
            return [f"background-color: {ThemeColours.GREEN}; color: {ThemeColours.TEXT}"] * len(row)

        styled_child_df = child_df.style.apply(_style_guid, axis=1)
        st.dataframe(styled_child_df, width='stretch', hide_index=True)
        unique_suffix = " (All unique children)" if mode_key == "unique" else ""
        spacer = "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        st.caption(
            f"Showing {len(child_df)} of {view_data['total_count']} child codes{unique_suffix}"
            f"{spacer}|{spacer}EMIS GUID Coverage: "
            f"{lookup_stats.get('emis_guid_found', 0)}/{lookup_stats.get('total_child_codes', 0)} "
            f"({lookup_stats.get('coverage_pct', 0):.1f}%)"
        )
    else:
        st.info("No child codes match the current filters")

    lookup_stats = expansion_data.get("lookup_stats", {})
    if lookup_stats:
        pass

    with st.expander("📥 Export Options", expanded=True):
        export_options, export_stats, base_rows = get_child_code_export_options(
            all_child_codes,
            view_mode=mode_key,
            include_inactive=True
        )
        default_index = 0
        col1, col2 = st.columns([1, 2])
        with col1:
            export_filter = st.radio(
                "Export Filter:",
                export_options,
                index=default_index,
                key="child_codes_export_filter",
                horizontal=len(export_options) <= 3
            )
            st.caption(
                f"📊 Total: {export_stats['total_count']} | "
                f"✅ Matched: {export_stats['matched_count']} | "
                f"❌ Unmatched: {export_stats['unmatched_count']}"
            )
        row_count, col_count = get_child_code_export_preview(
            base_rows,
            export_filter=export_filter,
            view_mode=mode_key
        )
        with col2:
            st.caption(f"📊 Will generate CSV with {row_count} rows × {col_count} columns")

            xml_filename = st.session_state.get(SessionStateKeys.XML_FILENAME, "")
            mode_label = "Unique" if mode_key == "unique" else "Per Source"
            label_map = {
                "All Child Codes": "All Child Codes",
                "Only Matched": "All Matched Child Codes",
                "Only Unmatched": "All Unmatched Child Codes",
            }
            label_base = label_map.get(export_filter, export_filter)
            context_id = f"{xml_filename}|{mode_key}|{export_filter}"
            export_state_key = "child_codes_export_state"
            export_state = st.session_state.get(export_state_key, {})
            if export_state.get("context") != context_id:
                export_state = {"context": context_id, "ready": False, "filename": "", "csv": ""}
                st.session_state[export_state_key] = export_state

            export_filename = export_state.get("filename") or build_child_code_export_filename(
                xml_filename,
                export_filter=export_filter,
                view_mode=mode_key
            )

            if export_state.get("ready"):
                download_label = f"📥 Download {label_base} ({mode_label})"
                download_help = f"Start Download: {export_filename}"
                downloaded = st.download_button(
                    download_label,
                    data=export_state.get("csv", ""),
                    file_name=export_filename or "child_codes_export.csv",
                    mime="text/csv",
                    help=download_help,
                    disabled=not export_state.get("csv"),
                    key="child_codes_export_download"
                )
                if downloaded:
                    if export_state_key in st.session_state:
                        del st.session_state[export_state_key]
                    gc.collect()
                    st.rerun()
            else:
                export_label = f"🔄 Export {label_base} ({mode_label})"
                export_help = f"Generate: {export_filename}"
                generate_clicked = st.button(
                    export_label,
                    help=export_help,
                    disabled=row_count == 0,
                    key="child_codes_export_generate"
                )
                if generate_clicked:
                    filename, csv_content, export_df = build_child_code_export_csv(
                        base_rows,
                        export_filter=export_filter,
                        view_mode=mode_key,
                        filename=export_filename,
                        xml_filename=xml_filename
                    )
                    st.session_state[export_state_key] = {
                        "context": context_id,
                        "ready": True,
                        "filename": filename,
                        "csv": csv_content,
                    }
                    st.rerun()


def render_hierarchy_view(expansion_data: Dict):
    """Render hierarchy view section with button-triggered lineage trace."""
    st.markdown("### 🌲 Hierarchy View")

    processed_children = expansion_data.get('processed_children', [])
    if not processed_children:
        st.info("No child codes available for hierarchy view")
        return

    # Count parents and descendants for display
    parent_codes = set(row.get("Parent Code") for row in processed_children if row.get("Parent Code"))
    unique_descendants = set(row.get("Child Code") for row in processed_children if row.get("Child Code"))

    if not parent_codes:
        st.info("No parent codes found in expansion results")
        return

    st.caption(
        f"Build a tree showing all {len(parent_codes)} XML parent codes and their "
        f"{len(unique_descendants)} unique descendants organised by SNOMED lineage."
    )

    hierarchy_warnings = st.session_state.get("full_lineage_trace_warnings", [])
    for warning in hierarchy_warnings:
        st.warning(warning)

    # Check for existing results
    lineage_result: FullLineageTraceResult = st.session_state.get("full_lineage_trace_result")

    col1, col2 = st.columns([1, 5])
    with col1:
        build_clicked = st.button("🌲 Build Hierarchy", type="secondary", key="build_hierarchy_btn")
    with col2:
        progress_placeholder = st.empty()
        status_placeholder = st.empty()

    if build_clicked:
        _run_full_lineage_trace(
            expansion_data,
            progress_placeholder=progress_placeholder,
            status_placeholder=status_placeholder,
        )

    if lineage_result:
        _render_full_lineage_tree(lineage_result)


def _run_full_lineage_trace(
    expansion_data: Dict,
    progress_placeholder=None,
    status_placeholder=None,
):
    """Run lineage trace for all parent codes."""
    st.session_state.full_lineage_trace_warnings = []
    progress_host = progress_placeholder if progress_placeholder is not None else st
    status_host = status_placeholder if status_placeholder is not None else st

    progress_bar = progress_host.progress(0.0)
    status_text = status_host.empty()

    try:
        processed_children = expansion_data.get('processed_children', [])
        expected_descendants = {
            str(row.get("Child Code")).strip()
            for row in processed_children
            if row.get("Child Code")
        }

        client_id = st.secrets.get("NHSTSERVER_ID")
        client_secret = st.secrets.get("NHSTSERVER_TOKEN")
        if not client_id or not client_secret:
            st.error("NHS Terminology Server credentials not configured")
            return

        def on_progress(message: str, current: int, total: int):
            progress_bar.progress(current / total if total > 0 else 0)
            status_text.text(message)

        result = trace_full_lineage(
            processed_children=processed_children,
            include_inactive=expansion_data.get('include_inactive', False),
            max_depth=EXPANSION_HIERARCHY_DEPTH_CAP,
            max_api_calls_per_parent=100,
            max_nodes_per_parent=EXPANSION_HIERARCHY_NODE_CAP_PER_PARENT,
            client_id=client_id,
            client_secret=client_secret,
            progress_callback=on_progress,
        )

        progress_bar.empty()
        status_text.empty()

        if result.error:
            st.error(f"Lineage trace failed: {result.error}")
            return

        if not result.trees:
            st.error("No hierarchy data could be built")
            return

        traced_descendants = set()

        def _collect_descendants(node):
            if getattr(node, "depth", 0) > 0:
                traced_descendants.add(str(node.code))
            for child in node.children or []:
                _collect_descendants(child)

        for tree in result.trees:
            _collect_descendants(tree)

        warnings = []
        truncation_reasons = result.truncation_reasons or {}
        if truncation_reasons:
            depth_limited = sum(
                1 for reason in truncation_reasons.values() if "Depth cap reached" in reason
            )
            api_limited = sum(
                1 for reason in truncation_reasons.values() if "API call cap reached" in reason
            )
            node_limited = sum(
                1 for reason in truncation_reasons.values() if "Node cap reached" in reason
            )

            if depth_limited:
                warnings.append(
                    f"Depth cap applied: {depth_limited} parent(s) reached the depth cap "
                    f"({EXPANSION_HIERARCHY_DEPTH_CAP})."
                )
            if api_limited:
                warnings.append(
                    f"API call cap applied: {api_limited} parent(s) reached the API cap "
                    f"(100 calls per parent)."
                )
            if node_limited:
                warnings.append(
                    f"Node cap applied: {node_limited} parent(s) hit the node cap "
                    f"({EXPANSION_HIERARCHY_NODE_CAP_PER_PARENT}) and were truncated."
                )

            accounted = depth_limited + api_limited + node_limited
            other = len(result.truncated_parent_codes or []) - accounted
            if other > 0:
                warnings.append(f"Hierarchy truncation occurred for {other} additional parent(s).")

        expected_count = len(expected_descendants)
        traced_count = len(traced_descendants)
        if traced_count < expected_count:
            warnings.append(
                f"Hierarchy includes {traced_count} of {expected_count} descendant code(s)."
            )

        st.session_state.full_lineage_trace_result = result
        st.session_state.full_lineage_trace_warnings = warnings
        st.success(
            f"Built hierarchy: {result.parent_count} parents, "
            f"{traced_count}/{expected_count} descendants, "
            f"max depth {result.max_depth_reached}, {result.total_api_calls} API calls"
            + (f", {len(result.shared_lineage_codes)} shared lineage" if result.shared_lineage_codes else "")
        )
        st.rerun()

    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"Lineage trace failed: {str(e)}")


def _render_full_lineage_tree(result: FullLineageTraceResult):
    """Render the combined lineage tree for all parents."""
    if not result.trees:
        st.info("No hierarchy data available")
        return

    def _build_code_display_map(node, mapping):
        mapping[str(node.code)] = node.display or str(node.code)
        for child in node.children or []:
            _build_code_display_map(child, mapping)

    def _collect_flat_nodes(node, bucket):
        bucket.append(node)
        for child in node.children or []:
            _collect_flat_nodes(child, bucket)

    def _get_shared_parents(shared_code: str, display_map: dict, flat_nodes: list) -> list:
        parents = []
        seen = set()
        for node in flat_nodes:
            if str(node.code) != shared_code:
                continue
            parent_code_value = str(node.direct_parent_code or "").strip()
            if not parent_code_value:
                continue
            parent_display = display_map.get(parent_code_value, parent_code_value)
            key = (parent_code_value, parent_display)
            if key in seen:
                continue
            seen.add(key)
            parents.append(key)
        return parents

    def _escape_html(text: str) -> str:
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    # Legend
    st.caption("**Key:** ✓ EMIS GUID found | ❌ Not in EMIS lookup | ⚠️ Shared lineage (multiple parents)")

    # Build combined ASCII tree once (for display + export)
    all_lines = []
    for idx, tree in enumerate(result.trees):
        tree_lines = _build_ascii_lineage_tree(tree, result.shared_lineage_codes, is_root=True)
        all_lines.extend(tree_lines)
        if idx < len(result.trees) - 1:
            all_lines.append("")

    with st.expander("🌲 Full Hierarchy Tree", expanded=True):
        if all_lines:
            st.code("\n".join(all_lines))

            descendant_nodes = max(result.total_nodes - result.parent_count, 0)
            st.caption(
                f"Parents: {result.parent_count} \u00a0|\u00a0 "
                f"Tree nodes: {result.total_nodes} (descendants: {descendant_nodes}) \u00a0|\u00a0 "
                f"Max depth: {result.max_depth_reached} \u00a0|\u00a0 "
                f"API calls: {result.total_api_calls}"
                + (f" \u00a0|\u00a0 Shared lineage: {len(result.shared_lineage_codes)}" if result.shared_lineage_codes else "")
            )

            if result.errors:
                with st.expander(f"⚠️ {len(result.errors)} parents had errors", expanded=False):
                    for err in result.errors[:10]:
                        st.markdown(f"- {err}")
                    if len(result.errors) > 10:
                        st.markdown(f"- ... and {len(result.errors) - 10} more")

    if result.shared_lineage_codes:
        code_display_map = {}
        flat_nodes = []
        for tree in result.trees:
            _build_code_display_map(tree, code_display_map)
            _collect_flat_nodes(tree, flat_nodes)

        with st.container(key="expansion_shared_lineage_scope"):
            # Scope nested expander title tweaks to this section only.
            st.markdown(
                """
                <style>
                .st-key-expansion_shared_lineage_scope div[data-testid="stExpander"] div[data-testid="stExpander"] summary p {
                    font-size: 0.9rem;
                    margin: 0;
                    line-height: 1.2;
                }
                .st-key-expansion_shared_lineage_scope div[data-testid="stExpander"] div[data-testid="stExpander"] summary {
                    min-height: 1.8rem;
                    padding-top: 0.1rem;
                    padding-bottom: 0.1rem;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )
            with st.expander("⚠️ Shared Lineage Codes", expanded=False):
                st.caption(
                    f"{len(result.shared_lineage_codes)} code(s) appear under multiple parent branches."
                )
                for code in sorted(result.shared_lineage_codes):
                    code_str = str(code)
                    code_display = code_display_map.get(code_str, code_str)
                    shared_parents = _get_shared_parents(code_str, code_display_map, flat_nodes)
                    with st.expander(f"{code_str} ({code_display})", expanded=False):
                        if shared_parents:
                            for parent_code_value, parent_display in shared_parents:
                                safe_display = _escape_html(parent_display)
                                st.markdown(
                                    f"- `{parent_code_value}` "
                                    f"<span style='font-size:0.9em;'>({safe_display})</span>",
                                    unsafe_allow_html=True,
                                )
                        else:
                            st.markdown("- Parent lineage unavailable")

    xml_filename = st.session_state.get(SessionStateKeys.XML_FILENAME, "")
    render_lookup_hierarchy_export_controls(
        lines=all_lines,
        parent_code="full_hierarchy",
        json_data=result.to_hierarchical_json(source_filename=xml_filename or None),
    )


def _build_ascii_lineage_tree(
    node,
    shared_codes: List[str],
    prefix: str = "",
    is_last: bool = True,
    is_root: bool = True
) -> List[str]:
    """Build ASCII tree lines from LineageNode in SQL/file-browser style."""
    lines = []

    # Format node display - SQL style: [Depth].[Code].[Display]
    code = node.code
    display = node.display or code
    depth_label = "R" if node.depth == 0 else f"D{node.depth}"

    # Build indicators
    indicators = ""
    if node.inactive:
        indicators += " (inactive)"
    if node.emis_guid:
        if node.emis_guid == "Not in EMIS lookup table":
            indicators += " ❌"
        else:
            indicators += " ✓"
    if code in shared_codes:
        indicators += " ⚠️"

    node_text = f"[{depth_label}].[{code}].[{display}]{indicators}"

    if is_root:
        lines.append(f"🌲 {node_text}")
        # Children of root get initial indent
        child_prefix = "    "
    else:
        connector = "+--" if is_last else "|--"
        lines.append(f"{prefix}{connector} {node_text}")
        child_prefix = prefix + ("      " if is_last else "|     ")

    # Render children
    children = node.children or []

    for idx, child in enumerate(children):
        is_last_child = idx == len(children) - 1
        child_lines = _build_ascii_lineage_tree(
            child,
            shared_codes,
            prefix=child_prefix,
            is_last=is_last_child,
            is_root=False
        )
        lines.extend(child_lines)

    return lines
