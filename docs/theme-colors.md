# Custom Theme Color Reference

## Base Theme Colors (from .streamlit/config.toml)
- **Primary**: `#4A9EFF` (blue accent)
- **Background**: `#1E1E1E` (dark gray)
- **Secondary Background**: `#2D2D2D` (lighter dark gray)
- **Text**: `#FAFAFA` (off-white)
- **Font**: Roboto

## Custom Info Bar Colors

### Report Tabs (report_tabs.py)
- **Population/Parent Search Info**: `#28546B` (blue)
- **Search Date Info**: `#5B2758` (purple)
- **Text Color**: `#FAFAFA` (consistent with theme)
- **Padding**: `0.75rem`
- **Border Radius**: `0.5rem`
- **Bottom Margin**: `0.5rem`

### Status Bar (status_bar.py)
- **Lookup Table Status**: `#1F4E3D` (green)
- **SCT Codes & Medications**: `#28546B` (blue)
- **Text Color**: `#FAFAFA` (consistent with theme)
- **Styling**: Same padding and border radius as report tabs

### List Reports (list_report_tab.py)
- **Column Group Criteria**: `#28546B` (blue)

### Audit Reports (audit_report_tab.py)
- **Results Grouped By**: `#5B2758` (purple)
- **Member Searches Info**: `#28546B` (blue)
- **Simple Organizational Report**: `#5B2758` (purple)

### Aggregate Reports (aggregate_report_tab.py)
- **Statistical Setup - Rows**: `#28546B` (blue)
- **Statistical Setup - Columns**: `#28546B` (blue)
- **Statistical Setup - Result**: `#1F4E3D` (green)
- **Built-in Criteria Info**: `#5B2758` (purple)

### Clinical Codes Tab (clinical_tabs.py)
- **Processed Items Summary**: `#1F4E3D` (green)
- **Clinical Codes in Pseudo-Refsets**: RAG rated - `#1F4E3D` (green) for 0, `#660022` (wine red) for >0
- **Medications in Pseudo-Refsets**: RAG rated - `#1F4E3D` (green) for 0, `#660022` (wine red) for >0  
- **Clinical Codes Mapping Success**: `#28546B` (blue)
- **Medications Mapping Success**: `#5B2758` (purple)
- **Section Info Text (via render_section_with_data)**: `#28546B` (blue)
- **Pseudo-Refset Warning Message**: `#660022` (wine red)
- **Pseudo-Refsets Info**: `#28546B` (blue)
- **Pseudo-Refset Members Info**: `#28546B` (blue)
- **Pseudo-Refsets Usage Notes**: `#28546B` (blue)
- **Pseudo-Refset Members Usage Notes**: `#28546B` (blue)
- **Table Row Styling - All Sections (via ui_helpers.py)**:
  - **Found/Success**: `#1F4E3D` (green)
  - **Not Found/Failed**: `#660022` (wine red)
  - **Warning/Pseudo-refsets**: `#7A5F0B` (amber)

### Analytics Tab (analytics_tab.py)
- **RAG Rating System**:
  - **Success/Good Performance**: `#1F4E3D` (green)
  - **Warning/Moderate Performance**: `#7A5F0B` (amber)
  - **Error/Poor Performance**: `#660022` (wine red)
  - **Info/Neutral**: `#28546B` (blue)
- **Applied to**: File size, processing time, ValueSets count, GUID counts, duplication rates, search/report counts, quality indicators
- **Success Rate Metrics (via render_success_rate_metric)**: 
  - **≥90%**: `#1F4E3D` (green)
  - **70-89%**: `#7A5F0B` (amber)
  - **<70%**: `#660022` (wine red)
  - **No items**: `#28546B` (blue)
- **Covers**: Translation accuracy, standalone items, pseudo-refset members, overall success rates, combined clinical success

### Search Rule Visualizer (search_rule_visualizer.py)
- **Base Population Info**: `#28546B` (blue)

### Terminology Server Expansion (expansion_ui.py)
- **Connection Status - Authenticated**: `#1F4E3D` (green)
- **Connection Status - Failed**: `#660022` (wine red)
- **Connection Status - Not Authenticated**: `#7A5F0B` (amber)
- **No Expandable Codes Found**: `#28546B` (blue)
- **Expandable Codes Summary**: `#28546B` (blue)
- **Expansion Results - Success (100%)**: `#1F4E3D` (green)
- **Expansion Results - Partial Success**: `#7A5F0B` (amber)
- **Expansion Results - Failed**: `#660022` (wine red)
- **Total Child Codes Discovered**: `#28546B` (blue)
- **EMIS GUID Coverage**: `#28546B` (blue)
- **Error Messages**: `#660022` (wine red)
- **Debug Messages**: `#7A5F0B` (amber)
- **Table Row Styling - Matched/Found**: `#1F4E3D` (green)
- **Table Row Styling - Unmatched**: `#7A5F0B` (amber)
- **Table Row Styling - Error/Not Found**: `#660022` (wine red)
- **Filter Status Messages**: `#28546B` (blue)
- **Individual Lookup Success**: `#1F4E3D` (green)
- **Individual Lookup Warning**: `#7A5F0B` (amber)
- **Individual Lookup Messages**: `#28546B` (blue)
- **Bottom Margin**: `1.0rem` for completion messages, `0.5rem` for others

## Main Application (streamlit_app.py)
- **Upload Prompt**: `#28546B` (blue)
- **Processing Status**: `#28546B` (blue)
- **Demographics Info**: `#28546B` (blue)

## Shared UI Components

### UI Helpers (ui_helpers.py)
- **get_success_highlighting_function()**: Used across Clinical Codes, Medications, and Refsets tabs
  - **Found/Success rows**: `#1F4E3D` (green)
  - **Not Found/Failed rows**: `#660022` (wine red)
- **get_warning_highlighting_function()**: Used for pseudo-refsets and warning states
  - **Warning/Pseudo-refset rows**: `#7A5F0B` (amber)

## Report Tabs
### List Reports (list_report_tab.py)
- **Upload Prompt**: `#28546B` (blue)
- **No Reports Found**: `#28546B` (blue)

### Audit Reports (audit_report_tab.py)  
- **Upload Prompt**: `#28546B` (blue)
- **No Reports Found**: `#28546B` (blue)

### Aggregate Reports (aggregate_report_tab.py)
- **Upload Prompt**: `#28546B` (blue) 
- **No Reports Found**: `#28546B` (blue)

### Analysis Tabs (analysis_tabs.py)
- **Upload Prompt**: `#28546B` (blue)
- **Processing Complete**: `#28546B` (blue)
- **Analytics Ready**: `#28546B` (blue)

## Shared Report Browser Elements
### All Report Tabs (report_tabs.py, audit_report_tab.py, aggregate_report_tab.py)
- **No Reports Found**: `#28546B` (blue)
- **Upload Prompts**: `#28546B` (blue)
- **Status Info ("Showing all X reports from...")**: `#28546B` (blue)
- **Tab Usage Info**: `#28546B` (blue)
- **Rendering Complete Status**: `#1F4E3D` (green)

## Color Palette Notes
- Colors chosen from coolors.co palette that complements the dark medical theme
- All custom colors maintain good contrast with `#FAFAFA` text
- Consistent styling across all custom elements (padding, border-radius, margins)

### Complete Color Palette
- **Blue (`#28546B`)**: Info/neutral messages, general information
- **Purple (`#5B2758`)**: Specific categories (search dates, audit groupings)
- **Green (`#1F4E3D`)**: Success states, good performance, authenticated status
- **Amber (`#7A5F0B`)**: Warning states, moderate performance, partial success
- **Wine Red (`#660022`)**: Error states, poor performance, failed operations, attention needed

## Implementation Pattern
```css
background-color: [color];
padding: 0.75rem;
border-radius: 0.5rem;
color: #FAFAFA;
text-align: left;
margin-bottom: 0.5rem; /* Standard margin */
```

### Margin Variations
- **Standard Margin**: `0.5rem` (most info bars)
- **Extended Margin**: `1.0rem` (completion/result messages that need extra spacing)
  - Analytics tab RAG completion messages
  - Terminology server expansion completion messages
