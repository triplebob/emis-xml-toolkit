"""
Lightweight export helpers for UI components.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import re

import pandas as pd
import streamlit as st

from .search_excel import generate_search_excel
from .search_json import export_search_json, export_full_structure_json


class UIExportManager:
    """Minimal export manager for UI download buttons."""

    def __init__(self, analysis: Optional[Any] = None):
        self.analysis = analysis

    def render_download_button(
        self,
        data: Any,
        label: str,
        filename_prefix: str,
        xml_filename: Optional[str] = None,
        key: Optional[str] = None,
    ) -> None:
        """Render a CSV download button for a DataFrame or list of dicts."""
        df = self._to_dataframe(data)
        if df.empty:
            return

        df = self._clean_dataframe(df)
        filename = self._build_filename(filename_prefix, xml_filename)
        csv_content = df.to_csv(index=False, lineterminator="\n")

        st.download_button(
            label=label,
            data=csv_content,
            file_name=filename,
            mime="text/csv",
            key=key,
        )

    def render_lazy_master_json_export_button(self, reports: Any, xml_filename: str) -> None:
        """Render a master JSON export button if search data is available."""
        searches, folders = self._get_search_context(reports)
        if not searches:
            st.button("Export ALL", disabled=True, help="Search data not available", key="export_master_json_disabled")
            return

        json_content = export_full_structure_json(searches, folders or [])
        filename = self._build_filename("searches_master", xml_filename, extension="json")
        st.download_button(
            "Export ALL",
            data=json_content,
            file_name=filename,
            mime="application/json",
            key="export_master_json",
        )

    def render_lazy_excel_export_button(
        self,
        current_search: Any,
        clean_name: str,
        search_id: str,
        export_type: str,
    ) -> None:
        """Render a per-search Excel export button if data is available."""
        if not isinstance(current_search, dict):
            st.button("Excel", disabled=True, help="Search data not available", key=f"export_excel_{search_id}_disabled")
            return

        searches, folders = self._get_search_context()
        id_to_name = {s.get("id"): s.get("name") for s in searches if isinstance(s, dict)}

        if not searches:
            st.button("Excel", disabled=True, help="Search data not available", key=f"export_excel_{search_id}_disabled")
            return

        excel_bytes = generate_search_excel(current_search, searches, folders or [], id_to_name)
        filename = f"{clean_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        st.download_button(
            "Excel",
            data=excel_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"export_excel_{search_id}",
        )

    def render_lazy_json_export_button(
        self,
        current_search: Any,
        clean_name: str,
        search_id: str,
        export_type: str,
        xml_filename: str,
    ) -> None:
        """Render a per-search JSON export button if data is available."""
        if not isinstance(current_search, dict):
            st.button("JSON", disabled=True, help="Search data not available", key=f"export_json_{search_id}_disabled")
            return

        searches, folders = self._get_search_context()
        id_to_name = {s.get("id"): s.get("name") for s in searches if isinstance(s, dict)}

        if not searches:
            st.button("JSON", disabled=True, help="Search data not available", key=f"export_json_{search_id}_disabled")
            return

        json_content = export_search_json(search_id, searches, folders or [], id_to_name)
        filename = self._build_filename(clean_name, xml_filename, extension="json")
        st.download_button(
            "JSON",
            data=json_content,
            file_name=filename,
            mime="application/json",
            key=f"export_json_{search_id}",
        )

    def _to_dataframe(self, data: Any) -> pd.DataFrame:
        if data is None:
            return pd.DataFrame()
        if isinstance(data, pd.DataFrame):
            return data.copy()
        if isinstance(data, list):
            return pd.DataFrame(data)
        return pd.DataFrame()

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        clean_df = df.copy()
        emoji_pattern = re.compile(
            r"^["
            r"\U0001F50D"  # magnifying glass
            r"\U0001F4DD"  # memo
            r"\u2695\ufe0f"  # medical symbol
            r"\U0001F4CA"  # bar chart
            r"\U0001F4CB"  # clipboard
            r"\U0001F4C8"  # chart increasing
            r"\U0001F4C4"  # page
            r"\U0001F3E5"  # hospital
            r"\U0001F48A"  # pill
            r"\u2B07\ufe0f"  # down arrow
            r"\u2705"  # check mark
            r"\u274C"  # cross mark
            r"\U0001F504"  # anticlockwise arrows
            r"\U0001F4E5"  # inbox tray
            r"\U0001F333"  # deciduous tree
            r"\U0001F517"  # link
            r"]+\\s*"
        )
        for col in clean_df.columns:
            if clean_df[col].dtype == "object":
                clean_df[col] = clean_df[col].astype(str).str.replace(emoji_pattern, "", regex=True)
        return clean_df

    def _build_filename(self, prefix: str, xml_filename: Optional[str], extension: str = "csv") -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if xml_filename:
            base = Path(xml_filename).stem
            return f"{prefix}_{base}_{timestamp}.{extension}"
        return f"{prefix}_{timestamp}.{extension}"

    def _get_search_context(self, reports: Any = None):
        if self.analysis is not None:
            searches = getattr(self.analysis, "searches", None)
            folders = getattr(self.analysis, "folders", None)
            if isinstance(searches, list) and searches and isinstance(searches[0], dict):
                return searches, folders if isinstance(folders, list) else []
        return [], []
