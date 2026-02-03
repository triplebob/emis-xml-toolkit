# ClinXML Theme System Documentation

## Overview

ClinXML uses a centralised theme management system located in `utils/ui/theme.py` that provides consistent colours, spacing, and styling across the entire application. This replaces previous hardcoded colour values with maintainable theme constants and utility functions.

## Core Theme Manager

### Location
```python
from utils.ui.theme import ThemeColours, ComponentThemes, create_info_box_style
```

### Base Colour Palette

All colours are defined in the `ThemeColours` class:

```python
class ThemeColours:
 # Streamlit Base Theme (from .streamlit/config.toml)
 PRIMARY = "#4A9EFF" # Streamlit primary button colour
 BACKGROUND = "#1E1E1E" # Dark background
 SECONDARY_BACKGROUND = "#2D2D2D" # Lighter dark background
 TEXT = "#FAFAFA" # Off-white text
 
 # ClinXML Medical-Grade Colour Palette
 BLUE = "#28546B" # Info/neutral messages, general information
 PURPLE = "#5B2758" # Specific categories (search dates, audit groupings)
 GREEN = "#1F4E3D" # Success states, good performance, authenticated status
 AMBER = "#7A5F0B" # Warning states, moderate performance, partial success
 RED = "#660022" # Error states, poor performance, failed operations
```

### Spacing Constants

Consistent spacing is managed through `ThemeSpacing`:

```python
class ThemeSpacing:
 PADDING_STANDARD = "0.75rem"
 BORDER_RADIUS = "0.5rem"
 MARGIN_STANDARD = "0.5rem"
 MARGIN_EXTENDED = "1.0rem" # For completion/result messages
```

## Usage Patterns

### 1. Simple Info Boxes

```python
# Using convenience functions
st.markdown(info_box("General information message"))
st.markdown(success_box("Operation completed successfully"))
st.markdown(warning_box("Please check this setting"))
st.markdown(error_box("Something went wrong"))
```

### 2. Custom Styling

```python
# Using the flexible create_info_box_style function
st.markdown(create_info_box_style(
 ComponentThemes.LOOKUP_TABLE_STATUS, 
 "Lookup table loaded successfully"
))

# With custom margin
st.markdown(create_info_box_style(
 ThemeColours.BLUE, 
 "Processing complete",
 margin_bottom=ThemeSpacing.MARGIN_EXTENDED
))
```

### 3. Success Rate Colouring

```python
# Automatic RAG colouring based on percentage
colour = get_success_rate_colour(85.5) # Returns appropriate colour
st.markdown(create_info_box_style(colour, f"Success Rate: {success_rate}%"))
```

## Component-Specific Themes

The `ComponentThemes` class provides semantic colour mappings for specific UI components:

### Status Bar
```python
ComponentThemes.LOOKUP_TABLE_STATUS # Green - successful lookup table load
ComponentThemes.SCT_CODES_MEDICATIONS # Blue - codes and medications info
```

### Report Tabs
```python
ComponentThemes.POPULATION_SEARCH_INFO # Blue - population/parent search info
ComponentThemes.SEARCH_DATE_INFO # Purple - search date information
ComponentThemes.COLUMN_GROUP_CRITERIA # Blue - list report criteria
```

### Clinical Codes Tab
```python
ComponentThemes.PROCESSED_ITEMS_SUMMARY # Green - processing success summary
ComponentThemes.CLINICAL_MAPPING_SUCCESS # Blue - clinical codes mapping
ComponentThemes.MEDICATIONS_MAPPING_SUCCESS # Purple - medications mapping
ComponentThemes.PSEUDO_REFSET_WARNING # Red - pseudo-refset warnings
```

### Analytics Tab (RAG System)
```python
ComponentThemes.RAG_SUCCESS # Green - ≥90% success rate
ComponentThemes.RAG_WARNING # Amber - 70-89% success rate
ComponentThemes.RAG_ERROR # Red - <70% success rate
ComponentThemes.RAG_INFO # Blue - No items or neutral info
```

### Terminology Server
```python
ComponentThemes.CONNECTION_AUTHENTICATED # Green - successful authentication
ComponentThemes.CONNECTION_FAILED # Red - connection failure
ComponentThemes.CONNECTION_NOT_AUTHENTICATED # Amber - not authenticated
ComponentThemes.EXPANSION_SUCCESS # Green - 100% expansion success
ComponentThemes.EXPANSION_PARTIAL # Amber - partial expansion
ComponentThemes.EXPANSION_FAILED # Red - expansion failure
```

## Migration Complete

All UI components now use the centralized theme system. The recommended patterns are:

1. **Use convenience functions for common cases**:
 ```python
 st.markdown(info_box("General information"))
 st.markdown(success_box("Operation successful"))
 st.markdown(warning_box("Please check this"))
 st.markdown(error_box("Something went wrong"))
 ```

2. **Use semantic component themes for specific UI areas**:
 ```python
 st.markdown(create_info_box_style(ComponentThemes.RAG_SUCCESS, "Success"))
 st.markdown(create_info_box_style(ComponentThemes.LOOKUP_TABLE_STATUS, "Ready"))
 ```

3. **Use utility functions for special cases**:
 ```python
 # For RAG style messages when you already have a colour
 st.markdown(create_info_box_style(ThemeColours.AMBER, "️ Check configuration"))
 ```

## Colour & Medical Context

The ClinXML colour palette is specifically chosen for medical/clinical applications:

- **Blue (#28546B)**: Used for informational content
- **Green (#1F4E3D)**: Success, positive outcomes - used for successful operations
- **Amber (#7A5F0B)**: Caution, attention needed - used for warnings and partial success
- **Red (#660022)**: Critical issues, errors - used for failures and important alerts
- **Purple (#5B2758)**: Categorisation, specificity - used for categorical information

All colours maintain excellent contrast with the `#FAFAFA` text colour on dark backgrounds, ensuring accessibility compliance.

## Future Enhancements

The centralised theme system enables:
- Easy colour scheme updates across the entire application
- Accessibility improvements (high contrast modes)
- User customisation options
- Consistent component styling
- Simplified maintenance and updates
