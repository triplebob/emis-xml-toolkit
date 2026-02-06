"""
XML caching utilities for the parsing pipeline.
Uses Streamlit caching decorators to keep per-XML results keyed by content hash.
Supports CodeStore for efficient flattening of deduplicated codes.
"""


import streamlit as st
from typing import Dict, Any, List, Optional
from ..parsing.pipeline import parse_xml
from ..metadata.enrichment import enrich_codes_from_xml
from ..metadata.serialisers import serialise_codes_for_ui
from ..system.session_state import SessionStateKeys
from ..parsing.namespace_utils import get_child_text_any, find_child_any
from .code_store import CodeStore

# Increment to force Streamlit cache invalidation after pipeline changes
_PIPELINE_VERSION = "7"


def _flatten_from_code_store(code_store: CodeStore) -> List[Dict[str, Any]]:
    """
    Flatten codes directly from code store - already deduplicated.
    More efficient than iterating through entities when code store is available.
    """
    flattened: List[Dict[str, Any]] = []

    for code in code_store.get_all_codes():
        sources = code.get("source_entities", [])
        first_source = sources[0] if sources else {}
        criterion_ctx = first_source.get("criterion_context", {}) if first_source else {}

        flattened.append({
            "valueSet_guid": code.get("valueSet_guid"),
            "valueSet_description": code.get("valueSet_description"),
            "code_system": code.get("code_system"),
            "emis_guid": code.get("code_value"),
            "xml_display_name": code.get("display_name") or "Clinical Codes",
            "include_children": code.get("include_children", False),
            "is_refset": code.get("is_refset"),
            "is_pseudorefset": code.get("is_pseudo_refset"),
            "is_pseudomember": code.get("is_pseudo_member"),
            "inactive": code.get("inactive"),
            "is_emisinternal": code.get("is_emisinternal", False),
            "table_context": criterion_ctx.get("table") if criterion_ctx else None,
            "column_context": criterion_ctx.get("column") if criterion_ctx else None,
            "source_guid": first_source.get("entity_id"),
            "source_type": first_source.get("entity_type"),
            "source_name": first_source.get("entity_name"),
            "source_container": criterion_ctx.get("container") if criterion_ctx else first_source.get("entity_type"),
            "report_type": first_source.get("entity_type"),
            "source_count": len(sources),  # How many entities reference this code
        })

    return flattened


@st.cache_data(ttl=600, max_entries=1, show_spinner=False, scope="session")
def cache_parsed_xml(xml_hash: str, xml_content: str, pipeline_version: str = _PIPELINE_VERSION) -> Dict[str, Any]:
    """
    Cache pipeline parsing + enrichment keyed by XML content hash.
    Returns UI-ready rows and raw entities.
    Uses CodeStore for efficient flattening when available.
    """
    parsed = parse_xml(xml_content, source_name=xml_hash, run_patterns=False)
    parsed_doc = parsed["parsed_document"]
    entities = parsed["entities"]
    code_store = parsed.get("code_store")

    flattened = _flatten_from_code_store(code_store)
    namespaces = getattr(parsed_doc, "namespaces", {}) or {}

    def _extract_folders() -> List[Dict[str, Any]]:
        folders: List[Dict[str, Any]] = []
        for elem in getattr(parsed_doc.buckets, "folders", []) or []:
            folder_id = get_child_text_any(elem, ["id"], namespaces)
            name = get_child_text_any(elem, ["name"], namespaces)
            parent_id = get_child_text_any(elem, ["parentFolderId", "parentId", "parentFolder"], namespaces)
            enterprise_level = get_child_text_any(elem, ["enterpriseReportingLevel"], namespaces)
            version_guid = get_child_text_any(elem, ["VersionIndependentGUID"], namespaces)
            population_type_id = get_child_text_any(elem, ["PopulationTypeId"], namespaces)
            is_override = get_child_text_any(elem, ["IsEnterpriseSearchOverride"], namespaces)
            author_elem = find_child_any(elem, ["author"], namespaces)
            author_name = get_child_text_any(author_elem, ["authorName"], namespaces) if author_elem is not None else ""

            associations: List[Dict[str, Any]] = []
            seen_associations = set()
            for assoc in elem.findall(".//association", namespaces) + elem.findall(".//emis:association", namespaces):
                org = get_child_text_any(assoc, ["organisation"], namespaces)
                assoc_type = get_child_text_any(assoc, ["type"], namespaces)
                if org or assoc_type:
                    key = (org or "", assoc_type or "")
                    if key in seen_associations:
                        continue
                    seen_associations.add(key)
                    associations.append(
                        {
                            "organisation_guid": org or "",
                            "type": assoc_type or "",
                        }
                    )
            folders.append(
                {
                    "id": folder_id or "",
                    "name": name or "",
                    "parent_id": parent_id or "",
                    "enterprise_reporting_level": enterprise_level or "",
                    "version_independent_guid": version_guid or "",
                    "population_type_id": population_type_id or "",
                    "is_enterprise_search_override": is_override or "",
                    "author_name": author_name or "",
                    "associations": associations,
                }
            )
        return folders

    folders = _extract_folders()

    # Parse structure data using dedicated structure parser (metadata-only)
    from ..parsing.node_parsers.structure_parser import parse_structure
    structure_data = parse_structure(xml_content)

    # Note: criteria_groups, criteria, etc. are accessed from PIPELINE_ENTITIES directly
    # by UI code (metadata_provider.py, search_detail_tab.py). We no longer copy them into
    # structure_data to avoid memory duplication (~148 MB savings for large files).

    # Extract EMIS GUIDs for filtered lookup
    emis_guids = [
        str(code.get("emis_guid") or "").strip()
        for code in flattened
        if code.get("emis_guid")
    ]

    # Enrich with filtered lookup (loads only matching rows from parquet)
    enriched = enrich_codes_from_xml(flattened, emis_guids)

    debug_mode = st.session_state.get(SessionStateKeys.DEBUG_MODE, False)
    ui_rows = serialise_codes_for_ui(enriched, include_debug_fields=debug_mode)
    return {
        "ui_rows": ui_rows,
        "entities": entities,
        "folders": folders,
        "structure_data": structure_data,
        "code_store": code_store,
    }
