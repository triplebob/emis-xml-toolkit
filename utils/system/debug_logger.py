"""
Debug Logging Utility
Provides optional debug logging for audit trails and troubleshooting.
"""

import logging
import streamlit as st
from datetime import datetime
from typing import Dict, Any, List, Optional
import json
import unittest
import sys
import io
from contextlib import redirect_stdout, redirect_stderr
from ..system.session_state import SessionStateKeys
from .version import __version__
# Note: theme imports removed to prevent circular imports


class EMISDebugLogger:
    """
    Debug logger for EMIS XML to SNOMED translation process.
    Provides structured logging for audit trails and troubleshooting.
    """
    
    def __init__(self, enable_debug: bool = False):
        """
        Initialise the debug logger.
        
        Args:
            enable_debug: Whether to enable debug logging
        """
        self.enable_debug = enable_debug
        self.logger = logging.getLogger('emis_translator')
        
        if self.enable_debug:
            # Configure logger
            self.logger.setLevel(logging.DEBUG)
            self.logger.propagate = False
            
            # Create formatter
            formatter = logging.Formatter(
                '[%(levelname)s][%(name)s] %(message)s'
            )
            
            # Keep a single managed handler so formatting stays consistent.
            self.logger.handlers.clear()

            # Create console handler
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.DEBUG)
            console_handler.setFormatter(formatter)
            console_handler._clinxml_debug_handler = True  # type: ignore[attr-defined]
            
            self.logger.addHandler(console_handler)
    
    def log_xml_processing_start(self, filename: str, file_size: int) -> None:
        """Log the start of XML processing."""
        if not self.enable_debug:
            return
            
        self.logger.info(f"Starting XML processing for file: {filename} (size: {file_size} bytes)")
    
    def log_xml_parsing_result(self, emis_guids: List[Dict]) -> None:
        """Log XML parsing results."""
        if not self.enable_debug:
            return
            
        def _get_guid(entry: Dict[str, Any]) -> Optional[str]:
            return entry.get('emis_guid') or entry.get('EMIS GUID')

        def _get_valueset(entry: Dict[str, Any]) -> Optional[str]:
            return entry.get('valueSet_guid') or entry.get('ValueSet GUID')

        unique_guids = set(g for g in (_get_guid(guid) for guid in emis_guids) if g)
        unique_valuesets = set(v for v in (_get_valueset(guid) for guid in emis_guids) if v)
        
        self.logger.info(f"XML parsing completed: {len(emis_guids)} total entries, "
                        f"{len(unique_guids)} unique GUIDs, {len(unique_valuesets)} unique valueSets")
        
        # Log code system distribution
        code_systems = {}
        for guid in emis_guids:
            system = guid.get('code_system') or guid.get('Code System') or 'UNKNOWN'
            code_systems[system] = code_systems.get(system, 0) + 1
        
        self.logger.debug(f"Code system distribution: {json.dumps(code_systems, indent=2)}")
    
    def log_pseudo_refset_detection(self, pseudo_refsets: List[str]) -> None:
        """Log pseudo-refset detection results."""
        if not self.enable_debug:
            return
            
        self.logger.info(f"Pseudo-refset detection: {len(pseudo_refsets)} pseudo-refsets found")
        for refset_id in pseudo_refsets:
            self.logger.debug(f"Detected pseudo-refset: {refset_id}")
    
    def log_classification_results(self, results: Dict[str, List]) -> None:
        """Log classification results summary."""
        if not self.enable_debug:
            return
            
        clinical_count = len(results.get('clinical', []))
        medication_count = len(results.get('medications', []))
        refset_count = len(results.get('refsets', []))
        pseudo_refset_count = len(results.get('pseudo_refsets', []))
        
        self.logger.info(f"Classification results: {clinical_count} clinical, "
                        f"{medication_count} medications, {refset_count} refsets, "
                        f"{pseudo_refset_count} pseudo-refsets")
    
    def log_lookup_performance(self, lookup_stats: Dict[str, Any]) -> None:
        """Log lookup table performance metrics."""
        if not self.enable_debug:
            return
            
        self.logger.info(f"Lookup performance: {lookup_stats.get('total_lookups', 0)} lookups, "
                        f"{lookup_stats.get('successful_lookups', 0)} successful, "
                        f"{lookup_stats.get('lookup_time_ms', 0):.2f}ms average")
    
    def log_error(self, error: Exception, context: str = "") -> None:
        """Log errors with context."""
        if not self.enable_debug:
            return
            
        context_msg = f" in {context}" if context else ""
        self.logger.error(f"Error{context_msg}: {str(error)}", exc_info=True)
    
    def log_user_action(self, action: str, details: Optional[Dict] = None) -> None:
        """Log user actions for audit trail."""
        if not self.enable_debug:
            return
            
        details_str = f" - Details: {json.dumps(details)}" if details else ""
        self.logger.info(f"User action: {action}{details_str}")
    
    def log_processing_complete(self, total_time: float, success_rate: float) -> None:
        """Log processing completion summary."""
        if not self.enable_debug:
            return
            
        self.logger.info(f"Processing completed in {total_time:.2f}s with "
                        f"{success_rate:.1f}% success rate")


def get_debug_logger() -> EMISDebugLogger:
    """
    Get a debug logger instance based on Streamlit settings.
    
    Returns:
        EMISDebugLogger instance
    """
    # Check if debug mode is enabled via Streamlit session state or environment
    enable_debug = st.session_state.get(SessionStateKeys.DEBUG_MODE, False)
    
    return EMISDebugLogger(enable_debug)


def run_test_suite(test_module: str) -> tuple[bool, str]:
    """
    Run a specific test module and return results.
    
    Args:
        test_module: Name of the test module (e.g., 'test_performance')
        
    Returns:
        Tuple of (success: bool, output: str)
    """
    try:
        import sys
        import os
        
        # Add the project root to Python path if not already there
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        # Import the test module
        if test_module == 'test_performance':
            import tests.test_performance as test_perf
            suite = unittest.TestLoader().loadTestsFromModule(test_perf)
        else:
            return False, f"Unknown test module: {test_module}"
        
        # Capture output
        output_buffer = io.StringIO()
        error_buffer = io.StringIO()
        
        with redirect_stdout(output_buffer), redirect_stderr(error_buffer):
            runner = unittest.TextTestRunner(
                stream=output_buffer,
                verbosity=2,
                buffer=True
            )
            result = runner.run(suite)
        
        # Combine stdout and stderr
        output = output_buffer.getvalue()
        errors = error_buffer.getvalue()
        if errors:
            output += "\n" + errors
        
        # Add detailed failure information
        if not result.wasSuccessful():
            output += f"\n\n=== TEST SUMMARY ===\n"
            output += f"Tests run: {result.testsRun}\n"
            output += f"Failures: {len(result.failures)}\n"
            output += f"Errors: {len(result.errors)}\n"
            
            if result.failures:
                output += "\n=== FAILURES ===\n"
                for test, traceback in result.failures:
                    output += f"\nFAILED: {test}\n{traceback}\n"
            
            if result.errors:
                output += "\n=== ERRORS ===\n"
                for test, traceback in result.errors:
                    output += f"\nERROR: {test}\n{traceback}\n"
            
        success = result.wasSuccessful()
        return success, output
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return False, f"Error running tests: {str(e)}\n\nFull traceback:\n{error_details}"


def render_debug_controls() -> None:
    """
    Render debug controls in Streamlit sidebar as a collapsible section.
    Only shows in local development environment.
    """
    import os
    
    # Detect if running in Streamlit Cloud environment
    is_cloud = (os.getenv('STREAMLIT_SHARING_MODE') or 
                os.getenv('HOSTNAME', '').startswith('streamlit') or
                'streamlit.app' in os.getenv('STREAMLIT_SERVER_HEADLESS', '') or
                os.path.exists('/.streamlit'))
    
    # Only show debug options in local environment
    if not is_cloud:
        with st.sidebar.expander("🐛 Debug Options", expanded=False):
            # Debug mode toggle
            debug_mode = st.checkbox(
                "Enable Debug Logging",
                value=st.session_state.get(SessionStateKeys.DEBUG_MODE, False),
                help="Enable detailed logging for troubleshooting and audit trails"
            )
            
            st.session_state[SessionStateKeys.DEBUG_MODE] = debug_mode
            
            if debug_mode:
                from ..ui.theme import info_box
                st.markdown(info_box("Debug logging is enabled. Check console output for detailed logs."), unsafe_allow_html=True)
                
                # Option to download debug logs
                if st.button("📁 Export Debug Session"):
                    debug_info = {
                        'session_id': st.session_state.get(SessionStateKeys.SESSION_ID, 'unknown'),
                        'timestamp': datetime.now().isoformat(),
                        'debug_enabled': True,
                        'processed_files': st.session_state.get(SessionStateKeys.PROCESSED_FILES, []),
                        'lookup_table_info': {
                            'loaded': st.session_state.get(SessionStateKeys.LOOKUP_ENCRYPTED_BYTES) is not None,
                            'encrypted_size': len(st.session_state.get(SessionStateKeys.LOOKUP_ENCRYPTED_BYTES, b'')),
                            'version_info': st.session_state.get(SessionStateKeys.LOOKUP_VERSION_INFO, {})
                        }
                    }
                    
                    debug_json = json.dumps(debug_info, indent=2, default=str)
                    
                    from utils.exports.ui_export_manager import UIExportManager
                    export_manager = UIExportManager()
                    export_manager.render_json_download_button(
                        content=debug_json,
                        filename=f"emis_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        label="💾 Download Debug Info",
                        key="download_debug_info"
                    )
            
            # Session Cache Management
            st.markdown("---")
            st.markdown("**🗑️ Session Cache Management**")
            
            if st.button("🚮 Force Purge Session Cache", help="Clear all session state and cached metadata (keeps .cache folder)", type="secondary"):
                # Import session state clearing functions
                from ..system.session_state import clear_all_except_core
                
                try:
                    # Clear Streamlit caches
                    st.cache_data.clear()
                    
                    # Clear all session state except core system state
                    clear_all_except_core()
                    
                    # Reset debug mode to maintain current setting
                    st.session_state[SessionStateKeys.DEBUG_MODE] = debug_mode
                    
                    st.success("✅ Session cache purged! All metadata cleared except .cache folder.")
                    st.info("🔄 Page will refresh to apply changes...")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error purging cache: {str(e)}")
            
            # Version Update Section
            st.markdown("---")
            st.markdown("**📝 Version Updates**")
            
            # Update versions button as fragment
            @st.fragment
            def version_update_fragment():
                if st.button("📝 Update README & Changelog", key="update_versions_btn"):
                    try:
                        # Import the update_versions module
                        from .update_versions import update_all_version_files
                        
                        with st.spinner("Updating README.md and changelog.md with current version..."):
                            updated_files, formatted_date = update_all_version_files()
                            
                            if updated_files:
                                st.toast(f"✅ Updated {len(updated_files)} files to version {__version__}!", icon="🎉")
                                success_message = f"**✅ Successfully updated {len(updated_files)} files:**\n"
                                for file in updated_files:
                                    success_message += f"- {file}\n"
                                if formatted_date:
                                    success_message += f"\n**Last updated:** {formatted_date}"
                                from ..ui.theme import success_box
                                st.markdown(success_box(success_message), unsafe_allow_html=True)
                            else:
                                from ..ui.theme import warning_box
                                st.markdown(warning_box("⚠️ No files were updated"), unsafe_allow_html=True)
                    
                    except Exception as e:
                        from ..ui.theme import error_box
                        st.markdown(error_box(f"❌ Version update failed: {str(e)}"), unsafe_allow_html=True)
                        import traceback
                        with st.expander("🔍 Error Details", expanded=True):
                            st.code(traceback.format_exc())
            
            version_update_fragment()
            
            st.caption("💡 Updates README.md and changelog.md with current version and date from version.py")
            
            # Cache Generation Section
            st.markdown("---")
            st.markdown("**⚡ Cache Generation**")

            # Generate GitHub cache button as fragment
            @st.fragment
            def cache_generation_fragment():
                if st.button("🔨 Regenerate Encrypted Lookup", key="generate_cache_btn"):
                    try:
                        from ..caching.lookup_manager import force_regenerate_lookup

                        with st.spinner("Generating encrypted lookup table from Github..."):
                            success = force_regenerate_lookup()

                            if success:
                                st.toast("Encrypted lookup generated successfully!", icon="✅")
                                from ..ui.theme import success_box
                                st.markdown(success_box("Encrypted lookup saved to .cache/ directory"), unsafe_allow_html=True)
                            else:
                                from ..ui.theme import error_box
                                st.markdown(error_box("Failed to generate encrypted lookup"), unsafe_allow_html=True)

                    except Exception as e:
                        from ..ui.theme import error_box
                        st.markdown(error_box(f"Cache generation failed: {str(e)}"), unsafe_allow_html=True)

            cache_generation_fragment()

            # Session State Debug
            if debug_mode:
                render_session_state_debug()


def render_session_state_debug() -> None:
    """Render session state diagnostics in a dedicated expander."""
    if not st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        return

    from ..ui.theme import error_box, success_box

    validation = _validate_session_state()
    summary = _get_session_state_summary()
    debug_info = _get_state_debug_info()

    with st.expander("🔧 Session State Debug", expanded=False):
        st.markdown("**Session State Validation**")
        if validation.get("issues"):
            st.markdown(error_box("Issues found:"), unsafe_allow_html=True)
            for issue in validation["issues"]:
                st.write(f"- {issue}")
        else:
            st.markdown(success_box("No validation issues found"), unsafe_allow_html=True)

        st.markdown("**State Summary**")
        st.json(summary)

        st.markdown("**Debug Information**")
        st.json(debug_info)


def _session_state_groups() -> dict[str, list[str]]:
    return {
        "core_data": [
            SessionStateKeys.XML_FILENAME,
            SessionStateKeys.XML_FILESIZE,
            SessionStateKeys.UPLOADED_FILENAME,
            SessionStateKeys.UPLOADED_FILE,
        ],
        "processing_state": [
            SessionStateKeys.IS_PROCESSING,
            SessionStateKeys.PROCESSING_CONTEXT,
            "progress_placeholder",
            "processing_placeholder",
        ],
        "results_data": [
            SessionStateKeys.EMIS_GUIDS,
            SessionStateKeys.AUDIT_STATS,
            SessionStateKeys.PIPELINE_CODES,
            SessionStateKeys.PIPELINE_ENTITIES,
            SessionStateKeys.PIPELINE_FOLDERS,
            SessionStateKeys.XML_STRUCTURE_DATA,
            SessionStateKeys.CODE_STORE,
            "unified_clinical_data_cache",
            "expansion_results_data",
        ],
        "lookup_data": [
            SessionStateKeys.LOOKUP_ENCRYPTED_BYTES,
            SessionStateKeys.EMIS_GUID_COL,
            SessionStateKeys.SNOMED_CODE_COL,
            SessionStateKeys.LOOKUP_VERSION_INFO,
            SessionStateKeys.MATCHED_EMIS_SNOMED_CACHE,
            SessionStateKeys.MATCHED_EMIS_SNOMED_TIMESTAMP,
        ],
        "user_preferences": [
            SessionStateKeys.CURRENT_DEDUPLICATION_MODE,
            SessionStateKeys.CHILD_VIEW_MODE,
            SessionStateKeys.DEBUG_MODE,
            SessionStateKeys.FORCE_MEMORY_REFRESH,
            SessionStateKeys.CLINICAL_INCLUDE_REPORT_CODES,
            SessionStateKeys.CLINICAL_SHOW_CODE_SOURCES,
        ],
        "nhs_terminology": [
            SessionStateKeys.NHS_CONNECTION_STATUS,
            SessionStateKeys.EXPANSION_IN_PROGRESS,
            SessionStateKeys.EXPANSION_STATUS,
        ],
        "system_monitoring": [
            SessionStateKeys.MEMORY_PEAK_MB,
            SessionStateKeys.PENDING_ERRORS,
        ],
    }


def _validate_session_state() -> Dict[str, Any]:
    issues = []
    recommendations = []
    stats = {
        "total_keys": len(st.session_state),
        "core_data_present": 0,
        "cache_keys": 0,
        "export_keys": 0,
        "orphaned_keys": [],
    }

    core_data = _session_state_groups()["core_data"]

    for key in core_data:
        if key in st.session_state:
            stats["core_data_present"] += 1

    dynamic_prefixes = [
        SessionStateKeys.CACHE_KEY_PREFIX,
        SessionStateKeys.EXCEL_CACHE_PREFIX,
        SessionStateKeys.JSON_CACHE_PREFIX,
        SessionStateKeys.TREE_TEXT_PREFIX,
        SessionStateKeys.DEP_TREE_TEXT_PREFIX,
        SessionStateKeys.NHS_TERMINOLOGY_CACHE_PREFIX,
        SessionStateKeys.CACHED_SELECTED_REPORT_PREFIX,
    ]

    known_keys = set()
    for keys in _session_state_groups().values():
        known_keys.update(keys)

    for key in st.session_state.keys():
        if key.startswith(SessionStateKeys.CACHE_KEY_PREFIX):
            stats["cache_keys"] += 1
        elif key.startswith((SessionStateKeys.EXCEL_CACHE_PREFIX, SessionStateKeys.JSON_CACHE_PREFIX)):
            stats["export_keys"] += 1
        elif key not in known_keys and not any(key.startswith(prefix) for prefix in dynamic_prefixes):
            stats["orphaned_keys"].append(key)

    if SessionStateKeys.UPLOADED_FILE in st.session_state and SessionStateKeys.XML_FILENAME not in st.session_state:
        issues.append("Uploaded file present but filename missing")
        recommendations.append("Ensure XML filename is set when file is loaded")

    if stats["cache_keys"] > 50:
        issues.append(f"High cache count: {stats['cache_keys']} keys")
        recommendations.append("Consider clearing cache with clear_all_except_core()")

    if stats["orphaned_keys"]:
        issues.append(f"Found {len(stats['orphaned_keys'])} orphaned keys")
        recommendations.append("Review orphaned keys for cleanup opportunities")

    return {
        "stats": stats,
        "issues": issues,
        "recommendations": recommendations,
        "healthy": len(issues) == 0,
    }


def _get_session_state_summary() -> Dict[str, Any]:
    summary = {"total_keys": len(st.session_state), "groups": {}}

    for group_name, keys in _session_state_groups().items():
        present = [key for key in keys if key in st.session_state]
        summary["groups"][group_name] = {
            "present": len(present),
            "total": len(keys),
            "keys": present,
        }

    dynamic_counts = {}
    for key in st.session_state.keys():
        if key.startswith(SessionStateKeys.CACHE_KEY_PREFIX):
            dynamic_counts["cache"] = dynamic_counts.get("cache", 0) + 1
        elif key.startswith(SessionStateKeys.EXCEL_CACHE_PREFIX):
            dynamic_counts["excel_export"] = dynamic_counts.get("excel_export", 0) + 1
        elif key.startswith(SessionStateKeys.JSON_CACHE_PREFIX):
            dynamic_counts["json_export"] = dynamic_counts.get("json_export", 0) + 1
        elif key.startswith(SessionStateKeys.TREE_TEXT_PREFIX):
            dynamic_counts["tree_viz"] = dynamic_counts.get("tree_viz", 0) + 1

    summary["dynamic_keys"] = dynamic_counts
    return summary


def _get_state_debug_info() -> dict:
    debug_info = {
        "total_keys": len(st.session_state.keys()),
        "dynamic_keys": {},
        "unknown_keys": [],
    }

    groups = _session_state_groups()
    known_keys = set()
    for keys in groups.values():
        known_keys.update(keys)
    debug_info.update({name: [key for key in keys if key in st.session_state] for name, keys in groups.items()})

    dynamic_counts = {}
    for key in st.session_state.keys():
        if key.startswith(SessionStateKeys.CACHE_KEY_PREFIX):
            dynamic_counts["cache"] = dynamic_counts.get("cache", 0) + 1
        elif key.startswith(SessionStateKeys.EXCEL_CACHE_PREFIX):
            dynamic_counts["excel_export"] = dynamic_counts.get("excel_export", 0) + 1
        elif key.startswith(SessionStateKeys.JSON_CACHE_PREFIX):
            dynamic_counts["json_export"] = dynamic_counts.get("json_export", 0) + 1
        elif key.startswith(SessionStateKeys.TREE_TEXT_PREFIX):
            dynamic_counts["tree_visualisation"] = dynamic_counts.get("tree_visualisation", 0) + 1
        elif key.startswith(SessionStateKeys.NHS_TERMINOLOGY_CACHE_PREFIX):
            dynamic_counts["nhs_terminology"] = dynamic_counts.get("nhs_terminology", 0) + 1
        elif key not in known_keys:
            debug_info["unknown_keys"].append(key)

    debug_info["dynamic_keys"] = dynamic_counts
    return debug_info


def add_performance_logging(func):
    """
    Decorator to add performance logging to functions.
    
    Args:
        func: Function to wrap with performance logging
        
    Returns:
        Wrapped function with performance logging
    """
    def wrapper(*args, **kwargs):
        logger = get_debug_logger()
        
        start_time = datetime.now()
        if logger.enable_debug:
            logger.logger.debug(f"Starting {func.__name__}")
        
        try:
            result = func(*args, **kwargs)
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            if logger.enable_debug:
                logger.logger.debug(f"Completed {func.__name__} in {duration:.3f}s")
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.log_error(e, f"{func.__name__} after {duration:.3f}s")
            raise
    
    return wrapper
