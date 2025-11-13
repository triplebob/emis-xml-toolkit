![ClinXML - The Unofficial EMIS XML Toolkit](img/clinxml.svg)

A comprehensive web application for analyzing EMIS XML files with advanced search logic analysis, NHS terminology server integration, and clinical code translation. 
Transform complex EMIS XML documents into actionable insights for NHS healthcare teams.

## 🚀 **[Live Application](https://clinxml.streamlit.app/)**

**Ready to use immediately - no installation required.** Click the link above to access the live application.

*Comprehensive EMIS XML analysis and clinical code extraction for NHS healthcare teams*

---

## ✨ Key Features

### 📊 **Complete 5-Tab Analysis Interface**
- **🏥 Clinical Codes**: Advanced SNOMED translation with NHS terminology server integration and dual-mode deduplication
- **🔍 Search Analysis**: Rule Logic Browser with detailed criterion analysis and dependency visualisation
- **📋 List Reports**: Column structure analysis with healthcare context and filter logic
- **📊 Audit Reports**: Multi-population analysis with organisational grouping and quality indicators  
- **📈 Aggregate Reports**: Statistical analysis with cross-tabulation

### 🌳 **NHS England Terminology Server Integration**
- **FHIR R4 API Integration**: Direct connection to NHS England Terminology Server
- **Hierarchical Code Expansion**: Automatic expansion of codes with `includechildren=true` flags  
- **Adaptive Threading**: Scales 8-20 concurrent workers based on workload size for optimal performance
- **Session-based Caching**: Eliminates repeated API calls with intelligent result caching
- **EMIS Comparison Analysis**: Compare EMIS expected vs actual child counts from terminology server
- **Multiple Export Formats**: CSV, hierarchical JSON, and XML-ready outputs
- **Real-time Validation**: Individual code lookup and testing capabilities

### 🔍 **Advanced XML Pattern Support**
- **baseCriteriaGroup**: Nested criterion logic within wrapper criteria
- **Linked Criteria**: Cross-table relationships with temporal constraints
- **SNOMED Refsets**: Direct code handling with clean description extraction
- **EMISINTERNAL Classifications**: Episode types, consultation headings, clinical status
- **Complex Restrictions**: "Latest N WHERE condition" with test attributes

### 📤 **Comprehensive Export System**
- **Multi-sheet Excel exports** with professional formatting
- **NHS terminology exports**: SNOMED codes, EMIS mappings, hierarchical JSON
- **Type-specific report exports** for List/Audit/Aggregate reports
- **Smart filtering**: Export all codes, matched only, or unmatched only
- **Multiple formats**: Excel, CSV, JSON, XML-ready, and TXT reports
- **Source attribution**: Track codes to their originating searches/reports

### ⚡ **Cache-First Architecture**
- **Multi-tier caching**: Local cache → GitHub cache → API fallback
- **Optimized performance**: Faster startup and reduced external dependencies
- **Session persistence**: Results maintained across download operations
- **Health monitoring**: Automatic cache validation and regeneration

### 🏗️ **Enterprise Features**
- **Hierarchical folder management** with multi-level navigation
- **Supports EMIS QOF indicators** and custom healthcare quality metrics
- **Multi-organisation support** for EMIS Enterprise exports
- **Clinical pathway analysis** with workflow context
- **Version independence** across EMIS system versions

---

## 🎯 Supported EMIS XML Types

### **Search Reports**
- Population-based searches with complex criteria groups
- Rule logic analysis with AND/OR operators
- Population criteria and cross-search references
- Dependency visualisation and execution flow

### **List Reports** 
- Multi-column data extraction with column-specific filtering
- Healthcare context classification (clinical data, appointments, demographics)
- Per-column search criteria and restrictions analysis
- Clinical code extraction from report filters

### **Audit Reports**
- Quality monitoring and compliance tracking
- Multi-population analysis with member search combinations
- Organisational grouping (practice codes, user authorisation)
- Enhanced metadata with creation time and author information

### **Aggregate Reports**
- Statistical analysis and cross-tabulation
- Built-in filters and criteria analysis
- Healthcare metrics and quality measurement
- Enterprise reporting capabilities

### **Patient Demographics & LSOA Filtering**
- Future-proof LSOA detection supporting exisiting 2011 census data, with dynamic year support for future LSOA releases
- Demographics-only XML analysis without clinical codes
- EMIS-style phrasing for patient demographic criteria
- Individual LSOA code display in exports
- Grouped criteria analysis for shared IDs with different demographic values

---

## 🔬 Clinical Code Systems

### **SNOMED CT Support**
- **Concepts and Refsets**: Full SNOMED CT concept hierarchy
- **NHS Terminology Server**: Live expansion of hierarchical concepts
- **Direct Refset Handling**: NHS refsets processed as direct SNOMED codes
- **Legacy Read Codes**: Backward compatibility via mapping tables
- **Include Children**: Automatic descendant code inclusion with validation

### **Medication Systems**
- **dm+d Codes**: Dictionary of medicines and devices
- **SCT_APPNAME**: Brand-specific medication names (Emerade, EpiPen, etc.)
- **SCT_CONST**: Constituent/generic drug names 
- **SCT_DRGGRP**: Drug group classifications

### **EMIS Internal Classifications**
- **Episode Types**: FIRST, NEW, REVIEW, ENDED, NONE
- **Consultation Headings**: PROBLEM, REVIEW, ISSUE
- **Clinical Status**: COMPLICATION, ONGOING, RESOLVED
- **User Authorisation**: Active user and contract status filtering

---

## 🚀 Quick Start

### **Option 1: Use Live App (Recommended)**
**[🌐 Access Live Application](https://clinxml.streamlit.app/)** - No installation required

1. Upload your EMIS XML file
2. View comprehensive analysis across 5 specialised tabs
3. Optional: Configure NHS terminology server credentials for expansion features
4. Export detailed reports in multiple formats
5. Navigate folder structures and analyse dependencies

### **Option 2: Run Locally**

#### Prerequisites
- Python 3.8+
- MKB lookup table with EMIS GUID to SNOMED mappings
- NHS England System-to-System credentials (optional, for terminology server features)

#### Installation
```bash
git clone https://github.com/triplebob/emis-xml-convertor.git
cd emis-xml-convertor
pip install -r requirements.txt
```

#### Configuration (Optional)
Create `.streamlit/secrets.toml` for NHS terminology server integration:
```toml
NHSTSERVER_ID = "Your_Organization_Consumer_ID"
NHSTSERVER_TOKEN = "your_client_secret_token"
```

#### Run Application
```bash
streamlit run streamlit_app.py
```

---

## 📁 Project Structure

```
⚕️ emis-xml-convertor/
├── streamlit_app.py                                    # Main application entry point
├── requirements.txt                                    # Python dependencies
├── changelog.md                                        # Version history and improvements
├── util_modules/                                       # 📁 **Modular application architecture**
│   ├── analysis/                                       # 📁 **Analysis engines and orchestration**
│   │   ├── analysis_orchestrator.py                    # Central analysis coordination
│   │   ├── xml_element_classifier.py                   # Element type classification
│   │   ├── xml_structure_analyzer.py                   # Compatibility interface
│   │   ├── search_analyzer.py                          # Search logic analysis
│   │   ├── search_rule_analyzer.py                     # Legacy search analysis
│   │   ├── report_analyzer.py                          # Report structure analysis
│   │   ├── common_structures.py                        # Shared data structures
│   │   ├── performance_optimizer.py                    # Performance monitoring
│   │   ├── search_rule_visualizer.py                   # Interactive rule displays
│   │   ├── report_structure_visualizer.py              # Report visualisation
│   │   ├── shared_render_utils.py                      # Common visualisation utilities
│   │   └── linked_criteria_handler.py                  # Linked criteria processing
│   ├── terminology_server/                             # 📁 **NHS Terminology Server integration**
│   │   ├── nhs_terminology_client.py                   # FHIR R4 API client
│   │   ├── expansion_service.py                        # Service layer for code expansion
│   │   └── expansion_ui.py                             # User interface components
│   ├── xml_parsers/                                    # 📁 **Modular XML parsing system**
│   │   ├── xml_utils.py                                # Core XML parsing and GUID extraction
│   │   ├── namespace_handler.py                        # Universal namespace handling
│   │   ├── base_parser.py                              # Base parsing utilities
│   │   ├── criterion_parser.py                         # Search criteria parsing
│   │   ├── report_parser.py                            # Report structure parsing
│   │   ├── value_set_parser.py                         # Clinical code value sets
│   │   ├── restriction_parser.py                       # Search restrictions parsing
│   │   └── linked_criteria_parser.py                   # Linked criteria parsing
│   ├── core/                                           # 📁 **Business logic and classification**
│   │   ├── translator.py                               # GUID to SNOMED translation
│   │   ├── report_classifier.py                        # EMIS report type classification
│   │   ├── folder_manager.py                           # Folder hierarchy management
│   │   ├── search_manager.py                           # Search data management
│   │   ├── background_processor.py                     # Background processing
│   │   └── optimized_processor.py                      # Processing integration
│   ├── ui/                                             # 📁 **User interface components**
│   │   ├── ui_tabs.py                                  # Main results interface
│   │   ├── status_bar.py                               # Application status display
│   │   ├── ui_helpers.py                               # Reusable UI components
│   │   ├── rendering_utils.py                          # Standard UI components
│   │   ├── layout_utils.py                             # Complex layout management
│   │   ├── progressive_loader.py                       # Progressive loading components
│   │   ├── async_components.py                         # Asynchronous UI components
│   │   └── tabs/                                       # 📁 **Modular tab structure**
│   │       ├── clinical_tabs.py                        # Clinical data tab rendering
│   │       ├── analysis_tabs.py                        # Analysis tab rendering
│   │       ├── analytics_tab.py                        # Analytics display
│   │       ├── report_tabs.py                          # Core report tab infrastructure
│   │       ├── list_report_tab.py                      # List report specialised module
│   │       ├── audit_report_tab.py                     # Audit report specialised module
│   │       ├── aggregate_report_tab.py                 # Aggregate report specialised module
│   │       ├── tab_helpers.py                          # Shared tab utilities
│   │       ├── base_tab.py                             # Tab base classes
│   │       ├── field_mapping.py                        # Universal field mapping
│   │       └── common_imports.py                       # Shared imports
│   ├── export_handlers/                                # 📁 **Comprehensive export system**
│   │   ├── ui_export_manager.py                        # Export coordination
│   │   ├── search_export.py                            # Search-specific exports
│   │   ├── report_export.py                            # Report export handler
│   │   ├── rule_export.py                              # Individual rule export
│   │   ├── clinical_code_export.py                     # Clinical code exports
│   │   ├── terminology_export.py                       # NHS terminology exports
│   │   ├── json_export_generator.py                    # Search JSON exports
│   │   └── report_json_export_generator.py             # Report JSON exports
│   ├── utils/                                          # 📁 **General utilities and caching**
│   │   ├── lookup.py                                   # Cache-first lookup table management
│   │   ├── audit.py                                    # Processing statistics
│   │   ├── text_utils.py                               # Text processing utilities
│   │   ├── debug_logger.py                             # Development tools
│   │   ├── github_loader.py                            # External data loading
│   │   └── caching/                                    # 📁 **Comprehensive caching system**
│   │       ├── cache_manager.py                        # Centralized cache management with TTL
│   │       ├── lookup_cache.py                         # Core caching engine
│   │       └── generate_github_cache.py                # Cache generation utilities
│   └── common/                                         # 📁 **Shared utilities and infrastructure**
│       ├── error_handling.py                           # Standardized error management
│       ├── ui_error_handling.py                        # UI error display
│       ├── export_utils.py                             # Centralized export utilities
│       └── dataframe_utils.py                          # DataFrame operations
├── docs/                                               # 📁 **Technical documentation**
│   ├── modules.md                                      # Module architecture guide
│   ├── nhs-terminology-server-integration.md           # NHS terminology server reference
│   ├── emis-xml-patterns.md                            # EMIS XML pattern reference
│   ├── namespace-handling.md                           # Namespace handling guide
│   └── theme-colors.md                                 # Custom theme colour reference guide
├── img/                                                # 📁 **Application branding assets**
│   ├── logo.svg                                        # ClinXML medical cross icon
│   ├── clinxml.svg                                     # Full logo with text and tagline
│   ├── clinxml_title.svg                               # Text-only logo
│   └── favicon.ico                                     # Browser favicon
└── tests/                                              # 📁 **Test suite**
    └── test_performance.py                             # Performance testing
```

---

## 🔧 Technical Specifications

### **Performance Optimizations**
- **Centralised Cache Management**: Unified caching architecture with optimised TTL settings
- **Report-Specific Caching**: Instant dropdown switching with 10,000-entry SNOMED cache
- **Memory Management**: Real-time monitoring with automatic garbage collection
- **Dictionary-based Lookups**: O(1) SNOMED translation (100x faster than DataFrame searches)
- **Progressive Loading**: Section-by-section rendering with native Streamlit spinners
- **Lazy Export Generation**: Export files created only when requested

### **NHS Terminology Server Integration**
- **FHIR R4 Compliance**: Full NHS England Terminology Server API support
- **OAuth2 Authentication**: System-to-system authentication with automatic token refresh
- **ECL Support**: Expression Constraint Language for hierarchical expansion
- **Adaptive Threading**: Dynamic worker scaling (8-20 workers) optimised for Streamlit Cloud 2.7GB limits
- **Session Caching**: Intelligent result caching eliminates repeated API calls for instant reuse
- **Rate Limiting**: Graceful handling of API constraints and timeouts
- **Error Recovery**: Comprehensive error handling with fallback strategies

### **XML Processing**
- **Universal Namespace Handling**: Mixed namespaced/non-namespaced document support
- **Robust Error Handling**: Comprehensive exception management with graceful degradation
- **Memory Optimisation**: Efficient processing of large XML files (40+ entities)
- **Cloud Compatibility**: Optimised for Streamlit Cloud deployment

### **Data Management**
- **Dual-mode Deduplication**: Unique codes vs per-source tracking
- **Session State Integration**: Persistent analysis across tab navigation
- **Export Filtering**: Conditional data inclusion based on user selection
- **Source Attribution**: Track clinical codes to originating searches/reports

### **Browser Compatibility**
- **Chrome/Edge**: Recommended (full feature support)
- **Firefox/Safari**: Supported (core functionality)
- **Mobile**: Limited support (view-only recommended)

---

## 📊 Use Cases

### **Clinical Governance**
- **QOF Indicator Analysis**: Quality and Outcomes Framework reporting
- **Clinical Pathway Review**: Analyze complex care pathways and protocols
- **Code Set Validation**: Verify SNOMED code usage and mapping accuracy with NHS terminology server
- **Search Logic Auditing**: Review and optimise clinical search criteria
- **Hierarchy Validation**: Compare EMIS expectations with current NHS terminology data

### **System Administration**
- **EMIS Configuration Review**: Analyze search and report configurations
- **Folder Organization**: Review hierarchical folder structures
- **Dependency Mapping**: Understand search and report relationships
- **Performance Analysis**: Identify complex searches and optimisation opportunities
- **Terminology Updates**: Validate code hierarchies against current NHS terminology

### **Healthcare Analytics**
- **Population Analysis**: Understand search population logic and criteria
- **Report Structure Review**: Analyze List/Audit/Aggregate report configurations
- **Clinical Code Translation**: Convert EMIS codes to SNOMED for external systems
- **Quality Measurement**: Export data for external quality measurement tools
- **Hierarchical Analysis**: Export parent-child relationships for programmatic integration

---

## 🛡️ Security & Privacy

### **Data Handling**
- **No Data Storage**: XML files processed in memory only
- **Session-based Processing**: Data cleared when session ends
- **Client-side Processing**: SNOMED translation performed locally
- **No External Transmission**: Lookup tables cached locally
- **NHS API Security**: Secure OAuth2 authentication with NHS England

### **Compliance Considerations**
- **IG Toolkit Compatible**: Designed for NHS IG Toolkit compliance
- **GDPR Aligned**: No persistent data storage or tracking
- **Audit Trail**: Processing statistics available for governance
- **Version Transparency**: Lookup table versions clearly displayed
- **NHS Terms Compliance**: Usage subject to NHS England API terms of service

---

## 🤝 Contributing

### **Bug Reports**
Please report issues with detailed XML examples (anonymized) and steps to reproduce.

### **Feature Requests**
Enhancement suggestions welcome, particularly for new EMIS XML patterns or export formats.

### **Technical Documentation**
Contributions to technical documentation and pattern identification appreciated.

---

## ⚖️ Legal & Compliance

### **Disclaimer**
**EMIS and EMIS Web are trademarks of Optum Inc.** This unofficial toolkit is not affiliated with, endorsed by, or sponsored by Optum Inc, EMIS Health, NHS England, or any of their subsidiaries. All trademarks are the property of their respective owners.

### **License**
This project is provided as-is for healthcare and research purposes. Users are responsible for ensuring compliance with local data protection and clinical governance requirements.

### **No Warranty**
This toolkit is provided without warranty of any kind. Healthcare professionals should validate all clinical code translations against authoritative sources before clinical use.

---

## 📞 Support

### **Documentation**
- **NHS Terminology Server**: [Integration Reference](docs/nhs-terminology-server-integration.md)
- **Technical Patterns**: [EMIS XML Patterns Reference](docs/emis-xml-patterns.md)
- **Architecture Guide**: [Module Architecture](docs/modules.md)
- **Namespace Handling**: [Namespace Documentation](docs/namespace-handling.md)

### **Live Application**
**🌐 [https://clinxml.streamlit.app/](https://clinxml.streamlit.app/)**

---

*Last Updated: November 2025*  
*Application Version: 2.2.3*  
*Live Application: https://clinxml.streamlit.app/*
