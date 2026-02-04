# EMIS XML Namespace Handling Reference

## Overview

ClinXML v3 handles mixed EMIS namespace formats through shared parsing helpers in `utils/parsing/namespace_utils.py`.
The goal is consistent behaviour when XML contains:

- Fully prefixed tags (`<emis:report>`)
- Unprefixed tags (`<report>`)
- Mixed usage inside the same subtree

---

## Namespace Capture and Normalisation

Namespace extraction happens in `utils/parsing/document_loader.py`:

**Process:**
1. `_extract_namespaces()` reads namespace declarations via `ElementTree.iterparse(..., events=("start-ns",))`
2. If extraction fails, a default map is applied: `{"emis": "http://www.e-mis.com/emisopen"}`
3. If `emis` is missing from the extracted map, it is added

**Result:** Downstream parsers always receive an `emis` namespace alias.

---

## Core Namespace Helpers

`utils/parsing/namespace_utils.py` provides the canonical helper set:

<details>
<summary><strong>find_ns(elem, tag, namespaces)</strong></summary>

Find first matching node (bare tag first, then `emis:` path).

```python
from utils.parsing.namespace_utils import find_ns

# Finds <name> or <emis:name>
name_elem = find_ns(report_elem, "name", namespaces)
```

</details>

<details>
<summary><strong>findall_ns(elem, tag, namespaces)</strong></summary>

Find all matching elements, combining bare + `emis:` matches, deduplicated by element identity.

```python
from utils.parsing.namespace_utils import findall_ns

# Finds all <criteriaGroup> and <emis:criteriaGroup>
groups = findall_ns(search_elem, "population/criteriaGroup", namespaces)
```

</details>

<details>
<summary><strong>get_text_ns(elem, tag, namespaces)</strong></summary>

Text extraction wrapper around `find_ns`.

```python
from utils.parsing.namespace_utils import get_text_ns

# Gets text from <name> or <emis:name>
name = get_text_ns(report_elem, "name", namespaces)
```

</details>

<details>
<summary><strong>find_child_any(parent, candidate_tags, namespaces)</strong></summary>

Find first matching child across multiple tag candidates.

```python
from utils.parsing.namespace_utils import find_child_any

# Finds first match among multiple possible tag names
author = find_child_any(elem, ["author", "createdBy", "owner"], namespaces)
```

</details>

<details>
<summary><strong>get_child_text_any(elem, candidate_tags, namespaces)</strong></summary>

Get text from first matching child across candidate tags.

```python
from utils.parsing.namespace_utils import get_child_text_any

# Gets text from first match among candidate tags
folder_id = get_child_text_any(elem, ["folder", "parentFolderId"], namespaces)
```

</details>

<details>
<summary><strong>get_attr_any(elem, candidate_attrs)</strong></summary>

Attribute lookup with localname fallback for namespaced attributes.

```python
from utils.parsing.namespace_utils import get_attr_any

# Gets attribute, checking both plain and namespaced variants
guid = get_attr_any(elem, ["guid", "id", "GUID"])
```

</details>

---

## Path Conversion

`_to_emis_path()` supports bare, nested, and descendant paths:

| Input | Output |
|-------|--------|
| `name` | `emis:name` |
| `criteria/criterion` | `emis:criteria/emis:criterion` |
| `.//population` | `.//emis:population` |

---

## Usage in the Parsing Pipeline

**Primary usage locations:**

| Module | Usage |
|--------|-------|
| `utils/parsing/node_parsers/search_parser.py` | Search element navigation |
| `utils/parsing/node_parsers/report_parser.py` | Report element navigation |
| `utils/parsing/node_parsers/criterion_parser.py` | Criterion element navigation |
| `utils/parsing/node_parsers/value_set_parser.py` | Value set extraction |
| `utils/parsing/node_parsers/structure_parser.py` | Structure analysis |
| `utils/metadata/flag_mapper.py` | Candidate-tag and candidate-attribute extraction |

**ElementClassifier** (`utils/parsing/element_classifier.py`) also applies dual-path discovery for top-level buckets by querying namespaced and plain paths, then deduplicating results.

---

## Implementation Patterns

### Preferred Pattern

```python
from utils.parsing.namespace_utils import find_ns, findall_ns, get_text_ns

# Single element lookup
name = get_text_ns(report_elem, "name", namespaces)

# Multiple element lookup
groups = findall_ns(search_elem, "population/criteriaGroup", namespaces)

# Optional element lookup
parent = find_ns(report_elem, "parent", namespaces)
if parent is not None:
    parent_id = parent.text
```

### For Variable Tag Names

```python
from utils.parsing.namespace_utils import find_child_any, get_child_text_any

# Multiple possible tag names
folder_id = get_child_text_any(elem, ["folder", "parentFolderId"], namespaces)

# Element lookup with fallback
author = find_child_any(elem, ["author", "createdBy"], namespaces)
```

---

## Important Edge Cases

### Element Fallback Logic

**Avoid** `a or b` with `ElementTree.find(...)` results for element fallback logic.

```python
# WRONG - empty element evaluates to False
elem = root.find("a") or root.find("b")  # May skip empty but present element

# CORRECT - explicit None check
elem = root.find("a")
if elem is None:
    elem = root.find("b")
```

**For plugin code**, use the `find_first` helper from `utils/pattern_plugins/base.py`:

```python
from utils.pattern_plugins.base import find_first

# Tries each query in order, returns first match
elem = find_first(root, namespaces, ".//tag", ".//emis:tag")
```

### Mixed Namespace Content

For mixed namespace content, helpers intentionally check both bare and namespaced forms. This handles XML like:

```xml
<emis:report>
    <name>Report Name</name>  <!-- bare tag -->
    <emis:criteria>           <!-- namespaced tag -->
        <criterion>...</criterion>
    </emis:criteria>
</emis:report>
```

### Namespaced Attributes

For namespaced attributes, `get_attr_any()` compares attribute local names so both plain and namespaced variants can resolve:

```python
# Handles both guid="abc" and emis:guid="abc"
guid = get_attr_any(elem, ["guid", "id"])
```

---

## Practical Rules for New Parsers

1. **Accept and pass through `namespaces`** in parser signatures
2. **Use `find_ns`/`findall_ns`/`get_text_ns`** instead of hardcoding `emis:` XPath in feature code
3. **Use candidate-based helpers** (`find_child_any`, `get_child_text_any`, `get_attr_any`) where schemas vary between XML variants
4. **Keep namespace fallbacks centralised** in `namespace_utils.py` rather than adding bespoke fallback logic per parser

---

## Related Documentation

- **[Module Architecture](modules.md)** - System overview
- **[Flags Technical Guide](../flags-and-plugins/flags.md)** - Flag system
- **[Plugin Development Guide](../flags-and-plugins/plugins.md)** - Pattern plugins

---

*Last Updated: 3rd February 2026*
*Application Version: 3.0.1*
