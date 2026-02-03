# Changelog

> **Version 3.0** - A generational leap in architecture and performance.
> For v1.x-2.x history, see [`docs/changelog-archive/changelog-v2.md`](docs/changelog-archive/changelog-v2.md)

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

*Last Updated: 2nd February 2026*
*Application Version: 3.0.0*
*Live at: https://clinxml.streamlit.app/*
