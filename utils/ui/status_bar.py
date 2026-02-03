import streamlit as st
import re
import psutil
import os
import platform
from typing import Dict, Any
from ..system.session_state import SessionStateKeys

# Platform-specific imports for true peak memory tracking
_IS_LINUX = platform.system() == "Linux"
_IS_WINDOWS = platform.system() == "Windows"

if _IS_LINUX:
    try:
        import resource
        _HAS_RESOURCE = True
    except ImportError:
        _HAS_RESOURCE = False
else:
    _HAS_RESOURCE = False
from ..system.version import __version__
from ..ui.theme import ThemeColours, ComponentThemes, create_info_box_style, get_success_rate_colour
from ..caching.lookup_manager import load_lookup_table, get_lookup_statistics, is_lookup_loaded
from .theme import info_box, success_box, warning_box, error_box

# NHS Terminology Server integration
from ..terminology_server import test_connection

NHS_TERMINOLOGY_AVAILABLE = True


def render_terminology_server_status():
    """Render NHS Terminology Server connection status in sidebar."""
    with st.expander("🏥 NHS Term Server", expanded=False):
        if 'nhs_connection_status' not in st.session_state:
            st.session_state.nhs_connection_status = None

        if st.button("Test connection", key="test_nhs_connection"):
            try:
                client_id = st.secrets["NHSTSERVER_ID"]
                client_secret = st.secrets["NHSTSERVER_TOKEN"]
            except KeyError:
                st.session_state.nhs_connection_status = {
                    "success": False,
                    "message": "Credentials not configured. Add NHSTSERVER_ID and NHSTSERVER_TOKEN to secrets.",
                    "tested": True,
                }
            else:
                success, message = test_connection(client_id, client_secret)
                st.session_state.nhs_connection_status = {
                    "success": success,
                    "message": message,
                    "tested": True,
                }

        status = st.session_state.nhs_connection_status or {}
        if status.get("tested"):
            if status.get("success"):
                st.markdown(
                    success_box("<div style=\"text-align: center;\">🔑 Authenticated</div>"),
                    unsafe_allow_html=True
                )
            else:
                st.error(status.get("message", "Connection failed"))


def render_performance_controls():
    """Render display options for processing feedback."""
    with st.sidebar.expander("⚡ Display Options", expanded=False):
        show_progress = st.checkbox(
            "Show Processing Progress",
            value=True,
            help="Display progress bar during XML processing"
        )

        show_metrics = st.checkbox(
            "Show Performance Metrics",
            value=False,
            help="Display processing time and memory statistics after completion"
        )

        return {
            "show_metrics": show_metrics,
            "show_progress": show_progress,
        }


def display_performance_metrics(metrics: Dict[str, Any]):
    """Display performance metrics in Streamlit."""
    st.markdown("##### ⚡ Performance Metrics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"**Peak Memory**  \n{metrics.get('memory_peak_mb', 0):.1f} MB")

    with col2:
        st.markdown(f"**Processing Time**  \n{metrics.get('total_time', 0):.2f}s")

    with col3:
        st.markdown(f"**Items Processed**  \n{metrics.get('items_processed', 0)}")

    with col4:
        success_rate = metrics.get('success_rate', 0)
        st.markdown(f"**Match Rate**  \n{success_rate:.1f}%")

def _get_true_peak_memory_mb() -> float:
    """
    Get true peak memory usage from OS/kernel.

    Linux (Streamlit Cloud): Uses resource.getrusage() - kernel-tracked true peak
    Windows (local dev): Uses psutil peak_wset - OS-tracked peak working set

    Returns peak in MB, or 0.0 if unavailable.
    """
    try:
        if _IS_LINUX and _HAS_RESOURCE:
            # Linux: ru_maxrss is in KB
            peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return peak_kb / 1024.0
        elif _IS_WINDOWS:
            # Windows: peak_wset is in bytes (peak working set size)
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            # peak_wset available on Windows
            if hasattr(memory_info, 'peak_wset'):
                return memory_info.peak_wset / (1024 * 1024)
        return 0.0
    except Exception:
        return 0.0


def get_memory_usage():
    """Get current memory usage information with true peak tracking."""
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

        # Get true peak from OS/kernel (preferred) or fall back to session tracking
        true_peak_mb = _get_true_peak_memory_mb()

        if true_peak_mb > 0:
            # Use OS-tracked true peak
            peak_mb = true_peak_mb
            # Also update session state for consistency
            st.session_state[SessionStateKeys.MEMORY_PEAK_MB] = peak_mb
        else:
            # Fallback: session-based tracking (sampled, less accurate)
            if SessionStateKeys.MEMORY_PEAK_MB not in st.session_state:
                st.session_state[SessionStateKeys.MEMORY_PEAK_MB] = current_memory_mb
            elif current_memory_mb > st.session_state[SessionStateKeys.MEMORY_PEAK_MB]:
                st.session_state[SessionStateKeys.MEMORY_PEAK_MB] = current_memory_mb
            peak_mb = st.session_state[SessionStateKeys.MEMORY_PEAK_MB]

        return {
            'current_mb': current_memory_mb,
            'virtual_mb': virtual_memory_mb,
            'peak_mb': peak_mb,
            'peak_source': 'kernel' if true_peak_mb > 0 else 'sampled',
            'system_total_gb': system_total_gb,
            'system_available_gb': system_available_gb,
            'system_usage_percent': system_usage_percent
        }
    except Exception:
        return None

def get_memory_status_colour(memory_mb):
    """Determine status colour based on memory usage"""
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
        "local_cache": "🔐",
        "encrypted_cache": "🔐",
        "github": "📥",
        "generated": "📥",
    }
    source_messages = {
        "session": "session data",
        "cache": "encrypted cache",
        "local_cache": "encrypted cache",
        "encrypted_cache": "encrypted cache",
        "github": "Github",
        "generated": "Github",
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
    from .theme import apply_custom_styling
    apply_custom_styling()
    
    st.markdown("""
        <style>
            section[data-testid="stSidebar"] {
                width: 255px !important;
                min-width: 255px !important;
            }
            /* Ensure main content shrinks accordingly */
            section[data-testid="stSidebar"] > div:first-child {
                width: 255px !important;
            }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    with st.sidebar:
        st.header("🗃️ Lookup Table Status")
        
        # Create a status container for dynamic updates
        status_placeholder = st.empty()
        
        try:
            # Check if lookup is already loaded
            if not is_lookup_loaded():
                # Load encrypted parquet from GitHub or local cache
                encrypted_bytes, emis_guid_col, snomed_code_col, version_info = load_lookup_table()
            else:
                emis_guid_col = st.session_state.get(SessionStateKeys.EMIS_GUID_COL)
                snomed_code_col = st.session_state.get(SessionStateKeys.SNOMED_CODE_COL)
                version_info = st.session_state.get(SessionStateKeys.LOOKUP_VERSION_INFO, {})

            load_source = version_info.get('load_source', 'cache') if version_info else 'cache'

            # Clear status container
            status_placeholder.empty()

            # Get lookup statistics from version_info (pre-computed)
            stats = get_lookup_statistics()
            
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
                from .theme import info_box
                st.markdown(info_box(f"📊 Other types: {stats['other_count']:,}"), unsafe_allow_html=True)
            
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
                        **Complete Architecture Rebuild & Encrypted Lookup System:**
                        - Compatibility codebase replaced with a modern `utils/` architecture featuring clean module boundaries, single‑responsibility design, and consistent imports.
                        - Plugin-based parsing pipeline with module auto-loading, structured pattern handlers, and central flag registry for extensible XML processing.
                        - Encrypted parquet lookup system with filtered lookup APIs, Fernet encryption, and automatic cache generation from the private lookup repo.
                        - CodeStore introduces key-based deduplication and full source tracking across searches and reports.
                        - NHS Terminology Server refactor adds lazy hierarchy expansion, standalone SNOMED lookup, improved credential handling, and adaptive rate limiting.
                        - XML Explorer reimagined with hierarchical navigation, dependency visualisation, raw XML viewer, and performance‑optimised lazy loading.
                        - Export system rebuilt with lazy generation, context‑sensitive filenames, automatic cache invalidation, and unified naming conventions.
                        - System-wide performance upgrades include TTL/max-entry cache controls, explicit cache cleanup, GC optimisation, and real-time memory monitoring.
    """)
                st.markdown("**[📄 View Full Technical Changelog](https://github.com/triplebob/emis-xml-convertor/blob/main/changelog.md)**")



            
            # Session state is already updated by load_lookup_table()
            # Just ensure version_info is stored
            if version_info and len(version_info) > 0:
                st.session_state[SessionStateKeys.LOOKUP_VERSION_INFO] = version_info
            elif SessionStateKeys.LOOKUP_VERSION_INFO not in st.session_state:
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
                    peak_source = memory_info.get('peak_source', 'sampled')

                    # Memory usage guidance (show warnings outside expander)
                    if current_mb > 2300:
                        from .theme import error_box
                        st.markdown(error_box("⚠️ High memory usage! Consider refreshing the page to reset."), unsafe_allow_html=True)
                    elif current_mb > 1800:
                        from .theme import warning_box
                        st.markdown(warning_box("💡 Approaching memory limits. Avoid multiple large exports."), unsafe_allow_html=True)

                    # Add expandable memory info with current and peak inside
                    with st.expander("💻 Memory Usage", expanded=False):
                        # Display current memory with appropriate colour
                        status_colour = get_memory_status_colour(current_mb)
                        current_display = format_memory_display(current_mb)
                        peak_display = format_memory_display(peak_mb)

                        st.markdown(create_info_box_style(status_colour, f"Current: {current_display}"), unsafe_allow_html=True)

                        # Show peak memory with source indicator
                        peak_label = "Peak" if peak_source == 'kernel' else "Peak~"
                        st.markdown(create_info_box_style(ComponentThemes.RAG_INFO, f"{peak_label}: {peak_display}"), unsafe_allow_html=True)
                        if peak_source == 'sampled':
                            st.caption("~ Estimated (sampled)")

                        st.markdown("")

                        # Detailed system information
                        st.caption(f"System Total: {memory_info['system_total_gb']:.1f} GB")
                        st.caption(f"System Available: {memory_info['system_available_gb']:.1f} GB")
                        st.caption(f"System Usage: {memory_info['system_usage_percent']:.1f}%")

                        # Memory buttons (now inside the same fragment as the display)
                        columns = st.columns(2) if peak_source == 'sampled' else st.columns(1)
                        with columns[0]:
                            if st.button("🔄 Refresh Usage", help="Update current memory usage display", key="memory_refresh_btn"):
                                st.session_state[SessionStateKeys.FORCE_MEMORY_REFRESH] = True
                                # Fragment will auto-rerun, updating the memory display immediately
                        if peak_source == 'sampled':
                            with columns[1]:
                                # Reset Peak only useful for sampled mode (kernel peak resets on process restart)
                                if st.button("📊 Reset Peak", help="Reset session peak counter", key="memory_reset_btn"):
                                    current_memory_info = get_memory_usage()
                                    if current_memory_info:
                                        st.session_state[SessionStateKeys.MEMORY_PEAK_MB] = current_memory_info['current_mb']
                                        st.toast("📊 Peak memory counter reset!", icon="✅")
                else:
                    with st.expander("💻 Memory Usage", expanded=False):
                        from .theme import error_box
                        st.markdown(error_box("❌ Memory monitoring unavailable"), unsafe_allow_html=True)
            
            memory_monitoring_fragment()

            return emis_guid_col, snomed_code_col, version_info
                
        except Exception as e:
            # Use structured UI error handling for lookup table errors
            st.markdown(error_box(f"❌ Error loading lookup table: {str(e)}"), unsafe_allow_html=True)
            st.stop()
