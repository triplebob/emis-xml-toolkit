"""
Structure metadata provider for UI consumption.
Sources data from SessionStateKeys.XML_STRUCTURE_DATA populated by the structure parser/manager.
No clinical pipeline fallback.
"""

from typing import Dict, Any
import streamlit as st
from ..system.session_state import SessionStateKeys
from .structure_enricher import StructureEnricher


def get_structure_metadata() -> Dict[str, Any]:
    data = st.session_state.get(SessionStateKeys.XML_STRUCTURE_DATA) or {}
    pipeline_entities = st.session_state.get(SessionStateKeys.PIPELINE_ENTITIES)
    pipeline_folders = st.session_state.get(SessionStateKeys.PIPELINE_FOLDERS)
    if pipeline_entities:
        normalised_entities = []
        for ent in pipeline_entities:
            flags = ent.get("flags") or {}
            merged = dict(ent)
            if not merged.get("id") and flags.get("element_id"):
                merged["id"] = flags.get("element_id")
            if not merged.get("name") and flags.get("display_name"):
                merged["name"] = flags.get("display_name")
            if not merged.get("description") and flags.get("description"):
                merged["description"] = flags.get("description")
            if not merged.get("folder_id") and flags.get("folder_id"):
                merged["folder_id"] = flags.get("folder_id")
            if not merged.get("parent_guid") and flags.get("parent_search_guid"):
                merged["parent_guid"] = flags.get("parent_search_guid")
            if not merged.get("source_type") and flags.get("element_type"):
                merged["source_type"] = flags.get("element_type")
            if not merged.get("parent_type") and flags.get("parent_type"):
                merged["parent_type"] = flags.get("parent_type")
            normalised_entities.append(merged)
        data = dict(data)
        data["entities"] = normalised_entities
    if pipeline_folders:
        data = dict(data)
        data["folders"] = pipeline_folders
    manager = StructureEnricher(data)
    id_to_name = manager.id_to_name()
    deps = manager.dependency_graph()
    dependents = manager.dependents()
    folder_tree = manager.folder_tree()
    folder_paths = manager.folder_paths()
    searches = manager.enrich_searches()
    reports = manager.enrich_reports()
    nodes = searches + reports
    return {
        "folders": manager.folders,
        "searches": searches,
        "reports": reports,
        "nodes": nodes,
        "folder_tree": folder_tree,
        "folder_paths": folder_paths,
        "dependencies": deps,
        "dependents": dependents,
        "id_to_name": id_to_name,
    }
