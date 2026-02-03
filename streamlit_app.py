import streamlit as st
import chardet
from utils.ui import render_status_bar, render_results_tabs, apply_custom_styling, render_performance_controls, display_performance_metrics
from utils.metadata.snomed_translation import translate_emis_to_snomed
from utils.system.session_state import (
    SessionStateKeys,
    clear_processing_state,
    clear_all_except_core,
    clear_for_new_xml,
    clear_for_new_xml_selection,
)
import hashlib
from utils.ui.theme import ThemeColours, create_info_box_style, info_box, success_box, warning_box, error_box
from utils.system import get_debug_logger, render_debug_controls
from utils.metadata.processing_stats import create_processing_stats
from utils.system.error_handling import (
    ErrorHandler,
    create_error_context,
    handle_xml_parsing_error,
    handle_file_operation_error,
    ErrorSeverity,
    display_error_to_user,
    display_generic_error,
    streamlit_safe_execute,
)


# Simple file session tracking functions
def generate_file_hash(filename: str, filesize: int) -> str:
    """Generate hash based on filename and filesize."""
    file_identity = f"{filename}_{filesize}"
    return hashlib.md5(file_identity.encode()).hexdigest()[:16]


def is_reprocessing_same_file(filename: str, filesize: int) -> bool:
    """Check if this is reprocessing the same file with existing results."""
    new_hash = generate_file_hash(filename, filesize)
    current_hash = st.session_state.get('current_file_hash')
    processed_hash = st.session_state.get('last_processed_hash')
    has_results = SessionStateKeys.PIPELINE_CODES in st.session_state
    
    return (new_hash == current_hash == processed_hash and has_results)


def mark_file_processed(filename: str, filesize: int):
    """Mark current file as processed."""
    file_hash = generate_file_hash(filename, filesize)
    st.session_state['last_processed_hash'] = file_hash
import time
import psutil
import os
import hashlib
import xml.etree.ElementTree as ET
from utils.caching.cache_manager import cache_manager

# Task weight configuration for realistic progress tracking
TASK_WEIGHTS = {
    'encoding_detection': 5,    # 5% - Fast encoding detection
    'xml_parsing': 15,          # 15% - XML structure parsing
    'cache_building': 10,       # 10% - Building lookup caches (if needed)
    'guid_processing': 10,      # 10% - Processing EMIS GUIDs
    'translation': 40,          # 40% - SNOMED translation (main work)
    'statistics': 10,           # 10% - Creating audit statistics
    'finalization': 5,          # 5% - Finalizing results
    'analysis': 5               # 5% - XML structure analysis
}

# Cumulative progress points for each stage
PROGRESS_POINTS = {
    'start': 0,
    'encoding': TASK_WEIGHTS['encoding_detection'],
    'parsing': TASK_WEIGHTS['encoding_detection'] + TASK_WEIGHTS['xml_parsing'],
    'cache': TASK_WEIGHTS['encoding_detection'] + TASK_WEIGHTS['xml_parsing'] + TASK_WEIGHTS['cache_building'],
    'guids': TASK_WEIGHTS['encoding_detection'] + TASK_WEIGHTS['xml_parsing'] + TASK_WEIGHTS['cache_building'] + TASK_WEIGHTS['guid_processing'],
    'translation_prep': TASK_WEIGHTS['encoding_detection'] + TASK_WEIGHTS['xml_parsing'] + TASK_WEIGHTS['cache_building'] + TASK_WEIGHTS['guid_processing'] + 5,  # Mid-way through translation
    'translation': TASK_WEIGHTS['encoding_detection'] + TASK_WEIGHTS['xml_parsing'] + TASK_WEIGHTS['cache_building'] + TASK_WEIGHTS['guid_processing'] + TASK_WEIGHTS['translation'],
    'statistics': 100 - TASK_WEIGHTS['finalization'] - TASK_WEIGHTS['analysis'],
    'finalization': 100 - TASK_WEIGHTS['analysis'],
    'complete': 100
}

# Page configuration
st.set_page_config(
    page_title="The Unofficial EMIS XML Toolkit",
    page_icon="static/favicon.ico",
    layout="wide"
)
# Apply global custom styling (buttons, sidebar, etc.)
apply_custom_styling()


# Main app
def main():
    # Load lookup table and render status bar first
    # Use safe execution for status bar rendering
    status_result = streamlit_safe_execute(
        "render_status_bar",
        render_status_bar,
        show_error_to_user=True,
        error_message_override="Failed to load status bar. Please refresh the page."
    )
    
    if status_result is None:
        return

    emis_guid_col, snomed_code_col, version_info = status_result
    
    # Initialise error handler for this session
    error_handler = ErrorHandler("streamlit_main")
    
    try:
        # Initialise debug logger
        debug_logger = get_debug_logger()
        
        # Render performance controls in sidebar (near top)
        perf_settings = render_performance_controls()

        # Render debug controls in sidebar (at bottom)
        render_debug_controls()

        # Logo at bottom of sidebar
        import pathlib
        import base64
        logo_path = pathlib.Path("static/logo.svg")
        if logo_path.exists():
            with open(logo_path, "r", encoding="utf-8") as f:
                svg_content = f.read()
            # Encode SVG as base64 data URI
            svg_b64 = base64.b64encode(svg_content.encode("utf-8")).decode("utf-8")
            logo_uri = f"data:image/svg+xml;base64,{svg_b64}"

            st.sidebar.markdown(
                f"""
                <div class="sidebar-footer" style="margin-top: 50px; text-align: center;">
                    <img src="{logo_uri}" style="width:100px; height:auto;" />
                </div>
                """,
                unsafe_allow_html=True,
            )

    except Exception as e:
        st.sidebar.error(f"Error in performance features: {str(e)}")
        st.sidebar.info("Running in basic mode")
        debug_logger = None
        perf_settings = {'show_metrics': False, 'show_progress': True}
    
    # Get lookup column names from session state
    emis_guid_column = st.session_state.get(SessionStateKeys.EMIS_GUID_COL)
    snomed_code_column = st.session_state.get(SessionStateKeys.SNOMED_CODE_COL)
    
    # Header and upload section in columns
    col1, col2 = st.columns([2, 1.2])
    
    with col1:
        # Clean header without button
        st.image("static/clinxml.svg", width=620)
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

        st.markdown(
            """
            <style>
            .processing-spinner {
                display: inline-flex;
                align-items: center;
                gap: 0.4rem;
                color: #9aa7b2;
                font-size: 0.9rem;
            }
            .processing-spinner .spinner {
                width: 16px;
                height: 16px;
                border: 2px solid rgba(255, 255, 255, 0.2);
                border-top-color: #6ea8ff;
                border-radius: 50%;
                animation: spin 0.8s linear infinite;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        
        if uploaded_xml is not None:
            # Detect encoding and decode content (sample only to avoid large-file slowdown)
            xml_bytes = uploaded_xml.read()
            sample_bytes = xml_bytes[:200_000]  # ~200KB sample for fast detection
            detected = chardet.detect(sample_bytes)
            encoding = detected['encoding'] or 'utf-8'

            # Try detected encoding first
            try:
                xml_content = xml_bytes.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                # If detected encoding fails (or is invalid), try UTF-8
                try:
                    xml_content = xml_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    # Last resort: UTF-8 with error replacement
                    xml_content = xml_bytes.decode('utf-8', errors='replace')
                    st.warning(f"File contains invalid UTF-8 characters. Some characters may be replaced with �.")
            try:
                uploaded_xml.seek(0)
            except Exception:
                pass
            
            # Check whether this is a different file
            new_hash = generate_file_hash(uploaded_xml.name, uploaded_xml.size)
            current_hash = st.session_state.get('current_file_hash')
            
            if new_hash != current_hash:
                # Different file: clear session and store file info
                clear_for_new_xml_selection()
                st.session_state['current_file_hash'] = new_hash
                st.session_state[SessionStateKeys.UPLOADED_FILE] = uploaded_xml
                st.session_state[SessionStateKeys.XML_FILENAME] = uploaded_xml.name
                st.session_state[SessionStateKeys.XML_FILESIZE] = uploaded_xml.size
                st.session_state[SessionStateKeys.UPLOADED_FILENAME] = uploaded_xml.name
                st.toast(f"New file uploaded: {uploaded_xml.name}", icon="📁")
                st.rerun()
            else:
                # Same file - just ensure content is stored and preserve filename
                st.session_state[SessionStateKeys.UPLOADED_FILE] = uploaded_xml
                # Ensure filename and filesize are always set (in case cleared during reprocessing)
                st.session_state[SessionStateKeys.XML_FILENAME] = uploaded_xml.name
                st.session_state[SessionStateKeys.XML_FILESIZE] = uploaded_xml.size
                st.session_state[SessionStateKeys.UPLOADED_FILENAME] = uploaded_xml.name
            
            # Initialise processing state
            if SessionStateKeys.IS_PROCESSING not in st.session_state:
                st.session_state[SessionStateKeys.IS_PROCESSING] = False
            
            button_col, indicator_col = st.columns([1.4, 1])

            # Show process button or cancel button based on state
            if not st.session_state.get(SessionStateKeys.IS_PROCESSING, False):
                # Check if this is reprocessing the same file
                is_reprocessing = is_reprocessing_same_file(uploaded_xml.name, uploaded_xml.size)
                
                if is_reprocessing:
                    button_text = "🔄 Reprocess XML File"
                    button_help = "Reprocess as if loading a new file — clears all cache"
                else:
                    button_text = "🔄 Process XML File"
                    button_help = "Process XML file for analysis"
                with button_col:
                    process_clicked = st.button(button_text, help=button_help)
                with indicator_col:
                    st.markdown("&nbsp;", unsafe_allow_html=True)

                if process_clicked:
                    if is_reprocessing:
                        # Reprocess = reset to fresh state, keeping only the uploaded file
                        # This shows "Process XML File" button on next render
                        uploaded_file_backup = st.session_state.get(SessionStateKeys.UPLOADED_FILE)
                        filename_backup = st.session_state.get(SessionStateKeys.XML_FILENAME)
                        filesize_backup = st.session_state.get(SessionStateKeys.XML_FILESIZE)

                        st.cache_data.clear()
                        clear_for_new_xml()

                        # Reset hash tracking so the file is treated as not yet processed
                        st.session_state.pop('last_processed_hash', None)
                        st.session_state.pop('current_file_hash', None)

                        # Restore only the uploaded file
                        if uploaded_file_backup:
                            st.session_state[SessionStateKeys.UPLOADED_FILE] = uploaded_file_backup
                        if filename_backup:
                            st.session_state[SessionStateKeys.XML_FILENAME] = filename_backup
                            st.session_state[SessionStateKeys.UPLOADED_FILENAME] = filename_backup
                        if filesize_backup:
                            st.session_state[SessionStateKeys.XML_FILESIZE] = filesize_backup

                        st.toast("Ready to reprocess - click 'Process XML File'", icon="🔄")
                        st.rerun()
                    else:
                        # Normal processing flow
                        st.cache_data.clear()
                        clear_for_new_xml()
                        st.session_state[SessionStateKeys.PROCESSING_CONTEXT] = "process"
                        st.session_state[SessionStateKeys.IS_PROCESSING] = True
                        st.rerun()
            else:
                with button_col:
                    if st.button("🛑 Cancel Processing", type="secondary"):
                        # Comprehensive cleanup when cancelling - same as XML upload
                        clear_for_new_xml()
                        clear_processing_state()
                        st.markdown(success_box("Processing cancelled - all data cleared"), unsafe_allow_html=True)
                        st.rerun()
                with indicator_col:
                    if st.session_state.get(SessionStateKeys.PROCESSING_CONTEXT) == "reprocess":
                        st.markdown(
                            "<div class=\"processing-spinner\"><span class=\"spinner\"></span>Reprocessing...</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown("&nbsp;", unsafe_allow_html=True)

                # Show file info as toast notification
                file_size_mb = uploaded_xml.size / (1024 * 1024)
                if file_size_mb > 10:
                    st.toast(f"Large file detected ({file_size_mb:.1f} MB). Processing optimised for cloud.", icon="⚠️")
                elif file_size_mb > 1:
                    st.toast(f"Medium file ({file_size_mb:.1f} MB). Using memory-efficient processing.", icon="📁")

                # Process the file - remove spinner to avoid UI conflicts
                try:
                    # Initialise progress tracking FIRST for immediate feedback
                    progress_bar = None
                    status_text = None
                    if perf_settings.get('show_progress', True):
                        progress_bar = st.progress(0, text="Starting XML processing...")
                        status_text = st.empty()  # For detailed status updates
                        # Force UI flush so progress bar renders before heavy processing
                        time.sleep(0.05)
                    
                    # Get stored content from session state (file already read during upload)
                    uploaded_file = st.session_state.get(SessionStateKeys.UPLOADED_FILE) or uploaded_xml
                    raw_bytes = None
                    if uploaded_file is not None:
                        try:
                            uploaded_file.seek(0)
                        except Exception:
                            pass
                        raw_bytes = uploaded_file.read()
                        try:
                            uploaded_file.seek(0)
                        except Exception:
                            pass
                    if not raw_bytes:
                        st.error("No XML content found. Please re-upload the file.")
                        st.session_state[SessionStateKeys.IS_PROCESSING] = False
                        st.rerun()
                        
                    if progress_bar:
                        progress_bar.progress(PROGRESS_POINTS['encoding'], text="Reading XML content...")
                        if status_text:
                            status_text.text(f"📁 File size: {len(raw_bytes):,} bytes - Content ready for processing")
                    
                    # Decode XML content and get encoding info for display
                    from utils.parsing.encoding import decode_xml_bytes
                    xml_content, encoding_used, declared_encoding, guessed_encoding = decode_xml_bytes(raw_bytes)
                    
                    if status_text:
                        status_text.empty()
                    
                    # Cloud-optimised processing with progress tracking (no spinner)
                    start_time = time.time()
                    
                    # Track memory usage with peak monitoring
                    process = psutil.Process(os.getpid())
                    memory_start = process.memory_info().rss / 1024 / 1024  # MB
                    memory_peak = memory_start
                    
                    # Log processing start
                    if debug_logger:
                        debug_logger.log_xml_processing_start(uploaded_xml.name, uploaded_xml.size)
                        debug_logger.log_user_action("process_xml_file", {"filename": uploaded_xml.name})
                        
                        # Parse XML with memory optimisation
                        if progress_bar:
                            progress_bar.progress(PROGRESS_POINTS['parsing'], text="Parsing XML structure...")
                            if status_text:
                                status_text.text(f"🔍 Scanning XML for EMIS GUIDs and clinical codes...")
                        
                        # Use cached XML code extraction from cache_manager (silent in UI)
                        xml_content_hash = hashlib.md5(raw_bytes).hexdigest()
                        emis_guids = cache_manager.cache_xml_code_extraction(xml_content_hash, xml_content)
                        
                        if status_text and emis_guids:
                            status_text.text(f"✅ Found {len(emis_guids):,} clinical codes in XML structure")
                        
                        # Update memory peak after parsing
                        current_memory = process.memory_info().rss / 1024 / 1024
                        memory_peak = max(memory_peak, current_memory)
                        
                        # Store emis_guids in session state for potential reprocessing
                        st.session_state[SessionStateKeys.EMIS_GUIDS] = emis_guids
                        
                        # Log parsing results
                        if debug_logger:
                            debug_logger.log_xml_parsing_result(emis_guids)
                        
                        if not emis_guids:
                            # Check if this XML contains valid searches/reports even without clinical codes
                            # This handles patient demographics filtering XMLs and other non-clinical patterns
                            try:
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
                                    # Create structured error for empty XML processing
                                    empty_xml_error = handle_xml_parsing_error(
                                        "XML file processing", 
                                        Exception("No EMIS GUIDs or valid reports found"), 
                                        "document_root"
                                    )
                                    error_handler.handle_error(empty_xml_error)
                                    
                                    # Use structured UI error display
                                    display_error_to_user(empty_xml_error, show_technical_details=True)
                                    return
                                    
                            except Exception as parse_error:
                                # Create structured error for XML validation failure
                                validation_error = handle_xml_parsing_error(
                                    "XML structure validation", 
                                    parse_error, 
                                    "document_structure"
                                )
                                error_handler.handle_error(validation_error)
                                
                                # Use structured UI error display
                                display_error_to_user(validation_error, show_technical_details=True)
                                return
                        else:
                            # Normal processing path with clinical codes
                            if debug_logger:
                                debug_logger.log_xml_parsing_result(emis_guids)
                        
                        # Only do clinical code processing if we have EMIS GUIDs
                        if emis_guids:
                            # Get lookup DataFrame for translation
                            from utils.caching.lookup_manager import get_full_lookup_df
                            lookup_df, lookup_emis_col, lookup_snomed_col = get_full_lookup_df()
                            
                            # Calculate unique GUIDs for accurate user messaging
                            def _get_emis_guid(entry):
                                return entry.get('emis_guid') or entry.get('EMIS GUID')

                            unique_guids = set(g for g in (_get_emis_guid(g) for g in emis_guids) if g)
                            
                            # Pre-calculate clinical/medication GUIDs to match completion count
                            clinical_med_guids = set()
                            for guid_info in emis_guids:
                                # Only count non-refset GUIDs that will appear in clinical/medications categories
                                guid_val = _get_emis_guid(guid_info)
                                if guid_val and not guid_info.get('is_refset', False):
                                    clinical_med_guids.add(guid_val)
                            
                            if progress_bar:
                                progress_bar.progress(PROGRESS_POINTS['guids'], text=f"Found {len(unique_guids)} unique GUIDs from {len(emis_guids)} references, preparing translation...")
                            
                            # Show progress as toast notification
                            st.toast(f"Analysing XML structure and extracting clinical data...", icon="⚙️")
                            
                            # Translate to SNOMED codes with progress tracking
                            if progress_bar:
                                progress_bar.progress(PROGRESS_POINTS['translation_prep'], text="Processing clinical codes...")
                                if status_text:
                                    status_text.text(f"🔄 Translating all discovered codes to SNOMED...")
                            
                            # Get deduplication mode from session state, default to unique_codes
                            deduplication_mode = st.session_state.get(SessionStateKeys.CURRENT_DEDUPLICATION_MODE, 'unique_codes')
                            
                            # Show intermediate progress during translation
                            translation_start_time = time.time()
                            translated_codes = translate_emis_to_snomed(
                                emis_guids,
                                lookup_df,
                                lookup_emis_col or emis_guid_column,
                                lookup_snomed_col or snomed_code_column,
                                deduplication_mode
                            )
                            # Warm unified clinical cache so tabs render immediately on first pass
                            try:
                                from utils.ui.tabs.tab_helpers import get_unified_clinical_data
                                _ = get_unified_clinical_data()
                            except Exception:
                                pass
                            translation_time = time.time() - translation_start_time
                            
                            if status_text:
                                # Count successful translations for clinical and medications only (same logic as success_rate)
                                success_count = sum(1 for item in translated_codes.get('clinical', []) if item.get('Mapping Found') == 'Found')
                                success_count += sum(1 for item in translated_codes.get('medications', []) if item.get('Mapping Found') == 'Found')
                                total_translated = len(translated_codes.get('clinical', [])) + len(translated_codes.get('medications', []))
                                status_text.text(f"✅ Translation complete: {success_count:,}/{total_translated:,} codes mapped ({translation_time:.1f}s)")
                            
                            # Update memory peak after translation
                            current_memory = process.memory_info().rss / 1024 / 1024
                            memory_peak = max(memory_peak, current_memory)
                            
                            if progress_bar:
                                progress_bar.progress(PROGRESS_POINTS['translation'], text="Translation complete, generating statistics...")
                            
                            # Show progress as toast notification
                            st.toast("Creating audit statistics and finalizing results...", icon="📊")
                            
                            # Log classification results
                            if debug_logger:
                                debug_logger.log_classification_results(translated_codes)
                        else:
                            # No clinical codes - skip translation but still show progress
                            if progress_bar:
                                progress_bar.progress(PROGRESS_POINTS['translation_prep'], text="No clinical codes found, processing structure only...")
                            st.toast("Processing patient demographics filters and XML structure...", icon="📍")
                        
                        # Calculate processing time and final memory usage
                        processing_time = time.time() - start_time
                        memory_end = process.memory_info().rss / 1024 / 1024  # MB
                        memory_peak = max(memory_peak, memory_end)  # Update final peak
                        
                        # Create audit statistics (handle case with no clinical codes)
                        if progress_bar:
                            progress_bar.progress(PROGRESS_POINTS['statistics'], text="Creating audit statistics...")
                        
                        # Use empty dict for translated_codes if no clinical codes found
                        if 'translated_codes' not in locals():
                            translated_codes = {}
                        
                        audit_stats = create_processing_stats(
                            uploaded_xml.name,
                            None,
                            emis_guids or [],  # Use empty list if None
                            translated_codes,
                            processing_time,
                            file_size_bytes=uploaded_xml.size
                        )
                        
                        if progress_bar:
                            progress_bar.progress(PROGRESS_POINTS['finalization'], text="Finalizing results...")
                        
                        # Store core metadata for current file session
                        st.session_state[SessionStateKeys.XML_FILENAME] = uploaded_xml.name
                        st.session_state[SessionStateKeys.AUDIT_STATS] = audit_stats
                        # XML content is streamed on demand for the XML viewer
                        
                        # Clear processing state as soon as we have results
                        clear_processing_state()
                        
                        # Calculate success rate for logging - handle empty translated_codes for patient demographics XMLs
                        total_found = sum(1 for item in translated_codes.get('clinical', []) if item.get('Mapping Found') == 'Found')
                        total_found += sum(1 for item in translated_codes.get('medications', []) if item.get('Mapping Found') == 'Found')
                        total_items = len(translated_codes.get('clinical', [])) + len(translated_codes.get('medications', []))
                        success_rate = (total_found / total_items * 100) if total_items > 0 else 100
                        
                        # Log processing completion
                        if debug_logger:
                            debug_logger.log_processing_complete(processing_time, success_rate)
                        
                        # Complete progress
                        if progress_bar:
                            # Get final memory usage for completion message
                            final_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
                            processing_time_str = f"{processing_time:.1f}s" if processing_time < 60 else f"{processing_time/60:.1f}m"
                            
                            completion_text = f"✅ Processing Complete in {processing_time_str}! Memory: {final_memory:.1f}MB"
                            progress_bar.progress(PROGRESS_POINTS['complete'], text=completion_text)
                            
                            # Brief pause to show completion message
                            time.sleep(0.5)
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
                        
                        # Use lightweight pipeline metadata for the completion toast
                        try:
                            entities = st.session_state.get(SessionStateKeys.PIPELINE_ENTITIES) or []
                            folders = st.session_state.get(SessionStateKeys.PIPELINE_FOLDERS) or []
                            report_count = 0
                            for ent in entities:
                                flags = ent.get("flags", {}) or {}
                                etype = flags.get("element_type") or flags.get("source_type")
                                if etype in {"list_report", "audit_report", "aggregate_report"}:
                                    report_count += 1
                            folder_count = len(folders)
                            breakdown_text = ", ".join(breakdown_parts) if breakdown_parts else "items"
                            st.toast(
                                f"Processing complete! Found {len(emis_guids)} GUIDs • {report_count} reports • "
                                f"{folder_count} folders • {total_display_items} clinical items",
                                icon="✅",
                            )
                        except Exception:
                            breakdown_text = ", ".join(breakdown_parts) if breakdown_parts else "items"
                            st.toast(f"Processing complete! Found {total_display_items} items: {breakdown_text}", icon="✅")
                        
                        # Show performance metrics if enabled
                        if perf_settings.get('show_metrics', False):
                            metrics = {
                                'total_time': processing_time,
                                'items_processed': total_display_items,
                                'success_rate': success_rate,
                                'memory_peak_mb': memory_peak
                            }
                            display_performance_metrics(metrics)
                        
                        
                        # Reset processing state on completion - ensure clean state and progress indicators
                        clear_processing_state()
                        st.rerun()
                
                except ET.ParseError as e:
                    # XML parsing specific error with structured UI handling
                    xml_error = handle_xml_parsing_error("XML file processing", e, "root")
                    error_handler.handle_error(xml_error)
                    
                    # Use structured UI error display
                    display_error_to_user(xml_error, show_technical_details=True)
                    
                    # Reset processing state on error
                    clear_processing_state()
                    st.rerun()
                    
                except UnicodeDecodeError as e:
                    # Encoding detection/decoding error with structured UI handling
                    file_error = handle_file_operation_error(
                        "encoding detection", 
                        uploaded_xml.name if uploaded_xml else "unknown", 
                        e
                    )
                    error_handler.handle_error(file_error)
                    
                    # Use structured UI error display
                    display_error_to_user(file_error, show_technical_details=True)
                    
                    # Reset processing state on error
                    clear_processing_state()
                    st.rerun()
                    
                except MemoryError as e:
                    # Memory exhaustion error with structured UI handling
                    context = create_error_context(
                        operation="XML processing",
                        user_data={"file_size": uploaded_xml.size if uploaded_xml else 0}
                    )
                    memory_error = error_handler.log_exception(
                        "XML file processing", 
                        e, 
                        context, 
                        ErrorSeverity.HIGH
                    )
                    
                    # Use structured UI error display
                    display_error_to_user(memory_error, show_technical_details=True)
                    
                    # Reset processing state on error
                    clear_processing_state()
                    st.rerun()
                    
                except Exception as e:
                    # Generic exception with structured UI handling
                    context = create_error_context(
                        operation="XML processing", 
                        file_path=uploaded_xml.name if uploaded_xml else "unknown",
                        user_data={"file_size": uploaded_xml.size if uploaded_xml else 0}
                    )
                    
                    # Use the structured error handler to log and categorize the exception
                    structured_error = error_handler.log_exception(
                        "XML file processing", 
                        e, 
                        context, 
                        ErrorSeverity.MEDIUM
                    )
                    
                    # Use structured UI error display
                    display_error_to_user(structured_error, show_technical_details=True)
                    
                    # Reset processing state on error - ensure clean state and progress indicators
                    clear_processing_state()
                    st.rerun()
        
        else:
            st.markdown(info_box("📤 Upload an XML file to begin processing"), unsafe_allow_html=True)
    
    # Full-width results section - only show when not processing and results exist
    if not st.session_state.get(SessionStateKeys.IS_PROCESSING, False):
        # Check if any processing has occurred (pipeline results only)
        has_results = (
            st.session_state.get(SessionStateKeys.PIPELINE_CODES) or
            st.session_state.get(SessionStateKeys.PIPELINE_ENTITIES)
        )
        
        st.subheader("📊 Results")
        render_results_tabs()
    elif st.session_state.get(SessionStateKeys.IS_PROCESSING, False):
        # Show processing indicator
        st.subheader("⏳ Processing...")
        st.markdown(info_box("Processing your XML file. This may take a few moments for large files."), unsafe_allow_html=True)

    # Footer with copyright and disclaimer
    from datetime import datetime
    current_year = datetime.now().year

    st.markdown("---")
    st.markdown(
        f"""<div style="text-align: center; color: #aaa; font-size: 0.8em; margin-top: 30px;">
        <p style="margin-bottom: 8px; opacity: 1.0;">
            <strong>ClinXML™ - The Unofficial EMIS XML Toolkit</strong> | Comprehensive XML analysis and clinical code extraction |
            <strong>© {current_year} ClinXML™</strong> All rights reserved.
        </p>
        <p style='font-size: 0.9em; margin-top: 8px;'>
            <strong>Disclaimer:</strong> EMIS and EMIS Web are trademarks of Optum Inc. This unofficial toolkit is not affiliated with, endorsed by, or sponsored by Optum Inc, EMIS Health, or any of their subsidiaries. All trademarks are the property of their respective owners.
        </p>
        <p style="font-size: 0.9em; opacity: 0.8;">
            Unauthorised copying, distribution, or commercial use prohibited. |
            By using this application you agree to the
            <a href='https://github.com/triplebob/clinxml-legal/blob/main/EULA-clinxml.md' style="color: inherit;">ClinXML™ EULA</a>.
        </p>
        </div>""",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
