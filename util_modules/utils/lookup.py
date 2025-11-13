import streamlit as st
from .github_loader import GitHubLookupLoader
from .caching.lookup_cache import get_cached_emis_lookup
import pandas as pd
from typing import Dict, Tuple, Any, Optional, List
import time
from functools import lru_cache
import hashlib

@st.cache_resource(ttl=7200, max_entries=1)  # Cache lookup dictionaries for 2 hours
def get_cached_lookup_dictionaries():
    """Get cached lookup dictionaries to avoid rebuilding them repeatedly."""
    try:
        lookup_df = st.session_state.get('lookup_df')
        emis_guid_col = st.session_state.get('emis_guid_col', 'EMIS GUID')
        snomed_code_col = st.session_state.get('snomed_code_col', 'SNOMED Code')
        
        if lookup_df is None:
            return None, None
            
        return create_lookup_dictionaries(lookup_df, emis_guid_col, snomed_code_col)
    except Exception:
        return None, None

def load_lookup_table():
    """Load the lookup table using cache-first approach with GitHub fallback."""
    try:
        # First try to use session state (if already loaded)
        lookup_df = st.session_state.get('lookup_df')
        emis_guid_col = st.session_state.get('emis_guid_col')
        snomed_code_col = st.session_state.get('snomed_code_col')
        version_info = st.session_state.get('lookup_version_info', {})
        
        # If we have session data, return it immediately
        if lookup_df is not None and emis_guid_col is not None and snomed_code_col is not None:
            # Ensure version_info is returned even if it's empty - this prevents the issue
            # where version info gets lost when loading from session data
            return lookup_df, emis_guid_col, snomed_code_col, version_info
        
        # Try to load from local cache first (without needing GitHub data)
        try:
            from .caching.lookup_cache import get_latest_cached_emis_lookup
            cached_result = get_latest_cached_emis_lookup()
            if cached_result is not None:
                lookup_df, emis_guid_col, snomed_code_col, version_info = cached_result
                # Mark that we loaded from cache
                version_info['load_source'] = 'cache'
                
                # Store in session state immediately to ensure it persists
                st.session_state.lookup_df = lookup_df
                st.session_state.emis_guid_col = emis_guid_col
                st.session_state.snomed_code_col = snomed_code_col
                st.session_state.lookup_version_info = version_info
                
                return lookup_df, emis_guid_col, snomed_code_col, version_info
            else:
                # No cache available, will load from GitHub
                st.info("📥 No local cache found, loading from GitHub...")
        except Exception as e:
            # Cache loading failed, continue to GitHub fallback
            st.warning(f"🔍 Cache loading failed: {str(e)}, falling back to GitHub...")
            pass
        
        # Load from GitHub API
        # Get secrets from Streamlit configuration
        url = st.secrets["LOOKUP_TABLE_URL"]
        token = st.secrets["GITHUB_TOKEN"]
        expiry_date = st.secrets.get("TOKEN_EXPIRY", "2025-12-31")  # Default expiry if not set
        
        # Create loader instance
        loader = GitHubLookupLoader(token=token, lookup_url=url, expiry_date=expiry_date)
        
        # Check token health and show warnings if needed
        is_healthy, status = loader.get_token_health_status()
        if not is_healthy:
            st.warning(f"⚠️ Token Issue: {status}")
        elif "expires soon" in status.lower():
            st.info(f"📅 Token Status: {status}")
        
        # Load the lookup table with version info from GitHub
        lookup_df, emis_guid_col, snomed_code_col, version_info = loader.load_lookup_table()
        
        # Mark that we loaded from GitHub
        if version_info is None:
            version_info = {}
        version_info['load_source'] = 'github'
        
        # Store in session state immediately to ensure it persists
        st.session_state.lookup_df = lookup_df
        st.session_state.emis_guid_col = emis_guid_col
        st.session_state.snomed_code_col = snomed_code_col
        st.session_state.lookup_version_info = version_info
        
        # After loading from GitHub, try to build cache for next time
        if lookup_df is not None and version_info:
            try:
                from .caching.lookup_cache import build_emis_lookup_cache
                st.info("🔐 Building local cache for faster future loads...")
                cache_built = build_emis_lookup_cache(lookup_df, snomed_code_col, emis_guid_col, version_info)
                if cache_built:
                    st.success("✅ Local cache built successfully")
                else:
                    st.warning("⚠️ Cache building failed but data loaded")
            except Exception as e:
                # Cache building failed, but we still have the data
                st.warning(f"⚠️ Cache building error: {str(e)}")
                pass
        
        return lookup_df, emis_guid_col, snomed_code_col, version_info
        
    except KeyError as e:
        raise Exception(f"Required secret not found: {e}. Please configure in Streamlit Cloud settings.")
    except Exception as e:
        raise Exception(f"Error loading lookup table: {str(e)}")

@st.cache_data(ttl=3600)
def get_lookup_statistics(lookup_df):
    """Calculate optimized statistics about the lookup table using vectorized operations."""
    if lookup_df is None or lookup_df.empty:
        return {
            'total_count': 0,
            'clinical_count': 0,
            'medication_count': 0,
            'other_count': 0,
            'unique_snomed_codes': 0,
            'unique_emis_guids': 0,
            'data_quality_score': 0.0
        }
    
    start_time = time.time()
    
    total_count = len(lookup_df)
    
    # Vectorized statistics calculation
    stats = {'total_count': total_count}
    
    if 'Source_Type' in lookup_df.columns:
        source_types = lookup_df['Source_Type']
        clinical_mask = source_types == 'Clinical'
        medication_mask = source_types.isin(['Medication', 'Constituent', 'DM+D'])
        
        stats.update({
            'clinical_count': clinical_mask.sum(),
            'medication_count': medication_mask.sum(),
            'other_count': total_count - clinical_mask.sum() - medication_mask.sum()
        })
    else:
        stats.update({
            'clinical_count': 0,
            'medication_count': 0,
            'other_count': total_count
        })
    
    # Additional performance-oriented statistics
    if len(lookup_df.columns) > 1:
        # Count unique values efficiently
        if 'SNOMED_ConceptId' in lookup_df.columns:
            stats['unique_snomed_codes'] = lookup_df['SNOMED_ConceptId'].nunique()
        
        if 'EMIS_GUID' in lookup_df.columns:
            stats['unique_emis_guids'] = lookup_df['EMIS_GUID'].nunique()
        
        # Calculate data quality score (percentage of non-null, non-empty values)
        non_null_mask = lookup_df.notna()
        non_empty_mask = lookup_df.astype(str).ne('')
        quality_mask = non_null_mask & non_empty_mask
        
        stats['data_quality_score'] = quality_mask.values.mean()
    
    processing_time = time.time() - start_time
    
    # Store performance metrics
    if 'lookup_performance' not in st.session_state:
        st.session_state.lookup_performance = {}
    
    st.session_state.lookup_performance.update({
        'stats_calculation_time': processing_time,
        'stats_timestamp': time.time()
    })
    
    return stats


class OptimizedLookupCache:
    """
    High-performance lookup cache with intelligent pre-loading and memory optimization.
    Designed for O(1) SNOMED lookups with minimal memory footprint.
    """
    
    def __init__(self):
        """Initialize the optimized lookup cache."""
        self._guid_cache: Dict[str, Dict[str, Any]] = {}
        self._snomed_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        self._last_update = None
        self._cache_hash = None
    
    def load_from_dataframe(
        self, 
        lookup_df: pd.DataFrame, 
        emis_guid_col: str, 
        snomed_code_col: str,
        force_reload: bool = False
    ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """
        Load lookup cache from DataFrame with intelligent caching.
        
        Args:
            lookup_df: Source DataFrame
            emis_guid_col: EMIS GUID column name
            snomed_code_col: SNOMED code column name
            force_reload: Force cache reload even if data hasn't changed
            
        Returns:
            Tuple of (guid_to_snomed_dict, snomed_to_info_dict)
        """
        # Generate hash of dataframe to detect changes
        current_hash = self._generate_dataframe_hash(lookup_df, emis_guid_col, snomed_code_col)
        
        # Check if cache is still valid
        if (not force_reload and 
            self._cache_hash == current_hash and 
            self._guid_cache and 
            self._snomed_cache):
            return self._guid_cache, self._snomed_cache
        
        # Rebuild cache
        start_time = time.time()
        
        # Use the optimized dictionary creation function
        guid_dict, snomed_dict = create_lookup_dictionaries(
            lookup_df, emis_guid_col, snomed_code_col
        )
        
        # Store in instance cache
        self._guid_cache = guid_dict
        self._snomed_cache = snomed_dict
        self._cache_hash = current_hash
        self._last_update = time.time()
        
        # Reset hit/miss counters
        self._cache_hits = 0
        self._cache_misses = 0
        
        build_time = time.time() - start_time
        
        # Store performance metrics
        if 'lookup_performance' not in st.session_state:
            st.session_state.lookup_performance = {}
        
        st.session_state.lookup_performance.update({
            'cache_build_time': build_time,
            'cache_size_guid': len(self._guid_cache),
            'cache_size_snomed': len(self._snomed_cache),
            'cache_last_update': self._last_update
        })
        
        return self._guid_cache, self._snomed_cache
    
    def lookup_guid(self, emis_guid: str) -> Optional[Dict[str, Any]]:
        """
        Perform O(1) GUID lookup with hit/miss tracking.
        
        Args:
            emis_guid: EMIS GUID to lookup
            
        Returns:
            SNOMED mapping dictionary or None
        """
        if emis_guid in self._guid_cache:
            self._cache_hits += 1
            return self._guid_cache[emis_guid]
        else:
            self._cache_misses += 1
            return None
    
    def lookup_snomed(self, snomed_code: str) -> Optional[Dict[str, Any]]:
        """
        Perform O(1) SNOMED code lookup with hit/miss tracking.
        
        Args:
            snomed_code: SNOMED code to lookup
            
        Returns:
            SNOMED info dictionary or None
        """
        if snomed_code in self._snomed_cache:
            self._cache_hits += 1
            return self._snomed_cache[snomed_code]
        else:
            self._cache_misses += 1
            return None
    
    def batch_lookup_guids(self, emis_guids: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Perform batch GUID lookups for improved performance.
        
        Args:
            emis_guids: List of EMIS GUIDs to lookup
            
        Returns:
            Dictionary mapping GUIDs to their SNOMED info (or None)
        """
        results = {}
        
        for guid in emis_guids:
            results[guid] = self.lookup_guid(guid)
        
        return results
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0
        
        return {
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'hit_rate': hit_rate,
            'total_requests': total_requests,
            'guid_cache_size': len(self._guid_cache),
            'snomed_cache_size': len(self._snomed_cache),
            'last_update': self._last_update,
            'memory_estimate_mb': self._estimate_cache_memory()
        }
    
    def clear_cache(self):
        """Clear all cached data."""
        self._guid_cache.clear()
        self._snomed_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        self._last_update = None
        self._cache_hash = None
    
    def _generate_dataframe_hash(
        self, 
        df: pd.DataFrame, 
        emis_col: str, 
        snomed_col: str
    ) -> str:
        """Generate hash of relevant DataFrame columns for change detection."""
        try:
            # Hash based on shape and key columns
            relevant_data = (
                str(df.shape) + 
                str(df[emis_col].iloc[:100].tolist() if len(df) > 0 else []) +
                str(df[snomed_col].iloc[:100].tolist() if len(df) > 0 else [])
            )
            return hashlib.md5(relevant_data.encode()).hexdigest()
        except Exception:
            # Fallback to simple hash
            return hashlib.md5(str(time.time()).encode()).hexdigest()
    
    def _estimate_cache_memory(self) -> float:
        """Estimate cache memory usage in MB."""
        try:
            import sys
            
            guid_size = sum(sys.getsizeof(k) + sys.getsizeof(v) for k, v in self._guid_cache.items())
            snomed_size = sum(sys.getsizeof(k) + sys.getsizeof(v) for k, v in self._snomed_cache.items())
            
            return (guid_size + snomed_size) / 1024 / 1024
        except Exception:
            return 0.0


@st.cache_resource
def get_optimized_lookup_cache() -> OptimizedLookupCache:
    """Get or create the global optimized lookup cache instance."""
    return OptimizedLookupCache()


def batch_translate_emis_guids(
    emis_guids: List[str], 
    lookup_df: pd.DataFrame,
    emis_guid_col: str, 
    snomed_code_col: str
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    High-performance batch translation of EMIS GUIDs to SNOMED codes.
    
    Args:
        emis_guids: List of EMIS GUIDs to translate
        lookup_df: Lookup DataFrame
        emis_guid_col: EMIS GUID column name
        snomed_code_col: SNOMED code column name
        
    Returns:
        Dictionary mapping GUIDs to their SNOMED translation results
    """
    cache = get_optimized_lookup_cache()
    
    # Ensure cache is loaded
    cache.load_from_dataframe(lookup_df, emis_guid_col, snomed_code_col)
    
    # Perform batch lookup
    return cache.batch_lookup_guids(emis_guids)


def display_lookup_performance_metrics():
    """Display lookup performance metrics in Streamlit UI."""
    cache = get_optimized_lookup_cache()
    stats = cache.get_cache_stats()
    
    # Get additional performance data from session state
    perf_data = st.session_state.get('lookup_performance', {})
    
    st.subheader("🚀 Lookup Performance Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Cache Hit Rate", f"{stats['hit_rate']:.1%}")
    
    with col2:
        st.metric("Total Requests", stats['total_requests'])
    
    with col3:
        st.metric("Memory Usage", f"{stats['memory_estimate_mb']:.1f} MB")
    
    with col4:
        if stats['last_update']:
            age = time.time() - stats['last_update']
            st.metric("Cache Age", f"{age:.0f}s")
        else:
            st.metric("Cache Age", "Not loaded")
    
    # Additional metrics
    if perf_data:
        st.subheader("📊 Detailed Performance")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if 'dictionary_build_time' in perf_data:
                st.metric("Dict Build Time", f"{perf_data['dictionary_build_time']:.2f}s")
        
        with col2:
            if 'valid_entries' in perf_data and 'total_rows_processed' in perf_data:
                validity = perf_data['valid_entries'] / perf_data['total_rows_processed']
                st.metric("Data Validity", f"{validity:.1%}")
        
        with col3:
            if 'guid_dictionary_size' in perf_data:
                st.metric("GUID Dictionary Size", f"{perf_data['guid_dictionary_size']:,}")
    
    # Cache management
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🗑️ Clear Lookup Cache"):
            cache.clear_cache()
            st.success("Lookup cache cleared")
            st.rerun()
    
    with col2:
        if st.button("🔄 Refresh Cache"):
            lookup_df = st.session_state.get('lookup_df')
            if lookup_df is not None:
                emis_col = st.session_state.get('emis_guid_col')
                snomed_col = st.session_state.get('snomed_code_col')
                if emis_col and snomed_col:
                    cache.load_from_dataframe(lookup_df, emis_col, snomed_col, force_reload=True)
                    st.success("Lookup cache refreshed")
                    st.rerun()

@st.cache_data(ttl=7200, show_spinner=False)  # Cache for 2 hours, no spinner
def create_lookup_dictionaries(lookup_df, emis_guid_col, snomed_code_col):
    """Create optimized lookup dictionaries for O(1) GUID to SNOMED translation."""
    # GUID -> SNOMED mapping for clinical codes and medications
    guid_to_snomed_dict = {}
    # SNOMED -> SNOMED mapping for refsets (to get descriptions)
    snomed_to_info_dict = {}
    
    if lookup_df is not None and not lookup_df.empty:
        # Vectorized operations for better performance
        start_time = time.time()
        
        # Convert to numpy arrays for faster processing
        code_ids = lookup_df[emis_guid_col].astype(str).str.strip()
        snomed_values = lookup_df[snomed_code_col]
        source_types = lookup_df.get('Source_Type', 'Unknown').astype(str).str.strip()
        
        # Handle SNOMED code conversion vectorized
        concept_ids = pd.Series(index=snomed_values.index, dtype=str)
        float_mask = pd.api.types.is_float_dtype(snomed_values) & snomed_values.notna()
        integer_floats = float_mask & (snomed_values % 1 == 0)
        
        concept_ids[integer_floats] = snomed_values[integer_floats].astype(int).astype(str)
        concept_ids[~integer_floats] = snomed_values[~integer_floats].astype(str).str.strip()
        
        # Get additional columns with defaults
        has_qualifiers = lookup_df.get('HasQualifier', 'Unknown').astype(str).str.strip()
        is_parents = lookup_df.get('IsParent', 'Unknown').astype(str).str.strip()
        descendants = lookup_df.get('Descendants', '0').astype(str).str.strip()
        code_types = lookup_df.get('CodeType', 'Unknown').astype(str).str.strip()
        
        # Create masks for valid entries
        valid_mask = (code_ids.notna() & 
                     (code_ids != 'nan') & 
                     (code_ids != '') &
                     concept_ids.notna() & 
                     (concept_ids != 'nan') & 
                     (concept_ids != ''))
        
        # Build dictionaries using vectorized operations
        for idx in lookup_df.index[valid_mask]:
            code_id = code_ids[idx]
            concept_id = concept_ids[idx]
            
            entry_data = {
                'snomed_code': concept_id,
                'source_type': source_types[idx],
                'has_qualifier': has_qualifiers[idx],
                'is_parent': is_parents[idx], 
                'descendants': descendants[idx],
                'code_type': code_types[idx]
            }
            
            # For GUID lookup (clinical codes and medications)
            guid_to_snomed_dict[code_id] = entry_data
            
            # For SNOMED lookup (refsets) - map SNOMED code back to itself with source info
            snomed_to_info_dict[concept_id] = entry_data
        
        processing_time = time.time() - start_time
        
        # Store performance metrics in session state for monitoring
        if 'lookup_performance' not in st.session_state:
            st.session_state.lookup_performance = {}
        
        st.session_state.lookup_performance.update({
            'dictionary_build_time': processing_time,
            'guid_dictionary_size': len(guid_to_snomed_dict),
            'snomed_dictionary_size': len(snomed_to_info_dict),
            'total_rows_processed': len(lookup_df),
            'valid_entries': valid_mask.sum(),
            'build_timestamp': time.time()
        })
    
    return guid_to_snomed_dict, snomed_to_info_dict
