"""
Advanced progress tracking for NHS Terminology Server operations
Provides time estimation and detailed progress feedback
"""

import time
import threading
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import statistics
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProgressMetrics:
    """Detailed progress metrics"""
    total_items: int
    completed_items: int
    failed_items: int
    successful_items: int
    current_item: Optional[str] = None
    estimated_total_time: Optional[float] = None
    estimated_remaining_time: Optional[float] = None
    elapsed_time: float = 0.0
    items_per_second: float = 0.0
    success_rate: float = 0.0
    error_rate: float = 0.0


@dataclass
class TimeEstimation:
    """Time estimation data"""
    total_estimated_seconds: float
    remaining_estimated_seconds: float
    completion_percentage: float
    estimated_completion_time: datetime
    confidence_level: str  # 'low', 'medium', 'high'


class AdaptiveTimeEstimator:
    """
    Adaptive time estimator that improves accuracy as more data becomes available
    """
    
    def __init__(self, window_size: int = 50):
        self.window_size = window_size
        self._timing_samples: List[float] = []
        self._lock = threading.Lock()
        self.base_estimate_per_item = 0.01  # Default 10ms per item for concurrent operations
        
    def record_item_time(self, processing_time: float):
        """Record processing time for a single item"""
        with self._lock:
            self._timing_samples.append(processing_time)
            
            # Keep only recent samples for adaptive estimation
            if len(self._timing_samples) > self.window_size:
                self._timing_samples.pop(0)
    
    def get_time_estimate(self, remaining_items: int, completed_items: int = 0) -> TimeEstimation:
        """
        Get time estimation for remaining items
        
        Args:
            remaining_items: Number of items left to process
            completed_items: Number of items already completed
            
        Returns:
            TimeEstimation with detailed timing information
        """
        with self._lock:
            if not self._timing_samples:
                # No data yet, use conservative estimate
                estimated_per_item = self.base_estimate_per_item
                confidence = 'low'
            elif len(self._timing_samples) < 5:
                # Limited data, use simple average but cap at reasonable maximum
                raw_average = sum(self._timing_samples) / len(self._timing_samples)
                estimated_per_item = min(raw_average, 0.1)  # Cap at 100ms max per item for limited data
                confidence = 'medium'
            else:
                # Good data, use adaptive approach
                estimated_per_item = self._calculate_adaptive_estimate()
                confidence = 'high'
            
            total_estimated = estimated_per_item * remaining_items
            total_items = completed_items + remaining_items
            completion_percentage = (completed_items / total_items * 100) if total_items > 0 else 0
            
            return TimeEstimation(
                total_estimated_seconds=total_estimated,
                remaining_estimated_seconds=total_estimated,
                completion_percentage=completion_percentage,
                estimated_completion_time=datetime.now() + timedelta(seconds=total_estimated),
                confidence_level=confidence
            )
    
    def _calculate_adaptive_estimate(self) -> float:
        """Calculate adaptive time estimate using recent performance"""
        if not self._timing_samples:
            return self.base_estimate_per_item
        
        # Get recent samples (last 10 are most relevant for current conditions)
        recent_samples = self._timing_samples[-10:] if len(self._timing_samples) > 10 else self._timing_samples
        
        # For API calls, recent performance is highly predictive
        # Use heavily weighted recent average
        if len(recent_samples) >= 3:
            recent_average = sum(recent_samples) / len(recent_samples)
            # Cap unreasonably high estimates (probably network hiccups) - much more aggressive cap
            capped_estimate = min(recent_average, 0.2)  # Cap at 200ms max per item
            return capped_estimate
        
        # Fallback to simple average with cap
        simple_average = sum(self._timing_samples) / len(self._timing_samples)
        return min(simple_average, 0.15)  # Cap at 150ms for fallback
    
    def get_performance_stats(self) -> Dict[str, float]:
        """Get performance statistics"""
        with self._lock:
            if not self._timing_samples:
                return {'average': 0, 'median': 0, 'min': 0, 'max': 0, 'std_dev': 0}
            
            return {
                'average': statistics.mean(self._timing_samples),
                'median': statistics.median(self._timing_samples),
                'min': min(self._timing_samples),
                'max': max(self._timing_samples),
                'std_dev': statistics.stdev(self._timing_samples) if len(self._timing_samples) > 1 else 0
            }
    
    def reset(self):
        """Reset timing data"""
        with self._lock:
            self._timing_samples.clear()


class ProgressTracker:
    """
    Enhanced progress tracker with time estimation and performance monitoring
    """
    
    def __init__(self, total_items: int, operation_name: str = "NHS Terminology Expansion"):
        self.total_items = total_items
        self.operation_name = operation_name
        self.start_time = datetime.now()
        
        self._completed_items = 0
        self._failed_items = 0
        self._current_item: Optional[str] = None
        self._lock = threading.RLock()
        
        # Progress callbacks
        self._progress_callbacks: List[Callable[[ProgressMetrics], None]] = []
        self._update_interval = 1.0  # seconds
        self._last_update_time = 0.0
        
        # Time estimation
        self.time_estimator = AdaptiveTimeEstimator()
        
        # Performance tracking
        self._item_start_times: Dict[str, float] = {}
        
        logger.info(f"Started progress tracking for {operation_name} with {total_items} items")
    
    def start_item(self, item_id: str, item_description: str = None):
        """Mark the start of processing an item"""
        with self._lock:
            self._current_item = item_description or item_id
            self._item_start_times[item_id] = time.time()
            
            self._maybe_update_progress()
    
    def complete_item(self, item_id: str, success: bool = True):
        """Mark an item as completed"""
        with self._lock:
            # Calculate processing time
            if item_id in self._item_start_times:
                processing_time = time.time() - self._item_start_times[item_id]
                self.time_estimator.record_item_time(processing_time)
                del self._item_start_times[item_id]
            
            # Update counters
            self._completed_items += 1
            if not success:
                self._failed_items += 1
            
            self._current_item = None
            
            self._maybe_update_progress()
    
    def add_progress_callback(self, callback: Callable[[ProgressMetrics], None]):
        """Add a callback for progress updates"""
        with self._lock:
            self._progress_callbacks.append(callback)
    
    def set_update_interval(self, seconds: float):
        """Set minimum interval between progress updates"""
        self._update_interval = seconds
    
    def _maybe_update_progress(self):
        """Update progress if enough time has passed"""
        current_time = time.time()
        
        if (current_time - self._last_update_time) >= self._update_interval:
            self._update_progress()
            self._last_update_time = current_time
    
    def _update_progress(self):
        """Send progress update to all callbacks"""
        metrics = self.get_current_metrics()
        
        for callback in self._progress_callbacks:
            try:
                callback(metrics)
            except Exception as e:
                logger.error(f"Error in progress callback: {str(e)}")
    
    def get_current_metrics(self) -> ProgressMetrics:
        """Get current progress metrics"""
        with self._lock:
            elapsed_time = (datetime.now() - self.start_time).total_seconds()
            
            successful_items = self._completed_items - self._failed_items
            remaining_items = self.total_items - self._completed_items
            
            # Calculate rates
            items_per_second = self._completed_items / elapsed_time if elapsed_time > 0 else 0
            success_rate = (successful_items / self._completed_items * 100) if self._completed_items > 0 else 0
            error_rate = (self._failed_items / self._completed_items * 100) if self._completed_items > 0 else 0
            
            # Get time estimation
            time_estimate = None
            estimated_total_time = None
            estimated_remaining_time = None
            
            if remaining_items > 0:
                time_estimate = self.time_estimator.get_time_estimate(remaining_items, self._completed_items)
                estimated_total_time = elapsed_time + time_estimate.remaining_estimated_seconds
                estimated_remaining_time = time_estimate.remaining_estimated_seconds
            
            return ProgressMetrics(
                total_items=self.total_items,
                completed_items=self._completed_items,
                failed_items=self._failed_items,
                successful_items=successful_items,
                current_item=self._current_item,
                estimated_total_time=estimated_total_time,
                estimated_remaining_time=estimated_remaining_time,
                elapsed_time=elapsed_time,
                items_per_second=items_per_second,
                success_rate=success_rate,
                error_rate=error_rate
            )
    
    def is_complete(self) -> bool:
        """Check if all items have been processed"""
        with self._lock:
            return self._completed_items >= self.total_items
    
    def get_completion_summary(self) -> Dict[str, Any]:
        """Get final completion summary"""
        metrics = self.get_current_metrics()
        performance_stats = self.time_estimator.get_performance_stats()
        
        return {
            'operation_name': self.operation_name,
            'total_items': self.total_items,
            'successful_items': metrics.successful_items,
            'failed_items': metrics.failed_items,
            'success_rate': metrics.success_rate,
            'total_time': metrics.elapsed_time,
            'average_time_per_item': performance_stats['average'],
            'items_per_second': metrics.items_per_second,
            'performance_stats': performance_stats
        }
    
    def force_update(self):
        """Force a progress update regardless of interval"""
        self._update_progress()


class MultiStageProgressTracker:
    """
    Progress tracker for multi-stage operations
    """
    
    def __init__(self, stages: List[Tuple[str, int]], operation_name: str = "Multi-stage Operation"):
        self.stages = stages
        self.operation_name = operation_name
        self.current_stage_index = 0
        self.stage_trackers: List[ProgressTracker] = []
        self.start_time = datetime.now()
        
        # Create trackers for each stage
        for stage_name, stage_items in stages:
            tracker = ProgressTracker(stage_items, f"{operation_name} - {stage_name}")
            self.stage_trackers.append(tracker)
        
        self._progress_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        logger.info(f"Started multi-stage progress tracking for {operation_name}")
    
    def get_current_stage_tracker(self) -> Optional[ProgressTracker]:
        """Get tracker for current stage"""
        if 0 <= self.current_stage_index < len(self.stage_trackers):
            return self.stage_trackers[self.current_stage_index]
        return None
    
    def advance_stage(self):
        """Advance to next stage"""
        if self.current_stage_index < len(self.stage_trackers) - 1:
            self.current_stage_index += 1
            logger.info(f"Advanced to stage {self.current_stage_index + 1}/{len(self.stages)}")
    
    def get_overall_progress(self) -> Dict[str, Any]:
        """Get overall progress across all stages"""
        total_items = sum(stage_items for _, stage_items in self.stages)
        completed_items = 0
        failed_items = 0
        
        for i, tracker in enumerate(self.stage_trackers):
            metrics = tracker.get_current_metrics()
            if i < self.current_stage_index:
                # Completed stages
                completed_items += metrics.total_items
            elif i == self.current_stage_index:
                # Current stage
                completed_items += metrics.completed_items
            
            failed_items += metrics.failed_items
        
        elapsed_time = (datetime.now() - self.start_time).total_seconds()
        overall_completion = (completed_items / total_items * 100) if total_items > 0 else 0
        
        current_stage_name = self.stages[self.current_stage_index][0] if self.current_stage_index < len(self.stages) else "Complete"
        
        return {
            'operation_name': self.operation_name,
            'current_stage': current_stage_name,
            'current_stage_index': self.current_stage_index,
            'total_stages': len(self.stages),
            'total_items': total_items,
            'completed_items': completed_items,
            'failed_items': failed_items,
            'overall_completion': overall_completion,
            'elapsed_time': elapsed_time,
            'stage_details': [
                {
                    'name': stage_name,
                    'items': stage_items,
                    'metrics': tracker.get_current_metrics()
                }
                for (stage_name, stage_items), tracker in zip(self.stages, self.stage_trackers)
            ]
        }
    
    def add_progress_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback for overall progress updates"""
        self._progress_callbacks.append(callback)
        
        # Also add to current stage tracker to trigger overall updates
        def stage_callback(metrics: ProgressMetrics):
            overall_progress = self.get_overall_progress()
            for cb in self._progress_callbacks:
                try:
                    cb(overall_progress)
                except Exception as e:
                    logger.error(f"Error in multi-stage progress callback: {str(e)}")
        
        # Add to all stage trackers
        for tracker in self.stage_trackers:
            tracker.add_progress_callback(stage_callback)


def format_time_duration(seconds: float) -> str:
    """Format time duration in human-readable format"""
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hours"


def format_progress_message(metrics: ProgressMetrics) -> str:
    """Format progress metrics into a readable message"""
    completion_pct = (metrics.completed_items / metrics.total_items * 100) if metrics.total_items > 0 else 0
    
    message = f"Progress: {metrics.completed_items}/{metrics.total_items} ({completion_pct:.1f}%)"
    
    if metrics.current_item:
        message += f" - Processing: {metrics.current_item}"
    
    if metrics.estimated_remaining_time:
        remaining_str = format_time_duration(metrics.estimated_remaining_time)
        message += f" - Est. remaining: {remaining_str}"
    
    if metrics.items_per_second > 0:
        message += f" - Rate: {metrics.items_per_second:.1f} items/sec"
    
    return message