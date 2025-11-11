"""
Terminology Server Export Handler

Centralizes all terminology server export functionality including:
- Summary CSV exports
- SNOMED child codes exports  
- EMIS child codes exports
- Combined hierarchical JSON exports
- Filtered result exports

All exports use lazy generation patterns and proper debug logging.
"""

import streamlit as st
import pandas as pd
import json
import io
from datetime import datetime
from typing import List, Dict, Any, Optional
from ..utils.export_debug import log_export_created, log_memory_after_export, track_export_object


class TerminologyExportHandler:
    """Handles all terminology server export functionality"""
    
    def __init__(self):
        """Initialize the terminology export handler"""
        self.export_prefix = "terminology"
    
    def export_summary_csv(self, summary_df: pd.DataFrame) -> tuple[str, str]:
        """
        Export terminology expansion summary as CSV
        
        Args:
            summary_df: DataFrame containing expansion summary data
            
        Returns:
            Tuple of (filename, csv_content)
        """
        if summary_df.empty:
            return "", ""
        
        # Clean dataframe for export
        clean_df = self._clean_dataframe_for_export(summary_df)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"expansion_summary_{timestamp}.csv"
        
        # Generate CSV content
        csv_content = clean_df.to_csv(index=False)
        
        # Debug logging
        log_export_created("Terminology Export", "CSV", len(csv_content.encode('utf-8')), "expansion_summary")
        log_memory_after_export("Terminology Export", "CSV")
        
        return filename, csv_content
    
    def export_snomed_child_codes_csv(self, snomed_df: pd.DataFrame, export_filter: str = "SNOMED Child Codes") -> tuple[str, str]:
        """
        Export SNOMED child codes as CSV
        
        Args:
            snomed_df: DataFrame containing SNOMED child codes
            export_filter: Filter description for filename
            
        Returns:
            Tuple of (filename, csv_content)
        """
        if snomed_df.empty:
            return "", ""
        
        # Clean dataframe for export
        clean_df = self._clean_dataframe_for_export(snomed_df)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filter = export_filter.lower().replace(' ', '_').replace('&', 'and')
        filename = f"snomed_child_codes_{safe_filter}_{timestamp}.csv"
        
        # Generate CSV content
        csv_content = clean_df.to_csv(index=False)
        
        # Debug logging
        log_export_created("Terminology Export", "CSV", len(csv_content.encode('utf-8')), f"snomed_child_codes_{safe_filter}")
        log_memory_after_export("Terminology Export", "CSV")
        
        return filename, csv_content
    
    def export_emis_child_codes_csv(self, emis_df: pd.DataFrame) -> tuple[str, str]:
        """
        Export EMIS child codes as CSV
        
        Args:
            emis_df: DataFrame containing EMIS child codes
            
        Returns:
            Tuple of (filename, csv_content)
        """
        if emis_df.empty:
            return "", ""
        
        # Clean dataframe for export
        clean_df = self._clean_dataframe_for_export(emis_df)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"emis_child_codes_{timestamp}.csv"
        
        # Generate CSV content
        csv_content = clean_df.to_csv(index=False)
        
        # Debug logging
        log_export_created("Terminology Export", "CSV", len(csv_content.encode('utf-8')), "emis_child_codes")
        log_memory_after_export("Terminology Export", "CSV")
        
        return filename, csv_content
    
    def export_hierarchical_json(self, expanded_codes: List[Dict[str, Any]], original_filename: str = "") -> tuple[str, str]:
        """
        Export hierarchical child codes as JSON
        
        Args:
            expanded_codes: List of expanded code dictionaries
            original_filename: Optional original filename for context
            
        Returns:
            Tuple of (filename, json_content)
        """
        if not expanded_codes:
            return "", ""
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if original_filename:
            clean_original = original_filename.replace(' ', '_').replace('.xml', '')
            filename = f"hierarchical_codes_{clean_original}_{timestamp}.json"
        else:
            filename = f"hierarchical_codes_{timestamp}.json"
        
        # Create hierarchical JSON structure
        json_data = {
            'metadata': {
                'export_timestamp': datetime.now().isoformat(),
                'export_tool': 'EMIS XML Converter - Terminology Server',
                'total_codes': len(expanded_codes),
                'original_file': original_filename
            },
            'hierarchical_codes': expanded_codes
        }
        
        # Generate JSON content
        json_content = json.dumps(json_data, indent=2, ensure_ascii=False)
        
        # Debug logging
        log_export_created("Terminology Export", "JSON", len(json_content.encode('utf-8')), "hierarchical_codes")
        log_memory_after_export("Terminology Export", "JSON")
        
        return filename, json_content
    
    def export_combined_data_json(self, combined_data: Dict[str, Any], original_filename: str = "") -> tuple[str, str]:
        """
        Export combined expansion data as JSON
        
        Args:
            combined_data: Combined expansion data dictionary
            original_filename: Optional original filename for context
            
        Returns:
            Tuple of (filename, json_content)
        """
        if not combined_data:
            return "", ""
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if original_filename:
            clean_original = original_filename.replace(' ', '_').replace('.xml', '')
            filename = f"combined_expansion_{clean_original}_{timestamp}.json"
        else:
            filename = f"combined_expansion_{timestamp}.json"
        
        # Add metadata to combined data
        enhanced_data = combined_data.copy()
        enhanced_data['metadata'] = {
            'export_timestamp': datetime.now().isoformat(),
            'export_tool': 'EMIS XML Converter - Terminology Server',
            'original_file': original_filename
        }
        
        # Generate JSON content
        json_content = json.dumps(enhanced_data, indent=2, ensure_ascii=False)
        
        # Debug logging
        log_export_created("Terminology Export", "JSON", len(json_content.encode('utf-8')), "combined_expansion")
        log_memory_after_export("Terminology Export", "JSON")
        
        return filename, json_content
    

    def export_filtered_csv(self, filtered_df: pd.DataFrame, filter_description: str = "") -> tuple[str, str]:
        """
        Export filtered results as CSV
        
        Args:
            filtered_df: DataFrame containing filtered results
            filter_description: Description of the filter applied
            
        Returns:
            Tuple of (filename, csv_content)
        """
        if filtered_df.empty:
            return "", ""
        
        # Clean dataframe for export
        clean_df = self._clean_dataframe_for_export(filtered_df)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filter = filter_description.lower().replace(' ', '_').replace('&', 'and') if filter_description else "filtered"
        filename = f"terminology_filtered_{safe_filter}_{timestamp}.csv"
        
        # Generate CSV content
        csv_content = clean_df.to_csv(index=False)
        
        # Debug logging
        log_export_created("Terminology Export", "CSV", len(csv_content.encode('utf-8')), f"filtered_{safe_filter}")
        log_memory_after_export("Terminology Export", "CSV")
        
        return filename, csv_content
    
    def _clean_dataframe_for_export(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean DataFrame for export by removing emojis and formatting
        
        Args:
            df: DataFrame to clean
            
        Returns:
            Cleaned DataFrame
        """
        clean_df = df.copy()
        
        # Remove emojis from text columns
        for col in clean_df.columns:
            if clean_df[col].dtype == 'object':
                clean_df[col] = clean_df[col].astype(str).str.replace(
                    r'[🔍📝⚕️📊📋📈📄🏥💊⬇️✅❌🔄📥📈📋🌳🔗]+ ', '', regex=True
                )
        
        return clean_df
    
    def render_lazy_csv_download(self, data: pd.DataFrame, label: str, export_key: str, 
                                export_func: callable, *args, **kwargs) -> None:
        """
        Render a lazy CSV download button using single-click pattern
        
        Args:
            data: DataFrame to export
            label: Button label
            export_key: Unique key for this export
            export_func: Function to call for export generation
            *args, **kwargs: Arguments to pass to export_func
        """
        if data.empty:
            st.info("No data available for export")
            return
        
        cache_key = f'terminology_export_{export_key}'
        
        if cache_key not in st.session_state:
            # Show generate button
            if st.button(label, help=f"Generate and download {export_key}", key=f"generate_{export_key}"):
                with st.spinner(f"Generating {export_key}..."):
                    filename, content = export_func(*args, **kwargs)
                    st.session_state[cache_key] = (filename, content)
                    st.rerun()
        else:
            # Show download button
            filename, content = st.session_state[cache_key]
            st.download_button(
                label=f"📥 Download {label}",
                data=content,
                file_name=filename,
                mime="text/csv",
                key=f"download_{export_key}"
            )
    
    def render_lazy_json_download(self, data: Any, label: str, export_key: str, 
                                 export_func: callable, *args, **kwargs) -> None:
        """
        Render a lazy JSON download button using single-click pattern
        
        Args:
            data: Data to export
            label: Button label
            export_key: Unique key for this export
            export_func: Function to call for export generation
            *args, **kwargs: Arguments to pass to export_func
        """
        if not data:
            st.info("No data available for export")
            return
        
        cache_key = f'terminology_export_{export_key}'
        
        if cache_key not in st.session_state:
            # Show generate button
            if st.button(label, help=f"Generate and download {export_key}", key=f"generate_{export_key}"):
                with st.spinner(f"Generating {export_key}..."):
                    filename, content = export_func(*args, **kwargs)
                    st.session_state[cache_key] = (filename, content)
                    st.rerun()
        else:
            # Show download button
            filename, content = st.session_state[cache_key]
            st.download_button(
                label=f"📥 Download {label}",
                data=content,
                file_name=filename,
                mime="application/json",
                key=f"download_{export_key}"
            )