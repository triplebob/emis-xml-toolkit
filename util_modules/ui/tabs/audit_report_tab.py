"""
Audit Reports tab rendering functions.

This module handles rendering of audit report-related functionality:
- Audit Reports tab with dedicated browser and analysis
- Audit report detail renderer with organizational aggregation analysis
- Cached audit report content rendering for performance

Extracted from report_tabs.py to maintain focused responsibilities
and improve code organization. All functions maintain compatibility
with existing tab structure and preserve performance optimizations.
"""

from .common_imports import *
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

# Import will be done locally to avoid circular import


def render_audit_reports_tab(xml_content: str, xml_filename: str):
    """
    Render the Audit Reports tab with dedicated Audit Report browser and analysis.
    
    Args:
        xml_content: The XML content to analyze
        xml_filename: Name of the XML file being processed
        
    This function displays Audit Reports which provide organizational aggregation
    for quality monitoring and compliance tracking. Shows metrics about population
    references and additional criteria filtering.
    """
    
    if not xml_content:
        st.info("📊 Upload and process an XML file to see Audit Reports")
        return
    
    try:
        # EMERGENCY BYPASS: Report tabs should NOT trigger expensive analysis
        # If analysis isn't already cached, show error instead of hanging for 10 minutes
        analysis = st.session_state.get('search_analysis') or st.session_state.get('xml_structure_analysis')
        if analysis is None:
            st.error("⚠️ Analysis not available. Please ensure XML processing completed successfully and try refreshing the page.")
            st.info("💡 Try switching to the 'Clinical Codes' tab first, then return to this tab.")
            return
        
        from ...core.report_classifier import ReportClassifier
        
        # Using pre-processed data - no memory optimization needed
        
        # PERFORMANCE FIX: Use ONLY pre-processed report breakdown to avoid expensive filtering
        report_results = st.session_state.get('report_results')
        if report_results and hasattr(report_results, 'report_breakdown') and 'audit' in report_results.report_breakdown:
            audit_reports = report_results.report_breakdown['audit']
        else:
            # No pre-processed data available - skip expensive processing
            st.info("📊 No Audit Reports found in this XML file.")
            st.caption("This XML contains only searches or other report types.")
            return
        
        audit_count = len(audit_reports)
        
        # Only show toast on first load or when data actually changes
        toast_cache_key = 'audit_reports_toast_shown'
        if is_data_processing_needed(toast_cache_key):
            st.toast(f"Found {audit_count} Audit Report{'s' if audit_count != 1 else ''}", icon="📊")
            cache_processed_data(toast_cache_key, True)
        
        st.markdown("### 📊 Audit Reports Analysis")
        st.markdown("Audit Reports provide organizational aggregation for quality monitoring and compliance tracking.")
        
        if not audit_reports:
            st.info("📊 No Audit Reports found in this XML file")
            return
        
        # Audit Reports metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📊 Audit Reports", audit_count)
        with col2:
            # Count unique population references across all audit reports
            all_populations = set()
            for report in audit_reports:
                if hasattr(report, 'population_references') and report.population_references:
                    all_populations.update(report.population_references)
            st.metric("🧑‍🤝‍🧑 Referenced Populations", len(all_populations), help="Total unique base searches referenced by all Audit Reports")
        with col3:
            # Count reports with additional criteria (non-PATIENTS table reports)
            reports_with_criteria = 0
            for report in audit_reports:
                has_criteria = hasattr(report, 'criteria_groups') and report.criteria_groups
                # Also check if it's not a simple PATIENTS table report
                is_patients_only = (hasattr(report, 'custom_aggregate') and 
                                  report.custom_aggregate and 
                                  report.custom_aggregate.get('logical_table') == 'PATIENTS' and 
                                  not has_criteria)
                if has_criteria or not is_patients_only:
                    reports_with_criteria += 1
            st.metric("🔍 Reports with Additional Criteria", reports_with_criteria, help="Reports that apply additional filtering beyond organizational aggregation")
        
        # Audit Report browser
        from .report_tabs import render_report_type_browser
        render_report_type_browser(audit_reports, analysis, "Audit Report", "📊")
        
        # PERFORMANCE: Skip cleanup for tab-level functions - only needed for large reports
        pass
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        st.error(f"Error analyzing Audit Reports: {str(e)}")
        with st.expander("Debug Information", expanded=False):
            st.code(error_details)


@st.cache_data(ttl=1800, max_entries=1000)  # 30-minute TTL for report rendering
def _render_cached_audit_report_content(report_id, report_name, population_refs_count, criteria_count):
    """Cache expensive audit report rendering operations using cache_manager"""
    from ...utils.caching.cache_manager import cache_manager
    
    # Generate hash for cache invalidation
    report_hash = cache_manager.generate_report_hash(report_id, {
        'report_name': report_name,
        'population_refs_count': population_refs_count,
        'criteria_count': criteria_count
    })
    
    # Default aggregation config hash
    aggregation_config = cache_manager.generate_data_hash({
        'population_refs': population_refs_count,
        'criteria': criteria_count
    })
    
    return cache_manager.cache_audit_report_visualization(
        report_id, report_hash, population_refs_count, criteria_count, aggregation_config
    )

    # Clean up any remaining DataFrame memory and manage session state
    try:
        from ...utils.caching.cache_manager import cache_manager
        if 'dataframes_to_cleanup' in locals():
            cache_manager.cleanup_dataframe_memory(dataframes_to_cleanup)
        cache_manager.manage_session_state_memory()
    except:
        pass  # Ignore cleanup errors


def render_audit_report_details(report):
    """
    Render Audit Report specific details with size-adaptive performance optimization.
    
    Args:
        report: The audit report object to display
        
    This function displays audit report details including aggregation configuration,
    member searches, and any additional filtering criteria. Shows organizational
    grouping and population references.
    Uses size-adaptive memory management and batch processing for performance.
    """
    # PERFORMANCE: Get report size for optimization strategy
    report_size = _get_report_size_category(report)
    
    # SIZE-ADAPTIVE: Only do memory cleanup for large reports
    if report_size == "large":
        from ...utils.caching.cache_manager import cache_manager
        cache_manager.manage_session_state_memory(max_cache_items=15)
        gc.collect()
    # SNOMED cache is now handled by cache_manager in tab_helpers
    
    # Use caching for expensive report rendering operations
    pop_refs_count = len(report.population_references) if hasattr(report, 'population_references') and report.population_references else 0
    criteria_count = len(report.criteria_groups) if hasattr(report, 'criteria_groups') and report.criteria_groups else 0
    _render_cached_audit_report_content(report.id, report.name, pop_refs_count, criteria_count)
    
    
    # Helper function to resolve population GUIDs to search names
    def get_member_search_names(report, analysis):
        """Resolve population GUIDs to meaningful search names"""
        if not hasattr(report, 'population_references') or not report.population_references:
            return []
        
        member_searches = []
        for pop_guid in report.population_references:
            # Find the search by GUID
            search_report = next((r for r in analysis.reports if r.id == pop_guid), None)
            if search_report:
                member_searches.append(search_report.name)
            else:
                member_searches.append(f"Search {pop_guid[:8]}...")  # Fallback to shortened GUID
        
        return member_searches
    
    # Get analysis from session state for resolving names
    analysis = st.session_state.get('search_analysis')
    
    # Aggregation Configuration Section
    st.markdown("### 📊 Aggregation Configuration")
    
    if hasattr(report, 'custom_aggregate') and report.custom_aggregate:
        agg = report.custom_aggregate
        
        col1, col2 = st.columns(2)
        with col1:
            logical_table = agg.get('logical_table', 'N/A')
            st.markdown(f"**Logical Table:** {logical_table}")
            result = agg.get('result', {})
            result_source = result.get('source', 'N/A')
            calculation_type = result.get('calculation_type', 'N/A')
            
            # Capitalize first letter but preserve special cases like 'N/A'
            if result_source and result_source != 'N/A':
                result_source = result_source.capitalize()
            if calculation_type and calculation_type != 'N/A':
                calculation_type = calculation_type.capitalize()
                
            st.markdown(f"**Result Source:** {result_source}")
            st.markdown(f"**Calculation Type:** {calculation_type}")
        
        with col2:
            # Show member search count
            pop_count = len(report.population_references) if hasattr(report, 'population_references') else 0
            st.markdown(f"**Member Searches:** {pop_count}")
            
            # Show if it has additional criteria
            has_criteria = hasattr(report, 'criteria_groups') and report.criteria_groups
            criteria_type = "Complex (with additional criteria)" if has_criteria else "Simple (organizational only)"
            st.markdown(f"**Type:** {criteria_type}")
        
        # Dynamic Grouping Section
        groups = agg.get('groups', [])
        if groups:
            group_columns = []
            for group in groups:
                group_name = group.get('display_name', 'Unnamed')
                # Use display name if available, otherwise fall back to column name
                if group_name and group_name != 'Unnamed':
                    group_columns.append(group_name)
                else:
                    grouping_cols = group.get('grouping_column', [])
                    if isinstance(grouping_cols, str):
                        grouping_cols = [grouping_cols]
                    group_columns.extend(grouping_cols)
            
            # Determine grouping type for dynamic title
            grouping_type = "Data Grouping"  # Default fallback
            if group_columns:
                # Check for common patterns to determine grouping type
                columns_str = ' '.join(group_columns).lower()
                if any(term in columns_str for term in ['practice', 'organization', 'organisation', 'ccg', 'gp']):
                    grouping_type = "Organizational Grouping"
                elif any(term in columns_str for term in ['age', 'birth', 'dob']):
                    grouping_type = "Age Group Analysis"
                elif any(term in columns_str for term in ['medication', 'drug', 'prescription']):
                    grouping_type = "Medication Grouping"
                elif any(term in columns_str for term in ['clinical', 'diagnosis', 'condition', 'snomed']):
                    grouping_type = "Clinical Code Grouping"
                elif any(term in columns_str for term in ['gender', 'sex']):
                    grouping_type = "Demographic Grouping"
                elif any(term in columns_str for term in ['date', 'time', 'year', 'month']):
                    grouping_type = "Temporal Grouping"
            
            st.markdown(f"### 📋 {grouping_type}")
            st.info(f"Results grouped by: {', '.join(group_columns)}")
    else:
        st.info("No aggregation configuration found")
    
    # Member Searches Section (NEW - key feature for Audit Reports)
    if analysis:
        member_searches = get_member_search_names(report, analysis)
        if member_searches:
            st.markdown(f"### 🧑‍🤝‍🧑 Member Searches ({len(member_searches)} searches)")
            st.info("This Audit Report combines results from the following base searches:")
            
            with st.expander("📋 View All Member Searches", expanded=False):
                for i, search_name in enumerate(member_searches, 1):
                    st.markdown(f"{i}. **{search_name}**")
            
            st.caption("Each base search defines a patient population. The Audit Report shows aggregated results across all these populations.")
    
    # Additional Criteria Section (for non-PATIENTS table reports)
    if hasattr(report, 'criteria_groups') and report.criteria_groups:
        st.markdown("### 🔍 Additional Report Criteria")
        st.info(f"This Audit Report applies {len(report.criteria_groups)} additional filtering rule(s) across all member searches.")
        
        # Use the same detailed criteria rendering as List Reports
        for i, group in enumerate(report.criteria_groups, 1):
            rule_name = f"Additional Filter {i}"
            
            with st.expander(f"🔍 {rule_name} ({group.member_operator} Logic, {len(group.criteria)} criteria)", expanded=False):
                st.markdown(f"**Logic:** {group.member_operator}")
                st.markdown(f"**Action if True:** {group.action_if_true}")
                st.markdown(f"**Action if False:** {group.action_if_false}")
                
                if group.criteria:
                    st.markdown("**Criteria Details:**")
                    for j, criterion in enumerate(group.criteria, 1):
                        st.markdown(f"**Criterion {j}: {criterion.display_name}** ({criterion.table})")
                        if criterion.description:
                            st.markdown(f"_{criterion.description}_")
                        
                        # Value sets section (same format as List Reports)
                        value_sets = criterion.value_sets or []
                        total_codes = sum(len(vs.get('values', [])) for vs in value_sets) if value_sets else 0
                        if value_sets:
                            with st.expander(f"🏥 Value Set {j} ({total_codes} codes)", expanded=False):
                                for vs_idx, value_set in enumerate(value_sets, 1):
                                    code_system = value_set.get('code_system', 'Unknown')
                                    
                                    # Transform internal code system names to user-friendly labels
                                    if 'SNOMED_CONCEPT' in code_system:
                                        system_display = "SNOMED Clinical Terminology"
                                    elif 'SCT_DRGGRP' in code_system:
                                        system_display = "Drug Group Classification"
                                    elif 'EMISINTERNAL' in code_system:
                                        system_display = "EMIS Internal Classifications"
                                    else:
                                        system_display = code_system
                                    
                                    st.markdown(f"**System:** {system_display}")
                                    
                                    # Display codes using same format as List Reports
                                    codes = value_set.get('values', [])
                                    if codes:
                                        import pandas as pd
                                        
                                        # Prepare data for dataframe display
                                        code_data = []
                                        for code in codes:
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
                                        
                                        # Create dataframe with same styling as List Reports
                                        codes_df = pd.DataFrame(code_data)
                                        dataframes_to_cleanup = [codes_df]  # Track for cleanup
                                        
                                        try:
                                            # Display as scrollable table
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
                                            # CRITICAL: Immediate cleanup of DataFrame memory
                                            cache_manager.cleanup_dataframe_memory(dataframes_to_cleanup)
                                            del codes_df
                                            del code_data
                                            gc.collect()
                        
                        # Filter criteria section (same format as List Reports)
                        st.markdown("**⚙️ Filters:**")
                        column_filters = criterion.column_filters or []
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
                                elif 'AUTHOR' in filter_column or 'USER' in filter_column:
                                    st.caption(f"• User authorization: Active users only")
                                else:
                                    # Standard clinical code filter with count
                                    if total_codes > 0:
                                        st.caption(f"• Include {total_codes} specified clinical codes")
                                    else:
                                        st.caption(f"• Include specified clinical codes")
                        
                        # Record ordering and restrictions
                        restrictions = criterion.restrictions or []
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
                        
                        if j < len(group.criteria):  # Add separator if not last criterion
                            st.markdown("---")
    
    elif hasattr(report, 'custom_aggregate') and report.custom_aggregate:
        logical_table = report.custom_aggregate.get('logical_table', '')
        if logical_table == 'PATIENTS':
            st.markdown("### ℹ️ Simple Organizational Report")
            st.info("This Audit Report performs pure organizational aggregation without additional clinical criteria.")
        else:
            st.markdown("### ℹ️ No Additional Criteria")
            st.info(f"This Audit Report uses the {logical_table} table but does not apply additional filtering criteria.")
    
    # SIZE-ADAPTIVE: Final cleanup based on report size
    if report_size == "large":
        gc.collect()  # Only for large reports
    # Small/medium reports: no final cleanup for better performance


def render_report_type_browser(reports, analysis, report_type_name, icon):
    """
    Generic report type browser for dedicated report tabs with memory management.
    
    Args:
        reports: List of reports to browse
        analysis: Analysis data containing folder information
        report_type_name: Name of the report type (e.g., "List Report")
        icon: Icon to display for this report type
        
    This function provides a standardized browser interface for any report type,
    with folder filtering and report selection capabilities. Uses an efficient
    side-by-side layout similar to the Search Analysis tab.
    Includes comprehensive memory management to prevent session state bloat.
    """
    # PERFORMANCE: Minimal upfront memory management
    from ...utils.caching.cache_manager import cache_manager
    from ...core.report_classifier import ReportClassifier
    
    if not reports:
        st.info(f"{icon} No {report_type_name}s found in this XML file")
        return
    
    # Initialize session state for tracking rendering completion
    rendering_state_key = f"{report_type_name.lower().replace(' ', '_')}_rendering_complete"
    if rendering_state_key not in st.session_state:
        st.session_state[rendering_state_key] = False
    
    # Efficient side-by-side layout like Search Analysis tab
    st.markdown("---")
    
    # Use columns for folder selection, report selection, and export buttons
    col1, col2, col3 = st.columns([3, 4, 0.8])
    
    with col1:
        if analysis.folders:
            folder_options = ["All Folders"] + [f.name for f in analysis.folders]
            
            selected_folder_name = st.selectbox(
                "📁 Select Folder",
                folder_options,
                key=f"{report_type_name.lower().replace(' ', '_')}_folder_browser"
            )
        else:
            # No folders - show message like Rule Logic Browser
            report_type_plural = f"{report_type_name}s"
            st.selectbox(
                "📁 Select Folder",
                [f"All {report_type_plural} (No Folders)"],
                disabled=True,
                key=f"{report_type_name.lower().replace(' ', '_')}_folder_none"
            )
            selected_folder_name = f"All {report_type_plural} (No Folders)"
    
    # Filter reports by folder
    selected_folder = None
    if analysis.folders and selected_folder_name not in ["All Folders", f"All {report_type_name}s (No Folders)"]:
        selected_folder = next((f for f in analysis.folders if f.name == selected_folder_name), None)
    
    if selected_folder:
        folder_reports = [r for r in reports if r.folder_id == selected_folder.id]
    else:
        folder_reports = reports
    
    # Process all reports in folder - no artificial limits
    
    # Create report selection options (limited for performance)
    report_options = []
    for report in folder_reports:
        option_text = report.name
        report_options.append((option_text, report))
    
    # Sort by name
    report_options.sort(key=lambda x: x[1].name)
    
    with col2:
        if report_options:
            # Check if we have a previously selected report text to maintain after refresh
            stored_selection = st.session_state.get(f'selected_{report_type_name}_text')
            option_texts = [option[0] for option in report_options]
            
            # Use stored selection as index if it exists and is valid
            default_index = 0
            if stored_selection and stored_selection in option_texts:
                default_index = option_texts.index(stored_selection)
            
            selected_report_text = st.selectbox(
                f"📋 Select {report_type_name}",
                option_texts,
                index=default_index,
                key=f"{report_type_name.lower().replace(' ', '_')}_selection"
            )
        else:
            st.selectbox(
                f"📋 Select {report_type_name}",
                ["No reports in selected folder"],
                disabled=True,
                key=f"{report_type_name.lower().replace(' ', '_')}_selection_empty"
            )
            selected_report_text = None
    
    # Determine selected report for export buttons (ONLY DO THIS ONCE!)
    selected_report = None
    if selected_report_text and report_options:
        selected_report = next((option[1] for option in report_options if option[0] == selected_report_text), None)
        
        # Cache the found report to avoid duplicate lookup later
        st.session_state[f'cached_selected_report_{report_type_name}'] = selected_report
        
        # Reset rendering state when a new report is selected
        current_selected_id = selected_report.id if selected_report else None
        previous_selected_id = st.session_state.get(f'previous_selected_{report_type_name}_id')
        if current_selected_id != previous_selected_id:
            st.session_state[rendering_state_key] = False
            st.session_state[f'{rendering_state_key}_updated'] = False
            st.session_state[f'previous_selected_{report_type_name}_id'] = current_selected_id
        
        # Also store the selected report text to handle refresh scenarios
        st.session_state[f'selected_{report_type_name}_text'] = selected_report_text
    
    with col3:
        # Export buttons aligned with dropdowns
        # Add spacing to align with selectbox height
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Placeholder for export buttons - will render after report visualization
        export_placeholder = st.empty()
    
    # Display analysis status with rendering status indicator
    status_col1, status_col2 = st.columns([7, 0.8])  # Match dropdown column widths
    
    with status_col1:
        if selected_folder:
            st.info(f"📂 Showing {len(folder_reports)} {report_type_name}s from folder: **{selected_folder.name}**")
        elif analysis.folders:
            st.info(f"{icon} Showing all {len(folder_reports)} {report_type_name}s from all folders")
        else:
            st.info(f"{icon} Showing all {len(folder_reports)} {report_type_name}s (no folder organization)")
    
    with status_col2:
        # Rendering status indicator - will be populated after export buttons render
        status_placeholder = st.empty()
    
    if not folder_reports:
        st.warning(f"No {report_type_name}s found in the selected scope.")
        return
    
    if selected_report_text:
        # Get the selected report from current dropdown selection (not cache to avoid sync issues)
        selected_report = st.session_state.get(f'cached_selected_report_{report_type_name}')
        
        # Verify the cached report matches current selection to prevent sync issues
        if selected_report and selected_report.name == selected_report_text:
            # Cache is correct - use cached report
            pass
        else:
            # Cache is out of sync - re-lookup the correct report
            selected_report = next((option[1] for option in report_options if option[0] == selected_report_text), None)
            if selected_report:
                # Update cache with correct report
                st.session_state[f'cached_selected_report_{report_type_name}'] = selected_report
        
        if selected_report:
            # Use the original detailed rendering with memory monitoring
            try:
                # Import here to avoid circular import
                from .report_tabs import render_report_visualization
                render_report_visualization(selected_report, analysis)
                
                # Mark rendering as complete after visualization finishes
                st.session_state[rendering_state_key] = True
            finally:
                # REFINED: Skip cleanup for better performance
                pass
            
            # Now render export buttons after report is complete
            with export_placeholder.container():
                export_col1, export_col2 = st.columns(2)
                
                with export_col1:
                    # Cached Excel export to prevent regeneration
                    excel_cache_key = f"excel_export_cache_{selected_report.id}"
                    
                    # Only generate if not already cached
                    if excel_cache_key not in st.session_state:
                        try:
                            from ...export_handlers.report_export import ReportExportHandler
                            export_handler = ReportExportHandler(analysis)
                            filename, content = export_handler.generate_report_export(selected_report)
                            
                            # Cache the export data
                            st.session_state[excel_cache_key] = {
                                'filename': filename,
                                'content': content
                            }
                            
                            # Clean up handler
                            del export_handler
                            
                        except Exception as e:
                            st.session_state[excel_cache_key] = {'error': str(e)}
                    
                    # Show download button or error using centralized export manager
                    cached_data = st.session_state[excel_cache_key]
                    from ...export_handlers.ui_export_manager import UIExportManager
                    export_manager = UIExportManager()
                    export_manager.render_cached_excel_download(cached_data, selected_report.name, selected_report.id)
                
                with export_col2:
                    # Cached JSON export to prevent regeneration
                    json_cache_key = f"json_export_cache_{selected_report.id}"
                    
                    # Only generate if not already cached
                    if json_cache_key not in st.session_state:
                        try:
                            xml_filename = st.session_state.get('xml_filename', 'unknown.xml')
                            from ...export_handlers.report_json_export_generator import ReportJSONExportGenerator
                            json_generator = ReportJSONExportGenerator(analysis)
                            json_filename, json_content = json_generator.generate_report_json(selected_report, xml_filename)
                            
                            # Cache the export data
                            st.session_state[json_cache_key] = {
                                'filename': json_filename,
                                'content': json_content
                            }
                            
                            # Clean up generator
                            del json_generator
                            
                        except Exception as e:
                            st.session_state[json_cache_key] = {'error': str(e)}
                    
                    # Show download button or error
                    cached_data = st.session_state[json_cache_key]
                    from ...export_handlers.ui_export_manager import UIExportManager
                    export_manager = UIExportManager()
                    export_manager.render_cached_json_download(cached_data, selected_report.name, selected_report.id)
            
            # Update status indicator now that export buttons are ready
            with status_placeholder.container():
                st.success("✅ Rendering Complete")
                
        else:
            # Show disabled buttons when no report selected
            with export_placeholder.container():
                export_col1, export_col2 = st.columns(2)
                
                with export_col1:
                    st.button(
                        "📊 Excel",
                        disabled=True,
                        help=f"Select a {report_type_name.lower()} to export to Excel",
                        key="export_excel_nav_no_report"
                    )
                
                with export_col2:
                    st.button(
                        "📋 JSON",
                        disabled=True,
                        help=f"Select a {report_type_name.lower()} to export to JSON",
                        key="export_json_nav_no_report"
                    )
            
            # Show blank status when no report selected
            with status_placeholder.container():
                st.empty()