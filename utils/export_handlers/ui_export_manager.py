"""
UI Export Manager
Centralizes and enhances export functionality across all UI tabs
"""

import streamlit as st
import pandas as pd
import io
import gc
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from .clinical_code_export import ClinicalCodeExportHandler
from .search_export import SearchExportHandler
# Import moved to function level to avoid circular dependency
from ..core import ReportClassifier, SearchManager
from ..core.session_state import SessionStateKeys
from ..utils.export_debug import log_export_created, log_export_cleanup, track_export_object, log_memory_after_export, force_gc_and_log


class UIExportManager:
    """Manages all export functionality across the UI with enhanced options"""
    
    def __init__(self, analysis=None):
        self.analysis = analysis
        self.clinical_export = ClinicalCodeExportHandler()
        self.search_export = SearchExportHandler(analysis) if analysis else None
    
    def render_download_button(
        self,
        data: pd.DataFrame, 
        label: str, 
        filename_prefix: str,
        xml_filename: Optional[str] = None,
        key: Optional[str] = None,
        show_preview: bool = True
    ) -> None:
        """
        Render a lazy single-click CSV download button using Streamlit fragments.
        Only generates CSV when button is actually clicked.
        
        Args:
            data: DataFrame to export
            label: Button label text
            filename_prefix: Prefix for the generated filename
            xml_filename: Optional XML filename to include in export name
            key: Optional unique key for the button
        """
        # Debug: Log function entry (only when debug mode enabled)
        import sys
        if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
            print(f"[FRAGMENT DEBUG] render_download_button called: {label}, key: {key}, data rows: {len(data)}", file=sys.stderr)
        
        if data.empty:
            return
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if xml_filename and xml_filename.strip():
            # Clean filename for filesystem compatibility
            clean_xml_filename = xml_filename.replace(' ', '_').replace('.xml', '')
            filename = f"{filename_prefix}_{clean_xml_filename}_{timestamp}.csv"
        else:
            filename = f"{filename_prefix}_{timestamp}.csv"
        
        # Cache key for lazy generation
        simple_key = (key or filename_prefix).replace('download_', '').replace('_all_codes', '')
        cache_key = f'csv_export_{simple_key}_ready'
        
        # OPTIMIZED SINGLE-CLICK: Generate immediately on button press, then auto-download
        @st.fragment  
        def download_button_fragment():
            if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
                print(f"[FRAGMENT DEBUG] Optimized single-click download for {simple_key}", file=sys.stderr)
            
            # Check if we already have generated CSV ready for download
            if cache_key in st.session_state:
                # CSV is ready - show download button
                csv_data = st.session_state[cache_key]
                # Clean label to prevent emoji duplication
                clean_label = self._clean_label_emojis(label)
                downloaded = st.download_button(
                    label=f"📥 {clean_label}",
                    data=csv_data,
                    file_name=filename,
                    mime="text/csv",
                    key=f"{key}_download_ready",
                    help="Click to download your CSV file"
                )
                
                # Clean up after successful download
                if downloaded:
                    del st.session_state[cache_key]
                    if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
                        print(f"[DOWNLOAD DEBUG] CSV downloaded and cleaned up for {filename_prefix}", file=sys.stderr)
            else:
                # CSV not ready - show generate button that creates CSV and immediately switches to download
                # Clean label to prevent emoji duplication
                clean_label = self._clean_label_emojis(label)
                if st.button(f"📥 {clean_label}", key=key, help=f"Generate CSV: {filename}"):
                    with st.spinner("🔄 Generating CSV..."):
                        try:
                            # LAZY: Generate CSV only when clicked
                            clean_data = data.copy()
                            for col in clean_data.columns:
                                if clean_data[col].dtype == 'object':
                                    clean_data[col] = clean_data[col].astype(str).str.replace(r'[🔍📝⚕️📊📋📈📄🏥💊⬇️✅❌🔄📥📈📋]+\s*', '', regex=True).str.replace(r'\s+', ' ', regex=True).str.strip()
                            
                            csv_buffer = io.StringIO()
                            clean_data.to_csv(csv_buffer, index=False)
                            csv_data = csv_buffer.getvalue()
                            
                            # Debug logging
                            log_export_created("UI Export Manager", "CSV", len(csv_data.encode('utf-8')), filename_prefix)
                            track_export_object(csv_buffer, "UI Export Manager", "CSV", filename_prefix)
                            log_memory_after_export("UI Export Manager", "CSV")
                            
                            # Store CSV for immediate download
                            st.session_state[cache_key] = csv_data
                            
                            # Clean up generation memory
                            del clean_data, csv_buffer
                            gc.collect()
                            
                            # Auto-rerun to show download button immediately
                            st.rerun()
                            
                        except Exception as e:
                            if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
                                print(f"[ERROR] CSV generation failed: {str(e)}", file=sys.stderr)
                            st.error(f"Failed to generate CSV: {str(e)}")
                            
                    # Show success message
                    st.success("✅ CSV generated! Page will refresh to show download button...")
                    
                # Show preview caption if enabled
                if show_preview:
                    st.caption(f"Will generate CSV with {len(data)} rows × {len(data.columns)} columns")
        
        # Execute the fragment
        download_button_fragment()
    
    def render_enhanced_export_section(self, 
                                     data: List[Dict], 
                                     section_name: str,
                                     export_types: List[str] = None,
                                     additional_context: Dict = None):
        """
        Render enhanced export section with multiple format options
        
        Args:
            data: Data to export
            section_name: Name of the section (for filename generation)
            export_types: Types of exports to offer ['csv', 'excel', 'json']
            additional_context: Additional context for exports
        """
        if not data:
            return
            
        if export_types is None:
            export_types = ['csv']
        
        # Create export options in columns
        export_cols = st.columns(len(export_types))
        
        for i, export_type in enumerate(export_types):
            with export_cols[i]:
                self._render_export_button(data, section_name, export_type, additional_context)
    
    def render_clinical_codes_export(self, search_reports: List, export_options: Dict = None):
        """Render clinical codes export with advanced filtering"""
        if not search_reports:
            return
            
        st.subheader("🔬 Clinical Codes Export Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Basic Exports:**")
            
            # All codes CSV - direct download
            include_report_codes = st.session_state.get(SessionStateKeys.CLINICAL_INCLUDE_REPORT_CODES, True)
            show_code_sources = st.session_state.get(SessionStateKeys.CLINICAL_SHOW_CODE_SOURCES, True)
            
            filename, content = self.clinical_export.export_all_codes_as_csv(
                search_reports, 
                include_search_context=True,
                include_source_tracking=show_code_sources,
                include_report_codes=include_report_codes
            )
            st.download_button(
                label="📥 Export All Codes (CSV)",
                data=content,
                file_name=filename,
                mime="text/csv",
                key="export_all_codes_csv"
            )
            
        
        
        st.markdown("---")
        
        # Statistics
        if st.checkbox("📊 Show Code Statistics", key="show_code_stats"):
            stats = self.clinical_export.get_code_statistics(search_reports)
            self._render_code_statistics(stats)
    
    def render_search_structure_export(self, analysis, xml_filename: str):
        """Render search structure export options"""
        if not analysis or not analysis.reports:
            return
            
        st.subheader("🔍 Search Structure Export Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Individual Searches:**")
            st.caption("Each search can be exported with full breakdown")
            
            # Show per-search export info
            search_count = len(analysis.reports)
            child_searches = len([r for r in analysis.reports if r.parent_guid])
            st.metric("Available Exports", f"{search_count} searches", 
                     f"{child_searches} child searches" if child_searches > 0 else "")
        
        with col2:
            st.markdown("**Bulk Export Options:**")
            
            # Bulk ZIP export removed due to memory performance issues
            st.info("🔄 Bulk ZIP export has been removed due to memory performance issues. Individual exports are available above.")
    
    def _render_export_button(self, data: List[Dict], section_name: str, 
                            export_type: str, additional_context: Dict = None):
        """Render individual export button"""
        if export_type == 'csv':
            filename = self._generate_filename(section_name, 'csv')
            df = pd.DataFrame(data)
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()
            
            # Debug logging for export file creation
            log_export_created("Export Manager", "CSV", len(csv_data.encode('utf-8')), section_name)
            track_export_object(csv_buffer, "Export Manager", "CSV", section_name)
            
            st.download_button(
                label=f"📥 CSV",
                data=csv_data,
                file_name=filename,
                mime="text/csv",
                key=f"export_{section_name}_csv"
            )
            
            # Log memory usage after export creation
            log_memory_after_export("Export Manager", "CSV")
            
            # Clear cache after export to free memory
            del df, csv_buffer
            
            # Force cache clearing for large CSV exports
            if len(data) > 10000:  # Large export threshold
                self.clear_export_cache()
            
        elif export_type == 'excel':
            filename = self._generate_filename(section_name, 'xlsx')
            df = pd.DataFrame(data)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Data', index=False)
                
                # Add metadata sheet if additional context provided
                if additional_context:
                    metadata_df = pd.DataFrame(list(additional_context.items()), 
                                             columns=['Property', 'Value'])
                    metadata_df.to_excel(writer, sheet_name='Metadata', index=False)
            
            output.seek(0)
            excel_data = output.getvalue()
            
            # Debug logging for export file creation
            log_export_created("Export Manager", "Excel", len(excel_data), section_name)
            track_export_object(output, "Export Manager", "Excel", section_name)
            
            st.download_button(
                label=f"📊 Excel",
                data=excel_data,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"export_{section_name}_excel"
            )
            
            # Log memory usage and clear cache after export to free memory
            log_memory_after_export("Export Manager", "Excel")
            del df, output
            
            # Force cache clearing for large Excel exports
            if len(data) > 5000:  # Excel is heavier, lower threshold
                self.clear_export_cache()
            
        elif export_type == 'json':
            import json
            filename = self._generate_filename(section_name, 'json')
            
            export_data = {
                'data': data,
                'metadata': additional_context or {},
                'export_timestamp': datetime.now().isoformat(),
                'export_tool': 'ClinXML'
            }
            
            st.download_button(
                label=f"📄 JSON",
                data=json.dumps(export_data, indent=2, default=str),
                file_name=filename,
                mime="application/json",
                key=f"export_{section_name}_json"
            )
            
            # Clear cache after export to free memory
            del export_data
    
    def render_cached_excel_download(self, cached_data: Dict, report_name: str, report_id: str, button_key: str = None) -> None:
        """
        Render Excel download button for cached export data (with error handling)
        
        Args:
            cached_data: Dictionary containing 'content'/'filename' keys or 'error' key
            report_name: Name of the report for help text
            report_id: ID of the report for unique keys
            button_key: Optional custom key suffix
        """
        if not cached_data:
            return
        
        key_suffix = button_key or report_id
        
        # Handle error state
        if 'error' in cached_data:
            st.button(
                "📊 Excel",
                disabled=True,
                help=f"Excel export error: {cached_data['error']}",
                key=f"export_excel_error_{key_suffix}"
            )
        # Handle successful export
        elif 'content' in cached_data and 'filename' in cached_data:
            st.download_button(
                label="📊 Excel",
                data=cached_data['content'],
                file_name=cached_data['filename'],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help=f"Download Excel export for: {report_name}",
                key=f"export_excel_nav_{key_suffix}"
            )
    
    def render_cached_json_download(self, cached_data: Dict, report_name: str, report_id: str, button_key: str = None) -> None:
        """
        Render JSON download button for cached export data (with error handling)
        
        Args:
            cached_data: Dictionary containing 'content'/'filename' keys or 'error' key
            report_name: Name of the report for help text
            report_id: ID of the report for unique keys
            button_key: Optional custom key suffix
        """
        if not cached_data:
            return
        
        key_suffix = button_key or report_id
        
        # Handle error state
        if 'error' in cached_data:
            st.button(
                "📋 JSON",
                disabled=True,
                help=f"JSON export error: {cached_data['error']}",
                key=f"export_json_error_{key_suffix}"
            )
        # Handle successful export
        elif 'content' in cached_data and 'filename' in cached_data:
            st.download_button(
                label="📋 JSON",
                data=cached_data['content'],
                file_name=cached_data['filename'],
                mime="application/json",
                help=f"Download JSON export for: {report_name}",
                key=f"export_json_nav_{key_suffix}"
            )
    
    def render_report_export_buttons(self, excel_cache_data: Optional[Dict] = None, 
                                   json_cache_data: Optional[Dict] = None,
                                   report_name: str = "", report_id: str = "",
                                   show_excel: bool = True, show_json: bool = True) -> None:
        """
        Render both Excel and JSON export buttons for a report
        
        Args:
            excel_cache_data: Cached Excel export data
            json_cache_data: Cached JSON export data
            report_name: Name of the report
            report_id: ID of the report
            show_excel: Whether to show Excel button
            show_json: Whether to show JSON button
        """
        col1, col2 = st.columns(2)
        
        with col1:
            if show_excel and excel_cache_data:
                self.render_cached_excel_download(excel_cache_data, report_name, report_id)
        
        with col2:
            if show_json and json_cache_data:
                self.render_cached_json_download(json_cache_data, report_name, report_id)
    
    def render_text_download_button(self, content: str, filename: str, label: str = "📄 Download TXT", 
                                   key: str = None, help_text: str = None) -> None:
        """
        Render a text download button for analysis exports
        
        Args:
            content: Text content to download
            filename: Filename for the download
            label: Button label
            key: Optional unique key
            help_text: Optional help text
        """
        st.download_button(
            label=label,
            data=content,
            file_name=filename,
            mime="text/plain",
            help=help_text,
            key=key
        )
    
    def render_json_download_button(self, content: str, filename: str, label: str = "📊 Download JSON",
                                   key: str = None, help_text: str = None) -> None:
        """
        Render a JSON download button for analysis exports
        
        Args:
            content: JSON content to download
            filename: Filename for the download  
            label: Button label
            key: Optional unique key
            help_text: Optional help text
        """
        st.download_button(
            label=label,
            data=content,
            file_name=filename,
            mime="application/json",
            help=help_text,
            key=key
        )
    
    def render_cached_analysis_download_buttons(self, txt_content: str = None, txt_filename: str = None,
                                              json_cache_key: str = None, 
                                              base_filename: str = "", timestamp: str = "") -> None:
        """
        Render analysis export buttons (TXT and JSON) in columns
        
        Args:
            txt_content: Text content for TXT download
            txt_filename: Filename for TXT download
            json_cache_key: Session state key for cached JSON data
            base_filename: Base filename for automatic naming
            timestamp: Timestamp for filename generation
        """
        col1, col2 = st.columns(2)
        
        with col1:
            if txt_content and txt_filename:
                self.render_text_download_button(
                    content=txt_content,
                    filename=txt_filename,
                    key=f"txt_download_{base_filename}"
                )
        
        with col2:
            if json_cache_key and json_cache_key in st.session_state:
                filename, json_content = st.session_state[json_cache_key]
                self.render_json_download_button(
                    content=json_content,
                    filename=filename,
                    key=f"json_download_{base_filename}"
                )
    
    def render_cached_excel_json_buttons(self, excel_cache_key: str = None, json_cache_key: str = None,
                                        base_key: str = "") -> None:
        """
        Render Excel and JSON download buttons for search analysis
        
        Args:
            excel_cache_key: Session state key for cached Excel data
            json_cache_key: Session state key for cached JSON data  
            base_key: Base key for button identification
        """
        col1, col2 = st.columns(2)
        
        with col1:
            if excel_cache_key and excel_cache_key in st.session_state:
                filename, content = st.session_state[excel_cache_key]
                st.download_button(
                    label="📊 Excel",
                    data=content,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"excel_download_{base_key}"
                )
        
        with col2:
            if json_cache_key and json_cache_key in st.session_state:
                json_filename, json_content = st.session_state[json_cache_key]
                st.download_button(
                    label="📥 Download JSON",
                    data=json_content,
                    file_name=json_filename,
                    mime="application/json",
                    key=f"json_download_{base_key}"
                )
    
    def render_master_json_download(self, master_cache_key: str = "master_export_ready") -> None:
        """
        Render master JSON export download button
        
        Args:
            master_cache_key: Session state key for master export data
        """
        if st.session_state.get(master_cache_key):
            master_filename, master_content = st.session_state[master_cache_key]
            st.download_button(
                label="📥 Download Master JSON",
                data=master_content,
                file_name=master_filename,
                mime="application/json",
                key="master_json_download"
            )
    
    def clear_export_cache(self):
        """Clear Streamlit caches and force garbage collection after large exports"""
        try:
            # Clear Streamlit caches to free memory
            st.cache_data.clear()
            
            # Force garbage collection
            gc.collect()
            
        except Exception:
            # Silently handle cache clearing errors
            pass
    
    def _clean_label_emojis(self, label: str) -> str:
        """Clean duplicate emojis from button labels to prevent accumulation"""
        import re
        # Remove common download/export emojis that we add programmatically
        # This prevents duplicate emojis when labels already contain them
        clean_label = re.sub(r'[📥📊📄📋🔍⚕️📝📈]+\s*', '', label)
        return clean_label.strip()
    
    def _generate_filename(self, section_name: str, extension: str) -> str:
        """Generate standardized filename"""
        # Clean the section name first, then make it safe for filenames
        clean_name = SearchManager.clean_search_name(section_name)
        safe_name = "".join(c for c in clean_name if c.isalnum() or c in (' ', '-', '_')).strip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        return f"{safe_name}_{timestamp}.{extension}"
    
    def _render_code_statistics(self, stats: Dict):
        """Render clinical code statistics"""
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Codes", stats['total_codes'])
            st.metric("Unique Codes", stats['unique_codes_count'])
        
        with col2:
            st.metric("Refset Codes", stats['refset_codes'])
            st.metric("Hierarchical Codes", stats['hierarchical_codes'])
        
        with col3:
            st.metric("Code Systems", stats['code_systems_count'])
            st.metric("Searches with Codes", stats['searches_with_codes'])
        
        # Show code systems breakdown
        if stats['code_systems']:
            with st.expander("📋 Code Systems Breakdown"):
                for system in stats['code_systems']:
                    st.text(f"• {system}")
    
    
    
    def render_analytics_export(self, audit_stats: Dict[str, Any]):
        """Render analytics export with enhanced metrics including search/report/folder counts"""
        metrics_data = []
        
        # Add file info
        metrics_data.append(['Category', 'Metric', 'Value'])
        metrics_data.append(['File Info', 'Filename', audit_stats['xml_stats']['filename']])
        metrics_data.append(['File Info', 'Size (bytes)', audit_stats['xml_stats']['file_size_bytes']])
        metrics_data.append(['File Info', 'Processing Time (seconds)', audit_stats['xml_stats']['processing_time_seconds']])
        
        # Add structure info
        for key, value in audit_stats['xml_structure'].items():
            metrics_data.append(['XML Structure', key, value])
        
        # Add enhanced structure metrics (searches, reports, folders)
        search_results = st.session_state.get(SessionStateKeys.SEARCH_RESULTS)
        search_count = len(search_results.searches) if search_results and hasattr(search_results, 'searches') else 0
        metrics_data.append(['XML Structure', 'clinical_searches_found', search_count])
        
        report_results = st.session_state.get(SessionStateKeys.REPORT_RESULTS)
        if report_results and hasattr(report_results, 'report_breakdown'):
            total_reports = sum(len(reports) for reports in report_results.report_breakdown.values())
            metrics_data.append(['XML Structure', 'total_reports_found', total_reports])
            
            # Add individual report type counts
            for report_type, reports in report_results.report_breakdown.items():
                if reports:
                    metrics_data.append(['XML Structure', f'{report_type}_reports_found', len(reports)])
        else:
            metrics_data.append(['XML Structure', 'total_reports_found', 0])
        
        analysis = st.session_state.get(SessionStateKeys.SEARCH_ANALYSIS)
        folder_count = len(analysis.folders) if analysis and hasattr(analysis, 'folders') else 0
        metrics_data.append(['XML Structure', 'folders_found', folder_count])
        
        # Add translation accuracy
        for category, stats in audit_stats['translation_accuracy'].items():
            for metric, value in stats.items():
                metrics_data.append(['Translation Accuracy', f"{category}_{metric}", value])
        
        # Add enhanced translation accuracy including report data
        report_clinical_count = 0
        if report_results and hasattr(report_results, 'clinical_codes'):
            report_clinical_count = len(report_results.clinical_codes)
        
        # Enhanced clinical codes breakdown
        search_found = audit_stats['translation_accuracy']['clinical_codes']['found']
        search_total = audit_stats['translation_accuracy']['clinical_codes']['total']
        total_clinical = search_total + report_clinical_count
        total_found = search_found + report_clinical_count  # Report codes always found
        
        metrics_data.append(['Enhanced Translation', 'search_clinical_codes_found', search_found])
        metrics_data.append(['Enhanced Translation', 'search_clinical_codes_total', search_total])
        metrics_data.append(['Enhanced Translation', 'report_clinical_codes_found', report_clinical_count])
        metrics_data.append(['Enhanced Translation', 'report_clinical_codes_total', report_clinical_count])
        metrics_data.append(['Enhanced Translation', 'combined_clinical_codes_found', total_found])
        metrics_data.append(['Enhanced Translation', 'combined_clinical_codes_total', total_clinical])
        
        # Add quality metrics
        for key, value in audit_stats['quality_metrics'].items():
            metrics_data.append(['Quality Metrics', key, value])
        
        # Use lazy CSV export for analytics
        metrics_df = pd.DataFrame(metrics_data[1:], columns=metrics_data[0])
        filename = f"analytics_{audit_stats['xml_stats']['filename']}.csv"
        
        # Use the optimized single-click lazy pattern (without preview caption)
        self.render_download_button(
            data=metrics_df,
            label="Download Analytics CSV",
            filename_prefix="analytics",
            xml_filename=audit_stats['xml_stats']['filename'],
            key="download_analytics_csv",
            show_preview=False
        )
    
    def render_enhanced_json_export(self, audit_stats: Dict[str, Any]):
        """Render enhanced JSON export with the same enhanced metrics as CSV export"""
        import json
        
        # Start with original audit_stats
        enhanced_stats = audit_stats.copy()
        
        # Add enhanced structure metrics
        search_results = st.session_state.get(SessionStateKeys.SEARCH_RESULTS)
        search_count = len(search_results.searches) if search_results and hasattr(search_results, 'searches') else 0
        
        report_results = st.session_state.get(SessionStateKeys.REPORT_RESULTS)
        total_reports = 0
        report_breakdown = {}
        if report_results and hasattr(report_results, 'report_breakdown'):
            total_reports = sum(len(reports) for reports in report_results.report_breakdown.values())
            for report_type, reports in report_results.report_breakdown.items():
                if reports:
                    report_breakdown[f'{report_type}_reports_found'] = len(reports)
        
        analysis = st.session_state.get(SessionStateKeys.SEARCH_ANALYSIS)
        folder_count = len(analysis.folders) if analysis and hasattr(analysis, 'folders') else 0
        
        # Add enhanced structure data
        enhanced_stats['enhanced_xml_structure'] = {
            'clinical_searches_found': search_count,
            'total_reports_found': total_reports,
            'folders_found': folder_count,
            **report_breakdown
        }
        
        # Add enhanced translation metrics
        report_clinical_count = 0
        if report_results and hasattr(report_results, 'clinical_codes'):
            report_clinical_count = len(report_results.clinical_codes)
        
        search_found = audit_stats['translation_accuracy']['clinical_codes']['found']
        search_total = audit_stats['translation_accuracy']['clinical_codes']['total']
        total_clinical = search_total + report_clinical_count
        total_found = search_found + report_clinical_count
        
        enhanced_stats['enhanced_translation_accuracy'] = {
            'search_clinical_codes': {
                'found': search_found,
                'total': search_total,
                'success_rate': (search_found / search_total * 100) if search_total > 0 else 0
            },
            'report_clinical_codes': {
                'found': report_clinical_count,
                'total': report_clinical_count,
                'success_rate': 100.0 if report_clinical_count > 0 else 0
            },
            'combined_clinical_codes': {
                'found': total_found,
                'total': total_clinical,
                'success_rate': (total_found / total_clinical * 100) if total_clinical > 0 else 0
            }
        }
        
        # Single-click lazy JSON generation
        filename = f"analytics_{audit_stats['xml_stats']['filename']}.json"
        cache_key = f'analytics_json_export_{filename}'
        
        # Check if we already have generated data
        if cache_key not in st.session_state:
            # Show generate button
            if st.button("📄 Download Enhanced JSON Report", help=f"Generate and download analytics JSON: {filename}", key="analytics_json_export"):
                with st.spinner("Generating analytics JSON..."):
                    # Generate enhanced JSON
                    audit_json = json.dumps(enhanced_stats, indent=2, default=str)
                    
                    # Debug logging for export file creation
                    log_export_created("Analytics Export", "JSON", len(audit_json.encode('utf-8')), filename)
                    log_memory_after_export("Analytics Export", "JSON")
                    
                    # Store and trigger rerun to show download
                    st.session_state[cache_key] = audit_json
                    st.rerun()
        else:
            # Show download for ready data
            audit_json = st.session_state[cache_key]
            st.download_button(
                label="📥 Download Enhanced JSON Report",
                data=audit_json,
                file_name=filename,
                mime="application/json",
                key="download_analytics_json"
            )

    # New truly lazy export methods - two-click pattern for all exports
    def render_lazy_excel_export_button(self, export_object, object_name: str, object_id: str, 
                                        export_type: str = "report", xml_filename: str = None) -> None:
        """
        Render truly lazy Excel export with two-click pattern:
        Click 1: Generate button -> Creates Excel file
        Click 2: Download button -> Downloads file and cleans up
        
        Args:
            export_object: The object to export (report, search, etc.)
            object_name: Display name for the object
            object_id: Unique ID for the object
            export_type: Type of export ("report", "search", etc.)
            xml_filename: Optional XML filename for export naming
        """
        excel_cache_key = f'lazy_excel_{export_type}_{object_id}'
        
        if excel_cache_key not in st.session_state:
            # Show generate button
            if st.button("📊 Excel", help=f"Generate Excel export for: {object_name}", 
                        key=f"generate_excel_{export_type}_{object_id}"):
                
                with st.spinner(f"Generating Excel export for {object_name}..."):
                    try:
                        if export_type == "report":
                            from .report_export import ReportExportHandler
                            export_handler = ReportExportHandler(self.analysis)
                            filename, content = export_handler.generate_report_export(export_object)
                        elif export_type == "search":
                            from .search_export import SearchExportHandler
                            export_handler = SearchExportHandler(self.analysis)
                            include_parent_info = getattr(export_object, 'parent_guid', None) is not None
                            filename, content = export_handler.generate_search_export(
                                export_object, include_parent_info=include_parent_info
                            )
                        else:
                            raise ValueError(f"Unsupported export type: {export_type}")
                        
                        # Cache the result
                        st.session_state[excel_cache_key] = (filename, content)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Excel export generation failed: {str(e)}")
        else:
            # Show download button
            filename, content = st.session_state[excel_cache_key]
            downloaded = st.download_button(
                label="📊 Excel",
                data=content,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help=f"File Ready For Download: {filename}",
                key=f"download_excel_{export_type}_{object_id}"
            )
            
            if downloaded:
                del st.session_state[excel_cache_key]

    def render_lazy_json_export_button(self, export_object, object_name: str, object_id: str,
                                       export_type: str = "report", xml_filename: str = None) -> None:
        """
        Render truly lazy JSON export with two-click pattern:
        Click 1: Generate button -> Creates JSON file
        Click 2: Download button -> Downloads file and cleans up
        
        Args:
            export_object: The object to export (report, search, etc.)
            object_name: Display name for the object
            object_id: Unique ID for the object
            export_type: Type of export ("report", "search", etc.)
            xml_filename: Optional XML filename for export naming
        """
        json_cache_key = f'lazy_json_{export_type}_{object_id}'
        
        if json_cache_key not in st.session_state:
            # Show generate button
            if st.button("📋 JSON", help=f"Generate JSON export for: {object_name}",
                        key=f"generate_json_{export_type}_{object_id}"):
                
                with st.spinner(f"Generating JSON export for {object_name}..."):
                    try:
                        if export_type == "report":
                            from .report_json_export_generator import ReportJSONExportGenerator
                            json_generator = ReportJSONExportGenerator(self.analysis)
                            filename, content = json_generator.generate_report_json(export_object, xml_filename or 'unknown.xml')
                        elif export_type == "search":
                            from .json_export_generator import JSONExportGenerator
                            json_generator = JSONExportGenerator(self.analysis)
                            filename, content = json_generator.generate_search_json(export_object, xml_filename or 'unknown.xml')
                        else:
                            raise ValueError(f"Unsupported export type: {export_type}")
                        
                        # Cache the result
                        st.session_state[json_cache_key] = (filename, content)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"JSON export generation failed: {str(e)}")
        else:
            # Show download button
            filename, content = st.session_state[json_cache_key]
            downloaded = st.download_button(
                label="📋 JSON",
                data=content,
                file_name=filename,
                mime="application/json",
                help=f"File Ready For Download: {filename}",
                key=f"download_json_{export_type}_{object_id}"
            )
            
            if downloaded:
                del st.session_state[json_cache_key]

    def render_lazy_master_json_export_button(self, reports_list, xml_filename: str = None) -> None:
        """
        Render truly lazy master JSON export for all reports/searches
        Click 1: Generate button -> Creates master JSON file
        Click 2: Download button -> Downloads file and cleans up
        """
        cache_key = 'lazy_master_export_ready'
        
        if cache_key not in st.session_state:
            if st.button("🗂️ Export ALL", help="Generate and download ALL items as complete JSON", 
                        key="generate_lazy_master_export"):
                
                with st.spinner("Generating master export... This may take a moment."):
                    try:
                        from .json_export_generator import JSONExportGenerator
                        json_generator = JSONExportGenerator(self.analysis)
                        master_filename, master_content = json_generator.generate_master_json(
                            xml_filename or 'unknown.xml', reports_list
                        )
                        
                        # Cache the result
                        st.session_state[cache_key] = (master_filename, master_content)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Master JSON export generation failed: {str(e)}")
            
            # Show count caption if available
            if reports_list:
                st.caption(f"Will generate JSON for {len(reports_list)} items")
        else:
            # Show download button
            master_filename, master_content = st.session_state[cache_key]
            downloaded = st.download_button(
                label="🗂️ Export ALL",
                data=master_content,
                file_name=master_filename,
                mime="application/json",
                key="download_lazy_master_json",
                help=f"File Ready For Download: {master_filename}"
            )
            
            if downloaded:
                del st.session_state[cache_key]
