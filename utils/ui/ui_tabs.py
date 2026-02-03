import streamlit as st
import pandas as pd
import io
from datetime import datetime
import json
from ..system.session_state import SessionStateKeys
from .theme import info_box, success_box, warning_box, error_box
from .tabs import (
    render_summary_tab,
    render_clinical_codes_tab,
    render_medications_tab,
    render_refsets_tab,
    render_pseudo_refsets_tab,
    render_pseudo_refset_members_tab,
    render_analytics_tab,
    render_search_tabs,
    render_xml_tab,
    render_list_reports_tab,
    render_audit_reports_tab,
    render_aggregate_reports_tab,
    render_reports_tab,
    render_expansion_tab_content
)


def render_results_tabs(_results=None):
    """Render all result tabs with five-tab structure."""
    # Check if we have results OR if we have XML content (for patient demographics filtering XMLs)
    # For patient demographics XMLs, results might be empty dict {} but that's still valid
    # Also ensure results are from current file, not stale from previous file
    # In the pipeline we track hashes rather than compatibility file keys; consider results present if
    # any pipeline outputs exist and we're not currently processing.
    has_pipeline_outputs = (
        SessionStateKeys.PIPELINE_CODES in st.session_state
        or SessionStateKeys.PIPELINE_ENTITIES in st.session_state
    )
    has_processed_current_file = has_pipeline_outputs and not st.session_state.get(SessionStateKeys.IS_PROCESSING, False)
    
    has_clinical_results = has_processed_current_file
    has_xml_content = SessionStateKeys.UPLOADED_FILE in st.session_state
    
    # Only show tabs if we have processed results from the current file
    # Don't show tabs just because we have XML content - wait until processing is complete
    debug_mode = st.session_state.get(SessionStateKeys.DEBUG_MODE, False)

    if has_clinical_results:
        # Show clinical + XML browser + search browser + code lookup; reports remain disabled
        # Add Memory tab in debug mode
        if debug_mode:
            main_tab1, main_tab_xml, main_tab2, main_tab_reports, main_tab_lookup, main_tab_memory = st.tabs([
                "🏥 Clinical Codes",
                "🗂 XML Explorer",
                "🔍 Searches",
                "📊 Reports",
                "🔬 Code Lookup",
                "🧠 Memory"
            ])
        else:
            main_tab1, main_tab_xml, main_tab2, main_tab_reports, main_tab_lookup = st.tabs([
                "🏥 Clinical Codes",
                "🗂 XML Explorer",
                "🔍 Searches",
                "📊 Reports",
                "🔬 Code Lookup"
            ])

        with main_tab1:
            render_clinical_codes_main_tab()

        with main_tab_xml:
            render_xml_tab()

        with main_tab2:
            render_search_tabs()

        with main_tab_reports:
            render_reports_tab()

        with main_tab_lookup:
            from .tabs.terminology_server import render_individual_code_lookup
            render_individual_code_lookup()

        if debug_mode:
            with main_tab_memory:
                from .tabs.debug import render_memory_diagnostics_tab
                render_memory_diagnostics_tab()

    else:
        # No XML loaded - show welcome tab + Code Lookup (+ Memory in debug mode)
        if debug_mode:
            welcome_tab, lookup_tab, memory_tab = st.tabs(["📋 ClinXML", "🔬 Code Lookup", "🧠 Memory"])
        else:
            welcome_tab, lookup_tab = st.tabs(["📋 ClinXML", "🔬 Code Lookup"])

        with welcome_tab:
            # Get dynamic MKB version text from session state
            version_info = st.session_state.get(SessionStateKeys.LOOKUP_VERSION_INFO, {})
            mkb_version = version_info.get('emis_version', 'the latest MKB lookup table')
            if mkb_version != 'the latest MKB lookup table':
                mkb_text = f"MKB {mkb_version}"
            else:
                mkb_text = mkb_version

            st.markdown(
                info_box(
                    f"Upload EMIS XML files to analyse search logic, visualise report structures, "
                    f"and translate clinical codes to UK SNOMED using {mkb_text}."
                ),
                unsafe_allow_html=True
            )

        with lookup_tab:
            from .tabs.terminology_server import render_individual_code_lookup
            render_individual_code_lookup()

        if debug_mode:
            with memory_tab:
                from .tabs.debug import render_memory_diagnostics_tab
                render_memory_diagnostics_tab()


def render_clinical_codes_main_tab():
    """Render the Clinical Codes main tab (formerly XML Contents)"""
    from .tabs.clinical_codes.codes_common import get_unified_clinical_data
    unified_results = get_unified_clinical_data()
    # Check if we have clinical data or if this is a non-clinical XML (patient demographics filtering, etc.)
    has_clinical_data = bool(unified_results and unified_results.get("all_codes"))
    
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
    
    # Clinical codes sub-tabs (flat structure)
    (
        tab_summary,
        tab_clinical,
        tab_meds,
        tab_refsets,
        tab_pseudo_refsets,
        tab_pseudo_members,
        tab_expansion,
        tab_analytics,
    ) = st.tabs([
        "📊 Summary",
        "🏥 Clinical Codes",
        "💊 Medications",
        "📋 RefSets",
        "🔍 Pseudo RefSets",
        "📝 Pseudo RefSet Members",
        "👪 Child Code Finder",
        "📊 Analytics",
    ])
    
    with tab_summary:
        render_summary_tab()
    
    with tab_clinical:
        render_clinical_codes_tab()
    
    with tab_meds:
        render_medications_tab()
    
    with tab_refsets:
        render_refsets_tab()
    
    with tab_pseudo_refsets:
        render_pseudo_refsets_tab()
    
    with tab_pseudo_members:
        render_pseudo_refset_members_tab()

    with tab_expansion:
        # Get clinical codes for expansion
        from ..system.session_state import SessionStateKeys
        pipeline_codes = st.session_state.get(SessionStateKeys.PIPELINE_CODES, [])
        render_expansion_tab_content(pipeline_codes)

    with tab_analytics:
        render_analytics_tab()
