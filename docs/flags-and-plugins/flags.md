# ClinXML v3 Flags Technical Guide

## Overview

This guide documents the v3 flag system used across parsing, metadata enrichment, UI shaping, and exports.

**Scope:**
- Canonical flags defined in `utils/metadata/flag_registry.py`
- Where flags are generated in the parsing pipeline
- How flags flow into `CodeStore`, UI rows, and feature tabs
- How to safely add, change, or retire flags

**Related guide:** [Plugin Development Guide](plugins.md)

---

## Runtime Flag Flow

```text
XML element
  -> pattern plugins (PatternResult.flags)
  -> map_element_flags(...)
     -> validate_flags(...) against FLAG_DEFINITIONS
  -> parser-level enrichment (search/report/criterion specific flags)
  -> value_set mapping + CodeStore dedup
  -> flatten/enrich/serialise for UI and exports
```

**Primary code paths:**
- `utils/parsing/pipeline.py`
- `utils/parsing/node_parsers/search_parser.py`
- `utils/parsing/node_parsers/report_parser.py`
- `utils/parsing/node_parsers/criterion_parser.py`
- `utils/parsing/node_parsers/value_set_parser.py`
- `utils/metadata/flag_mapper.py`
- `utils/metadata/flag_registry.py`

---

## Validation Model

`FLAG_DEFINITIONS` is the canonical registry. Each entry defines:

| Property | Description |
|----------|-------------|
| `name` | Flag identifier |
| `description` | User-friendly description |
| `required` | Whether the flag is required (default: False) |
| `domain` | Optional list of valid values |
| `validator` | Optional validation function |

**Validation behaviour in `validate_flags(flags)`:**
- Unknown keys are dropped
- Known keys with invalid values are dropped
- Known keys with valid values are retained
- Keys missing from the input are not auto-added

**Important nuance:** `required=True` is enforced only when a key is present with `None`. Missing required keys are not currently raised as errors.

<details>
<summary><strong>Example: Flag Definition</strong></summary>

```python
from utils.metadata.flag_registry import FlagDefinition, _is_bool, _non_empty_str

# Boolean flag with validator
FlagDefinition(
    name="is_refset",
    description="Refset flag",
    validator=_is_bool
)

# Constrained domain flag
FlagDefinition(
    name="logical_table_name",
    description="Logical table name",
    domain=["PATIENTS", "EVENTS", "MEDICATION_ISSUES", "MEDICATION_COURSES", "GPES_JOURNALS"]
)

# Required string flag
FlagDefinition(
    name="element_id",
    description="Element identifier",
    required=True,
    validator=_non_empty_str
)
```

</details>

---

## Canonical Flag Catalogue

**Total registry-defined flags: 95**

<details>
<summary><strong>Identity Flags (3)</strong></summary>

| Flag | Description | Validator |
|------|-------------|-----------|
| `element_type` | High-level element classification | Required |
| `element_id` | Element identifier | Required, non-empty string |
| `element_guid` | GUID identifier where applicable | Non-empty string |

</details>

<details>
<summary><strong>Hierarchy and Structure Flags (9)</strong></summary>

| Flag | Description | Validator |
|------|-------------|-----------|
| `parent_search_guid` | Dependency to parent search/report | Non-empty string |
| `criteria_group_id` | Search criteria group id | Non-empty string |
| `criterion_id` | Criterion id reference | Non-empty string |
| `linked_criterion_parent_id` | Linked criterion parent id | Non-empty string |
| `column_group_id` | List report column group id | Non-empty string |
| `logical_table_name` | Logical table | Domain: PATIENTS, EVENTS, MEDICATION_ISSUES, MEDICATION_COURSES, GPES_JOURNALS |
| `population_reference_guid` | Referenced population/report GUID list | List of strings |
| `folder_id` | Owning folder id | Non-empty string |
| `folder_path` | Resolved folder path list | List of strings |

</details>

<details>
<summary><strong>XML Source Location Flags (2)</strong></summary>

| Flag | Description | Validator |
|------|-------------|-----------|
| `xpath_location` | XPath-style location marker | Non-empty string |
| `xml_tag_name` | Source XML local tag name | Non-empty string |

</details>

<details>
<summary><strong>Code and ValueSet Metadata Flags (18)</strong></summary>

| Flag | Description | Validator |
|------|-------------|-----------|
| `code_system` | Code system name | - |
| `valueSet_guid` | Value set identifier | - |
| `valueSet_description` | Value set description | - |
| `is_clinical_code` | Clinical-code marker | Boolean |
| `is_medication_code` | Medication-code marker | Boolean |
| `is_library_item` | Library-item marker | Boolean |
| `code_value` | Code value string | Non-empty string |
| `display_name` | Display label | Non-empty string |
| `include_children` | Include-children flag | Boolean |
| `is_refset` | Refset marker | Boolean |
| `is_emisinternal` | EMISINTERNAL marker | Boolean |
| `is_pseudo_refset` | Pseudo-refset container marker | Boolean |
| `is_pseudo_member` | Pseudo-refset member marker | Boolean |
| `inactive` | Inactive marker | Boolean |
| `legacy_value` | Legacy value mapping | - |
| `cluster_code` | Cluster-code marker | - |
| `exception_code` | Exception code | - |

</details>

<details>
<summary><strong>Relationship Flags (11)</strong></summary>

| Flag | Description |
|------|-------------|
| `relationship_type` | Inferred relationship type |
| `parent_column` | Relationship parent column |
| `child_column` | Relationship child column |
| `range_from_operator` | Range-from operator |
| `range_from_value` | Range-from value |
| `range_from_unit` | Range-from unit |
| `range_from_relation` | Range-from relation |
| `range_to_operator` | Range-to operator |
| `range_to_value` | Range-to value |
| `range_to_unit` | Range-to unit |
| `range_to_relation` | Range-to relation |

</details>

<details>
<summary><strong>Logic and Context Flags (4)</strong></summary>

| Flag | Description |
|------|-------------|
| `negation` | Include/exclude negation |
| `member_operator` | Criteria group operator |
| `action_if_true` | Action branch when true |
| `action_if_false` | Action branch when false |

</details>

<details>
<summary><strong>Filter and Classification Flags (20)</strong></summary>

| Flag | Description |
|------|-------------|
| `column_name` | List of column names in scope |
| `column_display_name` | Display column label |
| `in_not_in` | Inclusion/exclusion operator |
| `demographics_type` | Demographics subtype |
| `demographics_confidence` | Demographics confidence marker |
| `is_patient_demographics` | Demographics marker |
| `has_parameter` | Parameter presence marker |
| `parameter_names` | Parameter names list |
| `has_global_parameters` | Has global parameters |
| `has_local_parameters` | Has local parameters |
| `has_emisinternal_filters` | EMISINTERNAL filter marker |
| `emisinternal_values` | Flattened EMISINTERNAL values |
| `emisinternal_entries` | Structured EMISINTERNAL blocks |
| `emisinternal_all_values` | Any EMISINTERNAL all-values usage |
| `medication_type_flag` | Medication subtype label |
| `column_filters` | Parsed column filter metadata |
| `has_explicit_valueset_description` | ValueSet description explicitly present |
| `use_guid_as_valueset_description` | ValueSet description falls back to GUID |
| `has_individual_code_display_names` | Values contain per-code display names |
| `linked_criteria` | Linked criteria metadata collection |

</details>

<details>
<summary><strong>Temporal Flags (5)</strong></summary>

| Flag | Description |
|------|-------------|
| `has_temporal_filter` | Temporal filtering marker |
| `temporal_variable_value` | Relative variable value (`Last`, `This`, etc.) |
| `temporal_unit` | Temporal unit |
| `temporal_relation` | Temporal relation |
| `relative_to` | Relative baseline anchor |

</details>

<details>
<summary><strong>Restriction Flags (9)</strong></summary>

| Flag | Description |
|------|-------------|
| `has_restriction` | Restriction marker |
| `restriction_type` | Restriction subtype |
| `record_count` | Count in latest/earliest restrictions |
| `ordering_direction` | Ordering direction |
| `ordering_column` | Ordering column |
| `has_test_conditions` | Restriction test-attribute marker |
| `test_condition_column` | Restriction condition column |
| `test_condition_operator` | Restriction condition operator |

</details>

<details>
<summary><strong>Rendering and Export Context Flags (10)</strong></summary>

| Flag | Description |
|------|-------------|
| `source_file_name` | Source file name marker |
| `source_guid` | Source element GUID/id |
| `source_type` | Source element type |
| `container_type` | Source container classification |
| `search_date` | Search date metadata |
| `report_creation_time` | Report creation timestamp |
| `report_author_name` | Report author name |
| `report_author_user_id` | Report author id |
| `include_in_export` | Export inclusion marker |
| `export_category` | Export category label |

</details>

<details>
<summary><strong>Enterprise and Contract/QOF Flags (6)</strong></summary>

| Flag | Description |
|------|-------------|
| `enterprise_reporting_level` | Enterprise reporting level |
| `organisation_associations` | Enterprise associations list |
| `version_independent_guid` | Version-independent GUID |
| `qmas_indicator` | QMAS indicator value |
| `contract_information_needed` | Contract score-needed marker |
| `contract_target` | Contract target integer |

</details>

---

## Parser-Enriched Runtime Flags

These flags are set after initial validation and can exist at runtime even though they are not in `FLAG_DEFINITIONS`:

| Flag | Description |
|------|-------------|
| `description` | Element description |
| `source_name` | Source name context |
| `parent_type` | Parent element type |
| `score_range` | Score range for contract criteria |
| `is_consolidated` | Consolidated LSOA marker |
| `consolidated_count` | Count of consolidated LSOA codes |
| `consolidated_lsoa_codes` | Consolidated LSOA code list |
| `parent_column_display_name` | Parent column display name |
| `child_column_display_name` | Child column display name |
| `temporal_range` | Temporal range description |

If any of these should be treated as canonical, add them to `FLAG_DEFINITIONS` with appropriate validators.

---

## Where Flags Are Produced

### Plugin-derived (pre-validation)

- Plugin modules under `utils/pattern_plugins/`
- Aggregated in `map_element_flags(...)`
- Validated by `validate_flags(...)`

<details>
<summary><strong>Example: Plugin Flag Emission</strong></summary>

```python
from utils.pattern_plugins.registry import register_pattern
from utils.pattern_plugins.base import PatternContext, PatternResult

@register_pattern("my_pattern")
def detect_my_pattern(ctx: PatternContext):
    elem = ctx.element
    ns = ctx.namespaces

    # Match logic
    hit = elem.find(".//someTag", ns) or elem.find(".//emis:someTag", ns)
    if hit is None:
        return None

    return PatternResult(
        id="my_pattern",
        description="Detected my pattern",
        flags={
            "my_flag": True,
            "my_value": hit.text,
        },
        confidence="medium",
    )
```

</details>

### Parser-derived (post-validation)

- Search/report/criterion parsers add context-specific flags directly
- Value set parser enriches code-level metadata before insertion into `CodeStore`

### Value-level mapping

- `map_value_set_flags(...)` adds `code_value`, `display_name`, `include_children`, `inactive`, etc.
- `parse_value_sets(...)` applies pseudo-refset, EMISINTERNAL, and description fallback behaviour

---

## Where Flags Are Consumed

**Key consumers:**

| Module | Usage |
|--------|-------|
| `utils/caching/code_store.py` | Deduplicated code metadata |
| `utils/caching/xml_cache.py` | Flattened source-context rows |
| `utils/metadata/serialisers.py` | UI/export row shaping |
| `utils/metadata/report_filtering.py` | Report filtering logic |
| `utils/ui/tabs/search_browser/` | Search viewer display |
| `utils/ui/tabs/report_viewer/` | Report viewer display |

---

## How To Add a New Flag

<details>
<summary><strong>Step-by-Step Guide</strong></summary>

**1. Define the flag in `utils/metadata/flag_registry.py`**

```python
FLAG_DEFINITIONS["my_new_flag"] = FlagDefinition(
    name="my_new_flag",
    description="My new flag description",
    validator=_is_bool,  # or domain=[...] or custom validator
)
```

**2. Emit the flag in the correct producer**

For reusable detection logic, use a plugin:
```python
# In utils/pattern_plugins/my_plugin.py
return PatternResult(
    id="my_pattern",
    description="...",
    flags={"my_new_flag": True},
    confidence="high",
)
```

For structural/context logic, emit in the parser:
```python
# In utils/parsing/node_parsers/search_parser.py
entity_flags["my_new_flag"] = some_value
```

**3. Ensure the value shape matches the validator**

If validator is `_is_bool`, emit `True` or `False`.
If domain is `["A", "B"]`, emit only `"A"` or `"B"`.

**4. Wire downstream usage**

Update consumers:
- `CodeStore` (if code-level flag)
- Serialisation/export logic
- UI consumers as needed

**5. Add or update tests**

- Parser tests: `tests/test_search_parser.py`, `tests/test_parsing_report_parser.py`
- Built-in plugin regression tests: `tests/test_builtin_plugins.py`
- Flag/plugin contract tests: `tests/test_flags_and_plugins.py`
- Plugin harness tests: `tests/test_plugin_harness.py`
- Namespace helper tests: `tests/test_namespace_utils.py`
- Related downstream checks: `tests/test_exports.py`, `tests/test_snomed_translation.py`, `tests/test_code_store.py`
- Behaviour tests for target tab/export path

</details>

---

## How To Update or Retire a Flag

### Changing value type
1. Update registry validator/domain first
2. Update all producers
3. Update all consumers

### Renaming a flag
1. Add compatibility mapping period where both keys are read
2. Update producers to emit new key
3. Update consumers to read new key
4. Remove old key after deprecation period

### Retiring a flag
1. Remove from all consumers first
2. Remove from producers
3. Remove from registry

---

## Practical Checklist

**Before merge:**

- [ ] Registry updated for canonical flags
- [ ] No plugin-emitted flag silently dropped by validation
- [ ] Parser outputs and UI consumers agree on key names
- [ ] Tests updated for new/changed behaviour
- [ ] Docs updated (`flags.md` and, if plugin logic changed, `plugins.md`)

---

## Related Documentation

- **[Plugin Development Guide](plugins.md)** - Creating pattern plugins
- **[Test Suite Reference](../architecture/testing.md)** - Test coverage and patterns
- **[Module Architecture](../architecture/modules.md)** - System overview
- **[Session State Management](../architecture/session-state-management.md)** - State handling

---

*Last Updated: 3rd February 2026*
*Application Version: 3.0.0*
