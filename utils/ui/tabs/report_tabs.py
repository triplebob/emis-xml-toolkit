"""
Core report tab rendering functions.

This module handles rendering of core shared report functionality:
- Report type browser with folder navigation and export capabilities
- Reports tab with folder browser and report visualization  
- Report visualization orchestration and type routing
- Search report detail rendering

Specialized report types are handled by dedicated modules:
- List Reports: list_report_tab.py
- Audit Reports: audit_report_tab.py
- Aggregate Reports: aggregate_report_tab.py
"""

from .common_imports import *
from ...core.session_state import SessionStateKeys
from ...ui.theme import ComponentThemes, info_box, purple_box, success_box, warning_box, error_box
from ...common.ui_error_handling import display_generic_error
from .tab_helpers import (
    ensure_analysis_cached,
    _get_report_size_category,
    _monitor_memory_usage,
    _batch_lookup_snomed_for_ui,
    _lookup_snomed_for_ui,
    _load_report_metadata,
    _extract_clinical_codes,
    _process_column_groups
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

# Import specialized tab modules
from .list_report_tab import render_list_report_details
from .audit_report_tab import render_audit_report_details
from .aggregate_report_tab import render_aggregate_report_details


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
        st.markdown(info_box(f"{icon} No {report_type_name}s found in this XML file"), unsafe_allow_html=True)
        return
    
    # Initialize session state for tracking rendering completion
    rendering_state_key = f"{report_type_name.lower().replace(' ', '_')}_rendering_complete"
    if rendering_state_key not in st.session_state:
        st.session_state[rendering_state_key] = False
    
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
            st.markdown(info_box(f"📂 Showing {len(folder_reports)} {report_type_name}s from folder: **{selected_folder.name}**"), unsafe_allow_html=True)
        elif analysis.folders:
            st.markdown(info_box(f"{icon} Showing all {len(folder_reports)} {report_type_name}s from all folders"), unsafe_allow_html=True)
        else:
            st.markdown(info_box(f"{icon} Showing all {len(folder_reports)} {report_type_name}s (no folder organization)"), unsafe_allow_html=True)
    
    with status_col2:
        # Rendering status indicator - will be populated after export buttons render
        status_placeholder = st.empty()
    
    if not folder_reports:
        st.markdown(warning_box(f"No {report_type_name}s found in the selected scope."), unsafe_allow_html=True)
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
                            xml_filename = st.session_state.get(SessionStateKeys.XML_FILENAME, 'unknown.xml')
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
                st.markdown(success_box("✓&nbsp;&nbsp;Rendering Complete"), unsafe_allow_html=True)
                
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
        st.markdown(info_box("📋 No reports found in this XML file"), unsafe_allow_html=True)
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
        
    st.markdown(info_box("💡 Use individual report tabs (List Reports, Audit Reports, Aggregate Reports) for type-specific counts."), unsafe_allow_html=True)
    

    
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
        st.markdown(info_box(f"📂 Showing {len(folder_reports)} reports from folder: **{selected_folder.name}**"), unsafe_allow_html=True)
    else:
        folder_reports = analysis.reports
        if analysis.folders:
            st.markdown(info_box(f"📊 Showing all {len(folder_reports)} reports from all folders"), unsafe_allow_html=True)
        else:
            st.markdown(info_box(f"📊 Showing all {len(folder_reports)} reports"), unsafe_allow_html=True)
    
    if not folder_reports:
        st.markdown(warning_box("No reports found in the selected scope."), unsafe_allow_html=True)
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
    
    st.markdown(info_box(f"🎯 Found {len(filtered_reports)} reports matching your criteria"), unsafe_allow_html=True)
    
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
            st.markdown(warning_box("Memory pressure detected - performing cleanup"), unsafe_allow_html=True)
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
    
    # Just show the report name without redundant type prefix (users know the tab they're in)
    st.subheader(f"📊 {metadata['report_name']}")
    
    # Report header with useful info
    if metadata['description']:
        with st.container(border=True):
            st.write(metadata['description'])
    
    # Parent relationship context with search date in blue info bar
    parent_col1, parent_col2 = st.columns([4, 2])
    
    with parent_col1:
        if report.parent_type == 'ACTIVE':
            st.markdown(info_box("<strong>Population:</strong> All currently registered regular patients"), unsafe_allow_html=True)
        elif report.parent_type == 'ALL':
            st.markdown(info_box("<strong>Population:</strong> All patients (including left and deceased)"), unsafe_allow_html=True)
        elif report.parent_type == 'POP':
            st.markdown(info_box("<strong>Population:</strong> Population-based (filtered)"), unsafe_allow_html=True)
        elif hasattr(report, 'parent_guid') and report.parent_guid:
            parent_name = get_parent_search_name(report, analysis)
            if parent_name:
                st.markdown(info_box(f"<strong>Parent Search:</strong> {parent_name}"), unsafe_allow_html=True)
            else:
                st.markdown(info_box(f"<strong>Parent Search:</strong> Custom search ({report.parent_guid[:8]}...)"), unsafe_allow_html=True)
        elif report.parent_type:
            st.markdown(info_box(f"<strong>Parent Type:</strong> {report.parent_type}"), unsafe_allow_html=True)
    
    with parent_col2:
        # Simple inline styled element
        st.markdown(purple_box(f"<strong>Search Date:</strong> {metadata['search_date']}"), unsafe_allow_html=True)
 
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
                display_generic_error(f"Unknown report type: {report.report_type}", "error")
        else:
            # This is a SearchReport object from search_analyzer - shouldn't be in report visualization
            display_generic_error("⚠️ SearchReport object passed to report visualization - this indicates a data flow issue", "error")
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
                st.markdown(warning_box(f"Memory increased by {final_memory - initial_memory:.1f} MB during report rendering"), unsafe_allow_html=True)
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
        st.markdown(info_box("No search criteria found"), unsafe_allow_html=True)
    
    # SIZE-ADAPTIVE: Final cleanup based on report size
    if report_size == "large":
        gc.collect()  # Only for large reports
    # Small/medium reports: no final cleanup for better performance
