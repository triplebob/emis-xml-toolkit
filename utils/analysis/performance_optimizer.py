"""
Performance Optimization Module - Streamlit Cloud Compatible
Provides cloud-compatible performance monitoring and controls.
"""

import streamlit as st
from typing import Dict, Any


def render_performance_controls():
    """Render Streamlit Cloud compatible performance controls."""
    with st.sidebar.expander("⚡ Performance", expanded=False):
        # File size handling (ticked by default - first)
        chunk_large_files = st.checkbox(
            "Chunk Large Files",
            value=True,
            help="Process very large XML files in memory-efficient chunks"
        )
        
        # Progress display option (ticked by default - second)
        show_progress = st.checkbox(
            "Show Processing Progress",
            value=True,
            help="Display progress updates during XML processing"
        )
        
        # Performance monitoring (unticked by default - third)
        show_metrics = st.checkbox(
            "Show Performance Metrics",
            value=False,
            help="Display processing time and file statistics"
        )
        
        # Processing strategy - only cloud-effective options (last)
        selected_strategy = st.selectbox(
            "Processing Strategy",
            ["Memory Optimized", "Standard"],
            index=0,  # Default to Memory Optimized
            help="Choose processing strategy: Memory Optimized (efficient memory management for large files) or Standard (basic processing for smaller files)"
        )
        
        # Show dynamic help text below the selectbox
        if selected_strategy == "Memory Optimized":
            st.caption("💡 Memory Optimized: Uses efficient memory management for large files and complex lookups")
        else:
            st.caption("💡 Standard: Basic processing suitable for smaller files")
        
        return {
            'strategy': selected_strategy,
            'max_workers': 1,  # Always 1 for cloud compatibility
            'memory_optimize': True,  # Always enabled
            'show_metrics': show_metrics,
            'show_progress': show_progress,
            'chunk_large_files': chunk_large_files,
            'environment': 'cloud'
        }


def display_performance_metrics(metrics: Dict[str, Any]):
    """Display performance metrics in Streamlit."""
    st.markdown("##### ⚡ Performance Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"**Memory Used**  \n{metrics.get('memory_peak_mb', 0):.1f} MB")
    
    with col2:
        st.markdown(f"**Total Processing Time**  \n{metrics.get('total_time', 0):.2f}s")
    
    with col3:
        st.markdown(f"**Processing Strategy**  \n{metrics.get('processing_strategy', 'Unknown')}")
    
    with col4:
        st.markdown(f"**Items Processed**  \n{metrics.get('items_processed', 0)}")
    
