# Session State Management Architecture

## Overview
ClinXML implements a centralised session state management system to ensure consistent, reliable, and maintainable handling of application state across all components.

## Core Components

### SessionStateKeys Class
**Location**: `utils/core/session_state.py`

Provides centralised constants for all session state keys, eliminating hardcoded strings and reducing typos.

```python
from utils.core.session_state import SessionStateKeys

# Instead of: st.session_state['xml_content']
# Use: st.session_state[SessionStateKeys.XML_CONTENT]
```

### Key Categories

#### Core Data Keys
- `XML_CONTENT` - Uploaded XML file content
- `XML_FILENAME` - Original filename 
- `UPLOADED_FILENAME` - User-provided filename
- `LAST_PROCESSED_FILE` - Previously processed file reference

#### Results Data Keys
- `RESULTS` - Main processing results
- `SEARCH_RESULTS` - Search analysis results
- `REPORT_RESULTS` - Report analysis results
- `XML_STRUCTURE_ANALYSIS` - Structural analysis data
- `EMIS_GUIDS` - Extracted EMIS GUID data
- `AUDIT_STATS` - Processing audit statistics

#### Lookup Data Keys
- `LOOKUP_DF` - Main lookup DataFrame
- `LOOKUP` - Lookup dictionary cache
- `EMIS_GUID_COL` - EMIS GUID column name
- `SNOMED_CODE_COL` - SNOMED code column name
- `LOOKUP_VERSION_INFO` - Lookup table version metadata
- `LOOKUP_PERFORMANCE` - Lookup performance metrics
- `MATCHED_EMIS_SNOMED_CACHE` - Persistent EMIS GUID → SNOMED mappings (60-minute TTL)
- `MATCHED_EMIS_SNOMED_TIMESTAMP` - Cache timestamp for TTL validation

#### User Preference Keys
- `CURRENT_DEDUPLICATION_MODE` - Data deduplication setting
- `DEBUG_MODE` - Debug mode toggle
- `CHILD_VIEW_MODE` - NHS terminology child view mode
- `CLINICAL_INCLUDE_REPORT_CODES` - Include report codes in exports
- `CLINICAL_SHOW_CODE_SOURCES` - Show code source information

#### Processing State Keys
- `IS_PROCESSING` - Processing status flag
- `PROCESSING_CONTEXT` - Current processing context
- Dynamic placeholders for progress tracking

#### Dynamic Key Patterns
- `CACHE_KEY_PREFIX` - General cache prefix
- `EXCEL_CACHE_PREFIX` - Excel export cache
- `JSON_CACHE_PREFIX` - JSON export cache
- `TREE_TEXT_PREFIX` - Tree visualisation cache
- `NHS_TERMINOLOGY_CACHE_PREFIX` - NHS API cache

## SessionStateGroups Class

Organises keys into logical groups for bulk operations:

### Available Groups
- **CORE_DATA** - Essential application data
- **PROCESSING_STATE** - Processing and rendering state
- **RESULTS_DATA** - Analysis and processing results
- **LOOKUP_DATA** - Lookup table and translation data
- **USER_PREFERENCES** - User settings and preferences
- **NHS_TERMINOLOGY** - NHS Terminology Server state
- **SYSTEM_MONITORING** - System performance and error tracking

## State Management Functions

### Clearing Functions
```python
# Clear specific state categories
clear_processing_state()   # Clear processing flags and state
clear_results_state()      # Clear analysis results and data
clear_export_state()       # Clear export cache with full GC
clear_ui_state()           # Clear UI cache (preserves preferences)
clear_report_state()       # Clear specific report type state
clear_analysis_state()     # Clear visualisation and analysis cache
clear_cache_state()        # Clear general cache keys

# XML upload clearing strategies
clear_for_new_xml_selection()  # Lightweight: clears results, preserves caches (no UI reload)
clear_for_new_xml()            # Comprehensive: includes export cache + GC, preserves lookup cache
```

### Validation and Debugging
```python
# Validate session state
is_valid, issues = validate_state_keys()

# Get debug information
debug_info = get_state_debug_info()

# Display debug interface (when debug mode enabled)
debug_session_state()
```

### State Inspection
```python
# Get comprehensive state summary
summary = get_session_state_summary()

# Check state validation
validation_result = validate_session_state()
```

### SNOMED Cache Management
```python
# Get cached EMIS GUID → SNOMED mappings (60-minute TTL)
cached_mappings = get_cached_snomed_mappings()

# Update cache with new mappings
new_mappings = {'emis_guid_123': '12345678'}
update_snomed_cache(new_mappings)

# Check if cache is still valid
is_valid = is_snomed_cache_valid()

# Clear expired cache
was_cleared = clear_expired_snomed_cache()

# Get TTL configuration
ttl_minutes = get_snomed_cache_ttl_minutes()  # Returns 60
```

## Usage Patterns

### Standard Key Access
```python
# Import the keys
from utils.core.session_state import SessionStateKeys

# Reading state
xml_content = st.session_state.get(SessionStateKeys.XML_CONTENT)
debug_mode = st.session_state.get(SessionStateKeys.DEBUG_MODE, False)

# Writing state
st.session_state[SessionStateKeys.RESULTS] = processing_results
st.session_state[SessionStateKeys.IS_PROCESSING] = True
```

### State Clearing in Workflows
```python
from utils.core.session_state import clear_for_new_xml_selection, clear_for_new_xml

def handle_xml_file_selection():
    # Lightweight cleanup when user selects new XML file
    clear_for_new_xml_selection()
    
    # Clears previous results only - no UI reload
    # Status bar stays loaded, lookup cache preserved
    # Fast, non-disruptive user experience

def handle_xml_processing_start():
    # Comprehensive cleanup when processing begins
    clear_for_new_xml()
    
    # Clears export cache with GC, analysis cache
    # SNOMED lookup cache (LOOKUP_DF) remains intact for performance
    # User preferences (debug_mode, etc.) remain intact for UX

def handle_cancel_processing():
    # Same comprehensive cleanup when user cancels processing
    clear_for_new_xml()
    
    # Ensures clean state and prevents partial results
    # Preserves expensive SNOMED lookup cache
    # Maintains user preferences across sessions
```

### Debug Mode Integration
```python
from utils.core.session_state import SessionStateKeys, debug_session_state

# Show debug info when enabled
if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
    debug_session_state()
```

## Export Cache Management and Garbage Collection

### Export Cleanup Process
When `clear_export_state()` is called (including via `clear_for_new_xml()`), the system performs comprehensive cleanup:

```python
def clear_export_state() -> None:
    # 1. Clear session state export keys
    - Excel cache keys (excel_export_*)
    - JSON cache keys (json_export_*)  
    - Generic export keys (export_*)
    
    # 2. Clear unified export cache via CacheManager
    - TXT file exports
    - CSV file exports
    - XLSX file exports
    - JSON file exports
    - Export ready flags (_ready)
    
    # 3. Clear Streamlit internal caches
    st.cache_data.clear()
    
    # 4. Force Python garbage collection
    import gc
    gc.collect()
```

### Memory Management Strategy
- **Immediate cleanup**: Export objects cleared from session state
- **Streamlit cache clearing**: Internal Streamlit caches cleared
- **Forced GC**: Python garbage collection ensures memory is freed
- **Preserved data**: SNOMED lookup cache remains intact for performance

### Export Types Handled
- **Text exports** (.txt): Rule exports, code lists
- **CSV exports** (.csv): Clinical codes, medications, refsets
- **Excel exports** (.xlsx): Comprehensive data with multiple sheets
- **JSON exports** (.json): Structured data for API integration

## Comprehensive XML Upload Cleanup

### `clear_for_new_xml()` Function
This function provides complete state reset while preserving valuable cached data:

#### What Gets Cleared:
```python
# Processing and Results Data
- RESULTS, SEARCH_RESULTS, REPORT_RESULTS
- XML_STRUCTURE_ANALYSIS, SEARCH_ANALYSIS
- EMIS_GUIDS, AUDIT_STATS

# All Export Cache (with full GC)
- TXT, CSV, XLSX, JSON file exports
- Export ready flags and cache keys
- Streamlit internal caches
- Forced Python garbage collection

# UI and Rendering State  
- cached_selected_report_* keys
- *_rendering and *_rendering_updated keys
- selected_*_text dynamic keys

# Analysis and Visualisation Cache
- tree_text_*, tree_json_* visualisation cache
- dep_tree_text_* dependency trees
- cache_* general cache keys
- *_processing, *_translation cache
```

#### What Gets Preserved:
```python
# SNOMED Lookup Cache (Critical for Performance)
- LOOKUP_DF: Main SNOMED lookup DataFrame
- LOOKUP: Lookup dictionary cache
- EMIS_GUID_COL, SNOMED_CODE_COL: Column mappings
- LOOKUP_VERSION_INFO, LOOKUP_PERFORMANCE
- MATCHED_EMIS_SNOMED_CACHE: Persistent EMIS GUID → SNOMED mappings (60-minute TTL)
- MATCHED_EMIS_SNOMED_TIMESTAMP: Cache timestamp for expiration validation

# User Preferences (Critical for UX)
- DEBUG_MODE: Debug toggle
- CURRENT_DEDUPLICATION_MODE: Display preferences
- CHILD_VIEW_MODE: NHS terminology preferences
- CLINICAL_INCLUDE_REPORT_CODES, CLINICAL_SHOW_CODE_SOURCES

# NHS Terminology Cache (Performance)
- nhs_term_cache_* API response cache

# System State
- SESSION_ID: Session identification
```

### Memory Efficiency Benefits
- **Large file support**: Prevents memory accumulation across XML uploads
- **Export cleanup**: Ensures large Excel/JSON exports don't persist in memory
- **Cache preservation**: Avoids expensive SNOMED lookup recomputation
- **User experience**: Maintains preferences and settings across sessions
- **Cancel safety**: Prevents partial/corrupted data when processing is cancelled
- **Consistent state**: Same cleanup behaviour for upload and cancel operations
- **SNOMED cache optimisation**: 60-minute persistent cache reduces lookup table queries across multiple XML files

## SNOMED Persistent Cache Architecture

### Overview
ClinXML implements a 60-minute persistent cache for EMIS GUID → SNOMED code mappings to optimise performance across multiple XML file processing sessions. This cache significantly reduces lookup table queries and improves translation speed.

### Cache Management
- **Storage**: Session state keys `MATCHED_EMIS_SNOMED_CACHE` and `MATCHED_EMIS_SNOMED_TIMESTAMP`
- **TTL**: 60-minute time-to-live with automatic expiration
- **Validation**: Timestamp-based cache validity checking
- **Integration**: Seamless integration with translator workflow

### Cache Lifecycle
```python
# 1. Cache Initialisation (first XML upload)
clear_expired_snomed_cache()  # Clean any expired cache
cached_mappings = get_cached_snomed_mappings()  # Returns {} if empty/expired

# 2. Translation Enhancement
guid_to_snomed_dict.update(cached_mappings)  # Enhance lookup with cache

# 3. Cache Updates (after successful translation)
new_mappings = {'emis_guid_123': '12345678'}  # New mappings discovered
update_snomed_cache(new_mappings)  # Add to persistent cache

# 4. Subsequent XML Files (within 60 minutes)
cached_mappings = get_cached_snomed_mappings()  # Reuse existing mappings
# Performance benefit: Skip lookup table queries for known mappings

# 5. Cache Expiration (after 60 minutes)
clear_expired_snomed_cache()  # Automatic cleanup of expired cache
```

### Performance Benefits
- **Reduced Queries**: Cached mappings bypass expensive lookup table searches
- **Faster Translation**: Subsequent XML files with overlapping codes translate faster
- **Memory Efficient**: Cache preserved across session state clearing operations
- **User Experience**: Consistent performance across multiple file uploads

### Cache Preservation Strategy
The SNOMED cache is preserved during all session state clearing operations:

- **File Selection**: `clear_for_new_xml_selection()` preserves cache (lightweight cleanup)
- **Process XML**: `clear_for_new_xml()` preserves cache (comprehensive cleanup)
- **Cancel Processing**: `clear_for_new_xml()` preserves cache (same as process)

This ensures that users benefit from cached mappings across their entire session, regardless of workflow interruptions.

### Debug Mode Integration
When `DEBUG_MODE` is enabled, comprehensive cache logging provides insights:
```
[SNOMED CACHE] Age: 15.3min, TTL: 60min, Valid: True
[SNOMED CACHE] Retrieved 245 cached mappings
[SNOMED CACHE] Updated with 23 new mappings, total: 268
[SNOMED CACHE] Expired cache cleared
```

### Implementation Details
- **Zero Overhead**: Cache functions return early when debug mode is disabled
- **Atomic Updates**: Cache updates are transactional (all or nothing)
- **Type Safety**: Full type hints and comprehensive error handling
- **Thread Safety**: Session state provides natural thread isolation

## Benefits

### Development Benefits
- **Type Safety**: IntelliSense support for key names
- **Consistency**: Standardised key naming patterns
- **Maintainability**: Single source of truth for all keys
- **Debugging**: Comprehensive debug and validation utilities

### Runtime Benefits
- **Reliability**: Eliminates KeyError exceptions from typos
- **Memory Efficiency**: Multi-level cleanup prevents memory leaks
- **Performance**: Efficient bulk operations with selective preservation
- **State Hygiene**: Logical grouping enables targeted cleanup
- **Export Management**: Comprehensive export cache cleanup with forced GC
- **SNOMED Cache Performance**: 60-minute persistent cache reduces lookup queries and improves translation speed

### User Benefits
- **Stability**: Fewer crashes from state-related errors
- **Performance**: Better memory management with preserved lookup cache
- **Consistency**: Predictable behaviour with preserved user preferences
- **Efficiency**: Fast subsequent operations due to cached SNOMED lookups

## State Lifecycle

### Application Startup
1. Initialise session ID and core preferences
2. Load lookup data if available
3. Set up default user preferences

### XML Upload/Processing
1. **XML File Selection**: Lightweight cleanup: `clear_for_new_xml_selection()`
   - Clears previous XML results and UI state only
   - **Preserves SNOMED lookup cache** (keeps status bar loaded)
   - **Preserves export cache** (no UI reload required)
   - Fast, non-disruptive cleanup
2. **Process XML Button**: Comprehensive cleanup: `clear_for_new_xml()`
   - Clears all export cache (txt, csv, xlsx, json) with forced GC
   - Clears analysis and visualisation cache
   - **Still preserves SNOMED lookup cache** for performance
   - **Still preserves user preferences** for consistency
3. **Cancel Processing**: Same comprehensive cleanup: `clear_for_new_xml()`
   - Ensures clean state when user cancels mid-processing
   - Prevents partial or corrupted processing results
   - Same preservation of lookup cache and preferences
4. Process new XML and populate results
5. Update audit statistics

### Tab Navigation
1. Clear UI-specific cache: `clear_ui_state()`
2. Preserve core data and user preferences
3. Load tab-specific cached data if available

### Session Cleanup
1. Clear processing state
2. Preserve user preferences for next session
3. Clean up export cache to prevent memory bloat

## Error Handling

### State Validation
The system includes comprehensive validation to detect:
- Unknown/misspelled session state keys
- Missing critical keys
- Orphaned cache keys
- State inconsistencies

### Debug Mode
When `DEBUG_MODE` is enabled, comprehensive logging and validation occurs:

#### Debug Output Examples:
```
[EXPORT CLEAR] Cleared 15 export cache entries and performed GC
[NEW XML] Cleared all data except 8 preserved keys (lookup cache + preferences)
[DEBUG] Session state modified: xml_content
```

#### Debug Interface Features:
- **State validation**: Automatic validation with issue reporting
- **State summary**: Categorised overview of all session keys
- **Unknown key detection**: Highlights potential typos or orphaned keys
- **Memory monitoring**: Track state size and performance impact
- **Change logging**: Real-time logging of state modifications

#### Zero Overhead When Disabled:
```python
def debug_session_state() -> None:
    # Early return if debug mode is not enabled - prevents any computation
    if not st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        return
    # Only compute debug information when debug mode is active
```

This ensures production performance is unaffected by debug capabilities.

### Recovery Mechanisms
- Graceful handling of missing keys with defaults
- Automatic cleanup of orphaned cache entries
- State reset capabilities for error recovery

## Testing

### Unit Tests
**Location**: `tests/test_session_state.py`

Comprehensive test coverage includes:
- Session state key validation
- Clearing utility functions
- State categorisation
- Integration scenarios
- Error handling

### Integration Testing
- Tab switching workflows
- XML upload/processing cycles
- Export operation state management
- Error recovery scenarios

## Best Practices

### Key Usage
1. Always import `SessionStateKeys` rather than using string literals
2. Use appropriate defaults with `.get()` for optional keys
3. Group related operations using `SessionStateGroups`
4. Clear state appropriately for workflow transitions

### State Management
1. Use clearing utilities rather than manual deletion
2. Preserve user preferences across operations
3. Validate state in debug mode
4. Monitor state size to prevent memory bloat

### Error Prevention
1. Use validation utilities in development
2. Enable debug mode for troubleshooting
3. Test state transitions thoroughly
4. Document state dependencies clearly

This centralised approach ensures robust, maintainable session state management that supports ClinXML's complex clinical data workflows while providing excellent developer experience and runtime reliability.