"""
Aggregate Report tab rendering functions.

This module handles rendering of the Aggregate Reports tab with dedicated 
browser and analysis functionality. Aggregate Reports provide statistical 
cross-tabulation and analysis with built-in filtering capabilities.

Extracted from report_tabs.py to improve modularity and maintainability.
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
        st.markdown(info_box("📈 Upload and process an XML file to see Aggregate Reports"), unsafe_allow_html=True)
        return
    
    try:

        analysis = st.session_state.get(SessionStateKeys.SEARCH_ANALYSIS) or st.session_state.get(SessionStateKeys.XML_STRUCTURE_ANALYSIS)
        if analysis is None:
            display_generic_error("Analysis not available. Please ensure XML processing completed successfully and try refreshing the page.", "error", "⚠️")
            st.markdown(info_box("💡 Try switching to the 'Clinical Codes' tab first, then return to this tab."), unsafe_allow_html=True)
            return
        
        from ...core.report_classifier import ReportClassifier
        
        # Using pre-processed data - no memory optimization needed
        
        # PERFORMANCE FIX: Use ONLY pre-processed report breakdown to avoid expensive filtering
        report_results = st.session_state.get(SessionStateKeys.REPORT_RESULTS)
        if report_results and hasattr(report_results, 'report_breakdown') and 'aggregate' in report_results.report_breakdown:
            aggregate_reports = report_results.report_breakdown['aggregate']
        else:
            # No pre-processed data available - skip expensive processing
            st.markdown(info_box("📈 No Aggregate Reports found in this XML file."), unsafe_allow_html=True)
            st.caption("This XML contains only searches or other report types.")
            return
        aggregate_count = len(aggregate_reports)
        
        # Only show toast on first load or when data actually changes
        from .tab_helpers import is_data_processing_needed, cache_processed_data
        toast_cache_key = 'aggregate_reports_toast_shown'
        if is_data_processing_needed(toast_cache_key):
            st.toast(f"Found {aggregate_count} Aggregate Report{'s' if aggregate_count != 1 else ''}", icon="📈")
            cache_processed_data(toast_cache_key, True)
        
        if not aggregate_reports:
            st.markdown(info_box("📈 No Aggregate Reports found in this XML file"), unsafe_allow_html=True)
            return

        # 🔧 Aggregate Report Logic Browser - Fragmented expandable frame (prevents full reruns)
        with st.expander("🔧 Aggregate Report Logic Browser", expanded=True):
            @st.fragment
            def aggregate_report_browser_fragment():
                render_report_type_browser(aggregate_reports, analysis, "Aggregate Report", "📈")
            
            aggregate_report_browser_fragment()

        # 📈 Aggregate Reports Analysis - Collapsed expandable frame (not fragmented)
        with st.expander("📈 Aggregate Reports Analysis", expanded=False):
            st.markdown("Aggregate Reports provide statistical cross-tabulation and analysis with built-in filtering capabilities.")
            
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
        
        # PERFORMANCE: Skip cleanup for tab-level functions - only needed for large reports
        pass
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        display_generic_error(f"Error analyzing Aggregate Reports: {str(e)}", "error")
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
        st.markdown(info_box(f"{icon} No {report_type_name}s found in this XML file"), unsafe_allow_html=True)
        return
    
    # Initialize session state for tracking rendering completion
    rendering_state_key = f"{report_type_name.lower().replace(' ', '_')}_rendering_complete"
    if rendering_state_key not in st.session_state:
        st.session_state[rendering_state_key] = False
    
    # Efficient side-by-side layout like Search Analysis tab
    
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
            st.markdown(f"""
            <div style="
                background-color: #28546B;
                padding: 0.75rem;
                border-radius: 0.5rem;
                color: #FAFAFA;
                text-align: left;
                margin-bottom: 0.5rem;
            ">
                {icon} Showing all {len(folder_reports)} {report_type_name}s from all folders
            </div>
            """, unsafe_allow_html=True)
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
                    # Truly lazy Excel export using centralized UIExportManager
                    from ...export_handlers.ui_export_manager import UIExportManager
                    export_manager = UIExportManager(analysis)
                    export_manager.render_lazy_excel_export_button(
                        selected_report, selected_report.name, selected_report.id, "report"
                    )
                
                with export_col2:
                    # Truly lazy JSON export using centralized UIExportManager
                    from ...export_handlers.ui_export_manager import UIExportManager
                    export_manager = UIExportManager(analysis)
                    xml_filename = st.session_state.get(SessionStateKeys.XML_FILENAME, 'unknown.xml')
                    export_manager.render_lazy_json_export_button(
                        selected_report, selected_report.name, selected_report.id, "report", xml_filename
                    )
            
            # Update status indicator now that export buttons are ready
            with status_placeholder.container():
                st.markdown("""
                <div style="
                    background-color: #1F4E3D;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 0.5rem;
                ">
                    ✓&nbsp;&nbsp;Rendering Complete
                </div>
                """, unsafe_allow_html=True)
                
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
    
    # Just show the report name without redundant type prefix (users know the tab they're in)
    st.subheader(f"📊 {metadata['report_name']}")
    
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
                display_generic_error(f"Unknown report type: {report.report_type}", "error")
        else:
            # This is a SearchReport object from search_analyzer - shouldn't be in report visualization
            display_generic_error("SearchReport object passed to report visualization - this indicates a data flow issue", "error", "⚠️")
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


# Import render_list_report_details and render_audit_report_details from parent module for dependency
# These are referenced in render_report_visualization but only for aggregate report dependencies
def render_list_report_details(report):
    """Import from parent module for dependency compatibility."""
    from .list_report_tab import render_list_report_details as parent_render_list_report_details
    return parent_render_list_report_details(report)


def render_audit_report_details(report):
    """Import from parent module for dependency compatibility."""
    from .audit_report_tab import render_audit_report_details as parent_render_audit_report_details
    return parent_render_audit_report_details(report)


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
    
    # Statistical setup in nested bordered container
    if report.statistical_groups:
        with st.container(border=True):
            st.markdown("**📈 Statistical Configuration**")
            
            # Display statistical setup with resolved names
            rows_group = next((g for g in report.statistical_groups if g.get('type') == 'rows'), None)
            cols_group = next((g for g in report.statistical_groups if g.get('type') == 'columns'), None)
            result_group = next((g for g in report.statistical_groups if g.get('type') == 'result'), None)
            
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if rows_group:
                    group_name = rows_group.get('group_name', f"Group {rows_group.get('group_id', 'Unknown')}")
                    st.markdown(f"""
                    <div style="
                        background-color: #28546B;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 0.5rem;
                    ">
                        <strong>Rows:</strong> {group_name}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(warning_box("**Rows:** Not configured"), unsafe_allow_html=True)
            
            with col2:
                if cols_group:
                    group_name = cols_group.get('group_name', f"Group {cols_group.get('group_id', 'Unknown')}")
                    st.markdown(f"""
                    <div style="
                        background-color: #28546B;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 0.5rem;
                    ">
                        <strong>Columns:</strong> {group_name}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(warning_box("**Columns:** Not configured"), unsafe_allow_html=True)
            
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
                    st.markdown(f"""
                    <div style="
                        background-color: #1F4E3D;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 0.5rem;
                    ">
                        <strong>Result:</strong> {result_text}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    display_generic_error("**Result:** Not configured", "error")
    
    # Aggregate groups in collapsed expander (moved below Statistical Setup)
    if report.aggregate_groups:
        with st.expander("📊 Aggregate Groups", expanded=False):
            for i, group in enumerate(report.aggregate_groups, 1):
                with st.expander(f"Group {i}: {group.get('display_name', 'Unnamed')}", expanded=False):
                    st.markdown(f"**Grouping Columns:** {', '.join(group.get('grouping_columns', []))}")
                    st.markdown(f"**Sub Totals:** {'Yes' if group.get('sub_totals', False) else 'No'}")
                    st.markdown(f"**Repeat Header:** {'Yes' if group.get('repeat_header', False) else 'No'}")
    
    # Display built-in criteria if present (enhanced 2025-09-18)
    if hasattr(report, 'aggregate_criteria') and report.aggregate_criteria:
        st.markdown("### 🔍 Built-in Report Filters")
        st.markdown(f"""
        <div style="
            background-color: #5B2758;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 0.5rem;
        ">
            This aggregate report has its own built-in criteria that filters the data before aggregation.
        </div>
        """, unsafe_allow_html=True)
        
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
        st.markdown(info_box("This aggregate report defines its own search criteria (independent of other searches)"), unsafe_allow_html=True)
        render_search_report_details(report)
    
    if not report.aggregate_groups and not report.statistical_groups:
        st.markdown(info_box("No statistical configuration found"), unsafe_allow_html=True)
    
    # SIZE-ADAPTIVE: Final cleanup based on report size
    if report_size == "large":
        gc.collect()  # Only for large reports
    # Small/medium reports: no final cleanup for better performance
