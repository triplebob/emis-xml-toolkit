"""
UI Helper Functions
Reusable functions to reduce code duplication across Streamlit UI components.
"""

import streamlit as st
import pandas as pd
import io
import sys
from datetime import datetime
from typing import List, Dict, Any, Callable, Optional
from ..utils.export_debug import log_export_created, track_export_object, log_memory_after_export
from ..core.session_state import SessionStateKeys


def create_styled_dataframe(df: pd.DataFrame, style_function: Callable) -> Any:
    """
    Create a styled dataframe with consistent formatting.
    
    Args:
        df: The DataFrame to style
        style_function: Function that returns styling for each row
        
    Returns:
        Styled DataFrame
    """
    if df.empty:
        return df
    
    return df.style.apply(style_function, axis=1)





def get_success_highlighting_function(success_column: str = 'Mapping Found'):
    """
    Get a function for highlighting rows based on mapping success.
    
    Args:
        success_column: Column name that contains success/failure status
        
    Returns:
        Function for styling DataFrame rows
    """
    def highlight_success(row):
        if row[success_column] == 'Found':
            return ['background-color: #1F4E3D; color: #FAFAFA'] * len(row)  # Green for found
        else:
            return ['background-color: #660022; color: #FAFAFA'] * len(row)  # Wine red for not found
    
    return highlight_success


def get_warning_highlighting_function():
    """
    Get a function for highlighting rows with warning colors.
    
    Returns:
        Function for styling DataFrame rows with warning colors
    """
    def highlight_warning(row):
        return ['background-color: #7A5F0B; color: #FAFAFA'] * len(row)  # Amber for warning
    
    return highlight_warning



def render_section_with_data(
    title: str,
    data: List[Dict],
    info_text: str,
    empty_message: str,
    download_label: str,
    filename_prefix: str,
    highlighting_function: Optional[Callable] = None,
    additional_processing: Optional[Callable] = None
) -> None:
    """
    Render a standardized section with data table and download button with export filtering.
    
    Args:
        title: Section title
        data: List of dictionaries containing the data
        info_text: Information text to display
        empty_message: Message to show when no data
        download_label: Label for download button
        filename_prefix: Prefix for download filename
        highlighting_function: Optional function to highlight rows
        additional_processing: Optional function for additional data processing
    """
    if title and title.strip():  # Only show subheader if title is provided and not empty
        st.subheader(title)
    if info_text:
        st.markdown(f"""
        <div style="
            background-color: #28546B;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 1rem;
        ">
            {info_text}
        </div>
        """, unsafe_allow_html=True)
    
    if data:
        # Get current modes for cache key
        current_mode = st.session_state.get(SessionStateKeys.CURRENT_DEDUPLICATION_MODE, 'unique_codes')
        show_debug = st.session_state.get(SessionStateKeys.DEBUG_MODE, False)
        
        # Create a cache key for this specific data processing
        data_hash = hash(str(sorted(data[0].keys()) if data else "empty"))
        cache_key = f"processed_df_{filename_prefix}_{data_hash}_{current_mode}_{show_debug}"
        
        # Check if we have cached processed data
        if cache_key in st.session_state:
            df, display_df = st.session_state[cache_key]
        else:
            df = pd.DataFrame(data)
            
            # Apply deduplication based on current mode BEFORE other processing
            if current_mode == 'unique_codes' and df is not None and not df.empty:
                # Apply deduplication by EMIS GUID for unique_codes mode
                if 'EMIS GUID' in df.columns:
                    # Group by EMIS GUID and keep the first occurrence
                    df = df.drop_duplicates(subset=['EMIS GUID'], keep='first')
            
            # Apply additional processing if provided
            if additional_processing:
                df = additional_processing(df)
            
            # Create display version with emojis for UI
            display_df = df.copy()
        
        # Apply proper column filtering and ordering like clinical codes tab
        from .tabs.field_mapping import get_display_columns, get_hidden_columns
        
        # Get debug mode from sidebar toggle (not tab-specific toggles)
        show_debug = st.session_state.get(SessionStateKeys.DEBUG_MODE, False)
        
        # Always hide certain columns
        always_hidden = ['ValueSet GUID', 'VALUESET GUID']
        for col in always_hidden:
            if col in display_df.columns:
                display_df = display_df.drop(columns=[col])
        
        # Hide raw duplicate columns that have formatted versions
        raw_columns_to_hide = ['source_guid', 'source_name', 'source_container', 'source_type', 'report_type']
        for col in raw_columns_to_hide:
            if col in display_df.columns:
                display_df = display_df.drop(columns=[col])
        
        # Hide internal categorization flags
        internal_flags_to_hide = ['is_refset', 'is_pseudo', 'is_medication', 'is_pseudorefset', 'is_pseudomember']
        for col in internal_flags_to_hide:
            if col in display_df.columns:
                display_df = display_df.drop(columns=[col])
        
        # Hide debug columns unless debug mode is enabled
        if not show_debug and '_original_fields' in display_df.columns:
            display_df = display_df.drop(columns=['_original_fields'])
        
        # Hide source columns in unique_codes mode for display only (keep data for export)
        current_mode = st.session_state.get(SessionStateKeys.CURRENT_DEDUPLICATION_MODE, 'unique_codes')
        if current_mode == 'unique_codes':
            # Remove source columns from display but keep original df with all columns for export
            columns_to_hide = ['Source Type', 'Source Name', 'Source Container', 'Source GUID']
            for col in columns_to_hide:
                if col in display_df.columns:
                    display_df = display_df.drop(columns=[col])
        
        # Apply column ordering if we have clinical code data
        if 'EMIS GUID' in display_df.columns and 'SNOMED Code' in display_df.columns:
            try:
                display_columns = get_display_columns()
                # Reorder columns to match expected order, keeping any extra columns at the end
                ordered_columns = []
                for col in display_columns:
                    if col in display_df.columns:
                        ordered_columns.append(col)
                # Add any remaining columns not in the standard order
                for col in display_df.columns:
                    if col not in ordered_columns:
                        ordered_columns.append(col)
                display_df = display_df[ordered_columns]
            except Exception:
                # Fallback to original column order if reordering fails
                pass
        
        # Add emojis to specific columns for better UI display (without affecting CSV export)
        # Only add emojis if they're not already present to prevent multiplication
        if 'EMIS GUID' in display_df.columns:
            display_df['EMIS GUID'] = display_df['EMIS GUID'].astype(str).apply(
                lambda x: x if str(x).startswith('🔍') else f'🔍 {x}'
            )
        if 'SNOMED Code' in display_df.columns:
            display_df['SNOMED Code'] = display_df['SNOMED Code'].astype(str).apply(
                lambda x: x if str(x).startswith('⚕️') else f'⚕️ {x}'
            )
        if 'Source Type' in display_df.columns:
            # Only add emojis if they're not already present (to avoid double emojis)
            display_df['Source Type'] = display_df['Source Type'].apply(lambda x: 
                x if ('🔍' in str(x) or '📊' in str(x) or '📋' in str(x) or '📈' in str(x)) else (
                    f"🔍 {x}" if x and x == "Search" else
                    f"📊 {x}" if x and "Aggregate" in str(x) else
                    f"📋 {x}" if x and "List" in str(x) else
                    f"📈 {x}" if x and "Audit" in str(x) else
                    f"📊 {x}" if x else x  # Don't add emoji to empty values
                )
            )
            
            # Cache the processed dataframes for future use
            st.session_state[cache_key] = (df.copy(), display_df.copy())
        
        # Apply highlighting if provided
        if highlighting_function:
            styled_df = create_styled_dataframe(display_df, highlighting_function)
            st.dataframe(styled_df, width='stretch')
        else:
            st.dataframe(display_df, width='stretch')
        
        # Export filtering and download section as single fragment with conditional logic
        if 'Mapping Found' in df.columns:
            
            @st.fragment
            def export_section_fragment():
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    # Analyze data to determine available filter options
                    current_mode = st.session_state.get(SessionStateKeys.CURRENT_DEDUPLICATION_MODE, 'unique_codes')
                    has_source_tracking = 'Source GUID' in df.columns or ('Source Type' in df.columns and 'Source Name' in df.columns)
                    
                    # Count different types of data
                    total_count = len(df)
                    matched_count = len(df[df['Mapping Found'] == 'Found'])
                    unmatched_count = total_count - matched_count
                    
                    # Count source types specific to current data context (not always clinical codes)
                    search_count = 0
                    report_count = 0
                    if has_source_tracking:
                        if 'Source Type' in df.columns:
                            # Count from the current dataframe being displayed (context-specific)
                            search_count = len(df[df['Source Type'].str.contains('🔍', na=False)])
                            report_count = len(df[df['Source Type'].str.contains('📊', na=False)])
                        else:
                            # Fallback: try to determine from data content
                            search_count = len([item for item in data if item.get('source_type') == 'search'])
                            report_count = len([item for item in data if item.get('source_type') == 'report'])
                        
                        # Debug: Show what we found
                        if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
                            print(f"[DEBUG] Context-specific source counts - Searches: {search_count}, Reports: {report_count}", file=sys.stderr)
                    
                    # Build conditional filter options
                    filter_options = ["All Codes"]
                    
                    # Smart logic for matched/unmatched filters
                    if matched_count > 0 and unmatched_count > 0:
                        # Both matched and unmatched exist - show both filter options
                        filter_options.append("Only Matched")
                        filter_options.append("Only Unmatched")
                    elif matched_count > 0 and unmatched_count == 0:
                        # All codes are matched - no need for "Only Matched" (same as "All Codes")
                        pass  # Just keep "All Codes"
                    elif matched_count == 0 and unmatched_count > 0:
                        # All codes are unmatched - no need for "Only Unmatched" (same as "All Codes")
                        pass  # Just keep "All Codes"
                    
                    # Add source-based filters only if in per_source mode and both sources exist
                    if has_source_tracking and current_mode == 'unique_per_entity':
                        if search_count > 0:
                            filter_options.append("Only Codes from Searches")
                        if report_count > 0:
                            filter_options.append("Only Codes from Reports")
                    
                    # Show radio with conditional options
                    export_filter = st.radio(
                        "Export Filter:",
                        filter_options,
                        key=f"export_filter_{filename_prefix}",
                        horizontal=len(filter_options) <= 3
                    )
                    
                    # Always show counts for transparency (even with single filter option)
                    st.caption(f"📊 Total: {total_count} | ✅ Matched: {matched_count} | ❌ Unmatched: {unmatched_count}")
                    if has_source_tracking and current_mode == 'unique_per_entity':
                        st.caption(f"🔍 Searches: {search_count} | 📊 Reports: {report_count}")
                
                with col2:
                    # Filter data based on selection - need to handle both display mode and export filtering
                    filtered_df = None
                    
                    if export_filter == "Only Matched":
                        filtered_df = display_df[display_df['Mapping Found'] == 'Found']
                        export_label = download_label.replace("📥", "📥 ✅")
                        export_suffix = "_matched"
                    elif export_filter == "Only Unmatched":
                        filtered_df = display_df[display_df['Mapping Found'] != 'Found']
                        export_label = download_label.replace("📥", "📥 ❌")
                        export_suffix = "_unmatched"
                    elif export_filter == "Only Codes from Searches":
                        # Filter by source - check if Source Type column is available, otherwise look for source info in data
                        if 'Source Type' in display_df.columns:
                            filtered_df = display_df[display_df['Source Type'] == 'Search']
                        else:
                            # Filter based on original data source tracking
                            search_codes = []
                            for item in data:
                                if item.get('source_type') == 'search':
                                    search_codes.append(item)
                            filtered_df = pd.DataFrame(search_codes) if search_codes else pd.DataFrame()
                        export_label = download_label.replace("📥", "📥 🔍")
                        export_suffix = "_searches"
                    elif export_filter == "Only Codes from Reports":
                        # Filter by source - check if Source Type column is available, otherwise look for source info in data
                        if 'Source Type' in display_df.columns:
                            filtered_df = display_df[display_df['Source Type'].str.contains('Report', na=False)]
                        else:
                            # Filter based on original data source tracking
                            report_codes = []
                            for item in data:
                                if item.get('source_type') == 'report':
                                    report_codes.append(item)
                            filtered_df = pd.DataFrame(report_codes) if report_codes else pd.DataFrame()
                        export_label = download_label.replace("📥", "📥 📊")
                        export_suffix = "_reports"
                    else:  # All Codes
                        filtered_df = display_df
                        export_label = download_label
                        export_suffix = ""
                    
                    # Add deduplication mode to labels and filename
                    mode_suffix = "_unique" if current_mode == 'unique_codes' else "_per_source"
                    if export_suffix:
                        export_suffix = mode_suffix + export_suffix
                    else:
                        export_suffix = mode_suffix
                    
                    mode_label = " (Unique)" if current_mode == 'unique_codes' else " (Per Source)"
                    export_label = export_label.replace("📥", f"📥{mode_label}")
                    
                    # Show count of filtered items
                    st.caption(f"📊 {len(filtered_df)} of {len(display_df)} items selected for export")
                    
                    # Render download button with filtered data (clean version for export)
                    xml_filename = st.session_state.get(SessionStateKeys.XML_FILENAME)
                    from utils.export_handlers.ui_export_manager import UIExportManager
                    export_manager = UIExportManager()
                    export_manager.render_download_button(
                        data=filtered_df,
                        label=export_label,
                        filename_prefix=filename_prefix + export_suffix,
                        xml_filename=xml_filename,
                        key=f"download_{filename_prefix}_{export_filter.lower().replace(' ', '_')}"
                    )
            
            export_section_fragment()
        else:
            # No Mapping Found column, render normal download button (use cleaned data)
            xml_filename = st.session_state.get(SessionStateKeys.XML_FILENAME)
            from utils.export_handlers.ui_export_manager import UIExportManager
            export_manager = UIExportManager()
            export_manager.render_download_button(
                data=display_df,
                label=download_label,
                filename_prefix=filename_prefix,
                xml_filename=xml_filename,
                key=f"download_{filename_prefix}_all"
            )
    else:
        st.info(empty_message)


def render_metrics_row(metrics: List[Dict[str, Any]], columns: int = 4) -> None:
    """
    Render a row of metrics with consistent formatting and color coding.
    
    Args:
        metrics: List of metric dictionaries with 'label', 'value', and optional 'thresholds'
        columns: Number of columns to display metrics in
    """
    cols = st.columns(columns)
    
    for i, metric in enumerate(metrics):
        col_index = i % columns
        label = metric['label']
        value = metric['value']
        thresholds = metric.get('thresholds', {})
        
        with cols[col_index]:
            # Apply color coding based on thresholds
            if thresholds:
                if 'error' in thresholds and value >= thresholds['error']:
                    st.error(f"**{label}:** {value}")
                elif 'warning' in thresholds and value >= thresholds['warning']:
                    st.warning(f"**{label}:** {value}")
                elif 'success' in thresholds and value >= thresholds['success']:
                    st.success(f"**{label}:** {value}")
                else:
                    st.info(f"**{label}:** {value}")
            else:
                st.metric(label, value)


def render_success_rate_metric(
    label: str, 
    found: int, 
    total: int, 
    success_threshold: float = 90.0,
    warning_threshold: float = 70.0
) -> None:
    """
    Render a success rate metric with color coding.
    
    Args:
        label: Label for the metric
        found: Number of successful items
        total: Total number of items
        success_threshold: Threshold for success color (green)
        warning_threshold: Threshold for warning color (yellow)
    """
    if total == 0:
        st.markdown(f"""
        <div style="
            background-color: #28546B;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 1rem;
        ">
            <strong>{label}:</strong> No items to process
        </div>
        """, unsafe_allow_html=True)
        return
    
    rate = (found / total) * 100
    text_content = f"<strong>{label}:</strong> {rate:.0f}% ({found}/{total} found)"
    
    if rate >= success_threshold:
        st.markdown(f"""
        <div style="
            background-color: #1F4E3D;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 1rem;
        ">
            {text_content}
        </div>
        """, unsafe_allow_html=True)
    elif rate >= warning_threshold:
        st.markdown(f"""
        <div style="
            background-color: #7A5F0B;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 1rem;
        ">
            {text_content}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="
            background-color: #660022;
            padding: 0.75rem;
            border-radius: 0.5rem;
            color: #FAFAFA;
            text-align: left;
            margin-bottom: 1rem;
        ">
            {text_content}
        </div>
        """, unsafe_allow_html=True)


def create_expandable_sections(
    data_dict: Dict[str, List[Dict]], 
    section_info: Dict[str, Dict],
    item_processor: Optional[Callable] = None
) -> None:
    """
    Create expandable sections for grouped data.
    
    Args:
        data_dict: Dictionary where keys are section identifiers and values are data lists
        section_info: Dictionary containing section metadata
        item_processor: Optional function to process items before display
    """
    for section_id, items in data_dict.items():
        if not items:
            continue
            
        info = section_info.get(section_id, {})
        section_name = info.get('name', section_id)
        item_count = len(items)
        
        with st.expander(f"🔍 {section_name} ({item_count} items)"):
            if item_processor:
                processed_items = item_processor(items)
            else:
                processed_items = items
                
            df = pd.DataFrame(processed_items)
            
            # Apply standard success highlighting
            highlighting_func = get_success_highlighting_function()
            styled_df = create_styled_dataframe(df, highlighting_func)
            st.dataframe(styled_df, width='stretch')
            
            # Individual download button
            safe_name = section_name.replace(' ', '_').replace('/', '_')
            from utils.export_handlers.ui_export_manager import UIExportManager
            export_manager = UIExportManager()
            export_manager.render_download_button(
                data=df,
                label=f"📥 Download {section_name}",
                filename_prefix=f"items_{safe_name}",
                xml_filename=st.session_state.get(SessionStateKeys.XML_FILENAME),
                key=f"download_{section_id}"
            )


def add_tooltips_to_columns(df: pd.DataFrame, tooltip_map: Dict[str, str]) -> pd.DataFrame:
    """
    Add tooltips to DataFrame columns by renaming them.
    
    Args:
        df: DataFrame to modify
        tooltip_map: Dictionary mapping original column names to tooltip text
        
    Returns:
        DataFrame with renamed columns including tooltips
    """
    column_mapping = {}
    for col in df.columns:
        if col in tooltip_map:
            column_mapping[col] = f"{col} ℹ️"
            # Note: Streamlit doesn't support true tooltips in dataframes yet
            # This is a placeholder for when that feature becomes available
        else:
            column_mapping[col] = col
    
    return df.rename(columns=column_mapping)


def render_info_section(
    title: str,
    content: str,
    section_type: str = "info"
) -> None:
    """
    Render an informational section with consistent formatting.
    
    Args:
        title: Section title
        content: Section content (supports markdown)
        section_type: Type of section (info, warning, success, error)
    """
    if title and title.strip():  # Only show subheader if title is provided and not empty
        st.subheader(title)
    
    if section_type == "warning":
        st.warning(content)
    elif section_type == "success":
        st.success(content)
    elif section_type == "error":
        st.error(content)
    else:
        st.info(content)

