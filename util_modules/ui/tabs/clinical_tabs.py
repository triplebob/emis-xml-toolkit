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

# Import report functions from the specialized report modules
try:
    from .list_report_tab import render_list_reports_tab
    from .audit_report_tab import render_audit_reports_tab
    from .aggregate_report_tab import render_aggregate_reports_tab
except ImportError as e:
    # If imports fail, show the actual error instead of placeholder
    def render_list_reports_tab(xml_content, xml_filename):
        st.error(f"❌ Import Error for List Reports: {e}")
    
    def render_audit_reports_tab(xml_content, xml_filename):
        st.error(f"❌ Import Error for Audit Reports: {e}")
    
    def render_aggregate_reports_tab(xml_content, xml_filename):
        st.error(f"❌ Import Error for Aggregate Reports: {e}")

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
        st.metric("Total Clinical Codes", total_clinical_count, delta=f"+{report_clinical_count} from reports" if report_clinical_count > 0 else None, delta_color="off")
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
        
        st.markdown(f"""
        <div style="
            background-color: #1F4E3D;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 0.5rem;
        ">
            ✓&nbsp;&nbsp;Processed {total_items} items: {search_clinical_count} search clinical codes, {report_clinical_count} report clinical codes, {standalone_medications} standalone medications, {clinical_pseudo} clinical in pseudo-refsets, {medication_pseudo} medications in pseudo-refsets, {refset_count} refsets, {pseudo_refset_count} pseudo-refsets
        </div>
        """, unsafe_allow_html=True)
    
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
    
    # Row 1: Clinical codes mapping success and pseudo-refsets
    if search_clinical_count > 0:
        clinical_found = len([c for c in results['clinical'] if c['Mapping Found'] == 'Found'])
        col1_clinical, col2_clinical = st.columns([6, 2])
        
        with col1_clinical:
            st.markdown(f"""
            <div style="
                background-color: #28546B;
                padding: 0.75rem;
                border-radius: 0.5rem;
                color: #FAFAFA;
                text-align: left;
                margin-bottom: 0.5rem;
            ">
                Search clinical codes mapping success: {clinical_found}/{search_clinical_count} ({clinical_found/search_clinical_count*100:.1f}%)
            </div>
            """, unsafe_allow_html=True)
        
        with col2_clinical:
            if clinical_pseudo_count > 0:
                st.markdown(f"""
                <div style="
                    background-color: #660022;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 0.5rem;
                ">
                    📋 {clinical_pseudo_count} clinical codes are part of pseudo-refsets
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="
                    background-color: #1F4E3D;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 0.5rem;
                ">
                    📋 0 clinical codes in pseudo-refsets
                </div>
                """, unsafe_allow_html=True)
    
    # Row 2: Medications mapping success and pseudo-refsets  
    if medication_count > 0:
        med_found = len([m for m in results['medications'] if m['Mapping Found'] == 'Found'])
        col1_medication, col2_medication = st.columns([6, 2])
        
        with col1_medication:
            st.markdown(f"""
            <div style="
                background-color: #5B2758;
                padding: 0.75rem;
                border-radius: 0.5rem;
                color: #FAFAFA;
                text-align: left;
                margin-bottom: 0.5rem;
            ">
                Standalone medications mapping success: {med_found}/{medication_count} ({med_found/medication_count*100:.1f}%)
            </div>
            """, unsafe_allow_html=True)
        
        with col2_medication:
            if medication_pseudo_count > 0:
                st.markdown(f"""
                <div style="
                    background-color: #660022;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 0.5rem;
                ">
                    💊 {medication_pseudo_count} medications are part of pseudo-refsets
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="
                    background-color: #1F4E3D;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 0.5rem;
                ">
                    💊 0 medications in pseudo-refsets
                </div>
                """, unsafe_allow_html=True)


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
        
    # Clinical codes display fragment - isolated from main app
    @st.fragment
    def clinical_codes_display_fragment():
        # Deduplication mode toggle for clinical codes
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown("### 📋 Standalone Clinical Codes" + (" (with source tracking)" if show_code_sources else ""))
        with col2:
            current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
            dedup_mode = st.selectbox(
                "Code Display Mode:",
                options=['unique_codes', 'unique_per_entity'],
                format_func=lambda x: {
                    'unique_codes': '🔀 Unique Codes', 
                    'unique_per_entity': '📍 Per Source'
                }[x],
                index=0 if current_mode == 'unique_codes' else 1,
                key="clinical_deduplication_mode",
                help="🔀 Unique Codes: Show each code once\n📍 Per Source: Show codes per search/report"
            )
            
            # Check if mode changed - update session state within fragment
            if dedup_mode != current_mode:
                st.session_state.current_deduplication_mode = dedup_mode
                st.rerun()
        
        # Standalone clinical codes section - rendered within fragment
        render_section_with_data(
            title="",  # Empty title since we rendered it above
            data=clinical_data,
            info_text="These are clinical codes that are NOT part of any pseudo-refset and can be used directly.",
            empty_message="No standalone clinical codes found in this XML file",
            download_label="📥 Download Standalone Clinical Codes CSV",
            filename_prefix="standalone_clinical_codes",
            highlighting_function=get_success_highlighting_function()
        )
    
    # Execute the clinical codes display fragment
    clinical_codes_display_fragment()
    
    # Check for pseudo-refset members and show appropriate message
    pseudo_members_count = len(pseudo_members_data)
    
    if pseudo_members_count > 0:
        # Show info directing users to dedicated tab
        st.markdown(f"""
        <div style="
            background-color: #660022;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 0.5rem;
        ">
            ⚠️ <strong>{pseudo_members_count} clinical codes are part of pseudo-refsets</strong> - View and export them from the 'Pseudo-Refset Members' tab.
        </div>
        """, unsafe_allow_html=True)
    else:
        # Show success when no pseudo-refset members exist
        st.success("✅ **All clinical codes are properly mapped!** This means all codes in your XML are either standard refsets (directly usable in EMIS) or standalone codes (also directly usable).")


def render_medications_tab(results):
    # Switch to unified parsing approach using orchestrated analysis (like clinical codes tab)
    unified_results = get_unified_clinical_data()
    if not unified_results:
        st.write("❌ No analysis data found - please run XML analysis first")
        return
    
    # Get medications data from unified analysis (already standardized and categorized with _original_fields)
    medications_data = unified_results.get('medications', [])
    
    # Medications display fragment - isolated from main app
    @st.fragment
    def medications_display_fragment():
        # Deduplication mode toggle for medications
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown("### 💊 Standalone Medications")
        with col2:
            current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
            dedup_mode = st.selectbox(
                "Code Display Mode:",
                options=['unique_codes', 'unique_per_entity'],
                format_func=lambda x: {
                    'unique_codes': '🔀 Unique Codes', 
                    'unique_per_entity': '📍 Per Source'
                }[x],
                index=0 if current_mode == 'unique_codes' else 1,
                key="medication_deduplication_mode",
                help="🔀 Unique Codes: Show each code once\n📍 Per Source: Show codes per search/report"
            )
            
            # Check if mode changed - update session state within fragment
            if dedup_mode != current_mode:
                st.session_state.current_deduplication_mode = dedup_mode
                st.rerun()
        
        # Determine what medications we have
        has_standalone = len(medications_data) > 0
        
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
                info_text="These are medications that are NOT part of any pseudo-refset and can be used directly.",
                empty_message="No standalone medications found in this XML file",
                download_label="📥 Download Standalone Medications CSV",
                filename_prefix="standalone_medications",
                highlighting_function=get_success_highlighting_function()
            )
    
    # Execute the medications display fragment
    medications_display_fragment()
    
    # Additional sections outside fragment (keep existing logic)
    has_standalone = len(medications_data) > 0
    has_pseudo = results.get('medication_pseudo_members') and len(results.get('medication_pseudo_members', [])) > 0
    
    if has_standalone or has_pseudo:
        
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
                    return ['background-color: #7A5F0B; color: #FAFAFA'] * len(row)  # Amber for found
                else:
                    return ['background-color: #660022; color: #FAFAFA'] * len(row)  # Wine red for not found
            
            styled_pseudo_medications = medication_pseudo_df.style.apply(highlight_pseudo_medications, axis=1)
            st.dataframe(styled_pseudo_medications, width='stretch')


def render_refsets_tab(results):
    # Switch to unified parsing approach using orchestrated analysis (like clinical codes tab)
    unified_results = get_unified_clinical_data()
    if not unified_results:
        st.write("❌ No analysis data found - please run XML analysis first")
        return
    
    # Get refsets data from unified analysis (already standardized with _original_fields)
    refsets_data = unified_results.get('refsets', [])
    
    # Refsets display fragment - isolated from main app
    @st.fragment
    def refsets_display_fragment():
        # Deduplication mode toggle for refsets
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown("### 📊 Refsets")
        with col2:
            current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
            dedup_mode = st.selectbox(
                "Code Display Mode:",
                options=['unique_codes', 'unique_per_entity'],
                format_func=lambda x: {
                    'unique_codes': '🔀 Unique Codes', 
                    'unique_per_entity': '📍 Per Source'
                }[x],
                index=0 if current_mode == 'unique_codes' else 1,
                key="refsets_deduplication_mode",
                help="🔀 Unique Codes: Show each refset once\n📍 Per Source: Show refsets per search/report"
            )
            
            # Check if mode changed - update session state within fragment
            if dedup_mode != current_mode:
                st.session_state.current_deduplication_mode = dedup_mode
                st.rerun()
        
        # Refsets section with proper source tracking display
        if refsets_data:
            # Filter out Descendants and Has Qualifier columns for refsets - not relevant since refsets are container concepts, not individual codes with hierarchies or qualifiers
            refsets_data_filtered = []
            for refset in refsets_data:
                filtered_refset = {k: v for k, v in refset.items() if k not in ['Descendants', 'Has Qualifier']}
                refsets_data_filtered.append(filtered_refset)
            
            def highlight_refsets(row):
                return ['background-color: #1F4E3D; color: #FAFAFA'] * len(row)  # Green for refsets
            
            current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
            
            # Use the same efficient rendering pattern as clinical codes and medications
            render_section_with_data(
                title="",  # Empty title since we rendered it above
                data=refsets_data_filtered,
                info_text="These are true refsets that EMIS recognizes natively. They can be used directly by their SNOMED code in EMIS clinical searches.",
                empty_message="No refsets found in this XML file",
                download_label="📥 Download Refsets CSV",
                filename_prefix="refsets",
                highlighting_function=highlight_refsets
            )
        else:
            st.markdown("""
            <div style="
                background-color: #28546B;
                padding: 0.75rem;
                border-radius: 0.5rem;
                color: #FAFAFA;
                text-align: left;
                margin-bottom: 0.5rem;
            ">
                No refsets found in this XML file
            </div>
            """, unsafe_allow_html=True)
    
    # Execute the refsets display fragment
    refsets_display_fragment()


def render_pseudo_refsets_tab(results):
    # Switch to unified parsing approach using orchestrated analysis
    unified_results = get_unified_clinical_data()
    if not unified_results:
        st.write("❌ No analysis data found - please run XML analysis first")
        return
    
    # Get pseudo-refsets data from unified analysis
    pseudo_refsets_data = unified_results.get('pseudo_refsets', [])
    
    # Pseudo-refsets display fragment - isolated from main app
    @st.fragment
    def pseudo_refsets_display_fragment():
        # Deduplication mode toggle for pseudo-refsets
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown("### ⚠️ All Pseudo-Refsets")
        with col2:
            current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
            dedup_mode = st.selectbox(
                "Code Display Mode:",
                options=['unique_codes', 'unique_per_entity'],
                format_func=lambda x: {
                    'unique_codes': '🔀 Unique Codes', 
                    'unique_per_entity': '📍 Per Source'
                }[x],
                index=0 if current_mode == 'unique_codes' else 1,
                key="pseudo_refsets_deduplication_mode",
                help="🔀 Unique Codes: Show each pseudo-refset once\n📍 Per Source: Show pseudo-refsets per search/report"
            )
            
            # Check if mode changed - update session state within fragment
            if dedup_mode != current_mode:
                st.session_state.current_deduplication_mode = dedup_mode
                st.rerun()
        
        # Apply deduplication based on current mode (need to recalculate inside fragment)
        current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
        display_pseudo_refsets = pseudo_refsets_data
        if current_mode == 'unique_codes' and pseudo_refsets_data:
            # Deduplicate by EMIS GUID - keep only one instance per pseudo-refset
            unique_pseudo_refsets = {}
            for pseudo_refset in pseudo_refsets_data:
                emis_guid = pseudo_refset.get('EMIS GUID', '')
                if emis_guid and emis_guid not in unique_pseudo_refsets:
                    unique_pseudo_refsets[emis_guid] = pseudo_refset
            display_pseudo_refsets = list(unique_pseudo_refsets.values())
        
        # Show appropriate dynamic message based on pseudo-refsets and mode
        if not display_pseudo_refsets:
            st.success("✅ No pseudo-refsets found - all ValueSets are standard refsets or standalone codes (directly usable in EMIS).")
        
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
                info_text="ℹ️ These are ValueSet containers that hold multiple clinical codes but are NOT stored in the EMIS database as referenceable refsets.",
                empty_message="✅ No pseudo-refsets found - all ValueSets are standard refsets or standalone codes (directly usable in EMIS).",
                download_label="📥 Download Pseudo-Refsets CSV",
                filename_prefix="pseudo_refsets",
                highlighting_function=get_warning_highlighting_function()
            )
            
            st.markdown("""
            <div style="
                background-color: #28546B;
                padding: 0.75rem;
                border-radius: 0.5rem;
                color: #FAFAFA;
                text-align: left;
                margin-bottom: 0.5rem;
            ">
                <strong>Important Usage Notes:</strong><br>
                • These pseudo-refset containers cannot be referenced directly in EMIS clinical searches<br>
                • To use them, you must manually list all individual member codes within each valueset<br>
                • View the 'Pseudo-Refset Members' tab to see all member codes for each container
            </div>
            """, unsafe_allow_html=True)
    
    # Execute the pseudo-refsets display fragment
    pseudo_refsets_display_fragment()


def render_pseudo_refset_members_tab(results):
    # Switch to unified parsing approach using orchestrated analysis
    from .tab_helpers import get_unified_clinical_data
    
    unified_results = get_unified_clinical_data()
    if not unified_results:
        st.write("❌ No analysis data found - please run XML analysis first")
        return
    
    # Get pseudo-refset members data from unified analysis
    pseudo_members_data = unified_results.get('clinical_pseudo_members', [])
    
    # Pseudo-members display fragment - isolated from main app
    @st.fragment
    def pseudo_members_display_fragment():
        # Deduplication mode toggle for pseudo-refset members
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown("### 📝 Pseudo-Refset Member Codes")
        with col2:
            current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
            dedup_mode = st.selectbox(
                "Code Display Mode:",
                options=['unique_codes', 'unique_per_entity'],
                format_func=lambda x: {
                    'unique_codes': '🔀 Unique Codes', 
                    'unique_per_entity': '📍 Per Source'
                }[x],
                index=0 if current_mode == 'unique_codes' else 1,
                key="pseudo_members_deduplication_mode",
                help="🔀 Unique Codes: Show each code once\n📍 Per Source: Show codes per search/report"
            )
            
            # Check if mode changed - update session state within fragment
            if dedup_mode != current_mode:
                st.session_state.current_deduplication_mode = dedup_mode
                st.rerun()
        
        # Show appropriate dynamic message based on pseudo-members and mode
        if not pseudo_members_data:
            st.success("✅ No pseudo-refset member codes found - all codes are either standard refsets (directly usable in EMIS) or standalone codes (also directly usable).")
            return
        
        # Use efficient render_section_with_data pattern for pseudo-members
        render_section_with_data(
            title="",  # No title needed as it's already shown above
            data=pseudo_members_data,
            info_text="ℹ️ These clinical codes are part of pseudo-refsets (refsets EMIS does not natively support yet), and can only be used by listing all member codes.",
            empty_message="✅ No pseudo-refset member codes found - all codes are either standard refsets (directly usable in EMIS) or standalone codes (also directly usable).",
            download_label="📥 Download Pseudo-Members CSV",
            filename_prefix="pseudo_members",
            highlighting_function=get_warning_highlighting_function()
        )
        
        # Add helpful information about pseudo-refsets
        st.markdown("""
        <div style="
            background-color: #28546B;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 0.5rem;
        ">
            <strong>Important Usage Notes:</strong><br>
            • These codes are part of pseudo-refsets (ValueSets that EMIS does not recognize natively)<br>
            • To use these codes in EMIS clinical searches, you must manually list all individual member codes<br>
            • Pseudo-refset containers cannot be referenced directly by their container SNOMED code<br>
            • View the pseudo-refset containers in the 'All Pseudo-Refsets' tab
        </div>
        """, unsafe_allow_html=True)
    
    # Execute the pseudo-members display fragment
    pseudo_members_display_fragment()


def render_clinical_codes_main_tab(results):
    """Render the Clinical Codes main tab (formerly XML Contents)"""
    # Check if we have clinical data or if this is a non-clinical XML (patient demographics filtering, etc.)
    has_clinical_data = results and len(results) > 0
    
    if not has_clinical_data:
        # Handle XMLs with no clinical codes (patient demographics filtering, demographic filters, etc.)
        st.markdown("""
        <div style="
            background-color: #28546B;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 0.5rem;
        ">
            📍 <strong>Non-Clinical XML Detected</strong>
        </div>
        """, unsafe_allow_html=True)
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
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "📋 Summary", 
        "🏥 Clinical Codes", 
        "💊 Medications", 
        "📊 Refsets", 
        "⚠️ Pseudo-Refsets", 
        "📝 Pseudo-Refset Members", 
        "📊 Analytics",
        "👪 Child Code Finder"
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
        st.markdown("""
        <div style="
            background-color: #28546B;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 0.5rem;
        ">
            The terminology server module failed to import. Please check the installation.
        </div>
        """, unsafe_allow_html=True)
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
        st.markdown("""
        <div style="
            background-color: #28546B;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 0.5rem;
        ">
            ℹ️ No clinical codes found for expansion analysis
        </div>
        """, unsafe_allow_html=True)
        return
    
    # Render the expansion interface
    render_expansion_tab_content(all_clinical_codes)


def render_results_tabs(results):
    """Render all result tabs with new 5-tab structure."""
    # Check if we have results OR if we have XML content (for patient demographics filtering XMLs)
    # For patient demographics XMLs, results might be empty dict {} but that's still valid
    has_clinical_results = 'results' in st.session_state and st.session_state.results is not None
    has_xml_content = 'xml_content' in st.session_state and st.session_state.xml_content
    
    # Show tabs if we have either clinical results or XML content (including empty results from patient demographics XMLs)
    if has_clinical_results or has_xml_content:
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
        st.markdown("""
        <div style="
            background-color: #28546B;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 0.5rem;
        ">
            Upload EMIS XML files to analyze search logic, visualize report structures, and translate clinical codes to UK SNOMED using MKB 226.
        </div>
        """, unsafe_allow_html=True)
