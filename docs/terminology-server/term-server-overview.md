# NHS Terminology Server Integration - Overview

## What Is This Feature?

ClinXML provides seamless integration with the NHS England Terminology Server to automatically expand SNOMED CT codes that have `includeChildren=true` flags in your XML searches. This helps users return all child concepts that should be included when implementing search criteria outside of EMIS, or if a specific child code needs to be removed from a search (as the integrated internal EMIS browser only allows expansion of one level down the parent-child heirarchy).

## Key Benefits

### 🎯 Complete Code Coverage
- Automatically discovers all relevant child concepts
- Eliminates manual hierarchy traversal guesswork
- Ensures no important codes are missed in implementation

### 🔧 Implementation Support  
- Shows exact codes to add manually in EMIS
- Provides EMIS GUID mappings for direct implementation
- XML-ready output for copy-paste into queries

### 📊 Clinical Accuracy
- Uses official NHS England terminology data
- Ensures consistency with UK clinical standards
- Compares EMIS expectations vs current terminology server data

### ⚡ Professional Experience
- Real-time progress with accurate time estimates
- Individual code testing without XML processing
- Results persist across UI refreshes and downloads

## How It Works

### 1. Automatic Detection
The system automatically identifies SNOMED codes in your XML with expansion flags:
```xml
<includechildren>true</includechildren>
<include_children>true</include_children>
<Include Children>true</Include Children>
```

### 2. Intelligent Expansion
- **Progress Tracking**: Live updates showing "Expanding codes... 45/120 (37.5%) - Est. remaining: 23 seconds"
- **Smart Processing**: 8-20 concurrent workers scale automatically based on workload
- **Error Recovery**: Continues processing even if some codes fail

### 3. Comprehensive Results
- **Expansion Summary**: Parent codes with child counts (EMIS expected vs terminology server actual)
- **Detailed Child Codes**: Full list with EMIS GUID mappings and source tracking  
- **Export Options**: CSV, JSON, and XML formats for different use cases

## Getting Started

### Prerequisites
You need NHS England Terminology Server credentials:
- **System-to-System Account**: Apply through NHS England terminology portal
- **Credentials**: You'll receive `client_id` and `client_secret` 
- **Access**: Programmatic FHIR R4 API access

### Setup
Add your credentials to `.streamlit/secrets.toml`:
```toml
NHSTSERVER_ID = "Your_Organization_Consumer_ID"
NHSTSERVER_TOKEN = "your_client_secret_token"
```

### Basic Usage

1. **Process Your XML**: Upload and analyse your EMIS XML search file
2. **Navigate to NHS Term Server**: Go to Clinical Codes → NHS Term Server tab
3. **Review Detected Codes**: System shows codes with `includechildren=true`
4. **Configure Options**:
   - **Include inactive concepts**: Whether to include deprecated terms
   - **Use cached results**: Leverage previous expansions for speed
5. **Expand**: Click **🌳 Expand Child Codes** and monitor real-time progress
6. **Export Results**: Choose from multiple formats for your implementation needs

### Individual Code Testing

Test single codes without XML processing:
1. Use **🔍 Individual Code Lookup** section
2. Enter any SNOMED CT code (e.g., `73211009` for diabetes)
3. Results persist across page refreshes and are cached automatically

## Common Use Cases

### Diabetes Management Search
**Input**: `73211009` (Diabetes mellitus) with `includeChildren=true`
**Output**: All specific diabetes types:
- Type 1 diabetes mellitus (`46635009`)
- Type 2 diabetes mellitus (`44054006`)
- Gestational diabetes (`11687002`)
- Drug-induced diabetes (`4783006`)
- And many more specific subtypes

## Export Formats Explained

### CSV Summary
Expansion overview comparing EMIS expected vs terminology server actual child counts:
```csv
SNOMED Code,Description,EMIS Child Count,Term Server Child Count,Result Status,Expanded At
73211009,Diabetes mellitus,47,52,Matched - Found 52 children,2024-11-21 14:30:15
```

### Child Codes (SNOMED Only)
Clean clinical codes for professional use:
```csv
Parent Code,Parent Display,Child Code,Child Display,Inactive
73211009,Diabetes mellitus,46635009,Type 1 diabetes mellitus,False
73211009,Diabetes mellitus,44054006,Type 2 diabetes mellitus,False
```

### Child Codes with EMIS GUID
Implementation-ready mapping:
```csv
Parent Code,Child Code,Child Display,EMIS GUID,Source Type,Source Name
73211009,46635009,Type 1 diabetes mellitus,{guid-here},Search,Diabetes Register
73211009,44054006,Type 2 diabetes mellitus,{guid-here},Search,Diabetes Register
```

### Hierarchical JSON
Structured format for programmatic integration:
```json
{
  "source_filename": "diabetes_searches.xml",
  "expansion_date": "2024-11-21T14:30:15",
  "hierarchies": [
    {
      "parent_code": "73211009",
      "parent_display": "Diabetes mellitus",
      "child_count": 52,
      "children": [...]
    }
  ]
}
```

## Connection Status and Monitoring

The system provides real-time status monitoring:
- **Sidebar Status**: Live authentication status indicator
- **Progress Display**: Real-time completion with time estimates
- **Error Messages**: User-friendly guidance for common issues
- **Toast Notifications**: Connection updates during operations

## Limitations and Considerations

### Network Requirements
- Active internet connection required
- Subject to NHS terminology server availability
- API rate limits may apply for very large expansions

### Performance Expectations
- Small expansions (≤100 codes): typically complete in under 30 seconds
- Large expansions (≥500 codes): may take several minutes with progress tracking
- Very large hierarchies may have hundreds of children per parent code

### Data Considerations
- Results cached in session for performance and download persistence
- NHS server data follows official SNOMED release schedule
- EMIS lookup table may differ from current terminology server versions

## Getting Help

### Quick Troubleshooting
- **Authentication Issues**: Verify credentials in `.streamlit/secrets.toml`
- **No Results**: Use individual code lookup to test specific codes
- **Slow Performance**: System scales workers automatically based on workload
- **Missing Results**: Check expansion results table for detailed status information

### Common Error Messages
- **"NHS Terminology Server credentials invalid"** → Check your `client_id` and `client_secret`
- **"Code does not exist in terminology server"** → Verify SNOMED code is valid and properly formatted
- **"NHS Terminology Server experiencing issues"** → Temporary server problem, try again later

For technical implementation details, API specifications, and advanced configuration, see the [Technical Guide](technical-guide.md).

## Compliance and Security

- **No Patient Data**: Only SNOMED codes transmitted to NHS servers
- **Secure Authentication**: HTTPS and OAuth2 system-to-system authentication
- **Credential Security**: Stored securely in Streamlit configuration
- **Audit Logging**: Connection attempts logged for compliance purposes
- **Terms Compliance**: Usage subject to NHS England API terms of service

---

This integration provides healthcare professionals with reliable, accurate SNOMED code expansion capabilities essential for comprehensive clinical search implementation outside of EMIS environments.