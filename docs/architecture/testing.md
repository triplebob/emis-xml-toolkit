# ClinXML v3 Test Suite Reference

## Overview

The test suite validates core functionality across parsing, metadata, exports, and plugin systems. Tests run without requiring a Streamlit runtime and can be executed locally or in CI environments.

**Test Location:** `tests/`

**Total Tests:** 51

**Framework:** Python `unittest`

---

## Running Tests

### All Tests

```bash
python -m unittest discover tests -v
```

### Specific Test File

```bash
python -m unittest tests.test_builtin_plugins -v
```

### Specific Test Class

```bash
python -m unittest tests.test_builtin_plugins.TestBuiltinPlugins -v
```

### With pytest (if installed)

```bash
python -m pytest tests/ -v
```

---

## Test File Inventory

| File | Tests | Purpose |
|------|-------|---------|
| `test_builtin_plugins.py` | 6 | Built-in plugin pattern detection |
| `test_code_store.py` | 4 | CodeStore deduplication and reference tracking |
| `test_exports.py` | 5 | Clinical, search, and report export generation |
| `test_flags_and_plugins.py` | 5 | Flag validation and plugin registry contracts |
| `test_namespace_utils.py` | 6 | Namespace helper functions |
| `test_parsing_report_parser.py` | 3 | Report parsing (list, audit, aggregate) |
| `test_performance.py` | 7 | Performance controls and memory efficiency |
| `test_plugin_harness.py` | 3 | Standalone plugin execution harness |
| `test_search_parser.py` | 1 | Search parsing with groups and dependencies |
| `test_session_state.py` | 6 | Session state keys and cache utilities |
| `test_snomed_translation.py` | 3 | SNOMED translation and deduplication |
| `test_structure_parser.py` | 2 | Structure parsing and folder tree enrichment |

---

## Test File Details

<details>
<summary><strong>test_builtin_plugins.py</strong> - Plugin Pattern Detection</summary>

Tests all 14 built-in plugins against sample XML snippets.

**Test Class:** `TestBuiltinPlugins`

**Coverage:**
- `restrictions.py` — latest/earliest and test-attribute detection
- `temporal.py` — single-value and range temporal filters
- `demographics.py` — LSOA detection
- `relationships.py` — linked criteria relationships
- `value_sets.py` — library/inactive and description handling
- `refsets.py` — refset and pseudo-refset detection
- `medication.py` — medication code system detection
- `logic.py` — negation and member operators
- `population.py` — population references
- `enterprise.py` — enterprise metadata and QOF/contract
- `parameters.py` — parameter detection
- `column_filters.py` — column filter parsing
- `emisinternal.py` — EMISINTERNAL classification
- `source_containers.py` — container type heuristics

**Helper Functions:**
- `_criterion(inner_xml)` — Wraps XML in a namespaced criterion element
- `_ctx(inner_xml)` — Creates a `PatternContext` from inner XML

**Example:**
```python
def test_restriction_plugins(self):
    ctx = _ctx("""
        <emis:restriction>
          <emis:columnOrder>
            <emis:recordCount>1</emis:recordCount>
            <emis:direction>ASC</emis:direction>
            <emis:column>EVENT_DATE</emis:column>
          </emis:columnOrder>
        </emis:restriction>
    """)
    latest = restrictions.detect_latest_earliest(ctx)
    self.assertEqual(latest.flags["restriction_type"], "earliest_records")
```

</details>

<details>
<summary><strong>test_code_store.py</strong> - Code Deduplication</summary>

Tests `CodeStore` deduplication, reference tracking, and pseudo-member updates.

**Test Class:** `TestCodeStore`

**Coverage:**
- `add_or_ref` deduplication by key `(code_value, valueSet_guid, code_system)`
- Multiple contexts for the same entity
- `add_reference` method for cross-referencing
- `update_pseudo_member_context` placeholder description updates

**Example:**
```python
def test_add_or_ref_deduplicates_same_entity_and_context(self):
    store = CodeStore()
    store.add_or_ref(("111", "VS-1", "SNOMED_CONCEPT"), {...}, "SEARCH-A")
    store.add_or_ref(("111", "VS-1", "SNOMED_CONCEPT"), {...}, "SEARCH-A")
    codes = store.get_all_codes()
    self.assertEqual(len(codes), 1)
```

</details>

<details>
<summary><strong>test_exports.py</strong> - Export Generation</summary>

Tests clinical, search, and report export helpers.

**Test Classes:**
- `TestClinicalExportHelpers` — CSV metadata and filename generation
- `TestSearchAndReportExports` — JSON and Excel export structure

**Coverage:**
- `_count_mapping` — matched/unmatched counting
- `_generate_filename` — timestamped filename generation
- `_generate_csv_with_metadata` — CSV header rows
- `export_search_json` — JSON structure validation
- `generate_search_excel` — Excel workbook generation with sheets
- `build_report_json` — Report JSON payload structure

**Dependencies:** `pandas`, `openpyxl`

</details>

<details>
<summary><strong>test_flags_and_plugins.py</strong> - Flag and Registry Contracts</summary>

Tests flag validation, plugin registry behaviour, and pipeline integration.

**Test Classes:**
- `TestFlagValidation` — validates `validate_flags` and `map_element_flags`
- `TestPluginRegistry` — duplicate rejection and detector execution
- `TestPipelineSmoke` — end-to-end parsing with real XML fixtures

**Coverage:**
- Unknown flags are removed during validation
- Invalid value types are rejected
- Duplicate pattern IDs raise `ValueError`
- `run_all` executes registered detectors
- `parse_xml` returns expected output structure

**Fixture Dependency:** Requires at least one XML file in `xml_examples/`

</details>

<details>
<summary><strong>test_namespace_utils.py</strong> - Namespace Helpers</summary>

Tests namespace handling utilities from `utils/parsing/namespace_utils.py`.

**Test Class:** `TestNamespaceUtils`

**Coverage:**
- `_to_emis_path` — XPath transformation
- `find_ns` / `findall_ns` — bare and namespaced tag lookup
- `get_text_ns` — text extraction with trimming
- `unique_elements` — deduplication by element identity
- `get_child_text_any` — candidate tag text lookup
- `get_attr_any` — namespaced attribute lookup
- `find_child_any` — candidate tag element lookup

**Test XML:** Mixed namespace content with `emis:` and `other:` prefixes

</details>

<details>
<summary><strong>test_parsing_report_parser.py</strong> - Report Parsing</summary>

Tests report parsing for list, audit, and aggregate report types.

**Test Class:** `TestReportParser`

**Coverage:**
- List reports: column groups, columns, sort configuration, criteria
- Aggregate reports: groups, statistical groups, result blocks
- Audit reports: population references, custom aggregates

**Validates:**
- Column group structure and metadata
- Sort configuration capture
- Criteria parsing with value sets
- `CodeStore` integration for code storage

</details>

<details>
<summary><strong>test_performance.py</strong> - Performance and Memory</summary>

Tests performance controls, metrics display, and memory efficiency.

**Test Classes:**
- `TestPerformanceOptimisations` — controls, metrics, environment detection
- `TestMemoryOptimisation` — memory-efficient XML parsing

**Coverage:**
- `render_performance_controls` settings structure
- `display_performance_metrics` markdown output
- Memory measurement with `psutil`
- XML size classification
- Cloud environment detection
- Parse time benchmarks (small and large XML)

**Large XML Generation:** Dynamically generates XML with 100+ valuesets for stress testing

</details>

<details>
<summary><strong>test_plugin_harness.py</strong> - Standalone Plugin Testing</summary>

Demonstrates external plugin authoring and execution without modifying the codebase.

**Test Class:** `TestStandalonePluginHarness`

**Coverage:**
- External plugin loading from temporary files
- Plugin execution against inline XML
- Plugin execution against `xml_examples/` fixtures
- `PatternRegistry` standalone registration

**Helper Functions:**
- `_write_temp_plugin(source_code)` — writes plugin to temp file
- `_load_detector(plugin_path, detector_name)` — dynamically loads detector
- `_first_element_by_localname(root, local_name)` — finds element by local tag

**Use Case:** Allows testing new plugins before integrating into the codebase

</details>

<details>
<summary><strong>test_search_parser.py</strong> - Search Parsing</summary>

Tests search parsing with criteria groups, dependencies, and code storage.

**Test Class:** `TestSearchParser`

**Coverage:**
- Search flags extraction (id, folder, parent reference)
- Criteria group parsing (operators, actions)
- Population criteria references
- Value set key generation and `CodeStore` storage
- Dependency collection (parent and population references)

</details>

<details>
<summary><strong>test_session_state.py</strong> - Session State Management</summary>

Tests session state keys, groups, and cache utilities.

**Test Classes:**
- `TestSessionStateKeys` — key constants exist and have correct values
- `TestSessionStateGroups` — group membership validation
- `TestSessionStateCleanup` — `clear_all_except_core` behaviour
- `TestSnomedCache` — cache roundtrip and expiry

**Mocking:** Uses `@patch("streamlit.session_state", new_callable=dict)`

</details>

<details>
<summary><strong>test_snomed_translation.py</strong> - SNOMED Translation</summary>

Tests EMIS to SNOMED translation with deduplication and filtering.

**Test Class:** `TestSnomedTranslation`

**Coverage:**
- Clinical vs medication classification
- Deduplication modes (`unique_codes` vs `unique_per_entity`)
- EMISINTERNAL entries excluded from export and cache
- Cache update verification

**Mocking:** Patches `clear_expired_snomed_cache`, `get_cached_snomed_mappings`, `update_snomed_cache`

</details>

<details>
<summary><strong>test_structure_parser.py</strong> - Structure Parsing</summary>

Tests structure parsing and folder tree enrichment.

**Test Class:** `TestStructureParser`

**Coverage:**
- Folder and entity extraction from `parse_structure`
- Search dependency detection
- `StructureEnricher` folder tree building
- Nested report attachment to searches
- Dependency graph generation

**Dynamic Import:** Loads `StructureEnricher` via `importlib` to avoid UI dependencies

</details>

---

## Test Patterns and Conventions

### XML Test Fixtures

Tests use inline XML strings with the EMIS namespace:

```python
NS = {"emis": "http://www.e-mis.com/emisopen"}

xml = """
<emis:criterion xmlns:emis="http://www.e-mis.com/emisopen">
    <emis:table>EVENTS</emis:table>
</emis:criterion>
"""
elem = ET.fromstring(xml)
```

### Mocking Streamlit

Session state and UI components are mocked to run without a Streamlit runtime:

```python
from unittest.mock import patch

@patch("streamlit.session_state", new_callable=dict)
def test_cache_roundtrip(self, mock_state):
    mock_state["key"] = "value"
    # Test logic here
```

### Plugin Testing Pattern

For testing plugins in isolation:

```python
from utils.pattern_plugins.base import PatternContext, PatternResult

def _ctx(inner_xml: str) -> PatternContext:
    xml = f'<emis:criterion xmlns:emis="{NS["emis"]}">{inner_xml}</emis:criterion>'
    elem = ET.fromstring(xml)
    return PatternContext(element=elem, namespaces=NS)

# Usage
ctx = _ctx("<emis:table>EVENTS</emis:table>")
result = my_plugin.detect_something(ctx)
```

### CodeStore Testing

Tests use `CodeStore` directly without caching layers:

```python
from utils.caching.code_store import CodeStore

code_store = CodeStore()
code_store.add_or_ref(
    key=("111", "VS-1", "SNOMED_CONCEPT"),
    data={"code_value": "111", "display_name": "Test"},
    source_guid="SEARCH-1"
)
stored = code_store.get_code(("111", "VS-1", "SNOMED_CONCEPT"))
```

---

## Adding New Tests

### Checklist

1. **Create test file** in `tests/` with `test_` prefix
2. **Import dependencies** — use relative imports for application modules
3. **Create test class** inheriting from `unittest.TestCase`
4. **Write test methods** with `test_` prefix
5. **Use descriptive names** — method name should describe what is being tested
6. **Mock external dependencies** — Streamlit, file I/O, network calls
7. **Include docstrings** for complex test logic
8. **Run locally** before committing

### Example Template

```python
"""
Description of what this test file covers.
"""

import unittest
from unittest.mock import patch

from utils.module_under_test import function_to_test


class TestMyFeature(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.sample_data = {...}

    def test_positive_case(self):
        """Test expected behaviour with valid input."""
        result = function_to_test(self.sample_data)
        self.assertEqual(result, expected_value)

    def test_edge_case(self):
        """Test behaviour with edge case input."""
        result = function_to_test(None)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
```

---

## Fixture Requirements

Some tests require external fixtures:

| Test File | Fixture | Location |
|-----------|---------|----------|
| `test_flags_and_plugins.py` | XML files | `xml_examples/*.xml` |
| `test_plugin_harness.py` | XML files | `xml_examples/*.xml` |

Ensure at least one valid EMIS XML file exists in `xml_examples/` before running the full test suite.

---

## CI/Release Checks

**Recommended pre-release commands:**

```bash
# Run all tests
python -m unittest discover tests -v

# Alternative with pytest
python -m pytest tests/ -v

# Run specific category
python -m unittest tests.test_builtin_plugins tests.test_flags_and_plugins -v
```

**Expected output:** All tests should pass with status `OK`

**Streamlit warnings:** `No runtime found, using MemoryCacheStorageManager` warnings are expected and harmless when running outside the Streamlit runtime.

---

## Related Documentation

- **[Plugin Development Guide](../flags-and-plugins/plugins.md)** — Plugin creation and testing
- **[Flags Technical Guide](../flags-and-plugins/flags.md)** — Flag definitions
- **[Module Architecture](modules.md)** — System overview
- **[Project Structure](../project-structure.md)** — Repository layout

---

*Last Updated: 3rd February 2026*
*Application Version: 3.0.0*
