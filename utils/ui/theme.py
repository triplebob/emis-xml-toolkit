"""
Centralized Theme Constants for ClinXML Application

This module provides canonical definitions for all colors, spacing, and styling
used throughout the ClinXML application to ensure consistency and maintainability.

Usage:
    from utils.ui.theme import ThemeColors, create_info_box_style
    
    # Using color constants
    st.markdown(create_info_box_style(ThemeColors.BLUE, "Information message"))
    
    # Creating custom styles with theme colors
    style = f"background-color: {ThemeColors.GREEN}; color: {ThemeColors.TEXT};"
"""

from typing import Literal


class ThemeColors:
    """Canonical color definitions for ClinXML application"""
    
    # Streamlit Base Theme Colors (from .streamlit/config.toml)
    PRIMARY = "#4A9EFF"  # Streamlit primary button color
    BACKGROUND = "#1E1E1E"  # Dark background
    SECONDARY_BACKGROUND = "#2D2D2D"  # Lighter dark background
    TEXT = "#FAFAFA"  # Off-white text
    
    # ClinXML Custom Color Palette
    # Medical-grade dark theme colors chosen for accessibility and professional appearance
    BLUE = "#28546B"  # Info/neutral messages, general information
    PURPLE = "#5B2758"  # Specific categories (search dates, audit groupings)
    GREEN = "#1F4E3D"  # Success states, good performance, authenticated status  
    AMBER = "#7A5F0B"  # Warning states, moderate performance, partial success
    RED = "#660022"  # Error states, poor performance, failed operations, attention needed
    TEXT = "#FAFAFA"  # Text color for dark backgrounds


class ThemeSpacing:
    """Spacing constants for consistent UI layout"""
    
    PADDING_STANDARD = "0.75rem"
    BORDER_RADIUS = "0.5rem"
    MARGIN_STANDARD = "0.5rem"
    MARGIN_EXTENDED = "1.0rem"  # For completion/result messages needing extra spacing


class ThemeStyles:
    """Pre-built style patterns for common UI components"""
    
    @staticmethod
    def base_info_box() -> dict:
        """Base style properties for info boxes"""
        return {
            'padding': ThemeSpacing.PADDING_STANDARD,
            'border_radius': ThemeSpacing.BORDER_RADIUS,
            'color': ThemeColors.TEXT,
            'text_align': 'left',
            'margin_bottom': ThemeSpacing.MARGIN_STANDARD
        }


def create_info_box_style(
    background_color: str, 
    text: str,
    margin_bottom: str = ThemeSpacing.MARGIN_STANDARD,
    extra_styles: str = ""
) -> str:
    """
    Create a styled info box with consistent theme formatting
    
    Args:
        background_color: Background color for the box
        text: Text content for the box
        margin_bottom: Bottom margin (default: standard margin)
        extra_styles: Additional CSS styles to append
        
    Returns:
        Formatted HTML string for st.markdown()
        
    Example:
        st.markdown(create_info_box_style(ThemeColors.BLUE, "Processing complete!"))
    """
    base_style = f"""
        background-color: {background_color};
        padding: {ThemeSpacing.PADDING_STANDARD};
        border-radius: {ThemeSpacing.BORDER_RADIUS};
        color: {ThemeColors.TEXT};
        text-align: left;
        margin-bottom: {margin_bottom};
        {extra_styles}
    """
    
    return f"""
    <div style="{base_style.strip()}">
        {text}
    </div>
    """


def create_rag_status_style(
    status: Literal['success', 'warning', 'error', 'info'],
    text: str,
    margin_bottom: str = ThemeSpacing.MARGIN_STANDARD
) -> str:
    """
    Create RAG (Red/Amber/Green) status box with appropriate color
    
    Args:
        status: Status type determining color
        text: Text content for the status box
        margin_bottom: Bottom margin (default: standard margin)
        
    Returns:
        Formatted HTML string for st.markdown()
        
    Example:
        st.markdown(create_rag_status_style('success', "✅ All items processed successfully"))
    """
    color_map = {
        'success': ThemeColors.GREEN,
        'warning': ThemeColors.AMBER, 
        'error': ThemeColors.RED,
        'info': ThemeColors.BLUE
    }
    
    return create_info_box_style(color_map[status], text, margin_bottom)


def create_table_row_style(row_type: Literal['found', 'not_found', 'warning']) -> str:
    """
    Create table row styling for success/warning/error highlighting
    
    Args:
        row_type: Type of row determining background color
        
    Returns:
        CSS background-color style string
        
    Example:
        # In dataframe styling functions
        def highlight_success(val):
            return create_table_row_style('found') if val == 'Found' else ''
    """
    color_map = {
        'found': ThemeColors.GREEN,
        'not_found': ThemeColors.RED,
        'warning': ThemeColors.AMBER
    }
    
    return f"background-color: {color_map[row_type]}"


class ComponentThemes:
    """Theme configurations for specific UI components"""
    
    # Status Bar Colors
    LOOKUP_TABLE_STATUS = ThemeColors.GREEN
    SCT_CODES_MEDICATIONS = ThemeColors.BLUE
    
    # Report Tab Colors  
    POPULATION_SEARCH_INFO = ThemeColors.BLUE
    SEARCH_DATE_INFO = ThemeColors.PURPLE
    COLUMN_GROUP_CRITERIA = ThemeColors.BLUE
    
    # Audit Report Colors
    RESULTS_GROUPED_BY = ThemeColors.PURPLE
    MEMBER_SEARCHES_INFO = ThemeColors.BLUE
    ORGANIZATIONAL_REPORT = ThemeColors.PURPLE
    
    # Aggregate Report Colors
    STATISTICAL_SETUP_ROWS = ThemeColors.BLUE
    STATISTICAL_SETUP_COLUMNS = ThemeColors.BLUE
    STATISTICAL_SETUP_RESULT = ThemeColors.GREEN
    BUILTIN_CRITERIA_INFO = ThemeColors.PURPLE
    
    # Clinical Codes Tab Colors
    PROCESSED_ITEMS_SUMMARY = ThemeColors.GREEN
    CLINICAL_MAPPING_SUCCESS = ThemeColors.BLUE
    MEDICATIONS_MAPPING_SUCCESS = ThemeColors.PURPLE
    SECTION_INFO_TEXT = ThemeColors.BLUE
    PSEUDO_REFSET_WARNING = ThemeColors.RED
    PSEUDO_REFSETS_INFO = ThemeColors.BLUE
    WARNING_TEXT = ThemeColors.AMBER
    
    # Analytics Tab RAG Colors
    RAG_SUCCESS = ThemeColors.GREEN  # ≥90% success rate
    RAG_WARNING = ThemeColors.AMBER  # 70-89% success rate  
    RAG_ERROR = ThemeColors.RED  # <70% success rate
    RAG_INFO = ThemeColors.BLUE  # No items or neutral info
    
    # Terminology Server Colors
    CONNECTION_AUTHENTICATED = ThemeColors.GREEN
    CONNECTION_FAILED = ThemeColors.RED
    CONNECTION_NOT_AUTHENTICATED = ThemeColors.AMBER
    EXPANDABLE_CODES_SUMMARY = ThemeColors.BLUE
    EXPANSION_SUCCESS = ThemeColors.GREEN
    EXPANSION_PARTIAL = ThemeColors.AMBER
    EXPANSION_FAILED = ThemeColors.RED
    
    # Main Application Colors
    UPLOAD_PROMPT = ThemeColors.BLUE
    PROCESSING_STATUS = ThemeColors.BLUE
    DEMOGRAPHICS_INFO = ThemeColors.BLUE
    
    # Audit Report Tab Colors
    AUDIT_GROUPING_INFO = ThemeColors.PURPLE
    
    # Search Rule Visualizer Colors
    BASE_POPULATION_INFO = ThemeColors.BLUE
    
    # Report Tab Colors
    SEARCH_DATE_INFO = ThemeColors.PURPLE
    
    # Clinical Tab Colors
    MEDICATION_MAPPING_INFO = ThemeColors.PURPLE
    
    # Text Color Reference
    TEXT = ThemeColors.TEXT


def get_success_rate_color(success_rate: float) -> str:
    """
    Get appropriate color for success rate display based on RAG thresholds
    
    Args:
        success_rate: Success rate as percentage (0-100)
        
    Returns:
        Appropriate theme color for the success rate
        
    Example:
        color = get_success_rate_color(85.5)  # Returns AMBER color
        st.markdown(create_info_box_style(color, f"Success Rate: {success_rate}%"))
    """
    if success_rate >= 90:
        return ComponentThemes.RAG_SUCCESS
    elif success_rate >= 70:
        return ComponentThemes.RAG_WARNING
    elif success_rate > 0:
        return ComponentThemes.RAG_ERROR
    else:
        return ComponentThemes.RAG_INFO  # No items processed


def create_completion_message_style(
    status: Literal['success', 'warning', 'error', 'info'],
    text: str
) -> str:
    """
    Create completion message with extended margin for better spacing
    
    Args:
        status: Status determining color
        text: Completion message text
        
    Returns:
        Formatted HTML string with extended margin
        
    Example:
        st.markdown(create_completion_message_style('success', "Processing completed successfully!"))
    """
    return create_rag_status_style(status, text, ThemeSpacing.MARGIN_EXTENDED)


# Convenience functions for common patterns
def info_box(text: str, margin_bottom: str = ThemeSpacing.MARGIN_STANDARD) -> str:
    """Create blue info box - most common pattern"""
    return create_info_box_style(ThemeColors.BLUE, text, margin_bottom)


def success_box(text: str, margin_bottom: str = ThemeSpacing.MARGIN_STANDARD) -> str:
    """Create green success box"""
    return create_info_box_style(ThemeColors.GREEN, text, margin_bottom)


def warning_box(text: str, margin_bottom: str = ThemeSpacing.MARGIN_STANDARD) -> str:
    """Create amber warning box"""
    return create_info_box_style(ThemeColors.AMBER, text, margin_bottom)


def error_box(text: str, margin_bottom: str = ThemeSpacing.MARGIN_STANDARD) -> str:
    """Create red error box"""
    return create_info_box_style(ThemeColors.RED, text, margin_bottom)


def purple_box(text: str, margin_bottom: str = ThemeSpacing.MARGIN_STANDARD) -> str:
    """Create purple category box"""
    return create_info_box_style(ThemeColors.PURPLE, text, margin_bottom)


