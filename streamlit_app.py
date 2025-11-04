"""
The Unofficial EMIS XML Toolkit - Streamlit Cloud Optimized
"""

import streamlit as st
from util_modules.ui import render_status_bar, render_results_tabs
from util_modules.xml_parsers.xml_utils import parse_xml_for_emis_guids
from util_modules.core import translate_emis_to_snomed
from util_modules.analysis.search_analyzer import SearchAnalyzer
from util_modules.analysis.report_analyzer import ReportAnalyzer
from util_modules.utils import get_debug_logger, render_debug_controls
from util_modules.analysis import render_performance_controls, display_performance_metrics
from util_modules.utils import create_processing_stats
import time
import psutil
import os
import xml.etree.ElementTree as ET



# Page configuration
st.set_page_config(
    page_title="The Unofficial EMIS XML Toolkit",
    page_icon="🏥",
    layout="wide"
)


# Main app
def main():
    # Load lookup table and render status bar first
    from util_modules.common import streamlit_safe_execute, show_file_error
    
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
    lookup_df = st.session_state.get('lookup_df')
    emis_guid_column = st.session_state.get('emis_guid_col')
    snomed_code_column = st.session_state.get('snomed_code_col')
    version_info = st.session_state.get('lookup_version_info')
    
    # Header and upload section in columns
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Clean header without button
        st.header("🔧 The Unofficial EMIS XML Toolkit")
        st.markdown("*Comprehensive EMIS XML analysis and clinical code extraction for healthcare teams*")
        
        # Dynamic MKB version text
        mkb_version = version_info.get('emis_version', 'the latest MKB lookup table')
        if mkb_version != 'the latest MKB lookup table':
            mkb_text = f"MKB {mkb_version}"
        else:
            mkb_text = mkb_version
        
        st.markdown(f"Upload EMIS XML files to analyze search logic, visualize report structures, and translate clinical codes to SNOMED using {mkb_text}.")
        
    
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
            if st.session_state.get('last_processed_file') != current_file_info:
                # New file detected - clear all previous results
                keys_to_clear = ['results', 'xml_filename', 'audit_stats', 'xml_content', 
                               'search_analysis', 'search_results', 'report_results', 'is_processing', 'unified_clinical_data_cache']
                for key in keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]
                
                # Store new file info and show notification
                st.session_state.last_processed_file = current_file_info
                st.toast(f"New file uploaded: {uploaded_xml.name}", icon="📁")
                st.rerun()
            
            # Initialize processing state
            if 'is_processing' not in st.session_state:
                st.session_state.is_processing = False
            
            # Show process button or cancel button based on state
            if not st.session_state.is_processing:
                if st.button("🔄 Process XML File", type="primary"):
                    # Clear previous results
                    if 'results' in st.session_state:
                        del st.session_state.results
                    if 'xml_filename' in st.session_state:
                        del st.session_state.xml_filename
                    if 'audit_stats' in st.session_state:
                        del st.session_state.audit_stats
                    if 'xml_content' in st.session_state:
                        del st.session_state.xml_content
                    if 'unified_clinical_data_cache' in st.session_state:
                        del st.session_state.unified_clinical_data_cache
                    if 'master_xml_json_export' in st.session_state:
                        del st.session_state.master_xml_json_export
                    # Clean up report export caches
                    keys_to_remove = [key for key in st.session_state.keys() if key.startswith(('report_excel_', 'report_json_'))]
                    for key in keys_to_remove:
                        del st.session_state[key]
                    
                    st.session_state.is_processing = True
                    st.rerun()
            else:
                if st.button("🛑 Cancel Processing", type="secondary"):
                    st.session_state.is_processing = False
                    st.success("Processing cancelled")
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
                        from util_modules.utils.caching.cache_manager import cache_manager
                        import hashlib
                        
                        xml_content_hash = hashlib.md5(xml_content.encode()).hexdigest()
                        emis_guids = cache_manager.cache_xml_code_extraction(xml_content_hash, xml_content)
                        
                        # Store emis_guids in session state for potential reprocessing
                        st.session_state.emis_guids = emis_guids
                        
                        # Log parsing results
                        if debug_logger:
                            debug_logger.log_xml_parsing_result(emis_guids)
                        
                        if not emis_guids:
                            if debug_logger:
                                debug_logger.log_error(Exception("No EMIS GUIDs found"), "XML parsing")
                            st.error("No EMIS GUIDs found in the XML file")
                            return
                        
                        # Check if EMIS lookup cache needs building for terminology server integration
                        from util_modules.utils.caching.lookup_cache import build_emis_lookup_cache, get_cache_info
                        
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
                        deduplication_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
                        
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
                        
                        # Calculate processing time and memory usage
                        processing_time = time.time() - start_time
                        memory_end = process.memory_info().rss / 1024 / 1024  # MB
                        memory_peak = max(memory_start, memory_end)
                        
                        # Create audit statistics
                        if progress_bar:
                            progress_bar.progress(85, text="Creating audit statistics...")
                        
                        audit_stats = create_processing_stats(
                            uploaded_xml.name,
                            xml_content,
                            emis_guids,
                            translated_codes,
                            processing_time
                        )
                        
                        if progress_bar:
                            progress_bar.progress(95, text="Finalizing results...")
                        
                        # Store results in session state
                        st.session_state.results = translated_codes
                        st.session_state.xml_filename = uploaded_xml.name
                        st.session_state.audit_stats = audit_stats
                        st.session_state.xml_content = xml_content  # Store for search rule analysis
                        
                        # Clear processing state as soon as we have results
                        st.session_state.is_processing = False
                        
                        # Generate analysis for report structure tabs (SEPARATE from clinical codes)
                        if progress_bar:
                            progress_bar.progress(97, text="Analyzing XML structure...")
                        
                        # CRITICAL SEPARATION: Keep report analysis completely isolated from clinical codes
                        try:
                            # Use single analysis call for report structure tabs only
                            from util_modules.analysis.xml_structure_analyzer import analyze_search_rules
                            
                            # Run full XML structure analysis - this is ONLY for report tabs, not clinical codes
                            analysis = analyze_search_rules(xml_content)
                            
                            # Store analysis results in separate, isolated session keys
                            st.session_state.xml_structure_analysis = analysis  # Full analysis for report tabs
                            st.session_state.search_analysis = analysis  # Legacy compatibility
                            
                            # Extract specialized results for report structure display
                            st.session_state.search_results = getattr(analysis, 'search_results', None)
                            st.session_state.report_results = getattr(analysis, 'report_results', None)
                            
                        except Exception as e:
                            if debug_logger:
                                debug_logger.log_error(e, "XML structure analysis")
                            # Don't fail the whole process if analysis fails, but preserve clinical codes functionality
                            st.session_state.xml_structure_analysis = None
                            st.session_state.search_analysis = None
                            st.session_state.search_results = None
                            st.session_state.report_results = None
                        
                        # Calculate success rate for logging
                        total_found = sum(1 for item in translated_codes.get('clinical', []) if item.get('Mapping Found') == 'Found')
                        total_found += sum(1 for item in translated_codes.get('medications', []) if item.get('Mapping Found') == 'Found')
                        total_items = len(translated_codes['clinical']) + len(translated_codes['medications'])
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
                        
                        # Show success with detailed toast notification
                        clinical_count = len(translated_codes['clinical'])
                        medication_count = len(translated_codes['medications'])
                        refset_count = len(translated_codes['refsets'])
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
                            analysis = st.session_state.get('xml_structure_analysis')
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
                        st.session_state.is_processing = False
                        # Also clear any progress indicators to ensure clean UI
                        if 'progress_placeholder' in st.session_state:
                            del st.session_state.progress_placeholder
                        st.rerun()
                
                except Exception as e:
                    if debug_logger:
                        debug_logger.log_error(e, "XML processing")
                    st.error(f"Error processing XML: {str(e)}")
                    # Clear the rendering message if it exists
                    if 'rendering_placeholder' in locals():
                        rendering_placeholder.empty()
                    # Reset processing state on error - ensure clean state
                    st.session_state.is_processing = False
                    # Also clear any progress indicators to ensure clean UI
                    if 'progress_placeholder' in st.session_state:
                        del st.session_state.progress_placeholder
                    st.rerun()
        
        else:
            st.info("📤 Upload an XML file to begin processing")
    
    # Full-width results section - only show when not processing
    if not st.session_state.get('is_processing', False):
        st.subheader("📊 Results")
        render_results_tabs(st.session_state.get('results'))
    elif st.session_state.get('is_processing', False):
        # Show processing indicator
        st.subheader("⏳ Processing...")
        st.info("Processing your XML file. This may take a few moments for large files.")

    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
        <p>The Unofficial EMIS XML Toolkit | Comprehensive EMIS XML analysis and clinical code extraction</p>
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