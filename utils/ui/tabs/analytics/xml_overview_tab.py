"""
XML Overview tab - Processing analytics and quality metrics.

Displays file metrics, structure quality, translation success, and breakdowns
by source/category for the currently loaded XML file.
"""

import streamlit as st
import pandas as pd
from ...theme import info_box, warning_box, success_box
from ..clinical_codes.codes_common import get_unified_clinical_data
from ....system.session_state import SessionStateKeys
from ....metadata.structure_provider import get_structure_metadata
from ....exports.analytics_exports import render_analytics_export_controls


def _rag_box(label: str, value: str, colour: str) -> str:
    return f"""
    <div style="
        background-color: {colour};
        padding: 0.75rem;
        border-radius: 0.5rem;
        color: #FAFAFA;
        text-align: left;
        margin-bottom: 1rem;
    ">
        <strong>{label}:</strong> {value}
    </div>
    """

def render_xml_overview_tab(results=None):
    """
    XML Overview tab showing file metrics, structure quality, translation success,
    and breakdowns by source/category.
    """
    st.markdown("""<style>[data-testid="stElementToolbar"]{display: none;}</style>""", unsafe_allow_html=True)
    @st.fragment
    def analytics_fragment():
        unified_results = get_unified_clinical_data()
        audit_stats = st.session_state.get(SessionStateKeys.AUDIT_STATS)

        # Get entity data from pipeline for proper search/report counting
        entities = st.session_state.get(SessionStateKeys.PIPELINE_ENTITIES, [])

        if not unified_results and not audit_stats:
            st.markdown(info_box("📊 Analytics available after processing an XML file."), unsafe_allow_html=True)
            return

        # Build dataframe from unified pipeline (filter out EMISINTERNAL for display analytics)
        df = None
        full_df = None
        emisinternal_count = 0
        raw_codes = st.session_state.get(SessionStateKeys.PIPELINE_CODES) or []
        code_system_counts = {}

        if unified_results and unified_results.get("all_codes"):
            full_df = pd.DataFrame(unified_results["all_codes"])

        def _bool_series(series: pd.Series) -> pd.Series:
            if series.dtype == object:
                return series.fillna("").astype(str).str.lower().isin(["true", "1", "yes"])
            return series.fillna(False)

        def _code_system_series(frame: pd.DataFrame) -> pd.Series | None:
            if "code_system" in frame.columns:
                return frame["code_system"]
            if "Code System" in frame.columns:
                return frame["Code System"]
            return None

        def _emisinternal_mask(frame: pd.DataFrame) -> pd.Series:
            mask = pd.Series([False] * len(frame), index=frame.index)
            if "is_emisinternal" in frame.columns:
                mask |= _bool_series(frame["is_emisinternal"])
            code_system_series = _code_system_series(frame)
            if code_system_series is not None:
                code_system_norm = code_system_series.fillna("").astype(str).str.upper()
                mask |= code_system_norm.eq("EMISINTERNAL")
            return mask

        if full_df is not None:
            df_mask = _emisinternal_mask(full_df)
            df = full_df[~df_mask].copy()
            emisinternal_count = int(df_mask.sum())

        if raw_codes:
            def _truthy(value) -> bool:
                if isinstance(value, bool):
                    return value
                return str(value).strip().lower() in {"true", "1", "yes"}

            for code in raw_codes:
                code_system = code.get("code_system") or code.get("Code System") or ""
                code_system_norm = str(code_system).strip().upper()
                if code_system_norm:
                    code_system_counts[code_system_norm] = code_system_counts.get(code_system_norm, 0) + 1
                if _truthy(code.get("is_emisinternal")) or code_system_norm == "EMISINTERNAL":
                    emisinternal_count += 1

        st.subheader("📊 Processing Analytics & Quality Metrics")

        # File / processing info from audit stats if present
        if audit_stats and "xml_stats" in audit_stats:
            st.write("### 📁 File Information")
            with st.container(border=True):
                xml_stats = audit_stats["xml_stats"]
                filename = xml_stats.get("filename", "Unknown file")
                file_size_mb = xml_stats.get("file_size_bytes", 0) / (1024 * 1024)
                processing_time = xml_stats.get("processing_time_seconds")
                processed = xml_stats.get("processing_timestamp", "N/A")

                size_colour = "#1F4E3D"
                if file_size_mb > 10:
                    size_colour = "#660022"
                elif file_size_mb > 1:
                    size_colour = "#7A5F0B"

                time_colour = "#1F4E3D"
                if processing_time and processing_time > 120:
                    time_colour = "#660022"
                elif processing_time and processing_time > 60:
                    time_colour = "#7A5F0B"

                st.markdown(_rag_box("Filename", filename, "#28546B"), unsafe_allow_html=True)

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(_rag_box("File Size", f"{xml_stats.get('file_size_bytes', 0):,} bytes ({file_size_mb:.1f} MB)", size_colour), unsafe_allow_html=True)
                with col2:
                    st.markdown(_rag_box("Processing Time", f"{processing_time:.2f}s" if processing_time else "N/A", time_colour), unsafe_allow_html=True)
                with col3:
                    st.markdown(_rag_box("Processed", processed, "#28546B"), unsafe_allow_html=True)

        # XML structure metrics
        if audit_stats and "xml_structure" in audit_stats:
            st.write("### 🗃️ XML Structure Analysis")
            with st.container(border=True):
                xs = audit_stats["xml_structure"]

                # Get search and folder counts from structure metadata
                structure_metadata = get_structure_metadata()
                searches = structure_metadata.get("searches", [])
                reports = structure_metadata.get("reports", [])
                folders = structure_metadata.get("folders", [])

                search_count = len(searches)
                report_count = len(reports)
                folder_count = len(folders)

                # Count report types
                report_types = {}
                for report in reports:
                    rtype = report.get("type_label") or report.get("source_type") or report.get("type") or ""
                    rtype_lower = rtype.lower()
                    if "list" in rtype_lower:
                        report_types["List"] = report_types.get("List", 0) + 1
                    elif "audit" in rtype_lower:
                        report_types["Audit"] = report_types.get("Audit", 0) + 1
                    elif "aggregate" in rtype_lower:
                        report_types["Aggregate"] = report_types.get("Aggregate", 0) + 1
                    elif rtype:
                        report_types["Other"] = report_types.get("Other", 0) + 1

                # Row 1: Total ValueSets, Unique EMIS GUIDs, Total GUID References, Duplication Rate, Folders Found
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.markdown(_rag_box("Total ValueSets", xs.get("total_valuesets", 0), "#1F4E3D"), unsafe_allow_html=True)
                with col2:
                    st.markdown(_rag_box("Unique EMIS GUIDs", f"{xs.get('unique_emis_guids', 0):,}", "#1F4E3D"), unsafe_allow_html=True)
                with col3:
                    st.markdown(_rag_box("Total GUID References", f"{xs.get('total_guid_occurrences', 0):,}", "#28546B"), unsafe_allow_html=True)
                with col4:
                    st.markdown(_rag_box("Duplication Rate", f"{xs.get('duplicate_guid_ratio', 0)}%", "#28546B"), unsafe_allow_html=True)
                with col5:
                    st.markdown(_rag_box("Folders Found", folder_count, "#28546B"), unsafe_allow_html=True)

                # Row 2: Clinical Searches, Reports Found, List Reports, Audit Reports, Aggregate Reports
                col6, col7, col8, col9, col10 = st.columns(5)
                with col6:
                    st.markdown(_rag_box("Clinical Searches", f"{search_count}", "#1F4E3D"), unsafe_allow_html=True)
                with col7:
                    st.markdown(_rag_box("Reports Found", f"{report_count}", "#28546B"), unsafe_allow_html=True)
                with col8:
                    st.markdown(_rag_box("List Reports", report_types.get("List", 0), "#28546B"), unsafe_allow_html=True)
                with col9:
                    st.markdown(_rag_box("Audit Reports", report_types.get("Audit", 0), "#28546B"), unsafe_allow_html=True)
                with col10:
                    st.markdown(_rag_box("Aggregate Reports", report_types.get("Aggregate", 0), "#28546B"), unsafe_allow_html=True)

        # Translation accuracy and mapping success (pipeline)
        if df is not None and not df.empty:
            st.write("### 🎯 Translation & Mapping Success")
            with st.container(border=True):
                def _is_report(row):
                    stype = str(row.get("source_type", "") or "").lower()
                    rtype = str(row.get("report_type", "") or "").lower()
                    return ("report" in stype) or ("report" in rtype and rtype != "search")

                def _is_search(row):
                    stype = str(row.get("source_type", "") or "").lower()
                    rtype = str(row.get("report_type", "") or "").lower()
                    return ("search" in stype) or rtype == "search"

                # Safe column accessors to avoid scalar defaults
                def _col_bool(name: str):
                    if name in df.columns:
                        series = df[name]
                        if series.dtype == object:
                            return series.fillna("").astype(str).str.lower().isin(["true", "1", "yes"])
                        return series.fillna(False)
                    return pd.Series([False] * len(df), index=df.index)

                clinical_mask = (
                    (~_col_bool("is_medication"))
                    & (~_col_bool("is_refset"))
                    & (~_col_bool("is_pseudorefset"))
                )
                meds_mask = _col_bool("is_medication") & (~_col_bool("is_pseudorefset"))
                refset_mask = _col_bool("is_refset") & (~_col_bool("is_pseudorefset"))
                pseudo_member_mask = _col_bool("is_pseudomember")

                def _found(mask):
                    subset = df[mask]
                    found = (subset["Mapping Found"] == "Found").sum() if "Mapping Found" in subset else 0
                    return found, len(subset)

                clinical_found, clinical_total = _found(clinical_mask)
                meds_found, meds_total = _found(meds_mask)
                refset_found, refset_total = _found(refset_mask)
                pseudo_found, pseudo_total = _found(pseudo_member_mask)

                search_series = df.apply(
                    lambda row: "search" in str(row.get("source_type", "")).lower()
                    or str(row.get("report_type", "")).lower() == "search",
                    axis=1,
                )
                report_series = df.apply(
                    lambda row: "report" in str(row.get("source_type", "")).lower()
                    or ("report" in str(row.get("report_type", "")).lower() and str(row.get("report_type", "")).lower() != "search"),
                    axis=1,
                )

                search_mask = clinical_mask & search_series
                report_mask = clinical_mask & report_series
                search_found, search_total = _found(search_mask)
                report_found, report_total = _found(report_mask)

                meds_search_found, meds_search_total = _found(meds_mask & search_series)
                meds_report_found, meds_report_total = _found(meds_mask & report_series)
                refset_search_found, refset_search_total = _found(refset_mask & search_series)
                refset_report_found, refset_report_total = _found(refset_mask & report_series)
                pseudo_search_found, pseudo_search_total = _found(pseudo_member_mask & search_series)
                pseudo_report_found, pseudo_report_total = _found(pseudo_member_mask & report_series)

                r1c1, r1c2, r1c3 = st.columns(3)
                with r1c1:
                    st.markdown(_rag_box("Clinical Codes (All Sources)", f"{clinical_found}/{clinical_total} mapped", "#28546B"), unsafe_allow_html=True)
                with r1c2:
                    st.markdown(_rag_box("Clinical Codes (Searches)", f"{search_found}/{search_total} mapped", "#28546B"), unsafe_allow_html=True)
                with r1c3:
                    st.markdown(_rag_box("Clinical Codes (Reports)", f"{report_found}/{report_total} mapped", "#28546B"), unsafe_allow_html=True)

                r2c1, r2c2, r2c3 = st.columns(3)
                with r2c1:
                    st.markdown(_rag_box("Medications (All Sources)", f"{meds_found}/{meds_total} mapped", "#5B2758"), unsafe_allow_html=True)
                with r2c2:
                    st.markdown(_rag_box("Medications (Searches)", f"{meds_search_found}/{meds_search_total} mapped", "#5B2758"), unsafe_allow_html=True)
                with r2c3:
                    st.markdown(_rag_box("Medications (Reports)", f"{meds_report_found}/{meds_report_total} mapped", "#5B2758"), unsafe_allow_html=True)

                r3c1, r3c2, r3c3 = st.columns(3)
                with r3c1:
                    st.markdown(_rag_box("Pseudo Members (All Sources)", f"{pseudo_found}/{pseudo_total}", "#7A5F0B"), unsafe_allow_html=True)
                with r3c2:
                    st.markdown(_rag_box("Pseudo Members (Searches)", f"{pseudo_search_found}/{pseudo_search_total}", "#7A5F0B"), unsafe_allow_html=True)
                with r3c3:
                    st.markdown(_rag_box("Pseudo Members (Reports)", f"{pseudo_report_found}/{pseudo_report_total}", "#7A5F0B"), unsafe_allow_html=True)

        # Unified data breakdowns (code systems, mapping, sources, quality)
        if df is not None and not df.empty:
            c1, c2 = st.columns([2.1, 1])
            with c1:
                st.write("### ✅ Quality Indicators")
                with st.container(border=True):
                    # Quality indicators
                    include_children = df.get("include_children")
                    has_children = int(include_children.sum()) if include_children is not None else 0

                    has_qualifier_col = None
                    for candidate in ["Has Qualifier", "standardized_has_qualifier", "lookup_has_qualifier"]:
                        if candidate in df.columns:
                            has_qualifier_col = df[candidate]
                            break
                    qualifier_true = 0
                    if has_qualifier_col is not None:
                        qualifier_true = sum(str(v).lower() in ["true", "1"] for v in has_qualifier_col)

                    display_names = 0
                    total_codes = len(df)
                    if "xml_display_name" in df.columns:
                        display_names = df["xml_display_name"].apply(
                            lambda v: bool(v) and str(v).strip().lower() not in ["n/a", "no display name in xml", ""]
                        ).sum()

                    display_pct = (display_names / total_codes * 100) if total_codes > 0 else 0

                    # Check Title Case column names (as used in unified data)
                    table_ctx = 0
                    if "Table Context" in df.columns:
                        table_ctx = df["Table Context"].apply(
                            lambda v: bool(v) and str(v).strip().upper() not in ["N/A", ""]
                        ).sum()

                    column_ctx = 0
                    if "Column Context" in df.columns:
                        column_ctx = df["Column Context"].apply(
                            lambda v: bool(v) and str(v).strip().upper() not in ["N/A", ""]
                        ).sum()

                    # Calculate percentages for RAG rating
                    table_ctx_pct = (table_ctx / total_codes * 100) if total_codes > 0 else 0
                    column_ctx_pct = (column_ctx / total_codes * 100) if total_codes > 0 else 0

                    # RAG rating function
                    def _rag_colour(percentage):
                        if percentage >= 100:
                            return "#1F4E3D"  # Green
                        elif percentage >= 80:
                            return "#7A5F0B"  # Amber
                        else:
                            return "#660022"  # Red

                    # 2-column, 3-row grid
                    qc1, qc2 = st.columns(2)
                    with qc1:
                        st.markdown(_rag_box("Codes With 'Include Children = True'", has_children, "#28546B"), unsafe_allow_html=True)
                    with qc2:
                        st.markdown(_rag_box("Codes Flagged With Qualifiers", qualifier_true, "#28546B"), unsafe_allow_html=True)

                    qc3, qc4 = st.columns(2)
                    with qc3:
                        display_colour = _rag_colour(display_pct)
                        st.markdown(_rag_box("Display Names Present", f"{display_names} ({display_pct:.0f}%)", display_colour), unsafe_allow_html=True)
                    with qc4:
                        st.markdown(_rag_box("EMISINTERNAL Codes (Excluded)", emisinternal_count, "#660022"), unsafe_allow_html=True)

                    qc5, qc6 = st.columns(2)
                    with qc5:
                        table_colour = _rag_colour(table_ctx_pct)
                        st.markdown(_rag_box("Table Context Available", f"{table_ctx} ({table_ctx_pct:.0f}%)", table_colour), unsafe_allow_html=True)
                    with qc6:
                        column_colour = _rag_colour(column_ctx_pct)
                        st.markdown(_rag_box("Column Context Available", f"{column_ctx} ({column_ctx_pct:.0f}%)", column_colour), unsafe_allow_html=True)

            with c2:
                st.write("### ⚙️ Breakdown & Quality")
                with st.container(border=True):
                    st.caption("Code System Distribution (Unique ValueSet GUID + Code pairs)")
                    if code_system_counts:
                        dist = pd.DataFrame(
                            sorted(code_system_counts.items(), key=lambda item: item[1], reverse=True),
                            columns=["Code System", "Count"],
                        )
                        st.dataframe(dist, width="stretch")
                    elif full_df is not None:
                        code_system_series = _code_system_series(full_df)
                        if code_system_series is not None:
                            dist = code_system_series.value_counts().reset_index()
                            dist.columns = ["Code System", "Count"]
                            st.dataframe(dist, width="stretch")

        else:
            st.markdown(warning_box("No analytics data available for this file."), unsafe_allow_html=True)

        # Build export data dictionary
        analytics_export_data = {}

        if audit_stats:
            analytics_export_data = {
                "xml_stats": audit_stats.get("xml_stats", {}),
                "xml_structure": audit_stats.get("xml_structure", {}),
                "search_count": 0,
                "report_count": 0,
                "folder_count": 0,
                "report_types": {},
                "translation_stats": {},
                "quality_indicators": {},
                "code_system_distribution": {},
                "emisinternal_count": int(emisinternal_count),
            }

            # Add structure data if available
            if audit_stats.get("xml_structure"):
                structure_metadata = get_structure_metadata()
                searches = structure_metadata.get("searches", [])
                reports = structure_metadata.get("reports", [])
                folders = structure_metadata.get("folders", [])

                # Count report types
                report_types = {}
                for report in reports:
                    rtype = report.get("type_label") or report.get("source_type") or report.get("type") or ""
                    rtype_lower = rtype.lower()
                    if "list" in rtype_lower:
                        report_types["List"] = report_types.get("List", 0) + 1
                    elif "audit" in rtype_lower:
                        report_types["Audit"] = report_types.get("Audit", 0) + 1
                    elif "aggregate" in rtype_lower:
                        report_types["Aggregate"] = report_types.get("Aggregate", 0) + 1

                analytics_export_data["search_count"] = len(searches)
                analytics_export_data["report_count"] = len(reports)
                analytics_export_data["folder_count"] = len(folders)
                analytics_export_data["report_types"] = report_types

            # Add translation stats if df available
            if df is not None and not df.empty:
                # Recalculate translation stats for export
                def _col_bool(name: str):
                    if name in df.columns:
                        series = df[name]
                        if series.dtype == object:
                            return series.fillna("").astype(str).str.lower().isin(["true", "1", "yes"])
                        return series.fillna(False)
                    return pd.Series([False] * len(df), index=df.index)

                clinical_mask = (
                    (~_col_bool("is_medication"))
                    & (~_col_bool("is_refset"))
                    & (~_col_bool("is_pseudorefset"))
                )
                meds_mask = _col_bool("is_medication") & (~_col_bool("is_pseudorefset"))
                refset_mask = _col_bool("is_refset") & (~_col_bool("is_pseudorefset"))
                pseudo_member_mask = _col_bool("is_pseudomember")

                def _found(mask):
                    subset = df[mask]
                    found = (subset["Mapping Found"] == "Found").sum() if "Mapping Found" in subset else 0
                    return found, len(subset)

                clinical_found, clinical_total = _found(clinical_mask)
                meds_found, meds_total = _found(meds_mask)
                refset_found, refset_total = _found(refset_mask)
                pseudo_found, pseudo_total = _found(pseudo_member_mask)

                search_series = df.apply(
                    lambda row: "search" in str(row.get("source_type", "")).lower()
                    or str(row.get("report_type", "")).lower() == "search",
                    axis=1,
                )
                report_series = df.apply(
                    lambda row: "report" in str(row.get("source_type", "")).lower()
                    or ("report" in str(row.get("report_type", "")).lower() and str(row.get("report_type", "")).lower() != "search"),
                    axis=1,
                )
                search_mask = clinical_mask & search_series
                report_mask = clinical_mask & report_series
                search_found, search_total = _found(search_mask)
                report_found, report_total = _found(report_mask)
                meds_search_found, meds_search_total = _found(meds_mask & search_series)
                meds_report_found, meds_report_total = _found(meds_mask & report_series)
                pseudo_search_found, pseudo_search_total = _found(pseudo_member_mask & search_series)
                pseudo_report_found, pseudo_report_total = _found(pseudo_member_mask & report_series)

                analytics_export_data["translation_stats"] = {
                    "clinical_found": int(clinical_found),
                    "clinical_total": int(clinical_total),
                    "search_found": int(search_found),
                    "search_total": int(search_total),
                    "report_found": int(report_found),
                    "report_total": int(report_total),
                    "meds_found": int(meds_found),
                    "meds_total": int(meds_total),
                    "meds_search_found": int(meds_search_found),
                    "meds_search_total": int(meds_search_total),
                    "meds_report_found": int(meds_report_found),
                    "meds_report_total": int(meds_report_total),
                    "refset_found": int(refset_found),
                    "refset_total": int(refset_total),
                    "pseudo_found": int(pseudo_found),
                    "pseudo_total": int(pseudo_total),
                    "pseudo_search_found": int(pseudo_search_found),
                    "pseudo_search_total": int(pseudo_search_total),
                    "pseudo_report_found": int(pseudo_report_found),
                    "pseudo_report_total": int(pseudo_report_total),
                }

                # Quality indicators
                include_children = df.get("include_children")
                has_children = int(include_children.sum()) if include_children is not None else 0

                has_qualifier_col = None
                for candidate in ["Has Qualifier", "standardized_has_qualifier", "lookup_has_qualifier"]:
                    if candidate in df.columns:
                        has_qualifier_col = df[candidate]
                        break
                qualifier_true = 0
                if has_qualifier_col is not None:
                    qualifier_true = sum(str(v).lower() in ["true", "1"] for v in has_qualifier_col)

                display_names = 0
                total_codes = len(df)
                if "xml_display_name" in df.columns:
                    display_names = df["xml_display_name"].apply(
                        lambda v: bool(v) and str(v).strip().lower() not in ["n/a", "no display name in xml", ""]
                    ).sum()

                display_pct = (display_names / total_codes * 100) if total_codes > 0 else 0

                table_ctx = 0
                if "Table Context" in df.columns:
                    table_ctx = df["Table Context"].apply(
                        lambda v: bool(v) and str(v).strip().upper() not in ["N/A", ""]
                    ).sum()

                column_ctx = 0
                if "Column Context" in df.columns:
                    column_ctx = df["Column Context"].apply(
                        lambda v: bool(v) and str(v).strip().upper() not in ["N/A", ""]
                    ).sum()

                table_ctx_pct = (table_ctx / total_codes * 100) if total_codes > 0 else 0
                column_ctx_pct = (column_ctx / total_codes * 100) if total_codes > 0 else 0

                analytics_export_data["quality_indicators"] = {
                    "has_children": int(has_children),
                    "qualifier_true": int(qualifier_true),
                    "display_names": int(display_names),
                    "display_pct": float(display_pct),
                    "table_ctx": int(table_ctx),
                    "table_ctx_pct": float(table_ctx_pct),
                    "column_ctx": int(column_ctx),
                    "column_ctx_pct": float(column_ctx_pct),
                }

                # Code system distribution
                if code_system_counts:
                    analytics_export_data["code_system_distribution"] = {
                        k: int(v) for k, v in code_system_counts.items()
                    }
                elif full_df is not None:
                    code_system_series = _code_system_series(full_df)
                    if code_system_series is not None:
                        code_system_dist = {k: int(v) for k, v in code_system_series.value_counts().to_dict().items()}
                        analytics_export_data["code_system_distribution"] = code_system_dist

        # Render export controls
        render_analytics_export_controls(analytics_export_data)

    analytics_fragment()
