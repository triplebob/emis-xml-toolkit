"""
Report metadata provider for UI and exports.
Combines pipeline report entities with structure metadata.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import hashlib
import streamlit as st

from ..system.session_state import SessionStateKeys
from .structure_enricher import StructureEnricher


_REPORT_TYPES = {"list_report", "audit_report", "aggregate_report"}


def _normalise_report_type(raw_type: str) -> str:
    if not raw_type:
        return "unknown"
    text = raw_type.lower()
    if "list" in text:
        return "list"
    if "audit" in text:
        return "audit"
    if "aggregate" in text:
        return "aggregate"
    return text


def _build_signature(entities: List[Dict[str, Any]], structure_data: Dict[str, Any], file_hash: str) -> str:
    ids = []
    for ent in entities:
        flags = ent.get("flags") or {}
        etype = flags.get("element_type") or flags.get("source_type")
        if etype in _REPORT_TYPES:
            rid = flags.get("element_id") or ""
            if rid:
                ids.append(rid)
    struct_ids = []
    for ent in structure_data.get("entities") or []:
        if ent.get("source_type") in _REPORT_TYPES and ent.get("id"):
            struct_ids.append(ent["id"])
    signature = "|".join(sorted(set(ids + struct_ids)))
    combined = f"{file_hash}|{signature}"
    return hashlib.md5(combined.encode("utf-8")).hexdigest()


def _extract_pipeline_reports(entities: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    pipeline_reports: Dict[str, Dict[str, Any]] = {}
    for ent in entities:
        flags = ent.get("flags") or {}
        etype = flags.get("element_type") or flags.get("source_type")
        if etype not in _REPORT_TYPES:
            continue
        rid = flags.get("element_id") or ""
        if not rid:
            continue
        pipeline_reports[rid] = ent
    return pipeline_reports


def _merge_report_views(
    structure_reports: List[Dict[str, Any]],
    pipeline_reports: Dict[str, Dict[str, Any]],
    id_to_name: Dict[str, str],
) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen = set()

    for report in structure_reports:
        rid = report.get("id") or ""
        if not rid or rid in seen:
            continue
        seen.add(rid)

        pipeline = pipeline_reports.get(rid) or {}
        flags = pipeline.get("flags") or {}
        report_type = report.get("source_type") or flags.get("element_type") or ""

        merged.append(
            {
                "id": rid,
                "name": report.get("name") or flags.get("display_name") or "",
                "description": flags.get("description") or "",
                "type": report_type,
                "type_label": report.get("type_label") or "",
                "folder_id": report.get("folder_id") or flags.get("folder_id") or "",
                "folder_path": report.get("folder_path") or [],
                "parent_guid": report.get("parent_guid") or flags.get("parent_search_guid") or "",
                "dependencies": report.get("dependencies") or [],
                "dependency_names": report.get("dependency_names") or [id_to_name.get(d, d) for d in report.get("dependencies") or []],
                "dependents": report.get("dependents") or [],
                "dependent_names": report.get("dependent_names") or [id_to_name.get(d, d) for d in report.get("dependents") or []],
                "author": flags.get("report_author_name") or flags.get("report_author_user_id") or "",
                "creation_time": flags.get("report_creation_time") or "",
                "population_references": flags.get("population_reference_guid") or [],
                "column_groups": pipeline.get("column_groups") or [],
                "aggregate": pipeline.get("aggregate") or {},
                "aggregate_criteria": pipeline.get("aggregate_criteria") or [],
                "report_criteria": pipeline.get("report_criteria") or [],
                "flags": flags,
            }
        )

    # Include pipeline-only reports if any were not present in structure data
    for rid, pipeline in pipeline_reports.items():
        if rid in seen:
            continue
        flags = pipeline.get("flags") or {}
        report_type = flags.get("element_type") or ""
        merged.append(
            {
                "id": rid,
                "name": flags.get("display_name") or "",
                "description": flags.get("description") or "",
                "type": report_type,
                "type_label": report_type.replace("_", " ").title(),
                "folder_id": flags.get("folder_id") or "",
                "folder_path": [],
                "parent_guid": flags.get("parent_search_guid") or "",
                "dependencies": [],
                "dependency_names": [],
                "dependents": [],
                "dependent_names": [],
                "author": flags.get("report_author_name") or flags.get("report_author_user_id") or "",
                "creation_time": flags.get("report_creation_time") or "",
                "population_references": flags.get("population_reference_guid") or [],
                "column_groups": pipeline.get("column_groups") or [],
                "aggregate": pipeline.get("aggregate") or {},
                "aggregate_criteria": pipeline.get("aggregate_criteria") or [],
                "report_criteria": pipeline.get("report_criteria") or [],
                "flags": flags,
            }
        )

    return merged


def get_report_metadata() -> Dict[str, Any]:
    entities = st.session_state.get(SessionStateKeys.PIPELINE_ENTITIES) or []
    structure_data = st.session_state.get(SessionStateKeys.XML_STRUCTURE_DATA) or {}

    file_hash = st.session_state.get("last_processed_hash", "")
    signature = _build_signature(entities, structure_data, file_hash)
    cache_key = "report_metadata_cache"
    sig_key = "report_metadata_signature"
    if st.session_state.get(sig_key) == signature and cache_key in st.session_state:
        return st.session_state[cache_key]

    manager = StructureEnricher(structure_data)
    structure_reports = manager.enrich_reports()
    id_to_name = manager.id_to_name()
    folders = manager.folders
    folder_tree = manager.folder_tree()
    folder_paths = manager.folder_paths()

    pipeline_reports = _extract_pipeline_reports(entities)
    merged_reports = _merge_report_views(structure_reports, pipeline_reports, id_to_name)

    breakdown: Dict[str, List[Dict[str, Any]]] = {"list": [], "audit": [], "aggregate": []}
    for report in merged_reports:
        bucket = _normalise_report_type(report.get("type") or "")
        if bucket not in breakdown:
            continue
        breakdown[bucket].append(report)

    data = {
        "reports": merged_reports,
        "report_breakdown": breakdown,
        "folders": folders,
        "folder_tree": folder_tree,
        "folder_paths": folder_paths,
        "id_to_name": id_to_name,
    }

    st.session_state[sig_key] = signature
    st.session_state[cache_key] = data
    return data


def get_report_view(report_id: str) -> Optional[Dict[str, Any]]:
    if not report_id:
        return None
    metadata = get_report_metadata()
    for report in metadata.get("reports") or []:
        if report.get("id") == report_id:
            return report
    return None
