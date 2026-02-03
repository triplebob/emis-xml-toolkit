# ClinXML System Architecture

## Overview

This document describes the current v3 architecture and data flow from XML upload to UI rendering and exports.

## High-Level Flow

```mermaid
graph TD
    A[XML Upload] --> B[Decode and Parse]
    B --> C[Entity and Structure Build]
    C --> D[CodeStore Dedup + Metadata Flags]
    D --> E[Lookup Enrichment]
    E --> F[Translation and Categorisation]
    F --> G[Top-level Tabs]
    G --> H[On-demand Exports]

    subgraph Optional NHS Terminology
      I[OAuth2 Client]
      J[Single Code Lookup]
      K[Batch Expansion]
      L[Expansion Cache]
      I --> J
      I --> K --> L
    end

    G -. integration .-> J
    G -. integration .-> K
```

## Detailed Component Diagram

```mermaid
graph TB
    subgraph App Shell
      APP[streamlit_app.py]
      STATUS[utils/ui/status_bar.py]
      TABS[utils/ui/ui_tabs.py]
    end

    subgraph Parsing Layer
      DOC[document_loader.py]
      CLASS[element_classifier.py]
      PIPE[pipeline.py]
      NP[node_parsers/*]
      PAT[pattern_plugins/registry.py]
    end

    subgraph Metadata and Caching
      XMLC[utils/caching/xml_cache.py]
      CM[utils/caching/cache_manager.py]
      STORE[utils/caching/code_store.py]
      ENRICH[utils/metadata/enrichment.py]
      SERIAL[utils/metadata/serialisers.py]
      TRANS[utils/metadata/snomed_translation.py]
      FLAGS[utils/metadata/flag_mapper.py + flag_registry.py]
    end

    subgraph Lookup Infrastructure
      LM[utils/caching/lookup_manager.py]
      LC[utils/caching/lookup_cache.py]
      GH[utils/caching/github_loader.py]
    end

    subgraph UI Feature Tabs
      CLIN[clinical_codes/*]
      XMLX[xml_inspector/*]
      SEARCH[search_browser/*]
      REPORT[report_viewer/*]
      LOOKUP[terminology_server/lookup_tab.py]
      EXPAND[terminology_server/expansion_tab.py]
    end

    subgraph NHS Terminology
      NHSC[terminology_server/client.py]
      NHSS[terminology_server/service.py]
      NHSW[terminology_server/expansion_workflow.py]
    end

    subgraph Exports
      EXP[utils/exports/*]
    end

    APP --> STATUS
    APP --> CM
    CM --> XMLC
    XMLC --> PIPE
    PIPE --> DOC
    PIPE --> CLASS
    PIPE --> NP
    PIPE --> PAT
    NP --> STORE
    PAT --> FLAGS

    XMLC --> ENRICH
    ENRICH --> SERIAL
    APP --> TRANS

    STATUS --> LM
    LM --> LC
    LM --> GH
    ENRICH --> LM
    TRANS --> LM

    APP --> TABS
    TABS --> CLIN
    TABS --> XMLX
    TABS --> SEARCH
    TABS --> REPORT
    TABS --> LOOKUP

    CLIN --> EXPAND
    LOOKUP --> NHSW
    EXPAND --> NHSW
    NHSW --> NHSS
    NHSS --> NHSC

    CLIN --> EXP
    SEARCH --> EXP
    REPORT --> EXP
    LOOKUP --> EXP
    EXPAND --> EXP
```

## Runtime Sequence (Typical Upload)

```text
1. User uploads XML in streamlit_app.py
2. cache_manager.cache_xml_code_extraction() requests cached parse results
3. xml_cache.cache_parsed_xml() runs parsing pipeline (or returns cache hit)
4. metadata enrichment builds UI-ready rows
5. streamlit_app.py runs translation categorisation for clinical outputs
6. ui_tabs.py renders top-level tabs and feature-specific views
7. Export payloads are generated only when export buttons are clicked
```

## Top-Level UI Tabs

Processed-file mode:

1. Clinical Codes
2. XML Explorer
3. Searches
4. Reports
5. Code Lookup

Debug mode additionally exposes a Memory diagnostics tab.

## Caching Summary

- Lookup bytes cached in session state (`LOOKUP_ENCRYPTED_BYTES`)
- Parsed XML outputs cached by XML hash (`cache_parsed_xml`)
- SNOMED mapping cache maintained with 60-minute TTL
- Terminology expansion cache uses TTL + bounded eviction
- Export payloads are generated lazily and released after download actions

---

*Last Updated: 3rd February 2026*
*Application Version: 3.0.0*
