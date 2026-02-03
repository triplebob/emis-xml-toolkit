"""
Shared report viewer UI components.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import streamlit as st

from ....metadata.report_provider import get_report_metadata
from ....metadata.description_generators import format_base_population
from ...theme import ThemeColours, create_info_box_style
from ..search_browser.search_criteria_viewer import render_criterion_detail
from ...tab_helpers import build_folder_option_list
from ....metadata.value_set_resolver import resolve_value_sets
from ....exports.report_excel import build_report_excel
from ....exports.report_json import build_report_json
from ....exports.report_export_common import build_report_filename
from ....system.session_state import SessionStateKeys


@st.cache_data(ttl=600, max_entries=1)
def _build_snomed_lookup(file_hash: str, codes_count: int) -> Dict[str, str]:
    """Cached SNOMED lookup builder - invalidates on file change."""
    ui_rows = st.session_state.get(SessionStateKeys.PIPELINE_CODES, [])
    if not ui_rows:
        return {}
    lookup: Dict[str, str] = {}
    for row in ui_rows:
        emis_guid = row.get("emis_guid") or row.get("EMIS GUID") or ""
        snomed_code = row.get("SNOMED Code") or row.get("snomed_code") or ""
        if emis_guid and snomed_code:
            lookup[emis_guid] = str(snomed_code)
    return lookup


def get_enriched_snomed_lookup() -> Dict[str, str]:
    """
    Build a lightweight SNOMED lookup from pre-enriched pipeline data.
    Uses PIPELINE_CODES which already has SNOMED codes from enrichment.
    Much smaller than full lookup table (only codes in current file).
    """
    file_hash = st.session_state.get("last_processed_hash") or st.session_state.get("current_file_hash") or ""
    codes = st.session_state.get(SessionStateKeys.PIPELINE_CODES, [])
    return _build_snomed_lookup(file_hash, len(codes))


def _sort_key(report: Dict[str, Any]) -> str:
    return (report.get("name") or "").lower()


def _filter_by_folder(reports: List[Dict[str, Any]], folder_id: str) -> List[Dict[str, Any]]:
    if not folder_id:
        return reports
    return [r for r in reports if r.get("folder_id") == folder_id]


def render_report_status_box(text: str) -> None:
    st.markdown(create_info_box_style(ThemeColours.BLUE, text), unsafe_allow_html=True)


def _lookup_snomed(emis_guid: str) -> str:
    """Look up SNOMED code from pre-enriched pipeline data (no heavy dictionary building)."""
    if not emis_guid:
        return ""
    lookup = get_enriched_snomed_lookup()
    return lookup.get(emis_guid, "")


def render_report_selector(
    report_type: str,
    label: str,
    key_prefix: str,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    metadata = get_report_metadata()
    reports = metadata.get("report_breakdown", {}).get(report_type, [])
    folders = metadata.get("folders", [])

    if not reports:
        render_report_status_box(f"No {label}s found in this XML file.")
        return None, metadata, ""

    st.markdown("")
    col1, col2 = st.columns([3, 4])

    with col1:
        folder_options = build_folder_option_list(reports, folders, all_label="All Folders inc Root")
        selected_folder = st.selectbox(
            "📁 Folder",
            options=folder_options,
            format_func=lambda x: x["label"],
            key=f"{key_prefix}_folder",
        )
        folder_id = "" if selected_folder["value"] == "__all__" else selected_folder["value"]

    filtered_reports = _filter_by_folder(reports, folder_id)
    filtered_reports.sort(key=_sort_key)

    with col2:
        if filtered_reports:
            report_labels = [r.get("name") or r.get("id") or "Unnamed" for r in filtered_reports]
            stored = st.session_state.get(f"{key_prefix}_selected_name")
            default_index = report_labels.index(stored) if stored in report_labels else 0
            selected_label = st.selectbox(
                f"📊 {label}",
                report_labels,
                index=default_index,
                key=f"{key_prefix}_report",
            )
            st.session_state[f"{key_prefix}_selected_name"] = selected_label
            selected_report = next((r for r in filtered_reports if (r.get("name") or r.get("id")) == selected_label), None)
        else:
            st.selectbox(
                f"📊 {label}",
                ["No reports in selected folder"],
                disabled=True,
                key=f"{key_prefix}_report_disabled",
            )
            selected_report = None

    if folder_id:
        status_text = f"📋 Showing {len(filtered_reports)} {label.lower()}s in selected folder."
    else:
        status_text = f"📋 Showing {len(filtered_reports)} {label.lower()}s across all folders."

    return selected_report, metadata, status_text


def render_report_metadata(report: Dict[str, Any], id_to_name: Dict[str, str]) -> None:
    st.markdown("")
    st.subheader(f"📊 {report.get('name') or 'Unnamed report'}")
    description = report.get("description") or ""
    if description:
        with st.container(border=True):
            st.markdown(f"<i>{description}</i>", unsafe_allow_html=True)

    parent_guid = report.get("parent_guid") or ""
    if parent_guid:
        parent_name = id_to_name.get(parent_guid, "Unknown")
        population_text = f"🟠 <strong>Child Report!</strong> Parent Search: {parent_name}"
    else:
        parent_type = (
            report.get("parent_type")
            or report.get("parentType")
            or (report.get("flags") or {}).get("parent_type")
            or (report.get("flags") or {}).get("parentType")
        )
        base_pop_text = format_base_population(parent_type)
        population_text = f"<strong>Base Population:</strong> {base_pop_text}"

    info_col1, info_col2 = st.columns([3, 1.5])
    with info_col1:
        st.markdown(create_info_box_style(ThemeColours.BLUE, population_text), unsafe_allow_html=True)
    with info_col2:
        report_id = report.get("id") or "Unknown"
        st.markdown(
            create_info_box_style(
                ThemeColours.PURPLE,
                f"<strong>Report GUID:</strong> {report_id}",
            ),
            unsafe_allow_html=True,
        )

    _ = id_to_name


def render_report_export_controls(
    report: Dict[str, Any],
    key_prefix: str,
    id_to_name: Optional[Dict[str, str]] = None,
) -> None:
    with st.expander("Export Options", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            _render_export_button(
                report,
                key_prefix,
                "xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                id_to_name,
            )
        with col2:
            _render_export_button(report, key_prefix, "json", "application/json", id_to_name)
    st.markdown("")


def _render_export_button(
    report: Dict[str, Any],
    key_prefix: str,
    export_type: str,
    mime: str,
    id_to_name: Optional[Dict[str, str]] = None,
) -> None:
    state_key = f"{key_prefix}_{export_type}_state"
    context_id = f"{export_type}|{report.get('id') or ''}"
    state = _init_export_state(state_key, context_id)

    generate_label = f"🔄 Export Report ({export_type.upper()})"
    download_label = f"📥 Download Report ({export_type.upper()})"
    filename_preview = build_report_filename(report, "report", export_type)

    if state.get("ready"):
        if state.get("size_mb") and state["size_mb"] > 50:
            st.warning(f"Large file: {state['size_mb']:.1f}MB. Download may take time.")
        download_help = f"Start Download: {state.get('filename') or filename_preview}"
        downloaded = st.download_button(
            download_label,
            data=state.get("payload") or "",
            file_name=state.get("filename") or filename_preview,
            mime=mime,
            help=download_help,
            key=f"{state_key}_download",
            width="stretch",
        )
        if downloaded:
            st.session_state.pop(state_key, None)
            import gc
            gc.collect()
            st.rerun()
        return

    generate_help = f"Generate: {filename_preview}"
    generate_clicked = st.button(
        generate_label,
        help=generate_help or None,
        key=f"{state_key}_generate",
        width="stretch",
    )
    if generate_clicked:
        with st.spinner(f"Generating {export_type.upper()}..."):
            try:
                filename, payload = _build_export_payload(
                    report,
                    export_type,
                    id_to_name,
                    filename_override=filename_preview,
                )
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


def _build_export_payload(
    report: Dict[str, Any],
    export_type: str,
    id_to_name: Optional[Dict[str, str]] = None,
    filename_override: Optional[str] = None,
) -> tuple[str, Any]:
    if export_type == "xlsx":
        filename, payload = build_report_excel(report, id_to_name)
        return filename_override or filename, payload
    filename, payload = build_report_json(report, id_to_name)
    return filename_override or filename, payload


def render_criteria_list(
    criteria: List[Dict[str, Any]],
    title: str,
    key_prefix: str,
    show_title: bool = True,
) -> None:
    if not criteria:
        if show_title:
            st.markdown(create_info_box_style(ThemeColours.BLUE, f"No {title.lower()} found."), unsafe_allow_html=True)
        return

    if show_title:
        st.markdown(f"### {title}")
    for idx, criterion in enumerate(criteria, start=1):
        flags = criterion.get("flags") or {}
        display_name = flags.get("display_name") or f"Criterion {idx}"
        with st.expander(f"{idx}. {display_name}", expanded=False):
            table = flags.get("logical_table_name") or ""
            if table:
                st.caption(f"Table: {table}")
            column_names = flags.get("column_name") or []
            if column_names:
                st.caption(f"Columns: {', '.join(column_names)}")
            if flags.get("negation") is True:
                st.caption("Action: Exclude")
            elif flags.get("negation") is False:
                st.caption("Action: Include")
            description = flags.get("description") or ""
            if description:
                st.caption(description)

            _render_column_filters(criterion.get("column_filters") or [])
            _render_value_sets(resolve_value_sets(criterion))


def _render_column_filters(filters: List[Dict[str, Any]]) -> None:
    if not filters:
        return
    rows = []
    for entry in filters:
        rows.append(
            {
                "Column": entry.get("column") or "",
                "Display": entry.get("display_name") or "",
                "In/Not In": entry.get("in_not_in") or "",
                "Range": _format_range(entry.get("range_info") or {}),
            }
        )
    if rows:
        st.markdown("**Column Filters**")
        st.dataframe(rows, hide_index=True, width="stretch")


def _render_value_sets(value_sets: List[Dict[str, Any]]) -> None:
    if not value_sets:
        return
    rows = []
    for entry in value_sets:
        code_value = entry.get("code_value") or ""
        snomed_code = ""
        if entry.get("is_refset"):
            snomed_code = code_value
        else:
            snomed_code = _lookup_snomed(code_value)
        rows.append(
            {
                "Value Set": entry.get("valueSet_description") or "",
                "Code System": entry.get("code_system") or "",
                "EMIS GUID": code_value,
                "SNOMED Code": snomed_code,
                "Description": entry.get("display_name") or "",
                "Include Children": bool(entry.get("include_children")),
                "Refset": bool(entry.get("is_refset")),
                "Inactive": bool(entry.get("inactive")),
            }
        )
    if rows:
        st.markdown("**Value Sets**")
        st.dataframe(rows, hide_index=True, width="stretch")


def _format_range(range_info: Dict[str, Any]) -> str:
    if not range_info:
        return ""
    start = range_info.get("from") or {}
    end = range_info.get("to") or {}
    parts = []
    if start:
        start_val = start.get("value") or ""
        if start_val:
            parts.append(f">= {start_val}")
    if end:
        end_val = end.get("value") or ""
        if end_val:
            parts.append(f"<= {end_val}")
    return " and ".join(parts)


def render_report_criteria_blocks(
    criteria: List[Dict[str, Any]],
    report_name: str,
    report_id: Optional[str],
    title: str,
    summary: str,
) -> None:
    if not criteria:
        return

    st.markdown(f"### {title}")
    st.markdown(summary)
    for criterion in criteria:
        criterion["_group_criteria"] = criteria
    for idx, criterion in enumerate(criteria, start=1):
        render_criterion_detail(criterion, idx - 1, report_name, report_id, 0)
