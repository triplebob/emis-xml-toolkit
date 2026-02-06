"""
NHS Terminology Server Service Layer

Manages expansion operations with:
- Session-state expansion caching (no disk writes)
- Batch code expansion with concurrency
- Integration with existing EMIS lookup cache
- Progress callback support
"""

import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

from .client import NHSTerminologyClient, TerminologyServerConfig, ExpansionResult, ExpandedConcept
from ..system.debug_output import emit_debug

logger = logging.getLogger(__name__)

try:
    import streamlit as st
except Exception:
    st = None


@dataclass
class ExpansionConfig:
    """Configuration for expansion operations"""
    include_inactive: bool = False
    use_cache: bool = True
    max_workers: int = 10


@dataclass
class CachedExpansion:
    """Serializable expansion result for persistent cache"""
    source_code: str
    source_display: str
    children: List[Dict[str, Any]]  # Serialized ExpandedConcept objects
    total_count: int
    cached_at: str  # ISO timestamp
    error: Optional[str] = None


class ExpansionCache:
    """
    Session-state cache for expansion results
    """

    def __init__(self, max_size: int = 10000, ttl_minutes: int = 90):
        self.max_size = max_size
        self.ttl_minutes = ttl_minutes
        self._cache: Dict[str, CachedExpansion] = {}
        self._session_key = "terminology_expansion_cache"
        self._lock = threading.RLock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "saves": 0
        }

    def _cache_key(self, code: str, include_inactive: bool) -> str:
        """Generate cache key"""
        return f"{code}_{include_inactive}"

    def _get_store(self) -> Dict[str, CachedExpansion]:
        if st is None:
            return self._cache
        try:
            if self._session_key not in st.session_state:
                st.session_state[self._session_key] = {}

            # Keep expansion cache scoped to the currently loaded XML session.
            # If the file hash changes, drop old expansion entries to avoid
            # accumulation across uploads/reprocess cycles.
            current_file_hash = (
                st.session_state.get("current_file_hash")
                or st.session_state.get("last_processed_hash")
            )
            file_hash_key = f"{self._session_key}_file_hash"
            cached_file_hash = st.session_state.get(file_hash_key)
            if (
                current_file_hash
                and cached_file_hash
                and cached_file_hash != current_file_hash
            ):
                st.session_state[self._session_key] = {}
            if current_file_hash:
                st.session_state[file_hash_key] = current_file_hash
            return st.session_state[self._session_key]
        except Exception:
            return self._cache

    def _is_valid_cached(self, cached: CachedExpansion) -> bool:
        """Validate cached entries to avoid stale or incomplete results."""
        if cached.error:
            return False
        if cached.total_count and not cached.children:
            return False
        display = str(cached.source_display or "").strip()
        if not cached.children and display in {"", "Unknown"}:
            return False
        return True

    def load_from_disk(self) -> int:
        """Initialise session cache, return number of entries available"""
        with self._lock:
            store = self._get_store()
            expired_count = self.clear_expired()
            loaded_count = len(store)
            logger.info(f"Loaded {loaded_count} expansion results from session cache (removed {expired_count} expired)")
            return loaded_count

    def save_to_disk(self):
        """No-op: expansion cache is session-state only."""
        return None

    def get(self, code: str, include_inactive: bool) -> Optional[ExpansionResult]:
        """Get cached expansion result"""
        key = self._cache_key(code, include_inactive)

        with self._lock:
            store = self._get_store()
            if key in store:
                cached = store[key]

                # Check if expired
                cached_time = datetime.fromisoformat(cached.cached_at)
                if datetime.now() - cached_time > timedelta(minutes=self.ttl_minutes):
                    del store[key]
                    self._stats["misses"] += 1
                    return None
                if not self._is_valid_cached(cached):
                    del store[key]
                    self._stats["misses"] += 1
                    return None

                self._stats["hits"] += 1

                # Deserialise to ExpansionResult
                return ExpansionResult(
                    source_code=cached.source_code,
                    source_display=cached.source_display,
                    children=[ExpandedConcept(**c) for c in cached.children],
                    total_count=cached.total_count,
                    expansion_timestamp=cached_time,
                    error=cached.error
                )

            self._stats["misses"] += 1
            return None

    def put(self, code: str, include_inactive: bool, result: ExpansionResult):
        """Cache expansion result"""
        key = self._cache_key(code, include_inactive)

        with self._lock:
            # Enforce size limit
            store = self._get_store()
            if len(store) >= self.max_size and key not in store:
                # Remove oldest entry
                oldest_key = min(store, key=lambda k: store[k].cached_at)
                del store[oldest_key]
                emit_debug("terminology_service", "Removed oldest cache entry to maintain size limit")

            # Serialise children
            children_serialised = [asdict(c) for c in result.children]

            # Cache the result
            store[key] = CachedExpansion(
                source_code=result.source_code,
                source_display=result.source_display,
                children=children_serialised,
                total_count=result.total_count,
                cached_at=datetime.now().isoformat(),
                error=result.error
            )

    def clear_expired(self) -> int:
        """Remove expired entries, return count removed"""
        with self._lock:
            store = self._get_store()
            now = datetime.now()
            expired = [
                key for key, cached in store.items()
                if now - datetime.fromisoformat(cached.cached_at) > timedelta(minutes=self.ttl_minutes)
            ]

            for key in expired:
                del store[key]

            if expired:
                logger.info(f"Removed {len(expired)} expired cache entries")

            return len(expired)

    def clear(self):
        """Clear all cached entries"""
        with self._lock:
            store = self._get_store()
            store.clear()
            logger.info("Cleared expansion cache")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            store = self._get_store()
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = (self._stats["hits"] / total_requests * 100) if total_requests > 0 else 0

            return {
                "size": len(store),
                "max_size": self.max_size,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate": hit_rate,
                "saves": self._stats["saves"]
            }


class ExpansionService:
    """Service for managing SNOMED code expansion with caching"""

    def __init__(self):
        self.expansion_cache = ExpansionCache()
        self.expansion_cache.load_from_disk()

        self.emis_lookup_cache: Optional[Dict[str, str]] = None
        self.client: Optional[NHSTerminologyClient] = None
        self._lock = threading.RLock()

        logger.info("Initialised Expansion Service")

    def configure_credentials(self, client_id: str, client_secret: str):
        """Configure NHS Terminology Server credentials"""
        config = TerminologyServerConfig(
            client_id=client_id,
            client_secret=client_secret
        )
        self.client = NHSTerminologyClient(config)
        logger.info("Configured NHS Terminology Server client")

    def load_emis_lookup(self, lookup_df: pd.DataFrame, version_info: Dict) -> bool:
        """
        Load EMIS lookup cache using existing infrastructure

        Args:
            lookup_df: EMIS lookup DataFrame
            version_info: Version info for cache validation

        Returns:
            True if loaded successfully
        """
        try:
            from ..caching.lookup_cache import get_cached_emis_lookup

            cached_data = get_cached_emis_lookup(
                lookup_df,
                snomed_code_col="SNOMED Code",
                emis_guid_col="EMIS GUID",
                version_info=version_info
            )

            if cached_data:
                self.emis_lookup_cache = cached_data['lookup_mapping']
                logger.info(f"Loaded EMIS lookup cache with {len(self.emis_lookup_cache)} mappings")
                return True

            logger.warning("EMIS lookup cache not available")
            return False

        except Exception as e:
            logger.error(f"Failed to load EMIS lookup cache: {e}")
            return False

    def expand_codes_batch(
        self,
        codes: List[str],
        config: ExpansionConfig,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, ExpansionResult]:
        """
        Expand codes with two-tier caching:
        1. Check expansion cache (Tier 1)
        2. Make API calls for misses
        3. Save results to cache

        Args:
            codes: List of SNOMED codes to expand
            config: Expansion configuration
            progress_callback: Optional callback(completed, total)

        Returns:
            Dict mapping code -> ExpansionResult
        """
        if not self.client:
            raise ValueError("Client not configured. Call configure_credentials first.")

        results = {}
        cache_misses = []

        # Step 1: Check cache first
        for code in codes:
            if config.use_cache:
                cached = self.expansion_cache.get(code, config.include_inactive)
                if cached:
                    results[code] = cached
                    if progress_callback:
                        progress_callback(len(results), len(codes))
                    continue

            cache_misses.append(code)

        logger.info(f"Batch expansion: {len(results)} cache hits, {len(cache_misses)} cache misses")

        # Step 2: Fetch misses from API
        if cache_misses:
            with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
                future_to_code = {
                    executor.submit(self.client.expand_concept, code, config.include_inactive): code
                    for code in cache_misses
                }

                for future in as_completed(future_to_code):
                    code = future_to_code[future]
                    try:
                        result = future.result()
                        results[code] = result

                        # Cache successful results
                        if config.use_cache and not result.error:
                            self.expansion_cache.put(code, config.include_inactive, result)

                        # Progress callback
                        if progress_callback:
                            progress_callback(len(results), len(codes))

                    except Exception as e:
                        logger.error(f"Failed to expand {code}: {e}")
                        # Create error result
                        results[code] = ExpansionResult(
                            source_code=code,
                            source_display="Unknown",
                            children=[],
                            total_count=0,
                            expansion_timestamp=datetime.now(),
                            error=str(e)
                        )
                        if progress_callback:
                            progress_callback(len(results), len(codes))

            # Step 3: Persist cache
            if config.use_cache and cache_misses:
                self.expansion_cache.save_to_disk()

        return results

    def should_expand_value_set(self, value_set: Dict[str, Any]) -> bool:
        """Check if value set should be expanded"""
        return value_set.get("include_children", False)

    def filter_expandable_value_sets(self, value_sets: List[Dict]) -> List[Dict]:
        """Filter value sets that have include_children=true"""
        expandable = [vs for vs in value_sets if self.should_expand_value_set(vs)]
        logger.info(f"Filtered {len(expandable)} expandable value sets from {len(value_sets)} total")
        return expandable

    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get combined cache statistics"""
        expansion_stats = self.expansion_cache.get_stats()

        emis_stats = {
            "size": len(self.emis_lookup_cache) if self.emis_lookup_cache else 0
        }

        return {
            "expansion_cache": expansion_stats,
            "emis_lookup_cache": emis_stats
        }


# Process-wide fallback singleton (used outside Streamlit session contexts)
_expansion_service: Optional[ExpansionService] = None
_service_lock = threading.Lock()


def get_expansion_service() -> ExpansionService:
    """
    Get expansion service instance.

    - In Streamlit runtime: scope to current session via st.session_state
    - Outside Streamlit (tests/scripts): fall back to process singleton
    """
    if st is not None:
        try:
            session_key = "terminology_expansion_service"
            if session_key not in st.session_state:
                st.session_state[session_key] = ExpansionService()
            return st.session_state[session_key]
        except Exception:
            # If session state isn't available, use process singleton fallback.
            pass

    global _expansion_service
    with _service_lock:
        if _expansion_service is None:
            _expansion_service = ExpansionService()
    return _expansion_service
