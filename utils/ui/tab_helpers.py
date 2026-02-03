"""
Shared utility functions for tab rendering.

This module contains helper functions that are used across multiple
tab rendering modules but are specific to tab functionality.
"""

from datetime import datetime
import re
from typing import Any, Dict, List, Tuple

import streamlit as st
from ..system.session_state import SessionStateKeys
from ..metadata.value_set_resolver import resolve_value_sets

# Caching functions moved to cache_manager.py
# Import cache functions from centralised cache manager
from ..caching.cache_manager import cache_manager


def natural_sort_key(text: str) -> Tuple:
    """
    Generate sort key for natural sorting (numeric-aware).
    Numbers sort before letters to match EMIS-style listings.
    """
    if text is None:
        return (1, 0, "")
    cleaned = str(text).strip()
    match = re.match(r"^(\d+)\.\s*", cleaned)
    if match:
        number = int(match.group(1))
        remaining = cleaned[match.end():].lower()
        return (0, number, remaining)
    return (1, 0, cleaned.lower())


def build_folder_paths(folders: List[Dict[str, Any]]) -> Dict[str, str]:
    """Build folder path labels from folder metadata."""
    id_to_folder = {f.get("id"): f for f in folders if f.get("id")}
    paths: Dict[str, str] = {}

    for folder_id in id_to_folder:
        parts: List[str] = []
        current = id_to_folder.get(folder_id)
        seen: set = set()
        while current:
            current_id = current.get("id")
            if current_id in seen:
                break
            seen.add(current_id)
            parts.append(current.get("name") or current_id or "")
            parent_id = current.get("parent_id")
            current = id_to_folder.get(parent_id) if parent_id else None
        label = " \\ ".join(reversed([p for p in parts if p]))
        if label:
            paths[folder_id] = label
    return paths


def build_folder_groups(
    items: List[Dict[str, Any]],
    folders: List[Dict[str, Any]],
    all_label: str = "All Folders inc Root",
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Build a folder label -> items map, hiding empty folders.
    """
    folder_paths = build_folder_paths(folders)
    items_by_folder: Dict[str, List[Dict[str, Any]]] = {}
    for item in items or []:
        folder_id = item.get("folder_id")
        if folder_id:
            items_by_folder.setdefault(folder_id, []).append(item)

    grouped: Dict[str, List[Dict[str, Any]]] = {all_label: list(items)}
    for folder_id, label in folder_paths.items():
        group_items = items_by_folder.get(folder_id, [])
        if group_items:
            grouped[label] = group_items

    sorted_grouped: Dict[str, List[Dict[str, Any]]] = {all_label: grouped[all_label]}
    for key in sorted([k for k in grouped if k != all_label], key=natural_sort_key):
        sorted_grouped[key] = grouped[key]
    return sorted_grouped


def build_folder_option_list(
    items: List[Dict[str, Any]],
    folders: List[Dict[str, Any]],
    all_label: str = "All Folders inc Root",
) -> List[Dict[str, str]]:
    """
    Build folder options for dropdowns, hiding empty folders.
    """
    folder_paths = build_folder_paths(folders)
    folder_ids_with_items = {item.get("folder_id") for item in items or [] if item.get("folder_id")}
    options: List[Dict[str, str]] = [{"value": "__all__", "label": all_label}]

    labels: List[Tuple[str, str]] = []
    for folder_id in folder_ids_with_items:
        label = folder_paths.get(folder_id) or str(folder_id)
        labels.append((label, folder_id))

    for label, folder_id in sorted(labels, key=lambda x: natural_sort_key(x[0])):
        options.append({"value": folder_id, "label": label})
    return options


def _batch_lookup_snomed_for_ui(emis_guids: List[str]) -> Dict[str, str]:
    """Batch lookup SNOMED codes for multiple EMIS GUIDs - much faster than individual lookups"""
    if not emis_guids:
        return {}
        
    try:
        # Get cached unified data from session state to avoid expensive recomputation
        cached_unified_data = st.session_state.get("unified_clinical_data_cache")
        if cached_unified_data is None:
            # Only call expensive function if no cache exists
            from .clinical_codes.codes_common import get_unified_clinical_data
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



@st.cache_data(show_spinner="Loading report metadata...", ttl=1800, max_entries=10)
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

@st.cache_data(show_spinner="Extracting clinical codes...", ttl=1800, max_entries=10)
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
            value_sets = resolve_value_sets(criterion)
        
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
                value_sets = resolve_value_sets(criterion)
            
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


@st.cache_data(show_spinner="Processing column groups...", ttl=1800, max_entries=10)
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

@st.cache_data(ttl=1800, max_entries=10)  # 30-minute TTL for report pagination
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

@st.cache_data(ttl=1800, max_entries=10, show_spinner="Loading report sections...")
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

@st.cache_data(show_spinner="Preparing export data...", ttl=600, max_entries=10)
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

def _is_medication_from_context(code_system, table_context, column_context):
    """
    Determine if a code is a medication based on code system and table/column context.
    Uses the same logic as code_classification.is_medication_code_system but as a helper function.
    """
    from ..metadata.code_classification import is_medication_code_system
    return is_medication_code_system(code_system, table_context, column_context)


def _reprocess_with_new_mode(deduplication_mode):
    """Handle deduplication mode change - no reprocessing needed, deduplication handled at display level"""
    # No-op function - deduplication is handled at display level
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


def _enrich_pipeline_codes_with_lookup(codes: List[dict]) -> List[dict]:
    """
    Enrich pipeline-produced codes with SNOMED lookup data.
    Uses filtered parquet lookup for memory efficiency.
    """
    import streamlit as st
    from ..caching.lookup_manager import is_lookup_loaded, get_lookup_for_guids

    if not is_lookup_loaded():
        if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
            import sys
            print("[DEBUG][pipeline_ui] Lookup enrichment skipped (lookup not loaded)", file=sys.stderr)
        return codes

    # Extract EMIS GUIDs from codes
    emis_guids = [
        str(code.get("EMIS GUID") or code.get("emis_guid") or "").strip()
        for code in codes
        if code.get("EMIS GUID") or code.get("emis_guid")
    ]

    if not emis_guids:
        return codes

    # Get filtered lookup dicts
    lookup_dicts = get_lookup_for_guids(emis_guids)
    guid_to_snomed = lookup_dicts.get("guid_to_snomed", {})
    guid_to_record = lookup_dicts.get("guid_to_record", {})

    enriched: List[dict] = []
    for code in codes:
        guid = str(code.get("EMIS GUID") or code.get("emis_guid") or "").strip()
        new_code = dict(code)
        if guid:
            snomed_val = guid_to_snomed.get(guid)
            if snomed_val:
                new_code["SNOMED Code"] = snomed_val
                new_code["Mapping Found"] = "Found"

            record = guid_to_record.get(guid, {})
            if record.get("descendants"):
                new_code["Descendants"] = record["descendants"]
            if record.get("has_qualifier"):
                new_code["Has Qualifier"] = str(record["has_qualifier"])

        enriched.append(new_code)

    return enriched


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




def prepare_report_for_caching(report):
    """
    Prepare report data for caching by extracting key structure information
    
    Args:
        report: Report object to analyse
        
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
