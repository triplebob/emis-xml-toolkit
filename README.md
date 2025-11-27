![ClinXML - The Unofficial EMIS XML Toolkit](img/clinxml.svg)

A comprehensive web application for analysing EMIS XML files with advanced search logic analysis, NHS terminology server integration, and clinical code translation. 
Transform complex EMIS XML documents into actionable insights for NHS healthcare teams.

## ClinXML At a Glance

| **Feature** | **Capability** | **Benefit** |
|-------------|----------------|-------------|
| **Code Translation** | EMIS GUID → SNOMED via cached lookup tables | Instant code translation without external dependencies |
| **NHS API Support** | Optional FHIR R4 hierarchy expansion | Live validation against current NHS terminology |
| **Search Analysis** | Multi-tab interface for all EMIS XML types | Complete visibility into search logic and dependencies |
| **Export System** | Excel, CSV, JSON, XML-ready formats | Ready-to-use outputs for external systems |
| **Performance** | Session caching + adaptive threading | Process large XMLs efficiently on any device |
| **Security** | Local processing, optional NHS API | XML data never leaves your session |

---

## Key Features

<details>
<summary><strong>Complete Analysis Interface (5 Tabs)</strong></summary>

- **Clinical Codes**: Advanced SNOMED translation with NHS terminology server integration and dual-mode deduplication
- **Search Analysis**: Rule Logic Browser with detailed criterion analysis and dependency visualisation
- **List Reports**: Column structure analysis with healthcare context and filter logic
- **Audit Reports**: Multi-population analysis with organisational grouping and quality indicators  
- **Aggregate Reports**: Statistical analysis with cross-tabulation

</details>

<details>
<summary><strong>NHS Terminology Server Integration</strong></summary>

- **FHIR R4 API Integration**: Direct connection to NHS England Terminology Server
- **Hierarchical Code Expansion**: Automatic expansion of codes with `includechildren=true` flags  
- **Adaptive Threading**: Scales 8-20 concurrent workers based on workload size for optimal performance
- **Session-based Caching**: Eliminates repeated API calls with intelligent result caching
- **EMIS Comparison Analysis**: Compare EMIS expected vs actual child counts from terminology server
- **Multiple Export Formats**: CSV, hierarchical JSON, and XML-ready outputs
- **Real-time Validation**: Individual code lookup and testing capabilities

</details>

<details>
<summary><strong>Advanced XML Pattern Support</strong></summary>

- **baseCriteriaGroup**: Nested criterion logic within wrapper criteria
- **Linked Criteria**: Cross-table relationships with temporal constraints
- **SNOMED Refsets**: Direct code handling with clean description extraction
- **EMISINTERNAL Classifications**: Episode types, consultation headings, clinical status
- **Complex Restrictions**: "Latest N WHERE condition" with test attributes

</details>

<details>
<summary><strong>Comprehensive Export System</strong></summary>

- **Multi-sheet Excel exports** with professional formatting
- **NHS terminology exports**: SNOMED codes, EMIS mappings, hierarchical JSON
- **Type-specific report exports** for List/Audit/Aggregate reports
- **Smart filtering**: Export all codes, matched only, or unmatched only
- **Multiple formats**: Excel, CSV, JSON, XML-ready, and TXT reports
- **Source attribution**: Track codes to their originating searches/reports

</details>

<details>
<summary><strong>Cache-First Architecture</strong></summary>

- **Multi-tier caching**: Local cache → GitHub cache → API fallback
- **Optimised performance**: Faster startup and reduced external dependencies
- **Session persistence**: Results maintained across download operations
- **Health monitoring**: Automatic cache validation and regeneration

</details>

<details>
<summary><strong>Enterprise Features</strong></summary>

- **Hierarchical folder management** with multi-level navigation
- **Supports EMIS QOF indicators** and custom healthcare quality metrics
- **Multi-organisation support** for EMIS Enterprise exports
- **Clinical pathway analysis** with workflow context
- **Version independence** across EMIS system versions

</details>

---

## Supported EMIS XML Types

ClinXML supports all standard EMIS XML exports with specialised analysis for each type:

- **Search Reports**: Population-based searches with complex criteria and dependency analysis
- **List Reports**: Multi-column data extraction with healthcare context classification
- **Audit Reports**: Quality monitoring with multi-population analysis and metadata
- **Aggregate Reports**: Statistical analysis with cross-tabulation and enterprise reporting
- **Demographics & LSOA**: Future-proof LSOA detection with grouped criteria analysis

📋 **[Complete XML Pattern Reference](docs/emis-xml-patterns.md)** - Detailed technical patterns and examples

---

## Clinical Code Systems

Translates EMIS GUIDs to SNOMED CT codes with comprehensive system support:

- **SNOMED CT**: Full concept hierarchy with NHS terminology server expansion
- **dm+d Medications**: Dictionary of medicines and devices with brand/generic classifications
- **EMIS Internal**: Episode types, consultation headings, and clinical status codes
- **Legacy Systems**: Read codes via mapping tables for backward compatibility

💊 **[Complete Code System Reference](docs/emis-xml-patterns.md#clinical-code-systems)** - Full technical specifications

---

## Quick Start

### Option 1: Use Live App (Recommended)

<details>
<summary>No installation required - <strong><a href="https://clinxml.streamlit.app/">Access Live Application</a></strong></summary>

1. Upload your EMIS XML file
2. View comprehensive analysis across 5 specialised tabs
3. Use NHS terminology server features (credentials pre-configured)
4. Export detailed reports in multiple formats
5. Navigate folder structures and analyse dependencies

</details>

### Option 2: Run Locally

#### Prerequisites
- **Python 3.8-3.12** (tested and verified)
- **Pinned dependencies** as specified in requirements.txt
- MKB lookup table with EMIS GUID to SNOMED mappings
- NHS England System-to-System credentials (optional, for terminology server features)

#### Installation
```bash
git clone https://github.com/triplebob/emis-xml-toolkit.git
cd emis-xml-toolkit
pip install -r requirements.txt
```

#### Configuration (Optional)
Create `.streamlit/secrets.toml` for NHS terminology server integration:
```toml
NHSTSERVER_ID = "Your_Organisation_Consumer_ID"
NHSTSERVER_TOKEN = "your_client_secret_token"
```

#### Run Application
```bash
streamlit run streamlit_app.py
```

<details>

<summary><strong>Quick Reference Commands</strong></summary>

```bash
# Clone and setup
git clone https://github.com/triplebob/emis-xml-toolkit.git
cd emis-xml-toolkit && pip install -r requirements.txt

# Run locally
streamlit run streamlit_app.py

# Run tests (performance & session state tests included)
python -m unittest discover tests/

# Check dependencies
pip list | grep -E "(streamlit|pandas|requests)"

# View logs (check terminal output or OS-specific Streamlit logs)
streamlit run streamlit_app.py --logger.level debug
```

</details>

---

## System Architecture

*High-level Overview*

![ClinXML System Architecture - XML upload flows through parsers to translation engine to 5-tab interface to export system with optional NHS terminology integration](img/architecture-diagram.svg)

**Please see [full interactive architecture diagram](docs/architecture/system-architecture-diagram.md) for complete component details**

---

## Project Structure

ClinXML uses a modular architecture with specialised components for analysis, UI rendering, export functionality, and caching. 
The codebase is organised into logical directories that separate functions and enable maintainable development.

**📋 [Complete Project Structure Documentation](docs/project-structure.md)**

### Key Directories
```
utils/analysis/               - Analysis engines and orchestration
utils/core/                   - Business logic and session management with 60-minute SNOMED caching
utils/ui/tabs/                - Modular tab structure for specialised report types
utils/export_handlers/        - Comprehensive export system for multiple formats
utils/terminology_server/     - NHS Terminology Server FHIR R4 integration
utils/xml_parsers/            - Modular XML parsing with universal namespace handling
utils/caching/                - Multi-tier caching architecture
docs/                         - Technical documentation and architecture guides
```

---

## Technical Specifications

<details>

<summary><strong>Performance Optimizations</strong></summary>

- **Centralised Cache Management**: Unified caching architecture with optimised TTL settings
- **Persistent SNOMED Cache**: 60-minute session state cache for EMIS GUID → SNOMED mappings across XML uploads
- **Report-Specific Caching**: Instant dropdown switching with 10,000-entry SNOMED cache
- **Memory Management**: Real-time monitoring with automatic garbage collection
- **Dictionary-based Lookups**: O(1) SNOMED translation (100x faster than DataFrame searches)
- **Progressive Loading**: Section-by-section rendering with native Streamlit spinners
- **Lazy Export Generation**: Export files created only when requested

</details>

<details>

<summary><strong>NHS Terminology Server Integration</strong></summary>

- **FHIR R4 Compliance**: Full NHS England Terminology Server API support
- **OAuth2 Authentication**: System-to-system authentication with automatic token refresh
- **ECL Support**: Expression Constraint Language for hierarchical expansion
- **Adaptive Threading**: Dynamic worker scaling (8-20 workers) optimised for Streamlit Cloud 2.7GB limits
- **Session Caching**: Intelligent result caching eliminates repeated API calls for instant reuse
- **Rate Limiting**: Graceful handling of API constraints and timeouts

**Terminology Server Fallback Matrix:**
```
Code Lookup Priority:
1. Session Cache      → Instant (if previously fetched)
2. GitHub Cache       → ~2-3 seconds (bulk EMIS mappings)
3. NHS API Direct     → ~5-15 seconds (live validation)
4. Graceful Degradation → Show unmapped codes with explanatory message

Error States:
• API Unavailable     → Fall back to cached mappings only
• Authentication Fail → Disable hierarchy expansion, core translation continues  
• Rate Limited        → Exponential backoff with cache fallback
• Network Timeout     → Retry with cached results where available
```

</details>

<details>

<summary><strong>XML Processing & Data Management</strong></summary>

**XML Processing:**
- **Universal Namespace Handling**: Mixed namespaced/non-namespaced document support
- **Robust Error Handling**: Comprehensive exception management with graceful degradation
- **Memory Optimisation**: Efficient processing of large XML files (40+ entities)
- **Cloud Compatibility**: Optimised for Streamlit Cloud deployment

**Data Management:**
- **Dual-mode Deduplication**: Unique codes vs per-source tracking
- **Session State Integration**: Persistent analysis across tab navigation
- **Export Filtering**: Conditional data inclusion based on user selection
- **Source Attribution**: Track clinical codes to originating searches/reports

**Browser Compatibility:**
- **Chrome/Edge**: Recommended (full feature support)
- **Firefox/Safari**: Supported (core functionality)
- **Mobile**: Limited support (view-only recommended)

</details>

---

## Use Cases

<details>
<summary><strong>Clinical Governance</strong></summary>

- **QOF Indicator Analysis**: Quality and Outcomes Framework reporting
- **Clinical Pathway Review**: Analyse complex care pathways and protocols
- **Code Set Validation**: Verify SNOMED code usage and mapping accuracy with NHS terminology server
- **Search Logic Auditing**: Review and optimise clinical search criteria
- **Hierarchy Validation**: Compare EMIS expectations with current NHS terminology data

</details>

<details>
<summary><strong>System Administration</strong></summary>

- **EMIS Configuration Review**: Analyse search and report configurations
- **Folder Organisation**: Review hierarchical folder structures
- **Dependency Mapping**: Understand search and report relationships
- **Performance Analysis**: Identify complex searches and optimisation opportunities
- **Terminology Updates**: Validate code hierarchies against current NHS terminology

</details>

<details>
<summary><strong>Healthcare Analytics</strong></summary>

- **Population Analysis**: Understand search population logic and criteria
- **Report Structure Review**: Analyse List/Audit/Aggregate report configurations
- **Clinical Code Translation**: Convert EMIS codes to SNOMED for external systems
- **Quality Measurement**: Export data for external quality measurement tools
- **Hierarchical Analysis**: Export parent-child relationships for programmatic integration

</details>

---

## Security & Privacy

<details>
<summary><strong>Data Handling</strong></summary>

- **No Persistent Storage**: XML files processed in memory only, deleted when session ends
- **Session-based Processing**: All data cleared when browser session terminates
- **Local SNOMED Translation**: Core EMIS GUID → SNOMED translation performed locally using pre-cached lookup tables
- **XML Data Isolation**: Uploaded XML files remain in user's browser session, never transmitted externally

</details>

<details>
<summary><strong>NHS API Security</strong></summary>

- **Controlled API Usage**: Only NHS Terminology Server accessed (optional, credentials required) for:
  - Individual SNOMED code validation
  - Hierarchical code expansion (`includeChildren=true`)
  - Parent-child relationship verification
- **API Data Scope**: Only SNOMED codes (not XML content) sent to NHS API for validation/expansion
- **OAuth2 Authentication**: Optional system-to-system authentication with NHS England for terminology features only
- **No XML Transmission**: Patient data and XML content never sent to external APIs

</details>

<details>
<summary><strong>Compliance Considerations</strong></summary>

- **IG Toolkit Compatible**: Designed for NHS IG Toolkit compliance
- **GDPR Aligned**: No persistent data storage or tracking
- **Audit Trail**: Processing statistics available for governance
- **Version Transparency**: Lookup table versions clearly displayed
- **NHS Terms Compliance**: Usage subject to NHS England API terms of service

</details>

---

## Contributing

Contributions welcome - **[View Contribution Guidelines](CONTRIBUTING.md)**

- **Bug Reports**: Detailed XML examples (anonymised) with reproduction steps
- **Feature Requests**: New EMIS XML patterns or export formats
- **Documentation**: Technical patterns and identification guides

---

## Legal & Compliance

**Disclaimer**: **EMIS and EMIS Web are trademarks of Optum Inc.** This unofficial toolkit is not affiliated with, endorsed by, or sponsored by Optum Inc, EMIS Health, NHS England, or any subsidiaries.

**License**: Provided as-is for healthcare and research. Users responsible for data protection and clinical governance compliance.

**No Warranty**: Healthcare professionals must validate all clinical code translations before clinical use.

---

## Support

**[Complete Documentation Hub](docs/)** with technical guides:

- [Project Structure](docs/project-structure.md) - Directory organisation
- [Architecture Guide](docs/architecture/modules.md) - System design  
- [NHS Integration](docs/nhs-terminology-server-integration.md) - API reference
- [XML Patterns](docs/emis-xml-patterns.md) - Technical patterns
- [Namespace Handling](docs/namespace-handling.md) - XML processing

---

*Last Updated: 27th November 2025*  
*Application Version: [2.2.6](changelog.md) • [View Release Notes](changelog.md)*
