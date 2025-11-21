"""
UI Components for SNOMED Code Expansion

This module provides Streamlit UI components for interacting with
the NHS Terminology Server expansion functionality.
"""

import streamlit as st
import pandas as pd
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import io
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..utils.export_debug import log_export_created, track_export_object, log_memory_after_export
from ..export_handlers.terminology_export import TerminologyExportHandler
from ..core.session_state import SessionStateKeys
import threading
import queue
import time
import gc

from .expansion_service import get_expansion_service
from .nhs_terminology_client import get_terminology_client
from ..utils.caching.lookup_cache import get_cached_emis_lookup


def _pure_worker_expand_code(code_entry, include_inactive, result_queue, worker_id, client_id, client_secret, debug_mode=False):
    """Pure worker function - API calls only, no EMIS processing or caching"""
    try:
        snomed_code = code_entry.get('SNOMED Code', '').strip()
        if debug_mode:
            print(f"DEBUG Worker {worker_id}: Starting with code {snomed_code}")
        
        if not snomed_code:
            if debug_mode:
                print(f"DEBUG Worker {worker_id}: No SNOMED code")
            result_queue.put({
                'worker_id': worker_id,
                'snomed_code': snomed_code,
                'code_entry': code_entry,
                'success': False,
                'error': 'No SNOMED code provided',
                'raw_result': None
            })
            return
        
        # Create terminology client with explicit credentials (no Streamlit dependencies)
        from .nhs_terminology_client import NHSTerminologyClient
        client = NHSTerminologyClient()
        # Override credentials directly
        client.client_id = client_id
        client.client_secret = client_secret
        
        # Perform expansion (pure API call) - no caching, no processing
        if debug_mode:
            print(f"DEBUG Worker {worker_id}: Calling API...")
        expansion_result = client._expand_concept_uncached(snomed_code, include_inactive)
        if debug_mode:
            print(f"DEBUG Worker {worker_id}: API call done, result: {expansion_result is not None}")
        
        # Determine success status
        success = expansion_result is not None and not expansion_result.error
        error_msg = expansion_result.error if expansion_result else 'No expansion result returned'
        if debug_mode:
            print(f"DEBUG Worker {worker_id}: Success: {success}, Error: {error_msg[:50] if error_msg else 'None'}")
        
        # Put raw result in queue for main thread processing
        result_queue.put({
            'worker_id': worker_id,
            'snomed_code': snomed_code,
            'code_entry': code_entry,
            'success': success,
            'error': error_msg,
            'raw_result': expansion_result
        })
        if debug_mode:
            print(f"DEBUG Worker {worker_id}: Result queued")
        
    except Exception as e:
        if debug_mode:
            print(f"DEBUG Worker {worker_id}: Exception: {str(e)}")
        # Put error in queue
        result_queue.put({
            'worker_id': worker_id,
            'snomed_code': code_entry.get('SNOMED Code', 'unknown'),
            'code_entry': code_entry,
            'success': False,
            'error': str(e),
            'raw_result': None
        })


# Removed _clean_dataframe_for_export - now handled by TerminologyExportHandler._clean_dataframe_for_export()


def _escape_xml(text: str) -> str:
    """Escape special characters for XML compatibility"""
    if not text or str(text) == 'nan':
        return ''
    
    text = str(text)
    # XML entity escaping
    text = text.replace('&', '&amp;')  # Must be first
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&apos;')
    
    return text


def _create_xml_output(emis_guid: str, description: str) -> str:
    """Create XML wrapper for EMIS GUID with proper escaping"""
    if not emis_guid or emis_guid == 'Not in EMIS lookup table':
        return 'N/A - No EMIS GUID available'
    
    # Clean EMIS GUID (remove emoji if present)
    clean_guid = emis_guid.replace('🔍 ', '').strip()
    
    # Escape description for XML (quotes only if they're in the original text)
    escaped_desc = _escape_xml(description)
    
    # Build XML structure without adding quotes
    xml_output = f'<values><value>{clean_guid}</value><displayName>{escaped_desc}</displayName><includeChildren>false</includeChildren></values>'
    
    return xml_output


def _create_hierarchical_json(all_child_codes: List[Dict], view_mode: str) -> Dict:
    """
    Create hierarchical JSON structure showing parent-child relationships.
    Ignores filters and shows unique parents only with their child codes.
    
    Args:
        all_child_codes: List of all child code dictionaries
        view_mode: Current view mode (affects structure organization)
    
    Returns:
        Dict: Hierarchical JSON structure with parent-child relationships
    """
    # Group children by parent
    parent_children_map = {}
    
    for child in all_child_codes:
        # Get clean codes (remove emojis)
        parent_code = str(child.get('Parent Code', '')).replace('⚕️ ', '').strip()
        parent_display = str(child.get('Parent Display', '')).strip()
        child_code = str(child.get('Child Code', '')).replace('⚕️ ', '').strip()
        child_display = str(child.get('Child Display', '')).strip()
        
        # Skip if we don't have essential data
        if not parent_code or not child_code:
            continue
        
        # Initialize parent entry if not exists
        if parent_code not in parent_children_map:
            parent_children_map[parent_code] = {
                'parent_code': parent_code,
                'parent_display': parent_display,
                'children': []
            }
        
        # Add child (avoid duplicates in unique mode)
        child_entry = {
            'code': child_code,
            'display': child_display
        }
        
        # In unique mode, avoid duplicate children
        if view_mode == "🔀 Unique Codes":
            # Check if this child already exists for this parent
            existing_codes = [c['code'] for c in parent_children_map[parent_code]['children']]
            if child_code not in existing_codes:
                parent_children_map[parent_code]['children'].append(child_entry)
        else:
            # In per-source mode, include all instances
            parent_children_map[parent_code]['children'].append(child_entry)
    
    # Get source XML filename from session state
    source_xml_filename = st.session_state.get(SessionStateKeys.XML_FILENAME, 'Unknown XML file')
    
    # Build final hierarchical structure
    hierarchy = {
        'export_metadata': {
            'export_type': 'hierarchical_terminology_expansion',
            'export_timestamp': datetime.now().isoformat(),
            'source_xml_file': source_xml_filename,
            'view_mode': view_mode.replace('🔀 ', '').replace('📄 ', '').lower().replace(' ', '_'),
            'total_unique_parents': len(parent_children_map),
            'total_child_relationships': sum(len(p['children']) for p in parent_children_map.values()),
            'description': 'Parent-child SNOMED code relationships from NHS Terminology Server expansion'
        },
        'parent_child_hierarchy': []
    }
    
    # Sort parents by code for consistent output
    sorted_parents = sorted(parent_children_map.items(), key=lambda x: x[0])
    
    for parent_code, parent_data in sorted_parents:
        # Sort children by code for consistent output
        sorted_children = sorted(parent_data['children'], key=lambda x: x['code'])
        
        parent_entry = {
            'parent': {
                'code': parent_data['parent_code'],
                'display': parent_data['parent_display']
            },
            'children': sorted_children,
            'child_count': len(sorted_children)
        }
        
        hierarchy['parent_child_hierarchy'].append(parent_entry)
    
    return hierarchy


# Also suppress Streamlit logging warnings about ScriptRunContext
streamlit_logger = logging.getLogger('streamlit.runtime.scriptrunner.script_runner')
streamlit_logger.setLevel(logging.ERROR)


def render_terminology_server_status():
    """Render NHS Terminology Server connection status in sidebar"""
    # Make NHS Terminology Server expandable like other sections
    with st.expander("🏥 NHS Term Server", expanded=False):
        # Initialize shared session state for connection status if not exists
        if SessionStateKeys.NHS_CONNECTION_STATUS not in st.session_state:
            st.session_state[SessionStateKeys.NHS_CONNECTION_STATUS] = None
        
        client = get_terminology_client()
        
        # Test connection button and status display as fragment for isolated execution
        @st.fragment
        def connection_test_fragment():
            if st.button("🔗 Test Connection", key="test_nhs_connection"):
                with st.spinner("Testing connection..."):
                    success, message = client.test_connection()
                    # Store test result in shared session state
                    st.session_state[SessionStateKeys.NHS_CONNECTION_STATUS] = {
                        'success': success,
                        'message': message,
                        'tested': True
                    }
                    # Show toast notification
                    if success:
                        st.toast("✅ Connected to NHS Terminology Server!", icon="🎉")
                    else:
                        st.toast("❌ Failed to connect to NHS Terminology Server", icon="⚠️")
                    # Fragment will auto-rerun to show updated status
            
            # Show connection status using shared session state (inside fragment for live updates)
            if st.session_state[SessionStateKeys.NHS_CONNECTION_STATUS] and st.session_state[SessionStateKeys.NHS_CONNECTION_STATUS].get('tested'):
                # Show test result
                if st.session_state[SessionStateKeys.NHS_CONNECTION_STATUS]['success']:
                    st.markdown("""
                    <div style="
                        background-color: #1F4E3D;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1.0rem;
                    ">
                        🔑 Authenticated
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style="
                        background-color: #660022;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1.0rem;
                    ">
                        🔑 Connection failed
                    </div>
                    """, unsafe_allow_html=True)
            else:
                # Show default status based on token validity
                if client._is_token_valid():
                    st.markdown("""
                    <div style="
                        background-color: #1F4E3D;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1.0rem;
                    ">
                        🔑 Authenticated
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style="
                        background-color: #7A5F0B;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1.0rem;
                    ">
                        🔑 Not authenticated
                    </div>
                    """, unsafe_allow_html=True)
        
        connection_test_fragment()


def render_expansion_controls(clinical_data: List[Dict]) -> Optional[Dict]:
    """
    Render expansion controls and return expansion results if performed
    
    Args:
        clinical_data: List of clinical code dictionaries
        
    Returns:
        Dictionary with expansion results or None
    """
    service = get_expansion_service()
    
    # Find codes that can be expanded (initially without filtering)
    all_expandable_codes = service.find_codes_with_include_children(clinical_data, filter_zero_descendants=False)
    
    if not all_expandable_codes:
        st.markdown("""
        <div style="
            background-color: #28546B;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 0.5rem;
        ">
            ℹ️ No codes with includechildren=True found in this dataset
        </div>
        """, unsafe_allow_html=True)
        return None
    
    st.markdown("### ⚕️ SNOMED Code Expansion")
    
    # Deduplicate codes and track source information
    code_sources = {}  # SNOMED code -> list of source entries
    unique_codes = {}  # SNOMED code -> representative entry
    
    for code_entry in all_expandable_codes:
        snomed_code = code_entry.get('SNOMED Code', '').strip()
        if snomed_code:
            if snomed_code not in code_sources:
                code_sources[snomed_code] = []
                unique_codes[snomed_code] = code_entry
            
            # Track source information for this code
            source_info = {
                'Source Type': code_entry.get('Source Type', 'Unknown'),
                'Source Name': code_entry.get('Source Name', 'Unknown'),
                'Source Container': code_entry.get('Source Container', 'Unknown'),
                'SNOMED Description': code_entry.get('SNOMED Description', ''),
                'Descendants': code_entry.get('Descendants', '')
            }
            code_sources[snomed_code].append(source_info)
    
    # Apply filtering and show dynamic summary with deduplication info in two-column layout
    original_count = len(all_expandable_codes)
    unique_count = len(unique_codes)
    dedupe_savings = original_count - unique_count
    
    # Two-column layout: info message + checkboxes
    info_col, options_col = st.columns([1, 1])
    
    # Get checkbox values in right column - arrange in 3 sub-columns for horizontal layout
    with options_col:
        cb_col1, cb_col2, cb_col3 = st.columns(3)
        
        with cb_col1:
            st.markdown("")
            include_inactive = st.checkbox(
                "Include inactive concepts",
                value=False,
                help="Include concepts that are inactive/deprecated in SNOMED CT"
            )
        
        with cb_col2:
            st.markdown("")
            use_cache = st.checkbox(
                "Use cached results",
                value=True,
                help="Use previously cached expansion results (24h expiry)"
            )
        
        with cb_col3:
            st.markdown("")
            filter_zero_descendants = st.checkbox(
                "Skip codes with 0 descendants",
                value=True,
                help="Filter out codes already known to have no child concepts (saves API calls)"
            )
    
    # Show info message in left column
    with info_col:
        if filter_zero_descendants:
            # Count codes with 0 descendants before filtering
            zero_descendant_count = sum(1 for code in unique_codes.values() 
                                      if str(code.get('Descendants', '')).strip() == '0')
            
            if zero_descendant_count > 0:
                remaining_codes = unique_count - zero_descendant_count
                if dedupe_savings > 0:
                    st.markdown(f"""
                    <div style="
                        background-color: #28546B;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1.0rem;
                    ">
                        Found {original_count} expandable codes → {unique_count} unique codes (saved {dedupe_savings} duplicate API calls) → {remaining_codes} after filtering 0-descendant codes
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="
                        background-color: #28546B;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1.0rem;
                    ">
                        Found {unique_count} codes that can be expanded - filtered out {zero_descendant_count} codes with 0 descendants (saves API calls), {remaining_codes} codes will be processed
                    </div>
                    """, unsafe_allow_html=True)
                # Apply the actual filtering
                expandable_codes = [code for code in unique_codes.values() 
                                  if str(code.get('Descendants', '')).strip() != '0']
            else:
                if dedupe_savings > 0:
                    st.markdown(f"""
                    <div style="
                        background-color: #28546B;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1.0rem;
                    ">
                        Found {original_count} expandable codes → {unique_count} unique codes (saved {dedupe_savings} duplicate API calls)
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="
                        background-color: #28546B;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1.0rem;
                    ">
                        Found {unique_count} codes that can be expanded to include child concepts
                    </div>
                    """, unsafe_allow_html=True)
                expandable_codes = list(unique_codes.values())
        else:
            if dedupe_savings > 0:
                st.markdown(f"""
                <div style="
                    background-color: #5B2758;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 0.5rem;
                ">
                    Found {original_count} expandable codes → {unique_count} unique codes (saved {dedupe_savings} duplicate API calls)
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="
                    background-color: #5B2758;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 0.5rem;
                ">
                    Found {unique_count} codes that can be expanded to include child concepts
                </div>
                """, unsafe_allow_html=True)
            expandable_codes = list(unique_codes.values())
    
    # Expansion button with protection against double-clicks
    if SessionStateKeys.EXPANSION_IN_PROGRESS not in st.session_state:
        st.session_state[SessionStateKeys.EXPANSION_IN_PROGRESS] = False
    
    if st.button("🌳 Expand Child Codes", type="primary", disabled=st.session_state.get(SessionStateKeys.EXPANSION_IN_PROGRESS, False)):
        if not st.session_state.get(SessionStateKeys.EXPANSION_IN_PROGRESS, False):
            st.session_state[SessionStateKeys.EXPANSION_IN_PROGRESS] = True
            try:
                result = perform_expansion(expandable_codes, include_inactive, use_cache, code_sources)
                return result
            finally:
                st.session_state[SessionStateKeys.EXPANSION_IN_PROGRESS] = False
    
    return None


def _expand_single_code_with_emis_lookup(code_entry: Dict, include_inactive: bool, use_cache: bool, service, emis_lookup: Dict, code_sources: Dict = None) -> Tuple[str, any, List[Dict]]:
    """
    Expand a single SNOMED code and immediately process EMIS GUIDs for children
    
    Args:
        code_entry: Dictionary containing the code information
        include_inactive: Whether to include inactive concepts
        use_cache: Whether to use cached results
        service: The expansion service instance
        emis_lookup: Dictionary for SNOMED -> EMIS GUID mapping
        
    Returns:
        Tuple of (snomed_code, expansion_result, processed_child_codes)
    """
    snomed_code = code_entry.get('SNOMED Code', '').strip()
    if not snomed_code:
        return snomed_code, None, []
    
    # Get expansion result from terminology server
    result = service.expand_snomed_code(snomed_code, include_inactive, use_cache)
    
    # Immediately process child codes with EMIS GUID lookup and source tracking
    processed_children = []
    if not result.error and result.children:
        # Get source information for this parent code
        parent_sources = code_sources.get(snomed_code, []) if code_sources else []
        
        for child in result.children:
            # Simple direct lookup - no normalization
            child_code = str(child.code).strip()
            emis_guid = emis_lookup.get(child_code)
            emis_status = emis_guid if emis_guid else 'Not in EMIS lookup table'
            
            # Create child entries for each source this parent appears in
            if parent_sources:
                for source in parent_sources:
                    processed_children.append({
                        'Parent Code': snomed_code,
                        'Parent Display': result.source_display,
                        'Child Code': child.code,
                        'Child Display': child.display,
                        'EMIS GUID': emis_status,
                        'Inactive': 'True' if child.inactive else 'False',
                        'Source Type': source.get('Source Type', 'Unknown'),
                        'Source Name': source.get('Source Name', 'Unknown'),
                        'Source Container': source.get('Source Container', 'Unknown')
                    })
            else:
                # Fallback if no source information
                processed_children.append({
                    'Parent Code': snomed_code,
                    'Parent Display': result.source_display,
                    'Child Code': child.code,
                    'Child Display': child.display,
                    'EMIS GUID': emis_status,
                    'Inactive': 'True' if child.inactive else 'False',
                    'Source Type': 'Unknown',
                    'Source Name': 'Unknown',
                    'Source Container': 'Unknown'
                })
    
    return snomed_code, result, processed_children


def perform_expansion(expandable_codes: List[Dict], include_inactive: bool = False, use_cache: bool = True, code_sources: Dict = None) -> Dict:
    """
    Perform the actual expansion operation with concurrent processing and progress tracking
    
    Args:
        expandable_codes: List of codes to expand
        include_inactive: Whether to include inactive concepts
        use_cache: Whether to use cached results
        
    Returns:
        Dictionary with expansion results
    """
    service = get_expansion_service()
    
    # Create progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Show immediate feedback
    status_text.text("Starting expansion process...")
    
    # Clear any previous expansion status
    if SessionStateKeys.EXPANSION_STATUS in st.session_state:
        del st.session_state[SessionStateKeys.EXPANSION_STATUS]
    
    # Load pre-built EMIS lookup cache (built during XML processing)
    lookup_df = getattr(st.session_state, 'lookup_df', None)
    snomed_code_col = getattr(st.session_state, 'snomed_code_col', 'SNOMED Code')
    emis_guid_col = getattr(st.session_state, 'emis_guid_col', 'EMIS GUID')
    version_info = getattr(st.session_state, 'lookup_version_info', None)
    
    # Get debug mode from session state
    debug_mode = st.session_state.get(SessionStateKeys.DEBUG_MODE, False)
    
    status_text.text("Loading EMIS lookup cache...")
    
    # Load from persistent cache (should already be built during XML processing)
    cached_data = get_cached_emis_lookup(lookup_df, snomed_code_col, emis_guid_col, version_info)
    
    # Debug logging
    if cached_data is None:
        from ..utils.caching.lookup_cache import _get_lookup_table_hash
        expected_hash = _get_lookup_table_hash(lookup_df, version_info)
        st.markdown(f"""
        <div style="
            background-color: #7A5F0B;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 0.5rem;
        ">
            🔍 Debug: Cache lookup failed. Expected hash: {expected_hash}, Version info available: {version_info is not None}
        </div>
        """, unsafe_allow_html=True)
    
    if cached_data is not None:
        # Found persistent cache
        emis_lookup = cached_data['lookup_mapping']
        lookup_records = cached_data['lookup_records']
        status_text.text(f"✅ Loaded EMIS lookup cache ({len(emis_lookup)} mappings)")
        lookup_count = len(emis_lookup)
    else:
        # No cache available - cannot proceed with terminology server expansion
        status_text.text("❌ EMIS lookup cache not available")
        st.markdown("""
        <div style="
            background-color: #660022;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 0.5rem;
        ">
            ⚠️ EMIS lookup cache not found. Please process an XML file first to build the cache, then try expanding codes again.
        </div>
        """, unsafe_allow_html=True)
        st.stop()  # Stop execution here
    
    # Filter valid codes first
    valid_codes = [code for code in expandable_codes if code.get('SNOMED Code', '').strip()]
    total_codes = len(valid_codes)
    
    # Check session state for cached expansion results
    session_cache_key = f"expansion_cache_{include_inactive}"
    if session_cache_key not in st.session_state:
        st.session_state[session_cache_key] = {}
    
    cached_results = {}
    uncached_codes = []
    
    # Check which codes are already cached in session state
    for code_entry in valid_codes:
        snomed_code = code_entry.get('SNOMED Code', '').strip()
        if snomed_code in st.session_state[session_cache_key]:
            cached_results[snomed_code] = st.session_state[session_cache_key][snomed_code]
        else:
            uncached_codes.append(code_entry)
    
    cache_hits = len(cached_results)
    cache_misses = len(uncached_codes)
    
    status_text.text("Processing cached results...")
    
    expansion_results = cached_results.copy()  # Start with cached results
    all_processed_children = []
    total_child_codes = 0
    successful_expansions = cache_hits  # Count cached results as successful
    completed_count = 0
    first_success_toast_shown = False
    
    # Process cached results to generate processed children
    if cached_results:
        for snomed_code, cached_result in cached_results.items():
            if cached_result and not cached_result.error:
                # Find the original code entry for source information
                code_entry = next((code for code in valid_codes if code.get('SNOMED Code', '').strip() == snomed_code), None)
                
                if code_entry and cached_result.children:
                    for child in cached_result.children:
                        child_code = str(child.code).strip()
                        emis_guid = emis_lookup.get(child_code, 'Not in EMIS lookup table')
                        
                        child_data = {
                            'Parent Code': snomed_code,
                            'Parent Display': cached_result.source_display,
                            'Child Code': child.code,
                            'Child Display': child.display,
                            'EMIS GUID': emis_guid,
                            'Inactive': 'True' if child.inactive else 'False',
                            'Source Type': code_entry.get('Source Type', 'Unknown'),
                            'Source Name': code_entry.get('Source Name', 'Unknown'),
                            'Source Container': code_entry.get('Source Container', 'Unknown')
                        }
                        all_processed_children.append(child_data)
                        total_child_codes += 1
    
    # Show cache statistics if any cache hits
    if cache_hits > 0:
        status_text.text(f"✅ Using {cache_hits} cached results, fetching {cache_misses} new codes...")
    else:
        status_text.text("Starting terminology server connections...")
    
    try:
        # Get credentials in main thread (where Streamlit secrets are available)
        try:
            client_id = st.secrets["NHSTSERVER_ID"]
            client_secret = st.secrets["NHSTSERVER_TOKEN"]
        except KeyError as e:
            st.markdown(f"""
            <div style="
                background-color: #660022;
                padding: 0.75rem;
                border-radius: 0.5rem;
                color: #FAFAFA;
                text-align: left;
                margin-bottom: 0.5rem;
            ">
                Missing NHS Terminology Server credentials: {e}
            </div>
            """, unsafe_allow_html=True)
            return {
                'success': False,
                'message': f'Missing credential: {e}',
                'total_codes': 0,
                'successful_expansions': 0,
                'children': [],
                'results': {}
            }
        
        # If no codes need fetching, skip worker setup
        if not uncached_codes:
            # All results were cached!
            threads = []
            max_workers = 0
        else:
            # Adaptive worker scaling based on uncached workload size
            uncached_count = len(uncached_codes)
            if uncached_count <= 100:
                max_workers = 8   # Small workloads: conservative threading
            elif uncached_count <= 300:
                max_workers = 12  # Medium workloads: moderate threading  
            elif uncached_count <= 500:
                max_workers = 16  # Large workloads: high threading
            else:
                max_workers = 20  # Very large workloads: maximum threading
            
            max_workers = min(max_workers, uncached_count)  # Don't exceed available codes
            result_queue = queue.Queue()
        
            # Simple threading approach that works within memory limits
            threads = []
            for i, code_entry in enumerate(uncached_codes[:max_workers]):  # Start first batch
                thread = threading.Thread(
                    target=_pure_worker_expand_code,
                    args=(code_entry, include_inactive, result_queue, i, client_id, client_secret, debug_mode),
                    daemon=True
                )
                thread.start()
                threads.append(thread)
            
            # Keep track of remaining codes to process
            remaining_codes = uncached_codes[max_workers:]
            next_thread_id = max_workers
        
        # Orchestrator loop: collect results and update UI in main thread
        timeout_counter = 0
        max_timeouts = 100  # Allow 10 seconds of timeouts before giving up
        uncached_target = len(uncached_codes)  # Only need to wait for uncached results
        
        while completed_count < uncached_target:
            try:
                # Non-blocking check for results with longer timeout
                result = result_queue.get(timeout=1.0)  # Increased to 1 second
                completed_count += 1
                timeout_counter = 0  # Reset timeout counter on successful result
                # Debug output only when debug mode is enabled
                if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
                    print(f"DEBUG: Got result {completed_count}/{total_codes}, success: {result.get('success')}, error: {result.get('error', 'None')[:50] if result.get('error') else 'None'}")
                
                # Process raw result in main thread (Streamlit calls are safe here)
                if result['success'] and result['raw_result']:
                    raw_expansion = result['raw_result']
                    code_entry = result['code_entry']
                    snomed_code = result['snomed_code']
                    
                    # Process children with EMIS lookup in main thread
                    processed_children = []
                    if raw_expansion and not raw_expansion.error:
                        for child in raw_expansion.children:
                            # Look up EMIS GUID for child code
                            child_code = str(child.code).strip()
                            emis_guid = emis_lookup.get(child_code, 'Not in EMIS lookup table')
                            
                            child_data = {
                                'Parent Code': snomed_code,
                                'Parent Display': raw_expansion.source_display,
                                'Child Code': child.code,
                                'Child Display': child.display,
                                'EMIS GUID': emis_guid,
                                'Inactive': 'True' if child.inactive else 'False',
                                'Source Type': code_entry.get('Source Type', 'Unknown'),
                                'Source Name': code_entry.get('Source Name', 'Unknown'),
                                'Source Container': code_entry.get('Source Container', 'Unknown')
                            }
                            processed_children.append(child_data)
                    
                    # Store results
                    expansion_results[snomed_code] = raw_expansion
                    all_processed_children.extend(processed_children)
                    successful_expansions += 1
                    total_child_codes += len(processed_children)
                    
                    # Cache the result in session state for immediate reuse
                    st.session_state[session_cache_key][snomed_code] = raw_expansion
                    
                    # Show toast for first successful connection during expansion
                    if not first_success_toast_shown:
                        st.toast("🔗 Connected to NHS Terminology Server for expansion!", icon="✅")
                        first_success_toast_shown = True
                        
                        # Update connection status in session state
                        st.session_state[SessionStateKeys.NHS_CONNECTION_STATUS] = {
                            'tested': True,
                            'success': True,
                            'message': 'Connected to NHS England Terminology Server',
                            'timestamp': datetime.now().isoformat()
                        }
                
                # Start next thread if there are remaining codes
                if remaining_codes:
                    next_code = remaining_codes.pop(0)
                    thread = threading.Thread(
                        target=_pure_worker_expand_code,
                        args=(next_code, include_inactive, result_queue, next_thread_id, client_id, client_secret, debug_mode),
                        daemon=True
                    )
                    thread.start()
                    threads.append(thread)
                    next_thread_id += 1
                
                # Update progress (safe in main thread)
                progress = completed_count / total_codes
                progress_bar.progress(progress)
                status_text.text(f"Completed {completed_count}/{total_codes} expansions... (using {max_workers} concurrent workers)")
                
                # Periodic garbage collection to manage memory
                if completed_count % 50 == 0:
                    gc.collect()
                
            except queue.Empty:
                # No results yet, continue polling
                timeout_counter += 1
                if timeout_counter >= max_timeouts:
                    print(f"DEBUG: Timeout waiting for results after {timeout_counter} attempts, breaking")
                    break
                time.sleep(0.01)  # Small sleep to prevent busy waiting
                continue
            except Exception as e:
                completed_count += 1
                continue
        
        # Ensure all threads complete
        for thread in threads:
            thread.join(timeout=1)  # Don't wait forever
        
        # Show results summary with dynamic status indicators
        progress_bar.empty()
        status_text.empty()
        
        total_codes = len(expandable_codes)
        success_rate = successful_expansions / total_codes if total_codes > 0 else 0
        
        # Store completion status in session state for persistent display
        expansion_status = {
            'successful_expansions': successful_expansions,
            'total_codes': total_codes,
            'total_child_codes': total_child_codes,
            'success_rate': success_rate
        }
        st.session_state[SessionStateKeys.EXPANSION_STATUS] = expansion_status
        
        return {
            'expansion_results': expansion_results,
            'total_child_codes': total_child_codes,
            'successful_expansions': successful_expansions,
            'include_inactive': include_inactive,
            'original_codes': expandable_codes,  # Pass original codes for descriptions
            'processed_children': all_processed_children  # Pre-processed child codes with EMIS GUIDs
        }
        
    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.markdown(f"""
        <div style="
            background-color: #660022;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 0.5rem;
        ">
            Expansion failed: {str(e)}
        </div>
        """, unsafe_allow_html=True)
        return {}


def render_expansion_results(expansion_data: Dict):
    """
    Render the expansion results table (middle-level fragment content)
    
    Args:
        expansion_data: Dictionary containing expansion results
    """
    if not expansion_data or 'expansion_results' not in expansion_data:
        return
    
    expansion_results = expansion_data['expansion_results']
    original_codes = expansion_data.get('original_codes', [])
    service = get_expansion_service()
    
    with st.expander("📊 Expansion Results", expanded=True):
        # Create summary table with original codes for descriptions
        summary_df = service.create_expansion_summary_dataframe(expansion_results, original_codes)
        
        if not summary_df.empty:
            # Add visual indicators for SNOMED codes (matching other tabs)
            summary_df['SNOMED Code'] = '⚕️ ' + summary_df['SNOMED Code'].astype(str)
            
            # Style the summary table based on result status
            def style_status(row):
                result_status = row['Result Status']
                if result_status.startswith('Matched'):
                    return ['background-color: #1F4E3D; color: #FAFAFA'] * len(row)  # Green for matched
                elif result_status.startswith('Unmatched'):
                    return ['background-color: #7A5F0B; color: #FAFAFA'] * len(row)  # Amber for unmatched
                else:  # Error
                    return ['background-color: #660022; color: #FAFAFA'] * len(row)  # Wine red for errors
            
            styled_summary = summary_df.style.apply(style_status, axis=1)
            st.dataframe(styled_summary, width='stretch', hide_index=True)

        # Show completion status below results table
        if SessionStateKeys.EXPANSION_STATUS in st.session_state and st.session_state[SessionStateKeys.EXPANSION_STATUS]:
            status = st.session_state[SessionStateKeys.EXPANSION_STATUS]
            success_rate = status['success_rate']
            successful_expansions = status['successful_expansions']
            total_codes = status['total_codes']
            total_child_codes = status['total_child_codes']
        
            col1, col2 = st.columns(2)
        
            with col1:
                if success_rate == 1.0:
                    # Green: 100% success
                    st.markdown(f"""
                    <div style="
                        background-color: #1F4E3D;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1.0rem;
                    ">
                        ✅ Expansion complete: {successful_expansions}/{total_codes} codes expanded successfully
                    </div>
                    """, unsafe_allow_html=True)
                elif success_rate > 0:
                    # Yellow: Partial success
                    st.markdown(f"""
                    <div style="
                        background-color: #7A5F0B;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1.0rem;
                    ">
                        ⚠️ Expansion complete: {successful_expansions}/{total_codes} codes expanded successfully
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    # Red: No success
                    st.markdown(f"""
                    <div style="
                        background-color: #660022;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1.0rem;
                    ">
                        ❌ Expansion failed: {successful_expansions}/{total_codes} codes expanded successfully
                    </div>
                    """, unsafe_allow_html=True)
        
            with col2:
                st.markdown(f"""
                <div style="
                    background-color: #28546B;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1.0rem;
                ">
                    📊 Total child codes discovered: {total_child_codes}
                </div>
                """, unsafe_allow_html=True)


def render_child_codes_detail(expansion_data: Dict):
    """
    Render the child codes detail section (bottom-level fragment content)
    
    Args:
        expansion_data: Dictionary containing expansion results
    """
    if not expansion_data or 'expansion_results' not in expansion_data:
        return
    
    # EMIS GUID Coverage information
    expansion_results = expansion_data['expansion_results']
    original_codes = expansion_data.get('original_codes', [])
    service = get_expansion_service()
    
    # Use pre-processed child codes if available (much faster!)
    all_child_codes = expansion_data.get('processed_children', [])
    
    # If no pre-processed children, fall back to old method (for compatibility)
    if not all_child_codes:
        # Fallback: Create detailed child codes list with EMIS GUID lookup
        lookup_df = getattr(st.session_state, 'lookup_df', None)
        snomed_code_col = getattr(st.session_state, 'snomed_code_col', 'SNOMED Code')
        emis_guid_col = getattr(st.session_state, 'emis_guid_col', 'EMIS GUID')
        
        emis_lookup = {}
        if lookup_df is not None:
            for _, row in lookup_df.iterrows():
                snomed_code = str(row.get(snomed_code_col, '')).strip()
                emis_guid = str(row.get(emis_guid_col, '')).strip()
                if snomed_code and emis_guid:
                    emis_lookup[snomed_code] = emis_guid
        
        # Create full child codes list with EMIS GUID lookup
        all_child_codes = []
        for parent_code, result in expansion_results.items():
            if result and hasattr(result, 'child_codes') and result.child_codes:
                for child in result.child_codes:
                    child_snomed = str(child.get('code', '')).strip()
                    emis_guid = emis_lookup.get(child_snomed, 'Not in EMIS lookup table')
                    
                    # Find original code entry for source tracking
                    original_entry = next((code for code in original_codes if code.get('SNOMED Code', '').strip() == parent_code), {})
                    
                    all_child_codes.append({
                        'Parent Code': parent_code,
                        'Parent Display': result.original_display if result else 'Unknown',
                        'Child Code': child_snomed,
                        'Child Display': child.get('display', 'Unknown'),
                        'Inactive': str(child.get('inactive', False)),
                        'EMIS GUID': emis_guid,
                        # Source tracking
                        'Source Type': original_entry.get('Source Type', 'Unknown'),
                        'Source Name': original_entry.get('Source Name', 'Unknown'),
                        'Source Container': original_entry.get('Source Container', 'Unknown')
                    })
    
    # Count total and with EMIS GUIDs
    total_count = len(all_child_codes)
    emis_count = len([code for code in all_child_codes if code.get('EMIS GUID') != 'Not in EMIS lookup table'])
    coverage_pct = (emis_count / total_count * 100) if total_count > 0 else 0
    
    
    if all_child_codes:
        # Child Codes table header and view mode selector (matching clinical codes pattern)
        st.markdown("### 👪 Child Codes Detail")
        st.caption("🌳 Expanded hierarchy includes ALL descendants (children, grandchildren, etc.) from NHS Terminology Server")

        
        # Filter controls
        col1, col2, col3 = st.columns([6, 1, 1])
        
        with col1:
            search_term = st.text_input(
                "Search child codes",
                placeholder="Enter code or description to filter...",
                label_visibility="visible",
                icon= "🔍",
                key="child_codes_search"
            )

        with col2:
            st.markdown("")
            st.markdown("")
            show_inactive = st.checkbox(
                "Include inactive concepts",
                value=False,
                help="Include concepts that are inactive/deprecated in SNOMED CT",
                key="show_inactive_children"
            )    

        with col3:
            view_mode = st.selectbox(
                "Code Display Mode:",
                ["🔀 Unique Codes", "📍 Per Source"],
                index=0,  # Default to Unique Codes
                key="child_view_mode",
                help="🔀 Unique Codes: Show distinct parent-child combinations only\n📍 Per Source: Show all parent-child relationships including duplicates across sources"
            )
        
        st.markdown("")

        # Apply filters
        filtered_codes = all_child_codes.copy()
        
        # Apply search filter
        if search_term:
            filtered_codes = [
                code for code in filtered_codes
                if search_term.lower() in code['Child Code'].lower() or
                   search_term.lower() in code['Child Display'].lower() or
                   search_term.lower() in code['Parent Code'].lower() or
                   search_term.lower() in code['Parent Display'].lower() or
                   search_term.lower() in code.get('Source Name', '').lower()
            ]
        
        # Apply inactive filter
        if not show_inactive:
            filtered_codes = [code for code in filtered_codes if code['Inactive'] == 'False']
        
        # Apply view mode filter and sorting
        if view_mode == "🔀 Unique Codes":
            # Deduplicate by parent-child combination, keeping first occurrence
            seen_combinations = set()
            unique_codes = []
            for code in filtered_codes:
                combination = (code['Parent Code'], code['Child Code'])
                if combination not in seen_combinations:
                    seen_combinations.add(combination)
                    unique_codes.append(code)
            filtered_codes = unique_codes
            
            # Sort by Parent Code, then Child Code for unique mode
            filtered_codes = sorted(filtered_codes, key=lambda x: (x['Parent Code'], x['Child Code']))
        
        else:  # Per Source mode
            # Sort by Source Type, Source Name, Parent Code, then Child Code for intuitive source grouping
            filtered_codes = sorted(filtered_codes, key=lambda x: (
                x.get('Source Type', 'Unknown'),
                x.get('Source Name', 'Unknown'), 
                x['Parent Code'], 
                x['Child Code']
            ))
        
        # Display filtered results with color coding and visual indicators
        if filtered_codes:
            child_df = pd.DataFrame(filtered_codes)
            
            # Hide source columns in Unique Codes mode (consistent with other tabs)
            if view_mode == "🔀 Unique Codes":
                # Remove source-related columns that are misleading when deduplicating
                columns_to_remove = ['Source Type', 'Source Name', 'Source Container']
                for col in columns_to_remove:
                    if col in child_df.columns:
                        child_df = child_df.drop(columns=[col])
            
            # Add visual indicators for code types (matching other tabs)
            child_df['Parent Code'] = '⚕️ ' + child_df['Parent Code'].astype(str)
            child_df['Child Code'] = '⚕️ ' + child_df['Child Code'].astype(str)
            
            # Add visual indicators for EMIS GUID column
            def format_emis_guid(guid):
                guid_str = str(guid)
                if guid_str == 'Not in EMIS lookup table':
                    # Only add emoji if not already present
                    if not guid_str.startswith('❌'):
                        return f'❌ {guid_str}'
                    return guid_str
                else:
                    # Only add emoji if not already present
                    if not guid_str.startswith('🔍'):
                        return f'🔍 {guid_str}'
                    return guid_str
            
            child_df['EMIS GUID'] = child_df['EMIS GUID'].apply(format_emis_guid)
            
            # Style the child codes table based on EMIS GUID availability
            def style_emis_guid(row):
                emis_guid = row['EMIS GUID']
                if 'Not in EMIS lookup table' in str(emis_guid):
                    return ['background-color: #660022; color: #FAFAFA'] * len(row)  # Wine red for not found
                else:
                    return ['background-color: #1F4E3D; color: #FAFAFA'] * len(row)  # Green for found
            
            styled_child_df = child_df.style.apply(style_emis_guid, axis=1)
            st.dataframe(styled_child_df, width='stretch', hide_index=True)
        else:
            if search_term or not show_inactive:
                st.markdown("""
                <div style="
                    background-color: #28546B;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 0.5rem;
                ">
                    No child codes match the current filters
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="
                    background-color: #28546B;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 0.5rem;
                ">
                    This concept has no child concepts
                </div>
                """, unsafe_allow_html=True)

    # Only show EMIS coverage if we have child codes
    if all_child_codes:
        st.markdown(f"""
        <div style="
            background-color: #28546B;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 0.5rem;
        ">
            📊 EMIS GUID Coverage: {emis_count}/{total_count} child codes found in EMIS lookup table ({coverage_pct:.1f}%)
        </div>
        """, unsafe_allow_html=True)

    
    # Export section with conditional filters (matching clinical code tabs pattern)
    if all_child_codes:
        @st.fragment
        def child_codes_export_fragment():
            col1, col2 = st.columns([1, 2])
            
            with col1:
                # Analyze data to determine available filter options
                current_mode = st.session_state.get(SessionStateKeys.CHILD_VIEW_MODE, '🔀 Unique Codes')
                has_source_tracking = any('Source Type' in code for code in all_child_codes)
                
                # Count different types of data
                total_count = len(all_child_codes)
                matched_count = len([code for code in all_child_codes if code.get('EMIS GUID', 'Not in EMIS lookup table') != 'Not in EMIS lookup table'])
                unmatched_count = total_count - matched_count
                
                # Count source types
                search_count = 0
                report_count = 0
                if has_source_tracking:
                    search_count = len([code for code in all_child_codes if 'Search' in str(code.get('Source Type', ''))])
                    report_count = len([code for code in all_child_codes if 'Search' not in str(code.get('Source Type', '')) and code.get('Source Type', '') != 'Unknown'])
                
                # Build conditional filter options (smart logic like clinical codes)
                filter_options = ["All Child Codes"]
                
                # Smart logic for matched/unmatched filters
                if matched_count > 0 and unmatched_count > 0:
                    # Both matched and unmatched exist - show both filter options
                    filter_options.append("Only Matched")
                    filter_options.append("Only Unmatched")
                elif matched_count > 0 and unmatched_count == 0:
                    # All codes are matched - no need for "Only Matched" (same as "All Codes")
                    pass  # Just keep "All Codes"
                elif matched_count == 0 and unmatched_count > 0:
                    # All codes are unmatched - no need for "Only Unmatched" (same as "All Codes")
                    pass  # Just keep "All Codes"
                
                # Add source-based filters only if in per_source mode and both sources exist
                if has_source_tracking and current_mode == '📍 Per Source':
                    if search_count > 0:
                        filter_options.append("Only Child Codes from Searches")
                    if report_count > 0:
                        filter_options.append("Only Child Codes from Reports")
                
                # Show radio with conditional options
                export_filter = st.radio(
                    "Export Filter:",
                    filter_options,
                    key="child_codes_export_filter",
                    horizontal=len(filter_options) <= 3
                )
                
                # Always show counts for transparency
                st.caption(f"📊 Total: {total_count} | ✅ Matched: {matched_count} | ❌ Unmatched: {unmatched_count}")
                if has_source_tracking and current_mode == '📍 Per Source':
                    st.caption(f"🔍 Searches: {search_count} | 📊 Reports: {report_count}")
            
            with col2:
                # Filter data based on selection
                filtered_codes = []
                export_label = "📥 👪 Child Codes"
                export_suffix = ""
                
                for code in all_child_codes:
                    include_code = False
                    
                    if export_filter == "All Child Codes":
                        include_code = True
                    elif export_filter == "Only Matched":
                        emis_guid = code.get('EMIS GUID', 'Not in EMIS lookup table')
                        include_code = emis_guid != 'Not in EMIS lookup table'
                        export_label = "📥 ✅ 👪 Matched Child Codes"
                        export_suffix = "_matched"
                    elif export_filter == "Only Unmatched":
                        emis_guid = code.get('EMIS GUID', 'Not in EMIS lookup table')
                        include_code = emis_guid == 'Not in EMIS lookup table'
                        export_label = "📥 ❌ 👪 Unmatched Child Codes"
                        export_suffix = "_unmatched"
                    elif export_filter == "Only Child Codes from Searches":
                        source_type = code.get('Source Type', '')
                        include_code = 'Search' in str(source_type)
                        export_label = "📥 🔍 👪 Child Codes from Searches"
                        export_suffix = "_searches"
                    elif export_filter == "Only Child Codes from Reports":
                        source_type = code.get('Source Type', '')
                        include_code = 'Search' not in str(source_type) and source_type != 'Unknown'
                        export_label = "📥 📊 👪 Child Codes from Reports"
                        export_suffix = "_reports"
                    
                    if include_code:
                        filtered_codes.append(code)
                
                # Add view mode to labels and filename
                mode_suffix = "_unique" if current_mode == '🔀 Unique Codes' else "_per_source"
                if export_suffix:
                    export_suffix = mode_suffix + export_suffix
                else:
                    export_suffix = mode_suffix
                
                mode_label = " (Unique)" if current_mode == '🔀 Unique Codes' else " (Per Source)"
                export_label = export_label.replace("📥", f"📥{mode_label}")
                
                # Show count of filtered items
                filtered_df = pd.DataFrame(filtered_codes) if filtered_codes else pd.DataFrame()
                st.caption(f"📊 Will generate CSV with {len(filtered_df)} rows × {len(filtered_df.columns) if len(filtered_df) > 0 else 9} columns")
                
                # Render download button using UIExportManager (matching clinical code pattern)
                if filtered_codes:
                    xml_filename = st.session_state.get(SessionStateKeys.XML_FILENAME)
                    from utils.export_handlers.ui_export_manager import UIExportManager
                    export_manager = UIExportManager()
                    export_manager.render_download_button(
                        data=filtered_df,
                        label=export_label,
                        filename_prefix=f"child_codes{export_suffix}",
                        xml_filename=xml_filename,
                        key=f"download_child_codes_{export_filter.lower().replace(' ', '_')}"
                    )
                else:
                    st.markdown("""
                    <div style="
                        background-color: #28546B;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 0.5rem;
                    ">
                        No child codes match the current export filter
                    </div>
                    """, unsafe_allow_html=True)
        
        # Execute the export fragment
        child_codes_export_fragment()


def render_expansion_tab_content(clinical_data: List[Dict]):
    """
    Render complete expansion tab content with fragment hierarchy
    
    Args:
        clinical_data: Clinical codes data from the main analysis
    """
    # Clean header without connection status
    st.subheader("🏥 Terminology Server Child Code Expansion")
    st.markdown("Use the NHS Terminology Server to expand SNOMED codes with `<includeChildren>true</includeChildren>` to return a comprehensive list of all child codes")
    
    st.markdown("---")
    
    # TOP LEVEL FRAGMENT: Expansion controls 
    @st.fragment
    def expansion_controls_fragment():
        # Main expansion interface
        expansion_data = render_expansion_controls(clinical_data)
        
        # Store expansion results in session state to persist across fragments
        if expansion_data:
            st.session_state.expansion_results_data = expansion_data
            # Force rerun to trigger dependent fragments
            st.rerun()
    
    # Execute top-level fragment
    expansion_controls_fragment()

    
    # MIDDLE LEVEL FRAGMENT: Expansion results table (only if we have data)
    if hasattr(st.session_state, 'expansion_results_data') and st.session_state.expansion_results_data:
        st.markdown("")
        
        @st.fragment
        def expansion_results_fragment():
            render_expansion_results(st.session_state.expansion_results_data)
        
        # Execute middle-level fragment
        expansion_results_fragment()

        st.markdown("")
        st.markdown("")

        # BOTTOM LEVEL FRAGMENT: Child codes detail (only if we have data)
        @st.fragment 
        def child_codes_detail_fragment():
            render_child_codes_detail(st.session_state.expansion_results_data)
        
        # Execute bottom-level fragment
        child_codes_detail_fragment()


def render_individual_code_lookup():
    """
    Render individual SNOMED code lookup interface
    
    Provides a simple interface for testing single concept expansions
    without requiring XML processing or cached EMIS lookup data.
    """
    st.markdown("### 🔍 Individual Code Lookup")
    st.markdown("Test individual SNOMED concept expansion (no XML file required)")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        snomed_code = st.text_input(
            "SNOMED CT Code",
            placeholder="e.g., 73211009",
            help="Enter a SNOMED CT concept code for expansion testing"
        )
    
    with col2:
        include_inactive = st.checkbox(
            "Include inactive",
            value=False,
            help="Include inactive/deprecated concepts in results"
        )
    
    with col3:
        use_cache = st.checkbox(
            "Use cached results",
            value=True,
            help="Use previously cached results if available"
        )
    
    if st.button("🔍 Lookup Code", type="primary"):
        if snomed_code.strip():
            try:
                with st.spinner(f"Looking up {snomed_code}..."):
                    client = get_terminology_client()
                    result = client.expand_concept(snomed_code.strip(), include_inactive)
                
                if result and not result.error:
                    st.markdown(f"""
                    <div style="
                        background-color: #1F4E3D;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 0.5rem;
                    ">
                        ✅ Found concept: <strong>{result.original_display}</strong>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if result.child_codes:
                        st.info(f"📊 **{len(result.child_codes)} child concepts** discovered")
                        
                        # Create simple DataFrame for display
                        child_data = []
                        for child in result.child_codes:
                            child_data.append({
                                'Code': child['code'],
                                'Display': child['display'],
                                'Active': 'Yes' if not child.get('inactive', False) else 'No'
                            })
                        
                        df = pd.DataFrame(child_data)
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("ℹ️ This concept has no child concepts")
                
                elif result and result.error:
                    st.error(f"❌ Error: {result.error}")
                else:
                    st.error("❌ No result returned from terminology server")
            
            except Exception as e:
                st.error(f"❌ Lookup failed: {str(e)}")
        else:
            st.warning("⚠️ Please enter a SNOMED CT code")
