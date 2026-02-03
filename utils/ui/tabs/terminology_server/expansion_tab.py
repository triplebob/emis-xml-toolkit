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
)
from ....exports import (
    get_child_code_export_options,
    get_child_code_export_preview,
    build_child_code_export_filename,
    build_child_code_export_csv,
)


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

    col1, col2, col3 = st.columns([6, 1, 1])
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

    with st.expander("📥 Export Options", expanded=False):
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
