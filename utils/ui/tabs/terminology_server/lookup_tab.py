"""
Individual SNOMED Code Lookup

Standalone tool for single concept expansion without XML file.
Works independently from XML processing - useful for testing and ad-hoc lookups.
"""

import gc
import streamlit as st
import pandas as pd

from ...theme import ThemeColours, success_box, warning_box, error_box
from ....caching.lookup_cache import lookup_snomed_to_emis
from ....system.session_state import SessionStateKeys
from ....terminology_server import (
    expand_single_code,
    get_expansion_service,
    lookup_concept_display,
    trace_lineage,
    LineageTraceResult,
)
from ....exports import (
    get_child_code_export_options,
    get_child_code_export_preview,
    build_child_code_export_filename,
    build_child_code_export_csv,
    render_lookup_hierarchy_export_controls,
)

LOOKUP_HIERARCHY_DEPTH_CAP = 10
LOOKUP_HIERARCHY_NODE_CAP = 2000
LOOKUP_HIERARCHY_MAX_API_CALLS_CAP = 600


def render_individual_code_lookup():
    """
    Render standalone code lookup interface

    No XML processing or EMIS lookup required - pure SNOMED expansion
    """

    st.markdown("""<style>[data-testid="stElementToolbar"]{display: none;}</style>""", unsafe_allow_html=True)

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
                        # Determine appropriate message and box type based on error
                        error_lower = lookup_error.lower()
                        if any(phrase in error_lower for phrase in ["not found", "no match", "invalid"]):
                            message = f"⚠️ Code '{snomed_code.strip()}': {lookup_error}"
                            st.markdown(warning_box(message), unsafe_allow_html=True)
                        elif "auth" in error_lower or "credential" in error_lower:
                            st.markdown(error_box(f"❌ {lookup_error}"), unsafe_allow_html=True)
                        elif "connect" in error_lower or "timeout" in error_lower:
                            st.markdown(error_box(f"❌ {lookup_error}"), unsafe_allow_html=True)
                        else:
                            st.markdown(warning_box(f"⚠️ {lookup_error}"), unsafe_allow_html=True)
                        st.session_state.pop(lookup_state_key, None)
                        return

                    # Pass display_name to avoid redundant API lookup
                    result, error = expand_single_code(
                        snomed_code.strip(),
                        include_inactive=include_inactive,
                        use_cache=use_cache,
                        client_id=client_id,
                        client_secret=client_secret,
                        source_display=display_name,
                    )

                    if error:
                        st.markdown(
                            error_box(f"❌ {error}"),
                            unsafe_allow_html=True
                        )
                        st.session_state.pop(lookup_state_key, None)
                        return

                    if result and not result.error:
                        # Collect all child SNOMED codes for batch lookup
                        child_codes = [str(c.code).strip() for c in (result.children or [])]

                        # Batch lookup SNOMED → EMIS (uses TTL cache internally)
                        snomed_code_col = st.session_state.get(SessionStateKeys.SNOMED_CODE_COL, "SNOMED_Code")
                        emis_guid_col = st.session_state.get(SessionStateKeys.EMIS_GUID_COL, "EMIS_GUID")
                        emis_lookup = lookup_snomed_to_emis(
                            child_codes,
                            snomed_code_col=snomed_code_col,
                            emis_guid_col=emis_guid_col,
                        )

                        # Build child data rows
                        child_data = []
                        for c in (result.children or []):
                            code_str = str(c.code).strip()
                            emis_guid = emis_lookup.get(code_str) or "Not in EMIS lookup table"
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

                # Hierarchy View Section
                st.markdown("---")
                _render_lookup_hierarchy_view(parent_code, parent_display, child_rows)

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


def _render_lookup_hierarchy_view(parent_code: str, parent_display: str, child_rows: list):
    """Render hierarchy view for single code lookup results."""
    st.markdown("### 🌲 Hierarchy View")
    st.caption(
        f"Build a tree showing {parent_display} ({parent_code}) and its "
        f"{len(child_rows)} descendants organised by SNOMED lineage."
    )
    
    st.markdown("")
    st.markdown("")
    
    if not child_rows:
        st.info("No child codes available for hierarchy view")
        return

    # Check for existing lineage results
    lineage_key = f"lookup_lineage_{parent_code}"
    lineage_result = st.session_state.get(lineage_key)

    capped_depth = LOOKUP_HIERARCHY_DEPTH_CAP

    col1, col2 = st.columns([1, 3])
    with col1:
        build_clicked = st.button(
            "🌲 Build Hierarchy",
            type="secondary",
            help=f"Trace lineage for {parent_code}",
            key="lookup_build_hierarchy_btn"
        )
    
    with col2:
        progress_placeholder = st.empty()
        status_placeholder = st.empty()

    if build_clicked:
        st.session_state[f"{lineage_key}_warnings"] = []
        _run_lookup_lineage_trace(
            parent_code,
            parent_display,
            child_rows,
            capped_depth,
            lineage_key,
            progress_placeholder=progress_placeholder,
            status_placeholder=status_placeholder,
        )

    lookup_warnings = st.session_state.get(f"{lineage_key}_warnings", [])
    for warning in lookup_warnings:
        st.warning(warning)

    # Display existing results
    if lineage_result:
        _render_lookup_lineage_tree(lineage_result, parent_code)


def _run_lookup_lineage_trace(
    parent_code: str,
    parent_display: str,
    child_rows: list,
    max_depth: int,
    lineage_key: str,
    progress_placeholder=None,
    status_placeholder=None,
):
    """Run lineage trace for lookup results."""
    progress_host = progress_placeholder if progress_placeholder is not None else st
    status_host = status_placeholder if status_placeholder is not None else st
    progress_bar = progress_host.progress(0.0)
    status_text = status_host.empty()

    try:
        # Get credentials
        try:
            client_id = st.secrets["NHSTSERVER_ID"]
            client_secret = st.secrets["NHSTSERVER_TOKEN"]
        except KeyError:
            st.error("NHS Terminology Server credentials not configured")
            return

        # Build lookups from child_rows
        descendant_codes = set()
        emis_lookup = {}
        display_lookup = {}
        inactive_lookup = {}

        for row in child_rows:
            child_code = row.get("Child Code")
            if child_code:
                descendant_codes.add(str(child_code))
                emis_lookup[str(child_code)] = row.get("EMIS GUID")
                display_lookup[str(child_code)] = row.get("Child Display", "")
                inactive_lookup[str(child_code)] = bool(row.get("Inactive"))

        # Progress callback
        def on_progress(message: str, current: int, total: int):
            progress = current / total if total > 0 else 0
            progress_bar.progress(min(progress, 1.0))
            status_text.text(message)

        status_text.text(f"Tracing lineage for {parent_code}...")

        # Scale API call budget with descendant volume to reduce avoidable truncation
        # on broad hierarchies, but keep a hard cap for safety.
        max_api_calls = min(
            max(100, len(descendant_codes) * 3),
            LOOKUP_HIERARCHY_MAX_API_CALLS_CAP,
        )

        result = trace_lineage(
            root_code=parent_code,
            root_display=parent_display,
            descendant_codes=descendant_codes,
            emis_lookup=emis_lookup,
            display_lookup=display_lookup,
            inactive_lookup=inactive_lookup,
            include_inactive=True,
            max_depth=max_depth,
            max_api_calls=max_api_calls,
            max_nodes=LOOKUP_HIERARCHY_NODE_CAP,
            client_id=client_id,
            client_secret=client_secret,
            progress_callback=on_progress,
        )

        progress_bar.empty()
        status_text.empty()

        if result.error:
            st.error(f"Lineage trace failed: {result.error}")
            return

        # Store result
        st.session_state[lineage_key] = result
        warnings = st.session_state.get(f"{lineage_key}_warnings", [])
        if result.truncated:
            truncation_warning = result.truncation_reason or (
                f"Hierarchy was truncated (node cap {LOOKUP_HIERARCHY_NODE_CAP})."
            )
            if truncation_warning not in warnings:
                warnings.append(truncation_warning)
        expected_nodes = len(descendant_codes)
        if not result.truncated and result.total_nodes < expected_nodes:
            coverage_warning = (
                f"Hierarchy includes {result.total_nodes} of {expected_nodes} "
                "descendant code(s)."
            )
            if coverage_warning not in warnings:
                warnings.append(coverage_warning)
        st.session_state[f"{lineage_key}_warnings"] = warnings

        st.success(
            f"Traced {result.total_nodes}/{expected_nodes} nodes, "
            f"max depth {result.max_depth_reached}, "
            f"{result.api_calls_made} API calls"
            + (f", {len(result.shared_lineage_codes)} shared lineage codes" if result.shared_lineage_codes else "")
        )
        st.rerun()

    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"Lineage trace failed: {str(e)}")


def _render_lookup_lineage_tree(result: LineageTraceResult, parent_code: str):
    """Render the lineage tree for lookup results."""
    if not result.tree:
        st.info("No hierarchy data available")
        return

    def _build_code_display_map(node, mapping):
        """Build code -> display lookup from the rendered lineage tree."""
        mapping[str(node.code)] = node.display or str(node.code)
        for child in node.children or []:
            _build_code_display_map(child, mapping)

    def _get_shared_parents(shared_code: str, display_map: dict) -> list:
        """Return unique direct parents for a shared-lineage code."""
        parents = []
        seen = set()
        for node in result.flat_nodes:
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

    # Build tree once, reuse for display and export
    tree_lines = _build_lookup_ascii_tree(result.tree, result.shared_lineage_codes)

    with st.expander(f"🌲 Hierarchy Tree: {parent_code}", expanded=True):
        if tree_lines:
            st.code("\n".join(tree_lines))

            # Stats
            st.caption(
                f"Total nodes: {result.total_nodes} \u00a0|\u00a0 "
                f"Max depth: {result.max_depth_reached} \u00a0|\u00a0 "
                f"API calls: {result.api_calls_made}"
                + (f" \u00a0|\u00a0 Shared lineage: {len(result.shared_lineage_codes)}" if result.shared_lineage_codes else "")
            )

    if result.shared_lineage_codes:
        code_display_map = {}
        _build_code_display_map(result.tree, code_display_map)

        with st.container(key="lookup_shared_lineage_scope"):
            # Scope nested-expander title tweaks to this lookup-tab section only.
            st.markdown(
                """
                <style>
                .st-key-lookup_shared_lineage_scope div[data-testid="stExpander"] div[data-testid="stExpander"] summary p {
                    font-size: 0.9rem;
                    margin: 0;
                    line-height: 1.2;
                }
                .st-key-lookup_shared_lineage_scope div[data-testid="stExpander"] div[data-testid="stExpander"] summary {
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
                    shared_parents = _get_shared_parents(code_str, code_display_map)
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

    render_lookup_hierarchy_export_controls(
        lines=tree_lines,
        parent_code=parent_code,
        json_data=result.to_hierarchical_json(source_filename=f"Individual lookup: {parent_code}"),
    )


def _build_lookup_ascii_tree(
    node,
    shared_codes: list,
    prefix: str = "",
    is_last: bool = True,
    is_root: bool = True
) -> list:
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

    children = node.children or []

    for idx, child in enumerate(children):
        is_last_child = idx == len(children) - 1
        child_lines = _build_lookup_ascii_tree(
            child,
            shared_codes,
            prefix=child_prefix,
            is_last=is_last_child,
            is_root=False
        )
        lines.extend(child_lines)

    return lines
