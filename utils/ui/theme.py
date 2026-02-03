"""
Centralised Theme Constants for ClinXML Application

This module provides canonical definitions for all colours, spacing, and styling
used throughout the ClinXML application to ensure consistency and maintainability.

Usage:
    from utils.ui.theme import ThemeColours, create_info_box_style
    
    # Using colour constants
    st.markdown(create_info_box_style(ThemeColours.BLUE, "Information message"))
    
    # Creating custom styles with theme colours
    style = create_info_box_style(ThemeColours.GREEN, "Status message")
"""

import streamlit as st


class ThemeColours:
    """Canonical colour definitions for ClinXML application"""
    
    # Streamlit Base Theme Colours (from .streamlit/config.toml)
    PRIMARY = "#4A9EFF"  # Streamlit primary button colour
    BACKGROUND = "#1E1E1E"  # Dark background
    SECONDARY_BACKGROUND = "#2D2D2D"  # Lighter dark background
    TEXT = "#FAFAFA"  # Off-white text
    
    # ClinXML Custom Colour Palette
    # Medical-grade dark theme colours chosen for accessibility and professional appearance
    BLUE = "#28546B"  # Info/neutral messages, general information
    PURPLE = "#5B2758"  # Specific categories (search dates, audit groupings)
    GREEN = "#1F4E3D"  # Success states, good performance, authenticated status  
    AMBER = "#7A5F0B"  # Warning states, moderate performance, partial success
    RED = "#660022"  # Error states, poor performance, failed operations, attention needed
    TEXT = "#FAFAFA"  # Text colour for dark backgrounds


class ThemeSpacing:
    """Spacing constants for consistent UI layout"""
    
    PADDING_STANDARD = "0.75rem"
    BORDER_RADIUS = "0.5rem"
    MARGIN_STANDARD = "0.5rem"
    MARGIN_MEDIUM = "0.75rem"
    MARGIN_EXTENDED = "1.0rem"  # For completion/result messages needing extra spacing


def _get_colour_class_name(background_colour: str) -> str:
    """Convert colour hex to a safe CSS class name"""
    return f"info-box-{background_colour.replace('#', '')}"


def _inject_info_box_css() -> str:
    """Inject CSS for all info box colour variants"""
    # Define all colour classes used in the app
    colours = {
        ThemeColours.BLUE: _get_colour_class_name(ThemeColours.BLUE),
        ThemeColours.GREEN: _get_colour_class_name(ThemeColours.GREEN),
        ThemeColours.AMBER: _get_colour_class_name(ThemeColours.AMBER),
        ThemeColours.RED: _get_colour_class_name(ThemeColours.RED),
        ThemeColours.PURPLE: _get_colour_class_name(ThemeColours.PURPLE),
    }

    css_rules = []
    for colour, class_name in colours.items():
        css_rules.append(f"""
        .{class_name} {{
            background-color: {colour} !important;
            padding: {ThemeSpacing.PADDING_STANDARD} !important;
            border-radius: {ThemeSpacing.BORDER_RADIUS} !important;
            color: {ThemeColours.TEXT} !important;
            text-align: left !important;
            margin-bottom: {ThemeSpacing.MARGIN_STANDARD} !important;
        }}
        """)

    return f"<style>{''.join(css_rules)}</style>"


def create_info_box_style(
    background_colour: str,
    text: str,
    margin_bottom: str = ThemeSpacing.MARGIN_STANDARD,
    extra_styles: str = ""
) -> str:
    """
    Create a styled info box with consistent theme formatting

    Args:
        background_colour: Background colour for the box
        text: Text content for the box
        margin_bottom: Bottom margin (default: standard margin)
        extra_styles: Additional CSS styles to append

    Returns:
        Formatted HTML string for st.markdown()

    Example:
        st.markdown(create_info_box_style(ThemeColours.BLUE, "Processing complete!"))
    """
    class_name = _get_colour_class_name(background_colour)

    # Add custom margin if different from standard
    style_attr = ""
    if margin_bottom != ThemeSpacing.MARGIN_STANDARD:
        style_attr = f' style="margin-bottom: {margin_bottom} !important;"'

    # Include CSS injection + HTML (Streamlit deduplicates identical style blocks)
    return f'{_inject_info_box_css()}<div class="{class_name}"{style_attr}>{text}</div>'


def apply_custom_styling():
    """Apply consistent custom styling across the application."""
    st.markdown("""
    <style>
    /* Custom styling for better readability */

    /* Smaller font size for sidebar text */
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] div {
        font-size: 0.9rem !important;
    }

    /* Style expander headers to match sidebar colour */
    details[data-testid="stExpander"] summary {
        background-color: #2D2D2D !important;
        color: #FAFAFA !important;
        border-radius: 4px !important;
        padding: 8px 12px !important;
    }

    details[data-testid="stExpander"] summary:hover {
        background-color: #3D3D3D !important;
    }

    /* Consistent spacing for metrics */
    .metric-container {
        background-color: #2d2d2d;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #404040;
        margin-bottom: 1rem;
    }
    .metric-spacer {
        display: block;
        height: calc(0.45rem + 2px);
        line-height: calc(0.45rem + 2px);
        font-size: 0.1rem;
    }
    .metric-top-gap {
        display: block;
        height: 0.05rem;
        line-height: 0.05rem;
        font-size: 0.05rem;
    }

    /* Table styling improvements */
    .dataframe tbody tr:hover {
        background-color: #3d3d3d;
    }

    /* Consistent button styling */
    button[kind="secondary"] {
        border-radius: 4px;
        border: 1px solid #555;
        background-color: #2d2d2d;
        color: #fafafa;
        padding: 0.5rem 1rem;
        transition: all 0.2s;
    }

    button[kind="secondary"]:hover {
        background-color: #3d3d3d;
        border-color: #4A9EFF;
    }
    </style>
    """, unsafe_allow_html=True)


class ComponentThemes:
    """Theme configurations for specific UI components"""
    
    # Status Bar Colours
    LOOKUP_TABLE_STATUS = ThemeColours.GREEN
    SCT_CODES_MEDICATIONS = ThemeColours.BLUE
    
    # Report Tab Colours  
    POPULATION_SEARCH_INFO = ThemeColours.BLUE
    SEARCH_DATE_INFO = ThemeColours.PURPLE
    COLUMN_GROUP_CRITERIA = ThemeColours.BLUE
    
    # Audit Report Colours
    RESULTS_GROUPED_BY = ThemeColours.PURPLE
    MEMBER_SEARCHES_INFO = ThemeColours.BLUE
    ORGANISATIONAL_REPORT = ThemeColours.PURPLE
    
    # Aggregate Report Colours
    STATISTICAL_SETUP_ROWS = ThemeColours.BLUE
    STATISTICAL_SETUP_COLUMNS = ThemeColours.BLUE
    STATISTICAL_SETUP_RESULT = ThemeColours.GREEN
    BUILTIN_CRITERIA_INFO = ThemeColours.PURPLE
    
    # Clinical Codes Tab Colours
    PROCESSED_ITEMS_SUMMARY = ThemeColours.GREEN
    CLINICAL_MAPPING_SUCCESS = ThemeColours.BLUE
    MEDICATIONS_MAPPING_SUCCESS = ThemeColours.PURPLE
    SECTION_INFO_TEXT = ThemeColours.BLUE
    PSEUDO_REFSET_WARNING = ThemeColours.RED
    PSEUDO_REFSETS_INFO = ThemeColours.BLUE
    WARNING_TEXT = ThemeColours.AMBER
    
    # Analytics Tab RAG Colours
    RAG_SUCCESS = ThemeColours.GREEN  # ≥90% success rate
    RAG_WARNING = ThemeColours.AMBER  # 70-89% success rate  
    RAG_ERROR = ThemeColours.RED  # <70% success rate
    RAG_INFO = ThemeColours.BLUE  # No items or neutral info
    
    # Terminology Server Colours
    CONNECTION_AUTHENTICATED = ThemeColours.GREEN
    CONNECTION_FAILED = ThemeColours.RED
    CONNECTION_NOT_AUTHENTICATED = ThemeColours.AMBER
    EXPANDABLE_CODES_SUMMARY = ThemeColours.BLUE
    EXPANSION_SUCCESS = ThemeColours.GREEN
    EXPANSION_PARTIAL = ThemeColours.AMBER
    EXPANSION_FAILED = ThemeColours.RED
    
    # Main Application Colours
    UPLOAD_PROMPT = ThemeColours.BLUE
    PROCESSING_STATUS = ThemeColours.BLUE
    DEMOGRAPHICS_INFO = ThemeColours.BLUE
    
    # Audit Report Tab Colours
    AUDIT_GROUPING_INFO = ThemeColours.PURPLE
    
    # Search Rule Visualizer Colours
    BASE_POPULATION_INFO = ThemeColours.BLUE
    
    # Report Tab Colours
    SEARCH_DATE_INFO = ThemeColours.PURPLE
    
    # Clinical Tab Colours
    MEDICATION_MAPPING_INFO = ThemeColours.PURPLE
    
    # Text Colour Reference
    TEXT = ThemeColours.TEXT


def get_success_rate_colour(success_rate: float) -> str:
    """
    Get appropriate colour for success rate display based on RAG thresholds
    
    Args:
        success_rate: Success rate as percentage (0-100)
        
    Returns:
        Appropriate theme colour for the success rate
        
    Example:
        colour = get_success_rate_colour(85.5)  # Returns AMBER colour
        st.markdown(create_info_box_style(colour, f"Success Rate: {success_rate}%"))
    """
    if success_rate >= 90:
        return ComponentThemes.RAG_SUCCESS
    elif success_rate >= 70:
        return ComponentThemes.RAG_WARNING
    elif success_rate > 0:
        return ComponentThemes.RAG_ERROR
    else:
        return ComponentThemes.RAG_INFO  # No items processed


# Convenience functions for common patterns
def info_box(text: str, margin_bottom: str = ThemeSpacing.MARGIN_STANDARD) -> str:
    """Create blue info box - most common pattern"""
    return create_info_box_style(ThemeColours.BLUE, text, margin_bottom)


def success_box(text: str, margin_bottom: str = ThemeSpacing.MARGIN_STANDARD) -> str:
    """Create green success box"""
    return create_info_box_style(ThemeColours.GREEN, text, margin_bottom)


def warning_box(text: str, margin_bottom: str = ThemeSpacing.MARGIN_STANDARD) -> str:
    """Create amber warning box"""
    return create_info_box_style(ThemeColours.AMBER, text, margin_bottom)


def error_box(text: str, margin_bottom: str = ThemeSpacing.MARGIN_STANDARD) -> str:
    """Create red error box"""
    return create_info_box_style(ThemeColours.RED, text, margin_bottom)
