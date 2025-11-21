import streamlit as st
import re
import psutil
import os
from ..core.session_state import SessionStateKeys
from ..core.version import __version__
from ..ui.theme import ThemeColors, ComponentThemes, create_info_box_style, get_success_rate_color
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
        if SessionStateKeys.MEMORY_PEAK_MB not in st.session_state:
            st.session_state[SessionStateKeys.MEMORY_PEAK_MB] = current_memory_mb
        else:
            if current_memory_mb > st.session_state[SessionStateKeys.MEMORY_PEAK_MB]:
                st.session_state[SessionStateKeys.MEMORY_PEAK_MB] = current_memory_mb
        
        return {
            'current_mb': current_memory_mb,
            'virtual_mb': virtual_memory_mb,
            'peak_mb': st.session_state[SessionStateKeys.MEMORY_PEAK_MB],
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
        return ComponentThemes.RAG_SUCCESS
    elif memory_mb < 1800:  # 1-1.8GB
        return ComponentThemes.RAG_INFO
    elif memory_mb < 2300:  # 1.8-2.3GB
        return ComponentThemes.RAG_WARNING
    else:  # Over 2.3GB
        return ComponentThemes.RAG_ERROR

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
    # Apply custom styling for sidebar elements
    from .rendering_utils import apply_custom_styling
    apply_custom_styling()
    
    # Set default sidebar width
    st.markdown("""
    <style>
    .css-1d391kg {
        width: 350px !important;
        min-width: 350px !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.header("🗃️ Lookup Table Status")
        
        # Create status placeholder for dynamic updates
        status_placeholder = st.empty()
        
        try:
            # First try to use cached lookup data
            lookup_df = st.session_state.get(SessionStateKeys.LOOKUP_DF)
            emis_guid_col = st.session_state.get(SessionStateKeys.EMIS_GUID_COL)
            snomed_code_col = st.session_state.get(SessionStateKeys.SNOMED_CODE_COL)
            version_info = st.session_state.get(SessionStateKeys.LOOKUP_VERSION_INFO, {})
            
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
            st.markdown(create_info_box_style(ComponentThemes.LOOKUP_TABLE_STATUS, status_message), unsafe_allow_html=True)
            st.markdown(create_info_box_style(ComponentThemes.SCT_CODES_MEDICATIONS, f"⚕️ SCT Codes: {stats['clinical_count']:,}"), unsafe_allow_html=True)
            st.markdown(create_info_box_style(ComponentThemes.SCT_CODES_MEDICATIONS, f"💊 Medications: {stats['medication_count']:,}"), unsafe_allow_html=True)
            
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
            with st.sidebar.expander(f"🎯 What's New: v{__version__}", expanded=False):
                st.markdown(f"""
                    **🚀 Major Architecture & Feature Improvements:**
                    - Session state management has been fully centralised: handling memory and temporary data more reliably without hidden errors.
                    - Auto-cleanup has been added so that temp data can be reset cleanly, improving stability.
                    - The theme system has been centralised, ensuring that colours, spacing, and layouts are consistent across every part of the app.
                    - All interface components now follow the same styling rules, giving the app a cleaner, more polished appearance.
                    """)
                st.markdown("**[📄 View Full Technical Changelog](https://github.com/triplebob/emis-xml-convertor/blob/main/changelog.md)**")

            
            # Store in session state for later use
            st.session_state[SessionStateKeys.LOOKUP_DF] = lookup_df
            st.session_state[SessionStateKeys.EMIS_GUID_COL] = emis_guid_col
            st.session_state[SessionStateKeys.SNOMED_CODE_COL] = snomed_code_col
            
            # Always store version_info to prevent session data from having empty version info
            # If version_info is empty or None, check if we already have stored version_info
            if version_info and len(version_info) > 0:
                st.session_state[SessionStateKeys.LOOKUP_VERSION_INFO] = version_info
            elif SessionStateKeys.LOOKUP_VERSION_INFO not in st.session_state:
                # Initialize with empty dict if no version info exists at all
                st.session_state[SessionStateKeys.LOOKUP_VERSION_INFO] = {}
            
            # Add NHS Terminology Server status as fragment
            if NHS_TERMINOLOGY_AVAILABLE:
                @st.fragment
                def nhs_terminology_fragment():
                    render_terminology_server_status()
                
                nhs_terminology_fragment()

            # Add memory monitoring section as fragment
            @st.fragment
            def memory_monitoring_fragment():
                # Check if manual refresh was requested
                if st.session_state.get(SessionStateKeys.FORCE_MEMORY_REFRESH, False):
                    st.session_state[SessionStateKeys.FORCE_MEMORY_REFRESH] = False
                
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
                        
                        st.markdown(create_info_box_style(status_color, f"Current: {current_display}"), unsafe_allow_html=True)
                        
                        # Show peak memory
                        st.markdown(create_info_box_style(ComponentThemes.RAG_INFO, f"Peak: {peak_display}"), unsafe_allow_html=True)

                        st.markdown("")

                        # Detailed system information
                        st.caption(f"System Total: {memory_info['system_total_gb']:.1f} GB")
                        st.caption(f"System Available: {memory_info['system_available_gb']:.1f} GB")
                        st.caption(f"System Usage: {memory_info['system_usage_percent']:.1f}%")
                        
                        # Memory buttons (now inside the same fragment as the display)
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("🔄 Refresh Usage", help="Update current memory usage display", key="memory_refresh_btn"):
                                st.session_state[SessionStateKeys.FORCE_MEMORY_REFRESH] = True
                                # Fragment will auto-rerun, updating the memory display immediately
                        with col2:
                            if st.button("📊 Reset Peak", help="Reset the session peak memory counter", key="memory_reset_btn"):
                                # Get current memory to reset peak
                                current_memory_info = get_memory_usage()
                                if current_memory_info:
                                    st.session_state[SessionStateKeys.MEMORY_PEAK_MB] = current_memory_info['current_mb']
                                    st.toast("📊 Peak memory counter reset!", icon="✅")
                else:
                    with st.expander("💻 Memory Usage", expanded=False):
                        st.error("❌ Memory monitoring unavailable")
            
            memory_monitoring_fragment()
            
            # Add logo at bottom of sidebar
            st.markdown("""
            <style>
            @media (max-height: 800px) {
                .sidebar-logo {
                    display: none !important;
                }
            }
            </style>
            <div class="sidebar-logo" style="
                position: fixed;
                bottom: 20px;
                left: 30px;
                width: 200px;
                height: 60px;
                display: flex;
                justify-content: center;
                align-items: center;
                opacity: 0.8;
                z-index: 999;
                pointer-events: none;
            ">
                <svg width="200" height="50" viewBox="0 0 2606 1893" xmlns="http://www.w3.org/2000/svg">
                    <path d="m1404.2598,1580.16491c-71.944,-0.35 -143.887,-0.738 -215.83,-1.014c-12.622,-0.048 -24.337,-2.341 -34.737,-10.172c-12.683,-9.549 -20.557,-21.755 -21.298,-37.722c-0.552,-11.897 -0.058,-23.842 -0.056,-35.765q0.021,-150.48 0.03,-300.957c0.001,-13.665 0.149,-27.333 -0.086,-40.994c-0.374,-21.715 -13.932,-36.13 -35.66,-38.066c-4.634,-0.414 -9.32,-0.355 -13.982,-0.356c-116.316,-0.032 -232.632,-0.153 -348.947,0.066c-16.206,0.03 -29.105,-5.631 -39.52,-17.729c-6.304,-7.322 -9.884,-15.56 -9.825,-25.419c0.133,-22.33 0.115,-44.66 -0.023,-66.99c-0.377,-61.203 -0.905,-122.405 -1.193,-183.608c-0.029,-6.274 0.118,-12.888 1.999,-18.763c4.563,-14.252 23.92,-33.277 44.548,-33.033c68.315,0.809 136.644,0.436 204.968,0.293c19.224,-0.04 38.445,-1.129 57.67,-1.228c20.654,-0.107 41.31,0.504 61.966,0.574c14.971,0.05 29.946,-0.169 44.915,-0.454c14.683,-0.28 29.407,-13.316 31.725,-28.38c1.008,-6.55 1.391,-13.254 1.396,-19.888c0.088,-118.65 0.44,-237.302 -0.229,-355.948c-0.131,-23.313 15.955,-44.429 38.572,-50.765c2.806,-0.786 5.922,-0.634 8.895,-0.635c80.313,-0.039 160.632,0.537 240.935,-0.374c26.676,-0.303 56.77,22.188 55.878,56.374c-0.86,32.934 -1.266,65.888 -1.336,98.834c-0.183,85.654 -0.09,171.309 -0.029,256.963c0.004,4.962 0.328,9.984 1.135,14.873c2.448,14.84 12.426,25.289 27.122,28.242c5.511,1.108 11.214,1.765 16.83,1.774c74.323,0.12 148.646,0.175 222.969,0.058c42.282,-0.067 84.564,-0.371 126.844,-0.788c16.168,-0.16 30.09,4.765 41.453,16.416c6.484,6.65 10.835,14.345 10.993,23.877c0.25,14.989 0.54,29.98 0.517,44.97c-0.113,70.648 -0.342,141.296 -0.492,211.944c-0.04,18.458 -7.866,32.538 -23.137,42.828c-8.182,5.513 -17.21,6.796 -26.666,6.63c-8.988,-0.16 -17.972,-0.708 -26.959,-0.71c-102.985,-0.031 -205.97,-0.014 -308.956,0.069c-10.314,0.008 -20.635,0.389 -30.942,0.855c-15.933,0.72 -30.136,16.215 -30.625,33.731c-0.363,12.989 -0.124,25.995 -0.126,38.993c-0.003,16.997 0.024,33.995 0.03,50.993c0.006,12.909 -0.193,25.821 0.053,38.726c0.272,14.292 1.356,28.577 1.376,42.866c0.084,60.561 -0.16,121.123 -0.13,181.685c0.007,14.012 0.088,28.142 -4.847,41.344c-7.16,19.154 -21.468,30.627 -41.555,34.752c-1.296,0.266 -2.618,0.411 -5.625,0.782c-7.801,0.195 -13.905,0.22 -20.008,0.246" fill="#28546b"/>
                    <path d="m1635.47998,1866.3644c55.253,0.02 109.584,0.294 163.91,-0.153c15.232,-0.126 30.426,-2.862 45.676,-3.52c18.395,-0.794 36.31,-4.163 54.122,-8.341c63.066,-14.794 120.67,-41.307 172.662,-80.1c32.305,-24.102 60.322,-52.5 84.42,-84.576c28.537,-37.982 50.93,-79.532 68.668,-123.66c17.24,-42.891 27.039,-87.584 33.2,-133.15c2.845,-21.042 4.327,-42.27 6.294,-63.427c3.596,-38.66 6.328,-77.42 10.84,-115.973c4.866,-41.568 15.147,-81.74 38.036,-117.61c29.48,-46.2 70.255,-77.597 122.942,-93.254c19.179,-5.7 38.838,-8.606 58.721,-10.264c11.231,-0.937 22.458,-1.93 34.472,-2.964c0.473,-2.35 1.414,-4.864 1.42,-7.38a61724,61724 0 0 0 0.137,-156.928c-0.003,-10.676 -1.467,-11.691 -11.91,-12.673c-49.169,-4.621 -96.501,-16.144 -139.679,-40.816c-26.689,-15.25 -47.905,-36.76 -65.089,-62.374c-19.593,-29.206 -32.15,-61.19 -38.696,-95.541c-2.917,-15.308 -4.903,-30.828 -6.57,-46.331c-2.935,-27.298 -5.507,-54.64 -7.827,-81.997c-1.346,-15.881 -1.472,-31.87 -2.948,-47.735c-1.287,-13.826 -3.591,-27.563 -5.632,-41.311c-5.135,-34.587 -12.121,-68.78 -22.798,-102.121c-25.726,-80.334 -70.187,-148.247 -135.46,-201.972c-57.356,-47.209 -122.777,-77.86 -195.327,-93.713c-37.617,-8.221 -75.657,-10.994 -114.02,-10.961c-28.665,0.024 -57.332,0.12 -85.997,-0.044c-20.927,-0.12 -41.852,-0.627 -62.78,-0.936c-7.095,-0.104 -8.897,1.336 -9.002,8.673c-0.242,16.996 -0.157,33.996 -0.162,50.995c-0.013,42.331 -0.004,84.663 0.003,126.995c0,2.332 -0.006,4.669 0.111,6.998c0.457,9.04 1.478,10.142 10.843,10.165c31.999,0.079 64.007,-0.428 95.995,0.165c32.964,0.611 65.794,3.266 97.799,12.009c69.338,18.943 120.798,60.037 153.487,124.26c18.771,36.88 29.032,76.175 33.256,117.207c2.41,23.409 5.467,46.755 7.586,70.188c2.12,23.429 3.25,46.945 5.14,70.396c3.711,46.043 9.363,91.826 23.095,136.125c18.447,59.507 51.421,109.288 100.936,147.673c16.632,12.894 34.656,23.394 53.889,31.9c4.688,2.073 9.173,4.61 15.383,7.761c-4.253,2.01 -6.472,3.298 -8.847,4.146c-31.496,11.247 -59.007,28.84 -83.974,51.01c-40.746,36.18 -65.02,81.924 -79.425,133.619c-7.606,27.299 -12.056,55.126 -14.21,83.394c-1.936,25.413 -4.668,50.764 -6.912,76.154c-0.556,6.296 -0.344,12.66 -0.901,18.956c-1.285,14.507 -2.95,28.98 -4.227,43.489c-1.22,13.862 -1.672,27.806 -3.285,41.617c-5.312,45.504 -14.886,89.872 -36.923,130.665c-21.133,39.12 -51.395,69.156 -90.118,90.944c-42.14,23.71 -87.773,34.314 -135.604,36.254c-25.284,1.026 -50.623,0.685 -75.936,1.028c-16.964,0.23 -33.926,0.666 -50.89,0.81c-4.323,0.037 -6.014,2.117 -6.236,6.014c-0.113,1.995 -0.138,3.997 -0.138,5.996q0.003,90.497 0.023,180.995c0,1.999 0.109,3.999 0.092,5.998c-0.043,5.029 2.567,7.277 8.365,7.226" fill="#28546b"/>
                    <path transform="rotate(180 526.625 946.5)" d="m83.10679,1866.3644c55.253,0.02 109.584,0.294 163.91,-0.153c15.232,-0.126 30.426,-2.862 45.676,-3.52c18.395,-0.794 36.31,-4.163 54.122,-8.341c63.066,-14.794 120.67,-41.307 172.662,-80.1c32.305,-24.102 60.322,-52.5 84.42,-84.576c28.537,-37.982 50.93,-79.532 68.668,-123.66c17.24,-42.891 27.039,-87.584 33.2,-133.15c2.845,-21.042 4.327,-42.27 6.294,-63.427c3.596,-38.66 6.328,-77.42 10.84,-115.973c4.866,-41.568 15.147,-81.74 38.036,-117.61c29.48,-46.2 70.255,-77.597 122.942,-93.254c19.179,-5.7 38.838,-8.606 58.721,-10.264c11.231,-0.937 22.458,-1.93 34.472,-2.964c0.473,-2.35 1.414,-4.864 1.42,-7.38a61724,61724 0 0 0 0.137,-156.928c-0.003,-10.676 -1.467,-11.691 -11.91,-12.673c-49.169,-4.621 -96.501,-16.144 -139.679,-40.816c-26.689,-15.25 -47.905,-36.76 -65.089,-62.374c-19.593,-29.206 -32.15,-61.19 -38.696,-95.541c-2.917,-15.308 -4.903,-30.828 -6.57,-46.331c-2.935,-27.298 -5.507,-54.64 -7.827,-81.997c-1.346,-15.881 -1.472,-31.87 -2.948,-47.735c-1.287,-13.826 -3.591,-27.563 -5.632,-41.311c-5.135,-34.587 -12.121,-68.78 -22.798,-102.121c-25.726,-80.334 -70.187,-148.247 -135.46,-201.972c-57.356,-47.209 -122.777,-77.86 -195.327,-93.713c-37.617,-8.221 -75.657,-10.994 -114.02,-10.961c-28.665,0.024 -57.332,0.12 -85.997,-0.044c-20.927,-0.12 -41.852,-0.627 -62.78,-0.936c-7.095,-0.104 -8.897,1.336 -9.002,8.673c-0.242,16.996 -0.157,33.996 -0.162,50.995c-0.013,42.331 -0.004,84.663 0.003,126.995c0,2.332 -0.006,4.669 0.111,6.998c0.457,9.04 1.478,10.142 10.843,10.165c31.999,0.079 64.007,-0.428 95.995,0.165c32.964,0.611 65.794,3.266 97.799,12.009c69.338,18.943 120.798,60.037 153.487,124.26c18.771,36.88 29.032,76.175 33.256,117.207c2.41,23.409 5.467,46.755 7.586,70.188c2.12,23.429 3.25,46.945 5.14,70.396c3.711,46.043 9.363,91.826 23.095,136.125c18.447,59.507 51.421,109.288 100.936,147.673c16.632,12.894 34.656,23.394 53.889,31.9c4.688,2.073 9.173,4.61 15.383,7.761c-4.253,2.01 -6.472,3.298 -8.847,4.146c-31.496,11.247 -59.007,28.84 -83.974,51.01c-40.746,36.18 -65.02,81.924 -79.425,133.619c-7.606,27.299 -12.056,55.126 -14.21,83.394c-1.936,25.413 -4.668,50.764 -6.912,76.154c-0.556,6.296 -0.344,12.66 -0.901,18.956c-1.285,14.507 -2.95,28.98 -4.227,43.489c-1.22,13.862 -1.672,27.806 -3.285,41.617c-5.312,45.504 -14.886,89.872 -36.923,130.665c-21.133,39.12 -51.395,69.156 -90.118,90.944c-42.14,23.71 -87.773,34.314 -135.604,36.254c-25.284,1.026 -50.623,0.685 -75.936,1.028c-16.964,0.23 -33.926,0.666 -50.89,0.81c-4.323,0.037 -6.014,2.117 -6.236,6.014c-0.113,1.995 -0.138,3.997 -0.138,5.996q0.003,90.497 0.023,180.995c0,1.999 0.109,3.999 0.092,5.998c-0.043,5.029 2.567,7.277 8.365,7.226" fill="#28546b"/>
                </svg>
            </div>
            """, unsafe_allow_html=True)
            
            return lookup_df, emis_guid_col, snomed_code_col
                
        except Exception as e:
            st.error(f"❌ Error loading lookup table: {str(e)}")
            st.stop()
