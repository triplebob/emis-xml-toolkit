"""
Batch processing service for NHS Terminology Server operations
Handles partial failures and provides resilient batch expansion
"""

import time
import threading
import queue
from typing import Dict, List, Optional, Set, Tuple, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
import logging

from ..common.error_handling import (
    TerminologyServerError, BatchParsingReport, get_batch_aggregator,
    create_user_friendly_error_message
)
from .nhs_terminology_client import NHSTerminologyServerClient, CredentialConfig, ClientConfig, ExpansionResult

logger = logging.getLogger(__name__)


@dataclass
class BatchItem:
    """Individual item in a batch operation"""
    item_id: str
    snomed_code: str
    include_inactive: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None


@dataclass
class BatchResult:
    """Result of a batch operation"""
    batch_id: str
    total_items: int
    successful_items: int
    failed_items: int
    partial_failures: int
    results: Dict[str, ExpansionResult] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    processing_time: float = 0.0
    completion_rate: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class ProgressCallback:
    """Callback configuration for progress updates"""
    update_interval: float = 1.0  # seconds
    callback_func: Optional[Callable[[int, int, float], None]] = None


class BatchExpansionProcessor:
    """
    Processes batches of SNOMED code expansions with resilience to partial failures
    """
    
    def __init__(self, client: NHSTerminologyServerClient, max_workers: int = 10):
        self.client = client
        self.max_workers = max_workers
        self.batch_aggregator = get_batch_aggregator()
        self._active_batches: Dict[str, BatchResult] = {}
        self._lock = threading.RLock()
    
    def process_batch(self, 
                     batch_items: List[BatchItem],
                     batch_id: str = None,
                     progress_callback: Optional[ProgressCallback] = None,
                     fail_fast: bool = False,
                     timeout_seconds: Optional[int] = None) -> BatchResult:
        """
        Process a batch of SNOMED code expansions
        
        Args:
            batch_items: List of items to process
            batch_id: Unique identifier for this batch
            progress_callback: Callback for progress updates
            fail_fast: Stop on first error if True
            timeout_seconds: Overall timeout for the batch
            
        Returns:
            BatchResult with outcomes for all items
        """
        if batch_id is None:
            batch_id = f"batch_{int(time.time())}"
        
        start_time = datetime.now()
        
        # Initialize batch result
        batch_result = BatchResult(
            batch_id=batch_id,
            total_items=len(batch_items),
            successful_items=0,
            failed_items=0,
            partial_failures=0,
            started_at=start_time
        )
        
        with self._lock:
            self._active_batches[batch_id] = batch_result
        
        # Start batch tracking
        batch_report = self.batch_aggregator.start_batch(
            f"NHS Terminology Expansion Batch {batch_id}",
            len(batch_items)
        )
        
        try:
            logger.info(f"Starting batch {batch_id} with {len(batch_items)} items")
            
            # Process items with thread pool
            completed_items = 0
            failed_items_count = 0
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                future_to_item = {}
                for item in batch_items:
                    future = executor.submit(self._process_single_item, item, batch_id)
                    future_to_item[future] = item
                
                # Process completed tasks
                start_processing = time.time()
                last_progress_update = 0
                
                for future in as_completed(future_to_item, timeout=timeout_seconds):
                    item = future_to_item[future]
                    completed_items += 1
                    
                    try:
                        success, result, error = future.result()
                        
                        if success and result:
                            batch_result.results[item.snomed_code] = result
                            batch_result.successful_items += 1
                        else:
                            batch_result.errors[item.snomed_code] = error or "Unknown error"
                            batch_result.failed_items += 1
                            failed_items_count += 1
                        
                        # Update progress
                        if progress_callback and progress_callback.callback_func:
                            current_time = time.time()
                            if (current_time - last_progress_update) >= progress_callback.update_interval:
                                elapsed_time = current_time - start_processing
                                progress_callback.callback_func(
                                    completed_items, 
                                    len(batch_items),
                                    elapsed_time
                                )
                                last_progress_update = current_time
                        
                        # Fail fast check
                        if fail_fast and failed_items_count > 0:
                            logger.warning(f"Fail-fast enabled, stopping batch {batch_id} after first failure")
                            # Cancel remaining futures
                            for remaining_future in future_to_item:
                                if not remaining_future.done():
                                    remaining_future.cancel()
                            break
                            
                    except Exception as e:
                        logger.error(f"Error processing item {item.snomed_code}: {str(e)}")
                        batch_result.errors[item.snomed_code] = str(e)
                        batch_result.failed_items += 1
                        failed_items_count += 1
            
            # Calculate final metrics
            end_time = datetime.now()
            batch_result.completed_at = end_time
            batch_result.processing_time = (end_time - start_time).total_seconds()
            batch_result.completion_rate = (
                batch_result.successful_items / batch_result.total_items * 100
                if batch_result.total_items > 0 else 0
            )
            
            # Identify partial failures (items that had some success but not complete)
            batch_result.partial_failures = self._count_partial_failures(batch_result.results)
            
            logger.info(
                f"Completed batch {batch_id}: {batch_result.successful_items}/{batch_result.total_items} successful "
                f"({batch_result.completion_rate:.1f}%), {batch_result.processing_time:.1f}s"
            )
            
            return batch_result
            
        except Exception as e:
            logger.error(f"Critical error in batch {batch_id}: {str(e)}")
            batch_result.errors['_batch_error'] = str(e)
            return batch_result
            
        finally:
            # Clean up
            with self._lock:
                self._active_batches.pop(batch_id, None)
            
            # Finish batch tracking
            self.batch_aggregator.finish_batch()
    
    def _process_single_item(self, item: BatchItem, batch_id: str) -> Tuple[bool, Optional[ExpansionResult], Optional[str]]:
        """
        Process a single expansion item with retry logic
        
        Returns:
            (success, result, error_message)
        """
        last_error = None
        
        for attempt in range(item.max_retries + 1):
            try:
                logger.debug(f"Processing {item.snomed_code} (attempt {attempt + 1})")
                
                result = self.client.expand_concept(item.snomed_code, item.include_inactive)
                
                if result.error:
                    last_error = result.error
                    
                    # Determine if we should retry based on error type
                    if self._should_retry_error(result.error, attempt):
                        logger.warning(f"Retrying {item.snomed_code} due to: {result.error}")
                        time.sleep(min(2 ** attempt, 10))  # Exponential backoff
                        continue
                    else:
                        return False, result, result.error
                
                # Success
                return True, result, None
                
            except TerminologyServerError as e:
                last_error = e.get_user_friendly_message()
                
                if self._should_retry_error(str(e), attempt):
                    logger.warning(f"Retrying {item.snomed_code} due to server error: {str(e)}")
                    time.sleep(min(2 ** attempt, 10))
                    continue
                else:
                    return False, None, last_error
                    
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                logger.error(f"Unexpected error processing {item.snomed_code}: {str(e)}")
                # Don't retry unexpected errors
                break
        
        # All retries exhausted
        return False, None, last_error or f"Failed after {item.max_retries + 1} attempts"
    
    def _should_retry_error(self, error_message: str, attempt: int) -> bool:
        """
        Determine if an error should trigger a retry
        """
        if attempt >= 3:  # Max attempts
            return False
        
        error_lower = error_message.lower()
        
        # Retry on temporary errors
        retryable_errors = [
            'timeout', 'connection', 'server error', '429', '502', '503', '504',
            'rate limit', 'temporary', 'unavailable'
        ]
        
        return any(retryable in error_lower for retryable in retryable_errors)
    
    def _count_partial_failures(self, results: Dict[str, ExpansionResult]) -> int:
        """
        Count results that succeeded but with warnings or partial data
        """
        partial_count = 0
        
        for result in results.values():
            if result.error is None:  # Successful
                # Check for indicators of partial success
                if (result.total_count > 0 and 
                    len(result.children) < result.total_count):
                    partial_count += 1
        
        return partial_count
    
    def get_batch_status(self, batch_id: str) -> Optional[BatchResult]:
        """Get status of an active or recent batch"""
        with self._lock:
            return self._active_batches.get(batch_id)
    
    def cancel_batch(self, batch_id: str) -> bool:
        """
        Attempt to cancel an active batch
        Note: This is best-effort as individual operations may not be cancellable
        """
        with self._lock:
            if batch_id in self._active_batches:
                logger.info(f"Cancellation requested for batch {batch_id}")
                # In a real implementation, you'd signal the executor to cancel
                return True
            return False
    
    def get_active_batches(self) -> List[str]:
        """Get list of currently active batch IDs"""
        with self._lock:
            return list(self._active_batches.keys())


class BatchItemBuilder:
    """Helper class to build batch items from different sources"""
    
    @staticmethod
    def from_snomed_codes(snomed_codes: List[str], 
                         include_inactive: bool = False,
                         max_retries: int = 3) -> List[BatchItem]:
        """Create batch items from a list of SNOMED codes"""
        return [
            BatchItem(
                item_id=f"code_{code}",
                snomed_code=code,
                include_inactive=include_inactive,
                max_retries=max_retries
            )
            for code in snomed_codes
        ]
    
    @staticmethod
    def from_clinical_data(clinical_data: List[Dict],
                          snomed_code_field: str = 'SNOMED Code',
                          include_inactive: bool = False,
                          max_retries: int = 3) -> List[BatchItem]:
        """Create batch items from clinical data dictionaries"""
        items = []
        
        for i, data in enumerate(clinical_data):
            snomed_code = data.get(snomed_code_field, '').strip()
            if snomed_code:
                items.append(BatchItem(
                    item_id=f"clinical_{i}",
                    snomed_code=snomed_code,
                    include_inactive=include_inactive,
                    max_retries=max_retries,
                    metadata=data
                ))
        
        return items


def create_progress_callback(update_func: Callable[[int, int, float], None],
                           update_interval: float = 1.0) -> ProgressCallback:
    """Create a progress callback configuration"""
    return ProgressCallback(
        update_interval=update_interval,
        callback_func=update_func
    )


def estimate_batch_time(item_count: int, 
                       avg_response_time: float = 1.0,
                       max_workers: int = 10) -> float:
    """
    Estimate total time for batch processing
    
    Args:
        item_count: Number of items to process
        avg_response_time: Average response time per item
        max_workers: Number of concurrent workers
        
    Returns:
        Estimated time in seconds
    """
    # Simple estimation: total work time / parallelism + overhead
    parallel_time = (item_count * avg_response_time) / max_workers
    overhead = item_count * 0.1  # Setup overhead per item
    
    return parallel_time + overhead