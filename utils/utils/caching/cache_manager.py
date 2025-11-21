"""
Cache Manager for EMIS XML Converter UI Components

Centralized caching functionality with properly sized limits for different data types.
Handles SNOMED lookups, report rendering, and UI component caching with appropriate TTLs.
"""

import streamlit as st
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional


class CacheManager:
    """Centralized cache management with type-aware strategies and proper capacity limits"""
    
    # =============================================================================
    # SNOMED & CLINICAL CODE CACHING (High Capacity - 10K+ codes possible)
    # =============================================================================
    
    @staticmethod
    @st.cache_data(ttl=3600, max_entries=10000)  # 1 hour TTL, high capacity for large XML files
    def cache_snomed_lookup_dictionary(unified_data_hash: str, clinical_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Cache SNOMED lookup dictionary for O(1) lookups
        
        Args:
            unified_data_hash: Hash of unified clinical data for cache invalidation
            clinical_data: Unified clinical data from get_unified_clinical_data()
            
        Returns:
            Dictionary mapping EMIS GUID -> SNOMED Code
        """
        lookup_dict = {}
        
        for data_category in ['clinical_codes', 'medications', 'refsets', 'pseudo_refsets']:
            if data_category in clinical_data:
                for item in clinical_data[data_category]:
                    emis_guid = item.get('EMIS GUID', '').strip()
                    snomed_code = item.get('SNOMED Code', 'Not found')
                    if emis_guid:
                        lookup_dict[emis_guid] = snomed_code
        
        return lookup_dict
    
    @staticmethod
    @st.cache_data(ttl=3600, max_entries=5000)  # 1 hour TTL for clinical data processing
    def cache_unified_clinical_data(analysis_hash: str, search_codes: List[Dict], report_codes: List[Dict], 
                                  medications: List[Dict], refsets: List[Dict], pseudo_refsets: List[Dict]) -> Dict[str, Any]:
        """
        Cache processed unified clinical data
        
        Args:
            analysis_hash: Hash of analysis data for cache invalidation
            search_codes: Clinical codes from searches
            report_codes: Clinical codes from reports  
            medications: Medication codes
            refsets: Refset codes
            pseudo_refsets: Pseudo-refset codes
            
        Returns:
            Unified clinical data dictionary
        """
        return {
            'clinical_codes': search_codes + report_codes,
            'medications': medications,
            'refsets': refsets,
            'pseudo_refsets': pseudo_refsets,
            'processed_at': datetime.now().isoformat(),
            'total_codes': len(search_codes) + len(report_codes) + len(medications) + len(refsets) + len(pseudo_refsets)
        }
    
    # =============================================================================
    # REPORT RENDERING CACHING (Medium Capacity - 100s of reports possible)
    # =============================================================================
    
    @staticmethod
    @st.cache_data(ttl=1800, max_entries=1000)  # 30-minute TTL for report visualization
    def cache_list_report_visualization(report_id: str, report_hash: str, column_groups_count: int, 
                                      criteria_count: int, total_codes: int) -> Dict[str, Any]:
        """
        Cache List Report visualization data
        
        Args:
            report_id: Unique report identifier
            report_hash: Hash of report structure for cache invalidation
            column_groups_count: Number of column groups
            criteria_count: Number of criteria
            total_codes: Total number of clinical codes
            
        Returns:
            Cached visualization metadata
        """
        return {
            "report_id": report_id,
            "report_type": "list",
            "column_groups_count": column_groups_count,
            "criteria_count": criteria_count,
            "total_codes": total_codes,
            "cached_at": datetime.now().isoformat(),
            "rendering_optimized": True
        }
    
    @staticmethod
    @st.cache_data(ttl=1800, max_entries=1000)  # 30-minute TTL for report visualization
    def cache_audit_report_visualization(report_id: str, report_hash: str, population_refs_count: int,
                                       criteria_count: int, aggregation_config: str) -> Dict[str, Any]:
        """
        Cache Audit Report visualization data
        
        Args:
            report_id: Unique report identifier
            report_hash: Hash of report structure for cache invalidation
            population_refs_count: Number of population references
            criteria_count: Number of criteria
            aggregation_config: Configuration hash for aggregation
            
        Returns:
            Cached visualization metadata
        """
        return {
            "report_id": report_id,
            "report_type": "audit", 
            "population_refs_count": population_refs_count,
            "criteria_count": criteria_count,
            "aggregation_config": aggregation_config,
            "cached_at": datetime.now().isoformat(),
            "rendering_optimized": True
        }
    
    @staticmethod
    @st.cache_data(ttl=1800, max_entries=1000)  # 30-minute TTL for report visualization
    def cache_aggregate_report_visualization(report_id: str, report_hash: str, aggregate_groups_count: int,
                                           statistical_groups_count: int, cross_tab_config: str) -> Dict[str, Any]:
        """
        Cache Aggregate Report visualization data
        
        Args:
            report_id: Unique report identifier
            report_hash: Hash of report structure for cache invalidation
            aggregate_groups_count: Number of aggregate groups
            statistical_groups_count: Number of statistical groups
            cross_tab_config: Cross-tabulation configuration hash
            
        Returns:
            Cached visualization metadata
        """
        return {
            "report_id": report_id,
            "report_type": "aggregate",
            "aggregate_groups_count": aggregate_groups_count,
            "statistical_groups_count": statistical_groups_count,
            "cross_tab_config": cross_tab_config,
            "cached_at": datetime.now().isoformat(),
            "rendering_optimized": True
        }
    
    @staticmethod
    @st.cache_data(ttl=1800, max_entries=500)  # 30-minute TTL for report metadata
    def cache_report_metadata(report_id: str, report_name: str, report_type: str, 
                            parent_info: str, search_date: str, description: str) -> Dict[str, Any]:
        """
        Cache basic report metadata for fast dropdown switching
        
        Args:
            report_id: Unique report identifier
            report_name: Report display name
            report_type: Type of report (list, audit, aggregate, search)
            parent_info: Parent search information
            search_date: Date of the search
            description: Report description
            
        Returns:
            Cached report metadata
        """
        return {
            "report_id": report_id,
            "report_name": report_name,
            "report_type": report_type,
            "parent_info": parent_info,
            "search_date": search_date,
            "description": description,
            "cached_at": datetime.now().isoformat()
        }
    
    # =============================================================================
    # UI COMPONENT CACHING (Lower Capacity - UI elements)
    # =============================================================================
    
    @staticmethod
    @st.cache_data(ttl=600, max_entries=200)  # 10-minute TTL for UI components
    def cache_dataframe_rendering(data_hash: str, dataframe_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cache DataFrame rendering configuration
        
        Args:
            data_hash: Hash of DataFrame data for cache invalidation
            dataframe_config: Configuration for DataFrame display
            
        Returns:
            Cached DataFrame configuration
        """
        return {
            "config": dataframe_config,
            "cached_at": datetime.now().isoformat(),
            "optimized_rendering": True
        }
    
    @staticmethod
    @st.cache_data(ttl=900, max_entries=100)  # 15-minute TTL for export operations
    def cache_export_generation(export_hash: str, export_data: Any, export_type: str) -> Dict[str, Any]:
        """
        Cache export generation for lazy loading
        
        Args:
            export_hash: Hash of export parameters for cache invalidation
            export_data: Generated export data
            export_type: Type of export (excel, json, csv)
            
        Returns:
            Cached export data
        """
        return {
            "export_data": export_data,
            "export_type": export_type,
            "generated_at": datetime.now().isoformat(),
            "cache_hit": True
        }
    
    # =============================================================================
    # CACHE MANAGEMENT UTILITIES
    # =============================================================================
    
    @staticmethod
    def generate_report_hash(report_id: str, report_structure: Dict[str, Any]) -> str:
        """
        Generate a hash for report structure to detect changes
        
        Args:
            report_id: Unique report identifier
            report_structure: Report structure data
            
        Returns:
            MD5 hash of report structure
        """
        structure_str = f"{report_id}_{str(report_structure)}"
        return hashlib.md5(structure_str.encode()).hexdigest()
    
    @staticmethod
    def generate_data_hash(data: Any) -> str:
        """
        Generate a hash for any data structure
        
        Args:
            data: Data to hash
            
        Returns:
            MD5 hash of data
        """
        data_str = str(data)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    @staticmethod
    def clear_report_caches(report_id: Optional[str] = None):
        """
        Clear report-related caches
        
        Args:
            report_id: Specific report ID to clear, or None to clear all
        """
        # Note: Streamlit doesn't provide direct cache clearing by key
        # This would need to be implemented with custom session state management
        # For now, cache TTL will handle cleanup automatically
        pass
    
    @staticmethod
    def clear_export_cache(report_id: str):
        """
        Clear export cache for a specific report to free memory
        
        Args:
            report_id: Report ID to clear exports for
        """
        import streamlit as st
        import gc
        
        # Clear Excel and JSON export caches from session state
        excel_key = f'report_excel_{report_id}'
        json_key = f'report_json_{report_id}'
        
        if excel_key in st.session_state:
            del st.session_state[excel_key]
        if json_key in st.session_state:
            del st.session_state[json_key]
        
        # Force garbage collection to free memory
        gc.collect()
    
    @staticmethod
    def cleanup_dataframe_memory(dataframe_refs: List[Any] = None):
        """
        Cleanup DataFrame memory and force garbage collection
        
        Args:
            dataframe_refs: Optional list of DataFrame references to delete
        """
        import gc
        import pandas as pd
        
        # Delete specific DataFrame references if provided
        if dataframe_refs:
            for df_ref in dataframe_refs:
                if df_ref is not None:
                    try:
                        if hasattr(df_ref, '__del__'):
                            del df_ref
                    except:
                        pass  # Ignore deletion errors
        
        # Force garbage collection to free memory
        gc.collect()
    
    @staticmethod
    def manage_session_state_memory(max_cache_items: int = 50):
        """
        Manage session state memory by cleaning up old cached items
        
        Args:
            max_cache_items: Maximum number of cached items to keep
        """
        import streamlit as st
        import gc
        
        # Get all report-related cache keys
        report_cache_keys = [
            key for key in st.session_state.keys() 
            if key.startswith(('report_excel_', 'report_json_', 'cached_selected_report_'))
        ]
        
        # If we have too many cached items, remove oldest ones
        if len(report_cache_keys) > max_cache_items:
            # Sort by key name (assumes sequential IDs or timestamps)
            report_cache_keys.sort()
            keys_to_remove = report_cache_keys[:-max_cache_items]
            
            for key in keys_to_remove:
                if key in st.session_state:
                    del st.session_state[key]
        
        # Force garbage collection
        gc.collect()
    
    @staticmethod 
    def get_memory_usage_stats() -> Dict[str, Any]:
        """
        Get memory usage statistics for monitoring
        
        Returns:
            Dictionary with memory usage information
        """
        import streamlit as st
        import sys
        
        # Count session state items
        total_session_items = len(st.session_state.keys())
        report_cache_items = len([
            key for key in st.session_state.keys() 
            if key.startswith(('report_excel_', 'report_json_', 'cached_selected_report_'))
        ])
        
        return {
            "total_session_state_items": total_session_items,
            "report_cache_items": report_cache_items,
            "cache_memory_pressure": "high" if report_cache_items > 30 else "normal",
            "cleanup_recommended": report_cache_items > 50
        }
    
    @staticmethod
    @st.cache_data(ttl=1800, max_entries=1000)  # 30-minute TTL for XML parsing
    def cache_xml_code_extraction(xml_content_hash: str, xml_content: str) -> List[Dict[str, Any]]:
        """
        Cache XML code extraction to avoid expensive parsing
        
        Args:
            xml_content_hash: Hash of XML content for cache invalidation
            xml_content: XML content to parse
            
        Returns:
            List of extracted EMIS GUIDs with source attribution
        """
        # Import here to avoid circular imports
        import xml.etree.ElementTree as ET
        from ...xml_parsers.xml_utils import parse_xml_for_emis_guids
        
        try:
            root = ET.fromstring(xml_content)
            all_emis_guids = []
            
            # Define namespaces
            namespaces = {
                'emis': 'http://www.e-mis.com/emisopen'
            }
            
            # Step 1: Extract codes from searches using SearchAnalyzer approach
            all_reports = root.findall('.//emis:report', namespaces) + root.findall('.//report')
            searches = []
            for report in all_reports:
                # Check if this report has criteria (making it a search)
                criteria = report.find('.//criteria')
                if criteria is None:
                    criteria = report.find('.//emis:criteria', namespaces)
                if criteria is not None:
                    searches.append(report)
            
            for search_elem in searches:
                try:
                    # Get search ID for source attribution
                    search_id_elem = search_elem.find('id')
                    if search_id_elem is None:
                        search_id_elem = search_elem.find('emis:id', namespaces)
                    if search_id_elem is None:
                        search_id_elem = search_elem.find('id')
                    search_id = search_id_elem.text if search_id_elem is not None else f"search_{hash(ET.tostring(search_elem))}"
                    
                    # Extract the criteria content from this search and parse it as XML
                    criteria_content = ET.tostring(search_elem, encoding='unicode')
                    search_codes = parse_xml_for_emis_guids(f"<root>{criteria_content}</root>", source_guid=search_id)
                    
                    # Add source attribution
                    for code in search_codes:
                        code['source_type'] = 'search'
                        code['source_guid'] = search_id
                    
                    all_emis_guids.extend(search_codes)
                except Exception as e:
                    continue  # Skip problematic searches
            
            # Step 2: Extract codes from reports using ReportAnalyzer approach
            list_reports = root.findall('.//emis:listReport', namespaces) + root.findall('.//listReport')
            audit_reports = root.findall('.//emis:auditReport', namespaces) + root.findall('.//auditReport')
            aggregate_reports = root.findall('.//emis:aggregateReport', namespaces) + root.findall('.//aggregateReport')
            all_report_elems = list_reports + audit_reports + aggregate_reports
            
            for report_elem in all_report_elems:
                try:
                    # Get report ID for source attribution
                    report_id_elem = report_elem.find('id')
                    if report_id_elem is None:
                        report_id_elem = report_elem.find('emis:id', namespaces)
                    report_id = report_id_elem.text if report_id_elem is not None else f"report_{hash(ET.tostring(report_elem))}"
                    
                    # Extract the report content and parse it as XML
                    report_content = ET.tostring(report_elem, encoding='unicode')
                    report_codes = parse_xml_for_emis_guids(f"<root>{report_content}</root>", source_guid=report_id)
                    
                    # Add source attribution
                    for code in report_codes:
                        code['source_type'] = 'report'
                        code['source_guid'] = report_id
                    
                    all_emis_guids.extend(report_codes)
                except Exception as e:
                    continue  # Skip problematic reports
            
            return all_emis_guids
            
        except Exception as e:
            return []
    
    @staticmethod
    def clear_all_export_cache() -> int:
        """
        Clear all export caches and force garbage collection
        
        Returns:
            int: Number of cache entries cleared
        """
        import streamlit as st
        import gc
        
        try:
            cleared_count = 0
            
            # Clear export-related session state keys
            export_keys = [
                key for key in st.session_state.keys() 
                if any(pattern in key for pattern in [
                    'csv_export_',
                    'lazy_excel_',
                    'lazy_json_', 
                    'lazy_master_export_ready',
                    'report_excel_',
                    'report_json_',
                    'analytics_json_export_',
                    'export_', # Generic export keys
                    '_ready' # Export ready keys
                ])
            ]
            
            for key in export_keys:
                del st.session_state[key]
                cleared_count += 1
            
            # Clear Streamlit caches (EXCEPT SNOMED lookup cache which should persist 30+ minutes)
            # NOTE: We avoid st.cache_data.clear() to preserve valuable SNOMED mappings
            # Only clear export-related caches specifically
            
            # Force garbage collection
            gc.collect()
            
            return cleared_count
            
        except Exception:
            # Silently handle cache clearing errors
            return 0
    
    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        """
        Get cache statistics for monitoring
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            "cache_manager_version": "1.0",
            "snomed_cache_capacity": 10000,
            "report_cache_capacity": 1000,
            "ui_cache_capacity": 200,
            "export_cache_capacity": 100,
            "default_ttl_minutes": {
                "snomed": 60,
                "reports": 30,
                "ui": 10,
                "exports": 15
            }
        }


# Global cache manager instance
cache_manager = CacheManager()

# Convenience functions for easier imports
def cache_snomed_lookups(*args, **kwargs):
    """Convenience function for SNOMED lookup caching"""
    return cache_manager.cache_snomed_lookup_dictionary(*args, **kwargs)

def cache_report_rendering(report_type: str, *args, **kwargs):
    """Convenience function for report rendering caching"""
    if report_type == 'list':
        return cache_manager.cache_list_report_visualization(*args, **kwargs)
    elif report_type == 'audit':
        return cache_manager.cache_audit_report_visualization(*args, **kwargs)
    elif report_type == 'aggregate':
        return cache_manager.cache_aggregate_report_visualization(*args, **kwargs)
    else:
        raise ValueError(f"Unknown report type: {report_type}")

def cache_ui_components(*args, **kwargs):
    """Convenience function for UI component caching"""
    return cache_manager.cache_dataframe_rendering(*args, **kwargs)
