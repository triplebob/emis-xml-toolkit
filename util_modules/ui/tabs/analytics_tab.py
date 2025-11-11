"""
Analytics tab rendering functions.

This module handles rendering of the analytics tab with:
- Processing analytics and quality metrics display
- File information with color-coded performance indicators
- XML statistics and structure analysis
- Lookup statistics and performance metrics
- Translation success rates with detailed breakdowns
- Processing time and performance analysis
- Export functionality for analytics data

All functionality is preserved including:
- UI styling and metrics display with proper color coding
- Session state management for analytics data
- Error handling and validation
- Enhanced analytics export capabilities
"""

from .common_imports import *
from .tab_helpers import (
    _build_report_type_caption
)


def render_analytics_tab():
    """
    Render the analytics tab with audit statistics and export capability.
    
    This function displays comprehensive analytics including:
    - File processing information with performance indicators
    - XML structure analysis with color-coded metrics
    - Translation accuracy metrics for clinical codes
    - Quality indicators and validation metrics
    - Export functionality for analytics data
    
    The tab provides detailed insights into:
    - Processing performance and file size metrics
    - Translation success rates for different code types
    - XML structure complexity and quality indicators
    - Report and search analysis results
    
    All metrics include color coding to highlight:
    - Success (green): Good performance/high accuracy
    - Warning (yellow): Moderate performance/accuracy
    - Error (red): Poor performance/low accuracy
    """
    if 'audit_stats' not in st.session_state:
        st.info("🔍 Analytics will appear here after processing an XML file")
        return
    
    audit_stats = st.session_state.audit_stats
    
    st.subheader("📊 Processing Analytics & Quality Metrics")
    
    # File and Processing Information
    st.write("### 📁 File Information")
    
    # Filename in full width
    st.info(f"**Filename:** {audit_stats['xml_stats']['filename']}")
    
    # Metrics in columns with color coding
    col1, col2, col3 = st.columns(3)
    
    with col1:
        file_size_mb = audit_stats['xml_stats']['file_size_bytes'] / (1024 * 1024)
        if file_size_mb > 10:
            st.error(f"**File Size:** {audit_stats['xml_stats']['file_size_bytes']:,} bytes ({file_size_mb:.1f} MB)")
        elif file_size_mb > 1:
            st.warning(f"**File Size:** {audit_stats['xml_stats']['file_size_bytes']:,} bytes ({file_size_mb:.1f} MB)")
        else:
            st.success(f"**File Size:** {audit_stats['xml_stats']['file_size_bytes']:,} bytes ({file_size_mb:.1f} MB)")
    
    with col2:
        processing_time = audit_stats['xml_stats']['processing_time_seconds']
        if processing_time > 120:
            st.error(f"**Processing Time:** {processing_time:.2f}s")
        elif processing_time > 60:
            st.warning(f"**Processing Time:** {processing_time:.2f}s")
        else:
            st.success(f"**Processing Time:** {processing_time:.2f}s")
    
    with col3:
        st.info(f"**Processed:** {audit_stats['xml_stats']['processing_timestamp']}")
    
    # XML Structure Analysis
    st.write("### 🏗️ XML Structure Analysis")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        valuesets = audit_stats['xml_structure']['total_valuesets']
        if valuesets > 50:
            st.error(f"**Total ValueSets:** {valuesets}")
        elif valuesets > 20:
            st.warning(f"**Total ValueSets:** {valuesets}")
        else:
            st.success(f"**Total ValueSets:** {valuesets}")
    
    with col2:
        unique_guids = audit_stats['xml_structure']['unique_emis_guids']
        if unique_guids > 1000:
            st.error(f"**Unique EMIS GUIDs:** {unique_guids:,}")
        elif unique_guids > 500:
            st.warning(f"**Unique EMIS GUIDs:** {unique_guids:,}")
        else:
            st.success(f"**Unique EMIS GUIDs:** {unique_guids:,}")
    
    with col3:
        total_refs = audit_stats['xml_structure']['total_guid_occurrences']
        if total_refs > 2000:
            st.info(f"**Total GUID References:** {total_refs:,}")
        else:
            st.success(f"**Total GUID References:** {total_refs:,}")
    
    with col4:
        dup_rate = audit_stats['xml_structure']['duplicate_guid_ratio']
        if dup_rate > 20:
            st.error(f"**Duplication Rate:** {dup_rate}%")
        elif dup_rate > 10:
            st.warning(f"**Duplication Rate:** {dup_rate}%")
        else:
            st.success(f"**Duplication Rate:** {dup_rate}%")
    
    with col5:
        # Clinical Searches count
        search_results = st.session_state.get('search_results')
        search_count = len(search_results.searches) if search_results and hasattr(search_results, 'searches') else 0
        if search_count > 0:
            st.success(f"**Clinical Searches:** {search_count}")
        else:
            st.info(f"**Clinical Searches:** {search_count}")
    
    with col6:
        # Reports count with breakdown
        report_results = st.session_state.get('report_results')
        if report_results and hasattr(report_results, 'report_breakdown'):
            total_reports = sum(len(reports) for reports in report_results.report_breakdown.values())
            if total_reports > 0:
                st.success(f"**Reports Found:** {total_reports}")
            else:
                st.info(f"**Reports Found:** {total_reports}")
        else:
            st.info(f"**Reports Found:** 0")
    
    # Show folder count in a second row
    st.write("")  # Add some spacing
    col_folder1, col_folder2, col_folder_spacer = st.columns([1, 1, 4])
    
    with col_folder1:
        # Folders count
        analysis = st.session_state.get('search_analysis')
        folder_count = len(analysis.folders) if analysis and hasattr(analysis, 'folders') else 0
        if folder_count > 0:
            st.success(f"**Folders Found:** {folder_count}")
        else:
            st.info(f"**Folders Found:** {folder_count}")
    
    with col_folder2:
        # Report type breakdown as detailed info
        if report_results and hasattr(report_results, 'report_breakdown'):
            breakdown_parts = []
            for report_type, reports in report_results.report_breakdown.items():
                if reports:
                    count = len(reports)
                    breakdown_parts.append(f"{count} {report_type.capitalize()}")
            
            if breakdown_parts:
                breakdown_text = ", ".join(breakdown_parts)
                st.info(f"**Report Types:** {breakdown_text}")
            else:
                st.info(f"**Report Types:** None")
        else:
            st.info(f"**Report Types:** None")
    
    # Enhanced Translation Accuracy using unified pipeline data
    st.write("### 🎯 Translation Accuracy")
    
    # Get unified data for accurate counts
    from .tab_helpers import get_unified_clinical_data
    unified_results = get_unified_clinical_data()
    
    if unified_results:
        # Use unified pipeline data for accurate counts
        clinical_codes = unified_results.get('clinical_codes', [])
        pseudo_members = unified_results.get('clinical_pseudo_members', [])
        medications = unified_results.get('medications', [])
        refsets = unified_results.get('refsets', [])
        pseudo_refsets = unified_results.get('pseudo_refsets', [])
        
        # Calculate found vs total for each category
        clinical_found = len([c for c in clinical_codes if c.get('Mapping Found') == 'Found'])
        clinical_total = len(clinical_codes)
        
        pseudo_members_found = len([c for c in pseudo_members if c.get('Mapping Found') == 'Found'])
        pseudo_members_total = len(pseudo_members)
        
        medications_found = len([m for m in medications if m.get('Mapping Found') == 'Found'])
        medications_total = len(medications)
        
        # Separate search vs report codes
        search_clinical = [c for c in clinical_codes if c.get('Source Type', '').lower() == 'search' or 'search' in c.get('Source Type', '').lower()]
        report_clinical = [c for c in clinical_codes if 'report' in c.get('Source Type', '').lower()]
        
        search_found = len([c for c in search_clinical if c.get('Mapping Found') == 'Found'])
        search_total = len(search_clinical)
        report_found = len([c for c in report_clinical if c.get('Mapping Found') == 'Found'])
        report_total = len(report_clinical)
        
        total_clinical = clinical_total + pseudo_members_total
        total_found = clinical_found + pseudo_members_found
    else:
        # Fallback to legacy data if unified not available
        trans_accuracy = audit_stats['translation_accuracy']
        report_results = st.session_state.get('report_results')
        report_clinical_count = 0
        if report_results and hasattr(report_results, 'clinical_codes'):
            report_clinical_count = len(report_results.clinical_codes)
        
        search_found = trans_accuracy['clinical_codes']['found']
        search_total = trans_accuracy['clinical_codes']['total']
        report_found = report_clinical_count
        report_total = report_clinical_count
        total_clinical = search_total + report_clinical_count
        total_found = search_found + report_clinical_count
        
        # Legacy fallback values
        pseudo_members_found = 0
        pseudo_members_total = 0
        medications_found = trans_accuracy.get('medications', {}).get('found', 0)
        medications_total = trans_accuracy.get('medications', {}).get('total', 0)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Search Codes**")
        
        # Search clinical codes
        render_success_rate_metric(
            "Search Clinical Codes",
            search_found,
            search_total
        )
        
        # Original clinical codes metric (for reference)
        st.caption(f"Parsed from clinical searches")
    
    with col2:
        st.markdown("**Report Codes**") 
        
        # Report clinical codes
        render_success_rate_metric(
            "Report Clinical Codes",
            report_found,
            report_total
        )
        
        if report_total > 0:
            st.caption(f"Parsed from report structures")
        else:
            st.caption("No reports found in XML")
    
    with col3:
        st.markdown("**Combined Totals**")
        
        # Combined clinical codes
        render_success_rate_metric(
            "All Clinical Codes",
            total_found,
            total_clinical
        )
        
        st.caption(f"Search + Report codes combined")
    
    # Additional metrics section
    st.write("---")
    col_additional1, col_additional2 = st.columns(2)
    
    with col_additional1:
        st.markdown("**Other Standalone Items**")
        
        render_success_rate_metric(
            "Standalone Medications",
            medications_found,
            medications_total
        )
    
    with col_additional2:
        st.markdown("**Pseudo-Refset Members**")
        
        # Clinical members (unified data)
        render_success_rate_metric(
            "Clinical Members",
            pseudo_members_found,
            pseudo_members_total
        )
        
        # Medication members - separate pseudo medication members if available
        if unified_results:
            # Count medication pseudo-members if they exist
            medication_pseudo_found = 0
            medication_pseudo_total = 0
            st.info("Medication Members: No items to process")
        else:
            # Legacy fallback
            medication_pseudo_found = trans_accuracy.get('pseudo_refset_medications', {}).get('found', 0)
            medication_pseudo_total = trans_accuracy.get('pseudo_refset_medications', {}).get('total', 0)
            render_success_rate_metric(
                "Medication Members",
                medication_pseudo_found,
                medication_pseudo_total
            )
    
    # Enhanced overall success rate including report data
    st.write("---")
    
    # Calculate overall metrics using unified data
    if unified_results:
        # Use unified pipeline data for accurate overall metrics
        overall_found = clinical_found + pseudo_members_found + medications_found
        overall_total = clinical_total + pseudo_members_total + medications_total
        
        col_overall1, col_overall2 = st.columns(2)
        
        with col_overall1:
            render_success_rate_metric(
                "Overall Success Rate",
                overall_found,
                overall_total
            )
            st.caption("All codes (clinical + pseudo-members + medications)")
        
        with col_overall2:
            render_success_rate_metric(
                "Combined Clinical Success",
                total_found,
                total_clinical
            )
            st.caption("Clinical codes + pseudo-members combined")
    else:
        # Legacy fallback
        original_overall_found = trans_accuracy['overall']['found']
        original_overall_total = trans_accuracy['overall']['total']
        enhanced_overall_found = original_overall_found + report_total
        enhanced_overall_total = original_overall_total + report_total
        
        col_overall1, col_overall2 = st.columns(2)
        
        with col_overall1:
            render_success_rate_metric(
                "Original Overall Success",
                original_overall_found,
                original_overall_total
            )
            st.caption("Based on main translation only")
        
        with col_overall2:
            render_success_rate_metric(
                "Enhanced Overall Success",
                enhanced_overall_found,
                enhanced_overall_total
            )
            st.caption("Including search + report codes")
    
    # Code System Breakdown and Quality Indicators side by side
    breakdown_col, quality_col = st.columns([1, 2])
    
    with breakdown_col:
        st.write("### ⚙️ Code System Breakdown")
        code_systems_df = pd.DataFrame(list(audit_stats['code_systems'].items()), 
                                      columns=['Code System', 'Count'])
        code_systems_df = code_systems_df.sort_values('Count', ascending=False)
        st.dataframe(code_systems_df, width='stretch')
    
    with quality_col:
        st.write("### ✅ Quality Indicators")
        quality = audit_stats['quality_metrics']
        
        col1, col2 = st.columns(2)
        with col1:
            # Include children flags
            include_children = quality['has_include_children_flags']
            if include_children > 0:
                st.success(f"**Codes With 'Include Children = True':** {include_children}")
            else:
                st.info(f"**Codes With 'Include Children = True':** {include_children}")
            
            # Display names present
            display_names = quality['has_display_names']
            total_references = audit_stats['xml_structure']['total_guid_occurrences']
            if total_references > 0:
                display_percentage = (display_names / total_references) * 100
                if display_percentage >= 90:
                    st.success(f"**Display Names Present:** {display_names} ({display_percentage:.0f}%)")
                elif display_percentage >= 70:
                    st.warning(f"**Display Names Present:** {display_names} ({display_percentage:.0f}%)")
                else:
                    st.error(f"**Display Names Present:** {display_names} ({display_percentage:.0f}%)")
            else:
                st.info(f"**Display Names Present:** {display_names}")
            
            # EMISINTERNAL codes (should be excluded)
            emis_internal = quality['emisinternal_codes_excluded']
            if emis_internal > 0:
                st.warning(f"**EMISINTERNAL Codes (Excluded):** {emis_internal}")
            else:
                st.success(f"**EMISINTERNAL Codes (Excluded):** {emis_internal}")
        
        with col2:
            # Table context
            table_context = quality['has_table_context']
            if table_context > 0:
                st.success(f"**Table Context Available:** {table_context}")
            else:
                st.info(f"**Table Context Available:** {table_context}")
            
            # Column context
            column_context = quality['has_column_context']
            if column_context > 0:
                st.success(f"**Column Context Available:** {column_context}")
            else:
                st.info(f"**Column Context Available:** {column_context}")
            
            # Add a spacer to balance the layout
            st.write("")
    
    # Export Functionality as fragments
    st.write("### 📤 Export Analytics")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Enhanced JSON export as fragment
        @st.fragment
        def json_export_fragment():
            from util_modules.export_handlers.ui_export_manager import UIExportManager
            export_manager = UIExportManager()
            export_manager.render_enhanced_json_export(audit_stats)
        
        json_export_fragment()
    
    with col2:
        # Summary report export as fragment
        @st.fragment
        def summary_report_fragment():
            from ...utils.audit import create_validation_report
            summary_report = create_validation_report(audit_stats)
            from util_modules.export_handlers.ui_export_manager import UIExportManager
            export_manager = UIExportManager()
            export_manager.render_text_download_button(
                content=summary_report,
                filename=f"processing_report_{audit_stats['xml_stats']['filename']}.txt",
                label="📋 Download Summary Report",
                key="download_summary_report"
            )
        
        summary_report_fragment()
    
    with col3:
        # Analytics export as fragment
        @st.fragment
        def analytics_export_fragment():
            from util_modules.export_handlers.ui_export_manager import UIExportManager
            export_manager = UIExportManager()
            export_manager.render_analytics_export(audit_stats)
        
        analytics_export_fragment()