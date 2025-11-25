"""
List Report tab rendering functions.

This module handles rendering of the List Reports tab with dedicated 
browser and analysis functionality. List Reports display patient data 
in column-based tables with specific data extraction rules.

Extracted from report_tabs.py to improve modularity and maintainability.
"""

from .common_imports import *
from ...core.session_state import SessionStateKeys
from ...ui.theme import info_box, success_box, warning_box, error_box
from .tab_helpers import (
    ensure_analysis_cached,
    _get_report_size_category,
    _monitor_memory_usage,
    _batch_lookup_snomed_for_ui,
    _lookup_snomed_for_ui,
    _load_report_metadata,
    _extract_clinical_codes,
    _process_column_groups,
    is_data_processing_needed,
    cache_processed_data
)
from ...analysis.search_rule_visualizer import render_column_filter
from ...utils.caching.cache_manager import cache_manager
from datetime import datetime
from typing import List, Dict
import gc
import psutil
import os

# Additional required imports not in common_imports
from ..ui_helpers import (
    render_section_with_data, 
    render_metrics_row, 
    render_success_rate_metric,
    get_success_highlighting_function,
    get_warning_highlighting_function,
    create_expandable_sections,
    render_info_section
)


def render_list_reports_tab(xml_content: str, xml_filename: str):
    """
    Render the List Reports tab with dedicated List Report browser and analysis.
    
    Args:
        xml_content: The XML content to analyze
        xml_filename: Name of the XML file being processed
        
    This function displays List Reports which show patient data in column-based tables
    with specific data extraction rules. It provides metrics, folder-based browsing,
    and detailed analysis of column structures and filtering criteria.
    """

    
    if not xml_content:
        st.markdown(info_box("📋 Upload and process an XML file to see List Reports"), unsafe_allow_html=True)
        return
    
    try:
        
        # Use ONLY cached analysis data - never trigger reprocessing
        analysis = st.session_state.get(SessionStateKeys.SEARCH_ANALYSIS) or st.session_state.get(SessionStateKeys.XML_STRUCTURE_ANALYSIS)
        if not analysis:
            st.markdown(error_box("⚠️ Analysis data not available. Please ensure XML processing completed successfully."), unsafe_allow_html=True)
            st.markdown(info_box("💡 Try refreshing the page or uploading your XML file again."), unsafe_allow_html=True)
            return
        
        from ...core.report_classifier import ReportClassifier
        
        # Using pre-processed data - no memory optimization needed
        
        # PERFORMANCE FIX: Use ONLY pre-processed report breakdown to avoid expensive filtering
        report_results = st.session_state.get(SessionStateKeys.REPORT_RESULTS)
        
        if report_results and hasattr(report_results, 'report_breakdown') and 'list' in report_results.report_breakdown:
            list_reports = report_results.report_breakdown['list']
        else:
            st.markdown(info_box("📋 No List Reports found in this XML file."), unsafe_allow_html=True)
            st.caption("This XML contains only searches or other report types.")
            return
        
        from ...core.report_classifier import ReportClassifier
        
        # PERFORMANCE FIX: Use ONLY pre-processed report breakdown to avoid expensive filtering
        report_results = st.session_state.get(SessionStateKeys.REPORT_RESULTS)
        
        if report_results and hasattr(report_results, 'report_breakdown') and 'list' in report_results.report_breakdown:
            list_reports = report_results.report_breakdown['list']
        else:
            # No pre-processed data available - skip expensive processing
            st.markdown(info_box("📋 No List Reports found in this XML file."), unsafe_allow_html=True)
            st.caption("This XML contains only searches or other report types.")
            return
        list_count = len(list_reports)
        
        # Only show toast on first load or when data actually changes
        toast_cache_key = 'list_reports_toast_shown'
        if is_data_processing_needed(toast_cache_key):
            st.toast(f"Found {list_count} List Report{'s' if list_count != 1 else ''}", icon="📋")
            cache_processed_data(toast_cache_key, True)
        
        if not list_reports:
            st.markdown(info_box("📋 No List Reports found in this XML file"), unsafe_allow_html=True)
            return

        # 📋 List Reports Analysis - Collapsed expandable frame (not fragmented)
        # 🔧 List Report Logic Browser - Fragmented expandable frame (prevents full reruns)
        with st.expander("🔧 List Report Logic Browser", expanded=True):
            @st.fragment
            def list_report_browser_fragment():
                from .report_tabs import render_report_type_browser
                render_report_type_browser(list_reports, analysis, "List Report", "📋")
            
            list_report_browser_fragment()

        with st.expander("📋 List Reports Analysis", expanded=False):
            st.markdown("List Reports display patient data in column-based tables with specific data extraction rules.")
            
            # List Reports metrics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("📋 List Reports", list_count)
                
            with col2:
                total_columns = sum(len(report.column_groups) if hasattr(report, 'column_groups') and report.column_groups else 0 for report in list_reports)
                st.metric("📊 Total Column Groups", total_columns)
            
            with col3:
                # For List Reports, criteria are in column groups, not main criteria_groups
                reports_with_criteria = 0
                for report in list_reports:
                    has_column_criteria = False
                    if hasattr(report, 'column_groups') and report.column_groups:
                        has_column_criteria = any(group.get('has_criteria', False) for group in report.column_groups)
                    if report.criteria_groups or has_column_criteria:
                        reports_with_criteria += 1
                st.metric("🔍 Reports with Criteria", reports_with_criteria)
        
        # PERFORMANCE: Skip cleanup for tab-level functions - only needed for large reports
        pass
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        st.markdown(error_box(f"Error analyzing List Reports: {str(e)}"), unsafe_allow_html=True)
        with st.expander("Debug Information", expanded=False):
            st.code(error_details)


@st.cache_data(ttl=1800, max_entries=1000)  # 30-minute TTL for report rendering
def _render_cached_list_report_content(report_id, report_name, column_groups_data):
    """Cache expensive list report rendering operations using cache_manager"""
    from ...utils.caching.cache_manager import cache_manager
    
    # Generate hash for cache invalidation
    report_hash = cache_manager.generate_report_hash(report_id, {
        'report_name': report_name,
        'column_groups_data': column_groups_data
    })
    
    # Calculate counts for caching
    column_groups_count = len(column_groups_data) if isinstance(column_groups_data, list) else 1
    criteria_count = 0  # Will be populated from actual report analysis
    total_codes = 0     # Will be populated from clinical codes
    
    return cache_manager.cache_list_report_visualization(
        report_id, report_hash, column_groups_count, criteria_count, total_codes
    )


def render_list_report_details(report):
    """
    Render List Report specific details with size-adaptive performance optimization.
    
    Args:
        report: The list report object to display
        
    This function displays the column structure of list reports, including
    column groups, their tables, criteria, and filtering rules. Shows both
    the user-visible column names and the underlying filtering logic.
    Uses size-adaptive memory management and batch processing for performance.
    """
    # PERFORMANCE: Get report size for optimization strategy
    report_size = _get_report_size_category(report)
    
    # SIZE-ADAPTIVE: Only do memory cleanup for large reports
    if report_size == "large":
        from ...utils.caching.cache_manager import cache_manager
        cache_manager.manage_session_state_memory(max_cache_items=15)
        gc.collect()
    st.markdown("### 📋 Column Structure")
    
    if report.column_groups:
        for i, group in enumerate(report.column_groups, 1):
            # Combine group info into cleaner header with restriction info
            group_name = group.get('display_name', 'Unnamed')
            logical_table = group.get('logical_table', 'N/A')
            
            # Check for restrictions to enhance the group name display
            enhanced_group_name = group_name
            if group.get('has_criteria', False) and group.get('criteria_details'):
                criteria_details = group['criteria_details']
                criteria_list = criteria_details.get('criteria', [])
                
                for criterion in criteria_list:
                    restrictions = criterion.get('restrictions', [])
                    for restriction in restrictions:
                        if isinstance(restriction, dict) and restriction.get('record_count'):
                            record_count = restriction.get('record_count')
                            direction = restriction.get('direction', 'DESC')
                            if direction == 'DESC':
                                enhanced_group_name = f"Latest {record_count} {group_name.lower()}"
                            else:
                                enhanced_group_name = f"First {record_count} {group_name.lower()}"
                            break
                    if enhanced_group_name != group_name:  # If we found a restriction, break out of criteria loop
                        break
            
            with st.expander(f"Group {i}: {enhanced_group_name} (Logical Table: {logical_table})", expanded=False):  # Default closed
                
                # Column structure (user-visible EMIS data)
                columns = group.get('columns', [])
                if columns:
                    st.markdown("**📊 Columns:**")
                    col_data = []
                    for col in columns:
                        # Only show what users see in the EMIS UI - the Display Name
                        col_data.append({
                            'Column': col.get('display_name', col.get('column', ''))  # Fallback to technical name if no display name
                        })
                    
                    if col_data:
                        import pandas as pd
                        df = pd.DataFrame(col_data)
                        
                        try:
                            st.dataframe(df, width='stretch', hide_index=True)
                        finally:
                            # REFINED: Clean only this specific display DataFrame, not source data
                            from ...utils.caching.cache_manager import cache_manager
                            cache_manager.cleanup_dataframe_memory([df])
                            del df
                            del col_data
                            # No gc.collect() here - too frequent
                else:
                    st.markdown(info_box("No columns defined"), unsafe_allow_html=True)
                
                # Filtering criteria
                st.markdown(f"**Has Criteria:** {'Yes' if group.get('has_criteria', False) else 'No'}")
                
                # Criteria implementation details
                if group.get('has_criteria', False) and group.get('criteria_details'):
                    criteria_details = group['criteria_details']
                    st.markdown("**🔍 Column Group Criteria:**")
                    
                    criteria_count = criteria_details.get('criteria_count', 0)
                    st.markdown(info_box(f"This column group has {criteria_count} filtering criterion that determines which records appear in this column section."), unsafe_allow_html=True)
                    
                    # Criteria display using standard format
                    criteria_list = criteria_details.get('criteria', [])
                    for j, criterion in enumerate(criteria_list, 1):
                        
                        # Table and action information
                        table_name = criterion.get('table', 'UNKNOWN')
                        negation = criterion.get('negation', False)
                        
                        st.markdown(f"**Table:** {table_name}")
                        
                        if negation:
                            st.markdown("**Action:** ❌ **Exclude**")
                        else:
                            st.markdown("**Action:** ✅ **Include**")
                        
                        # Value sets section - OPTIMIZED: Batch all codes together
                        value_sets = criterion.get('value_sets', [])
                        total_codes = sum(len(vs.get('values', [])) for vs in value_sets) if value_sets else 0
                        if value_sets:
                            with st.expander(f"🏥 Value Set {j} ({total_codes} codes)", expanded=False):
                                # MEMORY OPTIMIZATION: Process each value set individually to prevent memory spikes
                                # Removed all_codes_data accumulation to prevent memory leaks
                                
                                for i, value_set in enumerate(value_sets, 1):
                                    code_system = value_set.get('code_system', 'Unknown')
                                    
                                    # Transform internal code system names to user-friendly labels
                                    if 'SNOMED_CONCEPT' in code_system:
                                        system_display = "SNOMED CT"
                                    elif 'SCT_DRGGRP' in code_system:
                                        system_display = "Drug Group Classification"
                                    elif 'EMISINTERNAL' in code_system:
                                        system_display = "EMIS Internal Classifications"
                                    else:
                                        system_display = code_system
                                    
                                    st.markdown(f"**System:** {system_display}")
                                    
                                    # Display codes as scrollable dataframe with icons
                                    codes = value_set.get('values', [])
                                    if codes:
                                        import pandas as pd
                                        
                                        # MEMORY OPTIMIZATION: Batch process large code sets to prevent memory spikes
                                        code_data = []
                                        
                                        # Process codes in batches for very large value sets
                                        batch_size = 100 if len(codes) > 500 else len(codes)
                                        
                                        for batch_start in range(0, len(codes), batch_size):
                                            batch_end = min(batch_start + batch_size, len(codes))
                                            batch_codes = codes[batch_start:batch_end]
                                            
                                            for code in batch_codes:
                                                emis_guid = code.get('value', 'N/A')
                                                code_name = code.get('display_name', 'N/A')
                                                include_children = code.get('include_children', False)
                                                
                                                # Check if this is a refset
                                                is_refset = code.get('is_refset', False)
                                                
                                                # Handle refsets differently - they are direct SNOMED codes
                                                if is_refset:
                                                    snomed_code = emis_guid  # Refset codes are direct SNOMED codes
                                                    # Clean up the description for refsets
                                                    if code_name.startswith('Refset: ') and '[' in code_name and ']' in code_name:
                                                        # Extract just the name part before the bracket
                                                        clean_name = code_name.replace('Refset: ', '').split('[')[0]
                                                        code_name = clean_name
                                                    scope = '🎯 Refset'
                                                else:
                                                    snomed_code = _lookup_snomed_for_ui(emis_guid)
                                                    # Determine scope indicator for regular codes
                                                    if include_children:
                                                        scope = '👪 + Children'
                                                    else:
                                                        scope = '🎯 Exact'
                                                
                                                code_data.append({
                                                    'EMIS Code': emis_guid,
                                                    'SNOMED Code': snomed_code,
                                                    'Description': code_name,
                                                    'Scope': scope,
                                                    'Is Refset': 'Yes' if is_refset else 'No'
                                                })
                                            
                                            # Clean up batch references immediately
                                            del batch_codes
                                            
                                            # Force garbage collection for very large datasets
                                            if len(codes) > 1000 and (batch_start // batch_size) % 10 == 0:
                                                gc.collect()
                                        
                                        # Create dataframe with custom styling
                                        codes_df = pd.DataFrame(code_data)
                                        dataframes_to_cleanup = [codes_df]  # Track for cleanup
                                        
                                        try:
                                            # Display as scrollable table like Clinical Codes tab
                                            st.dataframe(
                                                codes_df,
                                                width='stretch',
                                                hide_index=True,
                                                column_config={
                                                    "EMIS Code": st.column_config.TextColumn(
                                                        "🔍 EMIS Code",
                                                        width="medium"
                                                    ),
                                                    "SNOMED Code": st.column_config.TextColumn(
                                                        "⚕️ SNOMED Code", 
                                                        width="medium"
                                                    ),
                                                    "Description": st.column_config.TextColumn(
                                                        "📝 Description",
                                                        width="large"
                                                    ),
                                                    "Scope": st.column_config.TextColumn(
                                                        "🔗 Scope",
                                                        width="small"
                                                    ),
                                                    "Is Refset": st.column_config.TextColumn(
                                                        "🎯 Refset",
                                                        width="small"
                                                    )
                                                }
                                            )
                                        finally:
                                            # REFINED: Clean only display DataFrame, preserve SNOMED cache
                                            from ...utils.caching.cache_manager import cache_manager
                                            cache_manager.cleanup_dataframe_memory(dataframes_to_cleanup)
                                            del codes_df
                                            del code_data
                                            # No cleanup of SNOMED cache - needed for tab switching
                        
                        # Filter criteria section
                        st.markdown("**⚙️ Filters:**")
                        column_filters = criterion.get('column_filters', [])
                        if column_filters:
                            for filter_item in column_filters:
                                # Handle column being either string or list
                                column_value = filter_item.get('column', '')
                                if isinstance(column_value, list):
                                    filter_column = str(column_value[0]).upper() if column_value else ''
                                else:
                                    filter_column = str(column_value).upper()
                                filter_name = filter_item.get('display_name', 'Filter')
                                
                                if 'DATE' in filter_column:
                                    # Use comprehensive temporal pattern support from search visualizer
                                    filter_desc = render_column_filter(filter_item)
                                    if filter_desc:
                                        st.caption(f"• {filter_desc}")
                                    else:
                                        # Fallback for unrecognized date patterns
                                        st.caption(f"• Date filtering applied")
                                else:
                                    # Standard clinical code filter with count
                                    if total_codes > 0:
                                        st.caption(f"• Include {total_codes} specified clinical codes")
                                    else:
                                        st.caption(f"• Include specified clinical codes")
                        
                        # Record ordering and restrictions
                        restrictions = criterion.get('restrictions', [])
                        if restrictions:
                            for restriction in restrictions:
                                if restriction.get('record_count'):
                                    count = restriction.get('record_count')
                                    direction = restriction.get('direction', 'DESC').upper()
                                    column = restriction.get('ordering_column')
                                    
                                    if column and column != 'None':
                                        st.caption(f"• Ordering by: {column}, select the latest {count}")
                                    else:
                                        st.caption(f"• Ordering by: Date, select the latest {count}")
                                else:
                                    restriction_desc = restriction.get('description', 'Record restriction applied')
                                    st.caption(f"• Restriction: {restriction_desc}")
                        
                        if j < len(criteria_list):  # Add separator if not last criterion
                            st.markdown("---")
                        
                        # SIZE-ADAPTIVE: Cleanup only for large reports with many criteria
                        if report_size == "large" and j % 50 == 0:  # Every 50 criteria, light cleanup
                            gc.collect()
    else:
        st.markdown(info_box("No column groups found"), unsafe_allow_html=True)
    
    # SIZE-ADAPTIVE: Final cleanup based on report size
    if report_size == "large":
        gc.collect()  # Only for large reports
    # Small/medium reports: no final cleanup for better performance
    
    # Dependencies are now shown in the header as "Parent Search" - no need for separate section
