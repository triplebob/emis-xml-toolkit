from .theme import info_box, success_box, warning_box, error_box
from ..common.ui_error_handling import display_generic_error
"""
Progressive Loading System for EMIS XML Converter UI
Implements lazy evaluation and async loading for heavy report tab rendering.
Based on Streamlit optimization patterns for non-blocking UI updates.
"""

import streamlit as st
import pandas as pd
import time
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import threading
import queue
import weakref
from functools import wraps


class LoadState(Enum):
    """Loading state enumeration for progressive components."""
    NOT_LOADED = "not_loaded"
    LOADING = "loading"
    LOADED = "loaded"
    ERROR = "error"
    REFRESHING = "refreshing"


@dataclass
class ProgressiveComponent:
    """Container for progressively loaded UI components."""
    component_id: str
    name: str
    load_func: Callable
    state: LoadState = LoadState.NOT_LOADED
    data: Any = None
    error: Optional[str] = None
    last_loaded: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    
    def should_reload(self, cache_duration: float = 300.0) -> bool:
        """Check if component should be reloaded based on cache duration."""
        if self.state in [LoadState.NOT_LOADED, LoadState.ERROR]:
            return True
        
        if self.last_loaded is None:
            return True
        
        return (time.time() - self.last_loaded) > cache_duration


class ProgressiveLoader:
    """
    Progressive loader for heavy UI components.
    Implements lazy loading, caching, and background refresh.
    """
    
    def __init__(self):
        """Initialize progressive loader."""
        self.components: Dict[str, ProgressiveComponent] = {}
        self._load_queue = queue.Queue()
        self._loader_thread = None
        self._stop_loading = threading.Event()
        self._lock = threading.Lock()
    
    def register_component(
        self,
        component_id: str,
        name: str,
        load_func: Callable,
        dependencies: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> ProgressiveComponent:
        """
        Register a component for progressive loading.
        
        Args:
            component_id: Unique identifier for the component
            name: Human-readable component name
            load_func: Function to load component data
            dependencies: List of component IDs this depends on
            metadata: Additional metadata for the component
            
        Returns:
            ProgressiveComponent object
        """
        with self._lock:
            component = ProgressiveComponent(
                component_id=component_id,
                name=name,
                load_func=load_func,
                dependencies=dependencies or [],
                metadata=metadata or {}
            )
            
            self.components[component_id] = component
            return component
    
    def load_component(
        self,
        component_id: str,
        force_reload: bool = False,
        cache_duration: float = 300.0
    ) -> ProgressiveComponent:
        """
        Load a component with progressive loading support.
        
        Args:
            component_id: ID of component to load
            force_reload: Force reload even if cached
            cache_duration: Cache duration in seconds
            
        Returns:
            ProgressiveComponent with loaded data
        """
        with self._lock:
            if component_id not in self.components:
                raise ValueError(f"Component {component_id} not registered")
            
            component = self.components[component_id]
            
            # Check if reload is needed
            if not force_reload and not component.should_reload(cache_duration):
                return component
            
            # Check dependencies
            for dep_id in component.dependencies:
                if dep_id in self.components:
                    dep_component = self.components[dep_id]
                    if dep_component.state not in [LoadState.LOADED]:
                        # Load dependency first
                        self.load_component(dep_id, force_reload=False, cache_duration=cache_duration)
            
            # Set loading state
            component.state = LoadState.LOADING
            
            try:
                # Execute load function
                start_time = time.time()
                component.data = component.load_func()
                
                # Update component state
                component.state = LoadState.LOADED
                component.last_loaded = time.time()
                component.error = None
                
                # Store performance metadata
                component.metadata['load_time'] = time.time() - start_time
                component.metadata['data_size'] = self._estimate_data_size(component.data)
                
            except Exception as e:
                component.state = LoadState.ERROR
                component.error = str(e)
                component.data = None
            
            return component
    
    def get_component(self, component_id: str) -> Optional[ProgressiveComponent]:
        """Get component without loading."""
        with self._lock:
            return self.components.get(component_id)
    
    def invalidate_component(self, component_id: str) -> bool:
        """Invalidate component cache to force reload."""
        with self._lock:
            if component_id in self.components:
                component = self.components[component_id]
                component.state = LoadState.NOT_LOADED
                component.data = None
                component.last_loaded = None
                return True
            return False
    
    def clear_cache(self):
        """Clear all cached components."""
        with self._lock:
            for component in self.components.values():
                component.state = LoadState.NOT_LOADED
                component.data = None
                component.last_loaded = None
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_components = len(self.components)
            loaded_components = sum(1 for c in self.components.values() if c.state == LoadState.LOADED)
            error_components = sum(1 for c in self.components.values() if c.state == LoadState.ERROR)
            
            total_load_time = sum(
                c.metadata.get('load_time', 0) 
                for c in self.components.values() 
                if c.state == LoadState.LOADED
            )
            
            return {
                'total_components': total_components,
                'loaded_components': loaded_components,
                'error_components': error_components,
                'cache_hit_rate': loaded_components / total_components if total_components > 0 else 0,
                'total_load_time': total_load_time
            }
    
    def _estimate_data_size(self, data: Any) -> int:
        """Estimate memory size of data object."""
        try:
            if isinstance(data, pd.DataFrame):
                return data.memory_usage(deep=True).sum()
            elif isinstance(data, (list, tuple)):
                return len(data)
            elif isinstance(data, dict):
                return len(data)
            elif hasattr(data, '__sizeof__'):
                return data.__sizeof__()
            else:
                return 0
        except Exception:
            return 0


# Global loader instance
@st.cache_resource
def get_progressive_loader() -> ProgressiveLoader:
    """Get or create the global progressive loader instance."""
    return ProgressiveLoader()


def progressive_component(
    component_id: str,
    name: str,
    dependencies: List[str] = None,
    cache_duration: float = 300.0,
    show_progress: bool = True
):
    """
    Decorator for creating progressive components.
    
    Args:
        component_id: Unique identifier for the component
        name: Human-readable component name
        dependencies: List of component IDs this depends on
        cache_duration: Cache duration in seconds
        show_progress: Whether to show loading progress
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            loader = get_progressive_loader()
            
            # Register component if not already registered
            if component_id not in loader.components:
                loader.register_component(
                    component_id=component_id,
                    name=name,
                    load_func=lambda: func(*args, **kwargs),
                    dependencies=dependencies
                )
            
            # Load component
            component = loader.load_component(
                component_id=component_id,
                cache_duration=cache_duration
            )
            
            # Render based on state
            if component.state == LoadState.LOADING and show_progress:
                with st.container():
                    from .theme import info_box
                    st.markdown(info_box(f"⏳ Loading {component.name}..."), unsafe_allow_html=True)
                    progress_bar = st.progress(0)
                    
                    # Simulate progress for user feedback
                    for i in range(10):
                        progress_bar.progress((i + 1) / 10)
                        time.sleep(0.1)
                    
                    progress_bar.empty()
                    st.rerun()
            
            elif component.state == LoadState.ERROR:
                from .theme import error_box
                display_generic_error(f"❌ Error loading {component.name}: {component.error}", "error")
                if st.button(f"🔄 Retry {component.name}", key=f"retry_{component_id}"):
                    loader.invalidate_component(component_id)
                    st.rerun()
                return None
            
            elif component.state == LoadState.LOADED:
                return component.data
            
            else:
                # Not loaded - trigger load on next rerun
                st.rerun()
                return None
        
        return wrapper
    return decorator


def render_loading_placeholder(
    name: str,
    estimated_time: Optional[float] = None,
    show_spinner: bool = True
):
    """
    Render a loading placeholder for progressive components.
    
    Args:
        name: Name of the component being loaded
        estimated_time: Estimated loading time in seconds
        show_spinner: Whether to show a spinner
    """
    if show_spinner:
        with st.spinner(f"Loading {name}..."):
            if estimated_time:
                st.caption(f"⏱️ Estimated time: {estimated_time:.1f}s")
            time.sleep(0.5)  # Brief pause for visual feedback
    else:
        from .theme import info_box
        st.markdown(info_box(f"⏳ Loading {name}..."), unsafe_allow_html=True)
        if estimated_time:
            st.caption(f"⏱️ Estimated time: {estimated_time:.1f}s")


def create_lazy_dataframe_renderer(
    component_id: str,
    data_func: Callable[[], pd.DataFrame],
    title: str,
    max_rows: int = 1000,
    enable_pagination: bool = True
):
    """
    Create a lazy DataFrame renderer with pagination support.
    
    Args:
        component_id: Unique identifier for the component
        data_func: Function that returns DataFrame data
        title: Title for the DataFrame display
        max_rows: Maximum rows to display at once
        enable_pagination: Whether to enable pagination
    """
    @progressive_component(
        component_id=component_id,
        name=title,
        cache_duration=600.0  # Cache for 10 minutes
    )
    def render_dataframe():
        df = data_func()
        
        if df is None or df.empty:
            from .theme import info_box
            st.markdown(info_box(f"No data available for {title}"), unsafe_allow_html=True)
            return None
        
        st.subheader(title)
        
        # Show basic stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Rows", len(df))
        with col2:
            st.metric("Columns", len(df.columns))
        with col3:
            memory_usage = df.memory_usage(deep=True).sum() / 1024 / 1024
            st.metric("Memory", f"{memory_usage:.1f} MB")
        
        # Pagination if needed
        if enable_pagination and len(df) > max_rows:
            total_pages = (len(df) - 1) // max_rows + 1
            page = st.selectbox(
                f"Page (showing {max_rows} rows per page)",
                range(1, total_pages + 1),
                key=f"{component_id}_page"
            )
            
            start_idx = (page - 1) * max_rows
            end_idx = min(start_idx + max_rows, len(df))
            
            st.caption(f"Showing rows {start_idx + 1}-{end_idx} of {len(df)}")
            df_to_show = df.iloc[start_idx:end_idx]
        else:
            df_to_show = df
        
        # Render DataFrame
        st.dataframe(df_to_show, width='stretch')
        
        return df
    
    return render_dataframe


def create_lazy_metrics_renderer(
    component_id: str,
    metrics_func: Callable[[], Dict[str, Any]],
    title: str
):
    """
    Create a lazy metrics renderer.
    
    Args:
        component_id: Unique identifier for the component
        metrics_func: Function that returns metrics dictionary
        title: Title for the metrics display
    """
    @progressive_component(
        component_id=component_id,
        name=title,
        cache_duration=300.0  # Cache for 5 minutes
    )
    def render_metrics():
        metrics = metrics_func()
        
        if not metrics:
            from .theme import info_box
            st.markdown(info_box(f"No metrics available for {title}"), unsafe_allow_html=True)
            return None
        
        st.subheader(title)
        
        # Create columns based on number of metrics
        num_metrics = len(metrics)
        cols = st.columns(min(num_metrics, 4))
        
        for i, (key, value) in enumerate(metrics.items()):
            with cols[i % len(cols)]:
                if isinstance(value, (int, float)):
                    st.metric(key, value)
                else:
                    st.metric(key, str(value))
        
        return metrics
    
    return render_metrics


def monitor_component_performance():
    """Monitor and display progressive loading performance metrics."""
    loader = get_progressive_loader()
    stats = loader.get_cache_stats()
    
    with st.expander("🔍 Progressive Loading Performance", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Components", stats['total_components'])
        with col2:
            st.metric("Loaded", stats['loaded_components'])
        with col3:
            st.metric("Cache Hit Rate", f"{stats['cache_hit_rate']:.1%}")
        with col4:
            st.metric("Total Load Time", f"{stats['total_load_time']:.2f}s")
        
        if stats['error_components'] > 0:
            from .theme import warning_box
            st.markdown(warning_box(f"⚠️ {stats['error_components']} components have errors"), unsafe_allow_html=True)
        
        # Component details
        if st.checkbox("Show Component Details"):
            component_data = []
            for comp_id, component in loader.components.items():
                component_data.append({
                    'ID': comp_id,
                    'Name': component.name,
                    'State': component.state.value,
                    'Load Time': component.metadata.get('load_time', 0),
                    'Data Size': component.metadata.get('data_size', 0),
                    'Dependencies': len(component.dependencies)
                })
            
            if component_data:
                df = pd.DataFrame(component_data)
                st.dataframe(df, width='stretch')


def clear_progressive_cache():
    """Utility function to clear progressive loading cache."""
    loader = get_progressive_loader()
    loader.clear_cache()
    from .theme import success_box
    st.markdown(success_box("🗑️ Progressive loading cache cleared"), unsafe_allow_html=True)
    st.rerun()
