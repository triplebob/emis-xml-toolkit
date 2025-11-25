# ClinXML Project Structure

## Overview
ClinXML uses a modular architecture with specialised modules for analysis, UI rendering, export functionality, and caching. 
The codebase is organised into logical directories that separate concerns and enable maintainable development.

## 📁 Directory Structure

```
⚕️ emis-xml-convertor/
├── streamlit_app.py                                    # Main application entry point
├── requirements.txt                                    # Python dependencies
├── changelog.md                                        # Version history and improvements
├── utils/                                              # 📁 **Modular application architecture**
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
│   │   ├── nhs_terminology_client.py                   # Thread-safe FHIR R4 API client
│   │   ├── expansion_service.py                        # UI-independent service layer
│   │   ├── expansion_ui.py                             # Streamlit interface components
│   │   ├── rate_limiter.py                             # Adaptive rate limiting with exponential backoff
│   │   ├── progress_tracker.py                         # Advanced progress tracking with time estimation
│   │   ├── batch_processor.py                          # Batch processing coordination
│   │   └── debug_utilities.py                          # Development and debugging utilities
│   ├── xml_parsers/                                    # 📁 **Modular XML parsing system**
│   │   ├── xml_utils.py                                # Core XML parsing and GUID extraction
│   │   ├── namespace_handler.py                        # Universal namespace handling
│   │   ├── base_parser.py                              # Base parsing utilities
│   │   ├── criterion_parser.py                         # Search criteria parsing
│   │   ├── report_parser.py                            # Report structure parsing
│   │   ├── value_set_parser.py                         # Clinical code value sets
│   │   ├── restriction_parser.py                       # Search restrictions parsing
│   │   └── linked_criteria_parser.py                   # Linked criteria parsing
│   ├── core/                                           # 📁 **Business logic and session management**
│   │   ├── translator.py                               # GUID to SNOMED translation with 60-minute caching
│   │   ├── report_classifier.py                        # EMIS report type classification
│   │   ├── folder_manager.py                           # Folder hierarchy management
│   │   ├── search_manager.py                           # Search data management
│   │   ├── background_processor.py                     # Background processing
│   │   ├── optimized_processor.py                      # Processing integration
│   │   ├── session_state.py                            # Centralised session state with SNOMED cache
│   │   ├── update_versions.py                          # Version update utilities
│   │   └── version.py                                  # Application version management
│   ├── ui/                                             # 📁 **User interface components**
│   │   ├── ui_tabs.py                                  # Main results interface
│   │   ├── status_bar.py                               # Application status display
│   │   ├── ui_helpers.py                               # Reusable UI components
│   │   ├── rendering_utils.py                          # Standard UI components
│   │   ├── layout_utils.py                             # Complex layout management
│   │   ├── progressive_loader.py                       # Progressive loading components
│   │   ├── async_components.py                         # Asynchronous UI components
│   │   ├── theme.py                                    # Centralised theme constants
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
│   │   ├── export_debug.py                             # Export system debugging
│   │   ├── github_loader.py                            # External data loading
│   │   └── caching/                                    # 📁 **Comprehensive caching system**
│   │       ├── cache_manager.py                        # Centralised cache management with TTL
│   │       ├── lookup_cache.py                         # Core caching engine
│   │       └── generate_github_cache.py                # Cache generation utilities
│   └── common/                                         # 📁 **Shared utilities and infrastructure**
│       ├── error_handling.py                           # Standardised error management
│       ├── ui_error_handling.py                        # UI error display
│       ├── export_utils.py                             # Centralised export utilities
│       └── dataframe_utils.py                          # DataFrame operations
├── docs/                                               # 📁 **Technical documentation**
│   ├── architecture/                                   # 📁 **Architecture documentation**
│   │   ├── error-handling.md                           # Guide to catching and logging errors
│   │   ├── modules.md                                  # Module architecture guide
│   │   ├── session-state-management.md                 # Session state architecture
│   │   └── project-structure.md                        # This document
│   ├── terminology-server/                             # 📁 **NHS Terminology Server documentation**
│   │   ├── term-server-overview.md                     # User-focused integration guide
│   │   └── term-server-technical-guide.md              # Developer implementation reference
│   ├── emis-xml-patterns.md                            # EMIS XML pattern reference
│   ├── namespace-handling.md                           # Namespace handling guide
│   └── theme-colors.md                                 # Custom theme colour reference guide
├── img/                                                # 📁 **Application branding assets**
│   ├── logo.svg                                        # ClinXML medical cross icon
│   ├── clinxml.svg                                     # Full logo with text and tagline
│   ├── clinxml_title.svg                               # Text-only logo
│   └── favicon.ico                                     # Browser favicon
└── tests/                                              # 📁 **Test suite**
    ├── test_performance.py                             # Performance testing
    └── test_session_state.py                           # Session state unit tests
```

## 🏗️ Architecture Principles

### **Modular Design**
- **Separation of Concerns**: Each module has a single, well-defined responsibility
- **Dependency Injection**: Core modules are independent and can be easily tested
- **Interface Consistency**: Standard patterns across similar modules

### **Performance-First**
- **Caching Architecture**: Multi-layer caching with appropriate TTL strategies
- **Lazy Loading**: Resources loaded only when needed
- **Memory Management**: Automatic cleanup and garbage collection

### **Maintainability**
- **Centralised Configuration**: Theme, session state, and error handling centralised
- **Consistent Naming**: Clear, descriptive file and function names
- **Documentation**: Comprehensive inline documentation and architectural docs

## 📊 Key Architectural Components

### **Analysis Pipeline**
```
XML Upload → Element Classification → Specialized Analysis → Results Unification → UI Rendering
```

### **Caching Strategy**
```
Session State ←→ Streamlit Cache ←→ Persistent Cache ←→ GitHub/API Fallback
```

### **Export Pipeline**
```
Raw Data → Type-Specific Processing → Format Generation → User Download
```

### **SNOMED Cache Management**
```
60-minute TTL → Persistent Mappings → Cross-XML Reuse → Automatic Cleanup
```

## 🔧 Module Dependencies

### **Core Dependencies**
- **UI modules** → core, common, utils, terminology_server
- **Analysis modules** → xml_parsers, core, ui
- **Export handlers** → core, common, utils
- **Terminology server** → common (error handling), utils (caching), ui (theme), integrates across modules

### **Shared Modules**
- **common/**: Error handling, utilities (used by all modules)
- **core/session_state.py**: Session state management (used by all modules)
- **ui/theme.py**: Consistent styling (used by all UI modules)

## 📝 File Naming Conventions

### **Module Files**
- `*_analyzer.py` - Analysis engines
- `*_parser.py` - XML parsing modules
- `*_export.py` - Export handlers
- `*_tab.py` - UI tab modules
- `*_utils.py` - Utility functions
- `*_manager.py` - Data management modules

### **Configuration Files**
- `session_state.py` - Session state management
- `theme.py` - UI theme constants
- `version.py` - Application versioning
- `field_mapping.py` - Data field mappings

## 🚀 Development Guidelines

### **Adding New Modules**
1. Choose appropriate directory based on functionality
2. Follow naming conventions
3. Implement proper error handling
4. Add comprehensive docstrings
5. Update this documentation

### **Modifying Existing Modules**
1. Maintain backward compatibility
2. Update related documentation
3. Consider caching implications
4. Test across all affected areas

### **Performance Considerations**
- Use appropriate caching strategies
- Implement lazy loading where beneficial
- Consider memory usage for large datasets
- Monitor session state size

## 📚 Related Documentation

- **[Module Architecture Guide](architecture/modules.md)** - Detailed module descriptions
- **[Session State Management](architecture/session-state-management.md)** - Session state architecture
- **[NHS Terminology Server Overview](terminology-server/term-server-overview.md)** - User guide for terminology expansion
- **[NHS Terminology Server Technical Guide](terminology-server/term-server-technical-guide.md)** - Developer implementation reference
- **[EMIS XML Patterns](emis-xml-patterns.md)** - XML parsing patterns

---

*This document reflects the current architecture as of:

*Last Updated: 25th November 2025*  
*Application Version: 2.2.5*  

For specific module details, see the [Module Architecture Guide](architecture/modules.md).*