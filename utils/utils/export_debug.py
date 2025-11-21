"""
Export debugging utilities for tracking file creation and cleanup.
Only active when debug mode is enabled via session state.
"""

import streamlit as st
import sys
import gc
import weakref
from typing import Any, Dict, Optional
from ..core.session_state import SessionStateKeys


def log_export_created(export_type: str, file_format: str, file_size: int, context: str = ""):
    """
    Log when an export file is created.
    Only logs when debug_mode session state is True.
    
    Args:
        export_type: Type of export (e.g., 'Clinical Codes', 'List Report', 'Search Export')
        file_format: File format (e.g., 'CSV', 'Excel', 'JSON', 'TXT')
        file_size: Size of the file in bytes
        context: Additional context about the export
    """
    if not st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        return
        
    context_str = f" ({context})" if context else ""
    print(f"[EXPORT DEBUG] CREATED: {export_type} {file_format} - Size: {file_size:,} bytes{context_str}", file=sys.stderr)


def log_export_cleanup(export_type: str, file_format: str, context: str = ""):
    """
    Log when an export file is cleaned up by garbage collection.
    Only logs when debug_mode session state is True.
    
    Args:
        export_type: Type of export (e.g., 'Clinical Codes', 'List Report', 'Search Export')
        file_format: File format (e.g., 'CSV', 'Excel', 'JSON', 'TXT')
        context: Additional context about the cleanup
    """
    if not st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        return
        
    context_str = f" ({context})" if context else ""
    print(f"[EXPORT DEBUG] CLEANUP: {export_type} {file_format}{context_str}", file=sys.stderr)


def track_export_object(obj: Any, export_type: str, file_format: str, context: str = ""):
    """
    Track an export object for garbage collection debugging.
    Creates a weak reference and logs when the object is collected.
    Only active when debug_mode session state is True.
    
    Args:
        obj: The export object to track
        export_type: Type of export
        file_format: File format
        context: Additional context
    """
    if not st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        return
        
    def cleanup_callback(ref):
        log_export_cleanup(export_type, file_format, context)
    
    # Create weak reference with cleanup callback
    weakref.ref(obj, cleanup_callback)


def log_memory_after_export(export_type: str, file_format: str):
    """
    Log memory usage after export creation.
    Only logs when debug_mode session state is True.
    
    Args:
        export_type: Type of export
        file_format: File format
    """
    if not st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        return
        
    try:
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / (1024 * 1024)
        
        print(f"[EXPORT DEBUG] MEMORY: {export_type} {file_format} - Current memory: {memory_mb:.1f} MB", file=sys.stderr)
    except Exception:
        # Silently ignore memory monitoring errors
        pass


def force_gc_and_log(context: str = ""):
    """
    Force garbage collection and log the action.
    Only active when debug_mode session state is True.
    
    Args:
        context: Context for the garbage collection
    """
    if not st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        return
        
    context_str = f" ({context})" if context else ""
    collected = gc.collect()
    print(f"[EXPORT DEBUG] GC: Forced garbage collection{context_str} - Collected {collected} objects", file=sys.stderr)
