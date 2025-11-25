"""
Async-Compatible UI Components for EMIS XML Converter
Implements non-blocking UI patterns with background processing integration.
Based on Streamlit optimization patterns for responsive user interfaces.
"""

import streamlit as st
import time
import threading
from typing import Dict, Any, Optional, Callable, List, Union
from dataclasses import dataclass
from enum import Enum
import pandas as pd
from functools import wraps
import queue
import uuid
from .theme import info_box, success_box, warning_box, error_box

from ..core.background_processor import (
    get_background_processor, 
    BackgroundTask, 
    TaskStatus,
    render_task_progress,
    monitor_background_tasks
)
from .progressive_loader import (
    get_progressive_loader,
    ProgressiveComponent,
    LoadState
)


class AsyncComponentState(Enum):
    """State enumeration for async components."""
    IDLE = "idle"
    LOADING = "loading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class AsyncRenderContext:
    """Context for async component rendering."""
    component_id: str
    container: st.container
    progress_placeholder: Optional[st.empty] = None
    status_placeholder: Optional[st.empty] = None
    content_placeholder: Optional[st.empty] = None
    state: AsyncComponentState = AsyncComponentState.IDLE
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AsyncTabRenderer:
    """
    Async tab renderer that loads content progressively without blocking UI.
    Designed for heavy report tab rendering with background processing.
    """
    
    def __init__(self):
        """Initialize async tab renderer."""
        self.active_tasks: Dict[str, str] = {}  # tab_id -> task_id mapping
        self.render_contexts: Dict[str, AsyncRenderContext] = {}
        self._processor = get_background_processor()
    
    def render_async_tab(
        self,
        tab_id: str,
        tab_name: str,
        content_func: Callable,
        *args,
        auto_refresh: bool = True,
        refresh_interval: float = 1.0,
        show_progress: bool = True,
        **kwargs
    ):
        """
        Render a tab with async content loading.
        
        Args:
            tab_id: Unique identifier for the tab
            tab_name: Display name for the tab
            content_func: Function to generate tab content
            *args, **kwargs: Arguments for content_func
            auto_refresh: Whether to auto-refresh during loading
            refresh_interval: Refresh interval in seconds
            show_progress: Whether to show progress indicators
        """
        # Create or get render context
        if tab_id not in self.render_contexts:
            container = st.container()
            self.render_contexts[tab_id] = AsyncRenderContext(
                component_id=tab_id,
                container=container,
                progress_placeholder=container.empty(),
                status_placeholder=container.empty(),
                content_placeholder=container.empty()
            )
        
        context = self.render_contexts[tab_id]
        
        # Check if we have an active background task
        if tab_id in self.active_tasks:
            task_id = self.active_tasks[tab_id]
            task = self._processor.get_task_status(task_id)
            
            if task:
                if task.status == TaskStatus.RUNNING:
                    # Show progress
                    if show_progress:
                        with context.progress_placeholder.container():
                            render_task_progress(task, show_details=True)
                    
                    # Auto-refresh if enabled
                    if auto_refresh:
                        time.sleep(refresh_interval)
                        st.rerun()
                    return
                
                elif task.status == TaskStatus.COMPLETED:
                    # Task completed - render results
                    with context.content_placeholder.container():
                        if task.result is not None:
                            # Render the computed content
                            if callable(task.result):
                                task.result()
                            else:
                                st.write(task.result)
                        else:
                            st.markdown(error_box("Task completed but no result available"), unsafe_allow_html=True)
                    
                    # Clean up
                    context.progress_placeholder.empty()
                    context.status_placeholder.empty()
                    del self.active_tasks[tab_id]
                    context.state = AsyncComponentState.COMPLETED
                    return
                
                elif task.status == TaskStatus.FAILED:
                    # Task failed - show error
                    with context.content_placeholder.container():
                        st.markdown(error_box(f"Failed to load {tab_name}: {task.error}"), unsafe_allow_html=True)
                        if st.button(f"🔄 Retry {tab_name}", key=f"retry_{tab_id}"):
                            # Clear error and retry
                            del self.active_tasks[tab_id]
                            context.state = AsyncComponentState.IDLE
                            st.rerun()
                    
                    # Clean up
                    context.progress_placeholder.empty()
                    del self.active_tasks[tab_id]
                    context.state = AsyncComponentState.ERROR
                    return
        
        # No active task - check if we should start one
        if context.state == AsyncComponentState.IDLE:
            # Start background processing
            task_id = f"{tab_id}_{int(time.time())}"
            
            task = self._processor.submit_task(
                task_id=task_id,
                name=f"Loading {tab_name}",
                func=self._wrap_content_func,
                content_func=content_func,
                *args,
                **kwargs
            )
            
            self.active_tasks[tab_id] = task_id
            context.state = AsyncComponentState.LOADING
            
            # Show initial loading state
            if show_progress:
                with context.progress_placeholder.container():
                    st.markdown(info_box(f"⏳ Loading {tab_name}..."), unsafe_allow_html=True)
            
            # Trigger rerun to start monitoring
            st.rerun()
    
    def _wrap_content_func(self, content_func: Callable, *args, **kwargs):
        """
        Wrapper for content functions to handle Streamlit context issues.
        This runs in the background process.
        """
        try:
            # For background processing, we need to return data, not Streamlit calls
            # The actual rendering happens in the main thread
            result = content_func(*args, **kwargs)
            
            # If the function returns Streamlit components, we need to handle it differently
            if hasattr(result, '__call__'):
                # It's a function that renders Streamlit components
                return result
            else:
                # It's data that can be rendered
                return result
        
        except Exception as e:
            # Return error information
            return {'error': str(e), 'type': 'content_generation_error'}
    
    def cancel_tab_loading(self, tab_id: str) -> bool:
        """Cancel loading for a specific tab."""
        if tab_id in self.active_tasks:
            task_id = self.active_tasks[tab_id]
            cancelled = self._processor.cancel_task(task_id)
            
            if cancelled:
                del self.active_tasks[tab_id]
                if tab_id in self.render_contexts:
                    context = self.render_contexts[tab_id]
                    context.progress_placeholder.empty()
                    context.status_placeholder.empty()
                    context.state = AsyncComponentState.IDLE
            
            return cancelled
        
        return False
    
    def get_tab_status(self, tab_id: str) -> Optional[AsyncComponentState]:
        """Get current state of a tab."""
        if tab_id in self.render_contexts:
            return self.render_contexts[tab_id].state
        return None
    
    def clear_all_tabs(self):
        """Clear all tab contexts and cancel active tasks."""
        for tab_id in list(self.active_tasks.keys()):
            self.cancel_tab_loading(tab_id)
        
        self.render_contexts.clear()


@st.cache_resource
def get_async_tab_renderer() -> AsyncTabRenderer:
    """Get or create the global async tab renderer."""
    return AsyncTabRenderer()


def async_tab_content(
    tab_id: str,
    tab_name: str,
    show_progress: bool = True,
    auto_refresh: bool = True
):
    """
    Decorator for creating async tab content.
    
    Args:
        tab_id: Unique identifier for the tab
        tab_name: Display name for the tab
        show_progress: Whether to show progress indicators
        auto_refresh: Whether to auto-refresh during loading
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            renderer = get_async_tab_renderer()
            
            renderer.render_async_tab(
                tab_id=tab_id,
                tab_name=tab_name,
                content_func=func,
                show_progress=show_progress,
                auto_refresh=auto_refresh,
                *args,
                **kwargs
            )
        
        return wrapper
    return decorator


class AsyncDataFrameRenderer:
    """
    Async DataFrame renderer with progressive loading and pagination.
    Optimized for large datasets with background processing.
    """
    
    def __init__(self):
        """Initialize async DataFrame renderer."""
        self.loading_tasks: Dict[str, str] = {}
        self.cached_dataframes: Dict[str, pd.DataFrame] = {}
    
    def render_async_dataframe(
        self,
        df_id: str,
        data_func: Callable[[], pd.DataFrame],
        title: str,
        max_rows: int = 1000,
        enable_pagination: bool = True,
        enable_search: bool = True,
        show_stats: bool = True,
        cache_duration: float = 600.0
    ):
        """
        Render DataFrame with async loading and progressive features.
        
        Args:
            df_id: Unique identifier for the DataFrame
            data_func: Function that returns DataFrame data
            title: Title for the DataFrame display
            max_rows: Maximum rows to display at once
            enable_pagination: Whether to enable pagination
            enable_search: Whether to enable search functionality
            show_stats: Whether to show DataFrame statistics
            cache_duration: Cache duration in seconds
        """
        # Check if we have cached data
        cache_key = f"{df_id}_{hash(str(data_func))}"
        
        if cache_key in self.cached_dataframes:
            df = self.cached_dataframes[cache_key]
            self._render_dataframe_content(
                df, title, max_rows, enable_pagination, 
                enable_search, show_stats, df_id
            )
            return
        
        # Check if loading is in progress
        if df_id in self.loading_tasks:
            processor = get_background_processor()
            task_id = self.loading_tasks[df_id]
            task = processor.get_task_status(task_id)
            
            if task:
                if task.status == TaskStatus.RUNNING:
                    render_task_progress(task, show_details=True)
                    time.sleep(0.5)
                    st.rerun()
                    return
                
                elif task.status == TaskStatus.COMPLETED:
                    if task.result is not None and not isinstance(task.result, dict):
                        # Cache the result
                        self.cached_dataframes[cache_key] = task.result
                        
                        # Render the DataFrame
                        self._render_dataframe_content(
                            task.result, title, max_rows, enable_pagination,
                            enable_search, show_stats, df_id
                        )
                    else:
                        st.markdown(error_box(f"Failed to load data for {title}"), unsafe_allow_html=True)
                    
                    # Clean up
                    del self.loading_tasks[df_id]
                    return
                
                elif task.status == TaskStatus.FAILED:
                    st.markdown(error_box(f"Error loading {title}: {task.error}"), unsafe_allow_html=True)
                    del self.loading_tasks[df_id]
                    return
        
        # Start loading
        processor = get_background_processor()
        task_id = f"dataframe_{df_id}_{int(time.time())}"
        
        task = processor.submit_task(
            task_id=task_id,
            name=f"Loading {title} data",
            func=data_func
        )
        
        self.loading_tasks[df_id] = task_id
        
        # Show loading indicator
        st.markdown(info_box(f"⏳ Loading {title}..."), unsafe_allow_html=True)
        st.rerun()
    
    def _render_dataframe_content(
        self,
        df: pd.DataFrame,
        title: str,
        max_rows: int,
        enable_pagination: bool,
        enable_search: bool,
        show_stats: bool,
        df_id: str
    ):
        """Render DataFrame content with interactive features."""
        st.subheader(title)
        
        if df is None or df.empty:
            st.markdown(info_box(f"No data available for {title}"), unsafe_allow_html=True)
            return
        
        # Show statistics
        if show_stats:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Rows", len(df))
            with col2:
                st.metric("Columns", len(df.columns))
            with col3:
                memory_usage = df.memory_usage(deep=True).sum() / 1024 / 1024
                st.metric("Memory", f"{memory_usage:.1f} MB")
            with col4:
                null_pct = (df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100
                st.metric("Null %", f"{null_pct:.1f}%")
        
        # Search functionality
        filtered_df = df
        if enable_search and len(df) > 10:
            search_term = st.text_input(
                "🔍 Search in data",
                key=f"search_{df_id}",
                help="Search across all text columns"
            )
            
            if search_term:
                # Search across string columns
                string_columns = df.select_dtypes(include=['object']).columns
                if not string_columns.empty:
                    mask = df[string_columns].astype(str).apply(
                        lambda x: x.str.contains(search_term, case=False, na=False)
                    ).any(axis=1)
                    filtered_df = df[mask]
                    
                    if len(filtered_df) != len(df):
                        st.caption(f"Found {len(filtered_df)} rows matching '{search_term}'")
        
        # Pagination
        df_to_show = filtered_df
        if enable_pagination and len(filtered_df) > max_rows:
            total_pages = (len(filtered_df) - 1) // max_rows + 1
            
            col1, col2 = st.columns([1, 3])
            
            with col1:
                page = st.selectbox(
                    f"Page (showing {max_rows} rows per page)",
                    range(1, total_pages + 1),
                    key=f"{df_id}_page"
                )
            
            with col2:
                st.caption(f"Page {page} of {total_pages} • Total rows: {len(filtered_df)}")
            
            start_idx = (page - 1) * max_rows
            end_idx = min(start_idx + max_rows, len(filtered_df))
            
            df_to_show = filtered_df.iloc[start_idx:end_idx]
            st.caption(f"Showing rows {start_idx + 1}-{end_idx}")
        
        # Render DataFrame
        st.dataframe(df_to_show, width='stretch')
        
        # Download option using centralized export manager
        from utils.export_handlers.ui_export_manager import UIExportManager
        export_manager = UIExportManager()
        export_manager.render_download_button(
            data=filtered_df,
            label=f"📥 Download {title} CSV",
            filename_prefix=title.lower().replace(' ', '_'),
            key=f"download_{df_id}"
        )
    
    def clear_cache(self, df_id: Optional[str] = None):
        """Clear cached DataFrames."""
        if df_id:
            # Clear specific DataFrame
            keys_to_remove = [k for k in self.cached_dataframes.keys() if k.startswith(df_id)]
            for key in keys_to_remove:
                del self.cached_dataframes[key]
        else:
            # Clear all cached DataFrames
            self.cached_dataframes.clear()


@st.cache_resource
def get_async_dataframe_renderer() -> AsyncDataFrameRenderer:
    """Get or create the global async DataFrame renderer."""
    return AsyncDataFrameRenderer()


def render_async_metrics(
    metrics_id: str,
    metrics_func: Callable[[], Dict[str, Any]],
    title: str,
    columns: int = 4,
    auto_refresh_interval: Optional[float] = None
):
    """
    Render metrics with async loading support.
    
    Args:
        metrics_id: Unique identifier for metrics
        metrics_func: Function that returns metrics dictionary
        title: Title for the metrics display
        columns: Number of columns for metrics layout
        auto_refresh_interval: Auto-refresh interval in seconds (None to disable)
    """
    # Use progressive loader for metrics
    loader = get_progressive_loader()
    
    # Register metrics component if not already registered
    component_id = f"metrics_{metrics_id}"
    if component_id not in loader.components:
        loader.register_component(
            component_id=component_id,
            name=title,
            load_func=metrics_func
        )
    
    # Load metrics
    cache_duration = auto_refresh_interval if auto_refresh_interval else 300.0
    component = loader.load_component(component_id, cache_duration=cache_duration)
    
    # Render based on state
    if component.state == LoadState.LOADING:
        st.markdown(info_box(f"⏳ Loading {title}..."), unsafe_allow_html=True)
        time.sleep(0.5)
        st.rerun()
    
    elif component.state == LoadState.ERROR:
        st.markdown(error_box(f"❌ Error loading {title}: {component.error}"), unsafe_allow_html=True)
        if st.button(f"🔄 Retry {title}", key=f"retry_metrics_{metrics_id}"):
            loader.invalidate_component(component_id)
            st.rerun()
    
    elif component.state == LoadState.LOADED and component.data:
        st.subheader(title)
        
        metrics = component.data
        if isinstance(metrics, dict) and metrics:
            # Create columns for metrics
            cols = st.columns(min(len(metrics), columns))
            
            for i, (key, value) in enumerate(metrics.items()):
                with cols[i % len(cols)]:
                    if isinstance(value, (int, float)):
                        st.metric(key, f"{value:,.0f}" if isinstance(value, int) else f"{value:.2f}")
                    else:
                        st.metric(key, str(value))
        
        # Show last update time
        if auto_refresh_interval and component.last_loaded:
            age = time.time() - component.last_loaded
            st.caption(f"Last updated: {age:.0f}s ago")
            
            # Auto-refresh if needed
            if age >= auto_refresh_interval:
                loader.invalidate_component(component_id)
                st.rerun()
    
    else:
        # Not loaded yet
        st.rerun()


def create_cancel_button(task_or_component_id: str, label: str = "Cancel") -> bool:
    """
    Create a cancel button for background tasks or progressive components.
    
    Args:
        task_or_component_id: ID of task or component to cancel
        label: Button label
        
    Returns:
        True if cancel was requested
    """
    if st.button(f"🛑 {label}", key=f"cancel_{task_or_component_id}"):
        # Try to cancel as background task
        processor = get_background_processor()
        task_cancelled = processor.cancel_task(task_or_component_id)
        
        # Try to invalidate as progressive component
        loader = get_progressive_loader()
        component_invalidated = loader.invalidate_component(task_or_component_id)
        
        if task_cancelled or component_invalidated:
            st.markdown(success_box(f"✅ {label} successful"), unsafe_allow_html=True)
            return True
        else:
            st.markdown(warning_box("⚠️ Nothing to cancel"), unsafe_allow_html=True)
            return False
    
    return False


def display_async_performance_dashboard():
    """Display comprehensive performance dashboard for async components."""
    st.subheader("🚀 Async Performance Dashboard")
    
    # Background processor stats
    processor = get_background_processor()
    all_tasks = processor.get_all_tasks()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        running_count = sum(1 for task in all_tasks.values() if task.status == TaskStatus.RUNNING)
        st.metric("Running Tasks", running_count)
    
    with col2:
        completed_count = sum(1 for task in all_tasks.values() if task.status == TaskStatus.COMPLETED)
        st.metric("Completed Tasks", completed_count)
    
    with col3:
        failed_count = sum(1 for task in all_tasks.values() if task.status == TaskStatus.FAILED)
        st.metric("Failed Tasks", failed_count)
    
    with col4:
        st.metric("Total Tasks", len(all_tasks))
    
    # Progressive loader stats
    loader = get_progressive_loader()
    cache_stats = loader.get_cache_stats()
    
    st.subheader("📊 Component Cache Performance")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Cache Hit Rate", f"{cache_stats['cache_hit_rate']:.1%}")
    
    with col2:
        st.metric("Loaded Components", cache_stats['loaded_components'])
    
    with col3:
        st.metric("Error Components", cache_stats['error_components'])
    
    with col4:
        st.metric("Total Load Time", f"{cache_stats['total_load_time']:.2f}s")
    
    # System performance
    from ..core.background_processor import get_system_performance_info
    system_info = get_system_performance_info()
    
    st.subheader("💻 System Performance")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Memory Usage", f"{system_info['memory_usage_mb']:.1f} MB")
    
    with col2:
        st.metric("Memory %", f"{system_info['memory_percent']:.1f}%")
    
    with col3:
        st.metric("CPU %", f"{system_info['cpu_percent']:.1f}%")
    
    with col4:
        st.metric("Threads", system_info['num_threads'])
    
    # Management buttons
    st.subheader("🛠️ Management")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🗑️ Clear All Caches"):
            loader.clear_cache()
            get_async_dataframe_renderer().clear_cache()
            st.markdown(success_box("All caches cleared"), unsafe_allow_html=True)
            st.rerun()
    
    with col2:
        if st.button("🛑 Cancel All Tasks"):
            renderer = get_async_tab_renderer()
            renderer.clear_all_tabs()
            st.markdown(success_box("All tasks cancelled"), unsafe_allow_html=True)
            st.rerun()
    
    with col3:
        if st.button("🔄 Refresh Dashboard"):
            st.rerun()
