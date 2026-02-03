"""
Individual SNOMED Code Lookup

Standalone tool for single concept expansion without XML file.
Works independently from XML processing - useful for testing and ad-hoc lookups.
"""

import gc
import streamlit as st
import pandas as pd

from ...theme import ThemeColours, success_box, warning_box, error_box
from ....caching.lookup_cache import get_cached_emis_lookup
from ....system.session_state import SessionStateKeys
from ....terminology_server import expand_single_code, get_expansion_service, lookup_concept_display
from ....exports import (
    get_child_code_export_options,
    get_child_code_export_preview,
    build_child_code_export_filename,
    build_child_code_export_csv,
)


def render_individual_code_lookup():
    """
    Render standalone code lookup interface

    No XML processing or EMIS lookup required - pure SNOMED expansion
    """
    @st.fragment
    def code_lookup_fragment():
        st.markdown("### 🔬 Individual SNOMED Code Lookup")
        st.markdown("""
        Test individual SNOMED concept expansion without loading XML files.
        Useful for:
        - Testing NHS Terminology Server connectivity
        - Exploring SNOMED hierarchies
        - Validating concept codes
        """)
        st.markdown("---")

        # Input controls
        col1, col2, col3, col4 = st.columns([1, 0.4, 0.4, 1])
        lookup_state_key = "lookup_child_codes_state"

        with col1:
            snomed_code = st.text_input(
                "SNOMED CT Code",
                placeholder="e.g., 73211009",
                help="Enter a SNOMED CT concept code to expand",
                icon="🔍"
            )

        with col2:
            st.markdown('<p style="font-size: 0.1rem; font-weight: 600; margin-top: 0; margin-bottom: 1.5rem;"> </p>', unsafe_allow_html=True)
            lookup_clicked = st.button("🔍 Lookup Code", type="secondary")

        with col3:
            st.markdown("")
            st.markdown("")
            include_inactive = st.checkbox(
                "Include inactive",
                value=False,
                help="Include inactive/deprecated concepts"
            )

        with col4:
            st.markdown("")
            st.markdown("")
            use_cache = st.checkbox(
                "Use cache",
                value=True,
                help="Use cached results if available"
            )

        if lookup_clicked:
            if not snomed_code.strip():
                st.warning("⚠️ Please enter a SNOMED code")
                return

            st.session_state.pop(lookup_state_key, None)
            st.session_state.pop("lookup_child_codes_export_state", None)

            try:
                with st.spinner(f"Looking up {snomed_code}..."):
                    # Configure credentials
                    try:
                        client_id = st.secrets["NHSTSERVER_ID"]
                        client_secret = st.secrets["NHSTSERVER_TOKEN"]
                    except KeyError:
                        st.error("❌ NHS Terminology Server credentials not configured. Please add NHSTSERVER_ID and NHSTSERVER_TOKEN to secrets.")
                        return

                    display_name, lookup_error = lookup_concept_display(
                        snomed_code.strip(),
                        client_id=client_id,
                        client_secret=client_secret,
                    )
                    if lookup_error:
                        if "Resource not found" in lookup_error:
                            message = f"⚠️ No match found for code {snomed_code.strip()}"
                        else:
                            message = f"⚠️ {lookup_error}"
                        st.markdown(
                            warning_box(message),
                            unsafe_allow_html=True
                        )
                        st.session_state.pop(lookup_state_key, None)
                        return

                    result, error = expand_single_code(
                        snomed_code.strip(),
                        include_inactive=include_inactive,
                        use_cache=use_cache,
                        client_id=client_id,
                        client_secret=client_secret,
                    )

                    if error:
                        st.markdown(
                            error_box(f"❌ {error}"),
                            unsafe_allow_html=True
                        )
                        st.session_state.pop(lookup_state_key, None)
                        return

                    if result and not result.error:
                        from ....caching.lookup_manager import is_lookup_loaded
                        snomed_code_col = st.session_state.get(SessionStateKeys.SNOMED_CODE_COL, "SNOMED Code")
                        emis_guid_col = st.session_state.get(SessionStateKeys.EMIS_GUID_COL, "EMIS GUID")
                        version_info = st.session_state.get(SessionStateKeys.LOOKUP_VERSION_INFO, {})
                        emis_lookup = {}
                        if is_lookup_loaded():
                            cached_data = get_cached_emis_lookup(
                                None,  # No longer needed - reads from session state
                                snomed_code_col=snomed_code_col,
                                emis_guid_col=emis_guid_col,
                                version_info=version_info
                            )
                            if cached_data:
                                emis_lookup = cached_data.get("lookup_mapping", {}) or {}

                        child_data = []
                        if result.children:
                            for c in result.children:
                                emis_guid = emis_lookup.get(str(c.code).strip()) or "Not in EMIS lookup table"
                                child_data.append({
                                    "Parent Code": snomed_code.strip(),
                                    "Parent Display": display_name or result.source_display,
                                    "Child Code": c.code,
                                    "Child Display": c.display,
                                    "EMIS GUID": emis_guid,
                                    "Inactive": bool(c.inactive),
                                })

                        st.session_state[lookup_state_key] = {
                            "parent_code": snomed_code.strip(),
                            "parent_display": display_name or result.source_display,
                            "child_rows": child_data,
                        }
                    elif result and result.error:
                        st.markdown(
                            error_box(f"❌ Error: {result.error}"),
                            unsafe_allow_html=True
                        )
                        st.session_state.pop(lookup_state_key, None)
                    else:
                        st.markdown(
                            error_box("❌ No result returned from server"),
                            unsafe_allow_html=True
                        )
                        st.session_state.pop(lookup_state_key, None)

            except Exception as e:
                st.markdown(
                    error_box(f"❌ Lookup failed: {str(e)}"),
                    unsafe_allow_html=True
                )
                st.session_state.pop(lookup_state_key, None)

        lookup_state = st.session_state.get(lookup_state_key)
        if lookup_state:
            parent_code = lookup_state.get("parent_code", "")
            parent_display = lookup_state.get("parent_display", "")
            child_rows = lookup_state.get("child_rows", []) or []

            st.markdown(
                success_box(f"✅ Found: **{parent_display}**"),
                unsafe_allow_html=True
            )

            if child_rows:
                st.markdown(f"### {len(child_rows)} Child Concepts")

                child_df = pd.DataFrame(child_rows)
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

                with st.expander("📥 Export Options", expanded=True):
                    export_options, export_stats, base_rows = get_child_code_export_options(
                        child_rows,
                        view_mode="unique",
                        include_inactive=True
                    )

                    col1, col2 = st.columns([1, 2])
                    with col1:
                        export_filter = st.radio(
                            "Export Filter:",
                            export_options,
                            key="lookup_child_codes_export_filter",
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
                        view_mode="unique"
                    )

                    with col2:
                        st.caption(f"📊 Will generate CSV with {row_count} rows × {col_count} columns")

                        label_map = {
                            "All Child Codes": "All Child Codes",
                            "Only Matched": "All Matched Child Codes",
                            "Only Unmatched": "All Unmatched Child Codes",
                        }
                        label_base = label_map.get(export_filter, export_filter)
                        mode_label = "Unique"
                        context_id = f"{parent_display}|{export_filter}"
                        export_state_key = "lookup_child_codes_export_state"
                        export_state = st.session_state.get(export_state_key, {})
                        if export_state.get("context") != context_id:
                            export_state = {"context": context_id, "ready": False, "filename": "", "csv": ""}
                            st.session_state[export_state_key] = export_state

                        export_filename = export_state.get("filename") or build_child_code_export_filename(
                            parent_display or parent_code,
                            export_filter=export_filter,
                            view_mode="unique"
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
                                key="lookup_child_codes_export_download"
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
                                key="lookup_child_codes_export_generate"
                            )
                            if generate_clicked:
                                filename, csv_content, export_df = build_child_code_export_csv(
                                    base_rows,
                                    export_filter=export_filter,
                                    view_mode="unique",
                                    filename=export_filename,
                                    xml_filename=parent_display or parent_code,
                                    include_xml_header=False,
                                )
                                st.session_state[export_state_key] = {
                                    "context": context_id,
                                    "ready": True,
                                    "filename": filename,
                                    "csv": csv_content,
                                }
                                st.rerun()

            else:
                st.info("📍 No child concepts found (this may be a leaf node)")

        # Help section
        with st.expander("ℹ️ Help & Examples"):
            st.markdown('<p style="font-size: 1.2rem; font-weight: 600; margin-top: 0; margin-bottom: 0.5rem;">Common SNOMED CT Concepts to Try</p>', unsafe_allow_html=True)
            st.markdown("""
            <div style="font-size: 0.9rem;">

            | Code | Description |
            |------|-------------|
            | 73211009 | Diabetes mellitus |
            | 38341003 | Hypertension |
            | 13644009 | Hypercholesterolemia |
            | 195967001 | Asthma |

            </div>
            """, unsafe_allow_html=True)
            st.markdown('<p style="font-size: 1.2rem; font-weight: 600; margin-top: 1rem; margin-bottom: 0.5rem;">About SNOMED CT Expansion</p>', unsafe_allow_html=True)
            st.markdown("""
            <div style="font-size: 0.9rem;">

            The NHS Terminology Server uses SNOMED CT's hierarchical structure to expand
            parent concepts into all child concepts. For example:

            - **Diabetes mellitus (73211009)** expands to include:
              - Type 1 diabetes
              - Type 2 diabetes
              - Gestational diabetes
              - And many other specific types

            </div>
            """, unsafe_allow_html=True)

    code_lookup_fragment()
