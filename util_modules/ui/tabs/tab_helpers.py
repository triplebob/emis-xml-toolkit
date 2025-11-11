"""
Shared utility functions for tab rendering.

This module contains helper functions that are used across multiple
tab rendering modules but are specific to tab functionality.
"""

from .common_imports import *
import hashlib
import os
import gc
import psutil

# Caching functions moved to cache_manager.py
# Import cache functions from centralized cache manager
from ...utils.caching.cache_manager import cache_manager


def _get_report_size_category(report) -> str:
    """Determine if report is small, medium, or large for performance optimization"""
    try:
        # Count total complexity indicators
        column_groups_count = 0
        criteria_count = 0
        codes_count = 0
        
        # Count column groups
        if hasattr(report, 'column_groups') and report.column_groups:
            column_groups_count = len(report.column_groups)
            
            # Count criteria in column groups
            for group in report.column_groups:
                if group.get('criteria_details'):
                    criteria_list = group['criteria_details'].get('criteria', [])
                    criteria_count += len(criteria_list)
                    
                    # Count codes in criteria
                    for criterion in criteria_list:
                        value_sets = criterion.get('value_sets', [])
                        for vs in value_sets:
                            codes_count += len(vs.get('values', []))
        
        # Count main criteria groups
        if hasattr(report, 'criteria_groups') and report.criteria_groups:
            criteria_count += len(report.criteria_groups)
            for group in report.criteria_groups:
                for criterion in group.criteria:
                    value_sets = criterion.value_sets or []
                    for vs in value_sets:
                        codes_count += len(vs.get('values', []))
        
        # Classify based on complexity
        if column_groups_count <= 3 and criteria_count <= 5 and codes_count <= 50:
            return "small"
        elif column_groups_count <= 10 and criteria_count <= 20 and codes_count <= 200:
            return "medium" 
        else:
            return "large"
            
    except Exception:
        return "medium"  # Safe default

def _monitor_memory_usage(location: str, report_size: str = "medium"):
    """Monitor memory usage at key points during report rendering - optimized for report size"""
    try:
        # Skip memory monitoring for small reports entirely
        if report_size == "small":
            return 0
            
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        
        # Higher thresholds for medium reports, aggressive for large reports
        threshold = 1500 if report_size == "large" else 2000
        
        if memory_mb > threshold:
            st.warning(f"High memory usage detected at {location}: {memory_mb:.1f} MB")
            
            # Trigger cleanup based on report size
            from ...utils.caching.cache_manager import cache_manager
            if report_size == "large":
                cache_manager.manage_session_state_memory(max_cache_items=10)
            else:
                cache_manager.manage_session_state_memory(max_cache_items=30)
            gc.collect()
            
            # Check memory again
            memory_info_after = process.memory_info()
            memory_mb_after = memory_info_after.rss / 1024 / 1024
            reduction = memory_mb - memory_mb_after
            
            if reduction > 50:  # Significant reduction
                st.success(f"Memory cleanup successful: freed {reduction:.1f} MB, now at {memory_mb_after:.1f} MB")
        
        return memory_mb
    except Exception:
        # If memory monitoring fails, just continue
        return 0

def _batch_lookup_snomed_for_ui(emis_guids: List[str]) -> Dict[str, str]:
    """Batch lookup SNOMED codes for multiple EMIS GUIDs - much faster than individual lookups"""
    if not emis_guids:
        return {}
        
    try:
        # Get cached unified data from session state to avoid expensive recomputation
        cached_unified_data = st.session_state.get('unified_clinical_data_cache')
        if cached_unified_data is None:
            # Only call expensive function if no cache exists
            from ..ui_helpers import get_unified_clinical_data
            unified_results = get_unified_clinical_data()
        else:
            unified_results = cached_unified_data
            
        data_hash = cache_manager.generate_data_hash(unified_results)
        
        # Get cached SNOMED lookup dictionary
        lookup_dict = cache_manager.cache_snomed_lookup_dictionary(data_hash, unified_results)
        
        # Batch O(1) lookups from cached dictionary
        result = {}
        for guid in emis_guids:
            if guid and guid != 'N/A':
                result[guid] = lookup_dict.get(str(guid).strip(), 'Not found')
            else:
                result[guid] = 'N/A'
        return result
        
    except Exception as e:
        # Return error dict for all GUIDs
        return {guid: f'Error: {str(e)[:20]}...' for guid in emis_guids}



@st.cache_data(show_spinner="Loading report metadata...", ttl=1800, max_entries=100)
def _load_report_metadata(report_id: str, report_hash: str, report_name: str, report_type: str, description: str, parent_info: str, search_date: str):
    """
    Load and cache basic report metadata with spinner.
    
    This cached function shows a spinner only on cache misses.
    Cache hits return instantly without spinner display.
    """
    return {
        'report_id': report_id,
        'report_name': report_name,
        'report_type': report_type,
        'description': description,
        'parent_info': parent_info,
        'search_date': search_date,
        'metadata_loaded': True
    }

@st.cache_data(show_spinner="Extracting clinical codes...", ttl=1800, max_entries=100)
def _extract_clinical_codes(report_id: str, report_hash: str, criteria_data: list):
    """
    Extract and count clinical codes with progress tracking and spinner.
    
    Shows spinner with progress updates only on cache misses.
    Cache hits return instantly.
    """
    if not criteria_data:
        return {'clinical_codes_extracted': 0, 'extraction_complete': True}
    
    # Count total codes efficiently
    total_codes = 0
    for criterion in criteria_data:
        # Handle both SearchCriterion objects and dict objects
        if hasattr(criterion, 'value_sets'):
            # SearchCriterion object
            value_sets = criterion.value_sets or []
        else:
            # Dictionary object
            value_sets = criterion.get('value_sets', [])
        
        for vs in value_sets:
            if hasattr(vs, 'get'):
                total_codes += len(vs.get('values', []))
            else:
                total_codes += len(getattr(vs, 'values', []))
    
    # Only show progress for large code sets
    if total_codes > 50:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        processed_codes = 0
        for criterion_idx, criterion in enumerate(criteria_data):
            # Handle both SearchCriterion objects and dict objects
            if hasattr(criterion, 'value_sets'):
                # SearchCriterion object
                value_sets = criterion.value_sets or []
            else:
                # Dictionary object
                value_sets = criterion.get('value_sets', [])
            
            for vs in value_sets:
                if hasattr(vs, 'get'):
                    codes = vs.get('values', [])
                else:
                    codes = getattr(vs, 'values', [])
                processed_codes += len(codes)  # Process all codes in this value set at once
                
                # Update progress every 25 codes or at significant milestones
                if processed_codes % 25 == 0 or processed_codes == total_codes:
                    progress = processed_codes / max(total_codes, 1)
                    progress_bar.progress(progress)
                    status_text.text(f"Extracting Clinical Codes: {processed_codes}/{total_codes} processed")
        
        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()
    
    return {
        'clinical_codes_extracted': total_codes,
        'codes_processed': total_codes,
        'extraction_complete': True
    }


@st.cache_data(show_spinner="Processing column groups...", ttl=1800, max_entries=100)
def _process_column_groups(report_id: str, report_hash: str, column_groups_data: list):
    """
    Process column groups with progress tracking and spinner.
    
    Shows spinner with progress updates only on cache misses.
    Cache hits return instantly.
    """
    if not column_groups_data:
        return {'column_groups_processed': 0, 'processing_complete': True}
    
    total_groups = len(column_groups_data)
    processed_groups = []
    
    # Only show progress for larger datasets
    if total_groups > 5:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, group in enumerate(column_groups_data):
            # Process group data efficiently
            processed_group = {
                'group_id': group.get('id', f'group_{i}'),
                'display_name': group.get('display_name', f'Group {i+1}'),
                'logical_table': group.get('logical_table', 'N/A'),
                'has_criteria': group.get('has_criteria', False),
                'columns_count': len(group.get('columns', [])),
                'criteria_count': len(group.get('criteria_details', {}).get('criteria', [])) if group.get('criteria_details') else 0
            }
            processed_groups.append(processed_group)
            
            # Update progress every few groups or at the end
            if (i + 1) % 3 == 0 or i == total_groups - 1:
                progress = (i + 1) / total_groups
                progress_bar.progress(progress)
                status_text.text(f"Processing Column Groups: {i + 1}/{total_groups} rendered")
        
        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()
    else:
        # Process small datasets without progress tracking
        for i, group in enumerate(column_groups_data):
            processed_group = {
                'group_id': group.get('id', f'group_{i}'),
                'display_name': group.get('display_name', f'Group {i+1}'),
                'logical_table': group.get('logical_table', 'N/A'),
                'has_criteria': group.get('has_criteria', False),
                'columns_count': len(group.get('columns', [])),
                'criteria_count': len(group.get('criteria_details', {}).get('criteria', [])) if group.get('criteria_details') else 0
            }
            processed_groups.append(processed_group)
    
    return {
        'column_groups_processed': len(processed_groups),
        'groups_data': processed_groups,
        'processing_complete': True
    }


def is_data_processing_needed(cache_key: str) -> bool:
    """
    Check if data processing is needed by examining cache state
    
    Args:
        cache_key: Cache key to check
        
    Returns:
        True if processing is needed, False if cached data is still valid
    """
    return cache_key not in st.session_state

def cache_processed_data(cache_key: str, data: Any) -> None:
    """
    Cache processed data in session state
    
    Args:
        cache_key: Key to store data under
        data: Data to cache
    """
    st.session_state[cache_key] = data

@st.cache_data(ttl=1800, max_entries=1000)  # 30-minute TTL for report classification
def paginate_reports(reports: List, page_size: int = 20, page_key: str = "page") -> tuple:
    """
    Implement pagination for large report lists to improve performance
    
    Args:
        reports: List of reports to paginate
        page_size: Number of reports per page (default 20)
        page_key: Session state key for page tracking
        
    Returns:
        Tuple of (current_page_reports, total_pages, current_page)
    """
    if not reports:
        return [], 0, 1
        
    total_reports = len(reports)
    total_pages = (total_reports + page_size - 1) // page_size  # Ceiling division
    
    # Get current page from session state
    current_page = st.session_state.get(page_key, 1)
    current_page = max(1, min(current_page, total_pages))  # Clamp to valid range
    
    # Calculate slice indices
    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_reports)
    
    current_page_reports = reports[start_idx:end_idx]
    
    return current_page_reports, total_pages, current_page

def render_pagination_controls(total_pages: int, current_page: int, page_key: str = "page"):
    """
    Render pagination controls for navigating between pages
    
    Args:
        total_pages: Total number of pages
        current_page: Current page number
        page_key: Session state key for page tracking
    """
    if total_pages <= 1:
        return
        
    col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
    
    with col1:
        if st.button("⏮️ First", disabled=current_page == 1, key=f"{page_key}_first"):
            st.session_state[page_key] = 1
            st.rerun()
    
    with col2:
        if st.button("⏪ Prev", disabled=current_page == 1, key=f"{page_key}_prev"):
            st.session_state[page_key] = current_page - 1
            st.rerun()
    
    with col3:
        st.markdown(f"<div style='text-align: center; margin-top: 8px;'>Page {current_page} of {total_pages}</div>", 
                   unsafe_allow_html=True)
    
    with col4:
        if st.button("Next ⏩", disabled=current_page == total_pages, key=f"{page_key}_next"):
            st.session_state[page_key] = current_page + 1
            st.rerun()
    
    with col5:
        if st.button("Last ⏭️", disabled=current_page == total_pages, key=f"{page_key}_last"):
            st.session_state[page_key] = total_pages
            st.rerun()

@st.cache_data(ttl=1800, max_entries=1000, show_spinner="Loading report sections...")
def load_report_sections(report_id: str, report_data_hash: str):
    """
    Load and process report sections with proper Streamlit caching
    
    Args:
        report_id: Unique report identifier
        report_data_hash: Hash of report structure for cache invalidation
        
    Returns:
        Processed report sections data
        
    This function uses Streamlit's native caching with spinner.
    - On cache miss: Shows "Loading report sections..." spinner
    - On cache hit: Returns instantly without spinner
    """
    # Fast processing for report sections - no artificial delays
    return {
        'report_id': report_id,
        'sections_loaded': True,
        'load_time': datetime.now().isoformat()
    }

@st.cache_data(show_spinner="Preparing export data...")
def prepare_export_data(report_id: str, export_type: str, report_hash: str):
    """
    Prepare export data with proper Streamlit caching
    
    Args:
        report_id: Report identifier
        export_type: Type of export (excel, json)
        report_hash: Report data hash for cache invalidation
        
    Returns:
        Export preparation status
        
    This function uses Streamlit's native caching with spinner.
    - On cache miss: Shows "Preparing export data..." spinner
    - On cache hit: Returns instantly
    """
    return {
        'report_id': report_id,
        'export_type': export_type,
        'prepared': True,
        'preparation_time': datetime.now().isoformat()
    }

def filter_reports_with_search(reports: List, search_term: str = "") -> List:
    """
    Filter reports based on search term for better performance with large lists
    
    Args:
        reports: List of reports to filter
        search_term: Search term to filter by (searches name and type)
        
    Returns:
        Filtered list of reports
    """
    if not search_term:
        return reports
        
    search_lower = search_term.lower()
    filtered = []
    
    for report in reports:
        # Search in report name
        if search_lower in report.name.lower():
            filtered.append(report)
            continue
            
        # Search in report type if available
        if hasattr(report, 'report_type') and report.report_type:
            if search_lower in report.report_type.lower():
                filtered.append(report)
                continue
                
        # Search in description if available
        if hasattr(report, 'description') and report.description:
            if search_lower in report.description.lower():
                filtered.append(report)
                continue
    
    return filtered

def classify_report_type_cached(report_id: str, report_structure_hash: str) -> str:
    """Memoized report type classification to avoid expensive recalculation"""
    from ...core.report_classifier import ReportClassifier
    
    # We can't cache the actual report object, so we'll use a simple detection
    # This is much faster than the full ReportClassifier.classify_report_type()
    # The report_structure_hash ensures cache invalidation when report changes
    
    # Get the report from session state if available
    analysis = st.session_state.get('xml_structure_analysis') or st.session_state.get('search_analysis')
    if analysis and analysis.reports:
        report = next((r for r in analysis.reports if r.id == report_id), None)
        if report:
            return ReportClassifier.classify_report_type(report)
    
    # Fallback to basic classification if report not found
    return "[Unknown]"


def _is_medication_from_context(code_system, table_context, column_context):
    """
    Determine if a code is a medication based on code system and table/column context.
    Uses the same logic as xml_utils.is_medication_code_system but as a helper function.
    """
    from ...xml_parsers.xml_utils import is_medication_code_system
    return is_medication_code_system(code_system, table_context, column_context)


def _is_pseudorefset_from_context(emis_guid, valueset_description):
    """
    Determine if a code is a pseudo-refset container based on GUID and description.
    Uses the same logic as xml_utils.is_pseudo_refset.
    """
    from ...xml_parsers.xml_utils import is_pseudo_refset
    return is_pseudo_refset(emis_guid, valueset_description)


def _is_pseudomember_from_context(valueset_guid, valueset_description):
    """
    Determine if a code is a member of a pseudo-refset based on its valueSet information.
    A code is a pseudo-refset member if its valueSet is a pseudo-refset.
    """
    from ...xml_parsers.xml_utils import is_pseudo_refset
    return is_pseudo_refset(valueset_guid, valueset_description)


def _reprocess_with_new_mode(deduplication_mode):
    """Handle deduplication mode change - no reprocessing needed, deduplication handled at display level"""
    # No-op function - deduplication is now handled by render_section_with_data()
    # Session state is already updated by the calling tab
    # Streamlit automatically reruns when session state changes
    pass


# SNOMED lookup now uses batch function for consistency and efficiency
def _lookup_snomed_for_ui(emis_guid: str) -> str:
    """Single SNOMED lookup - uses batch function for consistency"""
    if not emis_guid or emis_guid == 'N/A':
        return 'N/A'
    
    batch_result = _batch_lookup_snomed_for_ui([emis_guid])
    return batch_result.get(emis_guid, 'Not found')


def _deduplicate_clinical_data_by_emis_guid(clinical_data):
    """
    Remove duplicate clinical codes by EMIS GUID, keeping the best entry for each code.
    
    Args:
        clinical_data: List of clinical code dictionaries
        
    Returns:
        List of deduplicated clinical code dictionaries
    """
    # Group by EMIS GUID
    guid_groups = {}
    for code in clinical_data:
        emis_guid = code.get('EMIS GUID', '')
        if emis_guid not in guid_groups:
            guid_groups[emis_guid] = []
        guid_groups[emis_guid].append(code)
    
    # Select best entry from each group
    deduplicated_codes = []
    for emis_guid, codes_group in guid_groups.items():
        best_code = _select_best_clinical_code_entry(codes_group)
        deduplicated_codes.append(best_code)
    
    return deduplicated_codes


def _select_best_clinical_code_entry(codes_group):
    """
    Select the best clinical code entry from a group of duplicates.
    
    Note: All entries should have the same mapping status since they share the same EMIS GUID.
    This function only selects based on data completeness for better UI display.
    
    Prioritizes:
    1. Entries with complete descriptions
    2. Most complete entry (most non-empty fields)
    
    Args:
        codes_group: List of clinical code dictionaries with same EMIS GUID
        
    Returns:
        Best clinical code dictionary from the group
    """
    if len(codes_group) == 1:
        return codes_group[0]
    
    # Priority 1: Complete descriptions
    complete_codes = [c for c in codes_group if c.get('Description', '').strip()]
    if complete_codes:
        codes_group = complete_codes
    
    # Priority 2: Most complete entry (most non-empty fields)
    def completeness_score(code):
        return sum(1 for v in code.values() if v and str(v).strip())
    
    return max(codes_group, key=completeness_score)


def _filter_report_codes_from_analysis(analysis):
    """Filter out report codes from analysis when configurable integration is disabled"""
    # Create a copy of the analysis with report criteria removed from searches
    filtered_reports = []
    for report in analysis.reports:
        if hasattr(report, 'search_criteria') and report.search_criteria:
            # Create new criteria list without report criteria
            filtered_criteria = []
            for criterion in report.search_criteria:
                if not (hasattr(criterion, 'criterion_type') and 
                       criterion.criterion_type in ['report_codes', 'list_report_codes']):
                    filtered_criteria.append(criterion)
            
            # Only include reports that still have criteria after filtering
            if filtered_criteria:
                # Create a copy of the report with filtered criteria
                import copy
                filtered_report = copy.deepcopy(report)
                filtered_report.search_criteria = filtered_criteria
                filtered_reports.append(filtered_report)
        else:
            # No criteria to filter, include as-is
            filtered_reports.append(report)
    
    # Update the analysis with filtered reports
    analysis.reports = filtered_reports
    return analysis


def _convert_analysis_codes_to_translation_format(analysis_codes):
    """Convert analysis clinical codes to translation format for display with progress tracking"""
    
    # CRITICAL PERFORMANCE FIX: Cache translation results to avoid expensive recomputation
    translation_cache_key = f'translated_codes_cache_{len(analysis_codes)}'
    if translation_cache_key in st.session_state:
        cached_translation = st.session_state.get(translation_cache_key)
        if cached_translation is not None:
            return cached_translation
    
    translated_codes = []
    
    # CRITICAL FIX: Check if this is the first time processing (avoid progress bar on cache hits)
    processing_cache_key = f'codes_translation_processed_{len(analysis_codes)}'
    show_progress = processing_cache_key not in st.session_state
    
    # Add progress indicator for large code lists ONLY on first processing
    if show_progress and len(analysis_codes) > 100:
        progress_bar = st.progress(0)
        status_text = st.empty()
        status_text.text(f"Processing {len(analysis_codes)} clinical codes...")
    else:
        progress_bar = None
        status_text = None
    
    # Get the lookup table from session state for SNOMED translation
    lookup_df = st.session_state.get('lookup_df')
    emis_guid_col = st.session_state.get('emis_guid_col')
    snomed_code_col = st.session_state.get('snomed_code_col')
    snomed_desc_col = st.session_state.get('snomed_desc_col')
    
    
    # Quick validation
    if lookup_df is None or emis_guid_col is None:
        
        # If no lookup table, just return basic format without SNOMED lookup
        for code in analysis_codes:
            translated_codes.append({
                'ValueSet GUID': 'N/A',
                'ValueSet Description': 'N/A', 
                'Code System': code.get('code_system', 'SNOMED_CONCEPT'),
                'EMIS GUID': code.get('code_value', code.get('emis_guid', '')),
                'SNOMED Code': 'Lookup unavailable',
                'SNOMED Description': 'Lookup unavailable',
                'Mapping Found': 'Lookup unavailable',
                'Table Context': 'N/A',
                'Column Context': 'N/A', 
                'Include Children': 'Yes' if code.get('include_children', False) else 'No',
                'Has Qualifier': '0',
                'Is Parent': '0',
                'Descendants': '0',
                'Code Type': 'Finding',
                'source_type': code.get('source_type', 'report'),
                'report_type': code.get('report_type', code.get('source_report_type', 'unknown')),
                'source_name': code.get('source_report_name', code.get('source_name', 'Unknown Report'))
            })
        return translated_codes
    
    # Create a lookup dictionary for faster access (one-time setup)
    try:
        # Convert lookup table to dictionary with string keys for consistent lookup
        # Convert all EMIS GUIDs to strings for consistent comparison
        lookup_df_copy = lookup_df.copy()
        lookup_df_copy[emis_guid_col] = lookup_df_copy[emis_guid_col].astype(str).str.strip()
        
        # Create dictionaries for all available fields
        lookup_dict = lookup_df_copy.set_index(emis_guid_col)[snomed_code_col].to_dict()
        desc_dict = lookup_df_copy.set_index(emis_guid_col)[snomed_desc_col].to_dict() if snomed_desc_col and snomed_desc_col in lookup_df_copy.columns else {}
        
        # Additional enrichment dictionaries
        code_type_dict = lookup_df_copy.set_index(emis_guid_col)['CodeType'].to_dict() if 'CodeType' in lookup_df_copy.columns else {}
        has_qualifier_dict = lookup_df_copy.set_index(emis_guid_col)['HasQualifier'].to_dict() if 'HasQualifier' in lookup_df_copy.columns else {}
        is_parent_dict = lookup_df_copy.set_index(emis_guid_col)['IsParent'].to_dict() if 'IsParent' in lookup_df_copy.columns else {}
        descendants_dict = lookup_df_copy.set_index(emis_guid_col)['Descendants'].to_dict() if 'Descendants' in lookup_df_copy.columns else {}
        
        
    except Exception:
        # Fallback to basic format if lookup fails
        lookup_dict = {}
        desc_dict = {}
        code_type_dict = {}
        has_qualifier_dict = {}
        is_parent_dict = {}
        descendants_dict = {}
    
    for i, code in enumerate(analysis_codes):
        # Update progress for large datasets
        if progress_bar is not None and i % 50 == 0:  # Update every 50 items
            progress = i / len(analysis_codes)
            progress_bar.progress(progress)
            status_text.text(f"Processing clinical codes: {i}/{len(analysis_codes)} ({progress:.1%})")
        
        # Handle both raw format (code_value) and standardized format (EMIS GUID)
        emis_guid = code.get('EMIS GUID', code.get('code_value', code.get('emis_guid', ''))).strip()
        
        
        # Fast dictionary lookup
        snomed_code = 'N/A'
        snomed_desc = 'N/A' 
        mapping_found = 'Not found'
        
        
        # Default enriched values
        code_type = 'Finding'
        has_qualifier = '0'
        is_parent = '0'
        descendants = '0'
        
        if emis_guid and emis_guid != 'N/A':
            # Try dictionary lookup
            if emis_guid in lookup_dict:
                snomed_value = lookup_dict[emis_guid]
                if isinstance(snomed_value, float) and snomed_value.is_integer():
                    snomed_code = str(int(snomed_value))
                else:
                    snomed_code = str(snomed_value).strip()
                
                # Get SNOMED description from original XML parsing
                snomed_desc = code.get('display_name', 'N/A')
                
                # Get enriched metadata
                code_type = str(code_type_dict.get(emis_guid, 'Finding')).strip()
                has_qualifier = str(has_qualifier_dict.get(emis_guid, '0')).strip()
                is_parent = str(is_parent_dict.get(emis_guid, '0')).strip()
                descendants = str(descendants_dict.get(emis_guid, '0')).strip()
                
                
                mapping_found = 'Found'
            else:
                mapping_found = 'Not Found'
        
        # Enrich the original code with lookup data instead of creating new structure
        enriched_code = code.copy()  # Start with original structure
        
        # Add/update enriched fields
        enriched_code['SNOMED Code'] = snomed_code
        enriched_code['SNOMED Description'] = snomed_desc  
        enriched_code['Mapping Found'] = mapping_found
        enriched_code['Has Qualifier'] = has_qualifier
        enriched_code['Descendants'] = descendants
        enriched_code['Code Type'] = code_type
        enriched_code['Is Parent'] = is_parent
        
        # Preserve important original fields
        if 'is_refset' in code:
            enriched_code['is_refset'] = code['is_refset']
        if 'is_pseudorefset' in code:
            enriched_code['is_pseudorefset'] = code['is_pseudorefset']
        if 'is_pseudomember' in code:
            enriched_code['is_pseudomember'] = code['is_pseudomember']
        if 'is_pseudo' in code:
            enriched_code['is_pseudo'] = code['is_pseudo']
        if 'is_medication' in code:
            enriched_code['is_medication'] = code['is_medication']
        if 'is_pseudorefset' in code:
            enriched_code['is_pseudorefset'] = code['is_pseudorefset']
        if 'is_pseudomember' in code:
            enriched_code['is_pseudomember'] = code['is_pseudomember']
            
        # Add standard translation fields if missing
        if 'ValueSet GUID' not in enriched_code:
            enriched_code['ValueSet GUID'] = 'N/A'
        # Don't set ValueSet Description to 'N/A' - let standardization handle placeholder text
        if 'Include Children' not in enriched_code:
            enriched_code['Include Children'] = 'Yes' if code.get('include_children', False) else 'No'
        # Pseudo-refset member status is now determined by the is_pseudomember flag from XML structure analysis
        
        translated_codes.append(enriched_code)
    
    # Complete progress and cleanup
    if progress_bar is not None:
        progress_bar.progress(1.0)
        status_text.text(f"✅ Completed processing {len(analysis_codes)} clinical codes")
        # Clear progress indicators after a brief delay
        import time
        time.sleep(0.5)
        progress_bar.empty()
        status_text.empty()
        
        # Mark this processing as complete to avoid showing progress bar again
        st.session_state[processing_cache_key] = True
    
    # CRITICAL PERFORMANCE FIX: Cache the translation results for instant future access
    st.session_state[translation_cache_key] = translated_codes
    
    return translated_codes


def _build_report_type_caption(report_results):
    """Build a caption showing report type counts with proper plurality"""
    if not report_results or not hasattr(report_results, 'report_breakdown'):
        return "audit/list/aggregate reports"
    
    # Count each report type
    type_counts = {}
    for report_type, reports in report_results.report_breakdown.items():
        if reports:  # Only include types that have reports
            type_counts[report_type] = len(reports)
    
    if not type_counts:
        return "audit/list/aggregate reports"
    
    # Build caption parts with proper plurality
    caption_parts = []
    for report_type, count in type_counts.items():
        # Proper plurality handling
        if count == 1:
            caption_parts.append(f"1 {report_type} report")
        else:
            caption_parts.append(f"{count} {report_type} reports")
    
    # Join with proper grammar
    if len(caption_parts) == 1:
        return caption_parts[0]
    elif len(caption_parts) == 2:
        return f"{caption_parts[0]} and {caption_parts[1]}"
    else:
        # Oxford comma for 3 or more items
        return ", ".join(caption_parts[:-1]) + f", and {caption_parts[-1]}"


def _add_source_info_to_clinical_data(clinical_data, guid_to_source_name=None, guid_to_source_container=None, show_sources=True):
    """Add source tracking information to clinical codes data with GUID mapping support"""
    if not show_sources or not clinical_data:
        return clinical_data
    
    # Check current deduplication mode for conditional source column display
    import streamlit as st
    current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
    show_source_columns = (current_mode == 'unique_per_entity')
    
    # Build GUID mappings if not provided
    if guid_to_source_name is None:
        guid_to_source_name = {}
        guid_to_source_container = {} if guid_to_source_container is None else guid_to_source_container
        
        # Get search and report results for GUID mapping
        search_results = st.session_state.get('search_results')
        report_results = st.session_state.get('report_results')
        
        
        # Add search GUID mappings - map individual code EMIS GUIDs to search names with detailed container tracking
        if search_results and hasattr(search_results, 'searches'):
            for search in search_results.searches:
                for group in search.criteria_groups:
                    for criterion in group.criteria:
                        # Check if this criterion has restrictions (which contain testAttribute codes)
                        has_restrictions = hasattr(criterion, 'restrictions') and len(getattr(criterion, 'restrictions', [])) > 0
                        
                        # Check for different structural patterns based on EMIS XML patterns
                        
                        # Check if this is a linked criteria (cross-table relationships)
                        is_linked_criteria = (hasattr(criterion, 'linked_criteria') and getattr(criterion, 'linked_criteria', False)) or \
                                           (hasattr(criterion, 'linkedCriterion') and getattr(criterion, 'linkedCriterion', None))
                        
                        # Check if this is from a base criteria group (nested criterion logic)
                        is_base_criteria_group = hasattr(criterion, 'baseCriteriaGroup') and getattr(criterion, 'baseCriteriaGroup', None)
                        
                        # Check if this is a population criteria reference
                        is_population_ref = len(group.population_criteria) > 0
                        
                        # Check if restrictions contain test attributes
                        has_test_attributes = has_restrictions and hasattr(criterion, 'restrictions') and \
                                            any(hasattr(r, 'test_attribute') or hasattr(r, 'testAttribute') for r in criterion.restrictions if r)
                        
                        for value_set in criterion.value_sets:
                            # Map ValueSet GUID for refsets/pseudo-refsets (NOT description - that's different from source name)
                            valueset_guid = value_set.get('id') or value_set.get('guid')
                            if valueset_guid:
                                guid_to_source_name[valueset_guid] = search.name
                                
                                # Determine container type for ValueSet level
                                container_type = "Search Rule Main Criteria"
                                if is_base_criteria_group:
                                    container_type = "Search Rule Base Criteria Group"
                                elif is_linked_criteria:
                                    container_type = "Search Rule Linked Criteria"
                                elif is_population_ref:
                                    container_type = "Search Rule Population Reference"
                                elif has_test_attributes:
                                    container_type = "Search Rule Test Attribute"
                                elif has_restrictions:
                                    container_type = "Search Rule Restriction"
                                
                                guid_to_source_container[valueset_guid] = container_type
                            
                            # Also map individual codes within value sets
                            for value in value_set.get('values', []):
                                # Get the individual code EMIS GUID (not the ValueSet GUID)
                                emis_guid = value.get('value', '')  # This should be the individual code GUID
                                # Skip EMIS internal codes entirely - they shouldn't appear in clinical displays
                                code_system = value.get('code_system', '').upper()
                                if emis_guid and code_system != 'EMISINTERNAL':
                                    guid_to_source_name[emis_guid] = search.name
                                    
                                    # Determine container type based on EMIS XML structural patterns
                                    container_type = "Search Rule Main Criteria"
                                    
                                    # Priority order based on structural complexity
                                    if is_base_criteria_group:
                                        container_type = "Search Rule Base Criteria Group"
                                    elif is_linked_criteria:
                                        container_type = "Search Rule Linked Criteria"
                                    elif is_population_ref:
                                        container_type = "Search Rule Population Reference"
                                    elif has_test_attributes:
                                        container_type = "Search Rule Test Attribute"
                                    elif has_restrictions:
                                        # Basic restrictions without test attributes
                                        container_type = "Search Rule Restriction"
                                    
                                    guid_to_source_container[emis_guid] = container_type
        
        # Add report GUID mappings - map individual code EMIS GUIDs to report names  
        if report_results and hasattr(report_results, 'clinical_codes'):
            for code in report_results.clinical_codes:
                emis_guid = code.get('code_value', '')  # Report analyzer uses 'code_value'
                report_name = code.get('source_report_name', '')
                if emis_guid and report_name:
                    guid_to_source_name[emis_guid] = report_name
                    # Determine container type based on EMIS report structural patterns
                    container_type = "Report Main Criteria"
                    
                    # Priority order based on report structure patterns
                    if code.get('from_column_group'):
                        # List Report column groups - most specific
                        container_type = "List Report Column Group"
                    elif code.get('from_base_criteria_group'):
                        container_type = "Report Base Criteria Group"  
                    elif code.get('from_linked_criteria'):
                        container_type = "Report Linked Criteria"
                    elif code.get('from_population_ref'):
                        container_type = "Report Population Reference"
                    elif code.get('from_test_attribute'):
                        container_type = "Report Test Attribute"
                    elif code.get('from_audit_aggregate'):
                        container_type = "Audit Report Custom Aggregate"
                    elif code.get('from_sub_criteria'):
                        container_type = "Report Sub Criteria"
                    
                    guid_to_source_container[emis_guid] = container_type
        
    enhanced_data = []
    
    for code_entry in clinical_data:
        enhanced_entry = copy.deepcopy(code_entry)  # Proper deep copy
        
        # Get the GUID for mapping (try different key formats for different data types)
        emis_guid = (code_entry.get('code_value', '') or 
                    code_entry.get('EMIS GUID', '') or 
                    code_entry.get('VALUESET GUID', '') or 
                    code_entry.get('ValueSet GUID', '') or 
                    code_entry.get('SNOMED Code', ''))
        
        # Debug: Check if we have mapping data and what keys are available
        import streamlit as st
        
        # Prioritize GUID mapping over inherited source fields (which may be empty for containers)
        if guid_to_source_name and emis_guid in guid_to_source_name:
            source_name = guid_to_source_name[emis_guid]
        else:
            source_name = code_entry.get('source_name', '')  # Actual search/report name - pass through whatever was provided
        
        # Map GUID to source container if available
        if guid_to_source_container and emis_guid in guid_to_source_container:
            source_container = guid_to_source_container[emis_guid]
        else:
            source_container = code_entry.get('source_container', '')  # Container within the source structure
        
        # Extract source information from the original data if available
        source_type = code_entry.get('source_type', '')
        report_type = code_entry.get('report_type', '')
        
        # Determine the main source category 
        if source_type == 'search':
            source_category = 'Search'
        elif source_type == 'report':
            if report_type == 'list':
                source_category = 'List Report'
            elif report_type == 'audit':
                source_category = 'Audit Report'
            else:
                source_category = 'Report'
        else:
            source_category = ''  # No source info available
        
        # Add processed columns with proper data separation and NO emojis (for clean CSV export)
        # Always add source columns - the UI layer will hide them in unique_codes mode
        # Ensure string types for PyArrow compatibility
        enhanced_entry['Source Type'] = str(source_category)  # Category (Search, List Report, etc.)
        enhanced_entry['Source Name'] = str(source_name)  # Actual name of search/report - all must have names
        enhanced_entry['Source Container'] = str(source_container)  # Location within the source structure
        
        # Remove raw tracking fields now that we've processed them into display columns
        enhanced_entry.pop('source_type', None)
        enhanced_entry.pop('report_type', None) 
        enhanced_entry.pop('source_name', None)
        enhanced_entry.pop('source_container', None)
        
        # Remove unwanted columns that shouldn't be displayed
        enhanced_entry.pop('Source GUID', None)  # Remove irrelevant Source GUID
        enhanced_entry.pop('source_guid', None)  # Remove raw source GUID field
        enhanced_entry.pop('Description', None)  # Remove duplicate/unwanted Description column
        enhanced_entry.pop('Display Name', None)  # Remove unwanted Display Name column
        
        # Keep ValueSet GUID for GUID mapping purposes, but it will be hidden from display by UI layer
        
        enhanced_data.append(enhanced_entry)
    
    return enhanced_data


def ensure_analysis_cached(xml_content=None):
    """
    Ensure that analysis data is cached in session state.
    This function only returns existing cached analysis.
    
    Args:
        xml_content: XML content (ignored - kept for compatibility)
    """
    # Only return existing analysis, never trigger expensive recomputation
    analysis = st.session_state.get('search_analysis')
    xml_structure_analysis = st.session_state.get('xml_structure_analysis')
    
    return analysis or xml_structure_analysis


def extract_clinical_codes_from_searches(searches):
    """Extract clinical codes from search criteria in the orchestrated analysis"""
    clinical_codes = []
    
    for search in searches:
        if hasattr(search, 'criteria_groups'):
            for group in search.criteria_groups:
                if hasattr(group, 'criteria'):
                    for criterion in group.criteria:
                        if hasattr(criterion, 'value_sets'):
                            for value_set in criterion.value_sets:
                                # Extract clinical codes from value set
                                if value_set.get('values'):
                                    for value in value_set['values']:
                                        if value.get('code_system') != 'EMISINTERNAL':  # Exclude internal codes
                                            clinical_codes.append({
                                                'EMIS GUID': value.get('value', ''),
                                                'SNOMED Code': value.get('value', ''),
                                                'SNOMED Description': value.get('display_name', ''),
                                                'display_name': value.get('display_name', ''),  # Add for lookup function
                                                'ValueSet GUID': value_set.get('id', ''),
                                                'ValueSet Description': value_set.get('description', ''),
                                                'Code System': value.get('code_system', value_set.get('code_system', 'SNOMED_CONCEPT')),
                                                'Include Children': 'Yes' if value.get('include_children') else 'No',
                                                'is_refset': value.get('is_refset', False),  # Preserve refset flag
                                                'is_pseudorefset': value.get('is_pseudorefset', False),  # Preserve pseudo-refset flag
                                                'is_pseudomember': value.get('is_pseudomember', False),  # Preserve pseudo-member flag
                                                'is_medication': _is_medication_from_context(
                                                    value.get('code_system', value_set.get('code_system', 'SNOMED_CONCEPT')),
                                                    value.get('table_context'),
                                                    value.get('column_context')
                                                ),  # Set medication flag based on code system and context
                                                'is_pseudorefset': value.get('is_pseudorefset', False),  # Preserve pseudo-refset container flag from XML structure analysis
                                                'is_pseudomember': value.get('is_pseudomember', False),  # Preserve pseudo-refset member flag from XML structure analysis
                                                'Source Name': search.name,
                                                'Source Type': 'Search',
                                                'Source Container': determine_container_type(criterion, group),
                                                'Mapping Found': 'Found',  # Assume found for now
                                                'source_type': 'search',
                                                'source_name': search.name,
                                                'source_container': determine_container_type(criterion, group),
                                            })
    
    return clinical_codes


def determine_container_type(criterion, group):
    """Determine the container type based on criterion and group context"""
    # TODO: Implement the container detection logic from EMIS XML patterns
    # For now, return basic container type
    return "Search Rule Main Criteria"


def _determine_proper_container_type(code):
    """
    Determine proper container type based on code source and context.
    Implements EMIS XML patterns from docs/emis-xml-patterns.md
    """
    # Check if this is from a report
    source_type = code.get('source_type') or code.get('_original_fields', {}).get('source_type', '')
    
    if source_type == 'report':
        # Report codes - use column group name or logical table
        column_group = code.get('column_group_name') or code.get('_original_fields', {}).get('column_group_name')
        if column_group:
            return f"Report Column Group: {column_group}"
        
        logical_table = code.get('logical_table') or code.get('_original_fields', {}).get('logical_table')
        if logical_table:
            return f"Report Table: {logical_table}"
        
        # Check if from column group
        if code.get('from_column_group') or code.get('_original_fields', {}).get('from_column_group'):
            return "Report Column Filter"
        
        return "Report Column"
    
    # Search codes - determine container type based on EMIS XML patterns
    existing_container = (code.get('source_container') or 
                         code.get('Source Container') or 
                         code.get('_original_fields', {}).get('source_container'))
    
    if existing_container and existing_container != '':
        return existing_container
    
    # Advanced container detection based on EMIS XML patterns
    # Check for Base Criteria Group patterns
    original_fields = code.get('_original_fields', {})
    
    # Look for nested criteria patterns (Base Criteria Groups)
    if ('baseCriteriaGroup' in str(original_fields) or 
        'nested' in existing_container.lower() if existing_container else False):
        return "Search Rule Base Criteria Group"
    
    # Look for linked criteria patterns  
    if ('linked' in existing_container.lower() if existing_container else False or
        'linkedCriteria' in str(original_fields)):
        return "Search Rule Linked Criteria"
    
    # Look for population reference patterns
    if ('population' in existing_container.lower() if existing_container else False or
        'populationCriterion' in str(original_fields)):
        return "Search Rule Population Reference"
    
    # Look for test attribute patterns
    if ('test' in existing_container.lower() if existing_container else False or
        'testAttribute' in str(original_fields) or
        'NUMERIC_VALUE' in str(original_fields)):
        return "Search Rule Test Attribute"
    
    # Look for restriction patterns  
    if ('restriction' in existing_container.lower() if existing_container else False or
        'dateRestriction' in str(original_fields) or
        'latestRecords' in str(original_fields)):
        return "Search Rule Restriction"
    
    # Check table type for more specific categorization
    table_type = original_fields.get('table') or original_fields.get('logical_table', '')
    if table_type:
        table_containers = {
            'EVENTS': 'Search Rule Clinical Events',
            'MEDICATION_ISSUES': 'Search Rule Medication Issues', 
            'MEDICATION_COURSES': 'Search Rule Medication Courses',
            'PATIENTS': 'Search Rule Patient Demographics',
            'GPES_JOURNALS': 'Search Rule GP Registration'
        }
        if table_type in table_containers:
            return table_containers[table_type]
    
    # Default fallback
    return "Search Rule Main Criteria"




def is_pseudo_refset_valueset(valueset_guid, valueset_description):
    """Check if a valueset is a pseudo-refset based on patterns"""
    # Import the existing logic from xml_utils (in root directory)
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    from ...xml_parsers.xml_utils import is_pseudo_refset
    return is_pseudo_refset(valueset_guid, valueset_description)


# =============================================================================
# REPORT ORCHESTRATION FUNCTIONS
# =============================================================================

def prepare_report_for_caching(report):
    """
    Prepare report data for caching by extracting key structure information
    
    Args:
        report: Report object to analyze
        
    Returns:
        Dictionary with report structure data for cache key generation
    """
    report_structure = {
        'report_id': getattr(report, 'id', 'unknown'),
        'report_type': getattr(report, 'report_type', 'unknown'),
        'report_name': getattr(report, 'name', 'unknown')
    }
    
    # Add type-specific structure data
    if hasattr(report, 'column_groups') and report.column_groups:
        report_structure['column_groups_count'] = len(report.column_groups)
        report_structure['total_columns'] = sum(len(group.get('columns', [])) for group in report.column_groups)
    
    if hasattr(report, 'population_references') and report.population_references:
        report_structure['population_refs_count'] = len(report.population_references)
    
    if hasattr(report, 'criteria_groups') and report.criteria_groups:
        report_structure['criteria_count'] = len(report.criteria_groups)
    
    if hasattr(report, 'aggregate_groups') and report.aggregate_groups:
        report_structure['aggregate_groups_count'] = len(report.aggregate_groups)
    
    if hasattr(report, 'statistical_groups') and report.statistical_groups:
        report_structure['statistical_groups_count'] = len(report.statistical_groups)
    
    return report_structure

def extract_report_clinical_codes(report):
    """
    Extract all clinical codes from a report for caching
    
    Args:
        report: Report object to extract codes from
        
    Returns:
        List of clinical code dictionaries
    """
    clinical_codes = []
    
    if not hasattr(report, 'column_groups') or not report.column_groups:
        return clinical_codes
    
    for group in report.column_groups:
        if not group.get('has_criteria', False) or not group.get('criteria_details'):
            continue
            
        criteria_list = group['criteria_details'].get('criteria', [])
        for criterion in criteria_list:
            value_sets = criterion.get('value_sets', [])
            for value_set in value_sets:
                codes = value_set.get('values', [])
                for code in codes:
                    emis_guid = code.get('value', 'N/A')
                    code_name = code.get('display_name', 'N/A')
                    include_children = code.get('include_children', False)
                    is_refset = code.get('is_refset', False)
                    
                    clinical_codes.append({
                        'EMIS GUID': emis_guid,
                        'Code Name': code_name,
                        'Include Children': include_children,
                        'Is Refset': is_refset,
                        'Source Type': 'Report',
                        'Source Report': getattr(report, 'name', 'Unknown'),
                        'Source Report ID': getattr(report, 'id', 'unknown')
                    })
    
    return clinical_codes

def get_report_parent_info(report, analysis):
    """
    Get parent search information for a report with caching optimization
    
    Args:
        report: Report object
        analysis: Analysis data containing all reports
        
    Returns:
        Parent search name or None
    """
    if not hasattr(report, 'direct_dependencies') or not report.direct_dependencies:
        return None
        
    parent_guid = report.direct_dependencies[0]  # First dependency is usually the parent
    
    # Use cached lookup instead of linear search
    cache_key = f'parent_lookup_{parent_guid}'
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    # Find the parent report by GUID
    for parent_report in analysis.reports:
        if parent_report.id == parent_guid:
            parent_name = parent_report.name
            st.session_state[cache_key] = parent_name
            return parent_name
    
    # Fallback to shortened GUID
    fallback_name = f"Search {parent_guid[:8]}..."
    st.session_state[cache_key] = fallback_name
    return fallback_name

def should_report_be_cached(report, report_structure):
    """
    Determine if a report should be cached based on complexity
    
    Args:
        report: Report object
        report_structure: Report structure data from prepare_report_for_caching
        
    Returns:
        Boolean indicating if report should be cached
    """
    # Always cache reports with clinical codes
    total_columns = report_structure.get('total_columns', 0)
    criteria_count = report_structure.get('criteria_count', 0)
    
    # Cache if report has significant complexity
    return total_columns > 5 or criteria_count > 3

def get_unified_clinical_data():
    """Get clinical data from orchestrated analysis using centralized cache manager"""
    import streamlit as st
    
    # Check if we already have cached unified data with smart cache key
    cache_key_name = 'unified_clinical_data_cache'
    if cache_key_name in st.session_state:
        cached_data = st.session_state.get(cache_key_name)
        if cached_data is not None:
            return cached_data
    
    # Get comprehensive analysis data
    analysis = st.session_state.get('xml_structure_analysis')
    if not analysis:
        return None
    
    
    # Extract clinical codes from both searches and reports
    all_clinical_codes = []
    
    # Get clinical codes from reports (prefer orchestrated_results, fallback to report_results)
    report_codes_added = False
    if (hasattr(analysis, 'orchestrated_results') and analysis.orchestrated_results and 
        hasattr(analysis.orchestrated_results, 'report_clinical_codes') and 
        analysis.orchestrated_results.report_clinical_codes):
        all_clinical_codes.extend(analysis.orchestrated_results.report_clinical_codes)
        report_codes_added = True
    elif (hasattr(analysis, 'report_results') and analysis.report_results and
          hasattr(analysis.report_results, 'clinical_codes') and
          analysis.report_results.clinical_codes):
        all_clinical_codes.extend(analysis.report_results.clinical_codes)
        report_codes_added = True
        
    # Get clinical codes from searches (prefer orchestrated_results, fallback to search_results)
    search_codes_added = False
    if (hasattr(analysis, 'orchestrated_results') and analysis.orchestrated_results and
        hasattr(analysis.orchestrated_results, 'searches') and analysis.orchestrated_results.searches):
        orchestrated_search_codes = extract_clinical_codes_from_searches(analysis.orchestrated_results.searches)
        all_clinical_codes.extend(orchestrated_search_codes)
        search_codes_added = True
    elif (hasattr(analysis, 'search_results') and analysis.search_results and
          hasattr(analysis.search_results, 'searches') and analysis.search_results.searches):
        search_clinical_codes = extract_clinical_codes_from_searches(analysis.search_results.searches)
        all_clinical_codes.extend(search_clinical_codes)
        search_codes_added = True
    
    # Convert data format using universal field mapping system
    from .field_mapping import standardize_clinical_codes_list, get_field_value, StandardFields
    
    # Apply SNOMED lookup FIRST before filtering to enrich all codes
    translated_clinical_codes = _convert_analysis_codes_to_translation_format(all_clinical_codes)
    all_clinical_codes = translated_clinical_codes  # Use enriched data for filtering
    
    # Apply filtering after enrichment - separate codes for different tabs
    clinical_codes = []  # Standalone clinical codes only  
    medication_codes = []  # Medications
    refset_codes = []  # True refsets
    pseudo_refset_codes = []  # Pseudo-refset containers
    pseudo_member_codes = []  # Pseudo-refset members
    
    # Categorize on enriched data before standardization
    for code in all_clinical_codes:
        # Skip EMISINTERNAL codes entirely (these are internal EMIS filters like gender, age)
        code_system = get_field_value(code, StandardFields.CODE_SYSTEM, '').upper()
        if code_system == 'EMISINTERNAL':
            continue
            
        # Skip patient demographics and non-clinical filters
        table = code.get('table', '').upper()
        column = code.get('column', '').upper()
        if table == 'PATIENTS' or column in ['SEX', 'AGE', 'DOB', 'GENDER']:
            continue
            
        # Skip library item GUIDs (typically have dashes and are not numeric SNOMED codes)
        code_value = get_field_value(code, StandardFields.EMIS_GUID, '')
        if code_value and '-' in code_value and len(code_value) == 36:  # Standard GUID format
            continue
            
        # Separate medications for medications tab - check table info and proper code systems only
        table = code.get('table', '').upper()
        logical_table = code.get('logical_table', '').upper()
        source_name = code.get('source_name', '').lower()
        source_container = code.get('source_container', '').lower()
        original_code_system = code.get('_original_fields', {}).get('code_system', '')
        
        # Use the is_medication flag that was set during extraction based on proper code system/context detection
        is_medication = code.get('is_medication', False)
        if is_medication:
            medication_codes.append(code)
            continue
            
        # Determine code type based on structure and properties
        emis_guid = code.get('EMIS GUID', '')
        snomed_code = code.get('SNOMED Code', '')
        is_refset_flag = code.get('is_refset', False)
        
        # Clean refset descriptions for display
        display_name = get_field_value(code, StandardFields.SNOMED_DESCRIPTION, '')
        if display_name.startswith('Refset: ') and '[' in display_name:
            # Extract "NDAHEIGHT_COD" from "Refset: NDAHEIGHT_COD[999002731000230106]"
            refset_name = display_name.replace('Refset: ', '').split('[')[0]
            code['display_name'] = refset_name
            code['SNOMED Description'] = refset_name

        # Categorize codes based on type using the new flags
        is_pseudorefset = code.get('is_pseudorefset', False)
        is_pseudomember = code.get('is_pseudomember', False)
        
        
        if is_refset_flag and not is_pseudorefset:
            # True refsets only (not pseudo-refset containers)
            refset_codes.append(code)
        elif is_pseudorefset:
            # Pseudo-refset containers go to pseudo_refsets
            code['Source Container'] = _determine_proper_container_type(code)
            pseudo_refset_codes.append(code)
        elif is_pseudomember:
            # Codes that are members of pseudo-refsets go to separate pseudo-member list
            code['Source Container'] = _determine_proper_container_type(code)
            pseudo_member_codes.append(code)
        else:
            # All other codes go to clinical codes
            code['Source Container'] = _determine_proper_container_type(code)
            clinical_codes.append(code)
    
    # Apply standardization to each category separately 
    standardized_clinical_codes = standardize_clinical_codes_list(clinical_codes)
    standardized_medication_codes = standardize_clinical_codes_list(medication_codes)
    standardized_refset_codes = standardize_clinical_codes_list(refset_codes)
    standardized_pseudo_refset_codes = standardize_clinical_codes_list(pseudo_refset_codes)
    standardized_pseudo_member_codes = standardize_clinical_codes_list(pseudo_member_codes)
    
    # Create unified results structure with properly categorized and standardized codes
    unified_results = {
        'clinical_codes': standardized_clinical_codes,  # Standalone clinical codes only
        'medications': standardized_medication_codes,  # Separated medications  
        'refsets': standardized_refset_codes,  # True refsets only
        'pseudo_refsets': standardized_pseudo_refset_codes,  # Pseudo-refset containers only
        'clinical_pseudo_members': standardized_pseudo_member_codes,  # Pseudo-refset member codes
    }
    
    
    # Enhance source tracking with GUID mapping for all clinical data
    # The function should already be available in this module
    
    # Lookup already applied earlier before filtering
    # The unified parsing approach already provides better source tracking than GUID mapping
    
    # Apply standardization to pseudo-refset members  
    if unified_results.get('clinical_pseudo_members'):
        # Standardize pseudo-refset members to ensure consistent field formatting including source types
        unified_results['clinical_pseudo_members'] = standardize_clinical_codes_list(unified_results['clinical_pseudo_members'])
    
    
    # Cache the results using the new cache manager AND session state for immediate access
    analysis_hash = cache_manager.generate_data_hash(unified_results)
    cache_manager.cache_unified_clinical_data(
        analysis_hash, 
        unified_results.get('clinical_codes', []),
        unified_results.get('clinical_reports', []), 
        unified_results.get('clinical_medications', []),
        unified_results.get('clinical_refsets', []),
        unified_results.get('clinical_pseudo_members', [])
    )
    
    # CRITICAL FIX: Store in session state for immediate caching
    st.session_state[cache_key_name] = unified_results
    
    return unified_results