"""
UI Helper Functions
Reusable functions to reduce code duplication across Streamlit UI components.
"""

import streamlit as st
import pandas as pd
import io
from datetime import datetime
from typing import List, Dict, Any, Callable, Optional


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


def render_download_button(
    data: pd.DataFrame, 
    label: str, 
    filename_prefix: str,
    xml_filename: Optional[str] = None,
    key: Optional[str] = None
) -> None:
    """
    Render a standardized CSV download button.
    
    Args:
        data: DataFrame to export
        label: Button label text
        filename_prefix: Prefix for the generated filename
        xml_filename: Optional XML filename to include in export name
        key: Optional unique key for the button
    """
    if data.empty:
        return
    
    # Create clean export version by removing emojis
    clean_data = data.copy()
    for col in clean_data.columns:
        if clean_data[col].dtype == 'object':
            # Remove all emojis and extra spaces from text columns
            clean_data[col] = clean_data[col].astype(str).str.replace(r'[🔍📝⚕️📊📋📈📄🏥💊⬇️✅❌🔄📥📈📋]+ ', '', regex=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if xml_filename and xml_filename.strip():
        # Clean filename for filesystem compatibility
        clean_xml_filename = xml_filename.replace(' ', '_').replace('.xml', '')
        filename = f"{filename_prefix}_{clean_xml_filename}_{timestamp}.csv"
    else:
        filename = f"{filename_prefix}_{timestamp}.csv"
    
    csv_buffer = io.StringIO()
    clean_data.to_csv(csv_buffer, index=False)
    
    st.download_button(
        label=label,
        data=csv_buffer.getvalue(),
        file_name=filename,
        mime="text/csv",
        key=key
    )


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
            return ['background-color: #2d5a3d; color: #e8f5e8'] * len(row)  # Dark green with light text
        else:
            return ['background-color: #5a2d2d; color: #f5e8e8'] * len(row)  # Dark red with light text
    
    return highlight_success


def get_warning_highlighting_function():
    """
    Get a function for highlighting rows with warning colors.
    
    Returns:
        Function for styling DataFrame rows with warning colors
    """
    def highlight_warning(row):
        return ['background-color: #5a4d2d; color: #f5f3e8'] * len(row)  # Dark yellow/orange with light text
    
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
        st.info(info_text)
    
    if data:
        # Get current modes for cache key
        current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
        show_debug = st.session_state.get('debug_mode', False)
        
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
        show_debug = st.session_state.get('debug_mode', False)
        
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
        current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
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
        if 'EMIS GUID' in display_df.columns:
            display_df['EMIS GUID'] = '🔍 ' + display_df['EMIS GUID'].astype(str)
        if 'SNOMED Code' in display_df.columns:
            display_df['SNOMED Code'] = '⚕️ ' + display_df['SNOMED Code'].astype(str)
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
        
        # Export filtering options and download button
        if 'Mapping Found' in df.columns:
            col1, col2 = st.columns([1, 2])
            
            with col1:
                # Check if we have source tracking to offer source-based filtering
                # In unique_codes mode, source columns are filtered out but we should still offer source-based exports
                current_mode = st.session_state.get('current_deduplication_mode', 'unique_codes')
                has_source_tracking = 'Source Type' in df.columns and 'Source Name' in df.columns
                
                # Always show source-based export options if we have Source columns or Source GUID in the data
                # The data now always includes source tracking, even if hidden in unique_codes mode
                data_has_source_tracking = 'Source GUID' in df.columns or has_source_tracking
                
                if data_has_source_tracking:
                    export_filter = st.radio(
                        "Export Filter:",
                        ["All Codes", "Only Matched", "Only Unmatched", "Only Codes from Searches", "Only Codes from Reports"],
                        key=f"export_filter_{filename_prefix}",
                        horizontal=False
                    )
                else:
                    export_filter = st.radio(
                        "Export Filter:",
                        ["All Codes", "Only Matched", "Only Unmatched"],
                        key=f"export_filter_{filename_prefix}",
                        horizontal=True
                    )
            
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
                xml_filename = st.session_state.get('xml_filename')
                render_download_button(
                    data=filtered_df,
                    label=export_label,
                    filename_prefix=filename_prefix + export_suffix,
                    xml_filename=xml_filename,
                    key=f"download_{filename_prefix}_{export_filter.lower().replace(' ', '_')}"
                )
        else:
            # No Mapping Found column, render normal download button (use cleaned data)
            xml_filename = st.session_state.get('xml_filename')
            render_download_button(
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
        st.info(f"**{label}:** No items to process")
        return
    
    rate = (found / total) * 100
    text = f"**{label}:** {rate:.0f}% ({found}/{total} found)"
    
    if rate >= success_threshold:
        st.success(text)
    elif rate >= warning_threshold:
        st.warning(text)
    else:
        st.error(text)


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
            render_download_button(
                data=df,
                label=f"📥 Download {section_name}",
                filename_prefix=f"items_{safe_name}",
                xml_filename=st.session_state.get('xml_filename'),
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