"""Analytics tab: MDS (Minimum Dataset) view and export."""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd
import streamlit as st

from ....exports.mds_exports import render_mds_export_controls
from ....metadata.mds_provider import build_mds_dataset
from ....system.session_state import SessionStateKeys
from ...theme import ThemeColours, info_box, warning_box


def _active_file_hash() -> str:
    return (
        st.session_state.get("last_processed_hash")
        or st.session_state.get("current_file_hash")
        or st.session_state.get(SessionStateKeys.XML_FILENAME)
        or ""
    )


def _get_mds_dataset(view_mode: str, include_emis_xml: bool) -> Dict[str, Any]:
    """Build (or reuse) MDS dataset for the current file and selected options."""
    active_hash = _active_file_hash()
    cache_key = SessionStateKeys.MDS_DATASET_CACHE
    signature = {
        "schema_version": 2,
        "file_hash": active_hash,
        "view_mode": view_mode,
        "include_emis_xml": include_emis_xml,
    }

    cached = st.session_state.get(cache_key)
    if isinstance(cached, dict) and cached.get("signature") == signature and "dataset" in cached:
        return cached["dataset"]

    entities = st.session_state.get(SessionStateKeys.PIPELINE_ENTITIES) or []
    pipeline_codes = st.session_state.get(SessionStateKeys.PIPELINE_CODES) or []
    code_store = st.session_state.get(SessionStateKeys.CODE_STORE)

    dataset = build_mds_dataset(
        pipeline_entities=entities,
        pipeline_codes=pipeline_codes,
        view_mode=view_mode,
        include_emis_xml=include_emis_xml,
        code_store=code_store,
    )

    st.session_state[cache_key] = {"signature": signature, "dataset": dataset}
    return dataset


def _prepare_preview_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Prepare UI-only display DataFrame (friendly headings + code emojis)."""
    preview_df = pd.DataFrame(rows)
    if preview_df.empty:
        return preview_df

    ui_column_map = {
        "emis_guid": "EMIS GUID",
        "snomed_code": "SNOMED Code",
        "description": "SNOMED Description",
        "code_type": "Code Type",
        "mapping_status": "Mapping Found",
        "source_type": "Source Type",
        "source_name": "Source Name",
        "source_guid": "Source Container",
        "emis_xml": "EMIS XML",
    }
    preview_df = preview_df.rename(columns=ui_column_map)
    # UI preview never shows the raw EMIS XML payload column.
    preview_df = preview_df.drop(columns=["EMIS XML"], errors="ignore")

    ordered_columns = [
        "EMIS GUID",
        "SNOMED Code",
        "SNOMED Description",
        "Code Type",
        "Mapping Found",
        "Source Type",
        "Source Name",
        "Source Container",
    ]
    present_order = [col for col in ordered_columns if col in preview_df.columns]
    extras = [col for col in preview_df.columns if col not in present_order]
    preview_df = preview_df[present_order + extras]

    if "EMIS GUID" in preview_df.columns:
        preview_df["EMIS GUID"] = preview_df["EMIS GUID"].apply(
            lambda x: f"🔍 {x}" if x and str(x).strip() else ""
        )
    if "SNOMED Code" in preview_df.columns:
        preview_df["SNOMED Code"] = preview_df["SNOMED Code"].apply(
            lambda x: f"⚕️ {x}" if x and str(x).strip() else ""
        )
    if "Code Type" in preview_df.columns:
        code_type_map = {
            "clinical": "Clinical",
            "medication": "Medication",
            "refset": "RefSet",
        }
        preview_df["Code Type"] = preview_df["Code Type"].astype(str).str.lower().map(code_type_map).fillna(
            preview_df["Code Type"].astype(str).str.replace("_", " ", regex=False).str.title()
        )
    if "Mapping Found" in preview_df.columns:
        preview_df["Mapping Found"] = (
            preview_df["Mapping Found"].astype(str).str.replace("_", " ", regex=False).str.title()
        )
    if "Source Type" in preview_df.columns:
        preview_df["Source Type"] = (
            preview_df["Source Type"].astype(str).str.replace("_", " ", regex=False).str.title()
        )

    return preview_df


def _highlight_mapping_status(row: pd.Series) -> list[str]:
    """Apply row colour by mapping status (found -> green, otherwise red)."""
    mapping = str(row.get("Mapping Found", "")).strip().lower()
    colour = ThemeColours.GREEN if mapping == "found" else ThemeColours.RED
    return [f"background-color: {colour}; color: #FAFAFA"] * len(row)


def render_mds_tab() -> None:
    """Render the MDS tab content."""
    st.markdown("""<style>[data-testid=\"stElementToolbar\"]{display: none;}</style>""", unsafe_allow_html=True)

    @st.fragment
    def mds_fragment() -> None:
        entities = st.session_state.get(SessionStateKeys.PIPELINE_ENTITIES) or []
        if not entities:
            st.markdown(
                info_box("📦 MDS is available after processing an XML file."),
                unsafe_allow_html=True,
            )
            return

        title_col, spacer_col1, export_col, spacer_col2, mode_col = st.columns([2, 0.1, 0.8, 0.1, 1])
        with title_col:
            st.markdown("")
            st.subheader("📦 Minimum Dataset Generator (MDS)")
            st.caption("Build a clean minimum dataset from parsed entities, with optional per-source output and EMIS-ready XML snippets.")

        with spacer_col1:
            st.markdown("")

        with export_col:
            st.markdown("")
            st.markdown("")
            export_slot = st.container()

        with spacer_col2:
            st.markdown("")

        with mode_col:
            view_mode = st.selectbox(
                "Code Display Mode:",
                help="🔀 Unique Codes: Show each code once\n📍 Per Source: Show codes per search/report",
                options=["unique_codes", "per_source"],
                format_func=lambda x: "🔀 Unique Codes" if x == "unique_codes" else "📍 Per Source",
                key="mds_view_mode",
            )
            include_emis_xml = st.toggle(
                "Include EMIS XML output",
                value=False,
                key="mds_include_emis_xml",
                help="Adds an `emis_xml` column like <value>{EMIS_GUID}</value>",
            )

        dataset = _get_mds_dataset(view_mode=view_mode, include_emis_xml=include_emis_xml)
        rows = dataset.get("rows") or []
        summary = dataset.get("summary") or {}

        if not rows:
            st.markdown(
                warning_box("No eligible MDS rows were found for the current XML."),
                unsafe_allow_html=True,
            )
            skipped = summary.get("skipped") or {}
            if skipped:
                with st.expander("Skipped row reasons", expanded=False):
                    st.write(skipped)
            return

        unique_codes = summary.get("unique_codes", len({row.get("emis_guid") for row in rows}))
        mapping_found = summary.get("mapping_found", 0)
        mapping_rate = (mapping_found / len(rows) * 100) if rows else 0.0

        st.markdown("")
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            with st.container(border=True):
                st.metric("Criteria Scanned", f"{summary.get('criteria_processed', 0):,}")
        with m2:
            with st.container(border=True):
                st.metric("Rows", f"{len(rows):,}")
        with m3:
            with st.container(border=True):
                st.metric("Mapped", f"{mapping_found:,}")
        with m4:
            with st.container(border=True):
                st.metric("Mapping Rate", f"{mapping_rate:.1f}%")

        t_counts = summary.get("code_type_counts") or {}
        t1, t2, t3, t4 = st.columns(4)
        with t1:
            with st.container(border=True):
                st.metric("Unique Codes", f"{unique_codes:,}")
        with t2:
            with st.container(border=True):
                st.metric("Clinical", f"{t_counts.get('clinical', 0):,}")
        with t3:
            with st.container(border=True):
                st.metric("Medication", f"{t_counts.get('medication', 0):,}")
        with t4:
            with st.container(border=True):
                st.metric("RefSet", f"{t_counts.get('refset', 0):,}")

        with st.container(border=True):
            st.markdown("**MDS Output Preview (first 50 rows)**")
            preview_rows = rows[:50]
            preview_df = _prepare_preview_dataframe(preview_rows)
            styled_preview_df = preview_df.style.apply(_highlight_mapping_status, axis=1)
            st.dataframe(styled_preview_df, width="stretch", hide_index=True)
            if len(rows) > len(preview_rows):
                st.caption(f"Showing {len(preview_rows):,} of {len(rows):,} rows.")

        with st.expander("MDS Audit Summary", expanded=False):
            st.write(summary)

        xml_filename = st.session_state.get(SessionStateKeys.XML_FILENAME, "clinxml")
        active_hash = _active_file_hash()
        state_prefix = f"mds_export_{view_mode}_{'xml' if include_emis_xml else 'plain'}"
        with export_slot:
            render_mds_export_controls(
                rows=rows,
                xml_filename=xml_filename,
                view_mode=view_mode,
                state_prefix=state_prefix,
                context_token=active_hash,
            )

    mds_fragment()
