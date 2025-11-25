import streamlit as st
import pandas as pd
import io
from datetime import datetime
import json
from ..core.session_state import SessionStateKeys
from .ui_helpers import (
from .theme import info_box, success_box, warning_box, error_box
    render_section_with_data, 
    render_metrics_row, 
    render_success_rate_metric,
    get_success_highlighting_function,
    get_warning_highlighting_function,
    create_expandable_sections,
    render_info_section
)
from ..core import ReportClassifier, FolderManager, SearchManager
from ..export_handlers.report_export import ReportExportHandler
from ..core.translator import translate_emis_to_snomed
from ..utils.lookup import get_optimized_lookup_cache
from .tabs import (
    render_summary_tab,
    render_clinical_codes_tab,
    render_medications_tab,
    render_refsets_tab,
    render_pseudo_refsets_tab,
    render_pseudo_refset_members_tab,
    render_search_analysis_tab,
    render_list_reports_tab,
    render_audit_reports_tab,
    render_aggregate_reports_tab,
    render_folder_structure_tab,
    render_dependencies_tab,
    render_detailed_rules_tab,
    render_reports_tab
)


def render_results_tabs(results):
    """Render all result tabs with new 5-tab structure."""
    # Check if we have results OR if we have XML content (for patient demographics filtering XMLs)
    # For patient demographics XMLs, results might be empty dict {} but that's still valid
    # Also ensure results are from current file, not stale from previous file
    current_file_info = st.session_state.get(SessionStateKeys.LAST_PROCESSED_FILE, None)
    has_processed_current_file = current_file_info is not None and not st.session_state.get(SessionStateKeys.IS_PROCESSING, False)
    
    has_clinical_results = ('results' in st.session_state and 
                          st.session_state.results is not None and 
                          has_processed_current_file)
    has_xml_content = 'xml_content' in st.session_state and st.session_state.xml_content
    
    # Debug logging
    if st.session_state.get('debug_mode', False):
        print(f"[UI_TABS] results in session_state: {'results' in st.session_state}")
        print(f"[UI_TABS] results value: {type(st.session_state.get('results', None))}")
        print(f"[UI_TABS] has_processed_current_file: {has_processed_current_file}")
        print(f"[UI_TABS] has_clinical_results: {has_clinical_results}")
        print(f"[UI_TABS] current_file_info: {current_file_info}")
    
    # Only show tabs if we have processed results from the current file
    # Don't show tabs just because we have XML content - wait until processing is complete
    if has_clinical_results:
        results = st.session_state.results if has_clinical_results else {}
        
        # Create new 5-tab main structure
        main_tab1, main_tab2, main_tab3, main_tab4, main_tab5 = st.tabs([
            "🏥 Clinical Codes", 
            "🔍 Search Analysis", 
            "📋 List Reports", 
            "📊 Audit Reports", 
            "📈 Aggregate Reports"
        ])
        
        with main_tab1:
            render_clinical_codes_main_tab(results)
        
        with main_tab2:
            xml_content = getattr(st.session_state, 'xml_content', None)
            xml_filename = getattr(st.session_state, 'xml_filename', 'unknown.xml')
            render_search_analysis_tab(xml_content, xml_filename)
        
        with main_tab3:
            xml_content = getattr(st.session_state, 'xml_content', None)
            xml_filename = getattr(st.session_state, 'xml_filename', 'unknown.xml')
            render_list_reports_tab(xml_content, xml_filename)
        
        with main_tab4:
            xml_content = getattr(st.session_state, 'xml_content', None)
            xml_filename = getattr(st.session_state, 'xml_filename', 'unknown.xml')
            render_audit_reports_tab(xml_content, xml_filename)
        
        with main_tab5:
            xml_content = getattr(st.session_state, 'xml_content', None)
            xml_filename = getattr(st.session_state, 'xml_filename', 'unknown.xml')
            render_aggregate_reports_tab(xml_content, xml_filename)
    else:
        # Get dynamic MKB version text from session state
        version_info = st.session_state.get(SessionStateKeys.LOOKUP_VERSION_INFO, {})
        mkb_version = version_info.get('emis_version', 'the latest MKB lookup table')
        if mkb_version != 'the latest MKB lookup table':
            mkb_text = f"MKB {mkb_version}"
        else:
            mkb_text = mkb_version
        
        st.markdown(f"""
        <div style="
            background-color: var(--info-color);
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 0.5rem;
        ">
            Upload EMIS XML files to analyze search logic, visualize report structures, and translate clinical codes to UK SNOMED using {mkb_text}.
        </div>
        """, unsafe_allow_html=True)


def render_clinical_codes_main_tab(results):
    """Render the Clinical Codes main tab (formerly XML Contents)"""
    # Check if we have clinical data or if this is a non-clinical XML (patient demographics filtering, etc.)
    has_clinical_data = results and len(results) > 0
    
    if not has_clinical_data:
        # Handle XMLs with no clinical codes (patient demographics filtering, demographic filters, etc.)
        from .theme import info_box
        st.markdown(info_box("📍 **Non-Clinical XML Detected**"), unsafe_allow_html=True)
        st.markdown("""
        This XML file contains searches or reports without clinical codes. This commonly occurs with:
        - **Patient demographics filtering** (LSOA codes, postcodes, practice areas)
        - **Demographic filtering** (age ranges, gender, registration status)
        - **Administrative searches** (user authorization, practice codes)
        
        ℹ️ **Clinical code analysis is not applicable for this XML type.**
        
        👉 **Use the 'Search Analysis' tab** to view the search logic and filtering criteria.
        """)
        return
    
    # Clinical Codes Configuration
    # Always enable report codes and source tracking - no longer configurable
    st.session_state.clinical_include_report_codes = True
    st.session_state.clinical_show_code_sources = True
    
    # Clinical codes sub-tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Summary", 
        "🏥 Clinical Codes", 
        "💊 Medications", 
        "📋 RefSets", 
        "🔍 Pseudo RefSets"
    ])
    
    with tab1:
        render_summary_tab(results)
    
    with tab2:
        render_clinical_codes_tab(results)
    
    with tab3:
        render_medications_tab(results)
    
    with tab4:
        render_refsets_tab(results)
    
    with tab5:
        # Pseudo RefSets sub-tabs
        pseudo_tab1, pseudo_tab2 = st.tabs(["📋 Pseudo RefSets", "🔍 Pseudo RefSet Members"])
        
        with pseudo_tab1:
            render_pseudo_refsets_tab(results)
        
        with pseudo_tab2:
            render_pseudo_refset_members_tab(results)


def render_xml_structure_tabs(xml_content: str, xml_filename: str):
    """Render XML structure analysis with sub-tabs"""
    if not xml_content:
        from .theme import info_box
        st.markdown(info_box("📋 Upload and process an XML file to see XML structure analysis"), unsafe_allow_html=True)
        return
    
    try:
        # EMERGENCY BYPASS: Report tabs should NOT trigger expensive analysis
        # If analysis isn't already cached, show error instead of hanging for 10 minutes
        analysis = st.session_state.get(SessionStateKeys.SEARCH_ANALYSIS) or st.session_state.get(SessionStateKeys.XML_STRUCTURE_ANALYSIS)
        if analysis is None:
            from .theme import error_box
            st.markdown(error_box("⚠️ Analysis not available. Please ensure XML processing completed successfully and try refreshing the page."), unsafe_allow_html=True)
            from .theme import info_box
            st.markdown(info_box("💡 Try switching to the 'Clinical Codes' tab first, then return to this tab."), unsafe_allow_html=True)
            return
        
        if analysis:
            # Notify user of discovered report counts (SKIP expensive type counting to prevent hang)
            folder_count = len(analysis.folders) if analysis.folders else 0
            # PERFORMANCE FIX: Skip expensive get_report_type_counts() that causes hang
            total_items = len(analysis.reports) if analysis.reports else 0
            
            # PERFORMANCE FIX: Simple notification without expensive type classification
            st.toast(f"XML Structure analyzed! {total_items} items across {folder_count} folder{'s' if folder_count != 1 else ''}", icon="🔍")
            from .theme import info_box
            st.markdown(info_box("📊 Individual report type counts available in each dedicated tab to avoid performance issues."), unsafe_allow_html=True)
        
        # Calculate report type counts for metrics
        search_count = 0
        list_count = 0
        audit_count = 0
        aggregate_count = 0
        
        if analysis and analysis.reports:
            # Count different report types
            search_reports = ReportClassifier.filter_searches_only(analysis.reports)
            list_reports = ReportClassifier.filter_list_reports_only(analysis.reports)
            audit_reports = ReportClassifier.filter_audit_reports_only(analysis.reports)
            aggregate_reports = ReportClassifier.filter_aggregate_reports_only(analysis.reports)
            
            search_count = len(search_reports)
            list_count = len(list_reports)
            audit_count = len(audit_reports)
            aggregate_count = len(aggregate_reports)
        
        # Overview metrics for all report types
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        with col1:
            complexity_color = {
                'Basic': '🟢',
                'Moderate': '🟡', 
                'Complex': '🟠',
                'Very Complex': '🔴'
            }
            # Safe access to complexity metrics with fallbacks for both orchestrated and legacy analysis
            complexity_data = getattr(analysis, 'overall_complexity', getattr(analysis, 'complexity_metrics', {}))
            complexity_level = complexity_data.get('complexity_level', 
                               complexity_data.get('classification', 'Basic'))
            complexity_score = complexity_data.get('complexity_score', 'N/A')
            
            st.metric(
                "Complexity", 
                f"{complexity_color.get(complexity_level, '⚪')} {complexity_level}",
                help=f"Score: {complexity_score}"
            )
        
        with col2:
            st.metric(
                "🔍 Searches", 
                search_count,
                help="Population-based search criteria that define patient groups"
            )
        
        with col3:
            st.metric(
                "📋 List Reports", 
                list_count,
                help="Column-based reports displaying patient data"
            )
        
        with col4:
            st.metric(
                "📊 Audit Reports", 
                audit_count,
                help="Organizational aggregation reports for quality monitoring"
            )
        
        with col5:
            st.metric(
                "📈 Aggregate Reports", 
                aggregate_count,
                help="Statistical cross-tabulation and analysis reports"
            )
        
        with col6:
            # Use overall_complexity for orchestrated analysis, fall back to complexity_metrics for legacy
            complexity_data = getattr(analysis, 'overall_complexity', getattr(analysis, 'complexity_metrics', {}))
            st.metric(
                "📁 Folders", 
                complexity_data.get('total_folders', 0),
                help="Organizational folder structure"
            )
        
        # Create sub-tabs for different XML structure views
        if analysis.folders:
            # Complex structure with folders
            struct_tab1, struct_tab2, struct_tab3, struct_tab4 = st.tabs([
                "📁 Folder Structure", 
                "🔧 Rule Logic Browser",
                "🔗 Dependencies",
                "📊 Reports"
            ])
        else:
            # Simple structure without folders
            struct_tab1, struct_tab2, struct_tab3 = st.tabs([
                "🔧 Rule Logic Browser",
                "🔗 Dependencies",
                "📊 Reports"
            ])
        
        if analysis.folders:
            with struct_tab1:
                render_folder_structure_tab(analysis)
            
            with struct_tab2:
                render_detailed_rules_tab(analysis, xml_filename)
            
            with struct_tab3:
                render_dependencies_tab(analysis)
            
            with struct_tab4:
                render_reports_tab(analysis)
        else:
            with struct_tab1:
                render_detailed_rules_tab(analysis, xml_filename)
            
            with struct_tab2:
                render_dependencies_tab(analysis)
            
            with struct_tab3:
                render_reports_tab(analysis)
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        
        # Print detailed error to console for debugging
        print(f"ERROR: XML structure analysis failed")
        print(f"Error: {str(e)}")
        print(f"Full traceback:\n{error_details}")
        
        from .theme import error_box
        st.markdown(error_box(f"Error analyzing XML structure: {str(e)}"), unsafe_allow_html=True)
        with st.expander("Debug Information", expanded=False):
            st.code(error_details)
