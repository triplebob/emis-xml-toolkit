"""
SNOMED Code Expansion Service

This module provides high-level services for expanding SNOMED codes
when includechildren=True is detected in the XML analysis.

Enhanced version with:
- UI-independent service layer 
- Structured error handling
- Adaptive rate limiting
- Thread-safe operations
- Progress tracking
"""

import time
import threading
from typing import Dict, List, Optional, Set, Tuple, Union, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import Future
import logging

from ..common.error_handling import (
    TerminologyServerError, get_error_handler, create_user_friendly_error_message
)
from .nhs_terminology_client import (
    NHSTerminologyServerClient, CredentialConfig, ClientConfig, create_terminology_client
)
from .batch_processor import (
    BatchExpansionProcessor, BatchItem, BatchResult, BatchItemBuilder,
    ProgressCallback, create_progress_callback
)
from .nhs_terminology_client import ExpansionResult, ExpandedConcept

logger = logging.getLogger(__name__)


@dataclass
class ExpansionConfig:
    """Configuration for expansion operations"""
    include_inactive: bool = False
    use_cache: bool = True
    max_concurrent_requests: int = 10
    request_timeout: int = 30
    max_retries: int = 3
    debug_mode: bool = False
    batch_size: int = 1000


@dataclass
class ExpansionRequest:
    """Request for code expansion"""
    snomed_codes: List[str]
    config: ExpansionConfig = field(default_factory=ExpansionConfig)
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExpansionSummary:
    """Summary of expansion results"""
    total_codes: int
    successful_expansions: int
    failed_expansions: int
    total_child_codes: int
    processing_time: float
    success_rate: float
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


class CredentialManager:
    """Thread-safe credential management without UI dependencies"""
    
    def __init__(self):
        self._credentials: Optional[CredentialConfig] = None
        self._lock = threading.RLock()
    
    def set_credentials(self, client_id: str, client_secret: str,
                       base_url: str = None, auth_url: str = None):
        """Set NHS Terminology Server credentials"""
        with self._lock:
            self._credentials = CredentialConfig(
                client_id=client_id,
                client_secret=client_secret,
                base_url=base_url or "https://ontology.nhs.uk/production1/fhir",
                auth_url=auth_url or "https://ontology.nhs.uk/authorisation/auth/realms/nhs-digital-terminology/protocol/openid-connect/token"
            )
    
    def get_credentials(self) -> Optional[CredentialConfig]:
        """Get current credentials"""
        with self._lock:
            return self._credentials
    
    def has_credentials(self) -> bool:
        """Check if credentials are configured"""
        with self._lock:
            return (self._credentials is not None and 
                   self._credentials.client_id and 
                   self._credentials.client_secret)


class ExpansionCache:
    """Simple in-memory cache for expansion results"""
    
    def __init__(self, max_size: int = 1000, ttl_hours: int = 24):
        self.max_size = max_size
        self.ttl_hours = ttl_hours
        self._cache: Dict[str, Tuple[ExpansionResult, datetime]] = {}
        self._lock = threading.RLock()
    
    def _generate_key(self, snomed_code: str, include_inactive: bool) -> str:
        """Generate cache key"""
        return f"{snomed_code}_{include_inactive}"
    
    def get(self, snomed_code: str, include_inactive: bool) -> Optional[ExpansionResult]:
        """Get cached result if available and not expired"""
        key = self._generate_key(snomed_code, include_inactive)
        
        with self._lock:
            if key in self._cache:
                result, cached_at = self._cache[key]
                
                # Check if expired
                if (datetime.now() - cached_at).total_seconds() < (self.ttl_hours * 3600):
                    return result
                else:
                    # Remove expired entry
                    del self._cache[key]
        
        return None
    
    def put(self, snomed_code: str, include_inactive: bool, result: ExpansionResult):
        """Cache expansion result"""
        key = self._generate_key(snomed_code, include_inactive)
        
        with self._lock:
            # Remove oldest entries if cache is full
            if len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            
            self._cache[key] = (result, datetime.now())
    
    def clear(self):
        """Clear all cached results"""
        with self._lock:
            self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'ttl_hours': self.ttl_hours
            }


class ExpansionService:
    """
    UI-independent service for SNOMED code expansion
    
    Provides:
    - Clean separation from UI frameworks
    - Thread-safe operations
    - Configurable caching
    - Progress tracking
    - Comprehensive error handling
    """
    
    def __init__(self, credential_manager: Optional[CredentialManager] = None):
        self.credential_manager = credential_manager or CredentialManager()
        self.cache = ExpansionCache()
        self.error_handler = get_error_handler()
        
        self._client: Optional[NHSTerminologyServerClient] = None
        self._batch_processor: Optional[BatchExpansionProcessor] = None
        self._lock = threading.RLock()
        
        # Statistics
        self._stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'successful_expansions': 0,
            'failed_expansions': 0,
            'total_child_codes': 0
        }
    
    def _get_client(self) -> NHSTerminologyServerClient:
        """Get or create the NHS client with current credentials"""
        with self._lock:
            credentials = self.credential_manager.get_credentials()
            
            if not credentials:
                raise TerminologyServerError(
                    "NHS Terminology Server credentials not configured",
                    error_type="authentication_failed",
                    user_guidance="Please configure your NHS Terminology Server credentials before using expansion features."
                )
            
            if self._client is None:
                config = ClientConfig(debug_mode=False)
                self._client = NHSTerminologyServerClient(credentials, config)
                self._batch_processor = BatchExpansionProcessor(self._client)
            
            return self._client
    
    def test_connection(self) -> Tuple[bool, str]:
        """Test connection to NHS Terminology Server"""
        try:
            client = self._get_client()
            return client.test_connection()
        except TerminologyServerError as e:
            return False, e.get_user_friendly_message()
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"
    
    def expand_single_code(self, snomed_code: str, 
                          config: ExpansionConfig = None) -> ExpansionResult:
        """
        Expand a single SNOMED code
        
        Args:
            snomed_code: The SNOMED CT code to expand
            config: Expansion configuration
            
        Returns:
            ExpansionResult with children or error details
        """
        if config is None:
            config = ExpansionConfig()
        
        self._stats['total_requests'] += 1
        
        try:
            # Check cache first
            if config.use_cache:
                cached_result = self.cache.get(snomed_code, config.include_inactive)
                if cached_result:
                    self._stats['cache_hits'] += 1
                    return cached_result
                
                self._stats['cache_misses'] += 1
            
            # Perform expansion
            client = self._get_client()
            result = client.expand_concept(snomed_code, config.include_inactive)
            
            # Update statistics
            if result.error:
                self._stats['failed_expansions'] += 1
            else:
                self._stats['successful_expansions'] += 1
                self._stats['total_child_codes'] += len(result.children)
            
            # Cache successful results
            if config.use_cache and not result.error:
                self.cache.put(snomed_code, config.include_inactive, result)
            
            return result
            
        except TerminologyServerError:
            self._stats['failed_expansions'] += 1
            raise
        except Exception as e:
            self._stats['failed_expansions'] += 1
            error = TerminologyServerError(
                f"Unexpected error expanding {snomed_code}: {str(e)}",
                error_type="server_error",
                user_guidance="An unexpected error occurred during expansion. Please try again."
            )
            self.error_handler.handle_error(error)
            raise error
    
    def expand_batch(self, request: ExpansionRequest,
                    progress_callback: Optional[Callable[[int, int, float], None]] = None) -> Tuple[BatchResult, ExpansionSummary]:
        """
        Expand multiple SNOMED codes in batch
        
        Args:
            request: Expansion request with codes and configuration
            progress_callback: Optional callback for progress updates
            
        Returns:
            Tuple of (BatchResult, ExpansionSummary)
        """
        start_time = time.time()
        
        try:
            # Create batch items
            batch_items = BatchItemBuilder.from_snomed_codes(
                request.snomed_codes,
                request.config.include_inactive,
                request.config.max_retries
            )
            
            # Setup progress callback
            progress_config = None
            if progress_callback:
                progress_config = create_progress_callback(progress_callback)
            
            # Process batch
            client = self._get_client()
            batch_processor = BatchExpansionProcessor(client, request.config.max_concurrent_requests)
            
            batch_result = batch_processor.process_batch(
                batch_items=batch_items,
                batch_id=request.request_id,
                progress_callback=progress_config,
                fail_fast=False,
                timeout_seconds=None
            )
            
            # Create summary
            processing_time = time.time() - start_time
            total_child_codes = sum(
                len(result.children) for result in batch_result.results.values()
                if not result.error
            )
            
            # Categorize errors
            errors_by_type = {}
            for error_msg in batch_result.errors.values():
                if 'not found' in error_msg.lower():
                    errors_by_type['code_not_found'] = errors_by_type.get('code_not_found', 0) + 1
                elif 'authentication' in error_msg.lower():
                    errors_by_type['authentication_failed'] = errors_by_type.get('authentication_failed', 0) + 1
                elif 'timeout' in error_msg.lower():
                    errors_by_type['timeout_error'] = errors_by_type.get('timeout_error', 0) + 1
                else:
                    errors_by_type['other'] = errors_by_type.get('other', 0) + 1
            
            summary = ExpansionSummary(
                total_codes=batch_result.total_items,
                successful_expansions=batch_result.successful_items,
                failed_expansions=batch_result.failed_items,
                total_child_codes=total_child_codes,
                processing_time=processing_time,
                success_rate=batch_result.completion_rate,
                errors_by_type=errors_by_type
            )
            
            # Update statistics
            self._stats['total_requests'] += batch_result.total_items
            self._stats['successful_expansions'] += batch_result.successful_items
            self._stats['failed_expansions'] += batch_result.failed_items
            self._stats['total_child_codes'] += total_child_codes
            
            # Cache successful results
            if request.config.use_cache:
                for snomed_code, result in batch_result.results.items():
                    if not result.error:
                        self.cache.put(snomed_code, request.config.include_inactive, result)
            
            return batch_result, summary
            
        except Exception as e:
            error = TerminologyServerError(
                f"Batch expansion failed: {str(e)}",
                error_type="server_error",
                user_guidance="Batch expansion operation failed. Please try again with fewer codes or check your connection."
            )
            self.error_handler.handle_error(error)
            raise error
    
    def find_expandable_codes(self, clinical_data: List[Dict],
                             snomed_code_field: str = 'SNOMED Code',
                             include_children_fields: List[str] = None) -> List[Dict]:
        """
        Find codes in clinical data that should be expanded
        
        Args:
            clinical_data: List of clinical code dictionaries
            snomed_code_field: Field name containing SNOMED codes
            include_children_fields: Field names indicating includechildren=true
            
        Returns:
            List of codes that should be expanded
        """
        if include_children_fields is None:
            include_children_fields = ['include_children', 'includechildren', 'Include Children', 'descendants']
        
        expandable_codes = []
        
        for code_entry in clinical_data:
            snomed_code = code_entry.get(snomed_code_field, '').strip()
            if not snomed_code:
                continue
            
            # Check if expansion is requested
            should_expand = False
            
            for field in include_children_fields:
                if field in code_entry:
                    value = code_entry[field]
                    if isinstance(value, bool):
                        should_expand = value
                    elif isinstance(value, str):
                        should_expand = value.lower() in ['true', '1', 'yes']
                    break
            
            # Also check descendants count
            descendants = code_entry.get('Descendants', '')
            if descendants and str(descendants).strip() and str(descendants) != '0':
                should_expand = True
            
            if should_expand:
                expandable_codes.append(code_entry)
        
        return expandable_codes
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics"""
        cache_stats = self.cache.get_stats()
        
        stats = self._stats.copy()
        stats['cache'] = cache_stats
        
        if stats['total_requests'] > 0:
            stats['cache_hit_rate'] = (stats['cache_hits'] / stats['total_requests']) * 100
            stats['success_rate'] = (stats['successful_expansions'] / stats['total_requests']) * 100
        else:
            stats['cache_hit_rate'] = 0
            stats['success_rate'] = 0
        
        return stats
    
    def clear_cache(self):
        """Clear expansion cache"""
        self.cache.clear()
    
    def configure_credentials(self, client_id: str, client_secret: str):
        """Configure NHS Terminology Server credentials"""
        self.credential_manager.set_credentials(client_id, client_secret)
        
        # Reset client to use new credentials
        with self._lock:
            self._client = None
            self._batch_processor = None

    def expand_snomed_code(self, snomed_code: str, include_inactive: bool = False, use_cache: bool = True) -> ExpansionResult:
        """Expand a single SNOMED code"""
        config = ExpansionConfig(
            include_inactive=include_inactive,
            use_cache=use_cache
        )
        return self.expand_single_code(snomed_code, config)
    
    def enhance_clinical_codes_with_expansion(self, clinical_data: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Enhance clinical codes with expansion information"""
        enhanced_data = clinical_data.copy()
        expanded_child_codes = []
        
        expandable_codes = self.find_expandable_codes(clinical_data)
        
        if not expandable_codes:
            return enhanced_data, expanded_child_codes
        
        # Process each expandable code
        for code_entry in expandable_codes:
            snomed_code = code_entry.get('SNOMED Code', '').strip()
            if not snomed_code:
                continue
            
            try:
                result = self.expand_single_code(snomed_code)
                
                if result.error:
                    continue
                
                # Add expansion info to original code
                code_entry['Expansion Status'] = f"✅ {len(result.children)} child codes"
                code_entry['Child Count'] = len(result.children)
                
                # Create entries for child codes
                for child in result.children:
                    child_entry = {
                        'EMIS GUID': f"CHILD_{child.code}",
                        'SNOMED Code': child.code,
                        'SNOMED Description': child.display,
                        'Parent SNOMED Code': snomed_code,
                        'Parent Description': result.source_display,
                        'Mapping Found': 'Child Code',
                        'Source Type': code_entry.get('Source Type', 'Unknown'),
                        'Source Name': code_entry.get('Source Name', 'Unknown'),
                        'Source Container': code_entry.get('Source Container', 'Unknown'),
                        'Is Child Code': True,
                        'Inactive': child.inactive
                    }
                    expanded_child_codes.append(child_entry)
            
            except Exception:
                continue  # Skip failed expansions
        
        return enhanced_data, expanded_child_codes
    
    def create_expansion_summary_dataframe(self, expansions: Dict[str, ExpansionResult], original_codes: List[Dict] = None):
        """Create summary DataFrame of expansion results"""
        import pandas as pd
        
        summary_data = []
        
        # Create lookup for original descriptions and descendants
        original_descriptions = {}
        original_descendants = {}
        if original_codes:
            for code_entry in original_codes:
                snomed_code = code_entry.get('SNOMED Code', '').strip()
                if snomed_code:
                    original_descriptions[snomed_code] = code_entry.get('SNOMED Description', snomed_code)
                    # Get descendants count from original data
                    descendants = code_entry.get('Descendants', '')
                    original_descendants[snomed_code] = descendants
        
        for code, result in expansions.items():
            # Determine status and get appropriate description
            if result.error:
                if ('does not exist' in result.error.lower() or 
                    'not found' in result.error.lower() or 
                    'resource-not-found' in result.error.lower()):
                    status = 'Unmatched'
                    description = original_descriptions.get(code, result.source_display)
                    result_status = "Unmatched - No concept found on terminology server for that ID"
                else:
                    status = 'Error'
                    description = original_descriptions.get(code, result.source_display)
                    if 'connection' in result.error.lower() or 'network' in result.error.lower():
                        result_status = "Error - Failed to connect to terminology server"
                    else:
                        result_status = f"Error - {result.error}"
            else:
                if len(result.children) > 0:
                    status = 'Matched'
                    description = result.source_display if result.source_display != code else original_descriptions.get(code, result.source_display)
                    result_status = f"Matched - Found {len(result.children)} children"
                else:
                    if result.source_display and result.source_display != code and result.source_display != 'Unknown':
                        status = 'Matched'
                        description = result.source_display
                        result_status = "Matched - Valid concept but has no children"
                    else:
                        status = 'Unmatched'
                        description = original_descriptions.get(code, result.source_display)
                        result_status = "Unmatched - No concept found on terminology server for that ID"
            
            # Get EMIS child count from original data
            emis_child_count = 'N/A'
            if code in original_descendants:
                descendants = original_descendants[code]
                if descendants and str(descendants).strip() and str(descendants) != '0':
                    emis_child_count = str(descendants)
                elif descendants == '0' or descendants == 0:
                    emis_child_count = '0'
            
            summary_data.append({
                'SNOMED Code': code,
                'Description': description,
                'EMIS Child Count': emis_child_count,
                'Term Server Child Count': len(result.children),
                'Result Status': result_status,
                'Expanded At': result.expansion_timestamp.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return pd.DataFrame(summary_data)


# Global service instance
_expansion_service: Optional[ExpansionService] = None


def get_expansion_service() -> ExpansionService:
    """Get the global expansion service instance"""
    global _expansion_service
    if _expansion_service is None:
        _expansion_service = ExpansionService()
    return _expansion_service


def configure_expansion_service(client_id: str, client_secret: str):
    """Configure the global expansion service with credentials"""
    service = get_expansion_service()
    service.configure_credentials(client_id, client_secret)