# Changelog

> **Version 3.0** - A generational leap in architecture and performance.
> For v1.x-2.x history, see [`docs/changelog-archive/changelog-v2.md`](docs/changelog-archive/changelog-v2.md)

---

## v3.0.2 - Analytics & MDS Generator (6th February 2026)

### **Analytics Tab Restructure**

- **Promoted to top-level tab**: Analytics now sits between XML Explorer and Code Lookup (6 tabs total)
- **New tab order**: Clinical Codes | Searches | Reports | XML Explorer | Analytics | Code Lookup
- **Subtab organisation**: XML Overview (moved from Clinical Codes) and MDS Generator (new)

### **MDS (Minimum Dataset) Generator**

New MDS clinical code export for resource management, repository indexing, audit, and governance workflows.

- **📦 MDS Generator subtab**: Available under Analytics after XML processing
- **Entity-first traversal**: Memory-safe extraction from `pipeline_entities` without DataFrame transforms
- **Smart filtering**: Excludes EMISINTERNAL codes, pseudo-refset containers, and invalid GUIDs
- **View modes**: Unique Codes (dedupe by GUID) or Per Source (dedupe by source + GUID)
- **Code type classification**: Pseudo members assigned to core type (clinical/medication/refset)
- **EMIS XML output**: Optional XML ready code column with `<values>` blocks including dynamic `includeChildren` from source data
- **Conflict resolution**: Defaults to `includeChildren=false` when same code appears with conflicting values
- **Summary metrics**: Criteria scanned, row count, mapped count, mapping rate, type breakdown
- **Preview table**: First 50 rows with row highlighting by mapping status (green/red)
- **New modules**: `mds_provider.py`, `mds_exports.py`, `mds_tab.py`

### **NHS Terminology Server Hierarchy View**

Full lineage display for expanded SNOMED codes with tree visualisation.

- **Button-triggered hierarchy trace**: Available below Child Codes Detail table in expansion and lookup tabs
- **ASCII tree view**: Parent-child relationships with depth indicators starting at root: `[R]`, `[D1]`, `[D2]`...
- **Shared lineage detection**: Highlights codes appearing under multiple expansion branches
- **Efficient API usage**: Reuses cached expansion results; only `<!` (direct children) queries are new calls
- **Guard rails**: Configurable depth cap, API call cap, and node cap per parent
- **Export support**: TXT, SVG, and JSON with full hierarchy metadata and source file tracking
- **New module**: `lineage_workflow.py` extracted from `expansion_workflow.py` for maintainability

### **Session-Scoped Caching**

Streamlit 1.53.0+ session-scoped caching for user-isolated data.

- **Deployed `scope="session"`**: Applied to `_load_report_metadata()`, `_extract_clinical_codes()`, `_process_column_groups()`, `paginate_reports()`, `load_report_sections()`
- **Bug fix**: Resolved `paginate_reports()` reading session state inside cached function
- **Updated requirements**: Now requires `streamlit>=1.53.0`
- **Global caches preserved**: SNOMED lookups, version info, and file-hash based caches remain global as intended

### **Plugin Flag Propagation Fix**

- **Fixed incorrect flag inheritance**: `is_refset`, `is_pseudo_refset`, `is_pseudo_member` no longer propagate from criterion-level plugins to individual codes
- **Correct tagging**: Regular codes in pseudo-refsets now correctly tagged as `is_pseudo_member: true`
- **Fix location**: `value_set_parser.py` - excluded code-specific flags from `parent_flags` inheritance

### **Plugin Manager UI**

New debug interface for plugin inspection and control.

- **Plugins subtab**: Available in Debug tab (debug mode only)
- **Priority-coloured table**: Displays Name, Description, Tags, Priority, Score, Version, Enabled status
- **Interactive controls**: Enable/disable plugins via checkboxes
- **Reset functionality**: Reset All to Defaults button restores original plugin configuration

### **Test Coverage Expansion**

- **MDS tests**: 27 tests covering provider logic, export helpers, and preview transforms
- **Terminology workflow tests**: 6 tests for hierarchy lineage tracing and tree building
- **Total test count**: ~130 tests (up from 54)

---

## v3.0.1 - Security & UI Enhancements (3rd February 2026)

### **Security Patch**

- **`cryptography` upgraded** from constrained legacy range to `>=42.0.2`
- **Dependabot alerts resolved** for vulnerable versions in `requirements.txt`
- **Risk reduction** for TLS/RSA exchange and PKCS12 parsing vulnerability paths reported upstream

### **XML Explorer Improvements**

- **Line numbers in RAW XML viewer**: Syntax-highlighted XML now displays line numbers
- **Non-selectable gutter**: Line numbers excluded when copying code
- **Table-based rendering**: Ensures alignment between line numbers and code content

### **XML Explorer Export Enhancements**

- **New explorer export module**: Added `utils/exports/explorer_exports.py` for shared tree export logic
- **XML Explorer tabs exports**: Added lazy on-demand TXT and SVG export with immediate cleanup after download
- **Styled SVG output**: Exported tree SVG now preserves connector and node colour mapping for readability

### **Debug Output Streamlining**

- **CodeStore summary-only logging**: Replaced per-code debug spam with a single end-of-run summary and skipped/dropped detail events only
- **CodeStore cache invalidation hooks**: Added source-hash tracking and automatic stale cache invalidation when XML source data changes
- **Export lifecycle logging only**: `clinical_exports` debug output now logs only export creation and export garbage collection events

### **NHS Terminology Server Error Handling**

- **Structured error categories**: New `ErrorCategory` enum classifies errors (auth failure, invalid code, not found, no matches, rate limited, server error, connection error, timeout)
- **FHIR OperationOutcome parsing**: 422 responses now parsed to extract meaningful error details
- **SNOMED code validation**: Format validation before API calls (numeric, 6-18 digits)
- **User-friendly messages**: Clear error descriptions with actionable suggestions for each error type
- **Improved UI feedback**: Appropriate warning/error styling based on error severity

### **Terminology Server Lookup Performance**

- **Fixed slow EMIS GUID matching**: Replaced full DataFrame iteration with filtered PyArrow queries
- **New `lookup_snomed_to_emis()` function**: Batch lookup SNOMED → EMIS with TTL cache (5 min, 10k max entries)
- **Eliminated redundant API call**: Display name now passed through to expansion, saving one lookup per code
- **On-demand lookups**: Child codes queried after expansion completes, not pre-loaded
- **Memory efficiency**: No longer loads entire lookup table into memory for terminology server features

### **Plugin Versioning Enhancements**

- **Plugin versioning support**: Added version-aware plugin registry behaviour for safer plugin evolution
- **Compatibility checks**: Improved plugin loading/selection logic to respect declared plugin versions
- **Versioning test coverage**: Added targeted tests for registry versioning paths to lock in expected behaviour

### **Debug & Memory UI Refinements**

- **Debug tab**: Added debug-related tab to allow management overview of current plugins, enable/disable plugins and review load order
- **Metric card consistency**: Standardised key debug/memory metrics into framed card-style layouts
- **Memory diagnostics layout**: Reworked memory/lookup/GC sections for clearer at-a-glance operational status

---

## v3.0.0 - Complete Architecture Rebuild & Encrypted Parquet (February 2026)

Version 3.0 represents a complete ground-up rebuild of ClinXML, delivering improvements to memory efficiency, code organisation, and extensibility. 
The legacy `util_modules` structure has been replaced with a modern `utils/` architecture, and the lookup table system has been redesigned using encrypted parquet with on-demand filtering.

---

### **Complete Codebase Architecture Rebuild**

**Ground-Up Module Restructure:**
- **Legacy Elimination**: Complete migration from `util_modules/` to new `utils/` directory structure
- **Logical Separation**: Clean boundaries between parsing, metadata, caching, exports, UI, and system modules
- **Single Responsibility**: Each module now handles one concern with clear interfaces
- **Import Consistency**: Standardised relative imports throughout the codebase
- **Reduced Complexity**: Smaller, focused files replacing monolithic modules

**New Directory Structure:**
- **`utils/parsing/`**: XML parsing pipeline with element classification
- **`utils/metadata/`**: Code enrichment and SNOMED translation
- **`utils/caching/`**: Lookup table management and XML caching
- **`utils/exports/`**: Unified export handlers for all formats
- **`utils/ui/`**: Tab components, themes, and UI helpers
- **`utils/system/`**: Session state, versioning, and debugging utilities

---

### **Extensible Plugin Architecture**

The parsing system has been rebuilt around a plugin-based architecture, enabling modular extension without modifying core code. This design supports future EMIS XML pattern variations and custom processing requirements.

**Core Plugin Components:**
- **ElementClassifier**: Central dispatch system routing XML elements to appropriate handlers based on element type, namespace, and structural context
- **ParsedDocument**: Structured document representation providing typed access to classified elements, maintaining parse integrity throughout processing
- **Pattern Plugins**: Self-contained handlers for specific XML patterns, each responsible for recognising and extracting data from particular element structures
- **Flag Registry**: Centralised metadata management enabling consistent flag assignment (for example `is_restriction`, `is_linked_criteria`, `is_refset`) across all plugins

**Plugin Registration:**
- **Simple Registration**: Plugins registered via ID-to-callable mapping at module import
- **Opt-In Pattern Matching**: Only registered detectors emit pattern flags during parsing
- **Module Organisation**: Plugins organised by pattern type in `utils/pattern_plugins/` directory

**Extension Benefits:**
- **Isolation**: New XML patterns supported by adding plugins without touching existing code
- **Testing**: Individual plugins testable in isolation with mock documents
- **Maintainability**: Clean separation between pattern handlers simplifies debugging and updates

---

### **Encrypted Parquet Lookup Architecture**

**Memory-Optimised Lookup System:**
- **Significant Memory Reduction**: Encrypted bytes stored in session state instead of full DataFrame
- **Encrypted Storage**: Lookup table encrypted with Fernet using GZIP_TOKEN-derived key (PBKDF2HMAC)
- **Filtered Lookups**: XML processing uses filtered subset of lookup data for enrichment
- **Full DataFrame On-Demand**: Translation features load full DataFrame only when needed, then release

**Automatic Cache Generation:**
- **Private Repo Source**: Raw parquet downloaded from private GitHub repository via API
- **Local Encryption**: Automatic encryption and caching to `.cache/` directory on first load
- **Version Synchronisation**: Lookup version info fetched from private repo

**Technical Implementation:**
- **Fernet Encryption**: AES-128-CBC with HMAC authentication for data integrity
- **GZIP Compression**: Parquet compressed before encryption for optimal file size
- **PyArrow Integration**: Direct parquet reading with in-memory filtering
- **Filtered Dictionaries**: Per-XML lookup dicts built from filtered DataFrame subset

---

### **Enhanced Metadata System**

**Flag Framework:**
- **Systematic Flags**: `is_restriction`, `is_linked_criteria`, `is_refset` flags assigned during parsing
- **Source Attribution**: Complete tracking of code origins through processing pipeline
- **Enrichment Pipeline**: Dict-based enrichment for pipeline outputs, with compatibility DataFrame loading retained for translation workflows

---

### **CodeStore Deduplication & Source Tracking**

**Intelligent Deduplication:**
- **Key-Based Deduplication**: Codes deduplicated by `(code_value, valueSet_guid, code_system)` with per-context source references
- **Source Preservation**: Complete tracking of which searches/reports contain each code
- **Performance Optimisation**: O(1) lookups using dictionary-based storage

**Processing Improvements:**
- **Unified Data Flow**: Single code store feeding all downstream consumers
- **Consistent Counts**: All tabs now display synchronised code metrics
- **Memory Efficiency**: Reduced duplication in session state storage

---

### **NHS Terminology Server Refactor**

**Child Code Finder Enhancement:**
- **On-Demand Expansion**: Lazy loading of SNOMED hierarchies when requested
- **Lazy Exports**: Export generation only on button click, not during rendering
- **XML Output Generation**: Copy-paste ready XML for direct EMIS implementation
- **Progress Tracking**: Real-time feedback during large hierarchy expansions

**Standalone Code Lookup:**
- **No XML Required**: New dedicated tab for individual SNOMED code lookup
- **Direct Access**: Query NHS Terminology Server without uploading XML files
- **Validation Support**: Test and validate codes before search implementation
- **EMIS Mapping**: Immediate EMIS GUID lookup for entered SNOMED codes

**Architecture Improvements:**
- **Service Layer Separation**: Clean separation between API client and UI components
- **Credential Management**: Secure credential handling without UI coupling
- **Error Categorisation**: User-friendly messages for different failure scenarios
- **Rate Limiting**: Adaptive rate limiting with exponential backoff

---

### **Pseudo-Refset System**

**Comprehensive Refset Handling:**
- **Automatic Detection**: Pattern-based identification of pseudo-refsets in XML
- **Dedicated Tabs**: Separate UI tabs for refsets, pseudo-refsets, and pseudo-members
- **Smart Filtering**: Context-aware filtering distinguishing true refsets from pseudo-refsets
- **Member Flag**: Proper `is_pseudo_member` flagging throughout processing pipeline

**Export Integration:**
- **Format-Specific Handling**: Correct export behaviour for each refset type
- **Source Attribution**: Track pseudo-refset membership in exports
- **Clinical Accuracy**: Ensure SNOMED refset codes handled without translation attempts
- **Documentation**: Clear labelling in exports distinguishing refset types

---

### **XML Explorer Reimagined**

**Native File Browser:**
- **Hierarchical Navigation**: Tree-based exploration of XML structure
- **Element Details**: Click-to-inspect individual XML elements
- **Search Integration**: Find specific elements within complex documents
- **Performance Optimised**: Lazy loading for large XML files

**Dependencies Browser:**
- **Visual Relationships**: Clear display of search dependencies and linked criteria
- **Dependency Trees**: Text-based root/dependent tree rendering with summary metrics
- **Complexity Analysis**: Metrics for dependency depth and breadth

**RAW XML Viewer:**
- **Syntax Highlighting**: Colour-coded XML display for readability
- **Namespace Stripping**: Toggle to hide namespace prefixes for cleaner view
- **Copy Support**: Easy copying of XML fragments for external use

---

### **Export System Overhaul**

**Lazy Generation Pattern:**
- **On-Demand Creation**: Export files generated only when download button clicked
- **Memory Efficiency**: No pre-generation during UI rendering
- **Immediate Cleanup**: Automatic disposal after download completion
- **Progress Feedback**: Clear loading states during generation

**Export Cache Management:**
- **Automatic Invalidation**: Cache cleared when source data changes
- **Size Limits**: Configurable maximum cache entries to prevent memory accumulation
- **Cleanup Triggers**: Explicit cleanup on XML upload and mode changes

**Context-Sensitive Labelling:**
- **Dynamic Filenames**: Export names reflect content and deduplication mode
- **Source Attribution**: Filenames include source search/report where applicable
- **Timestamp Integration**: Optional timestamp suffixes for versioning
- **Format Consistency**: Unified naming conventions across all export types

---

### **Performance & Memory Optimisation**

**Cache Management:**
- **Max Entries Caps**: Configurable limits on all cache stores preventing unbounded growth
- **TTL Expiration**: Time-based cache invalidation for stale data
- **Bounded Eviction**: Expansion cache enforces size limits by removing oldest entries
- **Explicit Clearing**: Grouped clearing functions for targeted cleanup

**Garbage Collection:**
- **Systematic Cleanup**: GC triggers after large operations
- **Memory Monitoring**: Real-time usage tracking in sidebar
- **Peak Tracking**: Kernel-level peak memory monitoring (Linux/Windows)
- **Warning Thresholds**: Colour-coded alerts approaching memory limits

**Processing Flow:**
- **Cached Parsing Outputs**: Pipeline and structure outputs cached per XML hash for reuse across tabs
- **Lazy Loading**: Deferred computation until data actually needed
- **Batch Operations**: Grouped lookups reducing per-item overhead
- **Session Persistence**: Intelligent caching across tab navigation

---

### **Technical Infrastructure**

**Session State Management:**
- **Centralised Keys**: All session state operations use `SessionStateKeys` constants
- **Grouped Clearing**: Targeted cleanup functions for different data categories
- **Validation Utilities**: Integrity checking and debugging tools
- **SNOMED Cache**: Persistent 60-minute cache for translation results

**Version Management:**
- **Unified Version Source**: Single `version.py` for all version constants
- **Lookup Version Sync**: Automatic fetch from private repo
- **Update Utilities**: `update_versions.py` for documentation synchronisation
- **Cache Clearing**: Version-based cache invalidation for lookup updates

**Error Handling:**
- **Structured Exceptions**: Typed exceptions for different error categories
- **User-Friendly Messages**: Clear guidance for common error scenarios
- **Recovery Suggestions**: Actionable next steps in error displays
- **Debug Logging**: Comprehensive logging for troubleshooting

---

### **Performance Impact**

**Measured Improvements:**
- **Memory Usage**: 93% reduction in lookup table memory footprint
- **Startup Time**: Faster initial load with encrypted cache
- **XML Processing**: Reduced memory consumption with filtered lookups
- **Export Generation**: Lazy loading eliminates pre-generation overhead

**Architecture Benefits:**
- **Maintainability**: Smaller, focused modules easier to understand and modify
- **Extensibility**: Plugin architecture enables new/custom pattern handlers on demand
- **Testability**: Clean interfaces support unit testing
- **Documentation**: Comprehensive technical docs for all major elements

---

### **Migration Notes**

**Breaking Changes:**
- **Module Paths**: All imports changed from `util_modules/` to `utils/`
- **Session State Keys**: `LOOKUP_DF` replaced with `LOOKUP_ENCRYPTED_BYTES`
- **Lookup Loading**: Full DataFrame no longer available in session state

**Automatic Improvements:**
- **Cache Generation**: First load automatically generates encrypted cache
- **Version Sync**: Lookup version info fetched automatically from private repo
- **Memory Optimisation**: All performance improvements apply without configuration

**Configuration:**
- **Secrets Required**: `GITHUB_TOKEN`, `GZIP_TOKEN`, `LOOKUP_TABLE_URL` in Streamlit secrets
- **Private Repo**: Lookup parquet hosted in private GitHub repository
- **Cache Location**: `.cache/` directory for encrypted lookup storage

---

*Version 3.0.0 delivers a complete architectural transformation, replacing legacy structures with a modern, memory-efficient, and extensible platform whilst maintaining full clinical data processing capabilities.*

---

*Last Updated: 6th February 2026*
*Application Version: 3.0.2*
*Live at: https://clinxml.streamlit.app/*
