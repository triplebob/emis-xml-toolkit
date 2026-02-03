# ClinXML Module Architecture

## Overview

ClinXML v3 is organised around a parsing-first pipeline with dedicated packages for metadata enrichment, caching, UI composition, export generation, and terminology integration. This guide provides detailed descriptions of each module with responsibilities, key functions, and modification guidance.

---

## End-to-End Flow

```text
streamlit_app.py
  -> utils.ui.status_bar.render_status_bar()
  -> utils.caching.cache_manager.cache_xml_code_extraction()
      -> utils.caching.xml_cache.cache_parsed_xml()
          -> utils.parsing.pipeline.parse_xml()
          -> utils.metadata.enrichment / serialisation
  -> utils.metadata.snomed_translation.translate_emis_to_snomed()
  -> utils.ui.ui_tabs.render_results_tabs()
  -> utils.exports.* (on demand)
```

---

## Main Application

### `streamlit_app.py` - Main Application Entry Point

**Purpose:** Primary Streamlit application that coordinates all processing.

**Responsibilities:**
- File upload interface and user controls
- XML processing orchestration using the parsing pipeline
- Progress tracking with weighted task stages
- Session state management with file hashing
- SNOMED translation coordination
- Performance controls and debug mode

**Key Functions:**
- `main()` - Application entry point
- `generate_file_hash()` - Create file identity hash
- `is_reprocessing_same_file()` - Detect reprocessing of same file
- `mark_file_processed()` - Update processing state

**When to modify:** UI layout changes, main workflow changes, progress tracking updates.

---

## Parsing Pipeline (`utils/parsing/`)

The parsing layer is the canonical XML processing module. All XML analysis flows through this pipeline.

### `pipeline.py` - Orchestrated Parsing Pipeline

**Purpose:** Single entry point for parsing XML into entities, code stores, and optional pattern results.

**Responsibilities:**
- Load document via `document_loader`
- Classify elements via `ElementClassifier`
- Produce `ParsedDocument` with buckets
- Orchestrate node parsers for searches, reports
- Create and populate `CodeStore` for deduplication
- Optionally run pattern plugins

**Key Functions:**
- `parse_xml(xml_content, source_name, run_patterns)` - Main parsing entry point

**Returns:**
```python
{
    "parsed_document": ParsedDocument,
    "entities": List[Dict],
    "code_store": CodeStore,
    "pattern_results": List[PatternResult]  # optional
}
```

**When to modify:** Pipeline orchestration changes, new entity types, parse output shape changes.

---

### `document_loader.py` - XML Document Loading

**Purpose:** Load XML content and extract namespaces.

**Responsibilities:**
- Parse XML string to ElementTree
- Extract namespace declarations via `iterparse`
- Ensure `emis` namespace always available
- Build document metadata

**Key Functions:**
- `load_document(xml_content, source_name)` - Returns (root, namespaces, metadata)

**When to modify:** Encoding issues, namespace handling, metadata extraction.

---

### `element_classifier.py` - Element Classification

**Purpose:** Classify XML elements into logical buckets (searches, reports, folders).

**Responsibilities:**
- Identify searches vs reports vs folders
- Distinguish list/audit/aggregate report types
- Deduplicate elements found via multiple paths

**Key Classes:**
- `ElementClassifier` - Main classification engine
- `ClassifiedBuckets` - Container for classified elements

**When to modify:** New element types, classification rules, bucket structure.

---

### `namespace_utils.py` - Namespace Helpers

**Purpose:** Provide consistent namespace handling for mixed namespaced/non-namespaced XML.

**Key Functions:**
- `find_ns(elem, tag, namespaces)` - Find first matching element
- `findall_ns(elem, tag, namespaces)` - Find all matching elements
- `get_text_ns(elem, tag, namespaces)` - Get element text
- `find_child_any(parent, candidate_tags, namespaces)` - Find from candidates
- `get_child_text_any(elem, candidate_tags, namespaces)` - Get text from candidates
- `get_attr_any(elem, candidate_attrs)` - Get attribute with fallback

**When to modify:** Namespace resolution issues, new helper requirements.

---

### `node_parsers/` - Structured XML Parsers

**Purpose:** Parse specific XML node types into structured data.

<details>
<summary><strong>search_parser.py</strong></summary>

**Purpose:** Parse search elements including criteria, value sets, and linked criteria.

**Key Functions:**
- `parse_search(elem, namespaces, code_store)` - Parse search element

**When to modify:** Search structure changes, new criteria patterns.

</details>

<details>
<summary><strong>report_parser.py</strong></summary>

**Purpose:** Parse list, audit, and aggregate reports.

**Key Functions:**
- `parse_report(elem, namespaces, report_type, code_store)` - Parse report element

**When to modify:** Report structure changes, new report types.

</details>

<details>
<summary><strong>criterion_parser.py</strong></summary>

**Purpose:** Parse individual criterion elements with flag mapping.

**When to modify:** Criterion structure changes, new criterion types.

</details>

<details>
<summary><strong>value_set_parser.py</strong></summary>

**Purpose:** Parse value sets and extract clinical codes.

**When to modify:** Value set structure changes, code extraction logic.

</details>

---

## Pattern Plugins (`utils/pattern_plugins/`)

Modular detector framework for XML patterns. Each plugin inspects element context and emits structured flags.

### `registry.py` - Plugin Registration

**Purpose:** Manage plugin registration and execution.

**Key Functions:**
- `@register_pattern(pattern_id)` - Decorator for plugin registration
- `pattern_registry.run_all(context)` - Execute all registered plugins
- `pattern_registry.load_all_modules(package)` - Load all plugin modules

**When to modify:** Plugin execution flow, registration mechanism.

---

### `base.py` - Plugin Data Contracts

**Purpose:** Define `PatternContext` and `PatternResult` data classes, plus shared helper functions.

**Key Classes:**
- `PatternContext` - Input context (element, namespaces, path, container_info)
- `PatternResult` - Output result (id, description, flags, confidence, notes)

**Helper Functions:**
- `tag_local(elem)` - Returns local tag name, stripping namespace prefix
- `find_first(elem, namespaces, *queries)` - Safe namespace fallback lookup (avoids ElementTree truthiness issues)

**When to modify:** Plugin contract changes, shared helper additions.

---

### Plugin Modules

| Module | Pattern IDs | Primary Flags |
|--------|-------------|---------------|
| `restrictions.py` | `restriction_latest_earliest`, `restriction_test_attribute` | `has_restriction`, `restriction_type`, `record_count` |
| `temporal.py` | `temporal_single_value`, `temporal_range` | `has_temporal_filter`, `temporal_variable_value` |
| `demographics.py` | `demographics_lsoa`, `demographics_geo` | `is_patient_demographics`, `demographics_type` |
| `refsets.py` | `refset_detection` | `is_refset`, `is_pseudo_refset`, `is_pseudo_member` |
| `relationships.py` | `linked_relationship` | `relationship_type`, `parent_column`, `child_column` |
| `logic.py` | `logic_negation_and_actions` | `negation`, `member_operator` |
| `medication.py` | `medication_code_system` | `is_medication_code`, `medication_type_flag` |
| `parameters.py` | `parameters` | `has_parameter`, `parameter_names` |
| `enterprise.py` | `enterprise_metadata`, `qof_contract` | `enterprise_reporting_level`, `qmas_indicator` |
| `emisinternal.py` | `emisinternal_classification` | `has_emisinternal_filters`, `emisinternal_values` |
| `column_filters.py` | `column_filters` | `column_filters` |

**When to modify:** Add new pattern detection, update existing patterns.

---

## Metadata (`utils/metadata/`)

Enrichment and domain projection layer.

### `flag_registry.py` - Canonical Flag Definitions

**Purpose:** Define all valid flags with constraints and validators.

**Key Components:**
- `FlagDefinition` - Flag definition with name, description, domain, validator
- `FLAG_DEFINITIONS` - Dictionary of 95+ canonical flags
- Validators: `_is_bool`, `_non_empty_str`, `_list_str`, `_list_obj`

**When to modify:** Add/update flag definitions.

---

### `flag_mapper.py` - Flag Mapping and Validation

**Purpose:** Map and validate flags from parsing to canonical form.

**Key Functions:**
- `map_element_flags(element, results, defaults, namespaces)` - Merge plugin flags
- `validate_flags(flags)` - Validate against FLAG_DEFINITIONS

**When to modify:** Flag mapping logic, validation behaviour.

---

### `snomed_translation.py` - EMIS to SNOMED Translation

**Purpose:** Translate EMIS GUIDs to SNOMED codes using lookup table.

**Responsibilities:**
- Create lookup dictionaries for O(1) access
- Handle cached SNOMED mappings (60-minute TTL)
- Support deduplication modes (unique_codes, unique_per_entity)
- Categorise results (clinical, medications, refsets, pseudo-refsets)

**Key Functions:**
- `translate_emis_to_snomed(emis_guids, lookup_df, emis_guid_col, snomed_code_col, deduplication_mode)`

**When to modify:** Translation logic, deduplication modes, categorisation.

---

### `enrichment.py` - Code Enrichment

**Purpose:** Enrich parsed codes with additional metadata.

**When to modify:** Enrichment logic, new metadata fields.

---

### `serialisers.py` - UI/Export Row Shaping

**Purpose:** Transform parsed data into UI-ready and export-ready formats.

**When to modify:** Output format changes, new fields.

---

## Caching (`utils/caching/`)

Cache and lookup infrastructure.

### `cache_manager.py` - Centralised Cache Orchestration

**Purpose:** Coordinate all caching operations with TTL strategies.

**Responsibilities:**
- XML code extraction caching
- SNOMED lookup dictionary caching
- Memory management with garbage collection
- Cache clearing utilities

**Key Functions:**
- `cache_xml_code_extraction(xml_content, source_name)` - Cache pipeline output
- `clear_cache_for_new_file()` - Clear file-specific caches
- `get_memory_stats()` - Memory usage statistics

**When to modify:** Cache strategies, TTL configuration, memory management.

---

### `lookup_manager.py` - Lookup Table Coordination

**Purpose:** Coordinate loading encrypted parquet from cache or GitHub.

**Responsibilities:**
- Load from session state if available
- Load from local .cache/ if exists
- Generate from private repo if needed
- Provide filtered lookup APIs

**Key Functions:**
- `load_lookup_table()` - Main loading entry point
- `generate_encrypted_lookup()` - Generate from private repo
- `get_lookup_for_guids(guids)` - Get filtered lookup subset
- `is_lookup_loaded()` - Check if lookup available

**When to modify:** Loading strategy, encryption changes.

---

### `lookup_cache.py` - Encrypted Parquet Operations

**Purpose:** Handle encrypted parquet file operations.

**Responsibilities:**
- Fernet encryption/decryption using GZIP_TOKEN
- PyArrow parquet reading
- Local cache file management

**Key Functions:**
- `_encrypt_bytes(data)` - Encrypt with Fernet
- `_decrypt_bytes(encrypted)` - Decrypt with Fernet
- `load_filtered_lookup(guids)` - Load filtered subset
- `build_lookup_dicts(df)` - Create lookup dictionaries

**When to modify:** Encryption mechanism, parquet handling.

---

### `code_store.py` - Deduplicated Code Storage

**Purpose:** Store codes once with source tracking across entities.

**Responsibilities:**
- Deduplicate by (code_value, valueSet_guid, code_system)
- Track source entities per code
- O(1) lookups using dictionary storage

**Key Classes:**
- `CodeEntry` - Single code with source tracking
- `CodeStore` - Main storage class

**Key Methods:**
- `add_code(code_dict, entity_context)` - Add code with deduplication
- `get_all_codes()` - Get all stored codes
- `get_codes_for_entity(entity_id)` - Get codes for specific entity

**When to modify:** Deduplication logic, source tracking.

---

### `xml_cache.py` - XML Parsing Cache

**Purpose:** Cache parsed XML and derived UI rows.

**When to modify:** Cache structure, invalidation logic.

---

## Terminology Server (`utils/terminology_server/`)

NHS England Terminology Server FHIR R4 integration.

### `client.py` - FHIR R4 API Client

**Purpose:** Handle NHS Terminology Server communication.

**Responsibilities:**
- OAuth2 authentication with thread-safe token management
- SNOMED concept lookup and validation
- Hierarchical code expansion using ECL
- Retry logic and rate limiting

**Key Classes:**
- `TerminologyServerConfig` - Configuration settings
- `TokenManager` - Thread-safe token management
- `ExpandedConcept` - Expanded concept data
- `ExpansionResult` - Expansion operation result

**When to modify:** API changes, authentication, error handling.

---

### `service.py` - Expansion Service Layer

**Purpose:** Business logic for code expansion operations.

**Responsibilities:**
- Expansion workflow orchestration
- Result processing and validation
- EMIS lookup integration

**When to modify:** Expansion logic, result processing.

---

### `expansion_workflow.py` - Expansion Workflow

**Purpose:** Orchestrate batch expansion with progress tracking.

**When to modify:** Workflow steps, progress tracking.

---

## Exports (`utils/exports/`)

On-demand export builders.

### `ui_export_manager.py` - Export Coordination

**Purpose:** Coordinate lazy export generation and download state.

**Key Functions:**
- `_render_lazy_export()` - Render lazy export button with state management

**When to modify:** Export UI flow, state management.

---

### Search Exports

| Module | Purpose |
|--------|---------|
| `search_excel.py` | Excel exports with rule logic, criteria, codes |
| `search_json.py` | JSON exports with structure and metadata |
| `search_data_provider.py` | Data preparation for search exports |

**When to modify:** Export format changes, new fields.

---

### Report Exports

| Module | Purpose |
|--------|---------|
| `report_excel.py` | Excel exports for List/Audit/Aggregate reports |
| `report_json.py` | JSON exports for reports |
| `report_export_common.py` | Shared export utilities |

**When to modify:** Export format changes, new report types.

---

### Other Exports

| Module | Purpose |
|--------|---------|
| `clinical_exports.py` | Clinical code CSV exports with deduplication |
| `terminology_child_exports.py` | NHS expansion result exports with XML column |
| `analytics_exports.py` | Analytics export handlers |

---

## System (`utils/system/`)

Shared system utilities.

### `session_state.py` - Centralised Session State

**Purpose:** Define canonical session state keys and management utilities.

**Key Classes:**
- `SessionStateKeys` - All session state key constants
- `SessionStateGroups` - Logical key groupings

**Key Functions:**
- `clear_for_new_xml_selection()` - Clear when switching files
- `clear_for_new_xml()` - Full reset for reprocess
- `get_cached_snomed_mappings()` - Get 60-minute cached mappings
- `update_snomed_cache(mappings)` - Update SNOMED cache
- `clear_expired_snomed_cache()` - TTL-based cleanup

**When to modify:** New session keys, cleanup behaviour.

---

### `error_handling.py` - Error Management

**Purpose:** Structured error classes and user-friendly display.

**Key Functions:**
- `ErrorHandler` - Error handling utilities
- `create_error_context()` - Build error context
- `display_error_to_user()` - User-friendly error display
- `streamlit_safe_execute()` - Safe execution wrapper

**When to modify:** Error categories, display format.

---

### `debug_logger.py` - Debug Logging

**Purpose:** Debug logging controls and diagnostics.

**When to modify:** Logging configuration, debug features.

---

### `version.py` - Application Version

**Purpose:** Version constants for the application.

**When to modify:** Version updates.

---

## UI (`utils/ui/`)

User interface composition and rendering.

### `ui_tabs.py` - Main Results Interface

**Purpose:** Coordinate tab rendering and routing.

**Key Functions:**
- `render_results_tabs()` - Render all result tabs

**When to modify:** Tab structure, routing logic.

---

### `status_bar.py` - Sidebar Status Display

**Purpose:** Render sidebar status, lookup info, memory display.

**Key Functions:**
- `render_status_bar()` - Main status bar rendering
- `render_lookup_status()` - Lookup table status
- `render_memory_panel()` - Memory usage display

**When to modify:** Sidebar layout, status display.

---

### `theme.py` - Centralised Theme Constants

**Purpose:** Define colours, spacing, and styling.

**Key Classes:**
- `ThemeColours` - Colour palette definitions

**Key Functions:**
- `info_box()`, `success_box()`, `warning_box()`, `error_box()` - Styled message boxes

**When to modify:** UI theming, colour changes.

---

### `tab_helpers.py` - Shared Tab Utilities

**Purpose:** Common functionality for tab modules.

**Key Functions:**
- Pagination helpers
- SNOMED lookup wrappers
- Data processing utilities

**When to modify:** Shared tab functionality.

---

## UI Tabs (`utils/ui/tabs/`)

Modular tab implementations organised by domain.

| Directory | Purpose |
|-----------|---------|
| `clinical_codes/` | Clinical code tabs (summary, codes, medications, refsets, analytics) |
| `xml_inspector/` | XML exploration (file browser, dependencies, raw viewer) |
| `search_browser/` | Search analysis (overview, detail, criteria viewer) |
| `report_viewer/` | Report viewing (list, audit, aggregate) |
| `terminology_server/` | NHS integration (expansion, lookup) |
| `debug/` | Debug features (memory diagnostics) |

---

## Data Contracts

### Parsing Output
```python
{
    "parsed_document": ParsedDocument,
    "entities": List[Dict],
    "code_store": CodeStore,
    "pattern_results": List[PatternResult]  # optional
}
```

### Cached XML Output
```python
{
    "ui_rows": List[Dict],
    "entities": List[Dict],
    "folders": List[Dict],
    "structure_data": Dict,
    "code_store": CodeStore
}
```

### Session Keys
Use `SessionStateKeys` constants from `utils/system/session_state.py`.

---

## Design Principles

- **Single-responsibility modules**: Each module does one thing well
- **Session-key centralisation**: All keys defined in `SessionStateKeys`
- **Lazy export generation**: Exports built only when requested
- **Cache-aware processing**: Avoid repeated parse/transform work
- **Explicit compatibility layers**: Full DataFrame access where still needed

---

## Quick Reference

| Task | Location |
|------|----------|
| New export format | `utils/exports/` |
| UI display issues | `utils/ui/` |
| Classification problems | `utils/parsing/element_classifier.py` |
| Search rule logic | `utils/parsing/node_parsers/search_parser.py` |
| Translation issues | `utils/metadata/snomed_translation.py` |
| Lookup table problems | `utils/caching/lookup_manager.py` |
| Cache performance | `utils/caching/cache_manager.py` |
| NHS Terminology Server | `utils/terminology_server/` |
| Session state | `utils/system/session_state.py` |
| Theme and styling | `utils/ui/theme.py` |
| Error handling | `utils/system/error_handling.py` |
| New XML patterns | `utils/pattern_plugins/` |

---

## Related Documentation

- **[Project Structure](../project-structure.md)** - Repository layout
- **[Test Suite Reference](testing.md)** - Test coverage and patterns
- **[Session State Management](session-state-management.md)** - State handling
- **[Namespace Handling](namespace-handling.md)** - XML namespace utilities
- **[Flags Technical Guide](../flags-and-plugins/flags.md)** - Flag system
- **[Plugin Development Guide](../flags-and-plugins/plugins.md)** - Pattern plugins

---

*Last Updated: 3rd February 2026*
*Application Version: 3.0.0*
