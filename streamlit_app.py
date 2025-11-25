import streamlit as st
from utils.ui import render_status_bar, render_results_tabs
from utils.xml_parsers.xml_utils import parse_xml_for_emis_guids
from utils.core import translate_emis_to_snomed
from utils.core.session_state import SessionStateKeys, clear_processing_state, clear_results_state, clear_export_state, clear_all_except_core, clear_for_new_xml, clear_for_new_xml_selection
from utils.ui.theme import ThemeColors, create_info_box_style, info_box
from utils.analysis.search_analyzer import SearchAnalyzer
from utils.analysis.report_analyzer import ReportAnalyzer
from utils.utils import get_debug_logger, render_debug_controls
from utils.analysis import render_performance_controls, display_performance_metrics
from utils.utils import create_processing_stats
from utils.ui.theme import info_box, success_box, warning_box, error_box
import time
import psutil
import os
import xml.etree.ElementTree as ET


# Page configuration
st.set_page_config(
    page_title="The Unofficial EMIS XML Toolkit",
    page_icon="img/favicon.ico",
    layout="wide"
)


# Main app
def main():
    # Load lookup table and render status bar first
    from utils.common import streamlit_safe_execute, show_file_error
    
    # Use safe execution for status bar rendering
    status_result = streamlit_safe_execute(
        "render_status_bar",
        render_status_bar,
        show_error_to_user=True,
        error_message_override="Failed to load status bar. Please refresh the page."
    )
    
    if status_result is None:
        return
    
    lookup_df, emis_guid_col, snomed_code_col = status_result
    
    try:
        # Initialize debug logger
        debug_logger = get_debug_logger()
        
        # Render performance controls in sidebar (near top)
        perf_settings = render_performance_controls()
        
        # Render debug controls in sidebar (at bottom)
        render_debug_controls()
    
    except Exception as e:
        st.sidebar.error(f"Error in performance features: {str(e)}")
        st.sidebar.info("Running in basic mode")
        debug_logger = None
        perf_settings = {'strategy': 'Memory Optimized', 'max_workers': 1, 'memory_optimize': True, 'show_metrics': False, 'show_progress': True}
    
    # Get lookup table from session state
    lookup_df = st.session_state.get(SessionStateKeys.LOOKUP_DF)
    emis_guid_column = st.session_state.get(SessionStateKeys.EMIS_GUID_COL)
    snomed_code_column = st.session_state.get(SessionStateKeys.SNOMED_CODE_COL)
    version_info = st.session_state.get(SessionStateKeys.LOOKUP_VERSION_INFO)
    
    # Header and upload section in columns
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Clean header without button
        st.image("img/clinxml.svg", width=620)
        st.caption("*&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Comprehensive EMIS XML analysis and clinical code extraction for NHS healthcare teams*")
        
        # Dynamic MKB version text
        mkb_version = version_info.get('emis_version', 'the latest MKB lookup table')
        if mkb_version != 'the latest MKB lookup table':
            mkb_text = f"MKB {mkb_version}"
        else:
            mkb_text = mkb_version
        
        
    
    with col2:
        st.subheader("📁 Upload XML File")
        uploaded_xml = st.file_uploader(
            "Choose EMIS XML file",
            type=['xml'],
            help="Select an EMIS clinical search XML file"
        )
        
        if uploaded_xml is not None:
            # Check if this is a different file than previously processed
            current_file_info = f"{uploaded_xml.name}_{uploaded_xml.size}"
            if st.session_state.get(SessionStateKeys.LAST_PROCESSED_FILE) != current_file_info:
                # New file selected - lightweight cleanup preserving lookup cache (keeps status bar loaded)
                clear_for_new_xml_selection()
                
                # Store new file info and show notification
                st.session_state[SessionStateKeys.LAST_PROCESSED_FILE] = current_file_info
                st.toast(f"New file uploaded: {uploaded_xml.name}", icon="📁")
                st.rerun()
            
            # Initialize processing state
            if SessionStateKeys.IS_PROCESSING not in st.session_state:
                st.session_state[SessionStateKeys.IS_PROCESSING] = False
            
            # Show process button or cancel button based on state
            if not st.session_state.get(SessionStateKeys.IS_PROCESSING, False):
                if st.button("🔄 Process XML File", type="primary"):
                    # Comprehensive cleanup when processing starts (includes export cache + GC)
                    clear_for_new_xml()
                    
                    st.session_state[SessionStateKeys.IS_PROCESSING] = True
                    st.rerun()
            else:
                if st.button("🛑 Cancel Processing", type="secondary"):
                    # Comprehensive cleanup when cancelling - same as new XML upload
                    clear_for_new_xml()
                    st.session_state[SessionStateKeys.IS_PROCESSING] = False
                    from utils.ui.theme import success_box
                    st.markdown(success_box("Processing cancelled - all data cleared"), unsafe_allow_html=True)
                    st.rerun()
                
                # Show file info as toast notification
                file_size_mb = uploaded_xml.size / (1024 * 1024)
                if file_size_mb > 10:
                    st.toast(f"Large file detected ({file_size_mb:.1f} MB). Processing optimized for cloud.", icon="⚠️")
                elif file_size_mb > 1:
                    st.toast(f"Medium file ({file_size_mb:.1f} MB). Using memory-efficient processing.", icon="📁")
                
                # Process the file - remove spinner to avoid UI conflicts
                try:
                    # Read XML content
                    xml_content = uploaded_xml.read().decode('utf-8')
                    
                    # Cloud-optimized processing with progress tracking (no spinner)
                    start_time = time.time()
                    
                    # Track memory usage
                    process = psutil.Process(os.getpid())
                    memory_start = process.memory_info().rss / 1024 / 1024  # MB
                    
                    # Initialize progress tracking
                    progress_bar = None
                    if perf_settings.get('show_progress', True):
                        progress_bar = st.progress(0, text="Starting XML processing...")
                    
                    # Log processing start
                    if debug_logger:
                        debug_logger.log_xml_processing_start(uploaded_xml.name, uploaded_xml.size)
                        debug_logger.log_user_action("process_xml_file", {"filename": uploaded_xml.name})
                        
                        # Parse XML with memory optimization
                        if progress_bar:
                            progress_bar.progress(5, text="Parsing XML structure...")
                        
                        # Use cached XML code extraction from cache_manager
                        from utils.utils.caching.cache_manager import cache_manager
                        import hashlib
                        
                        xml_content_hash = hashlib.md5(xml_content.encode()).hexdigest()
                        emis_guids = cache_manager.cache_xml_code_extraction(xml_content_hash, xml_content)
                        
                        # Store emis_guids in session state for potential reprocessing
                        st.session_state[SessionStateKeys.EMIS_GUIDS] = emis_guids
                        
                        # Log parsing results
                        if debug_logger:
                            debug_logger.log_xml_parsing_result(emis_guids)
                        
                        if not emis_guids:
                            # Check if this XML contains valid searches/reports even without clinical codes
                            # This handles patient demographics filtering XMLs and other non-clinical patterns
                            try:
                                import xml.etree.ElementTree as ET
                                root = ET.fromstring(xml_content)
                                
                                # Check for report elements (with any namespace)
                                reports_found = (
                                    root.findall('.//report') or 
                                    root.findall('.//{http://www.e-mis.com/emisopen}report') or
                                    root.findall('.//search') or
                                    root.findall('.//{http://www.e-mis.com/emisopen}search')
                                )
                                
                                if reports_found:
                                    # Valid XML with searches/reports but no clinical codes
                                    if debug_logger:
                                        debug_logger.log_user_action("xml_structure_validation", {"pattern": "patient_demographics_filtering", "clinical_codes": False})
                                    st.markdown(info_box("📍 This XML contains patient demographic searches, but no detected clinical codes. Analysis will proceed with structure-only processing."), unsafe_allow_html=True)
                                    # Set empty clinical codes but continue processing
                                    translated_codes = {}
                                else:
                                    # No reports found - truly invalid XML
                                    if debug_logger:
                                        debug_logger.log_error(Exception("No EMIS GUIDs or valid reports found"), "XML parsing")
                                    from utils.ui.theme import error_box
                                    st.markdown(error_box("No EMIS GUIDs or valid search reports found in the XML file"), unsafe_allow_html=True)
                                    return
                                    
                            except Exception as parse_error:
                                if debug_logger:
                                    debug_logger.log_error(parse_error, "XML structure validation")
                                from utils.ui.theme import error_box
                                st.markdown(error_box(f"Error validating XML structure: {str(parse_error)}"), unsafe_allow_html=True)
                                return
                        else:
                            # Normal processing path with clinical codes
                            if debug_logger:
                                debug_logger.log_xml_parsing_result(emis_guids)
                        
                        # Only do clinical code processing if we have EMIS GUIDs
                        if emis_guids:
                            # Check if EMIS lookup cache needs building for terminology server integration
                            from utils.utils.caching.lookup_cache import build_emis_lookup_cache, get_cache_info
                            
                            # Skip cache building if we already loaded from cache
                            load_source = version_info.get('load_source', 'unknown')
                            if load_source == 'cache':
                                # We already loaded from cache, no need to rebuild
                                cache_built = True
                            else:
                                cache_info = get_cache_info(lookup_df, version_info)
                                
                                if cache_info["status"] == "not_cached":
                                    # Cache needs building - show progress
                                    if progress_bar:
                                        progress_bar.progress(20, text="Building EMIS lookup cache for terminology server (first time)...")
                                    
                                    cache_built = build_emis_lookup_cache(lookup_df, snomed_code_col, emis_guid_col, version_info)
                                    
                                    if cache_built:
                                        st.toast("✅ EMIS lookup cache built for terminology server optimization", icon="⚡")
                                elif cache_info["status"] == "cached":
                                    # Cache already exists - no delay needed
                                    cache_built = True
                                else:
                                    # Cache check failed - try to build anyway
                                    cache_built = build_emis_lookup_cache(lookup_df, snomed_code_col, emis_guid_col, version_info)
                            
                            if progress_bar:
                                progress_bar.progress(25, text=f"Found {len(emis_guids)} GUIDs, preparing translation...")
                            
                            # Show progress as toast notification
                            st.toast(f"Analyzing XML structure and extracting clinical data...", icon="⚙️")
                            
                            # Translate to SNOMED codes with progress tracking
                            if progress_bar:
                                progress_bar.progress(30, text="Processing clinical codes...")
                            
                            # Get deduplication mode from session state, default to unique_codes
                            deduplication_mode = st.session_state.get(SessionStateKeys.CURRENT_DEDUPLICATION_MODE, 'unique_codes')
                            
                            translated_codes = translate_emis_to_snomed(
                                emis_guids, 
                                lookup_df, 
                                emis_guid_column, 
                                snomed_code_column,
                                deduplication_mode
                            )
                            
                            if progress_bar:
                                progress_bar.progress(75, text="Translation complete, generating statistics...")
                            
                            # Show progress as toast notification
                            st.toast("Creating audit statistics and finalizing results...", icon="📊")
                            
                            # Log classification results
                            if debug_logger:
                                debug_logger.log_classification_results(translated_codes)
                        else:
                            # No clinical codes - skip translation but still show progress
                            if progress_bar:
                                progress_bar.progress(30, text="No clinical codes found, processing structure only...")
                            st.toast("Processing patient demographics filters and XML structure...", icon="📍")
                        
                        # Calculate processing time and memory usage
                        processing_time = time.time() - start_time
                        memory_end = process.memory_info().rss / 1024 / 1024  # MB
                        memory_peak = max(memory_start, memory_end)
                        
                        # Create audit statistics (handle case with no clinical codes)
                        if progress_bar:
                            progress_bar.progress(85, text="Creating audit statistics...")
                        
                        # Use empty dict for translated_codes if no clinical codes found
                        if 'translated_codes' not in locals():
                            translated_codes = {}
                        
                        audit_stats = create_processing_stats(
                            uploaded_xml.name,
                            xml_content,
                            emis_guids or [],  # Use empty list if None
                            translated_codes,
                            processing_time
                        )
                        
                        if progress_bar:
                            progress_bar.progress(95, text="Finalizing results...")
                        
                        # Store results in session state
                        st.session_state[SessionStateKeys.RESULTS] = translated_codes
                        st.session_state[SessionStateKeys.XML_FILENAME] = uploaded_xml.name
                        st.session_state[SessionStateKeys.AUDIT_STATS] = audit_stats
                        st.session_state[SessionStateKeys.XML_CONTENT] = xml_content  # Store for search rule analysis
                        
                        # Clear processing state as soon as we have results
                        st.session_state[SessionStateKeys.IS_PROCESSING] = False
                        
                        # Generate analysis for report structure tabs (SEPARATE from clinical codes)
                        if progress_bar:
                            progress_bar.progress(97, text="Analyzing XML structure...")
                        
                        # CRITICAL SEPARATION: Keep report analysis completely isolated from clinical codes
                        try:
                            # Use single analysis call for report structure tabs only
                            from utils.analysis.xml_structure_analyzer import analyze_search_rules
                            
                            # Run full XML structure analysis - this is ONLY for report tabs, not clinical codes
                            analysis = analyze_search_rules(xml_content)
                            
                            # Store analysis results in separate, isolated session keys
                            st.session_state[SessionStateKeys.XML_STRUCTURE_ANALYSIS] = analysis  # Full analysis for report tabs
                            st.session_state[SessionStateKeys.SEARCH_ANALYSIS] = analysis  # Legacy compatibility
                            
                            # Extract specialized results for report structure display
                            st.session_state[SessionStateKeys.SEARCH_RESULTS] = getattr(analysis, 'search_results', None)
                            st.session_state[SessionStateKeys.REPORT_RESULTS] = getattr(analysis, 'report_results', None)
                            
                        except Exception as e:
                            if debug_logger:
                                debug_logger.log_error(e, "XML structure analysis")
                            # Don't fail the whole process if analysis fails, but preserve clinical codes functionality
                            st.session_state[SessionStateKeys.XML_STRUCTURE_ANALYSIS] = None
                            st.session_state[SessionStateKeys.SEARCH_ANALYSIS] = None
                            st.session_state[SessionStateKeys.SEARCH_RESULTS] = None
                            st.session_state[SessionStateKeys.REPORT_RESULTS] = None
                        
                        # Calculate success rate for logging - handle empty translated_codes for patient demographics XMLs
                        total_found = sum(1 for item in translated_codes.get('clinical', []) if item.get('Mapping Found') == 'Found')
                        total_found += sum(1 for item in translated_codes.get('medications', []) if item.get('Mapping Found') == 'Found')
                        total_items = len(translated_codes.get('clinical', [])) + len(translated_codes.get('medications', []))
                        success_rate = (total_found / total_items * 100) if total_items > 0 else 100
                        
                        # Log processing completion
                        if debug_logger:
                            debug_logger.log_processing_complete(processing_time, success_rate)
                        
                        # Complete progress with helpful message about rendering
                        if progress_bar:
                            progress_bar.progress(100, text="Processing Complete! Rendering Results - This May Take a Moment...")
                        
                        # Remove the rendering message as it's no longer needed
                        rendering_placeholder = st.empty()
                        
                        # Clear progress bar after longer pause to show the message
                        if progress_bar:
                            time.sleep(1.0)  # Longer pause to show completion message
                            progress_bar.empty()
                        
                        # Show success with detailed toast notification - handle empty translated_codes for patient demographics XMLs
                        clinical_count = len(translated_codes.get('clinical', []))
                        medication_count = len(translated_codes.get('medications', []))
                        refset_count = len(translated_codes.get('refsets', []))
                        pseudo_refset_count = len(translated_codes.get('pseudo_refsets', []))
                        clinical_pseudo_count = len(translated_codes.get('clinical_pseudo_members', []))
                        medication_pseudo_count = len(translated_codes.get('medication_pseudo_members', []))
                        
                        total_display_items = clinical_count + medication_count + refset_count + pseudo_refset_count + clinical_pseudo_count + medication_pseudo_count
                        
                        # Create detailed breakdown message
                        breakdown_parts = []
                        if clinical_count > 0:
                            breakdown_parts.append(f"{clinical_count} clinical codes")
                        if medication_count > 0:
                            breakdown_parts.append(f"{medication_count} medications")
                        if refset_count > 0:
                            breakdown_parts.append(f"{refset_count} refsets")
                        if pseudo_refset_count > 0:
                            breakdown_parts.append(f"{pseudo_refset_count} pseudo-refsets")
                        
                        # PERFORMANCE FIX: Use simple toast without expensive analysis operations
                        # Quick structure analysis for toast
                        try:
                            # Use already computed analysis from session state
                            analysis = st.session_state.get(SessionStateKeys.XML_STRUCTURE_ANALYSIS)
                            if analysis:
                                folder_count = len(analysis.folders) if analysis.folders else 0
                                total_reports = len(analysis.reports) if analysis.reports else 0
                                
                                breakdown_text = ", ".join(breakdown_parts) if breakdown_parts else "items"
                                st.toast(f"Processing complete! Found {len(emis_guids)} GUIDs • {total_reports} reports • {folder_count} folders • {total_display_items} clinical items", icon="✅")
                            else:
                                # Fallback to simple message if analysis not available
                                breakdown_text = ", ".join(breakdown_parts) if breakdown_parts else "items" 
                                st.toast(f"Processing complete! Found {total_display_items} items: {breakdown_text}", icon="✅")
                        except Exception:
                            # Fallback to original message if any issues
                            breakdown_text = ", ".join(breakdown_parts) if breakdown_parts else "items" 
                            st.toast(f"Processing complete! Found {total_display_items} items: {breakdown_text}", icon="✅")
                        
                        # Show performance metrics if enabled
                        if perf_settings.get('show_metrics', False):
                            metrics = {
                                'total_time': processing_time,
                                'processing_strategy': perf_settings.get('strategy', 'Memory Optimized'),
                                'items_processed': total_display_items,
                                'success_rate': success_rate,
                                'memory_peak_mb': memory_peak
                            }
                            display_performance_metrics(metrics)
                        
                        # Clear the rendering message
                        if 'rendering_placeholder' in locals():
                            rendering_placeholder.empty()
                        
                        # Reset processing state on completion - ensure clean state
                        st.session_state[SessionStateKeys.IS_PROCESSING] = False
                        # Also clear any progress indicators to ensure clean UI
                        clear_processing_state()
                        st.rerun()
                
                except Exception as e:
                    # Print detailed error information to console for debugging
                    import traceback
                    full_error = traceback.format_exc()
                    
                    print("="*80)
                    print("GEOGRAPHICAL XML PROCESSING ERROR")
                    print("="*80)
                    print(f"Error type: {type(e).__name__}")
                    print(f"Error message: {str(e)}")
                    print("\nFull traceback:")
                    print(full_error)
                    print("="*80)
                    
                    if debug_logger:
                        debug_logger.log_error(e, "XML processing")
                    from utils.ui.theme import error_box
                    st.markdown(error_box(f"Error processing XML: {str(e)}"), unsafe_allow_html=True)
                    
                    # Clear the rendering message if it exists
                    if 'rendering_placeholder' in locals():
                        rendering_placeholder.empty()
                    # Reset processing state on error - ensure clean state
                    st.session_state[SessionStateKeys.IS_PROCESSING] = False
                    # Also clear any progress indicators to ensure clean UI
                    clear_processing_state()
                    st.rerun()
        
        else:
            st.markdown(info_box("📤 Upload an XML file to begin processing"), unsafe_allow_html=True)
    
    # Full-width results section - only show when not processing
    if not st.session_state.get(SessionStateKeys.IS_PROCESSING, False):
        
        st.subheader("📊 Results")
        render_results_tabs(st.session_state.get(SessionStateKeys.RESULTS))
    elif st.session_state.get(SessionStateKeys.IS_PROCESSING, False):
        # Show processing indicator
        st.subheader("⏳ Processing...")
        st.markdown(info_box("Processing your XML file. This may take a few moments for large files."), unsafe_allow_html=True)

    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #aaa;'>
        <p>ClinXML - The Unofficial EMIS XML Toolkit | Comprehensive XML analysis and clinical code extraction</p>
        <p style='font-size: 0.8em; margin-top: 10px;'>
        <strong>Disclaimer:</strong> EMIS and EMIS Web are trademarks of Optum Inc. This unofficial toolkit is not affiliated with, 
        endorsed by, or sponsored by Optum Inc, EMIS Health, or any of their subsidiaries. All trademarks are the property of their respective owners.
        </p>
        </div>
        """, 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
