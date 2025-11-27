# ClinXML System Architecture

## Overview

This document provides a visual overview of the ClinXML system architecture, showing the data flow from XML upload through processing to the final 5-tab user interface and export system.

## High-Level System Overview

For new contributors, here's a simplified view of the core system flow:

```mermaid
graph TB
    XML[📄 XML Upload] 
    PARSE[🔧 XML Processing<br/>Extract GUIDs & Structure]
    TRANS[🔄 Translation<br/>EMIS → SNOMED]
    UI[📊 5-Tab Interface<br/>Display Results]
    EXPORT[📤 Export System<br/>Multiple Formats]
    
    XML --> PARSE
    PARSE --> TRANS
    TRANS --> UI
    UI --> EXPORT
    
    subgraph "Optional NHS Integration"
        NHS[🌐 NHS Terminology<br/>Hierarchy Expansion]
    end
    
    TRANS -.-> NHS
    NHS -.-> UI
    
    classDef core fill:#e8f5e8
    classDef optional fill:#e3f2fd
    
    class XML,PARSE,TRANS,UI,EXPORT core
    class NHS optional
```

## Detailed System Architecture

```mermaid
graph TB
    %% Input Layer
    XML[📄 EMIS XML File<br/>Upload]
    
    %% XML Processing Layer
    subgraph "XML Processing Pipeline"
        NS[🔧 Namespace Handler<br/>Universal XML Support]
        BP[📋 Base Parser<br/>Defensive Programming]
        CP[🔍 Criterion Parser<br/>Search Logic]
        RP[📊 Report Parser<br/>List/Audit/Aggregate]
        VP[💊 Value Set Parser<br/>Clinical Codes]
        XU[⚙️ XML Utils<br/>GUID Extraction]
    end
    
    %% Core Translation Layer
    subgraph "Core Translation Engine"
        TR[🔄 Translator<br/>EMIS GUID → SNOMED]
        subgraph "Caching Layer"
            SC[⚡ Session Cache<br/>60min TTL]
            GC[📦 GitHub Cache<br/>Bulk Mappings]
            API[🌐 NHS API<br/>Live Validation]
        end
    end
    
    %% Analysis Layer
    subgraph "Analysis Pipeline"
        AO[🎯 Analysis Orchestrator<br/>Workflow Coordination]
        XEC[🏷️ XML Element Classifier<br/>Single Parse]
        SA[🔍 Search Analyzer<br/>Population Logic]
        RA[📊 Report Analyzer<br/>Structure Analysis]
    end
    
    %% UI Layer
    subgraph "5-Tab User Interface"
        CT[🏥 Clinical Codes<br/>SNOMED Translation]
        AT[🔍 Search Analysis<br/>Rule Logic Browser]
        LT[📋 List Reports<br/>Column Structure]
        AuT[📊 Audit Reports<br/>Quality Indicators]
        AgT[📈 Aggregate Reports<br/>Statistical Analysis]
    end
    
    %% Export Layer
    subgraph "Export System"
        EM[📤 Export Manager<br/>Format Coordination]
        SE[📄 Search Export<br/>Rule Breakdown]
        RE[📊 Report Export<br/>All Report Types]
        CE[💊 Clinical Export<br/>SNOMED Codes]
        JE[🔗 JSON Export<br/>API Integration]
        TE[🌳 Terminology Export<br/>NHS Hierarchy]
    end
    
    %% NHS Integration
    subgraph "NHS Terminology Server"
        TC[🔐 nhs_terminology_client.py<br/>OAuth2 + FHIR R4]
        RL[⚖️ rate_limiter.py<br/>Adaptive Throttling]
        PT[⏱️ progress_tracker.py<br/>Real-time Updates]
        BatchProc[🔄 batch_processor.py<br/>Concurrent Workers]
        ES[🌳 expansion_service.py<br/>Hierarchy Expansion]
    end
    
    %% Data Flow Connections
    XML --> NS
    NS --> BP
    BP --> CP
    BP --> RP
    BP --> VP
    BP --> XU
    
    XU --> TR
    TR --> SC
    SC --> GC
    GC --> API
    API --> TC
    
    CP --> AO
    RP --> AO
    VP --> AO
    AO --> XEC
    XEC --> SA
    XEC --> RA
    
    SA --> AT
    RA --> LT
    RA --> AuT
    RA --> AgT
    TR --> CT
    
    CT --> EM
    AT --> EM
    LT --> EM
    AuT --> EM
    AgT --> EM
    
    EM --> SE
    EM --> RE
    EM --> CE
    EM --> JE
    EM --> TE
    
    TC --> RL
    TC --> PT
    TC --> BatchProc
    TC --> ES
    
    %% NHS Integration Flow (explicit sequence)
    RL --> ES
    PT --> BatchProc
    ES --> BatchProc
    
    %% Terminology Integration
    ES --> CT
    ES --> TE
    
    %% Styling
    classDef inputLayer fill:#e1f5fe
    classDef processingLayer fill:#f3e5f5
    classDef coreLayer fill:#e8f5e8
    classDef analysisLayer fill:#fff3e0
    classDef uiLayer fill:#fce4ec
    classDef exportLayer fill:#f1f8e9
    classDef nhsLayer fill:#e3f2fd
    
    class XML inputLayer
    class NS,BP,CP,RP,VP,XU processingLayer
    class TR,SC,GC,API coreLayer
    class AO,XEC,SA,RA analysisLayer
    class CT,AT,LT,AuT,AgT uiLayer
    class EM,SE,RE,CE,JE,TE exportLayer
    class TC,RL,PT,BatchProc,ES nhsLayer
```

## Error Handling Flow

```mermaid
graph TB
    ParseErr[❌ XML Parse Error<br/>malformed XML]
    TransErr[❌ Translation Error<br/>lookup failure]
    APIErr[❌ NHS API Error<br/>auth/network failure]
    
    EH[🛡️ error_handling.py<br/>Centralized Error Management]
    UEH[📱 ui_error_handling.py<br/>User-Friendly Display]
    
    ParseErr --> EH
    TransErr --> EH
    APIErr --> EH
    
    EH --> UEH
    
    subgraph "Error Recovery"
        Cache[💾 Fallback to Cache]
        Graceful[⚠️ Graceful Degradation]
        UserMsg[💬 User Guidance]
    end
    
    EH --> Cache
    EH --> Graceful
    UEH --> UserMsg
    
    classDef error fill:#ffebee
    classDef recovery fill:#e8f5e8
    classDef handler fill:#fff3e0
    
    class ParseErr,TransErr,APIErr error
    class Cache,Graceful,UserMsg recovery
    class EH,UEH handler
```

## Component Descriptions

### Input Layer
- **EMIS XML File**: Source EMIS XML documents (Search, List, Audit, Aggregate reports)

### XML Processing Pipeline
- **Namespace Handler** (`namespace_handler.py`): Universal support for mixed namespaced/non-namespaced XML
- **Base Parser** (`base_parser.py`): Defensive programming patterns with structured error handling
- **Criterion Parser** (`criterion_parser.py`): Search logic and criteria parsing
- **Report Parser** (`report_parser.py`): List/Audit/Aggregate report structures
- **Value Set Parser** (`value_set_parser.py`): Clinical code value sets with deduplication
- **XML Utils** (`xml_utils.py`): Core GUID extraction with source attribution

### Core Translation Engine
- **Translator** (`translator.py`): Main EMIS GUID → SNOMED translation engine with dual-mode deduplication
- **Multi-tier Caching**: Session cache (60min) → GitHub cache → NHS API fallback strategy
- **Performance**: O(1) dictionary lookups with session state persistence and cache_manager integration

### Analysis Pipeline
- **Analysis Orchestrator** (`analysis_orchestrator.py`): Coordinates workflow across specialized analyzers
- **XML Element Classifier** (`xml_element_classifier.py`): Single XML parse with element type classification
- **Search Analyzer** (`search_analyzer.py`): Population logic, linked criteria, and dependency analysis
- **Report Analyzer** (`report_analyzer.py`): Structure analysis for List/Audit/Aggregate reports

### 5-Tab User Interface
- **Clinical Codes** (`clinical_tabs.py`): SNOMED translation with dual-mode deduplication
- **Search Analysis** (`analysis_tabs.py`): Rule Logic Browser with criteria visualization
- **List Reports** (`list_report_tab.py`): Column structure analysis with healthcare context
- **Audit Reports** (`audit_report_tab.py`): Multi-population analysis with quality indicators
- **Aggregate Reports** (`aggregate_report_tab.py`): Statistical analysis with cross-tabulation

### Export System
- **Export Manager** (`ui_export_manager.py`): Coordinates multiple export formats
- **Search Export** (`search_export.py`): Rule breakdown and criteria analysis
- **Report Export** (`report_export.py`): All report types with enhanced metadata
- **Clinical Export** (`clinical_code_export.py`): SNOMED codes with source tracking
- **JSON Export** (`json_export_generator.py`): API integration and structured data
- **Terminology Export** (`terminology_export.py`): NHS hierarchy formats

### NHS Terminology Server Integration
- **Terminology Client**: OAuth2 authentication with FHIR R4 API
- **Rate Limiter**: Adaptive throttling with exponential backoff
- **Progress Tracker**: Real-time updates with adaptive time estimation
- **Batch Processor**: Concurrent workers (8-20) for large hierarchies
- **Expansion Service**: SNOMED hierarchy expansion with `includeChildren=true`

## Data Flow Summary

1. **XML Upload** → XML processing pipeline extracts GUIDs and structure
2. **Translation** → Core engine translates GUIDs to SNOMED using cached lookups
3. **Analysis** → Specialized analyzers process search logic and report structure
4. **UI Display** → 5-tab interface presents organized results with export options
5. **NHS Integration** → Optional terminology server provides live hierarchy validation

## Performance Characteristics

- **Session Caching**: 60-minute SNOMED mapping persistence
- **Adaptive Threading**: 8-20 workers based on workload size
- **Memory Optimization**: Streamlit Cloud compatible (2.7GB limits)
- **Progressive Loading**: Section-by-section rendering for large datasets
- **Cache-first Strategy**: Minimizes external API dependencies

## Security & Privacy

- **Local Processing**: XML files processed in browser session only
- **Controlled API Usage**: Only SNOMED codes sent to NHS API (not XML content)
- **OAuth2 Security**: System-to-system authentication for NHS API
- **No Persistent Storage**: All data cleared when session ends