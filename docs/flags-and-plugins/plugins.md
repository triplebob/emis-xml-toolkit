# ClinXML v3 Pattern Plugin Guide

## Overview

This guide explains the pattern-plugin system used by ClinXML v3:

- What plugins do and how they work
- Where they run in the parsing pipeline
- Current plugin inventory and emitted flags
- How to create new plugins safely
- How plugin changes interact with the flag registry

**Related guide:** [Flags Technical Guide](flags.md)

---

## Core Architecture

The plugin system is a lightweight detector framework layered on top of XML parser stages.
Each detector inspects one element context and can emit a structured flag payload.

### Data Contracts

<details>
<summary><strong>PatternContext</strong> - Input to plugins</summary>

Defined in `utils/pattern_plugins/base.py`:

| Property | Type | Description |
|----------|------|-------------|
| `element` | `xml.etree.ElementTree.Element` | Current XML element |
| `namespaces` | `Dict[str, str]` | Namespace map for lookups |
| `path` | `Optional[str]` | Path hint |
| `container_info` | `Optional[Dict]` | Contextual metadata |

```python
@dataclass
class PatternContext:
    element: ET.Element
    namespaces: Dict[str, str]
    path: Optional[str] = None
    container_info: Optional[Dict[str, Any]] = None
```

</details>

<details>
<summary><strong>PatternResult</strong> - Output from plugins</summary>

Defined in `utils/pattern_plugins/base.py`:

| Property | Type | Description |
|----------|------|-------------|
| `id` | `str` | Pattern identifier |
| `description` | `str` | Short description of match |
| `flags` | `Dict[str, Any]` | Key/value flag payload |
| `confidence` | `str` | `low`, `medium`, or `high` |
| `notes` | `Optional[List[str]]` | Additional notes |

```python
@dataclass
class PatternResult:
    id: str
    description: str
    flags: Dict[str, Any]
    confidence: str = "medium"
    notes: List[str] = field(default_factory=list)
```

</details>

<details>
<summary><strong>Helper Functions</strong> - Shared utilities for plugins</summary>

Defined in `utils/pattern_plugins/base.py`:

| Function | Signature | Description |
|----------|-----------|-------------|
| `tag_local` | `(elem: ET.Element) -> str` | Returns the local name of an element, stripping any namespace prefix |
| `find_first` | `(elem, namespaces, *queries) -> Optional[ET.Element]` | Tries each XPath query in order, returns the first match (avoids ElementTree truthiness issues) |

```python
def tag_local(elem: ET.Element) -> str:
    """Return the local name of an element, stripping any namespace."""
    return elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag


def find_first(elem: ET.Element, namespaces: Optional[Dict[str, str]], *queries: str) -> Optional[ET.Element]:
    """Return the first element found for the given query list without truthiness checks."""
    ns = namespaces or {}
    for query in queries:
        node = elem.find(query, ns)
        if node is not None:
            return node
    return None
```

**Why use these helpers?**
- `tag_local`: Consistent tag-name extraction across namespaced and non-namespaced XML
- `find_first`: Avoids ElementTree deprecation warnings caused by implicit boolean evaluation of XML elements (e.g., `elem.find(...) or elem.find(...)` pattern)

</details>

### Detector Signature

A detector is `Callable[[PatternContext], Optional[PatternResult]]`.

Return `None` when no match is found.

---

## Registration and Loading

**Decorator:** `@register_pattern("pattern_id")`

**Registry:** Global `pattern_registry` in `utils/pattern_plugins/registry.py`

**Behaviour:**
- Duplicate pattern IDs raise `ValueError`
- `load_all_modules("utils.pattern_plugins")` imports all plugin modules once per process

<details>
<summary><strong>Example: Plugin Registration</strong></summary>

```python
from .registry import register_pattern
from .base import PatternContext, PatternResult, find_first, tag_local

@register_pattern("my_pattern_id")
def detect_my_pattern(ctx: PatternContext):
    # Guard: only process criterion elements
    if tag_local(ctx.element) != "criterion":
        return None

    ns = ctx.namespaces

    # Match logic using find_first (handles namespace fallback safely)
    hit = find_first(ctx.element, ns, ".//targetTag", ".//emis:targetTag")
    if hit is None:
        return None

    return PatternResult(
        id="my_pattern_id",
        description="Found target pattern",
        flags={
            "my_flag": True,
        },
        confidence="medium",
    )
```

</details>

---

## Execution Points

Plugins run in three parser stages:

| Stage | Function | Location |
|-------|----------|----------|
| Search parsing | `parse_search(...)` | `utils/parsing/node_parsers/search_parser.py` |
| Report parsing | `parse_report(...)` | `utils/parsing/node_parsers/report_parser.py` |
| Criterion parsing | `parse_criterion(...)` | `utils/parsing/node_parsers/criterion_parser.py` |

**At each stage:**
1. `pattern_registry.run_all(context)` collects all `PatternResult`s
2. `map_element_flags(...)` merges plugin flags + structural defaults
3. `validate_flags(...)` drops unknown/invalid keys using `FLAG_DEFINITIONS`

**Note:** `parse_xml(..., run_patterns=True)` can also return raw top-level `pattern_results`, but the cached v3 runtime path generally uses `run_patterns=False` and relies on parser-stage plugin usage.

---

## Current Plugin Inventory

<details>
<summary><strong>column_filters.py</strong></summary>

| Property | Value |
|----------|-------|
| Pattern ID | `column_filters` |
| Purpose | Parse `columnValue` filter blocks, including range/single-value structures |
| Primary flags | `column_filters` |

</details>

<details>
<summary><strong>demographics.py</strong></summary>

| Property | Value |
|----------|-------|
| Pattern IDs | `demographics_lsoa`, `demographics_geo` |
| Purpose | Detect LSOA/geographic demographics criteria |
| Primary flags | `is_patient_demographics`, `demographics_type`, `demographics_confidence` |

</details>

<details>
<summary><strong>emisinternal.py</strong></summary>

| Property | Value |
|----------|-------|
| Pattern ID | `emisinternal_classification` |
| Purpose | Extract EMISINTERNAL filter value sets with context |
| Primary flags | `has_emisinternal_filters`, `emisinternal_values`, `emisinternal_entries`, `emisinternal_all_values` |

</details>

<details>
<summary><strong>enterprise.py</strong></summary>

| Property | Value |
|----------|-------|
| Pattern IDs | `enterprise_metadata`, `qof_contract` |
| Purpose | Detect enterprise and contract/QOF metadata |
| Primary flags | `enterprise_reporting_level`, `version_independent_guid`, `organisation_associations`, `qmas_indicator`, `contract_information_needed`, `contract_target` |

</details>

<details>
<summary><strong>logic.py</strong></summary>

| Property | Value |
|----------|-------|
| Pattern ID | `logic_negation_and_actions` |
| Purpose | Detect negation/operators/actions in criteria |
| Primary flags | `negation`, `member_operator`, `action_if_true`, `action_if_false` |

</details>

<details>
<summary><strong>medication.py</strong></summary>

| Property | Value |
|----------|-------|
| Pattern ID | `medication_code_system` |
| Purpose | Identify medication code systems and subtype label |
| Primary flags | `is_medication_code`, `code_system`, `medication_type_flag` |

</details>

<details>
<summary><strong>parameters.py</strong></summary>

| Property | Value |
|----------|-------|
| Pattern ID | `parameters` |
| Purpose | Detect parameter usage and scope |
| Primary flags | `has_parameter`, `parameter_names`, `has_global_parameters`, `has_local_parameters` |

</details>

<details>
<summary><strong>population.py</strong></summary>

| Property | Value |
|----------|-------|
| Pattern ID | `population_references` |
| Purpose | Collect `populationCriterion` report GUID references |
| Primary flags | `population_reference_guid` |

</details>

<details>
<summary><strong>refsets.py</strong></summary>

| Property | Value |
|----------|-------|
| Pattern ID | `refset_detection` |
| Purpose | Detect refset/pseudo-refset structures |
| Primary flags | `is_refset`, `is_pseudo_refset`, `is_pseudo_member` |

</details>

<details>
<summary><strong>relationships.py</strong></summary>

| Property | Value |
|----------|-------|
| Pattern ID | `linked_relationship` |
| Purpose | Detect linked-criteria relationship type and columns |
| Primary flags | `relationship_type`, `parent_column`, `child_column` |

</details>

<details>
<summary><strong>restrictions.py</strong></summary>

| Property | Value |
|----------|-------|
| Pattern IDs | `restriction_latest_earliest`, `restriction_test_attribute` |
| Purpose | Detect restriction blocks (latest/earliest and test-attribute) |
| Primary flags | `has_restriction`, `restriction_type`, `record_count`, `ordering_direction`, `ordering_column`, `has_test_conditions`, `test_condition_column`, `test_condition_operator` |

</details>

<details>
<summary><strong>source_containers.py</strong></summary>

| Property | Value |
|----------|-------|
| Pattern ID | `container_heuristics` |
| Purpose | Infer `container_type` from criterion/report structure |
| Primary flags | `container_type` |

</details>

<details>
<summary><strong>temporal.py</strong></summary>

| Property | Value |
|----------|-------|
| Pattern IDs | `temporal_single_value`, `temporal_range` |
| Purpose | Detect temporal filters in single-value and range forms |
| Primary flags | `has_temporal_filter`, `temporal_variable_value`, `temporal_unit`, `temporal_relation`, `relative_to`, `range_from_*`, `range_to_*` |

</details>

<details>
<summary><strong>value_sets.py</strong></summary>

| Property | Value |
|----------|-------|
| Pattern IDs | `value_set_properties`, `value_set_description_handling` |
| Purpose | Detect library/inactive and description-shape patterns |
| Primary flags | `is_library_item`, `inactive`, `has_explicit_valueset_description`, `use_guid_as_valueset_description`, `has_individual_code_display_names` |

</details>

---

## Registry Interaction Rules

Plugin flags pass through `validate_flags(...)` in `map_element_flags(...)`.

**This means:**
- Plugin flag keys must exist in `FLAG_DEFINITIONS`
- Plugin values must satisfy registry validators/domains
- Otherwise the key is silently removed from canonical flags

**Important:** If you add a new plugin-emitted flag, update `utils/metadata/flag_registry.py` in the same change.

---

## Creating a New Plugin

<details>
<summary><strong>Minimal Template</strong></summary>

```python
"""
My pattern detection plugin.

Detects [describe what it detects] in EMIS XML.
"""

from .registry import register_pattern
from .base import PatternContext, PatternResult, find_first, tag_local


@register_pattern("my_new_pattern")
def detect_my_new_pattern(ctx: PatternContext):
    """Detect my new pattern in XML elements."""
    # Guard: only process criterion elements
    if tag_local(ctx.element) != "criterion":
        return None

    ns = ctx.namespaces

    # Match logic using find_first (handles namespace fallback safely)
    hit = find_first(ctx.element, ns, ".//someTag", ".//emis:someTag")
    if hit is None:
        return None

    # Extract values
    value = (hit.text or "").strip()

    return PatternResult(
        id="my_new_pattern",
        description="Detected my new pattern",
        flags={
            "my_new_flag": True,
            "my_value": value,
        },
        confidence="medium",
    )
```

</details>

<details>
<summary><strong>Implementation Checklist</strong></summary>

1. **Add the plugin file** under `utils/pattern_plugins/`
2. **Register detector(s)** with unique IDs using `@register_pattern`
3. **Add any new flag keys** to `FLAG_DEFINITIONS` in `utils/metadata/flag_registry.py`
4. **Ensure value types** satisfy validators
5. **Confirm parser-stage behaviour** where the plugin should apply
6. **Add tests** for positive and negative cases
7. **Update docs** (`flags.md` and this file)

</details>

---

## Updating an Existing Plugin

- Keep pattern IDs stable unless there is a migration reason
- Prefer additive flags over changing existing semantics unexpectedly
- If changing value shape, update validators and all consumers in the same PR
- Re-check UI/report/export paths that rely on the changed flags

---

## Testing Guidance

**Recommended coverage for plugin changes:**

- Mixed namespace XML (`<tag>` and `<emis:tag>` variants)
- Plugin match and non-match cases
- Validation pass/fail behaviour for emitted flags
- Downstream usage (at least one consumer path)

**Useful existing parser tests:**

| Test File | Purpose |
|-----------|---------|
| `tests/test_search_parser.py` | Search parsing tests |
| `tests/test_parsing_report_parser.py` | Report parsing tests |
| `tests/test_structure_parser.py` | Structure parsing tests |
| `tests/test_builtin_plugins.py` | Built-in plugin regression tests |
| `tests/test_flags_and_plugins.py` | Registry and validation contracts |
| `tests/test_plugin_harness.py` | Standalone plugin smoke tests |
| `tests/test_namespace_utils.py` | Namespace helper behaviour |
| `tests/test_exports.py` | Export path integration checks |
| `tests/test_snomed_translation.py` | SNOMED translation behaviour |

---

## Common Pitfalls

| Pitfall | Result |
|---------|--------|
| Emitting a new flag without updating `FLAG_DEFINITIONS` | Flag gets dropped |
| Emitting wrong value type | Flag gets dropped by validator |
| Using `elem.find(...) or elem.find(...)` pattern | ElementTree deprecation warnings; use `find_first` instead |
| Adding expensive traversal logic without guards | Performance degradation |
| Duplicating parser-owned logic | Inconsistent results |

---

## Related Documentation

- **[Flags Technical Guide](flags.md)** - Flag definitions and validation
- **[Test Suite Reference](../architecture/testing.md)** - Test coverage and patterns
- **[Module Architecture](../architecture/modules.md)** - System overview
- **[Namespace Handling](../architecture/namespace-handling.md)** - XML namespace utilities

---

*Last Updated: 3rd February 2026*
*Application Version: 3.0.0*
