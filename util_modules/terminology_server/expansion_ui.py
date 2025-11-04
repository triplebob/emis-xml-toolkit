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
import threading
import queue
import time
import gc

from .expansion_service import get_expansion_service
from .nhs_terminology_client import get_terminology_client
from ..utils.caching.lookup_cache import get_cached_emis_lookup


def _pure_worker_expand_code(code_entry, include_inactive, result_queue, worker_id, client_id, client_secret):
    """Pure worker function - API calls only, no EMIS processing or caching"""
    try:
        snomed_code = code_entry.get('SNOMED Code', '').strip()
        print(f"DEBUG Worker {worker_id}: Starting with code {snomed_code}")
        
        if not snomed_code:
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
        print(f"DEBUG Worker {worker_id}: Calling API...")
        expansion_result = client._expand_concept_uncached(snomed_code, include_inactive)
        print(f"DEBUG Worker {worker_id}: API call done, result: {expansion_result is not None}")
        
        # Determine success status
        success = expansion_result is not None and not expansion_result.error
        error_msg = expansion_result.error if expansion_result else 'No expansion result returned'
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
        print(f"DEBUG Worker {worker_id}: Result queued")
        
    except Exception as e:
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


def _clean_dataframe_for_export(df: pd.DataFrame) -> pd.DataFrame:
    """Remove emojis from DataFrame columns for clean CSV export"""
    df_clean = df.copy()
    
    # Remove all emoji prefixes used in the app from string columns
    for col in df_clean.columns:
        if df_clean[col].dtype == 'object':  # String columns
            # Remove common emoji prefixes used throughout the app
            df_clean[col] = df_clean[col].astype(str).str.replace(
                r'⚕️ |🔍 |❌ |📊 |🔬 |⚕️|🔍|❌|📊|🔬', '', regex=True
            ).str.strip()
    
    return df_clean


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
    source_xml_filename = st.session_state.get('xml_filename', 'Unknown XML file')
    
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
    with st.sidebar:
        # Make NHS Terminology Server expandable like other sections
        with st.expander("🏥 NHS Term Server", expanded=False):
            # Initialize shared session state for connection status if not exists
            if 'nhs_connection_status' not in st.session_state:
                st.session_state.nhs_connection_status = None
            
            client = get_terminology_client()
            
            # Test connection button
            if st.button("🔗 Test Connection", key="test_nhs_connection"):
                with st.spinner("Testing connection..."):
                    success, message = client.test_connection()
                    # Store test result in shared session state
                    st.session_state.nhs_connection_status = {
                        'success': success,
                        'message': message,
                        'tested': True
                    }
                    # Show toast notification
                    if success:
                        st.toast("✅ Connected to NHS Terminology Server!", icon="🎉")
                    else:
                        st.toast("❌ Failed to connect to NHS Terminology Server", icon="⚠️")
                    # Status display will update automatically when session state changes
            
            # Show connection status using shared session state
            if st.session_state.nhs_connection_status and st.session_state.nhs_connection_status.get('tested'):
                # Show test result
                if st.session_state.nhs_connection_status['success']:
                    st.success("🔑 Authenticated")
                else:
                    st.error("🔑 Connection failed")
            else:
                # Show default status based on token validity
                if client._is_token_valid():
                    st.success("🔑 Authenticated")
                else:
                    st.warning("🔑 Not authenticated")


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
        st.info("ℹ️ No codes with includechildren=True found in this dataset")
        return None
    
    st.markdown("### ⚕️ SNOMED Code Expansion")
    
    # Expansion options
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        include_inactive = st.checkbox(
            "Include inactive concepts",
            value=False,
            help="Include concepts that are inactive/deprecated in SNOMED CT"
        )
    
    with col2:
        use_cache = st.checkbox(
            "Use cached results",
            value=True,
            help="Use previously cached expansion results (24h expiry)"
        )
    
    with col3:
        filter_zero_descendants = st.checkbox(
            "Skip codes with 0 descendants",
            value=True,
            help="Filter out codes already known to have no child concepts (saves API calls)"
        )
    
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
    
    # Apply filtering and show dynamic summary with deduplication info
    original_count = len(all_expandable_codes)
    unique_count = len(unique_codes)
    dedupe_savings = original_count - unique_count
    
    if filter_zero_descendants:
        # Count codes with 0 descendants before filtering
        zero_descendant_count = sum(1 for code in unique_codes.values() 
                                  if str(code.get('Descendants', '')).strip() == '0')
        
        if zero_descendant_count > 0:
            remaining_codes = unique_count - zero_descendant_count
            if dedupe_savings > 0:
                st.info(f"Found {original_count} expandable codes → {unique_count} unique codes (saved {dedupe_savings} duplicate API calls) → {remaining_codes} after filtering 0-descendant codes")
            else:
                st.info(f"Found {unique_count} codes that can be expanded - filtered out {zero_descendant_count} codes with 0 descendants (saves API calls), {remaining_codes} codes will be processed")
            # Apply the actual filtering
            expandable_codes = [code for code in unique_codes.values() 
                              if str(code.get('Descendants', '')).strip() != '0']
        else:
            if dedupe_savings > 0:
                st.info(f"Found {original_count} expandable codes → {unique_count} unique codes (saved {dedupe_savings} duplicate API calls)")
            else:
                st.info(f"Found {unique_count} codes that can be expanded to include child concepts")
            expandable_codes = list(unique_codes.values())
    else:
        if dedupe_savings > 0:
            st.info(f"Found {original_count} expandable codes → {unique_count} unique codes (saved {dedupe_savings} duplicate API calls)")
        else:
            st.info(f"Found {unique_count} codes that can be expanded to include child concepts")
        expandable_codes = list(unique_codes.values())
    
    # Expansion button with protection against double-clicks
    if 'expansion_in_progress' not in st.session_state:
        st.session_state.expansion_in_progress = False
    
    if st.button("🌳 Expand Child Codes", type="primary", disabled=st.session_state.expansion_in_progress):
        if not st.session_state.expansion_in_progress:
            st.session_state.expansion_in_progress = True
            try:
                result = perform_expansion(expandable_codes, include_inactive, use_cache, code_sources)
                return result
            finally:
                st.session_state.expansion_in_progress = False
    
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
    
    # Load pre-built EMIS lookup cache (built during XML processing)
    lookup_df = getattr(st.session_state, 'lookup_df', None)
    snomed_code_col = getattr(st.session_state, 'snomed_code_col', 'SNOMED Code')
    emis_guid_col = getattr(st.session_state, 'emis_guid_col', 'EMIS GUID')
    version_info = getattr(st.session_state, 'lookup_version_info', None)
    
    status_text.text("Loading EMIS lookup cache...")
    
    # Load from persistent cache (should already be built during XML processing)
    cached_data = get_cached_emis_lookup(lookup_df, snomed_code_col, emis_guid_col, version_info)
    
    # Debug logging
    if cached_data is None:
        from ..utils.caching.lookup_cache import _get_lookup_table_hash
        expected_hash = _get_lookup_table_hash(lookup_df, version_info)
        st.warning(f"🔍 Debug: Cache lookup failed. Expected hash: {expected_hash}, Version info available: {version_info is not None}")
    
    if cached_data is not None:
        # Found persistent cache
        emis_lookup = cached_data['lookup_mapping']
        lookup_records = cached_data['lookup_records']
        status_text.text(f"✅ Loaded EMIS lookup cache ({len(emis_lookup)} mappings)")
        lookup_count = len(emis_lookup)
    else:
        # No cache available - cannot proceed with terminology server expansion
        status_text.text("❌ EMIS lookup cache not available")
        st.error("⚠️ EMIS lookup cache not found. Please process an XML file first to build the cache, then try expanding codes again.")
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
            st.error(f"Missing NHS Terminology Server credentials: {e}")
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
                    args=(code_entry, include_inactive, result_queue, i, client_id, client_secret),
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
                        st.session_state.nhs_connection_status = {
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
                        args=(next_code, include_inactive, result_queue, next_thread_id, client_id, client_secret),
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
        
        # Dynamic status indicator and totals in two columns
        col1, col2 = st.columns(2)
        
        with col1:
            if success_rate == 1.0:
                # Green: 100% success
                st.success(f"✅ Expansion complete: {successful_expansions}/{total_codes} codes expanded successfully")
            elif success_rate > 0:
                # Yellow: Partial success
                st.warning(f"⚠️ Expansion complete: {successful_expansions}/{total_codes} codes expanded successfully")
            else:
                # Red: No success
                st.error(f"❌ Expansion failed: {successful_expansions}/{total_codes} codes expanded successfully")
        
        with col2:
            st.info(f"📊 Total child codes discovered: {total_child_codes}")
        
        
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
        st.error(f"Expansion failed: {str(e)}")
        return {}


def render_expansion_results(expansion_data: Dict):
    """
    Render the results of code expansion
    
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
                    return ['background-color: #2d5a3d; color: #e8f5e8'] * len(row)  # Dark green for matched
                elif result_status.startswith('Unmatched'):
                    return ['background-color: #5a4d2d; color: #f5f3e8'] * len(row)  # Dark yellow for unmatched
                else:  # Error
                    return ['background-color: #5a2d2d; color: #f5e8e8'] * len(row)  # Dark red for errors
            
            styled_summary = summary_df.style.apply(style_status, axis=1)
            st.dataframe(styled_summary, width='stretch', hide_index=True)
    
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
        
        for code, result in expansion_results.items():
            if not result.error and result.children:
                for child in result.children:
                    emis_guid = emis_lookup.get(child.code)
                    emis_status = emis_guid if emis_guid else 'Not in EMIS lookup table'
                    
                    all_child_codes.append({
                        'Parent Code': code,
                        'Parent Display': result.source_display,
                        'Child Code': child.code,
                        'Child Display': child.display,
                        'EMIS GUID': emis_status,
                        'Inactive': 'True' if child.inactive else 'False'
                    })
    
    # Calculate EMIS GUID coverage statistics
    if all_child_codes:
        total_child_codes = len(all_child_codes)
        missing_emis_guids = sum(1 for code in all_child_codes if code['EMIS GUID'] == 'Not in EMIS lookup table')
        
        # Show helpful info about EMIS GUID coverage
        if missing_emis_guids > 0:
            coverage_rate = ((total_child_codes - missing_emis_guids) / total_child_codes) * 100
            st.info(f"ℹ️ EMIS GUID Coverage: {total_child_codes - missing_emis_guids}/{total_child_codes} child codes found in EMIS lookup table ({coverage_rate:.1f}%). Missing codes may be newer concepts not yet available in EMIS.")
    
    if all_child_codes:
        # Child Codes table header and view mode selector (matching clinical codes pattern)
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown("### 🔍 Child Codes Detail")
            st.caption("🌳 Expanded hierarchy includes ALL descendants (children, grandchildren, etc.) from NHS Terminology Server")
        with col2:
            view_mode = st.selectbox(
                "View mode",
                ["🔀 Unique Codes", "📍 Per Source"],
                index=0,  # Default to Unique Codes
                key="child_view_mode",
                help="🔀 Unique Codes: Show distinct parent-child combinations only\n📍 Per Source: Show all parent-child relationships including duplicates across sources"
            )
        
        # Filter controls
        col1, col2 = st.columns([2, 1])
        
        with col1:
            search_term = st.text_input(
                "🔍 Search child codes",
                placeholder="Enter code or description to filter...",
                key="child_codes_search"
            )
        
        with col2:
            show_inactive = st.checkbox(
                "Show inactive",
                value=False,
                key="show_inactive_children"
            )
        
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
                if str(guid) == 'Not in EMIS lookup table':
                    return f'❌ {guid}'  # Add red X for "not found" entries
                else:
                    return f'🔍 {guid}'  # Add EMIS GUID indicator
            
            child_df['EMIS GUID'] = child_df['EMIS GUID'].apply(format_emis_guid)
            
            # Style the child codes table based on EMIS GUID availability
            def style_emis_guid(row):
                emis_guid = row['EMIS GUID']
                if 'Not in EMIS lookup table' in str(emis_guid):
                    return ['background-color: #5a2d2d; color: #f5e8e8'] * len(row)  # Dark red for not found
                else:
                    return ['background-color: #2d5a3d; color: #e8f5e8'] * len(row)  # Dark green for found
            
            styled_child_df = child_df.style.apply(style_emis_guid, axis=1)
            st.dataframe(styled_child_df, width='stretch', hide_index=True)
    
    # Export options section (moved outside expander to prevent UI resets)
    st.markdown("### 📥 Export Options")
    # Check if we have source tracking for granular filters
    has_source_tracking = all_child_codes and any(
        'Source Type' in code for code in all_child_codes
    )
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # Always show Summary download first (ignores filters)
        st.markdown("**📊 Download Summary of Matched/Unmatched Parents**")
        summary_csv = _clean_dataframe_for_export(summary_df).to_csv(index=False)
        st.download_button(
            label="📊 Expansion Summary",
            data=summary_csv,
            file_name=f"expansion_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            help="Overview of expansion success rate for searched parent codes only",
            key="summary_download"
        )
        
        # Clear memory after export
        del summary_csv
        
        # Export filter options (for child codes)
        st.markdown("**🔍 Child Codes Filter**")
        if has_source_tracking:
            export_filter = st.radio(
                "Export Filter:",
                ["All Child Codes", "Only Matched", "Only Unmatched", "Only Child Codes from Searches", "Only Child Codes from Reports"],
                key="child_codes_export_filter"
            )
        else:
            export_filter = st.radio(
                "Export Filter:",
                ["All Child Codes", "Only Matched", "Only Unmatched"],
                key="child_codes_export_filter_simple"
            )
    
    with col2:
        if all_child_codes:
            # Apply export filter to child codes data
            export_filtered_codes = []
            
            for code in all_child_codes:
                include_code = False
                
                if export_filter == "All Child Codes":
                    include_code = True
                elif export_filter == "Only Matched":
                    # Code is matched if it has an EMIS GUID
                    emis_guid = code.get('EMIS GUID', 'Not in EMIS lookup table')
                    include_code = emis_guid != 'Not in EMIS lookup table'
                elif export_filter == "Only Unmatched":
                    # Code is unmatched if it doesn't have an EMIS GUID
                    emis_guid = code.get('EMIS GUID', 'Not in EMIS lookup table')
                    include_code = emis_guid == 'Not in EMIS lookup table'
                elif export_filter == "Only Child Codes from Searches" and has_source_tracking:
                    # Filter for search sources
                    source_type = code.get('Source Type', '')
                    include_code = 'Search' in str(source_type)
                elif export_filter == "Only Child Codes from Reports" and has_source_tracking:
                    # Filter for report sources
                    source_type = code.get('Source Type', '')
                    include_code = 'Search' not in str(source_type) and source_type != 'Unknown'
                
                if include_code:
                    export_filtered_codes.append(code)
            
            # Apply view mode filtering to export data (hide source columns if in Unique Codes mode)
            if export_filtered_codes:
                export_df = pd.DataFrame(export_filtered_codes)
                
                # Hide source columns in Unique Codes mode (consistent with display)
                if view_mode == "🔀 Unique Codes":
                    columns_to_remove = ['Source Type', 'Source Name', 'Source Container']
                    for col in columns_to_remove:
                        if col in export_df.columns:
                            export_df = export_df.drop(columns=[col])
            
            # Generate timestamps and filename components
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Create SNOMED-only download
            st.markdown("**⚕️ Download Child Codes (SNOMED Only)**")
            if export_filtered_codes:
                # Create SNOMED-only export (remove EMIS GUID column)
                snomed_export_df = export_df.copy()
                if 'EMIS GUID' in snomed_export_df.columns:
                    snomed_export_df = snomed_export_df.drop(columns=['EMIS GUID'])
                
                # Generate filename for SNOMED export with view mode
                view_suffix = "unique" if view_mode == "🔀 Unique Codes" else "per_source"
                
                if export_filter == "Only Matched":
                    snomed_filename = f"child_snomed_matched_{view_suffix}_{timestamp}.csv"
                elif export_filter == "Only Unmatched":
                    snomed_filename = f"child_snomed_unmatched_{view_suffix}_{timestamp}.csv"
                elif export_filter == "Only Child Codes from Searches":
                    snomed_filename = f"child_snomed_searches_{view_suffix}_{timestamp}.csv"
                elif export_filter == "Only Child Codes from Reports":
                    snomed_filename = f"child_snomed_reports_{view_suffix}_{timestamp}.csv"
                else:
                    snomed_filename = f"child_snomed_all_{view_suffix}_{timestamp}.csv"
                
                snomed_csv = _clean_dataframe_for_export(snomed_export_df).to_csv(index=False)
                st.download_button(
                    label=f"⚕️ {export_filter}",
                    data=snomed_csv,
                    file_name=snomed_filename,
                    mime="text/csv",
                    help="Child codes with SNOMED details only",
                    key="snomed_download"
                )
                
                # Clear memory after large export
                is_large_export = len(snomed_export_df) > 10000
                del snomed_csv, snomed_export_df
                if is_large_export:
                    st.cache_data.clear()
                    gc.collect()
            else:
                st.info(f"No SNOMED data available for {export_filter}")
            
            # Create EMIS import download (only active codes)
            # First calculate match statistics for all export filtered codes
            all_emis_export_codes = [code for code in export_filtered_codes if code.get('Inactive') == 'False']
            all_emis_available = sum(1 for code in all_emis_export_codes 
                                   if code.get('EMIS GUID') != 'Not in EMIS lookup table')
            all_total_codes = len(all_emis_export_codes)
            
            st.markdown(f"**🔍 Download Child Codes (inc EMIS GUID) - {all_emis_available}/{all_total_codes} matched**")
            
            if all_emis_export_codes:
                # Prepare EMIS import data
                emis_import_data = []
                for code in all_emis_export_codes:
                    emis_guid = code.get('EMIS GUID', 'Not in EMIS lookup table')
                    description = code['Child Display']
                    
                    emis_data = {
                        'SNOMED Code': code['Child Code'],
                        'EMIS GUID': emis_guid,
                        'Description': description,
                        'Parent Code': code['Parent Code'],
                        'Parent Description': code['Parent Display'],
                        'XML Output': _create_xml_output(emis_guid, description)
                    }
                    
                    # Add source columns if in Per Source mode
                    if view_mode == "📍 Per Source":
                        emis_data.update({
                            'Source Type': code.get('Source Type', 'Unknown'),
                            'Source Name': code.get('Source Name', 'Unknown'),
                            'Source Container': code.get('Source Container', 'Unknown')
                        })
                    
                    emis_import_data.append(emis_data)
                
                # Generate filename for EMIS export with view mode
                view_suffix = "unique" if view_mode == "🔀 Unique Codes" else "per_source"
                
                if export_filter == "Only Matched":
                    emis_filename = f"emis_import_matched_{view_suffix}_{timestamp}.csv"
                elif export_filter == "Only Unmatched":
                    emis_filename = f"emis_import_unmatched_{view_suffix}_{timestamp}.csv"
                elif export_filter == "Only Child Codes from Searches":
                    emis_filename = f"emis_import_searches_{view_suffix}_{timestamp}.csv"
                elif export_filter == "Only Child Codes from Reports":
                    emis_filename = f"emis_import_reports_{view_suffix}_{timestamp}.csv"
                else:
                    emis_filename = f"emis_import_all_{view_suffix}_{timestamp}.csv"
                
                emis_df = pd.DataFrame(emis_import_data)
                emis_csv = _clean_dataframe_for_export(emis_df).to_csv(index=False)
                
                st.download_button(
                    label=f"🔍 {export_filter}",
                    data=emis_csv,
                    file_name=emis_filename,
                    mime="text/csv",
                    help="Child codes with both SNOMED details and EMIS GUIDs for import",
                    key="emis_download"
                )
            else:
                st.info(f"No active EMIS import data available for {export_filter}")
            
            # JSON hierarchical export section
            st.markdown("**🌳 Download Hierarchical JSON (Parent-Child Structure)**")
            if all_child_codes:
                # Create hierarchical JSON structure for unique parents only
                json_data = _create_hierarchical_json(all_child_codes, view_mode)
                
                # Generate filename for JSON export
                view_suffix = "unique" if view_mode == "🔀 Unique Codes" else "per_source"
                json_filename = f"child_hierarchy_{view_suffix}_{timestamp}.json"
                
                # Format JSON with proper indentation
                json_string = json.dumps(json_data, indent=2, ensure_ascii=False)
                
                st.download_button(
                    label="🌳 Hierarchical JSON",
                    data=json_string,
                    file_name=json_filename,
                    mime="application/json",
                    help="Parent-child code hierarchy in JSON format - ignores filters, shows unique parents only",
                    key="json_download"
                )
            else:
                st.info("No child codes available for JSON export")
        else:
            st.info("No child codes available for export")
    
    if not all_child_codes:
        st.warning("No child codes were found in the expansion results")


def render_individual_code_lookup():
    """Render UI for looking up individual SNOMED codes"""
    with st.expander("🔍 Individual Code Lookup", expanded=False):
        st.markdown("Look up a specific SNOMED code to see its child concepts")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            lookup_code = st.text_input(
                "SNOMED Code",
                placeholder="e.g., 73211009",
                key="individual_lookup_code"
            )
        
        with col2:
            include_inactive = st.checkbox(
                "Include inactive",
                value=False,
                key="individual_lookup_inactive"
            )
        
        if st.button("🔍 Lookup Code", key="perform_individual_lookup") and lookup_code:
            service = get_expansion_service()
            
            with st.spinner(f"Looking up {lookup_code}... (may fetch multiple pages if >1000 results)"):
                result = service.expand_snomed_code(lookup_code.strip(), include_inactive, use_cache=True)
            
            if result.error:
                st.error(f"Lookup failed: {result.error}")
            else:
                # Display parent information prominently
                st.info(f"**Parent Code:** {lookup_code.strip()} | **Parent Term:** {result.source_display}")
                
                # Show result count with pagination indicator
                if len(result.children) >= 1000:
                    st.success(f"Found {len(result.children)} child concepts (fetched via automatic pagination)")
                else:
                    st.success(f"Found {len(result.children)} child concepts")
                
                if result.children:
                    child_data = []
                    for child in result.children:
                        child_data.append({
                            'Parent Code': lookup_code.strip(),
                            'Parent Term': result.source_display,
                            'Child Code': child.code,
                            'Child Display': child.display,
                            'Inactive': 'True' if child.inactive else 'False'
                        })
                    
                    df = pd.DataFrame(child_data)
                    # Add visual indicator for SNOMED codes
                    df['Child Code'] = '⚕️ ' + df['Child Code'].astype(str)
                    st.dataframe(df, width='stretch', hide_index=True)
                    
                    # Quick export with enhanced filename
                    csv_data = _clean_dataframe_for_export(df).to_csv(index=False)
                    # Create descriptive filename with parent term
                    safe_term = "".join(c for c in result.source_display if c.isalnum() or c in (' ', '-', '_')).rstrip()[:30]
                    filename = f"lookup_{lookup_code.strip()}_{safe_term}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    
                    st.download_button(
                        label="📥 Download Results",
                        data=csv_data,
                        file_name=filename,
                        mime="text/csv"
                    )
                else:
                    st.info("This concept has no child concepts")


def render_expansion_tab_content(clinical_data: List[Dict]):
    """
    Render complete expansion tab content
    
    Args:
        clinical_data: Clinical codes data from the main analysis
    """
    # Clean header without connection status
    st.markdown("# 🏥 NHS Terminology Server Integration")
    st.markdown("Use the NHS Terminology Server to expand SNOMED codes with `<includeChildren>true</includeChildren>` to return a comprehensive list of all child codes")
    
    st.markdown("---")
    
    # Main expansion interface
    expansion_data = render_expansion_controls(clinical_data)
    
    # Store expansion results in session state to persist across page reruns (e.g., when downloading)
    if expansion_data:
        st.session_state.expansion_results_data = expansion_data
        st.markdown("---")
        render_expansion_results(expansion_data)
    elif 'expansion_results_data' in st.session_state:
        # Show previous results if available (e.g., after download button rerun)
        st.markdown("---")
        render_expansion_results(st.session_state.expansion_results_data)
    
    st.markdown("---")
    
    # Individual lookup section
    render_individual_code_lookup()
    
    st.markdown("---")
    
    # Usage information
    with st.expander("ℹ️ About NHS Terminology Server Integration", expanded=False):
        st.markdown("""
        ### How it works
        
        1. **Detection**: The system automatically detects SNOMED codes with `includechildren=True` in your XML
        2. **Expansion**: Connects to NHS England Terminology Server to find all child concepts
        3. **Enhancement**: Adds discovered child codes to your clinical data for complete coverage
        
        ### Use Cases
        
        - **Complete Code Lists**: Get all specific codes under a general concept
        - **EMIS Implementation**: Know exactly which codes to add manually in EMIS
        - **Clinical Accuracy**: Ensure no relevant codes are missed in searches
        
        ### Data Source
        
        - **NHS England Terminology Server**: Official FHIR R4 compliant server
        - **SNOMED CT UK Edition**: Most current UK clinical terminology
        - **System-to-System Authentication**: Secure automated access
        
        ### Limitations
        
        - Requires active internet connection
        - Subject to NHS terminology server availability
        - Large hierarchies may take time to expand
        - Results cached for 24 hours to improve performance
        """)