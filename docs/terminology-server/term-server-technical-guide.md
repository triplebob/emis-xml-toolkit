# NHS Terminology Server Integration - Technical Guide

## Module Architecture

Current terminology integration modules:

- `utils/terminology_server/client.py`
- `utils/terminology_server/service.py`
- `utils/terminology_server/expansion_workflow.py`
- `utils/terminology_server/lineage_workflow.py`
- `utils/terminology_server/connection.py`
- UI entry points:
  - `utils/ui/tabs/terminology_server/lookup_tab.py`
  - `utils/ui/tabs/terminology_server/expansion_tab.py`

## Responsibility Split

### `client.py`

Low-level NHS API interaction.

Responsibilities:

- OAuth2 client-credentials token retrieval and refresh
- Authenticated FHIR requests
- Retry/backoff for transient HTTP/network issues
- Rate limiting and timeout handling
- Concept lookup and expansion request helpers

### `service.py`

Expansion orchestration and caching service.

Responsibilities:

- Expansion cache lifecycle management
- Cache lookup/hit/miss tracking
- Concurrent batch expansion execution
- Progress callback support for UI updates
- Shared singleton access (`get_expansion_service`)

### `expansion_workflow.py`

Domain workflow and output shaping.

Responsibilities:

- Identify expandable codes from clinical rows
- Apply include-children and filter rules
- Coordinate expansion calls through the service layer
- Build summary rows and child export rows
- Attach EMIS GUID mapping where available

### `lineage_workflow.py`

Hierarchy lineage tracing and tree building.

Responsibilities:

- Trace parent-child lineage from expansion results
- Build `LineageNode` tree structures with depth tracking
- Detect shared lineage across multiple branches
- Generate ASCII tree representations with depth indicators
- Export hierarchy to JSON with source file metadata

### `connection.py`

Connection checks and quick diagnostics used by sidebar status/actions.

## Data Flow

```text
UI tab action
  -> expansion_workflow.prepare_expansion_selection()
  -> expansion_workflow.run_expansion()
      -> service.expand_codes_batch()
          -> client.expand_concept()
  -> workflow builds summary + child rows
  -> UI renders tables and export controls
```

## Caching Details

### Expansion Cache (`service.py`)

- Backed by session state when Streamlit context is available
- Cache is scoped to the active file hash (`current_file_hash` / `last_processed_hash`)
- Default TTL: 90 minutes
- Default max size: 10,000 entries
- Eviction policy: remove oldest cached entry when at capacity
- Cache key includes code + include-inactive option
- File-change invalidation: cache is reset when a new XML file is loaded/reprocessed

### Hierarchy / Lineage Session State

- Hierarchy payloads (`full_lineage_trace_result`, `lookup_lineage_*`) are stored in session state
- These are explicitly cleared on new XML upload/reprocess via session-state cleanup helpers
- This prevents cross-file accumulation and memory creep in long-running sessions

### Lookup Mapping Dependency

Expansion workflow can enrich rows with EMIS GUID mapping by reading lookup cache outputs from the main app lookup infrastructure.

## Concurrency Model

- Batch expansion uses `ThreadPoolExecutor`
- Worker count is passed via `ExpansionConfig.max_workers`
- Current UI calls use a fixed max worker value (10)
- Progress updates are delivered via callback `(completed, total)`

## Error Handling Model

Primary failure paths handled in client/service/workflow:

- Authentication/token failures
- Rate limit responses
- Invalid or missing SNOMED concepts
- Network/timeout failures
- Partial batch failures (individual code failures with batch continuation)

UI surfaces these through clear status messages and error panels.

## Integration Points with Main App

- Credentials sourced from Streamlit secrets (`NHSTSERVER_ID`, `NHSTSERVER_TOKEN`)
- Code lookup available without XML upload
- Batch expansion in Clinical Codes tab consumes pipeline-produced clinical rows
- Export helpers live in `utils/exports/terminology_child_exports.py` (child code CSV) and `utils/exports/terminology_tree_exports.py` (hierarchy tree TXT/SVG/JSON)

## Extension Guidance

When adding terminology features:

1. Keep API calls in `client.py`.
2. Keep cache and execution policy in `service.py`.
3. Keep row shaping/business workflow in `expansion_workflow.py`.
4. Keep UI rendering and interactions in `utils/ui/tabs/terminology_server/`.
5. Reuse export helpers instead of duplicating CSV generation logic.

---

*Last Updated: 6th February 2026*
*Application Version: 3.0.2*
