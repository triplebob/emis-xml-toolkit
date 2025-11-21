"""
Optimized Processing Integration for EMIS XML Converter
Integrates background processing, progressive loading, and optimized caching
with existing session state management and Streamlit patterns.
"""

import streamlit as st
import time
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass
import threading
import queue
from functools import wraps

from .session_state import SessionStateKeys
from .background_processor import (
    get_background_processor,
    BackgroundTask,
    TaskStatus,
    create_xml_analysis_task,
    create_snomed_lookup_task
)
from ..ui.progressive_loader import (
    get_progressive_loader,
    progressive_component
)
from ..ui.async_components import (
    get_async_tab_renderer,
    AsyncComponentState
)
from ..utils.lookup import (
    get_optimized_lookup_cache,
    batch_translate_emis_guids
)


@dataclass
class ProcessingContext:
    """Context for optimized processing operations."""
    xml_content: Optional[str] = None
    xml_filename: Optional[str] = None
    emis_guids: Optional[List[Dict]] = None
    lookup_df: Optional[pd.DataFrame] = None
    emis_guid_col: Optional[str] = None
    snomed_code_col: Optional[str] = None
    processing_settings: Optional[Dict[str, Any]] = None
    

class OptimizedProcessor:
    """
    Optimized processor that integrates all performance enhancements
    with existing EMIS XML converter functionality.
    """
    
    def __init__(self):
        """Initialize optimized processor."""
        self.background_processor = get_background_processor()
        self.progressive_loader = get_progressive_loader()
        self.async_renderer = get_async_tab_renderer()
        self.lookup_cache = get_optimized_lookup_cache()
        
        # Track active processing tasks
        self.active_xml_tasks: Dict[str, str] = {}  # file_hash -> task_id
        self.active_translation_tasks: Dict[str, str] = {}  # guid_hash -> task_id
        
        # Processing state management
        self._processing_lock = threading.Lock()
    
    def process_xml_optimized(
        self,
        xml_content: str,
        xml_filename: str,
        settings: Dict[str, Any],
        progress_callback: Optional[Callable] = None
    ) -> str:
        """
        Process XML with optimized background processing and caching.
        
        Args:
            xml_content: XML content to process
            xml_filename: Name of the XML file
            settings: Processing settings from UI
            progress_callback: Optional callback for progress updates
            
        Returns:
            Task ID for monitoring
        """
        with self._processing_lock:
            # Generate content hash for deduplication
            content_hash = str(hash(xml_content))
            
            # Check if we already have this task running
            if content_hash in self.active_xml_tasks:
                existing_task_id = self.active_xml_tasks[content_hash]
                task = self.background_processor.get_task_status(existing_task_id)
                
                if task and task.status == TaskStatus.RUNNING:
                    return existing_task_id
                else:
                    # Clean up stale task
                    del self.active_xml_tasks[content_hash]
            
            # Create new background task for XML processing
            task_id = create_xml_analysis_task(xml_content, xml_filename)
            self.active_xml_tasks[content_hash] = task_id
            
            # Store processing context in session state
            st.session_state.processing_context = ProcessingContext(
                xml_content=xml_content,
                xml_filename=xml_filename,
                processing_settings=settings
            )
            
            return task_id
    
    def translate_codes_optimized(
        self,
        emis_guids: List[Dict],
        lookup_df: pd.DataFrame,
        emis_guid_col: str,
        snomed_code_col: str,
        deduplication_mode: str = 'unique_codes'
    ) -> str:
        """
        Translate EMIS codes with optimized background processing and caching.
        
        Args:
            emis_guids: List of EMIS GUID dictionaries
            lookup_df: Lookup DataFrame
            emis_guid_col: EMIS GUID column name
            snomed_code_col: SNOMED code column name
            deduplication_mode: Deduplication strategy
            
        Returns:
            Task ID for monitoring
        """
        with self._processing_lock:
            # Generate hash for deduplication
            guid_hash = str(hash(str(emis_guids) + deduplication_mode))
            
            # Check if we already have this task running
            if guid_hash in self.active_translation_tasks:
                existing_task_id = self.active_translation_tasks[guid_hash]
                task = self.background_processor.get_task_status(existing_task_id)
                
                if task and task.status == TaskStatus.RUNNING:
                    return existing_task_id
                else:
                    # Clean up stale task
                    del self.active_translation_tasks[guid_hash]
            
            # Pre-load lookup cache for faster processing
            self.lookup_cache.load_from_dataframe(lookup_df, emis_guid_col, snomed_code_col)
            
            # Create background task for translation
            task_id = create_snomed_lookup_task(
                emis_guids, lookup_df, emis_guid_col, snomed_code_col, deduplication_mode
            )
            
            self.active_translation_tasks[guid_hash] = task_id
            
            # Update processing context
            if hasattr(st.session_state, 'processing_context'):
                st.session_state.processing_context.emis_guids = emis_guids
                st.session_state.processing_context.lookup_df = lookup_df
                st.session_state.processing_context.emis_guid_col = emis_guid_col
                st.session_state.processing_context.snomed_code_col = snomed_code_col
            
            return task_id
    
    def render_optimized_results_tabs(self, results: Optional[Dict[str, Any]] = None):
        """
        Render results tabs with optimized async loading and progressive components.
        
        Args:
            results: Translation results (optional, will use session state if not provided)
        """
        if results is None:
            results = st.session_state.get(SessionStateKeys.RESULTS)
        
        if not results:
            st.info("📤 Upload and process an XML file to see results")
            return
        
        # Create optimized tab structure
        main_tabs = st.tabs([
            "🏥 Clinical Codes", 
            "🔍 Search Analysis", 
            "📋 List Reports", 
            "📊 Audit Reports", 
            "📈 Aggregate Reports"
        ])
        
        with main_tabs[0]:
            self._render_clinical_codes_tab_optimized(results)
        
        with main_tabs[1]:
            self._render_search_analysis_tab_optimized()
        
        with main_tabs[2]:
            self._render_list_reports_tab_optimized()
        
        with main_tabs[3]:
            self._render_audit_reports_tab_optimized()
        
        with main_tabs[4]:
            self._render_aggregate_reports_tab_optimized()
    
    def _render_clinical_codes_tab_optimized(self, results: Dict[str, Any]):
        """Render clinical codes tab with progressive loading."""
        
        @progressive_component(
            component_id="clinical_codes_summary",
            name="Clinical Codes Summary",
            cache_duration=300.0
        )
        def render_clinical_summary():
            # This runs in background - return data, not Streamlit calls
            clinical_count = len(results.get('clinical', []))
            medication_count = len(results.get('medications', []))
            pseudo_clinical_count = len(results.get('clinical_pseudo_members', []))
            pseudo_medication_count = len(results.get('medication_pseudo_members', []))
            
            return {
                'clinical_count': clinical_count,
                'medication_count': medication_count,
                'pseudo_clinical_count': pseudo_clinical_count,
                'pseudo_medication_count': pseudo_medication_count,
                'total_count': clinical_count + medication_count + pseudo_clinical_count + pseudo_medication_count
            }
        
        # Get summary data
        summary_data = render_clinical_summary()
        
        if summary_data:
            # Render summary metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Clinical Codes", summary_data['clinical_count'])
            with col2:
                st.metric("Medications", summary_data['medication_count'])
            with col3:
                st.metric("Pseudo Clinical", summary_data['pseudo_clinical_count'])
            with col4:
                st.metric("Pseudo Medications", summary_data['pseudo_medication_count'])
        
        # Render clinical codes data table with async loading
        from ..ui.async_components import get_async_dataframe_renderer
        
        async_renderer = get_async_dataframe_renderer()
        
        def get_clinical_data():
            return pd.DataFrame(results.get('clinical', []))
        
        async_renderer.render_async_dataframe(
            df_id="clinical_codes",
            data_func=get_clinical_data,
            title="Clinical Codes",
            max_rows=1000,
            enable_pagination=True,
            enable_search=True
        )
        
        # Render medications data table
        def get_medications_data():
            return pd.DataFrame(results.get('medications', []))
        
        async_renderer.render_async_dataframe(
            df_id="medications",
            data_func=get_medications_data,
            title="Medications",
            max_rows=1000,
            enable_pagination=True,
            enable_search=True
        )
    
    def _render_search_analysis_tab_optimized(self):
        """Render search analysis tab with async loading."""
        
        # Use async tab renderer for heavy search analysis
        def render_search_content():
            xml_content = st.session_state.get(SessionStateKeys.XML_CONTENT)
            if xml_content:
                from ..analysis.xml_structure_analyzer import analyze_search_rules
                analysis = analyze_search_rules(xml_content)
                
                # Return data structure that can be rendered
                return {
                    'analysis': analysis,
                    'search_count': len(analysis.searches) if analysis.searches else 0,
                    'folder_count': len(analysis.folders) if analysis.folders else 0
                }
            return None
        
        self.async_renderer.render_async_tab(
            tab_id="search_analysis",
            tab_name="Search Analysis",
            content_func=render_search_content,
            show_progress=True,
            auto_refresh=True
        )
    
    def _render_list_reports_tab_optimized(self):
        """Render list reports tab with progressive loading."""
        
        @progressive_component(
            component_id="list_reports",
            name="List Reports",
            cache_duration=600.0
        )
        def get_list_reports_data():
            analysis = st.session_state.get(SessionStateKeys.XML_STRUCTURE_ANALYSIS)
            if analysis and hasattr(analysis, 'reports'):
                list_reports = [r for r in analysis.reports if getattr(r, 'report_type', None) == 'list']
                return pd.DataFrame([{
                    'Name': r.name,
                    'ID': r.id,
                    'Type': getattr(r, 'report_type', 'list'),
                    'Criteria Count': len(getattr(r, 'criteria', [])),
                } for r in list_reports])
            return pd.DataFrame()
        
        list_reports_df = get_list_reports_data()
        if list_reports_df is not None and not list_reports_df.empty:
            st.dataframe(list_reports_df, width='stretch')
        else:
            st.info("No list reports found in the XML file")
    
    def _render_audit_reports_tab_optimized(self):
        """Render audit reports tab with progressive loading."""
        
        @progressive_component(
            component_id="audit_reports",
            name="Audit Reports", 
            cache_duration=600.0
        )
        def get_audit_reports_data():
            analysis = st.session_state.get(SessionStateKeys.XML_STRUCTURE_ANALYSIS)
            if analysis and hasattr(analysis, 'reports'):
                audit_reports = [r for r in analysis.reports if getattr(r, 'report_type', None) == 'audit']
                return pd.DataFrame([{
                    'Name': r.name,
                    'ID': r.id,
                    'Type': getattr(r, 'report_type', 'audit'),
                    'Criteria Count': len(getattr(r, 'criteria', [])),
                } for r in audit_reports])
            return pd.DataFrame()
        
        audit_reports_df = get_audit_reports_data()
        if audit_reports_df is not None and not audit_reports_df.empty:
            st.dataframe(audit_reports_df, width='stretch')
        else:
            st.info("No audit reports found in the XML file")
    
    def _render_aggregate_reports_tab_optimized(self):
        """Render aggregate reports tab with progressive loading."""
        
        @progressive_component(
            component_id="aggregate_reports",
            name="Aggregate Reports",
            cache_duration=600.0
        )
        def get_aggregate_reports_data():
            analysis = st.session_state.get(SessionStateKeys.XML_STRUCTURE_ANALYSIS)
            if analysis and hasattr(analysis, 'reports'):
                aggregate_reports = [r for r in analysis.reports if getattr(r, 'report_type', None) == 'aggregate']
                return pd.DataFrame([{
                    'Name': r.name,
                    'ID': r.id,
                    'Type': getattr(r, 'report_type', 'aggregate'),
                    'Criteria Count': len(getattr(r, 'criteria', [])),
                } for r in aggregate_reports])
            return pd.DataFrame()
        
        aggregate_reports_df = get_aggregate_reports_data()
        if aggregate_reports_df is not None and not aggregate_reports_df.empty:
            st.dataframe(aggregate_reports_df, width='stretch')
        else:
            st.info("No aggregate reports found in the XML file")
    
    def monitor_processing_tasks(self) -> Dict[str, TaskStatus]:
        """Monitor all active processing tasks."""
        task_statuses = {}
        
        # Monitor XML analysis tasks
        for content_hash, task_id in list(self.active_xml_tasks.items()):
            task = self.background_processor.get_task_status(task_id)
            if task:
                task_statuses[f"xml_{content_hash}"] = task.status
                
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    # Clean up completed task
                    del self.active_xml_tasks[content_hash]
        
        # Monitor translation tasks
        for guid_hash, task_id in list(self.active_translation_tasks.items()):
            task = self.background_processor.get_task_status(task_id)
            if task:
                task_statuses[f"translation_{guid_hash}"] = task.status
                
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    # Clean up completed task
                    del self.active_translation_tasks[guid_hash]
        
        return task_statuses
    
    def cancel_all_processing(self):
        """Cancel all active processing tasks."""
        # Cancel XML tasks
        for task_id in list(self.active_xml_tasks.values()):
            self.background_processor.cancel_task(task_id)
        
        # Cancel translation tasks
        for task_id in list(self.active_translation_tasks.values()):
            self.background_processor.cancel_task(task_id)
        
        # Clear async tabs
        self.async_renderer.clear_all_tabs()
        
        # Clear progressive loader cache
        self.progressive_loader.clear_cache()
        
        # Clear lookup cache
        self.lookup_cache.clear_cache()
        
        # Reset tracking
        self.active_xml_tasks.clear()
        self.active_translation_tasks.clear()
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        # Background processor stats
        all_tasks = self.background_processor.get_all_tasks()
        
        # Progressive loader stats
        cache_stats = self.progressive_loader.get_cache_stats()
        
        # Lookup cache stats
        lookup_stats = self.lookup_cache.get_cache_stats()
        
        # System performance
        from .background_processor import get_system_performance_info
        system_info = get_system_performance_info()
        
        return {
            'background_tasks': {
                'total': len(all_tasks),
                'running': sum(1 for t in all_tasks.values() if t.status == TaskStatus.RUNNING),
                'completed': sum(1 for t in all_tasks.values() if t.status == TaskStatus.COMPLETED),
                'failed': sum(1 for t in all_tasks.values() if t.status == TaskStatus.FAILED)
            },
            'progressive_cache': cache_stats,
            'lookup_cache': lookup_stats,
            'system': system_info,
            'active_xml_tasks': len(self.active_xml_tasks),
            'active_translation_tasks': len(self.active_translation_tasks)
        }


@st.cache_resource
def get_optimized_processor() -> OptimizedProcessor:
    """Get or create the global optimized processor instance."""
    return OptimizedProcessor()


def render_performance_monitoring_sidebar():
    """Render performance monitoring controls in sidebar."""
    with st.sidebar.expander("🚀 Performance Monitor", expanded=False):
        processor = get_optimized_processor()
        summary = processor.get_performance_summary()
        
        st.markdown("**Background Tasks**")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Running", summary['background_tasks']['running'])
        with col2:
            st.metric("Completed", summary['background_tasks']['completed'])
        
        st.markdown("**Cache Performance**")
        col1, col2 = st.columns(2)
        with col1:
            hit_rate = summary['progressive_cache']['cache_hit_rate']
            st.metric("Hit Rate", f"{hit_rate:.1%}")
        with col2:
            lookup_hit_rate = summary['lookup_cache']['hit_rate']
            st.metric("Lookup Hit", f"{lookup_hit_rate:.1%}")
        
        st.markdown("**System**")
        col1, col2 = st.columns(2)
        with col1:
            memory_mb = summary['system']['memory_usage_mb']
            st.metric("Memory", f"{memory_mb:.0f}MB")
        with col2:
            cpu_pct = summary['system']['cpu_percent']
            st.metric("CPU", f"{cpu_pct:.0f}%")
        
        # Management buttons
        if st.button("🛑 Cancel All", key="cancel_all_processing"):
            processor.cancel_all_processing()
            st.success("All processing cancelled")
            st.rerun()
        
        if st.button("🗑️ Clear Caches", key="clear_all_caches"):
            processor.progressive_loader.clear_cache()
            processor.lookup_cache.clear_cache()
            st.success("All caches cleared")
            st.rerun()


def integrate_with_existing_workflow():
    """
    Integration wrapper to update existing workflow with optimized processing.
    This function can be called from the main streamlit_app.py to enable optimizations.
    """
    # Initialize optimized processor
    processor = get_optimized_processor()
    
    # Store in session state for access from other modules
    st.session_state.optimized_processor = processor
    
    # Add performance monitoring to sidebar
    render_performance_monitoring_sidebar()
    
    # Return processor for direct use
    return processor


# Decorator for optimizing existing functions
def optimize_processing(
    cache_duration: float = 300.0,
    use_background: bool = True,
    show_progress: bool = True
):
    """
    Decorator to optimize existing processing functions with background processing and caching.
    
    Args:
        cache_duration: Cache duration in seconds
        use_background: Whether to use background processing
        show_progress: Whether to show progress indicators
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if use_background:
                # Use background processing
                processor = get_optimized_processor()
                
                # Generate task ID based on function and arguments
                task_id = f"{func.__name__}_{hash(str(args) + str(kwargs))}"
                
                # Submit background task
                background_task = processor.background_processor.submit_task(
                    task_id=task_id,
                    name=f"Processing {func.__name__}",
                    func=func,
                    *args,
                    **kwargs
                )
                
                # Monitor task
                while background_task.status == TaskStatus.RUNNING:
                    if show_progress:
                        st.info(f"⏳ Processing {func.__name__}...")
                    time.sleep(1.0)
                    background_task = processor.background_processor.get_task_status(task_id)
                
                if background_task.status == TaskStatus.COMPLETED:
                    return background_task.result
                else:
                    st.error(f"Processing failed: {background_task.error}")
                    return None
            else:
                # Use progressive component caching
                loader = get_progressive_loader()
                component_id = f"{func.__name__}_{hash(str(args) + str(kwargs))}"
                
                if component_id not in loader.components:
                    loader.register_component(
                        component_id=component_id,
                        name=func.__name__,
                        load_func=lambda: func(*args, **kwargs)
                    )
                
                component = loader.load_component(component_id, cache_duration=cache_duration)
                
                if component.state == LoadState.LOADED:
                    return component.data
                elif component.state == LoadState.ERROR:
                    st.error(f"Error in {func.__name__}: {component.error}")
                    return None
                else:
                    if show_progress:
                        st.info(f"⏳ Loading {func.__name__}...")
                    st.rerun()
        
        return wrapper
    return decorator
