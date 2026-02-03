# ClinXML Project Structure

## Overview

ClinXML v3 uses a modular architecture with specialised modules for parsing, metadata enrichment, caching, UI rendering, export functionality, and NHS terminology integration.
The codebase is organised into logical directories that separate concerns and enable maintainable development.

## Repository Layout

```text
emis-xml-convertor/
├── streamlit_app.py                              # Main application entry point
├── README.md                                     # Project overview and quick start
├── changelog.md                                  # Version history
├── requirements.txt                              # Python dependencies
├── LICENSE                                       # License terms
├── EULA.md                                       # End user licence agreement
├── static/                                       # Branding assets (logos, favicon)
├── docs/                                         # Technical documentation
├── tests/                                        # Test suite
└── utils/                                        # Modular application architecture
```

---

## `utils/` Package Structure

<details>
<summary><strong>utils/caching/</strong> - Cache management</summary>

```text
caching/
├── cache_manager.py        # Centralised cache orchestration with TTL strategies
├── code_store.py           # Deduplicated code storage with source tracking
├── github_loader.py        # GitHub API loading with authentication
├── lookup_cache.py         # Encrypted parquet operations (Fernet)
├── lookup_manager.py       # Lookup table coordination and loading
├── search_cache.py         # Search UI state helpers
└── xml_cache.py            # Cached parsed XML and derived UI rows
```

</details>

<details>
<summary><strong>utils/exports/</strong> - Export system</summary>

```text
exports/
├── analytics_exports.py         # Analytics export handlers
├── clinical_exports.py          # Clinical code exports (CSV)
├── report_excel.py              # Report Excel exports
├── report_export_common.py      # Shared report export logic
├── report_json.py               # Report JSON exports
├── search_data_provider.py      # Search export data helpers
├── search_excel.py              # Search Excel exports
├── search_json.py               # Search JSON exports
├── terminology_child_exports.py # NHS terminology expansion exports
└── ui_export_manager.py         # Export coordination and lazy generation
```

</details>

<details>
<summary><strong>utils/metadata/</strong> - Enrichment and domain models</summary>

```text
metadata/
├── code_classification.py       # Code type classification
├── column_name_mapper.py        # Column name mapping
├── description_generators.py    # Description generation
├── emisinternal_describer.py    # EMISINTERNAL description
├── enrichment.py                # Code enrichment
├── flag_mapper.py               # Flag mapping and validation
├── flag_registry.py             # Canonical flag definitions (95+ flags)
├── models.py                    # Data models
├── operator_translator.py       # Operator translation
├── population_describer.py      # Population description
├── processing_stats.py          # Processing statistics
├── report_filtering.py          # Report filtering logic
├── restriction_describer.py     # Restriction description
├── serialisers.py               # UI/export row shaping
├── snomed_translation.py        # EMIS to SNOMED translation
├── structure_enricher.py        # Structure enrichment
├── structure_provider.py        # Structure metadata provider
├── temporal_describer.py        # Temporal description
└── value_set_resolver.py        # Value set resolution
```

</details>

<details>
<summary><strong>utils/parsing/</strong> - XML parsing pipeline</summary>

```text
parsing/
├── document_loader.py      # XML loading and namespace extraction
├── element_classifier.py   # Element type classification
├── encoding.py             # Character encoding detection
├── namespace_utils.py      # Namespace helpers (find_ns, findall_ns, etc.)
├── pipeline.py             # Orchestrated parsing entry point
└── node_parsers/           # Structured XML parsers
    ├── criterion_parser.py       # Criterion parsing
    ├── linked_criteria_parser.py # Linked criteria parsing
    ├── report_parser.py          # Report structure parsing
    ├── search_parser.py          # Search criteria parsing
    ├── structure_parser.py       # Structure parsing
    └── value_set_parser.py       # Value set parsing
```

</details>

<details>
<summary><strong>utils/pattern_plugins/</strong> - Modular pattern detectors</summary>

```text
pattern_plugins/
├── base.py                 # PatternContext, PatternResult, and shared helpers (tag_local, find_first)
├── registry.py             # Plugin registration and execution
├── column_filters.py       # Column filter parsing
├── demographics.py         # LSOA/geographic detection
├── emisinternal.py         # EMISINTERNAL classification
├── enterprise.py           # Enterprise and QOF metadata
├── logic.py                # Negation and logic operators
├── medication.py           # Medication code systems
├── parameters.py           # Parameter detection
├── population.py           # Population references
├── refsets.py              # Refset/pseudo-refset detection
├── relationships.py        # Linked criteria relationships
├── restrictions.py         # Latest/earliest restriction detection
├── source_containers.py    # Container type heuristics
├── temporal.py             # Temporal filter detection
└── value_sets.py           # Value set properties
```

</details>

<details>
<summary><strong>utils/system/</strong> - System utilities</summary>

```text
system/
├── debug_logger.py     # Debug logging controls
├── error_handling.py   # Structured error management
├── session_state.py    # Centralised session state keys and helpers
├── update_versions.py  # Version update utilities
└── version.py          # Application version constants
```

</details>

<details>
<summary><strong>utils/terminology_server/</strong> - NHS integration</summary>

```text
terminology_server/
├── client.py              # FHIR R4 API client with OAuth2
├── connection.py          # Connection utilities
├── expansion_workflow.py  # Expansion workflow orchestration
└── service.py             # Expansion service layer
```

</details>

<details>
<summary><strong>utils/ui/</strong> - User interface components</summary>

```text
ui/
├── status_bar.py       # Sidebar status display
├── tab_helpers.py      # Shared tab utilities
├── theme.py            # Centralised theme constants
├── ui_tabs.py          # Main results interface routing
└── tabs/
    ├── clinical_codes/           # Clinical code tabs
    │   ├── analytics_tab.py      # Analytics view
    │   ├── clinical_tabs.py      # Tab orchestration
    │   ├── clinicalcodes_tab.py  # Clinical codes view
    │   ├── codes_common.py       # Shared utilities
    │   ├── medications_tab.py    # Medications view
    │   ├── pseudo_members_tab.py # Pseudo members view
    │   ├── pseudo_refsets_tab.py # Pseudo-refsets view
    │   ├── refsets_tab.py        # Refsets view
    │   └── summary_tab.py        # Summary view
    ├── debug/
    │   └── memory_tab.py         # Memory diagnostics
    ├── report_viewer/            # Report viewer tabs
    │   ├── aggregate_tab.py      # Aggregate report view
    │   ├── audit_tab.py          # Audit report view
    │   ├── common.py             # Shared utilities
    │   ├── list_tab.py           # List report view
    │   └── report_tabs.py        # Tab orchestration
    ├── search_browser/           # Search browser tabs
    │   ├── analysis_tabs.py      # Search overview
    │   ├── metadata_provider.py  # Search metadata
    │   ├── search_common.py      # Shared utilities
    │   ├── search_criteria_viewer.py # Criteria rendering
    │   ├── search_detail_tab.py  # Search detail view
    │   └── search_tabs.py        # Tab orchestration
    ├── terminology_server/       # Terminology server tabs
    │   ├── expansion_tab.py      # Child code expansion
    │   └── lookup_tab.py         # Individual code lookup
    └── xml_inspector/            # XML exploration tabs
        ├── dependencies_tab.py   # Dependencies view
        ├── file_browser.py       # File browser view
        ├── raw_viewer.py         # Raw XML viewer
        └── xml_tab.py            # Tab orchestration
```

</details>

---

## Architecture Principles

### Modular Design
- **Separation of Concerns**: Each module has a single, well-defined responsibility
- **Clean Interfaces**: Standard patterns across similar modules
- **Dependency Injection**: Core modules are independent and testable

### Performance-First
- **Caching Architecture**: Multi-layer caching with appropriate TTL strategies
- **Lazy Loading**: Resources loaded only when needed
- **Memory Management**: Automatic cleanup and garbage collection

### Maintainability
- **Centralised Configuration**: Theme, session state, and error handling centralised
- **Consistent Naming**: Clear, descriptive file and function names
- **Documentation**: Comprehensive inline documentation and architectural docs

---

## Runtime Flow (High Level)

```text
streamlit_app.py
  -> utils.ui.status_bar.render_status_bar()
  -> utils.caching.cache_manager.cache_xml_code_extraction()
      -> utils.caching.xml_cache.cache_parsed_xml()
          -> utils.parsing.pipeline.parse_xml()
          -> utils.metadata.enrichment / serialisation
  -> utils.metadata.snomed_translation.translate_emis_to_snomed()
  -> utils.ui.ui_tabs.render_results_tabs()
  -> utils.exports.* (on-demand export payloads)
```

---

## Key Architectural Components

### Analysis Pipeline
```
XML Upload → Document Loading → Element Classification → Node Parsing →
Flag Mapping → Enrichment → UI Row Shaping → Tab Rendering
```

### Caching Strategy
```
Session State ←→ Streamlit Cache ←→ Local Cache (.cache/) ←→ GitHub API Fallback
```

### Export Pipeline
```
Raw Data → Type-Specific Processing → Lazy Generation → User Download
```

---

## Top-Level Tabs

Normal processed view (non-debug):

1. Clinical Codes
2. XML Explorer
3. Searches
4. Reports
5. Code Lookup

Debug mode adds a Memory tab for diagnostics.

---

## File Naming Conventions

| Pattern | Purpose |
|---------|---------|
| `*_parser.py` | XML parsing modules |
| `*_tab.py` | UI tab modules |
| `*_exports.py` | Export handlers |
| `*_describer.py` | Description generators |
| `*_provider.py` | Data providers |
| `*_manager.py` | Data management modules |

---

## Tests

Current test files:

- `tests/test_builtin_plugins.py` - Built-in plugin regression tests
- `tests/test_code_store.py` - CodeStore deduplication and reference tests
- `tests/test_exports.py` - Search/report/clinical export generation tests
- `tests/test_parsing_report_parser.py` - Report parsing tests
- `tests/test_flags_and_plugins.py` - Flag/plugin contract tests
- `tests/test_namespace_utils.py` - Namespace helper tests
- `tests/test_plugin_harness.py` - Plugin harness smoke tests
- `tests/test_search_parser.py` - Search parsing tests
- `tests/test_session_state.py` - Session state unit tests
- `tests/test_snomed_translation.py` - SNOMED translation and deduplication tests
- `tests/test_structure_parser.py` - Structure parsing tests
- `tests/test_performance.py` - Performance benchmarks

Recommended release checks:

```bash
python -m pytest -q tests
python -m unittest discover tests
```

---

## Notes for Contributors

- Prefer `SessionStateKeys` constants over raw session key strings
- Keep parser output contracts stable (`entities`, `folders`, `ui_rows`, `code_store`)
- Keep exports lazy/on-demand to avoid holding large payloads in memory
- Add new XML pattern detection in `utils/pattern_plugins/` and wire flags through metadata mappers

---

## Related Documentation

- **[Module Architecture Guide](architecture/modules.md)** - Detailed module descriptions
- **[Session State Management](architecture/session-state-management.md)** - Session state architecture
- **[Namespace Handling](architecture/namespace-handling.md)** - Namespace handling guide
- **[Test Suite Reference](architecture/testing.md)** - Test coverage and patterns
- **[Flags Technical Guide](flags-and-plugins/flags.md)** - Flag system reference
- **[Plugin Development Guide](flags-and-plugins/plugins.md)** - Plugin creation guide
- **[EMIS XML Patterns](xml-pattern-library/emis-xml-patterns.md)** - XML parsing patterns

---

*Last Updated: 3rd February 2026*
*Application Version: 3.0.0*

For specific module details, see the [Module Architecture Guide](architecture/modules.md).
