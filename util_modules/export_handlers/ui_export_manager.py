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


class UIExportManager:
    """Manages all export functionality across the UI with enhanced options"""
    
    def __init__(self, analysis=None):
        self.analysis = analysis
        self.clinical_export = ClinicalCodeExportHandler()
        self.search_export = SearchExportHandler(analysis) if analysis else None
    
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
            include_report_codes = st.session_state.get('clinical_include_report_codes', True)
            show_code_sources = st.session_state.get('clinical_show_code_sources', True)
            
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
            
            st.download_button(
                label=f"📥 CSV",
                data=csv_buffer.getvalue(),
                file_name=filename,
                mime="text/csv",
                key=f"export_{section_name}_csv"
            )
            
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
            
            st.download_button(
                label=f"📊 Excel",
                data=output.getvalue(),
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"export_{section_name}_excel"
            )
            
            # Clear cache after export to free memory
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
                'export_tool': 'EMIS XML Converter'
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
        search_results = st.session_state.get('search_results')
        search_count = len(search_results.searches) if search_results and hasattr(search_results, 'searches') else 0
        metrics_data.append(['XML Structure', 'clinical_searches_found', search_count])
        
        report_results = st.session_state.get('report_results')
        if report_results and hasattr(report_results, 'report_breakdown'):
            total_reports = sum(len(reports) for reports in report_results.report_breakdown.values())
            metrics_data.append(['XML Structure', 'total_reports_found', total_reports])
            
            # Add individual report type counts
            for report_type, reports in report_results.report_breakdown.items():
                if reports:
                    metrics_data.append(['XML Structure', f'{report_type}_reports_found', len(reports)])
        else:
            metrics_data.append(['XML Structure', 'total_reports_found', 0])
        
        analysis = st.session_state.get('search_analysis')
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
        
        # Generate CSV
        metrics_df = pd.DataFrame(metrics_data[1:], columns=metrics_data[0])
        csv_buffer = io.StringIO()
        metrics_df.to_csv(csv_buffer, index=False)
        
        st.download_button(
            label="📊 Download Analytics CSV",
            data=csv_buffer.getvalue(),
            file_name=f"analytics_{audit_stats['xml_stats']['filename']}.csv",
            mime="text/csv"
        )
    
    def render_enhanced_json_export(self, audit_stats: Dict[str, Any]):
        """Render enhanced JSON export with the same enhanced metrics as CSV export"""
        import json
        
        # Start with original audit_stats
        enhanced_stats = audit_stats.copy()
        
        # Add enhanced structure metrics
        search_results = st.session_state.get('search_results')
        search_count = len(search_results.searches) if search_results and hasattr(search_results, 'searches') else 0
        
        report_results = st.session_state.get('report_results')
        total_reports = 0
        report_breakdown = {}
        if report_results and hasattr(report_results, 'report_breakdown'):
            total_reports = sum(len(reports) for reports in report_results.report_breakdown.values())
            for report_type, reports in report_results.report_breakdown.items():
                if reports:
                    report_breakdown[f'{report_type}_reports_found'] = len(reports)
        
        analysis = st.session_state.get('search_analysis')
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
        
        # Generate enhanced JSON
        audit_json = json.dumps(enhanced_stats, indent=2, default=str)
        st.download_button(
            label="📄 Download Enhanced JSON Report",
            data=audit_json,
            file_name=f"analytics_{audit_stats['xml_stats']['filename']}.json",
            mime="application/json"
        )