from ..ui.theme import info_box, success_box, warning_box, error_box
"""
Background Processing Module for EMIS XML Converter
Implements ProcessPoolExecutor-based background processing for heavy XML analysis tasks.
Based on Streamlit optimization patterns from Thiago's guide.
"""

import streamlit as st
import concurrent.futures
import threading
import time
import multiprocessing
from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass
from enum import Enum
import traceback
import os
import psutil


class TaskStatus(Enum):
    """Task execution status enumeration."""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackgroundTask:
    """Background task container with metadata."""
    task_id: str
    name: str
    status: TaskStatus
    progress: float = 0.0
    result: Any = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BackgroundProcessor:
    """
    Background processor using ProcessPoolExecutor for heavy computation.
    Optimized for Streamlit Cloud compatibility with progress tracking.
    """
    
    def __init__(self, max_workers: int = None):
        """Initialize background processor with worker pool."""
        if max_workers is None:
            # Optimize for cloud environment
            max_workers = min(2, max(1, multiprocessing.cpu_count() // 2))
        
        self.max_workers = max_workers
        self.executor = None
        self.futures: Dict[str, concurrent.futures.Future] = {}
        self.tasks: Dict[str, BackgroundTask] = {}
        self._lock = threading.Lock()
        
    def _ensure_executor(self):
        """Lazy initialization of ProcessPoolExecutor."""
        if self.executor is None:
            self.executor = concurrent.futures.ProcessPoolExecutor(
                max_workers=self.max_workers
            )
    
    def submit_task(
        self, 
        task_id: str, 
        name: str, 
        func: Callable, 
        *args, 
        **kwargs
    ) -> BackgroundTask:
        """
        Submit a task for background processing.
        
        Args:
            task_id: Unique identifier for the task
            name: Human-readable task name
            func: Function to execute in background
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            BackgroundTask object for tracking
        """
        with self._lock:
            # Cancel existing task with same ID if running
            if task_id in self.futures:
                self.cancel_task(task_id)
            
            # Create task record
            task = BackgroundTask(
                task_id=task_id,
                name=name,
                status=TaskStatus.PENDING,
                start_time=time.time()
            )
            
            self.tasks[task_id] = task
            
            # Submit to executor
            self._ensure_executor()
            future = self.executor.submit(self._wrapped_execution, func, *args, **kwargs)
            self.futures[task_id] = future
            
            # Update status
            task.status = TaskStatus.RUNNING
            
            return task
    
    def _wrapped_execution(self, func: Callable, *args, **kwargs) -> Any:
        """
        Wrapped execution with error handling.
        This runs in the separate process.
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Return error info that can be pickled
            return {
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    def get_task_status(self, task_id: str) -> Optional[BackgroundTask]:
        """Get current status of a background task."""
        with self._lock:
            if task_id not in self.tasks:
                return None
            
            task = self.tasks[task_id]
            
            # Update status from future if still running
            if task_id in self.futures:
                future = self.futures[task_id]
                
                if future.done():
                    try:
                        result = future.result(timeout=0.1)
                        
                        # Check if result indicates an error
                        if isinstance(result, dict) and 'error' in result:
                            task.status = TaskStatus.FAILED
                            task.error = result['error']
                            task.result = None
                        else:
                            task.status = TaskStatus.COMPLETED
                            task.result = result
                            task.error = None
                        
                        task.end_time = time.time()
                        task.progress = 100.0
                        
                        # Cleanup future
                        del self.futures[task_id]
                        
                    except concurrent.futures.TimeoutError:
                        # Still running
                        task.status = TaskStatus.RUNNING
                    except Exception as e:
                        task.status = TaskStatus.FAILED
                        task.error = str(e)
                        task.end_time = time.time()
                        del self.futures[task_id]
            
            return task
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running background task."""
        with self._lock:
            if task_id in self.futures:
                future = self.futures[task_id]
                cancelled = future.cancel()
                
                if cancelled and task_id in self.tasks:
                    self.tasks[task_id].status = TaskStatus.CANCELLED
                    self.tasks[task_id].end_time = time.time()
                
                if task_id in self.futures:
                    del self.futures[task_id]
                
                return cancelled
            
            return False
    
    def cleanup_completed_tasks(self, max_age_seconds: int = 3600):
        """Remove completed tasks older than specified age."""
        current_time = time.time()
        
        with self._lock:
            tasks_to_remove = []
            
            for task_id, task in self.tasks.items():
                if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED] and
                    task.end_time and 
                    current_time - task.end_time > max_age_seconds):
                    tasks_to_remove.append(task_id)
            
            for task_id in tasks_to_remove:
                del self.tasks[task_id]
    
    def get_all_tasks(self) -> Dict[str, BackgroundTask]:
        """Get all current tasks."""
        with self._lock:
            return self.tasks.copy()
    
    def shutdown(self, wait: bool = True):
        """Shutdown the background processor."""
        if self.executor:
            self.executor.shutdown(wait=wait)
            self.executor = None
        
        with self._lock:
            self.futures.clear()


@st.cache_resource
def get_background_processor() -> BackgroundProcessor:
    """
    Get or create the global background processor instance.
    Uses st.cache_resource for efficient resource management.
    """
    # Determine optimal worker count for cloud environment
    max_workers = min(2, max(1, multiprocessing.cpu_count() // 2))
    
    return BackgroundProcessor(max_workers=max_workers)


def render_task_progress(task: BackgroundTask, show_details: bool = False) -> None:
    """
    Render task progress in Streamlit UI.
    
    Args:
        task: BackgroundTask to display
        show_details: Whether to show detailed task information
    """
    if task.status == TaskStatus.RUNNING:
        # Show progress bar with spinner
        col1, col2 = st.columns([3, 1])
        
        with col1:
            progress_text = f"Processing {task.name}..."
            if task.progress > 0:
                st.progress(task.progress / 100.0, text=progress_text)
            else:
                st.progress(0.1, text=progress_text)  # Indeterminate progress
        
        with col2:
            elapsed = time.time() - task.start_time if task.start_time else 0
            st.caption(f"⏱️ {elapsed:.1f}s")
    
    elif task.status == TaskStatus.COMPLETED:
        st.markdown(success_box(f"✅ {task.name} completed"), unsafe_allow_html=True)
        
        if show_details and task.end_time and task.start_time:
            duration = task.end_time - task.start_time
            st.caption(f"⚡ Completed in {duration:.2f}s")
    
    elif task.status == TaskStatus.FAILED:
        st.markdown(error_box(f"❌ {task.name} failed"), unsafe_allow_html=True)
        
        if show_details and task.error:
            with st.expander("Error Details"):
                st.code(task.error)
    
    elif task.status == TaskStatus.CANCELLED:
        st.markdown(warning_box(f"⚠️ {task.name} cancelled"), unsafe_allow_html=True)


def monitor_background_tasks(
    task_ids: List[str],
    container: st.container = None,
    auto_refresh: bool = True,
    refresh_interval: float = 1.0
) -> Dict[str, BackgroundTask]:
    """
    Monitor multiple background tasks with automatic UI updates.
    
    Args:
        task_ids: List of task IDs to monitor
        container: Streamlit container for updates
        auto_refresh: Whether to auto-refresh the UI
        refresh_interval: Refresh interval in seconds
        
    Returns:
        Dictionary of current task states
    """
    processor = get_background_processor()
    
    if container is None:
        container = st.container()
    
    current_tasks = {}
    all_completed = False
    
    with container:
        # Create placeholder for task status
        status_placeholder = st.empty()
        
        while not all_completed and auto_refresh:
            with status_placeholder.container():
                current_tasks = {}
                running_count = 0
                
                for task_id in task_ids:
                    task = processor.get_task_status(task_id)
                    if task:
                        current_tasks[task_id] = task
                        render_task_progress(task, show_details=False)
                        
                        if task.status == TaskStatus.RUNNING:
                            running_count += 1
                
                # Check if all tasks completed
                all_completed = running_count == 0
                
                if not all_completed:
                    time.sleep(refresh_interval)
                    st.rerun()
    
    return current_tasks


# Utility functions for common XML processing tasks
def create_xml_analysis_task(
    xml_content: str, 
    xml_filename: str,
    task_type: str = "xml_analysis"
) -> str:
    """
    Create a background task for XML analysis.
    
    Args:
        xml_content: XML content to analyze
        xml_filename: Name of the XML file
        task_type: Type of analysis task
        
    Returns:
        Task ID for monitoring
    """
    from ..analysis.xml_structure_analyzer import analyze_search_rules
    
    processor = get_background_processor()
    task_id = f"{task_type}_{hash(xml_content)}_{int(time.time())}"
    
    task = processor.submit_task(
        task_id=task_id,
        name=f"Analyzing {xml_filename}",
        func=analyze_search_rules,
        xml_content=xml_content
    )
    
    return task_id


def create_snomed_lookup_task(
    emis_guids: List[Dict],
    lookup_df,
    emis_guid_col: str,
    snomed_code_col: str,
    deduplication_mode: str = 'unique_codes'
) -> str:
    """
    Create a background task for SNOMED code lookup.
    
    Args:
        emis_guids: List of EMIS GUID dictionaries
        lookup_df: DataFrame with SNOMED mappings
        emis_guid_col: Column name for EMIS GUIDs
        snomed_code_col: Column name for SNOMED codes
        deduplication_mode: Deduplication strategy
        
    Returns:
        Task ID for monitoring
    """
    from .translator import translate_emis_to_snomed
    
    processor = get_background_processor()
    task_id = f"snomed_lookup_{hash(str(emis_guids))}_{int(time.time())}"
    
    task = processor.submit_task(
        task_id=task_id,
        name=f"Translating {len(emis_guids)} codes to SNOMED",
        func=translate_emis_to_snomed,
        emis_guids=emis_guids,
        lookup_df=lookup_df,
        emis_guid_col=emis_guid_col,
        snomed_code_col=snomed_code_col,
        deduplication_mode=deduplication_mode
    )
    
    return task_id


def get_system_performance_info() -> Dict[str, Any]:
    """Get current system performance information."""
    try:
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        return {
            'memory_usage_mb': memory_info.rss / 1024 / 1024,
            'memory_percent': process.memory_percent(),
            'cpu_percent': process.cpu_percent(),
            'num_threads': process.num_threads(),
            'cpu_count': multiprocessing.cpu_count()
        }
    except Exception:
        return {
            'memory_usage_mb': 0,
            'memory_percent': 0,
            'cpu_percent': 0,
            'num_threads': 1,
            'cpu_count': 1
        }
