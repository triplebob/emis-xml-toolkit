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
from ...core.session_state import SessionStateKeys
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
        st.markdown("""
        <div style="
            background-color: #28546B;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 1rem;
        ">
            🔍 Analytics will appear here after processing an XML file
        </div>
        """, unsafe_allow_html=True)
        return
    
    audit_stats = st.session_state.audit_stats
    
    st.subheader("📊 Processing Analytics & Quality Metrics")
    
    # File and Processing Information
    st.write("### 📁 File Information")
    
    with st.container(border=True):
        # Filename in full width
        st.markdown(f"""
        <div style="
            background-color: #28546B;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 1rem;
        ">
            <strong>Filename:</strong> {audit_stats['xml_stats']['filename']}
        </div>
        """, unsafe_allow_html=True)
        
        # Metrics in columns with color coding
        col1, col2, col3 = st.columns(3)
        
        with col1:
            file_size_mb = audit_stats['xml_stats']['file_size_bytes'] / (1024 * 1024)
            if file_size_mb > 10:
                st.markdown(f"""
                <div style="
                    background-color: #660022;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>File Size:</strong> {audit_stats['xml_stats']['file_size_bytes']:,} bytes ({file_size_mb:.1f} MB)
                </div>
                """, unsafe_allow_html=True)
            elif file_size_mb > 1:
                st.markdown(f"""
                <div style="
                    background-color: #7A5F0B;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>File Size:</strong> {audit_stats['xml_stats']['file_size_bytes']:,} bytes ({file_size_mb:.1f} MB)
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="
                    background-color: #1F4E3D;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>File Size:</strong> {audit_stats['xml_stats']['file_size_bytes']:,} bytes ({file_size_mb:.1f} MB)
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            processing_time = audit_stats['xml_stats']['processing_time_seconds']
            if processing_time > 120:
                st.markdown(f"""
                <div style="
                    background-color: #660022;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Processing Time:</strong> {processing_time:.2f}s
                </div>
                """, unsafe_allow_html=True)
            elif processing_time > 60:
                st.markdown(f"""
                <div style="
                    background-color: #7A5F0B;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Processing Time:</strong> {processing_time:.2f}s
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="
                    background-color: #1F4E3D;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Processing Time:</strong> {processing_time:.2f}s
                </div>
                """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div style="
                background-color: #28546B;
                padding: 0.75rem;
                border-radius: 0.5rem;
                color: #FAFAFA;
                text-align: left;
                margin-bottom: 1rem;
            ">
                <strong>Processed:</strong> {audit_stats['xml_stats']['processing_timestamp']}
            </div>
            """, unsafe_allow_html=True)
    
    # XML Structure Analysis
    with st.container(border=True):
        st.write("### 🏗️ XML Structure Analysis")
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        with col1:
            valuesets = audit_stats['xml_structure']['total_valuesets']
            if valuesets > 50:
                st.markdown(f"""
                <div style="
                    background-color: #660022;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Total ValueSets:</strong> {valuesets}
                </div>
                """, unsafe_allow_html=True)
            elif valuesets > 20:
                st.markdown(f"""
                <div style="
                    background-color: #7A5F0B;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Total ValueSets:</strong> {valuesets}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="
                    background-color: #1F4E3D;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Total ValueSets:</strong> {valuesets}
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            unique_guids = audit_stats['xml_structure']['unique_emis_guids']
            if unique_guids > 1000:
                st.markdown(f"""
                <div style="
                    background-color: #660022;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Unique EMIS GUIDs:</strong> {unique_guids:,}
                </div>
                """, unsafe_allow_html=True)
            elif unique_guids > 500:
                st.markdown(f"""
                <div style="
                    background-color: #7A5F0B;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Unique EMIS GUIDs:</strong> {unique_guids:,}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="
                    background-color: #1F4E3D;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Unique EMIS GUIDs:</strong> {unique_guids:,}
                </div>
                """, unsafe_allow_html=True)
    
        with col3:
            total_refs = audit_stats['xml_structure']['total_guid_occurrences']
            if total_refs > 2000:
                st.markdown(f"""
                <div style="
                    background-color: #28546B;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Total GUID References:</strong> {total_refs:,}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="
                    background-color: #1F4E3D;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Total GUID References:</strong> {total_refs:,}
                </div>
                """, unsafe_allow_html=True)
    
        with col4:
            dup_rate = audit_stats['xml_structure']['duplicate_guid_ratio']
            if dup_rate > 20:
                st.markdown(f"""
                <div style="
                    background-color: #660022;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Duplication Rate:</strong> {dup_rate}%
                </div>
                """, unsafe_allow_html=True)
            elif dup_rate > 10:
                st.markdown(f"""
                <div style="
                    background-color: #7A5F0B;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Duplication Rate:</strong> {dup_rate}%
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="
                    background-color: #1F4E3D;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Duplication Rate:</strong> {dup_rate}%
                </div>
                """, unsafe_allow_html=True)
    
        with col5:
            # Clinical Searches count
            search_results = st.session_state.get(SessionStateKeys.SEARCH_RESULTS)
            search_count = len(search_results.searches) if search_results and hasattr(search_results, 'searches') else 0
            if search_count > 0:
                st.markdown(f"""
                <div style="
                    background-color: #1F4E3D;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Clinical Searches:</strong> {search_count}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="
                    background-color: #28546B;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Clinical Searches:</strong> {search_count}
                </div>
                """, unsafe_allow_html=True)
    
        with col6:
            # Reports count with breakdown
            report_results = st.session_state.get(SessionStateKeys.REPORT_RESULTS)
            if report_results and hasattr(report_results, 'report_breakdown'):
                total_reports = sum(len(reports) for reports in report_results.report_breakdown.values())
                if total_reports > 0:
                    st.markdown(f"""
                    <div style="
                        background-color: #1F4E3D;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1rem;
                    ">
                        <strong>Reports Found:</strong> {total_reports}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="
                        background-color: #28546B;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1rem;
                    ">
                        <strong>Reports Found:</strong> {total_reports}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="
                    background-color: #28546B;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Reports Found:</strong> 0
                </div>
                """, unsafe_allow_html=True)
    
        # Show folder count in a second row
        col_folder1, col_folder2, col_folder_spacer = st.columns([1, 1, 4])
        
        with col_folder1:
            # Folders count
            analysis = st.session_state.get(SessionStateKeys.SEARCH_ANALYSIS)
            folder_count = len(analysis.folders) if analysis and hasattr(analysis, 'folders') else 0
            if folder_count > 0:
                st.markdown(f"""
                <div style="
                    background-color: #1F4E3D;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Folders Found:</strong> {folder_count}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="
                    background-color: #28546B;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Folders Found:</strong> {folder_count}
                </div>
                """, unsafe_allow_html=True)
    
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
                    st.markdown(f"""
                    <div style="
                        background-color: #28546B;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1rem;
                    ">
                        <strong>Report Types:</strong> {breakdown_text}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style="
                        background-color: #28546B;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1rem;
                    ">
                        <strong>Report Types:</strong> None
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="
                    background-color: #28546B;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Report Types:</strong> None
                </div>
                """, unsafe_allow_html=True)
    
    # Enhanced Translation Accuracy using unified pipeline data
    with st.container(border=True):
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
            report_results = st.session_state.get(SessionStateKeys.REPORT_RESULTS)
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
                st.markdown("""
                <div style="
                    background-color: #28546B;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    Medication Members: No items to process
                </div>
                """, unsafe_allow_html=True)
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
                st.markdown(f"""
                <div style="
                    background-color: #1F4E3D;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Codes With 'Include Children = True':</strong> {include_children}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="
                    background-color: #28546B;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Codes With 'Include Children = True':</strong> {include_children}
                </div>
                """, unsafe_allow_html=True)
            
            # Display names present
            display_names = quality['has_display_names']
            total_references = audit_stats['xml_structure']['total_guid_occurrences']
            if total_references > 0:
                display_percentage = (display_names / total_references) * 100
                if display_percentage >= 90:
                    st.markdown(f"""
                    <div style="
                        background-color: #1F4E3D;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1rem;
                    ">
                        <strong>Display Names Present:</strong> {display_names} ({display_percentage:.0f}%)
                    </div>
                    """, unsafe_allow_html=True)
                elif display_percentage >= 70:
                    st.markdown(f"""
                    <div style="
                        background-color: #7A5F0B;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1rem;
                    ">
                        <strong>Display Names Present:</strong> {display_names} ({display_percentage:.0f}%)
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="
                        background-color: #660022;
                        padding: 0.75rem;
                        border-radius: 0.5rem;
                        color: #FAFAFA;
                        text-align: left;
                        margin-bottom: 1rem;
                    ">
                        <strong>Display Names Present:</strong> {display_names} ({display_percentage:.0f}%)
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="
                    background-color: #28546B;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Display Names Present:</strong> {display_names}
                </div>
                """, unsafe_allow_html=True)
            
            # EMISINTERNAL codes (should be excluded)
            emis_internal = quality['emisinternal_codes_excluded']
            if emis_internal > 0:
                st.markdown(f"""
                <div style="
                    background-color: #7A5F0B;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>EMISINTERNAL Codes (Excluded):</strong> {emis_internal}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="
                    background-color: #1F4E3D;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>EMISINTERNAL Codes (Excluded):</strong> {emis_internal}
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            # Table context
            table_context = quality['has_table_context']
            if table_context > 0:
                st.markdown(f"""
                <div style="
                    background-color: #1F4E3D;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Table Context Available:</strong> {table_context}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="
                    background-color: #28546B;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Table Context Available:</strong> {table_context}
                </div>
                """, unsafe_allow_html=True)
            
            # Column context
            column_context = quality['has_column_context']
            if column_context > 0:
                st.markdown(f"""
                <div style="
                    background-color: #1F4E3D;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Column Context Available:</strong> {column_context}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="
                    background-color: #28546B;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    color: #FAFAFA;
                    text-align: left;
                    margin-bottom: 1rem;
                ">
                    <strong>Column Context Available:</strong> {column_context}
                </div>
                """, unsafe_allow_html=True)
            
            # Add a spacer to balance the layout
            st.write("")
    
    # Export Functionality as fragments
    st.write("### 📤 Export Analytics")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Enhanced JSON export as fragment
        @st.fragment
        def json_export_fragment():
            from utils.export_handlers.ui_export_manager import UIExportManager
            export_manager = UIExportManager()
            export_manager.render_enhanced_json_export(audit_stats)
        
        json_export_fragment()
    
    with col2:
        # Summary report export as fragment
        @st.fragment
        def summary_report_fragment():
            from ...utils.audit import create_validation_report
            summary_report = create_validation_report(audit_stats)
            from utils.export_handlers.ui_export_manager import UIExportManager
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
            from utils.export_handlers.ui_export_manager import UIExportManager
            export_manager = UIExportManager()
            export_manager.render_analytics_export(audit_stats)
        
        analytics_export_fragment()
