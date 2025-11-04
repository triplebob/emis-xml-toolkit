"""
Report tab rendering functions.

This module handles rendering of all report-related tabs:
- List Reports tab with dedicated browser and analysis
- Audit Reports tab with organizational aggregation analysis  
- Aggregate Reports tab with statistical cross-tabulation
- Reports tab with folder browser and report visualization
- Individual report detail renderers for each report type

All functions maintain compatibility with the existing tab structure
and preserve performance optimizations, error handling, and UI styling.
"""

from .common_imports import *
from .tab_helpers import (
    ensure_analysis_cached
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
    render_download_button,
    get_success_highlighting_function,
    get_warning_highlighting_function,
    create_expandable_sections,
    render_info_section
)

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

def _lookup_snomed_for_ui(emis_guid: str) -> str:
    """Single SNOMED lookup - now uses batch function for consistency"""
    if not emis_guid or emis_guid == 'N/A':
        return 'N/A'
    
    batch_result = _batch_lookup_snomed_for_ui([emis_guid])
    return batch_result.get(emis_guid, 'Not found')



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
        st.info("📋 Upload and process an XML file to see List Reports")
        return
    
    try:
        
        # Use ONLY cached analysis data - never trigger reprocessing
        analysis = st.session_state.get('search_analysis') or st.session_state.get('xml_structure_analysis')
        if not analysis:
            st.error("⚠️ Analysis data not available. Please ensure XML processing completed successfully.")
            st.info("💡 Try refreshing the page or uploading your XML file again.")
            return
        
        from ...core.report_classifier import ReportClassifier
        
        # Using pre-processed data - no memory optimization needed
        
        # PERFORMANCE FIX: Use ONLY pre-processed report breakdown to avoid expensive filtering
        report_results = st.session_state.get('report_results')
        
        if report_results and hasattr(report_results, 'report_breakdown') and 'list' in report_results.report_breakdown:
            list_reports = report_results.report_breakdown['list']
        else:
            st.info("📋 No List Reports found in this XML file.")
            st.caption("This XML contains only searches or other report types.")
            return
        
        from ...core.report_classifier import ReportClassifier
        
        # PERFORMANCE FIX: Use ONLY pre-processed report breakdown to avoid expensive filtering
        report_results = st.session_state.get('report_results')
        
        if report_results and hasattr(report_results, 'report_breakdown') and 'list' in report_results.report_breakdown:
            list_reports = report_results.report_breakdown['list']
        else:
            # No pre-processed data available - skip expensive processing
            st.info("📋 No List Reports found in this XML file.")
            st.caption("This XML contains only searches or other report types.")
            return
        list_count = len(list_reports)
        
        # Only show toast on first load or when data actually changes
        from .tab_helpers import is_data_processing_needed, cache_processed_data
        toast_cache_key = 'list_reports_toast_shown'
        if is_data_processing_needed(toast_cache_key):
            st.toast(f"Found {list_count} List Report{'s' if list_count != 1 else ''}", icon="📋")
            cache_processed_data(toast_cache_key, True)
        
        st.markdown("### 📋 List Reports Analysis")
        st.markdown("List Reports display patient data in column-based tables with specific data extraction rules.")
        
        if not list_reports:
            st.info("📋 No List Reports found in this XML file")
            return
        
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
        
        # List Report browser
        render_report_type_browser(list_reports, analysis, "List Report", "📋")
        
        # PERFORMANCE: Skip cleanup for tab-level functions - only needed for large reports
        pass
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        st.error(f"Error analyzing List Reports: {str(e)}")
        with st.expander("Debug Information", expanded=False):
            st.code(error_details)


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
        from .tab_helpers import is_data_processing_needed, cache_processed_data
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
            st.metric("👥 Referenced Populations", len(all_populations), help="Total unique base searches referenced by all Audit Reports")
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
        render_report_type_browser(audit_reports, analysis, "Audit Report", "📊")
        
        # PERFORMANCE: Skip cleanup for tab-level functions - only needed for large reports
        pass
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        st.error(f"Error analyzing Audit Reports: {str(e)}")
        with st.expander("Debug Information", expanded=False):
            st.code(error_details)


def render_aggregate_reports_tab(xml_content: str, xml_filename: str):
    """
    Render the Aggregate Reports tab with dedicated Aggregate Report browser and analysis.
    
    Args:
        xml_content: The XML content to analyze
        xml_filename: Name of the XML file being processed
        
    This function displays Aggregate Reports which provide statistical cross-tabulation
    and analysis with built-in filtering capabilities. Shows metrics about statistical
    setup and built-in filters.
    """
    
    if not xml_content:
        st.info("📈 Upload and process an XML file to see Aggregate Reports")
        return
    
    try:

        analysis = st.session_state.get('search_analysis') or st.session_state.get('xml_structure_analysis')
        if analysis is None:
            st.error("⚠️ Analysis not available. Please ensure XML processing completed successfully and try refreshing the page.")
            st.info("💡 Try switching to the 'Clinical Codes' tab first, then return to this tab.")
            return
        
        from ...core.report_classifier import ReportClassifier
        
        # Using pre-processed data - no memory optimization needed
        
        # PERFORMANCE FIX: Use ONLY pre-processed report breakdown to avoid expensive filtering
        report_results = st.session_state.get('report_results')
        if report_results and hasattr(report_results, 'report_breakdown') and 'aggregate' in report_results.report_breakdown:
            aggregate_reports = report_results.report_breakdown['aggregate']
        else:
            # No pre-processed data available - skip expensive processing
            st.info("📈 No Aggregate Reports found in this XML file.")
            st.caption("This XML contains only searches or other report types.")
            return
        aggregate_count = len(aggregate_reports)
        
        # Only show toast on first load or when data actually changes
        from .tab_helpers import is_data_processing_needed, cache_processed_data
        toast_cache_key = 'aggregate_reports_toast_shown'
        if is_data_processing_needed(toast_cache_key):
            st.toast(f"Found {aggregate_count} Aggregate Report{'s' if aggregate_count != 1 else ''}", icon="📈")
            cache_processed_data(toast_cache_key, True)
        
        st.markdown("### 📈 Aggregate Reports Analysis")
        st.markdown("Aggregate Reports provide statistical cross-tabulation and analysis with built-in filtering capabilities.")
        
        if not aggregate_reports:
            st.info("📈 No Aggregate Reports found in this XML file")
            return
        
        # Aggregate Reports metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📈 Aggregate Reports", aggregate_count)
        with col2:
            reports_with_stats = sum(1 for report in aggregate_reports if hasattr(report, 'statistical_groups') and report.statistical_groups)
            st.metric("📊 With Statistical Setup", reports_with_stats)
        with col3:
            reports_with_builtin_filters = sum(1 for report in aggregate_reports if hasattr(report, 'aggregate_criteria') and report.aggregate_criteria)
            st.metric("🔍 With Built-in Filters", reports_with_builtin_filters)
        
        # Aggregate Report browser
        render_report_type_browser(aggregate_reports, analysis, "Aggregate Report", "📈")
        
        # PERFORMANCE: Skip cleanup for tab-level functions - only needed for large reports
        pass
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        st.error(f"Error analyzing Aggregate Reports: {str(e)}")
        with st.expander("Debug Information", expanded=False):
            st.code(error_details)


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
                render_report_visualization(selected_report, analysis)
                
                # Mark rendering as complete after visualization finishes
                st.session_state[rendering_state_key] = True
            finally:
                # REFINED: Skip cleanup for better performance
                # gc.collect() - removed to speed up small reports
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
                    
                    # Show download button or error
                    cached_data = st.session_state[excel_cache_key]
                    if 'error' in cached_data:
                        st.button(
                            "📊 Excel",
                            disabled=True,
                            help=f"Excel export error: {cached_data['error']}",
                            key=f"export_excel_error_{selected_report.id}"
                        )
                    else:
                        st.download_button(
                            label="📊 Excel",
                            data=cached_data['content'],
                            file_name=cached_data['filename'],
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            help=f"Download Excel export for: {selected_report.name}",
                            key=f"export_excel_nav_{selected_report.id}"
                        )
                
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
                    if 'error' in cached_data:
                        st.button(
                            "📋 JSON",
                            disabled=True,
                            help=f"JSON export error: {cached_data['error']}",
                            key=f"export_json_error_{selected_report.id}"
                        )
                    else:
                        st.download_button(
                            label="📋 JSON",
                            data=cached_data['content'],
                            file_name=cached_data['filename'],
                            mime="application/json",
                            help=f"Download JSON export for: {selected_report.name}",
                            key=f"export_json_nav_{selected_report.id}"
                        )
            
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


def render_reports_tab(analysis):
    """
    Render reports sub-tab with folder browser and report visualization.
    
    Args:
        analysis: Analysis data containing reports and folders
        
    This function provides a comprehensive report browser that shows all report types
    with folder-based navigation and type filtering. Includes export functionality
    and detailed visualization for selected reports.
    """
    
    if not analysis or not analysis.reports:
        st.info("📋 No reports found in this XML file")
        return
    
    # Import here to avoid circular imports
    from ...core.report_classifier import ReportClassifier
    from ...export_handlers.search_export import SearchExportHandler
    
    st.markdown("**📊 EMIS Report Explorer**")
    st.markdown("Browse and visualize all report types: Search, List, Audit, and Aggregate reports.")
    
    # PERFORMANCE FIX: Skip expensive report type counting to prevent hang
    # Show simple total count instead of per-type breakdown
    total_reports = len(analysis.reports) if analysis.reports else 0
    
    # Overview metrics (simplified to avoid expensive classification)
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📊 Total Reports", total_reports)
    with col2:
        folder_count = len(analysis.folders) if analysis.folders else 0
        st.metric("📁 Folders", folder_count)
        
    st.info("💡 Use individual report tabs (List Reports, Audit Reports, Aggregate Reports) for type-specific counts.")
    
    # Folder browser section
    st.markdown("---")
    
    # Folder selection (if folders exist)
    selected_folder = None
    if analysis.folders:
        st.subheader("📁 Browse by Folder")
        
        # Create folder options
        folder_options = ["All Folders"] + [f.name for f in analysis.folders]
        selected_folder_name = st.selectbox(
            "Select folder to view reports:",
            folder_options,
            key="reports_folder_browser"
        )
        
        if selected_folder_name != "All Folders":
            # Find the selected folder
            selected_folder = next((f for f in analysis.folders if f.name == selected_folder_name), None)
    
    # Filter reports based on selected folder
    if selected_folder:
        # Get reports in the selected folder
        folder_reports = [r for r in analysis.reports if r.folder_id == selected_folder.id]
        st.info(f"📂 Showing {len(folder_reports)} reports from folder: **{selected_folder.name}**")
    else:
        folder_reports = analysis.reports
        if analysis.folders:
            st.info(f"📊 Showing all {len(folder_reports)} reports from all folders")
        else:
            st.info(f"📊 Showing all {len(folder_reports)} reports")
    
    if not folder_reports:
        st.warning("No reports found in the selected scope.")
        return
    
    # Report type filter
    st.subheader("🔍 Filter by Report Type")
    
    report_types = ["All Types", "[Search]", "[List Report]", "[Audit Report]", "[Aggregate Report]"]
    selected_type = st.selectbox(
        "Filter by report type:",
        report_types,
        key="reports_type_filter"
    )
    
    # PERFORMANCE FIX: Apply type filter using pre-computed data instead of expensive classification
    if selected_type == "All Types":
        filtered_reports = folder_reports
    else:
        # Simple, fast filtering without expensive ReportClassifier operations
        filtered_reports = []
        for report in folder_reports:
            # Use simple heuristics instead of expensive classification
            if selected_type == "[Search]" and (not hasattr(report, 'list_report') and not hasattr(report, 'audit_report') and not hasattr(report, 'aggregate_report')):
                filtered_reports.append(report)
            elif selected_type == "[List Report]" and (hasattr(report, 'list_report') or 'listReport' in str(type(report))):
                filtered_reports.append(report)
            elif selected_type == "[Audit Report]" and (hasattr(report, 'audit_report') or 'auditReport' in str(type(report))):
                filtered_reports.append(report)
            elif selected_type == "[Aggregate Report]" and (hasattr(report, 'aggregate_report') or 'aggregateReport' in str(type(report))):
                filtered_reports.append(report)
    
    st.info(f"🎯 Found {len(filtered_reports)} reports matching your criteria")
    
    # Report selection and visualization with progressive loading
    if filtered_reports:
        st.subheader("📋 Select Report to Visualize")
        
        # Progressive loading for large report lists
        from .tab_helpers import paginate_reports, render_pagination_controls, filter_reports_with_search
        
        # Add search functionality for large lists
        if len(filtered_reports) > 10:
            search_term = st.text_input(
                "🔍 Search reports by name or type:",
                key="report_search",
                help="Filter reports to find specific ones quickly"
            )
            filtered_reports = filter_reports_with_search(filtered_reports, search_term)
            st.caption(f"Showing {len(filtered_reports)} reports")
        
        # Pagination for very large lists
        page_size = 20 if len(filtered_reports) > 50 else len(filtered_reports)
        current_page_reports, total_pages, current_page = paginate_reports(
            filtered_reports, page_size, "reports_page"
        )
        
        if total_pages > 1:
            st.caption(f"Page {current_page} of {total_pages} ({page_size} reports per page)")
            render_pagination_controls(total_pages, current_page, "reports_page")
        
        # Create report selection options for current page only
        from ...utils.caching.cache_manager import cache_manager
        from .tab_helpers import classify_report_type_cached
        
        report_options = []
        for report in current_page_reports:
            # Generate structure hash for cache invalidation
            structure_hash = cache_manager.generate_data_hash({
                'report_name': report.name,
                'report_type': getattr(report, 'report_type', None),
                'has_columns': hasattr(report, 'column_groups'),
                'has_aggregation': hasattr(report, 'aggregate_groups')
            })
            
            # Use cached classification from tab_helpers
            report_type = classify_report_type_cached(report.id, structure_hash)
            clean_type = report_type.strip('[]')
            option_text = f"{clean_type}: {report.name}"
            report_options.append((option_text, report))
        
        # Sort options by type then name
        report_options.sort(key=lambda x: (x[1].report_type or 'search', x[1].name))
        
        selected_report_text = st.selectbox(
            "Choose a report to view details:",
            [option[0] for option in report_options] if report_options else ["No reports on this page"],
            key="reports_selection",
            disabled=not report_options
        )
        
        if selected_report_text:
            # Find the selected report
            selected_report = next((option[1] for option in report_options if option[0] == selected_report_text), None)
            
            if selected_report:
                # Render the selected report visualization
                render_report_visualization(selected_report, analysis)


def _get_cached_report_visualization_data(report_id, analysis_hash, report_type, report_name, description, parent_info, search_date):
    """Cache report visualization data to make dropdown switching instant using cache_manager"""
    from ...utils.caching.cache_manager import cache_manager
    
    # Use the cache_manager's report metadata caching
    return cache_manager.cache_report_metadata(
        report_id, report_name, report_type or 'unknown', 
        parent_info or '', search_date or '', description or ''
    )

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
        value_sets = criterion.get('value_sets', [])
        for vs in value_sets:
            total_codes += len(vs.get('values', []))
    
    # Only show progress for large code sets
    if total_codes > 50:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        processed_codes = 0
        for criterion_idx, criterion in enumerate(criteria_data):
            value_sets = criterion.get('value_sets', [])
            for vs in value_sets:
                codes = vs.get('values', [])
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

@st.cache_data(show_spinner="Rendering detailed sections...", ttl=1800, max_entries=100)
def _render_detailed_sections(report_id: str, report_hash: str, report_type: str, sections_config: dict):
    """
    Prepare detailed section rendering data with spinner.
    
    Shows spinner only on cache misses.
    Cache hits return instantly.
    """
    return {
        'sections_prepared': True,
        'report_type': report_type,
        'sections_config': sections_config,
        'rendering_ready': True
    }



def render_report_visualization(report, analysis):
    """
    Render detailed visualization for a specific report based on its type with size-optimized performance.
    
    Args:
        report: The report object to visualize
        analysis: Analysis data for context and dependencies
        
    This function provides cached stages with spinners that only show on cache misses.
    Subsequent renders return instantly from cache without showing spinners.
    Uses size-adaptive memory management and performance optimizations.
    """
    # PERFORMANCE: Detect report size for optimization strategy
    report_size = _get_report_size_category(report)
    
    # Cache session state references to avoid repeated lookups
    session_state = st.session_state
    
    # OPTIMIZATION: Skip memory monitoring and cleanup for small reports
    from ...utils.caching.cache_manager import cache_manager
    
    if report_size == "large":
        # Only do expensive memory checks for large reports
        memory_stats = cache_manager.get_memory_usage_stats()
        if memory_stats.get('cleanup_recommended', False):
            st.warning("Memory pressure detected - performing cleanup")
            cache_manager.manage_session_state_memory(max_cache_items=10)
            gc.collect()
    elif report_size == "medium":
        # Light memory management for medium reports
        memory_stats = cache_manager.get_memory_usage_stats()
        if memory_stats.get('cache_memory_pressure') == 'high':
            cache_manager.manage_session_state_memory(max_cache_items=30)
    # Small reports: no upfront memory management
    
    # Generate hash for cache invalidation
    report_hash = cache_manager.generate_report_hash(report.id, {
        'report_name': report.name,
        'report_type': getattr(report, 'report_type', None),
        'has_columns': hasattr(report, 'column_groups'),
        'has_aggregation': hasattr(report, 'aggregate_groups')
    })
    
    # Get parent info for metadata
    def get_parent_search_name(report, analysis):
        if hasattr(report, 'direct_dependencies') and report.direct_dependencies:
            parent_guid = report.direct_dependencies[0]  # First dependency is usually the parent
            # Find the parent report by GUID
            for parent_report in analysis.reports:
                if parent_report.id == parent_guid:
                    return parent_report.name
            return f"Search {parent_guid[:8]}..."  # Fallback to shortened GUID
        return None
    
    parent_info = get_parent_search_name(report, analysis)
    
    # Detect report type
    report_type = getattr(report, 'report_type', None)
    if not report_type:
        # Simple, fast detection without expensive ReportClassifier operations
        if hasattr(report, 'list_report') or 'listReport' in str(type(report)):
            report_type = "[List Report]"
        elif hasattr(report, 'audit_report') or 'auditReport' in str(type(report)):
            report_type = "[Audit Report]"
        elif hasattr(report, 'aggregate_report') or 'aggregateReport' in str(type(report)):
            report_type = "[Aggregate Report]"
        else:
            report_type = "[Search]"
    
    # Create spinner container area (below XML upload, above detailed content)
    st.markdown("---")
    
    # SIZE-ADAPTIVE: Monitor memory usage only for medium/large reports
    initial_memory = _monitor_memory_usage(f"before rendering {report.name}", report_size) if report_size != "small" else 0
    
    # STAGE 1: Load report metadata (with spinner on cache miss)
    metadata = _load_report_metadata(
        report.id,
        report_hash,
        report.name,
        report_type,
        getattr(report, 'description', ''),
        parent_info or '',
        getattr(report, 'search_date', '')
    )
    
    # Format report type for display
    display_type = report_type
    if report_type.startswith("[") and report_type.endswith("]"):
        clean_type = report_type.strip("[]").lower()
        if clean_type in ["list", "audit", "aggregate"]:
            display_type = f"{clean_type.capitalize()} Report:"
        else:
            display_type = f"{clean_type.capitalize()}:"
    
    st.subheader(f"📊 {display_type} {metadata['report_name']}")
    
    # Report header with useful info
    if metadata['description']:
        st.markdown(f"**Description:** {metadata['description']}")
    
    # Parent relationship context
    if metadata['parent_info']:
        st.markdown(f"**Parent Search:** {metadata['parent_info']}")
    elif hasattr(report, 'parent_type'):
        if report.parent_type == 'ACTIVE':
            st.markdown(f"**Population:** All currently registered regular patients")
        elif report.parent_type == 'ALL':
            st.markdown(f"**Population:** All patients (including left and deceased)")
        elif report.parent_type == 'POP':
            st.markdown(f"**Population:** Population-based (filtered)")
        elif hasattr(report, 'parent_guid') and report.parent_guid:
            parent_name = get_parent_search_name(report, analysis)
            if parent_name:
                st.markdown(f"**Parent Search:** {parent_name}")
            else:
                st.markdown(f"**Parent Search:** Custom search ({report.parent_guid[:8]}...)")
        elif report.parent_type:
            st.markdown(f"**Parent Type:** {report.parent_type}")
    
    st.markdown(f"**Search Date:** {metadata['search_date']}")
    
    # STAGE 2: Process column groups (with progress and spinner on cache miss)
    if hasattr(report, 'column_groups') and report.column_groups:
        column_processing = _process_column_groups(
            report.id,
            report_hash,
            report.column_groups
        )
    
    # STAGE 3: Extract clinical codes (with progress and spinner on cache miss)
    criteria_data = []
    if hasattr(report, 'criteria_groups') and report.criteria_groups:
        for group in report.criteria_groups:
            criteria_data.extend(group.criteria if hasattr(group, 'criteria') else [])
    elif hasattr(report, 'column_groups') and report.column_groups:
        for group in report.column_groups:
            if group.get('criteria_details'):
                criteria_data.extend(group['criteria_details'].get('criteria', []))
    
    if criteria_data:
        codes_extraction = _extract_clinical_codes(
            report.id,
            report_hash,
            criteria_data
        )
    
    # STAGE 4: Render detailed sections (with spinner on cache miss)
    sections_config = {
        'has_columns': hasattr(report, 'column_groups'),
        'has_criteria': hasattr(report, 'criteria_groups'),
        'has_aggregation': hasattr(report, 'aggregate_groups')
    }
    
    sections_data = _render_detailed_sections(
        report.id,
        report_hash,
        report_type,
        sections_config
    )
    
    # Type-specific visualization (actual rendering) with memory monitoring
    try:
        if hasattr(report, 'report_type'):
            # This is a Report object from report_analyzer
            if report.report_type == 'search':
                render_search_report_details(report)
            elif report.report_type == 'list':
                render_list_report_details(report)
            elif report.report_type == 'audit':
                render_audit_report_details(report)
            elif report.report_type == 'aggregate':
                render_aggregate_report_details(report)
            else:
                st.error(f"Unknown report type: {report.report_type}")
        else:
            # This is a SearchReport object from search_analyzer - shouldn't be in report visualization
            st.error("⚠️ SearchReport object passed to report visualization - this indicates a data flow issue")
            st.write("Object type:", type(report).__name__)
            if hasattr(report, 'name'):
                st.write("Name:", report.name)
    finally:
        # SIZE-ADAPTIVE: Memory cleanup based on report size
        if report_size == "small":
            # Small reports: minimal cleanup, preserve speed
            pass
        elif report_size == "medium":
            # Medium reports: light cleanup
            if hasattr(report, 'id'):
                cache_manager.clear_export_cache(report.id)
        else:
            # Large reports: comprehensive cleanup
            if hasattr(report, 'id'):
                cache_manager.clear_export_cache(report.id)
            
            # Monitor memory usage after rendering for large reports only
            final_memory = _monitor_memory_usage(f"after rendering {getattr(report, 'name', 'unknown')}", report_size)
            
            # If memory increased significantly, show warning
            if hasattr(locals(), 'initial_memory') and final_memory > initial_memory + 200:
                st.warning(f"Memory increased by {final_memory - initial_memory:.1f} MB during report rendering")
                # Force additional cleanup for large reports only
                cache_manager.manage_session_state_memory(max_cache_items=5)
                gc.collect()



def render_search_report_details(report):
    """
    Render Search Report specific details with size-adaptive performance optimization.
    
    Args:
        report: The search report object to display
        
    This function displays the search criteria groups and their associated
    rules, showing the logical operators and actions for search reports.
    Uses size-adaptive memory management for performance.
    """
    # PERFORMANCE: Get report size for optimization strategy
    report_size = _get_report_size_category(report)
    
    # SIZE-ADAPTIVE: Only do memory cleanup for large reports
    if report_size == "large":
        from ...utils.caching.cache_manager import cache_manager
        cache_manager.manage_session_state_memory(max_cache_items=15)
        gc.collect()
    
    st.markdown("### 🔍 Search Criteria")
    
    if report.criteria_groups:
        for i, group in enumerate(report.criteria_groups, 1):
            with st.expander(f"Rule {i}: {group.member_operator} Logic ({len(group.criteria)} criteria)", expanded=False):
                st.markdown(f"**Logic:** {group.member_operator}")
                st.markdown(f"**Action if True:** {group.action_if_true}")
                st.markdown(f"**Action if False:** {group.action_if_false}")
                
                if group.criteria:
                    st.markdown("**Criteria:**")
                    for j, criterion in enumerate(group.criteria, 1):
                        st.markdown(f"  {j}. **{criterion.display_name}** ({criterion.table})")
                        if criterion.description:
                            st.markdown(f"     _{criterion.description}_")
    else:
        st.info("No search criteria found")
    
    # SIZE-ADAPTIVE: Final cleanup based on report size
    if report_size == "large":
        gc.collect()  # Only for large reports
    # Small/medium reports: no final cleanup for better performance


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
                    st.info("No columns defined")
                
                # Filtering criteria
                st.markdown(f"**Has Criteria:** {'Yes' if group.get('has_criteria', False) else 'No'}")
                
                # Criteria implementation details
                if group.get('has_criteria', False) and group.get('criteria_details'):
                    criteria_details = group['criteria_details']
                    st.markdown("**🔍 Column Group Criteria:**")
                    
                    criteria_count = criteria_details.get('criteria_count', 0)
                    st.info(f"This column group has {criteria_count} filtering criterion that determines which records appear in this column section.")
                    
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
                                                        scope = '👥 + Children'
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
                                                        "🩺 SNOMED Code", 
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
        st.info("No column groups found")
    
    # SIZE-ADAPTIVE: Final cleanup based on report size
    if report_size == "large":
        gc.collect()  # Only for large reports
    # Small/medium reports: no final cleanup for better performance
    
    # Dependencies are now shown in the header as "Parent Search" - no need for separate section



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
            st.markdown(f"### 👥 Member Searches ({len(member_searches)} searches)")
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
                                                    scope = '👥 + Children'
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
                                                        "🩺 SNOMED Code", 
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



@st.cache_data(ttl=1800, max_entries=1000)  # 30-minute TTL for report rendering
def _render_cached_aggregate_report_content(report_id, report_name, aggregate_groups_count, statistical_groups_count):
    """Cache expensive aggregate report rendering operations using cache_manager"""
    from ...utils.caching.cache_manager import cache_manager
    
    # Generate hash for cache invalidation
    report_hash = cache_manager.generate_report_hash(report_id, {
        'report_name': report_name,
        'aggregate_groups_count': aggregate_groups_count,
        'statistical_groups_count': statistical_groups_count
    })
    
    # Cross-tabulation config hash
    cross_tab_config = cache_manager.generate_data_hash({
        'aggregate_groups': aggregate_groups_count,
        'statistical_groups': statistical_groups_count
    })
    
    return cache_manager.cache_aggregate_report_visualization(
        report_id, report_hash, aggregate_groups_count, statistical_groups_count, cross_tab_config
    )

def render_aggregate_report_details(report):
    """
    Render Aggregate Report specific details with size-adaptive performance optimization.
    
    Args:
        report: The aggregate report object to display
        
    This function displays aggregate report details including statistical configuration,
    aggregate groups, and any built-in filtering criteria. Shows cross-tabulation
    setup and data grouping options.
    Uses size-adaptive memory management and batch processing for performance.
    """
    # PERFORMANCE: Get report size for optimization strategy
    report_size = _get_report_size_category(report)
    
    # SIZE-ADAPTIVE: Only do memory cleanup for large reports
    if report_size == "large":
        from ...utils.caching.cache_manager import cache_manager
        cache_manager.manage_session_state_memory(max_cache_items=15)
        gc.collect()
    
    # Cache expensive aggregate report operations
    aggregate_groups_count = len(report.aggregate_groups) if hasattr(report, 'aggregate_groups') and report.aggregate_groups else 0
    statistical_groups_count = len(report.statistical_groups) if hasattr(report, 'statistical_groups') and report.statistical_groups else 0
    _render_cached_aggregate_report_content(report.id, report.name, aggregate_groups_count, statistical_groups_count)
    
    st.markdown("### 📈 Statistical Configuration")
    
    # Aggregate groups
    if report.aggregate_groups:
        st.markdown("#### 📊 Aggregate Groups")
        for i, group in enumerate(report.aggregate_groups, 1):
            with st.expander(f"Group {i}: {group.get('display_name', 'Unnamed')}", expanded=False):
                st.markdown(f"**Grouping Columns:** {', '.join(group.get('grouping_columns', []))}")
                st.markdown(f"**Sub Totals:** {'Yes' if group.get('sub_totals', False) else 'No'}")
                st.markdown(f"**Repeat Header:** {'Yes' if group.get('repeat_header', False) else 'No'}")
    
    # Statistical setup with resolved names (enhanced 2025-09-18)
    if report.statistical_groups:
        st.markdown("#### 📈 Statistical Setup")
        
        # Display statistical setup with resolved names
        rows_group = next((g for g in report.statistical_groups if g.get('type') == 'rows'), None)
        cols_group = next((g for g in report.statistical_groups if g.get('type') == 'columns'), None)
        result_group = next((g for g in report.statistical_groups if g.get('type') == 'result'), None)
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if rows_group:
                group_name = rows_group.get('group_name', f"Group {rows_group.get('group_id', 'Unknown')}")
                st.info(f"**Rows:** {group_name}")
            else:
                st.warning("**Rows:** Not configured")
        
        with col2:
            if cols_group:
                group_name = cols_group.get('group_name', f"Group {cols_group.get('group_id', 'Unknown')}")
                st.info(f"**Columns:** {group_name}")
            else:
                st.warning("**Columns:** Not configured")
        
        with col3:
            if result_group:
                calc_type = result_group.get('calculation_type', 'count')
                source = result_group.get('source', 'record')
                
                # Determine what we're counting based on logical table and criteria
                count_of_what = "Records"  # Default
                
                if hasattr(report, 'logical_table'):
                    logical_table = getattr(report, 'logical_table', '')
                    if logical_table == 'EVENTS':
                        count_of_what = "Clinical Codes"
                    elif logical_table == 'MEDICATION_ISSUES':
                        count_of_what = "Medication Issues"
                    elif logical_table == 'MEDICATION_COURSES':
                        count_of_what = "Medication Courses"
                    elif logical_table == 'PATIENTS':
                        count_of_what = "Patients"
                    elif logical_table:
                        count_of_what = logical_table.replace('_', ' ').title()
                
                # Check if we can get more specific from criteria
                if hasattr(report, 'aggregate_criteria') and report.aggregate_criteria:
                    criteria_groups = report.aggregate_criteria.get('criteria_groups', [])
                    for group in criteria_groups:
                        for criterion in group.get('criteria', []):
                            display_name = criterion.get('display_name', '')
                            if 'Clinical Codes' in display_name:
                                count_of_what = "Clinical Codes"
                            elif 'Medication' in display_name:
                                count_of_what = "Medications"
                            break
                
                result_text = f"{calc_type.title()} of {count_of_what}"
                st.success(f"**Result:** {result_text}")
            else:
                st.error("**Result:** Not configured")
    
    # Display built-in criteria if present (enhanced 2025-09-18)
    if hasattr(report, 'aggregate_criteria') and report.aggregate_criteria:
        st.markdown("### 🔍 Built-in Report Filters")
        st.info("This aggregate report has its own built-in criteria that filters the data before aggregation.")
        
        # Use the same sophisticated rendering as regular searches
        from ...analysis.search_rule_visualizer import render_criteria_group
        from ...analysis.common_structures import CriteriaGroup
        from ...xml_parsers.criterion_parser import SearchCriterion
        
        criteria_data = report.aggregate_criteria
        for i, criteria_group_data in enumerate(criteria_data.get('criteria_groups', [])):
            # Convert the parsed criteria to CriteriaGroup format for rendering
            criteria_objects = []
            for criterion_data in criteria_group_data.get('criteria', []):
                # Create SearchCriterion object with full data
                search_criterion = SearchCriterion(
                    id=criterion_data.get('id', ''),
                    table=criterion_data.get('table', ''),
                    display_name=criterion_data.get('display_name', ''),
                    description=criterion_data.get('description', ''),
                    negation=criterion_data.get('negation', False),
                    column_filters=criterion_data.get('column_filters', []),
                    value_sets=criterion_data.get('value_sets', []),
                    restrictions=criterion_data.get('restrictions', []),
                    linked_criteria=criterion_data.get('linked_criteria', [])
                )
                criteria_objects.append(search_criterion)
            
            # Create CriteriaGroup object
            criteria_group = CriteriaGroup(
                id=criteria_group_data.get('id', ''),
                member_operator=criteria_group_data.get('member_operator', 'AND'),
                action_if_true=criteria_group_data.get('action_if_true', 'SELECT'),
                action_if_false=criteria_group_data.get('action_if_false', 'REJECT'),
                criteria=criteria_objects,
                population_criteria=criteria_group_data.get('population_criteria', [])
            )
            
            # Use the same detailed rendering as searches
            rule_name = f"Built-in Filter {i+1}"
            render_criteria_group(criteria_group, rule_name)
    
    # Include legacy criteria if present  
    elif report.criteria_groups:
        st.markdown("### 🔍 Own Criteria")
        st.info("This aggregate report defines its own search criteria (independent of other searches)")
        render_search_report_details(report)
    
    if not report.aggregate_groups and not report.statistical_groups:
        st.info("No statistical configuration found")
    
    # SIZE-ADAPTIVE: Final cleanup based on report size
    if report_size == "large":
        gc.collect()  # Only for large reports
    # Small/medium reports: no final cleanup for better performance