"""
Cache Manager for EMIS XML Converter UI Components

Centralised caching functionality with properly sized limits for different data types.
Handles SNOMED lookups, report rendering, and UI component caching with appropriate TTLs.
"""

import streamlit as st
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional


class CacheManager:
    """Centralised cache management with type-aware strategies and proper capacity limits"""
    
    # =============================================================================
    # SNOMED & CLINICAL CODE CACHING (High Capacity - 10K+ codes possible)
    # =============================================================================
    
    @staticmethod
    @st.cache_data(ttl=600, max_entries=1)  # Scoped to current XML session
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
    @st.cache_data(ttl=600, max_entries=1)  # Scoped to current XML session
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
    @st.cache_data(ttl=600, max_entries=10)  # 10-minute TTL, limited entries for memory
    def cache_list_report_visualisation(report_id: str, report_hash: str, column_groups_count: int,
                                      criteria_count: int, total_codes: int) -> Dict[str, Any]:
        """
        Cache List Report visualisation data
        
        Args:
            report_id: Unique report identifier
            report_hash: Hash of report structure for cache invalidation
            column_groups_count: Number of column groups
            criteria_count: Number of criteria
            total_codes: Total number of clinical codes
            
        Returns:
            Cached visualisation metadata
        """
        return {
            "report_id": report_id,
            "report_type": "list",
            "column_groups_count": column_groups_count,
            "criteria_count": criteria_count,
            "total_codes": total_codes,
            "cached_at": datetime.now().isoformat(),
            "rendering_optimised": True
        }
    
    @staticmethod
    @st.cache_data(ttl=600, max_entries=10)  # 10-minute TTL, limited entries for memory
    def cache_audit_report_visualisation(report_id: str, report_hash: str, population_refs_count: int,
                                       criteria_count: int, aggregation_config: str) -> Dict[str, Any]:
        """
        Cache Audit Report visualisation data
        
        Args:
            report_id: Unique report identifier
            report_hash: Hash of report structure for cache invalidation
            population_refs_count: Number of population references
            criteria_count: Number of criteria
            aggregation_config: Configuration hash for aggregation
            
        Returns:
            Cached visualisation metadata
        """
        return {
            "report_id": report_id,
            "report_type": "audit", 
            "population_refs_count": population_refs_count,
            "criteria_count": criteria_count,
            "aggregation_config": aggregation_config,
            "cached_at": datetime.now().isoformat(),
            "rendering_optimised": True
        }
    
    @staticmethod
    @st.cache_data(ttl=600, max_entries=10)  # 10-minute TTL, limited entries for memory
    def cache_aggregate_report_visualisation(report_id: str, report_hash: str, aggregate_groups_count: int,
                                           statistical_groups_count: int, cross_tab_config: str) -> Dict[str, Any]:
        """
        Cache Aggregate Report visualisation data
        
        Args:
            report_id: Unique report identifier
            report_hash: Hash of report structure for cache invalidation
            aggregate_groups_count: Number of aggregate groups
            statistical_groups_count: Number of statistical groups
            cross_tab_config: Cross-tabulation configuration hash
            
        Returns:
            Cached visualisation metadata
        """
        return {
            "report_id": report_id,
            "report_type": "aggregate",
            "aggregate_groups_count": aggregate_groups_count,
            "statistical_groups_count": statistical_groups_count,
            "cross_tab_config": cross_tab_config,
            "cached_at": datetime.now().isoformat(),
            "rendering_optimised": True
        }
    
    @staticmethod
    @st.cache_data(ttl=600, max_entries=20)  # 10-minute TTL, limited entries for memory
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
    @st.cache_data(ttl=300, max_entries=10)  # 5-minute TTL, limited entries for memory
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
            "optimised_rendering": True
        }
    
    @staticmethod
    def cache_export_generation(export_hash: str, export_data: Any, export_type: str) -> Dict[str, Any]:
        """
        Generate export data on-demand (no caching - immediate gc after download).

        Args:
            export_hash: Hash of export parameters (unused, kept for API compatibility)
            export_data: Generated export data
            export_type: Type of export (excel, json, csv)

        Returns:
            Export data wrapper (not cached)
        """
        # No caching - exports are generated fresh and gc'd after download
        return {
            "export_data": export_data,
            "export_type": export_type,
            "generated_at": datetime.now().isoformat(),
            "cache_hit": False
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
        Manage session state memory by cleaning up stale cached items
        
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
    @st.cache_data(ttl=600, max_entries=1, show_spinner=False)  # Scoped to current XML session
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
        from ..system.session_state import SessionStateKeys
        from .xml_cache import cache_parsed_xml

        def _debug(msg: str) -> None:
            # Debug output for pipeline transition debugging
            if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
                import sys
                print(f"[DEBUG][cache_manager] {msg}", file=sys.stderr)

        def _flatten_entities_to_guid_records(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            records: List[Dict[str, Any]] = []
            seen: set = set()

            for entity in entities:
                parent_flags = entity.get("flags", {}) or {}
                source_type = parent_flags.get("element_type")
                source_guid = parent_flags.get("element_id")
                source_name = parent_flags.get("display_name") or parent_flags.get("description") or ""
                report_type = parent_flags.get("element_type")

                for criterion in entity.get("criteria", []):
                    cflags = criterion.get("flags", {}) or {}
                    table_ctx = cflags.get("logical_table_name")
                    column_ctx = cflags.get("column_name")
                    if isinstance(column_ctx, list):
                        column_ctx = column_ctx[0] if column_ctx else None

                    from ..metadata.value_set_resolver import resolve_value_sets
                    for valueset in resolve_value_sets(criterion):
                        code_val = valueset.get("code_value")
                        if not code_val:
                            continue

                        key = (code_val, valueset.get("valueSet_guid"), valueset.get("code_system"))
                        if key in seen:
                            continue
                        seen.add(key)

                        record = {
                            "valueSet_guid": valueset.get("valueSet_guid") or "N/A",
                            "valueSet_description": valueset.get("valueSet_description") or "N/A",
                            "code_system": valueset.get("code_system") or "N/A",
                            "emis_guid": code_val,
                            "xml_display_name": valueset.get("display_name") or "N/A",
                            "include_children": bool(valueset.get("include_children", False)),
                            "is_refset": bool(valueset.get("is_refset", False)),
                            "is_pseudorefset": bool(valueset.get("is_pseudo_refset", False)),
                            "is_pseudomember": bool(valueset.get("is_pseudo_member", False)),
                            "inactive": bool(valueset.get("inactive", False)),
                            "table_context": table_ctx,
                            "column_context": column_ctx,
                            "source_guid": source_guid,
                            "source_type": source_type,
                            "source_name": source_name,
                            "source_container": parent_flags.get("container_type") or parent_flags.get("element_type"),
                            "report_type": report_type,
                        }
                        records.append(record)

            return records

        # Try the parsing pipeline first for canonical metadata (cached by XML hash)
        try:
            cached = cache_parsed_xml(xml_content_hash, xml_content)
            ui_rows = cached.get("ui_rows", [])
            entities = cached.get("entities", [])
            folders = cached.get("folders", [])
            code_store = cached.get("code_store")

            # Reuse structure data from cached parse (avoid duplicate parsing)
            structure_data = cached.get("structure_data", {}) or {}

            _debug(f"Pipeline returned: {len(ui_rows)} ui_rows, {len(entities)} entities, {len(folders)} folders")

            from .lookup_manager import is_lookup_loaded
            has_qualifier_present = any("Has Qualifier" in row for row in ui_rows)
            if is_lookup_loaded() and not has_qualifier_present:
                try:
                    from .xml_cache import _flatten_from_code_store
                    from ..metadata.enrichment import enrich_codes_from_xml
                    from ..metadata.serialisers import serialise_codes_for_ui
                    flattened = _flatten_from_code_store(code_store)
                    emis_guids = [str(c.get("emis_guid") or "").strip() for c in flattened if c.get("emis_guid")]
                    enriched = enrich_codes_from_xml(flattened, emis_guids)
                    debug_mode = st.session_state.get(SessionStateKeys.DEBUG_MODE, False)
                    ui_rows = serialise_codes_for_ui(enriched, include_debug_fields=debug_mode)
                except Exception:
                    pass
            _debug(f"Pipeline success: {len(ui_rows)} entries (empty permitted)")
            # Reset unified cache so a different file rebuilds UI data
            if "unified_clinical_data_cache" in st.session_state:
                del st.session_state["unified_clinical_data_cache"]
            st.session_state[SessionStateKeys.PIPELINE_CODES] = ui_rows
            st.session_state[SessionStateKeys.PIPELINE_ENTITIES] = entities
            st.session_state[SessionStateKeys.PIPELINE_FOLDERS] = folders
            st.session_state[SessionStateKeys.XML_STRUCTURE_DATA] = structure_data
            if code_store is not None:
                st.session_state[SessionStateKeys.CODE_STORE] = code_store
                st.session_state[SessionStateKeys.CODE_STORE_SOURCE_HASH] = xml_content_hash
            else:
                st.session_state.pop(SessionStateKeys.CODE_STORE, None)
                st.session_state.pop(SessionStateKeys.CODE_STORE_SOURCE_HASH, None)
            
            # Mark processing as complete for file session tracking (content-hash based).
            st.session_state["current_file_hash"] = xml_content_hash
            st.session_state["last_processed_hash"] = xml_content_hash
            
            return ui_rows
                
        except Exception as e:
            _debug(f"Pipeline failed with error: {type(e).__name__}: {str(e)}")
            # Surface the actual error for debugging
            raise ValueError(f"New parsing pipeline failed: {type(e).__name__}: {str(e)}") from e
    
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
            "cache_manager_version": "2.0",
            "snomed_cache_capacity": 1,
            "report_cache_capacity": 10,
            "ui_cache_capacity": 10,
            "export_cache_capacity": 0,  # No caching - on-demand only
            "default_ttl_minutes": {
                "snomed": 10,
                "reports": 10,
                "ui": 5,
                "exports": 0  # No caching
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
        return cache_manager.cache_list_report_visualisation(*args, **kwargs)
    elif report_type == 'audit':
        return cache_manager.cache_audit_report_visualisation(*args, **kwargs)
    elif report_type == 'aggregate':
        return cache_manager.cache_aggregate_report_visualisation(*args, **kwargs)
    else:
        raise ValueError(f"Unknown report type: {report_type}")

def cache_ui_components(*args, **kwargs):
    """Convenience function for UI component caching"""
    return cache_manager.cache_dataframe_rendering(*args, **kwargs)
