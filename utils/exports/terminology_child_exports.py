"""
Terminology server child code export helpers.

Keeps export logic out of UI modules and reuses cached expansion results.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
from xml.sax.saxutils import escape

import pandas as pd

from ..terminology_server.expansion_workflow import (
    prepare_child_codes_view,
    build_child_code_exports,
    build_child_code_export_options,
)

_SOURCE_COLUMNS = {"Source Type", "Source Name", "Source Container"}
_EXPORT_COLUMNS = [
    "Parent Code",
    "Parent Display",
    "Child Code",
    "Child Display",
    "EMIS GUID",
    "Inactive",
    "Source Type",
    "Source Name",
    "Source Container",
    "XML Output",
]


def _normalise_view_mode(view_mode: str) -> str:
    mode = (view_mode or "unique").strip().lower()
    return "unique" if mode == "unique" else "per_source"


def _select_export_columns(df: pd.DataFrame, view_mode: str) -> pd.DataFrame:
    mode = _normalise_view_mode(view_mode)
    columns = list(_EXPORT_COLUMNS)
    if mode == "unique":
        columns = [col for col in columns if col not in _SOURCE_COLUMNS]
    available = [col for col in columns if col in df.columns]
    if not available:
        return df
    return df[available]


def _normalise_export_values(df: pd.DataFrame) -> pd.DataFrame:
    if "Inactive" in df.columns:
        df["Inactive"] = df["Inactive"].apply(lambda v: "True" if bool(v) else "False")
    return df


def _build_xml_output(row: pd.Series) -> str:
    guid = str(row.get("EMIS GUID", "") or "").strip()
    if not guid or guid == "Not in EMIS lookup table":
        return ""
    display = str(row.get("Child Display", "") or "").strip()
    return (
        "<values>"
        f"<value>{escape(guid)}</value>"
        f"<displayName>{escape(display)}</displayName>"
        "<includeChildren>false</includeChildren>"
        "</values>"
    )


def _build_filename(export_filter: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = export_filter.lower().replace(" ", "_")
    return f"child_codes_{slug}_{timestamp}.csv"


def build_child_code_export_filename(
    xml_filename: Optional[str],
    export_filter: str,
    view_mode: str,
    export_date: Optional[str] = None,
) -> str:
    """Build export filename using XML base name, filter, mode, and date."""
    base = Path(xml_filename).stem if xml_filename else "child_codes"
    filter_map = {
        "All Child Codes": "all_Children",
        "Only Matched": "matched_Children",
        "Only Unmatched": "unmatched_Children",
    }
    filter_slug = filter_map.get(export_filter, export_filter.replace(" ", "_"))
    mode_slug = "unique" if _normalise_view_mode(view_mode) == "unique" else "per_source"
    date_slug = export_date or datetime.now().strftime("%Y%m%d")
    return f"{base}_{filter_slug}_{mode_slug}_{date_slug}.csv"


def get_child_code_export_preview(
    base_rows: List[Dict[str, Any]],
    export_filter: str,
    view_mode: str,
) -> Tuple[int, int]:
    """Return row and column counts for the current export filter."""
    export_sets = build_child_code_exports(base_rows, view_mode=view_mode)
    rows = export_sets.get(export_filter, [])
    if not rows:
        col_count = len(_select_export_columns(pd.DataFrame(columns=_EXPORT_COLUMNS), view_mode).columns)
        return 0, col_count
    export_df = pd.DataFrame(rows)
    export_df["XML Output"] = export_df.apply(_build_xml_output, axis=1)
    export_df = _select_export_columns(export_df, view_mode)
    return len(export_df), len(export_df.columns)


def get_child_code_export_options(
    all_child_codes: List[Dict[str, Any]],
    view_mode: str,
    include_inactive: bool = True,
) -> Tuple[List[str], Dict[str, int], List[Dict[str, Any]]]:
    """Return export options, summary stats, and base rows for exports."""
    view_data = prepare_child_codes_view(
        all_child_codes,
        search_term="",
        show_inactive=include_inactive,
        view_mode=view_mode,
    )
    base_rows = view_data["rows"]
    options, stats = build_child_code_export_options(base_rows, view_mode=view_mode)
    return options, stats, base_rows


def build_child_code_export_csv(
    base_rows: List[Dict[str, Any]],
    export_filter: str,
    view_mode: str,
    filename: Optional[str] = None,
    xml_filename: Optional[str] = None,
    include_xml_header: bool = True,
) -> Tuple[str, str, pd.DataFrame]:
    """Create CSV content for the selected export filter."""
    export_sets = build_child_code_exports(base_rows, view_mode=view_mode)
    rows = export_sets.get(export_filter, [])
    if not rows:
        return "", "", pd.DataFrame()

    export_df = pd.DataFrame(rows)
    export_df["XML Output"] = export_df.apply(_build_xml_output, axis=1)
    export_df = _select_export_columns(export_df, view_mode)
    export_df = _normalise_export_values(export_df)
    csv_body = export_df.to_csv(index=False, lineterminator="\n").rstrip("\n")
    export_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    metadata_lines = [
        f"# Export Date/Time: {export_datetime}",
        "# Generated by: ClinXML™ EMIS XML Toolkit (https://clinxml.streamlit.app)",
        "#",
    ]
    if include_xml_header:
        xml_label = Path(xml_filename).name if xml_filename else "Unknown"
        metadata_lines.insert(0, f"# Original XML File: {xml_label}")

    csv_content = "\n".join(metadata_lines) + "\n" + csv_body
    resolved_filename = filename or _build_filename(export_filter)
    return resolved_filename, csv_content, export_df
