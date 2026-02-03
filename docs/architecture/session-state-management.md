# Session State Management Architecture

## Overview

ClinXML v3 centralises Streamlit session-state contracts in `utils/system/session_state.py`.
This module defines canonical keys, grouped key sets, lifecycle clear/reset helpers, and the in-session SNOMED mapping cache.

---

## Canonical Key Registry

`SessionStateKeys` is the single source of truth for session keys.

<details>
<summary><strong>Core Application State</strong></summary>

| Key | Description |
|-----|-------------|
| `XML_FILENAME` | Name of uploaded XML file |
| `XML_FILESIZE` | Size of uploaded XML file |
| `XML_CONTENT` | Decoded XML content string |
| `XML_RAW_BYTES` | Raw XML bytes |
| `UPLOADED_FILE` | Streamlit uploaded file object |
| `UPLOADED_FILENAME` | Uploaded filename |
| `IS_PROCESSING` | Processing in progress flag |

</details>

<details>
<summary><strong>Lookup Table Data</strong></summary>

| Key | Description |
|-----|-------------|
| `LOOKUP_ENCRYPTED_BYTES` | Encrypted parquet bytes |
| `EMIS_GUID_COL` | EMIS GUID column name |
| `SNOMED_CODE_COL` | SNOMED code column name |
| `LOOKUP_VERSION_INFO` | Lookup version metadata |

</details>

<details>
<summary><strong>SNOMED Cache</strong></summary>

| Key | Description |
|-----|-------------|
| `MATCHED_EMIS_SNOMED_CACHE` | Cached EMIS GUID to SNOMED mappings |
| `MATCHED_EMIS_SNOMED_TIMESTAMP` | Cache timestamp for TTL |

</details>

<details>
<summary><strong>User Preferences</strong></summary>

| Key | Description |
|-----|-------------|
| `CURRENT_DEDUPLICATION_MODE` | Code deduplication mode |
| `CHILD_VIEW_MODE` | Child code view mode |
| `DEBUG_MODE` | Debug mode toggle |
| `SESSION_ID` | Session identifier |
| `PROCESSED_FILES` | List of processed files |
| `CLINICAL_INCLUDE_REPORT_CODES` | Include report codes in clinical view |
| `CLINICAL_SHOW_CODE_SOURCES` | Show code sources in clinical view |

</details>

<details>
<summary><strong>Pipeline Outputs</strong></summary>

| Key | Description |
|-----|-------------|
| `PIPELINE_CODES` | Parsed clinical codes |
| `PIPELINE_ENTITIES` | Parsed entities (searches, reports) |
| `PIPELINE_FOLDERS` | Parsed folder structure |
| `XML_STRUCTURE_DATA` | XML structure analysis data |
| `CODE_STORE` | CodeStore instance |

</details>

<details>
<summary><strong>NHS Terminology Server</strong></summary>

| Key | Description |
|-----|-------------|
| `NHS_CONNECTION_STATUS` | Connection status |
| `EXPANSION_IN_PROGRESS` | Expansion in progress flag |
| `EXPANSION_STATUS` | Expansion status message |

</details>

<details>
<summary><strong>Dynamic Key Patterns</strong></summary>

| Pattern | Usage |
|---------|-------|
| `CACHED_SELECTED_REPORT_PREFIX` | Report selection caching |
| `SELECTED_TEXT_PREFIX` | Selected text caching |
| `CACHE_KEY_PREFIX` | Generic cache keys |
| `EXCEL_CACHE_PREFIX` | Excel export caching |
| `JSON_CACHE_PREFIX` | JSON export caching |
| `TREE_TEXT_PREFIX` | Tree visualisation caching |
| `NHS_TERMINOLOGY_CACHE_PREFIX` | NHS terminology caching |

</details>

---

## Using Session State Keys

Always use `SessionStateKeys` constants instead of raw strings:

```python
from utils.system.session_state import SessionStateKeys

# Reading state
codes = st.session_state.get(SessionStateKeys.PIPELINE_CODES, [])

# Writing state
st.session_state[SessionStateKeys.IS_PROCESSING] = True

# Checking existence
if SessionStateKeys.CODE_STORE in st.session_state:
    code_store = st.session_state[SessionStateKeys.CODE_STORE]
```

---

## Grouped Key Sets

`SessionStateGroups` defines logical collections used by bulk operations:

| Group | Keys Included |
|-------|---------------|
| `CORE_DATA` | XML file data and identifiers |
| `PROCESSING_STATE` | Processing flags and context |
| `RESULTS_DATA` | Pipeline outputs and derived data |
| `LOOKUP_DATA` | Lookup table and SNOMED cache |
| `USER_PREFERENCES` | User settings and modes |
| `NHS_TERMINOLOGY` | NHS terminology server state |
| `SYSTEM_MONITORING` | Memory and performance metrics |

These groups are used by reset helpers to keep clear behaviour consistent across the app.

---

## Lifecycle Clear and Reset Helpers

### Targeted Helpers

<details>
<summary><strong>clear_processing_state()</strong></summary>

Removes processing placeholders and processing flags.

**Use when:** Cancelling processing, error recovery.

</details>

<details>
<summary><strong>clear_results_state()</strong></summary>

Removes parsed outputs and derived result payloads.

**Use when:** Clearing results to force reparse.

</details>

<details>
<summary><strong>clear_export_state()</strong></summary>

Clears export-prefixed state keys and export cache manager stores.

**Use when:** Resetting export UI state.

</details>

<details>
<summary><strong>clear_report_state(report_type_name=None)</strong></summary>

Clears report selection/rendering state (scoped or global).

**Use when:** Switching reports, clearing report viewer state.

</details>

<details>
<summary><strong>clear_ui_state()</strong></summary>

Removes UI rendering keys while preserving user preferences.

**Use when:** Resetting UI without losing preferences.

</details>

<details>
<summary><strong>clear_analysis_state()</strong></summary>

Clears tree/analysis and generic cache-prefixed keys.

**Use when:** Resetting analysis caches.

</details>

<details>
<summary><strong>clear_pipeline_caches()</strong></summary>

Clears `@st.cache_data` parse/metadata/tab helper caches.

**Use when:** Forcing full reparse of cached data.

</details>

### File-Switch Helpers

<details>
<summary><strong>clear_for_new_xml_selection()</strong></summary>

Called when selecting a new file in `streamlit_app.py`.

**Actions:**
- Clears pipeline/results/UI/report state
- Removes file-bound and lookup-bound keys
- Resets `IS_PROCESSING`

</details>

<details>
<summary><strong>clear_for_new_xml()</strong></summary>

Full reset path used for reprocess/cancel flows.

**Actions:**
- Clears processing/export/analysis state
- Clears pipeline caches
- Cleans up dynamic cache keys

</details>

<details>
<summary><strong>clear_all_except_core()</strong></summary>

Preserves only core file keys, lookup keys, and user preferences.

**Use when:** Heavy reset while keeping essential state.

</details>

---

## SNOMED Mapping Cache

The SNOMED mapping cache is session-scoped with a 60-minute TTL.

### Cache Management Functions

| Function | Description |
|----------|-------------|
| `get_snomed_cache_ttl_minutes()` | Returns current TTL (60 minutes) |
| `is_snomed_cache_valid()` | Checks if cache is within TTL |
| `get_cached_snomed_mappings()` | Gets cached mappings dict |
| `update_snomed_cache(new_mappings)` | Updates cache with new mappings |
| `clear_expired_snomed_cache()` | Clears cache if expired |

### Cache Keys

| Key | Description |
|-----|-------------|
| `MATCHED_EMIS_SNOMED_CACHE` | Dict of EMIS GUID to SNOMED mappings |
| `MATCHED_EMIS_SNOMED_TIMESTAMP` | Timestamp when cache was last updated |

<details>
<summary><strong>Example: Using SNOMED Cache</strong></summary>

```python
from utils.system.session_state import (
    get_cached_snomed_mappings,
    update_snomed_cache,
    clear_expired_snomed_cache
)

# Clean up expired cache first
clear_expired_snomed_cache()

# Get existing cached mappings
cached_mappings = get_cached_snomed_mappings()

# Use cached mappings in translation
if guid in cached_mappings:
    snomed_code = cached_mappings[guid]
else:
    # Perform lookup and cache result
    snomed_code = lookup_snomed(guid)
    update_snomed_cache({guid: snomed_code})
```

</details>

---

## Integration Points

**Key runtime usage:**

| Module | Usage |
|--------|-------|
| `streamlit_app.py` | File lifecycle, calls clear helpers |
| `utils/caching/cache_manager.py` | Writes pipeline outputs using `SessionStateKeys` |
| `utils/metadata/snomed_translation.py` | Uses SNOMED cache helper APIs |
| UI modules | Read key constants for stable cross-module state access |

---

## Practical Rules

1. **Add new keys to `SessionStateKeys` first**, then consume those constants everywhere
2. **If a new feature needs bulk cleanup**, add it to the correct `SessionStateGroups` bucket and/or a dedicated clear helper
3. **Use scoped clear helpers** in preference to ad-hoc key deletion in feature modules
4. **Never use magic strings** for session state keys - always use the constants

---

## Related Documentation

- **[Module Architecture](modules.md)** - System overview
- **[Flags Technical Guide](../flags-and-plugins/flags.md)** - Flag system
- **[Project Structure](../project-structure.md)** - File organisation

---

*Last Updated: 2nd February 2026*
*Application Version: 3.0.0*
