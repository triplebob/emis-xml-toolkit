"""
Centralized Session State Management for ClinXML

This module provides canonical definitions for all session state keys used
throughout the application, along with utilities for state management and validation.

Usage:
    from utils.core.session_state import SessionStateKeys, clear_processing_state
    
    # Using canonical keys
    st.session_state[SessionStateKeys.XML_FILENAME] = filename
    
    # Clearing state groups
    clear_processing_state()
"""

import streamlit as st
from typing import Dict, List, Optional, Set
import gc
from ..ui.theme import info_box, success_box, warning_box, error_box


class SessionStateKeys:
    """Canonical session state key definitions for ClinXML application"""
    
    # Core application state
    XML_FILENAME = 'xml_filename'
    XML_CONTENT = 'xml_content'
    XML_RAW_BYTES = 'xml_raw_bytes'
    UPLOADED_FILENAME = 'uploaded_filename'
    LAST_PROCESSED_FILE = 'last_processed_file'
    IS_PROCESSING = 'is_processing'
    
    # Results and analysis
    RESULTS = 'results'
    SEARCH_RESULTS = 'search_results'
    REPORT_RESULTS = 'report_results'
    XML_STRUCTURE_ANALYSIS = 'xml_structure_analysis'
    SEARCH_ANALYSIS = 'search_analysis'
    
    # Lookup table data
    LOOKUP_DF = 'lookup_df'
    LOOKUP = 'lookup'
    EMIS_GUID_COL = 'emis_guid_col'
    SNOMED_CODE_COL = 'snomed_code_col'
    LOOKUP_VERSION_INFO = 'lookup_version_info'
    LOOKUP_PERFORMANCE = 'lookup_performance'
    
    # Matched EMIS GUID → SNOMED mappings (long-term cache, 30+ minutes)
    MATCHED_EMIS_SNOMED_CACHE = 'matched_emis_snomed_cache'
    MATCHED_EMIS_SNOMED_TIMESTAMP = 'matched_emis_snomed_timestamp'
    
    # User preferences and modes
    CURRENT_DEDUPLICATION_MODE = 'current_deduplication_mode'
    CHILD_VIEW_MODE = 'child_view_mode'
    DEBUG_MODE = 'debug_mode'
    SESSION_ID = 'session_id'
    PROCESSED_FILES = 'processed_files'
    CLINICAL_INCLUDE_REPORT_CODES = 'clinical_include_report_codes'
    CLINICAL_SHOW_CODE_SOURCES = 'clinical_show_code_sources'
    
    # Memory monitoring
    FORCE_MEMORY_REFRESH = 'force_memory_refresh'
    MEMORY_PEAK_MB = 'memory_peak_mb'
    
    # UI state management (dynamic keys - patterns)
    CACHED_SELECTED_REPORT_PREFIX = 'cached_selected_report_'  # + report_type_name
    SELECTED_TEXT_PREFIX = 'selected_{}_text'  # format with report_type_name
    PREVIOUS_SELECTED_PREFIX = 'previous_selected_{}_id'  # format with report_type_name
    RENDERING_STATE_SUFFIX = '_rendering'
    RENDERING_UPDATED_SUFFIX = '_rendering_updated'
    
    # Cache keys (dynamic - patterns)
    CACHE_KEY_PREFIX = 'cache_'
    PAGE_KEY_SUFFIX = '_page'
    PROCESSING_CACHE_SUFFIX = '_processing'
    TRANSLATION_CACHE_SUFFIX = '_translation'
    
    # Export cache keys (dynamic patterns)
    EXCEL_CACHE_PREFIX = 'excel_export_'
    JSON_CACHE_PREFIX = 'json_export_'
    
    # Tree visualization cache (dynamic patterns)
    TREE_TEXT_PREFIX = 'tree_text_'
    TREE_JSON_PREFIX = 'tree_json_'
    DEP_TREE_TEXT_PREFIX = 'dep_tree_text_'
    
    # NHS Terminology Server
    NHS_TERMINOLOGY_CACHE_PREFIX = 'nhs_term_cache_'
    NHS_CONNECTION_STATUS = 'nhs_connection_status'
    EXPANSION_IN_PROGRESS = 'expansion_in_progress'
    EXPANSION_STATUS = 'expansion_status'
    
    # Processing and audit data
    EMIS_GUIDS = 'emis_guids'
    AUDIT_STATS = 'audit_stats'
    PROCESSING_CONTEXT = 'processing_context'
    
    # Error handling
    PENDING_ERRORS = 'pending_errors'


class SessionStateGroups:
    """Logical groupings of session state keys for bulk operations"""
    
    CORE_DATA = [
        SessionStateKeys.XML_FILENAME,
        SessionStateKeys.XML_CONTENT,
        SessionStateKeys.XML_RAW_BYTES,
        SessionStateKeys.UPLOADED_FILENAME,
        SessionStateKeys.LAST_PROCESSED_FILE
    ]
    
    PROCESSING_STATE = [
        SessionStateKeys.IS_PROCESSING,
        SessionStateKeys.PROCESSING_CONTEXT,
        'progress_placeholder',
        'processing_placeholder'
    ]
    
    RESULTS_DATA = [
        SessionStateKeys.RESULTS,
        SessionStateKeys.SEARCH_RESULTS,
        SessionStateKeys.REPORT_RESULTS,
        SessionStateKeys.XML_STRUCTURE_ANALYSIS,
        SessionStateKeys.SEARCH_ANALYSIS,
        SessionStateKeys.EMIS_GUIDS,
        SessionStateKeys.AUDIT_STATS
    ]
    
    LOOKUP_DATA = [
        SessionStateKeys.LOOKUP_DF,
        SessionStateKeys.LOOKUP,
        SessionStateKeys.EMIS_GUID_COL,
        SessionStateKeys.SNOMED_CODE_COL,
        SessionStateKeys.LOOKUP_VERSION_INFO,
        SessionStateKeys.LOOKUP_PERFORMANCE,
        SessionStateKeys.MATCHED_EMIS_SNOMED_CACHE,
        SessionStateKeys.MATCHED_EMIS_SNOMED_TIMESTAMP
    ]
    
    USER_PREFERENCES = [
        SessionStateKeys.CURRENT_DEDUPLICATION_MODE,
        SessionStateKeys.CHILD_VIEW_MODE,
        SessionStateKeys.DEBUG_MODE,
        SessionStateKeys.FORCE_MEMORY_REFRESH,
        SessionStateKeys.CLINICAL_INCLUDE_REPORT_CODES,
        SessionStateKeys.CLINICAL_SHOW_CODE_SOURCES
    ]
    
    NHS_TERMINOLOGY = [
        SessionStateKeys.NHS_CONNECTION_STATUS,
        SessionStateKeys.EXPANSION_IN_PROGRESS,
        SessionStateKeys.EXPANSION_STATUS
    ]
    
    SYSTEM_MONITORING = [
        SessionStateKeys.MEMORY_PEAK_MB,
        SessionStateKeys.PENDING_ERRORS
    ]


def clear_processing_state() -> None:
    """Clear all processing-related session state"""
    for key in SessionStateGroups.PROCESSING_STATE:
        if key in st.session_state:
            del st.session_state[key]


def clear_results_state() -> None:
    """Clear all results and analysis data"""
    cleared_keys = []
    for key in SessionStateGroups.RESULTS_DATA:
        if key in st.session_state:
            del st.session_state[key]
            cleared_keys.append(key)
    
    # Debug logging
    if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        print(f"[CLEAR_RESULTS] Cleared keys: {cleared_keys}")
        remaining_results = {k: v for k, v in st.session_state.items() if 'result' in k.lower()}
        if remaining_results:
            print(f"[CLEAR_RESULTS] WARNING: Remaining result keys: {list(remaining_results.keys())}")


def clear_export_state() -> None:
    """Clear all export-related cache keys and perform garbage collection"""
    keys_to_remove = []
    for key in st.session_state.keys():
        if (key.startswith(SessionStateKeys.EXCEL_CACHE_PREFIX) or
            key.startswith(SessionStateKeys.JSON_CACHE_PREFIX) or
            key.startswith('export_')):
            keys_to_remove.append(key)
    
    # Remove export cache keys from session state
    for key in keys_to_remove:
        del st.session_state[key]
    
    # Clear unified export cache (includes txt, csv, xlsx, json files)
    from ..utils.caching.cache_manager import CacheManager
    cleared_count = CacheManager.clear_all_export_cache()
    
    # Force garbage collection to free memory from export objects
    import gc
    gc.collect()
    
    if cleared_count > 0 and st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        print(f"[EXPORT CLEAR] Cleared {cleared_count} export cache entries and performed GC")


def clear_report_state(report_type_name: Optional[str] = None) -> None:
    """Clear report-specific UI state
    
    Args:
        report_type_name: Specific report type to clear, or None for all
    """
    if report_type_name:
        # Clear specific report type
        keys_to_clear = [
            f'{SessionStateKeys.CACHED_SELECTED_REPORT_PREFIX}{report_type_name}',
            SessionStateKeys.SELECTED_TEXT_PREFIX.format(report_type_name),
            SessionStateKeys.PREVIOUS_SELECTED_PREFIX.format(report_type_name),
            f'{report_type_name}{SessionStateKeys.RENDERING_STATE_SUFFIX}',
            f'{report_type_name}{SessionStateKeys.RENDERING_UPDATED_SUFFIX}'
        ]
        
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
    else:
        # Clear all report state
        keys_to_remove = []
        for key in st.session_state.keys():
            if (key.startswith(SessionStateKeys.CACHED_SELECTED_REPORT_PREFIX) or
                SessionStateKeys.RENDERING_STATE_SUFFIX in key or
                SessionStateKeys.RENDERING_UPDATED_SUFFIX in key or
                any(pattern in key for pattern in ['selected_', 'previous_selected_'])):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del st.session_state[key]


def clear_analysis_state() -> None:
    """Clear analysis and visualization cache"""
    keys_to_remove = []
    for key in st.session_state.keys():
        if (key.startswith(SessionStateKeys.TREE_TEXT_PREFIX) or
            key.startswith(SessionStateKeys.TREE_JSON_PREFIX) or
            key.startswith(SessionStateKeys.DEP_TREE_TEXT_PREFIX) or
            key.startswith(SessionStateKeys.CACHE_KEY_PREFIX)):
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del st.session_state[key]


def clear_cache_state() -> None:
    """Clear all cache-related session state"""
    keys_to_remove = []
    for key in st.session_state.keys():
        if (key.startswith(SessionStateKeys.CACHE_KEY_PREFIX) or
            key.startswith(SessionStateKeys.NHS_TERMINOLOGY_CACHE_PREFIX) or
            key.endswith(SessionStateKeys.PAGE_KEY_SUFFIX) or
            key.endswith(SessionStateKeys.PROCESSING_CACHE_SUFFIX) or
            key.endswith(SessionStateKeys.TRANSLATION_CACHE_SUFFIX)):
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del st.session_state[key]


def clear_ui_state() -> None:
    """Clear UI-specific cache while preserving user preferences"""
    keys_to_remove = []
    
    # Clear dynamic UI keys
    for key in st.session_state.keys():
        if (key.startswith(SessionStateKeys.CACHED_SELECTED_REPORT_PREFIX) or
            key.endswith(SessionStateKeys.RENDERING_STATE_SUFFIX) or
            key.endswith(SessionStateKeys.RENDERING_UPDATED_SUFFIX) or
            'selected_' in key and key.endswith('_text')):
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del st.session_state[key]


def clear_for_new_xml_selection() -> None:
    """
    Lightweight clearing for when a new XML file is selected (but not yet processed).
    
    Clears:
    - Previous XML processing results only
    - UI state from previous file
    - XML content from previous file
    
    Preserves:
    - SNOMED lookup cache (keeps status bar loaded)
    - User preferences
    - NHS terminology cache
    - System state
    """
    # Clear only results from previous XML processing
    clear_results_state()     # Previous XML results
    clear_ui_state()         # UI state from previous file
    clear_report_state()     # Report UI state
    
    # Clear XML content from previous file since it's stale
    if SessionStateKeys.XML_CONTENT in st.session_state:
        del st.session_state[SessionStateKeys.XML_CONTENT]
    
    # Do NOT clear export cache or perform heavy cleanup yet
    # This preserves lookup cache so status bar doesn't reload
    
    if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        print("[XML SELECTED] Cleared previous results and XML content, preserved lookup cache")


def clear_for_new_xml() -> None:
    """
    Comprehensive clearing for new XML upload.
    
    Clears:
    - All processing results and analysis data
    - All export cache (txt, csv, xlsx, json files) with GC
    - All UI and rendering state
    - All analysis and visualization cache
    
    Preserves:
    - SNOMED lookup cache (LOOKUP_DF, LOOKUP, etc.)
    - User preferences (debug mode, deduplication mode, etc.)
    - System configuration
    """
    # Clear main data categories
    clear_results_state()     # Analysis results
    clear_processing_state()  # Processing flags
    clear_export_state()      # Export cache + GC
    clear_ui_state()         # UI cache
    clear_analysis_state()   # Visualization cache
    clear_report_state()     # Report UI state
    
    # Additional cleanup for any remaining dynamic keys (except preserved ones)
    preserve_keys = set(SessionStateGroups.LOOKUP_DATA + 
                       SessionStateGroups.USER_PREFERENCES + 
                       [SessionStateKeys.SESSION_ID])
    
    keys_to_remove = []
    for key in st.session_state.keys():
        if (key not in preserve_keys and 
            not key.startswith(SessionStateKeys.NHS_TERMINOLOGY_CACHE_PREFIX)):  # Keep NHS cache too
            # Check if it's a dynamic key we want to clear
            if (key.startswith(SessionStateKeys.CACHE_KEY_PREFIX) or
                key.startswith(SessionStateKeys.EXCEL_CACHE_PREFIX) or
                key.startswith(SessionStateKeys.JSON_CACHE_PREFIX) or
                key.startswith(SessionStateKeys.TREE_TEXT_PREFIX) or
                '_processing' in key or '_rendering' in key):
                keys_to_remove.append(key)
    
    # Remove remaining keys
    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]
    
    # Force comprehensive garbage collection
    import gc
    gc.collect()
    
    if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        preserved_count = len([k for k in st.session_state.keys() if k in preserve_keys])
        print(f"[NEW XML] Cleared all data except {preserved_count} preserved keys (lookup cache + preferences)")


def clear_all_except_core() -> None:
    """Clear all session state except core data and user preferences"""
    preserve_keys = set(SessionStateGroups.CORE_DATA + SessionStateGroups.USER_PREFERENCES + SessionStateGroups.LOOKUP_DATA)
    
    keys_to_remove = []
    for key in st.session_state.keys():
        if key not in preserve_keys:
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del st.session_state[key]
    
    # Force garbage collection after major cleanup
    gc.collect()


def get_dynamic_key(pattern: str, *args) -> str:
    """Generate dynamic session state key from pattern
    
    Args:
        pattern: Key pattern with {} placeholders
        *args: Values to format into pattern
        
    Returns:
        Formatted key string
        
    Example:
        get_dynamic_key(SessionStateKeys.SELECTED_TEXT_PREFIX, 'audit_report')
        # Returns: 'selected_audit_report_text'
    """
    try:
        return pattern.format(*args)
    except (IndexError, KeyError) as e:
        raise ValueError(f"Invalid key pattern '{pattern}' with args {args}: {e}")


def validate_session_state() -> Dict[str, any]:
    """Validate session state integrity and return summary
    
    Returns:
        Dictionary with validation results and recommendations
    """
    issues = []
    recommendations = []
    stats = {
        'total_keys': len(st.session_state),
        'core_data_present': 0,
        'cache_keys': 0,
        'export_keys': 0,
        'orphaned_keys': []
    }
    
    # Check core data presence
    for key in SessionStateGroups.CORE_DATA:
        if key in st.session_state:
            stats['core_data_present'] += 1
    
    # Count different key types
    for key in st.session_state.keys():
        if key.startswith(SessionStateKeys.CACHE_KEY_PREFIX):
            stats['cache_keys'] += 1
        elif key.startswith((SessionStateKeys.EXCEL_CACHE_PREFIX, SessionStateKeys.JSON_CACHE_PREFIX)):
            stats['export_keys'] += 1
        elif not any(key.startswith(prefix) or key in SessionStateGroups.CORE_DATA + 
                    SessionStateGroups.USER_PREFERENCES + SessionStateGroups.LOOKUP_DATA
                    for prefix in [SessionStateKeys.CACHED_SELECTED_REPORT_PREFIX, 
                                 SessionStateKeys.TREE_TEXT_PREFIX,
                                 SessionStateKeys.NHS_TERMINOLOGY_CACHE_PREFIX]):
            stats['orphaned_keys'].append(key)
    
    # Validation checks
    if SessionStateKeys.XML_CONTENT in st.session_state and SessionStateKeys.XML_FILENAME not in st.session_state:
        issues.append("XML content present but filename missing")
        recommendations.append("Ensure XML filename is set when content is loaded")
    
    if stats['cache_keys'] > 50:
        issues.append(f"High cache count: {stats['cache_keys']} keys")
        recommendations.append("Consider clearing cache with clear_cache_state()")
    
    if stats['orphaned_keys']:
        issues.append(f"Found {len(stats['orphaned_keys'])} orphaned keys")
        recommendations.append("Review orphaned keys for cleanup opportunities")
    
    return {
        'stats': stats,
        'issues': issues,
        'recommendations': recommendations,
        'healthy': len(issues) == 0
    }


def get_session_state_summary() -> Dict[str, any]:
    """Get summary of current session state for debugging
    
    Returns:
        Summary dictionary with key counts and status
    """
    summary = {
        'total_keys': len(st.session_state),
        'groups': {}
    }
    
    # Count keys by group
    for group_name, keys in [
        ('core_data', SessionStateGroups.CORE_DATA),
        ('processing', SessionStateGroups.PROCESSING_STATE),
        ('results', SessionStateGroups.RESULTS_DATA),
        ('lookup', SessionStateGroups.LOOKUP_DATA),
        ('preferences', SessionStateGroups.USER_PREFERENCES)
    ]:
        present = sum(1 for key in keys if key in st.session_state)
        summary['groups'][group_name] = {
            'present': present,
            'total': len(keys),
            'keys': [key for key in keys if key in st.session_state]
        }
    
    # Count dynamic keys
    dynamic_counts = {}
    for key in st.session_state.keys():
        if key.startswith(SessionStateKeys.CACHE_KEY_PREFIX):
            dynamic_counts['cache'] = dynamic_counts.get('cache', 0) + 1
        elif key.startswith(SessionStateKeys.EXCEL_CACHE_PREFIX):
            dynamic_counts['excel_export'] = dynamic_counts.get('excel_export', 0) + 1
        elif key.startswith(SessionStateKeys.JSON_CACHE_PREFIX):
            dynamic_counts['json_export'] = dynamic_counts.get('json_export', 0) + 1
        elif key.startswith(SessionStateKeys.TREE_TEXT_PREFIX):
            dynamic_counts['tree_viz'] = dynamic_counts.get('tree_viz', 0) + 1
    
    summary['dynamic_keys'] = dynamic_counts
    return summary


def validate_state_keys() -> tuple[bool, list[str]]:
    """
    Validate session state keys and return any issues.
    
    Returns:
        tuple: (is_valid, list_of_issues)
    """
    issues = []
    
    # Check for unknown keys that might be typos
    all_known_keys = set()
    for group in [SessionStateGroups.CORE_DATA, SessionStateGroups.PROCESSING_STATE, 
                  SessionStateGroups.RESULTS_DATA, SessionStateGroups.LOOKUP_DATA, 
                  SessionStateGroups.USER_PREFERENCES, SessionStateGroups.NHS_TERMINOLOGY,
                  SessionStateGroups.SYSTEM_MONITORING]:
        all_known_keys.update(group)
    
    # Add dynamic key prefixes
    dynamic_prefixes = [
        SessionStateKeys.CACHE_KEY_PREFIX,
        SessionStateKeys.EXCEL_CACHE_PREFIX,
        SessionStateKeys.JSON_CACHE_PREFIX,
        SessionStateKeys.TREE_TEXT_PREFIX,
        SessionStateKeys.DEP_TREE_TEXT_PREFIX,
        SessionStateKeys.NHS_TERMINOLOGY_CACHE_PREFIX,
        SessionStateKeys.CACHED_SELECTED_REPORT_PREFIX
    ]
    
    unknown_keys = []
    for key in st.session_state.keys():
        if key not in all_known_keys:
            # Check if it matches a dynamic pattern
            is_dynamic = any(key.startswith(prefix) for prefix in dynamic_prefixes)
            if not is_dynamic:
                unknown_keys.append(key)
    
    if unknown_keys:
        issues.append(f"Unknown session state keys found: {unknown_keys}")
    
    # Check for missing critical keys
    critical_keys = [SessionStateKeys.SESSION_ID]
    missing_critical = [key for key in critical_keys if key not in st.session_state]
    if missing_critical:
        issues.append(f"Missing critical keys: {missing_critical}")
    
    return len(issues) == 0, issues


def get_state_debug_info() -> dict:
    """
    Get comprehensive debug information about session state.
    
    Returns:
        dict: Debug information categorized by key groups
    """
    debug_info = {
        'total_keys': len(st.session_state.keys()),
        'core_data': [],
        'processing_state': [],
        'results_data': [],
        'lookup_data': [],
        'user_preferences': [],
        'nhs_terminology': [],
        'system_monitoring': [],
        'dynamic_keys': {},
        'unknown_keys': []
    }
    
    # Categorize keys
    all_known_keys = set()
    for group_name, group_keys in [
        ('core_data', SessionStateGroups.CORE_DATA),
        ('processing_state', SessionStateGroups.PROCESSING_STATE),
        ('results_data', SessionStateGroups.RESULTS_DATA),
        ('lookup_data', SessionStateGroups.LOOKUP_DATA),
        ('user_preferences', SessionStateGroups.USER_PREFERENCES),
        ('nhs_terminology', SessionStateGroups.NHS_TERMINOLOGY),
        ('system_monitoring', SessionStateGroups.SYSTEM_MONITORING)
    ]:
        present_keys = [key for key in group_keys if key in st.session_state]
        debug_info[group_name] = present_keys
        all_known_keys.update(group_keys)
    
    # Count dynamic keys
    dynamic_counts = {}
    for key in st.session_state.keys():
        if key.startswith(SessionStateKeys.CACHE_KEY_PREFIX):
            dynamic_counts['cache'] = dynamic_counts.get('cache', 0) + 1
        elif key.startswith(SessionStateKeys.EXCEL_CACHE_PREFIX):
            dynamic_counts['excel_export'] = dynamic_counts.get('excel_export', 0) + 1
        elif key.startswith(SessionStateKeys.JSON_CACHE_PREFIX):
            dynamic_counts['json_export'] = dynamic_counts.get('json_export', 0) + 1
        elif key.startswith(SessionStateKeys.TREE_TEXT_PREFIX):
            dynamic_counts['tree_visualization'] = dynamic_counts.get('tree_visualization', 0) + 1
        elif key.startswith(SessionStateKeys.NHS_TERMINOLOGY_CACHE_PREFIX):
            dynamic_counts['nhs_terminology'] = dynamic_counts.get('nhs_terminology', 0) + 1
        elif key not in all_known_keys:
            debug_info['unknown_keys'].append(key)
    
    debug_info['dynamic_keys'] = dynamic_counts
    return debug_info


def debug_session_state() -> None:
    """
    Display detailed session state information for debugging.
    Only shows output when DEBUG_MODE is enabled in session state.
    
    This prevents unnecessary computation and UI elements when debugging is disabled.
    """
    # Early return if debug mode is not enabled - prevents any computation
    if not st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        return
    
    # Only compute debug information when debug mode is active
    validation = validate_session_state()
    summary = get_session_state_summary()
    debug_info = get_state_debug_info()
    
    # Display debug interface
    with st.expander("🔧 Session State Debug", expanded=False):
        st.markdown("**Session State Validation**")
        if validation.get('issues'):
            st.markdown(error_box("Issues found:"), unsafe_allow_html=True)
            for issue in validation['issues']:
                st.write(f"- {issue}")
        else:
            st.markdown(success_box("No validation issues found"), unsafe_allow_html=True)
        
        st.markdown("**State Summary**")
        st.json(summary)
        
        st.markdown("**Debug Information**")
        st.json(debug_info)


def log_state_change(key: str, operation: str = "modified") -> None:
    """
    Log session state changes when debug mode is enabled.
    
    Args:
        key: The session state key that was modified
        operation: Type of operation (modified, deleted, added)
    """
    if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        import sys
        print(f"[DEBUG] Session state {operation}: {key}", file=sys.stderr)


def get_snomed_cache_ttl_minutes() -> int:
    """Get TTL for SNOMED cache in minutes (60 minutes = 1 hour)"""
    return 60


def is_snomed_cache_valid() -> bool:
    """
    Check if the SNOMED cache is still valid based on TTL.
    
    Returns:
        bool: True if cache is valid, False if expired or missing
    """
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
            print(f"[SNOMED CACHE] Age: {age_minutes:.1f}min, TTL: {ttl_minutes}min, Valid: {is_valid}")
        
        return is_valid
    except (ValueError, TypeError):
        return False


def get_cached_snomed_mappings() -> dict:
    """
    Get cached EMIS GUID → SNOMED mappings if still valid.
    
    Returns:
        dict: EMIS GUID → SNOMED Code mappings, empty if expired/missing
    """
    if not is_snomed_cache_valid():
        return {}
    
    cache = st.session_state.get(SessionStateKeys.MATCHED_EMIS_SNOMED_CACHE, {})
    
    if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        print(f"[SNOMED CACHE] Retrieved {len(cache)} cached mappings")
    
    return cache


def update_snomed_cache(new_mappings: dict) -> None:
    """
    Update the SNOMED cache with new EMIS GUID → SNOMED mappings.
    
    Args:
        new_mappings: Dict of EMIS GUID → SNOMED Code mappings to add/update
    """
    from datetime import datetime
    
    # Get existing cache or start fresh
    existing_cache = get_cached_snomed_mappings() if is_snomed_cache_valid() else {}
    
    # Merge new mappings
    existing_cache.update(new_mappings)
    
    # Update cache and timestamp
    st.session_state[SessionStateKeys.MATCHED_EMIS_SNOMED_CACHE] = existing_cache
    st.session_state[SessionStateKeys.MATCHED_EMIS_SNOMED_TIMESTAMP] = datetime.now().isoformat()
    
    if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        print(f"[SNOMED CACHE] Updated with {len(new_mappings)} new mappings, total: {len(existing_cache)}")


def clear_expired_snomed_cache() -> bool:
    """
    Clear SNOMED cache if expired.
    
    Returns:
        bool: True if cache was cleared, False if still valid
    """
    if not is_snomed_cache_valid():
        if SessionStateKeys.MATCHED_EMIS_SNOMED_CACHE in st.session_state:
            del st.session_state[SessionStateKeys.MATCHED_EMIS_SNOMED_CACHE]
        if SessionStateKeys.MATCHED_EMIS_SNOMED_TIMESTAMP in st.session_state:
            del st.session_state[SessionStateKeys.MATCHED_EMIS_SNOMED_TIMESTAMP]
        
        if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
            print("[SNOMED CACHE] Expired cache cleared")
        return True
    return False
