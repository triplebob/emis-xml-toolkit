import streamlit as st
import re
import psutil
import os
from ..utils.lookup import load_lookup_table, get_lookup_statistics
from ..utils.caching.lookup_cache import get_cached_emis_lookup

# NHS Terminology Server integration
try:
    from ..terminology_server.expansion_ui import render_terminology_server_status
    NHS_TERMINOLOGY_AVAILABLE = True
except ImportError:
    NHS_TERMINOLOGY_AVAILABLE = False

def get_memory_usage():
    """Get current memory usage information"""
    try:
        # Get current process
        process = psutil.Process(os.getpid())
        
        # Memory info in bytes
        memory_info = process.memory_info()
        current_memory_mb = memory_info.rss / (1024 * 1024)  # RSS (Resident Set Size)
        virtual_memory_mb = memory_info.vms / (1024 * 1024)  # Virtual Memory Size
        
        # System memory info
        system_memory = psutil.virtual_memory()
        system_total_gb = system_memory.total / (1024 * 1024 * 1024)
        system_available_gb = system_memory.available / (1024 * 1024 * 1024)
        system_usage_percent = system_memory.percent
        
        # Memory peak tracking (store in session state)
        if 'memory_peak_mb' not in st.session_state:
            st.session_state.memory_peak_mb = current_memory_mb
        else:
            if current_memory_mb > st.session_state.memory_peak_mb:
                st.session_state.memory_peak_mb = current_memory_mb
        
        return {
            'current_mb': current_memory_mb,
            'virtual_mb': virtual_memory_mb,
            'peak_mb': st.session_state.memory_peak_mb,
            'system_total_gb': system_total_gb,
            'system_available_gb': system_available_gb,
            'system_usage_percent': system_usage_percent
        }
    except Exception as e:
        return None

def get_memory_status_color(memory_mb):
    """Determine status color based on memory usage"""
    # Streamlit Cloud limit is around 2.7GB (2700MB)
    # But we'll use more conservative thresholds
    if memory_mb < 1000:  # Under 1GB
        return "success"
    elif memory_mb < 1800:  # 1-1.8GB
        return "info" 
    elif memory_mb < 2300:  # 1.8-2.3GB
        return "warning"
    else:  # Over 2.3GB
        return "error"

def format_memory_display(memory_mb):
    """Format memory for display"""
    if memory_mb < 1024:
        return f"{memory_mb:.0f} MB"
    else:
        return f"{memory_mb/1024:.1f} GB"

@st.cache_data(ttl=3600, show_spinner=False)
def _get_cached_status_content(lookup_size, version_str, load_source):
    """Cache static status content that doesn't change during session"""
    source_icons = {
        "session": "⚡",
        "cache": "🔐", 
        "github": "📥"
    }
    source_messages = {
        "session": "Session data",
        "cache": "Encrypted cache", 
        "github": "GitHub (fallback)"
    }
    
    icon = source_icons.get(load_source, "📥")
    message = source_messages.get(load_source, "Unknown source")
    
    return f"{icon} Lookup table loaded from {message}: {lookup_size:,} total mappings"

@st.cache_data(ttl=3600, show_spinner=False)
def _get_cached_version_info(version_info_dict):
    """Cache version information that doesn't change during session"""
    if not version_info_dict or len(version_info_dict) == 0:
        return None
    return version_info_dict.copy()

def render_status_bar():
    """Render the status bar in the sidebar with lookup table information."""
    with st.sidebar:
        st.header("🗃️ Lookup Table Status")
        
        # Create status placeholder for dynamic updates
        status_placeholder = st.empty()
        
        try:
            # First try to use cached lookup data
            lookup_df = st.session_state.get('lookup_df')
            emis_guid_col = st.session_state.get('emis_guid_col')
            snomed_code_col = st.session_state.get('snomed_code_col')
            version_info = st.session_state.get('lookup_version_info', {})
            
            load_source = "session"  # Track where data came from
            
            # If not in session state, load lookup table (which will check cache internally)
            if lookup_df is None or emis_guid_col is None or snomed_code_col is None:
                # The load_lookup_table function handles cache checking internally
                lookup_df, emis_guid_col, snomed_code_col, version_info = load_lookup_table()
                
                # Determine the actual source from version_info
                load_source = version_info.get('load_source', 'github') if version_info else 'github'
            
            # Clear status placeholder
            status_placeholder.empty()
                
            # Get lookup statistics
            stats = get_lookup_statistics(lookup_df)
            
            # Use cached status content for better performance
            status_message = _get_cached_status_content(
                stats['total_count'], 
                version_info.get('emis_version', 'Unknown'),
                load_source
            )
            st.success(status_message)
            st.info(f"🩺 SCT Codes: {stats['clinical_count']:,}")
            st.info(f"💊 Medications: {stats['medication_count']:,}")
            
            if stats['other_count'] > 0:
                st.info(f"📊 Other types: {stats['other_count']:,}")
            
            # Display version information if available
            if version_info and len(version_info) > 0:
                with st.sidebar.expander("📊 Version Info", expanded=False):
                    if 'emis_version' in version_info:
                        st.markdown("**🏥 EMIS MKB Release**")
                        st.caption(f"📘 {version_info['emis_version']}")
                        
                        if 'snomed_version' in version_info:
                            # Parse SNOMED version string
                            # Example: "SNOMED Clinical Terms version: 20250201 [R] (February 2025 Release)"
                            snomed_raw = version_info['snomed_version']
                            
                            st.markdown("**📋 SNOMED Clinical Terms**")
                            # Extract the version number and release info
                            match = re.search(r'(\d{8})\s*\[R\]\s*\(([^)]+)\)', snomed_raw)
                            if match:
                                version_num = match.group(1)
                                # Convert version_num (yyyymmdd) to UK format (dd/mm/yyyy)
                                uk_date = f"{version_num[6:8]}/{version_num[4:6]}/{version_num[0:4]}"
                                st.caption(f"📘 {uk_date}")
                            else:
                                st.caption(f"📘 {snomed_raw}")
                        
                        if 'extract_date' in version_info:
                            # Convert extract_date to UK format (dd/mm/yyyy), remove time if present
                            extract_date_raw = version_info['extract_date']
                            
                            st.markdown("**📅 Last DB Update**")
                            # Try to extract just the date part (assume format yyyy-mm-dd or yyyy-mm-ddTHH:MM:SS)
                            date_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', extract_date_raw)
                            if date_match:
                                uk_extract_date = f"{date_match.group(3)}/{date_match.group(2)}/{date_match.group(1)}"
                                st.caption(f"📘 {uk_extract_date}")
                            else:
                                st.caption(f"📘 {extract_date_raw}")
                
            # Changelog section - Direct in-app display 
            with st.sidebar.expander("🎯 What's New - v2.2.0", expanded=False):
                st.markdown("""
                    **🚀 Major Performance & Caching Overhaul - v2.2.0**
                    
                    Comprehensive caching architecture and performance improvements eliminating report dropdown hangs and memory issues.
                    
                    **⚡ Caching Infrastructure:**
                    - New centralized cache manager with optimized TTL settings
                    - SNOMED lookup caching (10,000 entries, 1-hour TTL)
                    - Clinical data caching (5,000 entries, 30-minute TTL)
                    - Report-specific session state caching with instant dropdown switching
                    - Eliminated expensive reprocessing on every report selection
                    
                    **💻 Memory Management:**
                    - New Memory Usage section in sidebar with real-time monitoring
                    - Memory peak tracking and reset functionality
                    - Automatic garbage collection after large operations
                    - TTL-based cache expiration preventing memory accumulation
                    - Report switching time reduced from 10+ seconds to <1 second
                    
                    **📋 Export System Improvements:**
                    - NUMERIC_VALUE filters show actual values ("Value greater than or equal to 37.5")
                    - Fixed date range display for zero-offset dates ("Date is on the search date")
                    - Lazy export generation with instant downloads from cached data
                    - Consistent filter formatting across search and report exports
                    - Export buttons disabled until data fully loaded
                    
                    **🎯 UI Responsiveness:**
                    - Progressive loading with native Streamlit spinners
                    - Instant report dropdown switching using cached analysis
                    - Eliminated UI hangs and freezes during large operations
                    - Clean loading states with proper progress indicators
                    
                    ✅ **Resolves all critical performance bottlenecks and memory issues**
                    """)
                st.markdown("**[📄 View Full Technical Changelog](https://github.com/triplebob/emis-xml-convertor/blob/main/changelog.md)**")
            
            # Store in session state for later use
            st.session_state.lookup_df = lookup_df
            st.session_state.emis_guid_col = emis_guid_col
            st.session_state.snomed_code_col = snomed_code_col
            
            # Always store version_info to prevent session data from having empty version info
            # If version_info is empty or None, check if we already have stored version_info
            if version_info and len(version_info) > 0:
                st.session_state.lookup_version_info = version_info
            elif 'lookup_version_info' not in st.session_state:
                # Initialize with empty dict if no version info exists at all
                st.session_state.lookup_version_info = {}
            
            # Add NHS Terminology Server status
            if NHS_TERMINOLOGY_AVAILABLE:
                render_terminology_server_status()

            # Add memory monitoring section
            # Check if manual refresh was requested
            if st.session_state.get('force_memory_refresh', False):
                st.session_state.force_memory_refresh = False
            
            memory_info = get_memory_usage()
            
            if memory_info:
                current_mb = memory_info['current_mb']
                peak_mb = memory_info['peak_mb']
                
                # Memory usage guidance (show warnings outside expander)
                if current_mb > 2300:
                    st.error("⚠️ High memory usage! Consider refreshing the page to reset.")
                elif current_mb > 1800:
                    st.warning("💡 Approaching memory limits. Avoid multiple large exports.")
                
                # Add expandable memory info with current and peak inside
                with st.expander("💻 Memory Usage", expanded=False):
                    # Display current memory with appropriate color
                    status_color = get_memory_status_color(current_mb)
                    current_display = format_memory_display(current_mb)
                    peak_display = format_memory_display(peak_mb)
                    
                    if status_color == "success":
                        st.success(f"🟢 Current: {current_display}")
                    elif status_color == "info":
                        st.info(f"🔵 Current: {current_display}")
                    elif status_color == "warning":
                        st.warning(f"🟡 Current: {current_display}")
                    else:
                        st.error(f"🔴 Current: {current_display}")
                    
                    # Show peak memory
                    st.info(f"📈 Peak Use: {peak_display}")
                    
                    # Detailed system information
                    st.caption(f"System Total: {memory_info['system_total_gb']:.1f} GB")
                    st.caption(f"System Available: {memory_info['system_available_gb']:.1f} GB")
                    st.caption(f"System Usage: {memory_info['system_usage_percent']:.1f}%")
                    
                    # Add memory buttons
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🔄 Refresh Usage", help="Update current memory usage display", key="memory_refresh_btn"):
                            st.session_state.force_memory_refresh = True
                            st.rerun()
                    with col2:
                        if st.button("📊 Reset Peak", help="Reset the session peak memory counter"):
                            st.session_state.memory_peak_mb = current_mb
                            st.success("Peak memory counter reset!")
                            st.rerun()
            else:
                with st.expander("💻 Memory Usage", expanded=False):
                    st.error("❌ Memory monitoring unavailable")
            
            return lookup_df, emis_guid_col, snomed_code_col
                
        except Exception as e:
            st.error(f"❌ Error loading lookup table: {str(e)}")
            st.stop()