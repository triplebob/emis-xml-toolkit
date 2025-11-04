"""
Clinical data tab rendering functions.

This module handles rendering of all clinical data related tabs:
- Summary tab with statistics
- Clinical codes tab
- Medications tab  
- Refsets tab
- Pseudo refsets tab
- Pseudo refset members tab
- Clinical codes main tab (aggregated view)
- Results tabs (wrapper for all clinical tabs)
"""

from .common_imports import *
from .base_tab import BaseTab, TabRenderer
from .tab_helpers import (
    _lookup_snomed_for_ui,
    _deduplicate_clinical_data_by_emis_guid,
    _add_source_info_to_clinical_data,
    ensure_analysis_cached,
    get_unified_clinical_data
)

# Import report functions from the dedicated report_tabs module
try:
    from .report_tabs import (
        render_list_reports_tab,
        render_audit_reports_tab,
        render_aggregate_reports_tab
    )
except ImportError:
    # Fallback functions if imports fail
    def render_list_reports_tab(xml_content, xml_filename):
        st.info("🔄 List Reports tab under refactoring - functionality will be restored shortly")
    
    def render_audit_reports_tab(xml_content, xml_filename):
        st.info("🔄 Audit Reports tab under refactoring - functionality will be restored shortly")
    
    def render_aggregate_reports_tab(xml_content, xml_filename):
        st.info("🔄 Aggregate Reports tab under refactoring - functionality will be restored shortly")

# Import functions from the new modular tabs structure
from .analytics_tab import render_analytics_tab
from .analysis_tabs import render_search_analysis_tab

# NHS Terminology Server integration
try:
    from ...terminology_server.expansion_ui import render_expansion_tab_content
    NHS_TERMINOLOGY_AVAILABLE = True
except ImportError:
    NHS_TERMINOLOGY_AVAILABLE = False


def render_summary_tab(results):
    """Render the summary tab with statistics."""
    # Get comprehensive clinical code counts including report codes
    search_clinical_count = len(results['clinical'])
    medication_count = len(results['medications'])
    clinical_pseudo_count = len(results.get('clinical_pseudo_members', []))
    medication_pseudo_count = len(results.get('medication_pseudo_members', []))
    refset_count = len(results['refsets'])
    pseudo_refset_count = len(results.get('pseudo_refsets', []))
    
    # Calculate report code counts
    report_results = st.session_state.get('report_results')
    report_clinical_count = 0
    if report_results and hasattr(report_results, 'clinical_codes'):
        report_clinical_count = len(report_results.clinical_codes)
    
    # Total clinical codes (search + report)
    total_clinical_count = search_clinical_count + report_clinical_count
    total_count = total_clinical_count + medication_count + refset_count + pseudo_refset_count
    
    col1_summary, col2_summary, col3_summary, col4_summary, col5_summary = st.columns(5)
    
    with col1_summary:
        st.metric("Total Containers", total_count)
    with col2_summary:
        st.metric("Total Clinical Codes", total_clinical_count, delta=f"+{report_clinical_count} from reports" if report_clinical_count > 0 else None)
    with col3_summary:
        st.metric("Standalone Medications", medication_count)
    with col4_summary:
        st.metric("True Refsets", refset_count)
    with col5_summary:
        st.metric("Pseudo-Refsets", pseudo_refset_count, delta_color="inverse")
    
    # Processing summary from main app
    if hasattr(st.session_state, 'xml_filename'):
        # Calculate all items including pseudo-refset members
        standalone_clinical = len(results['clinical'])
        standalone_medications = len(results['medications'])
        clinical_pseudo = len(results.get('clinical_pseudo_members', []))
        medication_pseudo = len(results.get('medication_pseudo_members', []))
        total_items = search_clinical_count + report_clinical_count + standalone_medications + clinical_pseudo + medication_pseudo + refset_count + pseudo_refset_count
        
        st.success(f"✅ Processed {total_items} items: {search_clinical_count} search clinical codes, {report_clinical_count} report clinical codes, {standalone_medications} standalone medications, {clinical_pseudo} clinical in pseudo-refsets, {medication_pseudo} medications in pseudo-refsets, {refset_count} refsets, {pseudo_refset_count} pseudo-refsets")
    
    # Clinical codes breakdown
    if search_clinical_count > 0 or report_clinical_count > 0:
        st.subheader("📊 Clinical Codes Breakdown")
        col1_breakdown, col2_breakdown, col3_breakdown = st.columns(3)
        
        with col1_breakdown:
            st.metric("From Searches", search_clinical_count)
        with col2_breakdown:
            st.metric("From Reports", report_clinical_count)
        with col3_breakdown:
            search_pct = (search_clinical_count / total_clinical_count * 100) if total_clinical_count > 0 else 0
            st.metric("Search %", f"{search_pct:.1f}%")
    
    # Additional info rows with counts
    col1_extra, col2_extra = st.columns(2)
    
    with col1_extra:
        if clinical_pseudo_count > 0:
            st.info(f"📋 {clinical_pseudo_count} clinical codes are part of pseudo-refsets")
        else:
            st.success("📋 0 clinical codes in pseudo-refsets")
    
    with col2_extra:
        if medication_pseudo_count > 0:
            st.info(f"💊 {medication_pseudo_count} medications are part of pseudo-refsets")
        else:
            st.success("💊 0 medications in pseudo-refsets")
    
    # Success rates
    if search_clinical_count > 0:
        clinical_found = len([c for c in results['clinical'] if c['Mapping Found'] == 'Found'])
        st.info(f"Search clinical codes mapping success: {clinical_found}/{search_clinical_count} ({clinical_found/search_clinical_count*100:.1f}%)")
    
    if medication_count > 0:
        med_found = len([m for m in results['medications'] if m['Mapping Found'] == 'Found'])
        st.info(f"Standalone medications mapping success: {med_found}/{medication_count} ({med_found/medication_count*100:.1f}%)")


# Placeholder for other functions - will be filled in subsequent steps
def render_clinical_codes_tab(results=None):
    
    # Switch to unified parsing approach using orchestrated analysis
    from .tab_helpers import get_unified_clinical_data
    
    unified_results = get_unified_clinical_data()
    if not unified_results:
        st.write("❌ No analysis data found - please run XML analysis first")
        return
    
    # Get clinical data from unified analysis (already has source tracking and filtering)
    clinical_data = unified_results.get('clinical_codes', [])
    pseudo_members_data = unified_results.get('clinical_pseudo_members', [])
    pseudo_refsets_data = unified_results.get('pseudo_refsets', [])
    
    # Source tracking is always enabled in unified parsing (columns hidden based on mode)
    show_code_sources = True
        
    # Deduplication mode toggle for clinical codes
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("### 📋 Standalone Clinical Codes" + (" (with source tracking)" if show_code_sources else ""))
    with col2:
        current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
        dedup_mode = st.selectbox(
            "Code Display Mode (will trigger reprocessing):",
            options=['unique_codes', 'unique_per_entity'],
            format_func=lambda x: {
                'unique_codes': '🔀 Unique Codes', 
                'unique_per_entity': '📍 Per Source'
            }[x],
            index=0 if current_mode == 'unique_codes' else 1,
            key="clinical_deduplication_mode",
            help="🔀 Unique Codes: Show each code once\n📍 Per Source: Show codes per search/report"
        )
        
        # Check if mode changed - no reprocessing needed, just update session state
        if dedup_mode != current_mode:
            st.session_state.current_deduplication_mode = dedup_mode
    
    # Deduplication is now handled by render_section_with_data based on current mode
    
    # Standalone clinical codes section
    render_section_with_data(
        title="",  # Empty title since we rendered it above
        data=clinical_data,
        info_text="These are clinical codes that are NOT part of any pseudo-refset and can be used directly. " + 
                  ("Use the Mode toggle above to switch between 'Unique Codes' (show each code once across entire XML) and 'Per Source' (show codes per search/report with source tracking)." if current_mode == 'unique_per_entity' else 
                   "Currently showing unique codes only (one instance per code across entire XML). Use the Mode toggle to show per-source tracking."),
        empty_message="No standalone clinical codes found in this XML file",
        download_label="📥 Download Standalone Clinical Codes CSV",
        filename_prefix="standalone_clinical_codes",
        highlighting_function=get_success_highlighting_function()
    )
    
    # Check for pseudo-refset members and show appropriate message
    pseudo_members_count = len(pseudo_members_data)
    
    if pseudo_members_count > 0:
        # Show info directing users to dedicated tab
        st.info(f"⚠️ **{pseudo_members_count} clinical codes are part of pseudo-refsets** - View and export them from the 'Pseudo-Refset Members' tab.")
    else:
        # Show success when no pseudo-refset members exist
        st.success("✅ **All clinical codes are properly mapped!** This means all codes in your XML are either standard refsets (directly usable in EMIS) or standalone codes (also directly usable).")


def render_medications_tab(results):
    # Deduplication mode toggle for medications
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("### 💊 Standalone Medications")
    with col2:
        current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
        dedup_mode = st.selectbox(
            "Code Display Mode (will trigger reprocessing):",
            options=['unique_codes', 'unique_per_entity'],
            format_func=lambda x: {
                'unique_codes': '🔀 Unique Codes', 
                'unique_per_entity': '📍 Per Source'
            }[x],
            index=0 if current_mode == 'unique_codes' else 1,
            key="medication_deduplication_mode",
            help="🔀 Unique Codes: Show each code once\n📍 Per Source: Show codes per search/report"
        )
        
        # Check if mode changed - no reprocessing needed, just update session state
        if dedup_mode != current_mode:
            st.session_state.current_deduplication_mode = dedup_mode
    
    # Switch to unified parsing approach using orchestrated analysis (like clinical codes tab)
    unified_results = get_unified_clinical_data()
    if not unified_results:
        st.write("❌ No analysis data found - please run XML analysis first")
        return
    
    # Get medications data from unified analysis (already standardized and categorized with _original_fields)
    medications_data = unified_results.get('medications', [])
    
    # Deduplication is now handled by render_section_with_data based on current mode
        
    # Determine what medications we have
    has_standalone = len(medications_data) > 0
    has_pseudo = results.get('medication_pseudo_members') and len(results.get('medication_pseudo_members', [])) > 0
    
    if has_standalone or has_pseudo:
        # Show standalone medications if they exist
        if has_standalone:
            # Filter out Has Qualifier column for medications - not relevant since medications have unique SNOMED codes for different strengths
            medications_data_filtered = []
            for medication in medications_data:
                filtered_med = {k: v for k, v in medication.items() if k != 'Has Qualifier'}
                medications_data_filtered.append(filtered_med)
            
            # Use the same efficient rendering pattern as clinical codes
            render_section_with_data(
                title="",  # Empty title since we rendered it above
                data=medications_data_filtered,
                info_text="These are medications that are NOT part of any pseudo-refset and can be used directly. " + 
                          ("Use the Mode toggle above to switch between 'Unique Codes' (show each medication once across entire XML) and 'Per Source' (show medications per search/report with source tracking)." if current_mode == 'unique_per_entity' else 
                           "Currently showing unique medications only (one instance per medication across entire XML). Use the Mode toggle to show per-source tracking."),
                empty_message="No standalone medications found in this XML file",
                download_label="📥 Download Standalone Medications CSV",
                filename_prefix="standalone_medications",
                highlighting_function=get_success_highlighting_function()
            )
        
        # Show pseudo-refset medications section if they exist
        if has_pseudo:
            render_info_section(
                title="⚠️ Medications in Pseudo-Refsets",
                content="These medications are part of pseudo-refsets (refsets EMIS does not natively support yet), and can only be used by listing all member codes. Export these from the 'Pseudo-Refset Members' tab.",
                section_type="warning"
            )
    else:
        # No medications found at all
        render_info_section(
            title="",
            content="No medications found in this XML file. This file contains only clinical codes and/or refsets.",
            section_type="info"
        )
    
    # Show help sections only when medications exist
    if has_standalone or has_pseudo:
        # Add helpful tooltip information
        with st.expander("ℹ️ Medication Type Flags Help"):
            st.markdown("""
            **Medication Type Flags:**
            - **SCT_CONST** (Constituent): Active ingredients or components
            - **SCT_DRGGRP** (Drug Group): Groups of related medications  
            - **SCT_PREP** (Preparation): Specific medication preparations
            - **Standard Medication**: General medication codes from lookup table
            """)
        
        
        # Show pseudo-medications data if they exist
        if has_pseudo:
            medication_pseudo_df = pd.DataFrame(results['medication_pseudo_members'])
            
            # Color code pseudo-refset members differently
            def highlight_pseudo_medications(row):
                if row['Mapping Found'] == 'Found':
                    return ['background-color: #fff3cd'] * len(row)  # Light yellow/orange
                else:
                    return ['background-color: #f8cecc'] * len(row)  # Light red/orange
            
            styled_pseudo_medications = medication_pseudo_df.style.apply(highlight_pseudo_medications, axis=1)
            st.dataframe(styled_pseudo_medications, width='stretch')


def render_refsets_tab(results):
    # Deduplication mode toggle for refsets
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("### 📊 Refsets")
    with col2:
        current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
        dedup_mode = st.selectbox(
            "Code Display Mode (will trigger reprocessing):",
            options=['unique_codes', 'unique_per_entity'],
            format_func=lambda x: {
                'unique_codes': '🔀 Unique Codes', 
                'unique_per_entity': '📍 Per Source'
            }[x],
            index=0 if current_mode == 'unique_codes' else 1,
            key="refsets_deduplication_mode",
            help="🔀 Unique Codes: Show each refset once\n📍 Per Source: Show refsets per search/report"
        )
        
        # Check if mode changed - no reprocessing needed, just update session state
        if dedup_mode != current_mode:
            st.session_state.current_deduplication_mode = dedup_mode
    
    # Switch to unified parsing approach using orchestrated analysis (like clinical codes tab)
    unified_results = get_unified_clinical_data()
    if not unified_results:
        st.write("❌ No analysis data found - please run XML analysis first")
        return
    
    # Get refsets data from unified analysis (already standardized with _original_fields)
    refsets_data = unified_results.get('refsets', [])
    
    # Deduplication is now handled by render_section_with_data based on current mode
    
    # Refsets section with proper source tracking display
    if refsets_data:
        # Filter out Descendants and Has Qualifier columns for refsets - not relevant since refsets are container concepts, not individual codes with hierarchies or qualifiers
        refsets_data_filtered = []
        for refset in refsets_data:
            filtered_refset = {k: v for k, v in refset.items() if k not in ['Descendants', 'Has Qualifier']}
            refsets_data_filtered.append(filtered_refset)
        
        def highlight_refsets(row):
            return ['background-color: #d4edda'] * len(row)  # Light green for refsets
        
        current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
        
        # Use the same efficient rendering pattern as clinical codes and medications
        render_section_with_data(
            title="",  # Empty title since we rendered it above
            data=refsets_data_filtered,
            info_text="These are true refsets that EMIS recognizes natively. They can be used directly by their SNOMED code in EMIS clinical searches. " + 
                      ("Use the Mode toggle above to switch between 'Unique Codes' and 'Per Source' to see source tracking." if current_mode == 'unique_per_entity' else 
                       "Currently showing unique refsets only. Use the Mode toggle to show per-source tracking."),
            empty_message="No refsets found in this XML file",
            download_label="📥 Download Refsets CSV",
            filename_prefix="refsets",
            highlighting_function=highlight_refsets
        )
    else:
        st.info("No refsets found in this XML file")


def render_pseudo_refsets_tab(results):
    # Switch to unified parsing approach using orchestrated analysis
    unified_results = get_unified_clinical_data()
    if not unified_results:
        st.write("❌ No analysis data found - please run XML analysis first")
        return
    
    # Get pseudo-refsets data from unified analysis
    pseudo_refsets_data = unified_results.get('pseudo_refsets', [])
    
    # Apply deduplication based on current mode
    current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
    if current_mode == 'unique_codes' and pseudo_refsets_data:
        # Deduplicate by EMIS GUID - keep only one instance per pseudo-refset
        unique_pseudo_refsets = {}
        for pseudo_refset in pseudo_refsets_data:
            emis_guid = pseudo_refset.get('EMIS GUID', '')
            if emis_guid and emis_guid not in unique_pseudo_refsets:
                unique_pseudo_refsets[emis_guid] = pseudo_refset
        pseudo_refsets_data = list(unique_pseudo_refsets.values())
    
    # Deduplication mode toggle for pseudo-refsets
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("### ⚠️ All Pseudo-Refsets")
    with col2:
        current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
        dedup_mode = st.selectbox(
            "Code Display Mode (will trigger reprocessing):",
            options=['unique_codes', 'unique_per_entity'],
            format_func=lambda x: {
                'unique_codes': '🔀 Unique Codes', 
                'unique_per_entity': '📍 Per Source'
            }[x],
            index=0 if current_mode == 'unique_codes' else 1,
            key="pseudo_refsets_deduplication_mode",
            help="🔀 Unique Codes: Show each pseudo-refset once\n📍 Per Source: Show pseudo-refsets per search/report"
        )
        
        # Check if mode changed - no reprocessing needed, just update session state
        if dedup_mode != current_mode:
            st.session_state.current_deduplication_mode = dedup_mode
    
    # Show appropriate dynamic message based on pseudo-refsets and mode
    if not pseudo_refsets_data:
        st.success("✅ No pseudo-refsets found - all ValueSets are standard refsets or standalone codes (directly usable in EMIS).")
    else:
        current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
        if current_mode == 'unique_codes':
            st.info("ℹ️ These are ValueSet containers that hold multiple clinical codes but are NOT stored in the EMIS database as referenceable refsets. Currently showing unique pseudo-refsets only. Use the Mode toggle to show per-source tracking.")
        else:
            st.info("ℹ️ These are ValueSet containers that hold multiple clinical codes but are NOT stored in the EMIS database as referenceable refsets. Currently showing per-source tracking. Use the Mode toggle to show unique codes only.")
    
    # Deduplication is now handled by render_section_with_data based on current mode
    display_pseudo_refsets = pseudo_refsets_data
    
    # Use efficient render_section_with_data pattern for pseudo-refsets
    if display_pseudo_refsets:
        # Filter out unnecessary columns for pseudo-refsets display
        display_data = []
        for refset in display_pseudo_refsets:
            filtered_refset = {k: v for k, v in refset.items() if k not in ['Descendants', 'Has Qualifier']}
            display_data.append(filtered_refset)
        
        render_section_with_data(
            title="",  # No title needed as it's already shown above
            data=display_data,
            info_text=("Use the Mode toggle above to switch between 'Unique Codes' and 'Per Source' to see source tracking." if current_mode == 'unique_per_entity' else 
                      "Currently showing unique pseudo-refsets only. Use the Mode toggle to show per-source tracking."),
            empty_message="✅ No pseudo-refsets found - all ValueSets are standard refsets or standalone codes (directly usable in EMIS).",
            download_label="📥 Download Pseudo-Refsets CSV",
            filename_prefix="pseudo_refsets",
            highlighting_function=get_warning_highlighting_function()
        )
        
        st.warning("""
        **Important Usage Notes:**
        - These pseudo-refset containers cannot be referenced directly in EMIS clinical searches
        - To use them, you must manually list all individual member codes within each valueset
        - View the 'Pseudo-Refset Members' tab to see all member codes for each container
        """)
    # No else needed - the info box above already handles the no pseudo-refsets case


def render_pseudo_refset_members_tab(results):
    # Switch to unified parsing approach using orchestrated analysis
    from .tab_helpers import get_unified_clinical_data
    
    unified_results = get_unified_clinical_data()
    if not unified_results:
        st.write("❌ No analysis data found - please run XML analysis first")
        return
    
    # Get pseudo-refset members data from unified analysis
    pseudo_members_data = unified_results.get('clinical_pseudo_members', [])
    
    # Deduplication mode toggle for pseudo-refset members
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("### 📝 Pseudo-Refset Member Codes")
    with col2:
        current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
        dedup_mode = st.selectbox(
            "Code Display Mode (will trigger reprocessing):",
            options=['unique_codes', 'unique_per_entity'],
            format_func=lambda x: {
                'unique_codes': '🔀 Unique Codes', 
                'unique_per_entity': '📍 Per Source'
            }[x],
            index=0 if current_mode == 'unique_codes' else 1,
            key="pseudo_members_deduplication_mode",
            help="🔀 Unique Codes: Show each code once\n📍 Per Source: Show codes per search/report"
        )
        
        # Check if mode changed - no reprocessing needed, just update session state
        if dedup_mode != current_mode:
            st.session_state.current_deduplication_mode = dedup_mode
    
    # Deduplication is now handled by render_section_with_data based on current mode
    
    # Show appropriate dynamic message based on pseudo-members and mode
    if not pseudo_members_data:
        st.success("✅ No pseudo-refset member codes found - all codes are either standard refsets (directly usable in EMIS) or standalone codes (also directly usable).")
        return
    else:
        current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
        if current_mode == 'unique_codes':
            st.info("⚠️ These clinical codes are part of pseudo-refsets (refsets EMIS does not natively support yet), and can only be used by listing all member codes. Currently showing unique codes only. Use the Mode toggle to show per-source tracking.")
        else:
            st.info("⚠️ These clinical codes are part of pseudo-refsets (refsets EMIS does not natively support yet), and can only be used by listing all member codes. Currently showing per-source tracking. Use the Mode toggle to show unique codes only.")
    
    # Use efficient render_section_with_data pattern for pseudo-members
    render_section_with_data(
        title="",  # No title needed as it's already shown above
        data=pseudo_members_data,
        info_text=("Use the Mode toggle above to switch between 'Unique Codes' and 'Per Source' to see source tracking." if current_mode == 'unique_per_entity' else 
                  "Currently showing unique codes only. Use the Mode toggle to show per-source tracking."),
        empty_message="✅ No pseudo-refset member codes found - all codes are either standard refsets (directly usable in EMIS) or standalone codes (also directly usable).",
        download_label="📥 Download Pseudo-Members CSV",
        filename_prefix="pseudo_members",
        highlighting_function=get_warning_highlighting_function()
    )
    
    # Add helpful information about pseudo-refsets
    st.warning("""
    **Important Usage Notes:**
    - These codes are part of pseudo-refsets (ValueSets that EMIS does not recognize natively)
    - To use these codes in EMIS clinical searches, you must manually list all individual member codes
    - Pseudo-refset containers cannot be referenced directly by their container SNOMED code
    - View the pseudo-refset containers in the 'All Pseudo-Refsets' tab
    """)


def render_clinical_codes_main_tab(results):
    """Render the Clinical Codes main tab (formerly XML Contents)"""
    # Clinical Codes Configuration
    # Always enable report codes and source tracking - no longer configurable
    st.session_state.clinical_include_report_codes = True
    st.session_state.clinical_show_code_sources = True
    
    # Clinical codes sub-tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "📋 Summary", 
        "🏥 Clinical Codes", 
        "💊 Medications", 
        "📊 Refsets", 
        "⚠️ Pseudo-Refsets", 
        "📝 Pseudo-Refset Members", 
        "📊 Analytics",
        "🏥 NHS Term Server"
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
        render_pseudo_refsets_tab(results)
    
    with tab6:
        render_pseudo_refset_members_tab(results)
    
    with tab7:
        render_analytics_tab()
    
    with tab8:
        render_nhs_terminology_tab(results)


def render_nhs_terminology_tab(results):
    """Render NHS Terminology Server integration tab"""
    if not NHS_TERMINOLOGY_AVAILABLE:
        st.error("❌ NHS Terminology Server integration not available")
        st.info("The terminology server module failed to import. Please check the installation.")
        return
    
    # Get unified clinical data for expansion
    from .tab_helpers import get_unified_clinical_data
    
    unified_results = get_unified_clinical_data()
    if not unified_results:
        st.warning("❌ No clinical analysis data found - please run XML analysis first")
        return
    
    # Combine all clinical codes for expansion analysis
    all_clinical_codes = []
    
    # Add standalone clinical codes
    clinical_codes = unified_results.get('clinical_codes', [])
    all_clinical_codes.extend(clinical_codes)
    
    # Add pseudo-refset member codes
    pseudo_members = unified_results.get('clinical_pseudo_members', [])
    all_clinical_codes.extend(pseudo_members)
    
    # Add refsets (they might also have includechildren)
    refsets = unified_results.get('refsets', [])
    all_clinical_codes.extend(refsets)
    
    if not all_clinical_codes:
        st.info("ℹ️ No clinical codes found for expansion analysis")
        return
    
    # Render the expansion interface
    render_expansion_tab_content(all_clinical_codes)


def render_results_tabs(results):
    """Render all result tabs with new 5-tab structure."""
    if 'results' in st.session_state and st.session_state.results:
        results = st.session_state.results
        
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
        st.info("Results will appear here after processing an XML file")