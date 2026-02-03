"""
Centralised Session State Management for ClinXML

Defines canonical session state keys plus cleanup and SNOMED cache helpers.
"""

import gc
from typing import Dict, Optional
import streamlit as st


class SessionStateKeys:
    """Canonical session state key definitions for ClinXML application."""

    # Core application state
    XML_FILENAME = "xml_filename"
    XML_FILESIZE = "xml_filesize"
    XML_CONTENT = "xml_content"
    XML_RAW_BYTES = "xml_raw_bytes"
    UPLOADED_FILE = "uploaded_file"
    UPLOADED_FILENAME = "uploaded_filename"
    IS_PROCESSING = "is_processing"

    # Lookup table data
    LOOKUP_ENCRYPTED_BYTES = "lookup_encrypted_bytes"
    EMIS_GUID_COL = "emis_guid_col"
    SNOMED_CODE_COL = "snomed_code_col"
    LOOKUP_VERSION_INFO = "lookup_version_info"

    # Matched EMIS GUID -> SNOMED mappings (long-term cache)
    MATCHED_EMIS_SNOMED_CACHE = "matched_emis_snomed_cache"
    MATCHED_EMIS_SNOMED_TIMESTAMP = "matched_emis_snomed_timestamp"

    # User preferences and modes
    CURRENT_DEDUPLICATION_MODE = "current_deduplication_mode"
    CHILD_VIEW_MODE = "child_view_mode"
    DEBUG_MODE = "debug_mode"
    SESSION_ID = "session_id"
    PROCESSED_FILES = "processed_files"
    CLINICAL_INCLUDE_REPORT_CODES = "clinical_include_report_codes"
    CLINICAL_SHOW_CODE_SOURCES = "clinical_show_code_sources"

    # Memory monitoring
    FORCE_MEMORY_REFRESH = "force_memory_refresh"
    FORCE_FULL_REPROCESS = "force_full_reprocess"
    MEMORY_PEAK_MB = "memory_peak_mb"

    # UI state management (dynamic keys - patterns)
    CACHED_SELECTED_REPORT_PREFIX = "cached_selected_report_"
    SELECTED_TEXT_PREFIX = "selected_{}_text"
    PREVIOUS_SELECTED_PREFIX = "previous_selected_{}_id"
    RENDERING_STATE_SUFFIX = "_rendering"
    RENDERING_UPDATED_SUFFIX = "_rendering_updated"

    # Search Browser UI state
    SELECTED_SEARCH_ID = "selected_search_id"
    SELECTED_FOLDER_ID = "selected_folder_id"
    CRITERIA_EXPANDED_PREFIX = "criteria_expanded_"
    SEARCH_EXPORT_READY_PREFIX = "search_export_"
    SEARCH_EXPORT_PATH_PREFIX = "search_export_"

    # Cache keys (dynamic - patterns)
    CACHE_KEY_PREFIX = "cache_"
    PAGE_KEY_SUFFIX = "_page"
    PROCESSING_CACHE_SUFFIX = "_processing"
    TRANSLATION_CACHE_SUFFIX = "_translation"

    # Export cache keys (dynamic patterns)
    EXCEL_CACHE_PREFIX = "excel_export_"
    JSON_CACHE_PREFIX = "json_export_"

    # Tree visualisation cache (dynamic patterns)
    TREE_TEXT_PREFIX = "tree_text_"
    TREE_JSON_PREFIX = "tree_json_"
    DEP_TREE_TEXT_PREFIX = "dep_tree_text_"

    # NHS Terminology Server
    NHS_TERMINOLOGY_CACHE_PREFIX = "nhs_term_cache_"
    NHS_CONNECTION_STATUS = "nhs_connection_status"
    EXPANSION_IN_PROGRESS = "expansion_in_progress"
    EXPANSION_STATUS = "expansion_status"

    # Processing and audit data
    EMIS_GUIDS = "emis_guids"
    AUDIT_STATS = "audit_stats"
    PROCESSING_CONTEXT = "processing_context"

    # Parsing pipeline caches
    PIPELINE_CODES = "pipeline_codes"
    PIPELINE_ENTITIES = "pipeline_entities"
    PIPELINE_FOLDERS = "pipeline_folders"
    XML_STRUCTURE_DATA = "xml_structure_data"
    CODE_STORE = "code_store"

    # Error handling
    PENDING_ERRORS = "pending_errors"


class SessionStateGroups:
    """Logical groupings of session state keys for bulk operations."""

    CORE_DATA = [
        SessionStateKeys.XML_FILENAME,
        SessionStateKeys.XML_FILESIZE,
        SessionStateKeys.UPLOADED_FILENAME,
        SessionStateKeys.UPLOADED_FILE,
    ]

    PROCESSING_STATE = [
        SessionStateKeys.IS_PROCESSING,
        SessionStateKeys.PROCESSING_CONTEXT,
        "progress_placeholder",
        "processing_placeholder",
    ]

    RESULTS_DATA = [
        SessionStateKeys.EMIS_GUIDS,
        SessionStateKeys.AUDIT_STATS,
        SessionStateKeys.PIPELINE_CODES,
        SessionStateKeys.PIPELINE_ENTITIES,
        SessionStateKeys.PIPELINE_FOLDERS,
        SessionStateKeys.XML_STRUCTURE_DATA,
        SessionStateKeys.CODE_STORE,
        "unified_clinical_data_cache",
        "expansion_results_data",
    ]

    LOOKUP_DATA = [
        SessionStateKeys.LOOKUP_ENCRYPTED_BYTES,
        SessionStateKeys.EMIS_GUID_COL,
        SessionStateKeys.SNOMED_CODE_COL,
        SessionStateKeys.LOOKUP_VERSION_INFO,
        SessionStateKeys.MATCHED_EMIS_SNOMED_CACHE,
        SessionStateKeys.MATCHED_EMIS_SNOMED_TIMESTAMP,
    ]

    USER_PREFERENCES = [
        SessionStateKeys.CURRENT_DEDUPLICATION_MODE,
        SessionStateKeys.CHILD_VIEW_MODE,
        SessionStateKeys.DEBUG_MODE,
        SessionStateKeys.FORCE_MEMORY_REFRESH,
        SessionStateKeys.CLINICAL_INCLUDE_REPORT_CODES,
        SessionStateKeys.CLINICAL_SHOW_CODE_SOURCES,
    ]

    NHS_TERMINOLOGY = [
        SessionStateKeys.NHS_CONNECTION_STATUS,
        SessionStateKeys.EXPANSION_IN_PROGRESS,
        SessionStateKeys.EXPANSION_STATUS,
    ]

    SYSTEM_MONITORING = [
        SessionStateKeys.MEMORY_PEAK_MB,
        SessionStateKeys.PENDING_ERRORS,
    ]


def clear_processing_state() -> None:
    """Clear all processing-related session state."""
    for key in SessionStateGroups.PROCESSING_STATE:
        if key in st.session_state:
            del st.session_state[key]


def clear_results_state() -> None:
    """Clear all results and analysis data."""
    for key in SessionStateGroups.RESULTS_DATA:
        if key in st.session_state:
            del st.session_state[key]


def clear_export_state() -> None:
    """Clear export-related cache keys and perform garbage collection."""
    keys_to_remove = []
    for key in st.session_state.keys():
        if (
            key.startswith(SessionStateKeys.EXCEL_CACHE_PREFIX)
            or key.startswith(SessionStateKeys.JSON_CACHE_PREFIX)
            or key.startswith("export_")
        ):
            keys_to_remove.append(key)

    for key in keys_to_remove:
        del st.session_state[key]

    from ..caching.cache_manager import CacheManager

    CacheManager.clear_all_export_cache()
    gc.collect()


def clear_report_state(report_type_name: Optional[str] = None) -> None:
    """Clear report-specific UI state."""
    if report_type_name:
        keys_to_clear = [
            f"{SessionStateKeys.CACHED_SELECTED_REPORT_PREFIX}{report_type_name}",
            SessionStateKeys.SELECTED_TEXT_PREFIX.format(report_type_name),
            SessionStateKeys.PREVIOUS_SELECTED_PREFIX.format(report_type_name),
            f"{report_type_name}{SessionStateKeys.RENDERING_STATE_SUFFIX}",
            f"{report_type_name}{SessionStateKeys.RENDERING_UPDATED_SUFFIX}",
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        return

    keys_to_remove = []
    for key in st.session_state.keys():
        if (
            key.startswith(SessionStateKeys.CACHED_SELECTED_REPORT_PREFIX)
            or SessionStateKeys.RENDERING_STATE_SUFFIX in key
            or SessionStateKeys.RENDERING_UPDATED_SUFFIX in key
            or any(pattern in key for pattern in ["selected_", "previous_selected_"])
        ):
            keys_to_remove.append(key)

    for key in keys_to_remove:
        del st.session_state[key]


def clear_analysis_state() -> None:
    """Clear analysis and visualisation cache."""
    keys_to_remove = []
    for key in st.session_state.keys():
        if (
            key.startswith(SessionStateKeys.TREE_TEXT_PREFIX)
            or key.startswith(SessionStateKeys.TREE_JSON_PREFIX)
            or key.startswith(SessionStateKeys.DEP_TREE_TEXT_PREFIX)
            or key.startswith(SessionStateKeys.CACHE_KEY_PREFIX)
        ):
            keys_to_remove.append(key)

    for key in keys_to_remove:
        del st.session_state[key]


def clear_pipeline_caches() -> None:
    """Clear cached parsing and rendering outputs scoped to the current XML file."""
    try:
        from ..caching.xml_cache import cache_parsed_xml
        cache_parsed_xml.clear()
    except Exception:
        pass

    try:
        from ..caching.cache_manager import CacheManager

        CacheManager.cache_xml_code_extraction.clear()
        CacheManager.cache_snomed_lookup_dictionary.clear()
        CacheManager.cache_unified_clinical_data.clear()
        CacheManager.cache_list_report_visualisation.clear()
        CacheManager.cache_audit_report_visualisation.clear()
        CacheManager.cache_aggregate_report_visualisation.clear()
        CacheManager.cache_report_metadata.clear()
        CacheManager.cache_dataframe_rendering.clear()
    except Exception:
        pass

    try:
        from ..metadata.snomed_translation import translate_emis_to_snomed

        translate_emis_to_snomed.clear()
    except Exception:
        pass

    try:
        from ..ui.tab_helpers import (
            _load_report_metadata,
            _extract_clinical_codes,
            _process_column_groups,
            paginate_reports,
            load_report_sections,
            prepare_export_data,
        )

        _load_report_metadata.clear()
        _extract_clinical_codes.clear()
        _process_column_groups.clear()
        paginate_reports.clear()
        load_report_sections.clear()
        prepare_export_data.clear()
    except Exception:
        pass

    try:
        from ..ui.tabs.report_viewer.common import _build_snomed_lookup
        _build_snomed_lookup.clear()
    except Exception:
        pass

    try:
        from ..ui.tabs.search_browser.search_criteria_viewer import _build_clinical_codes_cache
        _build_clinical_codes_cache.clear()
    except Exception:
        pass


def clear_ui_state() -> None:
    """Clear UI-specific cache while preserving user preferences."""
    keys_to_remove = []
    for key in st.session_state.keys():
        if (
            key.startswith(SessionStateKeys.CACHED_SELECTED_REPORT_PREFIX)
            or key.endswith(SessionStateKeys.RENDERING_STATE_SUFFIX)
            or key.endswith(SessionStateKeys.RENDERING_UPDATED_SUFFIX)
            or ("selected_" in key and key.endswith("_text"))
        ):
            keys_to_remove.append(key)

    for key in keys_to_remove:
        del st.session_state[key]


def clear_for_new_xml_selection() -> None:
    """Lightweight clearing for when a XML file is selected."""
    clear_pipeline_caches()
    clear_results_state()
    clear_ui_state()
    clear_report_state()

    for key in [
        SessionStateKeys.XML_CONTENT,
        SessionStateKeys.XML_RAW_BYTES,
        SessionStateKeys.XML_STRUCTURE_DATA,
        SessionStateKeys.PIPELINE_FOLDERS,
        SessionStateKeys.PIPELINE_CODES,
        SessionStateKeys.PIPELINE_ENTITIES,
        SessionStateKeys.CODE_STORE,
        SessionStateKeys.UPLOADED_FILE,
        SessionStateKeys.LOOKUP_ENCRYPTED_BYTES,
        SessionStateKeys.EMIS_GUID_COL,
        SessionStateKeys.SNOMED_CODE_COL,
        SessionStateKeys.MATCHED_EMIS_SNOMED_CACHE,
        SessionStateKeys.MATCHED_EMIS_SNOMED_TIMESTAMP,
        "expansion_results_data",
        "unified_clinical_data_cache",
    ]:
        if key in st.session_state:
            del st.session_state[key]

    st.session_state[SessionStateKeys.IS_PROCESSING] = False
    gc.collect()


def clear_for_new_xml() -> None:
    """Comprehensive clearing for XML upload."""
    clear_pipeline_caches()
    clear_results_state()
    clear_processing_state()
    clear_export_state()
    clear_ui_state()
    clear_analysis_state()
    clear_report_state()

    for key in [
        SessionStateKeys.PIPELINE_CODES,
        SessionStateKeys.PIPELINE_ENTITIES,
        SessionStateKeys.PIPELINE_FOLDERS,
        SessionStateKeys.XML_STRUCTURE_DATA,
        SessionStateKeys.CODE_STORE,
        "unified_clinical_data_cache",
        SessionStateKeys.LOOKUP_ENCRYPTED_BYTES,
        SessionStateKeys.EMIS_GUID_COL,
        SessionStateKeys.SNOMED_CODE_COL,
        SessionStateKeys.MATCHED_EMIS_SNOMED_CACHE,
        SessionStateKeys.MATCHED_EMIS_SNOMED_TIMESTAMP,
        "expansion_results_data",
    ]:
        if key in st.session_state:
            del st.session_state[key]

    preserve_keys = set(
        SessionStateGroups.LOOKUP_DATA
        + SessionStateGroups.USER_PREFERENCES
        + SessionStateGroups.CORE_DATA
        + [SessionStateKeys.SESSION_ID, "current_file_hash", "last_processed_hash"]
    )

    keys_to_remove = []
    for key in st.session_state.keys():
        if key not in preserve_keys and not key.startswith(SessionStateKeys.NHS_TERMINOLOGY_CACHE_PREFIX):
            if (
                key.startswith(SessionStateKeys.CACHE_KEY_PREFIX)
                or key.startswith(SessionStateKeys.EXCEL_CACHE_PREFIX)
                or key.startswith(SessionStateKeys.JSON_CACHE_PREFIX)
                or key.startswith(SessionStateKeys.TREE_TEXT_PREFIX)
                or "_processing" in key
                or "_rendering" in key
            ):
                keys_to_remove.append(key)

    for key in keys_to_remove:
        del st.session_state[key]

    gc.collect()


def clear_all_except_core() -> None:
    """Clear all session state except core data, lookup cache, and user preferences."""
    preserve_keys = set(
        SessionStateGroups.CORE_DATA
        + SessionStateGroups.USER_PREFERENCES
        + SessionStateGroups.LOOKUP_DATA
    )

    keys_to_remove = [key for key in st.session_state.keys() if key not in preserve_keys]
    for key in keys_to_remove:
        del st.session_state[key]

    gc.collect()


def get_snomed_cache_ttl_minutes() -> int:
    """Get TTL for SNOMED cache in minutes."""
    return 60


def is_snomed_cache_valid() -> bool:
    """Check if the SNOMED cache is still valid based on TTL."""
    timestamp = st.session_state.get(SessionStateKeys.MATCHED_EMIS_SNOMED_TIMESTAMP)
    if not timestamp:
        return False

    from datetime import datetime

    try:
        cache_time = datetime.fromisoformat(timestamp)
        now = datetime.now()
        age_minutes = (now - cache_time).total_seconds() / 60
        ttl_minutes = get_snomed_cache_ttl_minutes()
        is_valid = age_minutes < ttl_minutes

        if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
            print(
                f"[SNOMED CACHE] Age: {age_minutes:.1f}min, TTL: {ttl_minutes}min, Valid: {is_valid}"
            )

        return is_valid
    except (ValueError, TypeError):
        return False


def get_cached_snomed_mappings() -> Dict[str, str]:
    """Get cached EMIS GUID -> SNOMED mappings if still valid."""
    if not is_snomed_cache_valid():
        return {}

    cache = st.session_state.get(SessionStateKeys.MATCHED_EMIS_SNOMED_CACHE, {})

    if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        print(f"[SNOMED CACHE] Retrieved {len(cache)} cached mappings")

    return cache


def update_snomed_cache(new_mappings: Dict[str, str]) -> None:
    """Update the SNOMED cache with EMIS GUID -> SNOMED mappings."""
    from datetime import datetime

    existing_cache = get_cached_snomed_mappings() if is_snomed_cache_valid() else {}
    existing_cache.update(new_mappings)

    st.session_state[SessionStateKeys.MATCHED_EMIS_SNOMED_CACHE] = existing_cache
    st.session_state[SessionStateKeys.MATCHED_EMIS_SNOMED_TIMESTAMP] = datetime.now().isoformat()

    if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        print(
            f"[SNOMED CACHE] Updated with {len(new_mappings)} additional mappings, total: {len(existing_cache)}"
        )


def clear_expired_snomed_cache() -> bool:
    """Clear SNOMED cache if expired."""
    if not is_snomed_cache_valid():
        if SessionStateKeys.MATCHED_EMIS_SNOMED_CACHE in st.session_state:
            del st.session_state[SessionStateKeys.MATCHED_EMIS_SNOMED_CACHE]
        if SessionStateKeys.MATCHED_EMIS_SNOMED_TIMESTAMP in st.session_state:
            del st.session_state[SessionStateKeys.MATCHED_EMIS_SNOMED_TIMESTAMP]

        if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
            print("[SNOMED CACHE] Expired cache cleared")
        return True
    return False
