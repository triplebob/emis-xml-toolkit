# NHS England Terminology Server Integration

## Overview

The EMIS XML Toolkit now includes integration with the NHS England Terminology Server to automatically expand SNOMED CT codes that have <includeChildren>true</includeChildren> flags. This feature helps users discover all child concepts that should be included when implementing search criteria outside of EMIS.

## What It Does

When your XML analysis contains SNOMED codes with <includeChildren>true</includeChildren>, this feature:

1. **Detects Expandable Codes**: Automatically identifies codes that need child concept expansion
2. **Connects to NHS Terminology Server**: Uses your System-to-System credentials to query the official NHS England Terminology Server
3. **Expands Hierarchies**: Retrieves all descendant concepts (children, grandchildren, etc.) under each parent concept
4. **EMIS Integration**: Maps expanded concepts to EMIS GUIDs using the lookup table
5. **Comparison Analysis**: Shows EMIS expected vs actual child counts from terminology server
6. **Multiple Export Formats**: CSV, hierarchical JSON, and XML-ready formats for various use cases

## Setup Requirements

### 1. NHS England Terminology Server Account

You need a **System-to-System account** from NHS England:

- Apply through the NHS England terminology server portal
- You will receive a `client_id` and `client_secret`
- These credentials provide programmatic access to the FHIR R4 API

### 2. Configure Credentials

Add your credentials to `.streamlit/secrets.toml`:

```toml
NHSTSERVER_ID = "Your_Organization_Consumer_ID"
NHSTSERVER_TOKEN = "your_client_secret_token"
```

## How to Use

### 1. Access the Feature

After processing your XML file:

1. Go to the **Clinical Codes** main tab
2. Click on the **NHS Term Server** sub-tab
3. The system will automatically detect codes with `includechildren=True`

### 2. Expand Child Codes

1. Review the detected expandable codes
2. Choose expansion options:
   - **Include inactive concepts**: Whether to include deprecated concepts
   - **Use cached results**: Use previously cached expansions for performance
3. Click **🌳 Expand Child Codes**

### 3. Review and Export Results

The system provides:

- **Expansion Results Table**: Shows SNOMED code, description, EMIS child count (expected), terminology server child count (actual), status, and timestamp
- **Detailed Child Codes**: Full list of discovered descendant concepts with EMIS GUID mapping and source tracking
- **Export Options**:
  - **Summary CSV**: Expansion results with count comparisons
  - **Child Codes (SNOMED Only)**: Clean SNOMED codes and descriptions
  - **Child Codes (inc EMIS GUID)**: Child codes with EMIS GUID mappings for implementation
  - **Hierarchical JSON**: Parent-child relationships in structured format with source XML filename
  - **Individual Code Lookup**: Single code expansion for testing

## Integration Points

### Clinical Codes Tab Enhancement

The NHS Terminology Server integration appears in:

- **Sidebar**: Connection status monitoring (no manual connection testing)
- **NHS Term Server Tab**: Full expansion interface with hierarchical display
- **Toast Notifications**: Connection status updates during expansion operations
- **Cache Integration**: Uses cache-first approach for EMIS lookup table access

### Automatic Detection

The system detects `includechildren=True` in various formats:

```xml
<!-- Standard format -->
<includechildren>true</includechildren>

<!-- Alternative formats -->
<include_children>true</include_children>
<Include Children>true</Include Children>
```

## Technical Implementation

### Authentication Flow

1. **System-to-System OAuth2**: Uses client credentials grant
2. **Token Management**: Automatic token refresh (30-minute expiry)
3. **Secure Storage**: Credentials stored in Streamlit secrets

### API Operations

- **Connection Test**: Validates credentials and server access
- **Concept Lookup**: Retrieves concept details and display names  
- **Child Expansion**: Uses FHIR CodeSystem operations for hierarchy traversal

### Caching Strategy

- **Session-based**: Results cached in Streamlit session state for UI persistence
- **EMIS Lookup Integration**: Uses cache-first approach (local cache → GitHub cache → API fallback)
- **Expansion Results**: Cached to prevent loss during download operations
- **Configurable**: Can disable caching for real-time queries

## Usage Examples

### Example 1: Diabetes Concepts

**Input Code**: `73211009` (Diabetes mellitus) with `includechildren=True`

**Expected Output**: All specific diabetes types like:
- Type 1 diabetes mellitus
- Type 2 diabetes mellitus  
- Gestational diabetes
- Drug-induced diabetes
- etc.

### Example 2: Hypertension Hierarchy

**Input Code**: `38341003` (Hypertensive disorder) with `includechildren=True`

**Expected Output**: All hypertension subtypes:
- Essential hypertension
- Secondary hypertension
- Malignant hypertension
- White coat hypertension
- etc.

## Benefits for EMIS Implementation

### 1. Complete Code Coverage
- Ensures no relevant child concepts are missed
- Provides comprehensive search criteria

### 2. Implementation Guidance
- Shows exact codes to add manually in EMIS
- Eliminates guesswork about hierarchy scope

### 3. Clinical Accuracy
- Uses official NHS terminology data
- Ensures consistency with UK clinical standards
- Compares EMIS lookup table expectations with current terminology server data

### 4. Time Savings
- Automated discovery vs manual hierarchy traversal
- Instant access to current terminology versions
- Cache-first approach minimizes API calls

### 5. Implementation Support
- XML-ready output for direct copy-paste into EMIS queries
- Hierarchical JSON export for programmatic integration
- Source file tracking for traceability

## Limitations and Considerations

### 1. Network Dependency
- Requires active internet connection
- Subject to NHS terminology server availability
- API rate limits may apply for large expansions

### 2. Hierarchy Complexity
- Very large hierarchies may take time to expand
- Results limited to prevent timeouts (configurable)
- Some concepts may have hundreds of children

### 3. Data Freshness
- Results cached in session state for performance
- Expansion results persist across download operations
- NHS server updates follow official SNOMED release schedule
- EMIS lookup table cache may differ from current terminology server data

### 4. Authentication Requirements
- Requires valid NHS England system-to-system account
- Credentials must be kept secure and updated as needed
- Access subject to NHS England terms of service

## Error Handling

The system gracefully handles:

- **Network Issues**: Clear error messages and retry options
- **Authentication Failures**: Guidance on credential verification
- **API Limitations**: Fallback modes and partial results
- **Invalid Concepts**: Skips problematic codes with warnings

## Current Features and Capabilities

The integration currently provides:

1. **FHIR R4 Compliance**: Full NHS England Terminology Server API support
2. **Hierarchical Expansion**: Complete descendant concept discovery
3. **EMIS Integration**: Direct lookup table mapping and comparison
4. **Multiple Export Formats**: CSV, JSON, and XML-ready outputs
5. **Cache Optimization**: Multi-tier caching for optimal performance
6. **Source Tracking**: Full traceability to original XML files
7. **View Modes**: Unique codes vs per-source display options
8. **Real-time Status**: Connection monitoring and error handling

## Support

### Troubleshooting

**Connection Issues**:
1. Verify internet connectivity
2. Check NHS England terminology server status
3. Validate credentials in secrets.toml
4. Monitor sidebar status for authentication updates

**No Results Found**:
1. Confirm concept exists in SNOMED CT
2. Check if concept has child relationships
3. Review expansion results table for detailed status
4. Use individual code lookup for testing specific concepts

**Performance Issues**:
1. Expansion results are cached in session state
2. Cache-first approach reduces API calls
3. Large hierarchies display progress during expansion

**Export Issues**:
1. Results persist across download operations
2. Multiple format options available (CSV, JSON, XML)
3. Clean exports with emoji removal for professional use

### Getting Help

For technical issues:
1. Check the sidebar status for connection monitoring
2. Review expansion results table for detailed error information
3. Use individual code lookup to isolate specific issues
4. Monitor toast notifications for real-time status updates

For credential issues:
1. Contact NHS England terminology server support
2. Verify system-to-system account status
3. Check API access permissions
4. Ensure credentials are correctly formatted in secrets.toml

## Compliance and Security

- **Data Protection**: No patient data transmitted to NHS servers
- **API Security**: Uses HTTPS and OAuth2 authentication
- **Credential Security**: Secrets stored securely in Streamlit configuration
- **Usage Logging**: Connection attempts logged for audit purposes
- **Terms Compliance**: Usage subject to NHS England API terms of service

## API Technical Reference

### Authentication Flow

**OAuth2 System-to-System Authentication:**
```
POST https://ontology.nhs.uk/authorisation/auth/realms/terminology/protocol/openid-connect/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&client_id={NHSTSERVER_ID}&client_secret={NHSTSERVER_TOKEN}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 1800,
  "scope": "openid"
}
```

### FHIR R4 API Operations

**Base URL:** `https://ontology.nhs.uk/authoring/fhir`

**Standard Headers:**
```
Authorization: Bearer {access_token}
Accept: application/fhir+json
Content-Type: application/fhir+json
```

### Concept Expansion API

**Operation:** ValueSet $expand with Expression Constraint Language (ECL)

**Request Format:**
```
GET /ValueSet/$expand?url=http://snomed.info/sct?fhir_vs=ecl/< {snomed_code}&_format=json&count=1000&offset=0&activeOnly=true
```

**ECL Expression Details:**
- `< {snomed_code}` - Returns all descendant concepts (children, grandchildren, etc.)
- `activeOnly=true` - Excludes inactive/deprecated concepts (configurable)
- `count=1000` - Limits results to prevent timeouts
- `offset=0` - Pagination support for large hierarchies

**Example Request:**
```
GET /ValueSet/$expand?url=http://snomed.info/sct?fhir_vs=ecl/<%2073211009&_format=json&count=1000&offset=0&activeOnly=true
```
(Expands all descendants of diabetes mellitus - 73211009)

**Successful Response Structure:**
```json
{
  "resourceType": "ValueSet",
  "expansion": {
    "total": 47,
    "offset": 0,
    "parameter": [
      {
        "name": "version",
        "valueUri": "http://snomed.info/sct/83821000000107/version/20231101"
      }
    ],
    "contains": [
      {
        "system": "http://snomed.info/sct",
        "code": "44054006",
        "display": "Type 2 diabetes mellitus",
        "inactive": false
      },
      {
        "system": "http://snomed.info/sct", 
        "code": "46635009",
        "display": "Type 1 diabetes mellitus",
        "inactive": false
      }
    ]
  }
}
```

### Concept Lookup API

**Operation:** CodeSystem $lookup for individual concept validation

**Request Format:**
```
GET /CodeSystem/$lookup?system=http://snomed.info/sct&code={snomed_code}&_format=json
```

**Example Request:**
```
GET /CodeSystem/$lookup?system=http://snomed.info/sct&code=73211009&_format=json
```

**Successful Response Structure:**
```json
{
  "resourceType": "Parameters",
  "parameter": [
    {
      "name": "name",
      "valueString": "SNOMEDCT"
    },
    {
      "name": "display",
      "valueString": "Diabetes mellitus"
    },
    {
      "name": "designation",
      "part": [
        {
          "name": "language",
          "valueCode": "en"
        },
        {
          "name": "use",
          "valueCoding": {
            "system": "http://snomed.info/sct",
            "code": "900000000000013009",
            "display": "Synonym"
          }
        },
        {
          "name": "value",
          "valueString": "Diabetes mellitus"
        }
      ]
    }
  ]
}
```

### Error Response Handling

**HTTP Status Codes and Responses:**

**401 Unauthorized:**
```json
{
  "resourceType": "OperationOutcome",
  "issue": [
    {
      "severity": "error",
      "code": "login",
      "details": {
        "text": "Authentication failed"
      }
    }
  ]
}
```

**404 Not Found (Invalid SNOMED Code):**
```json
{
  "resourceType": "OperationOutcome", 
  "issue": [
    {
      "severity": "error",
      "code": "not-found",
      "details": {
        "text": "Code does not exist in terminology server"
      }
    }
  ]
}
```

**422 Unprocessable Entity (Invalid ECL/Request):**
```json
{
  "resourceType": "OperationOutcome",
  "issue": [
    {
      "severity": "error", 
      "code": "invalid",
      "details": {
        "text": "Invalid expression constraint language"
      }
    }
  ]
}
```

**500 Internal Server Error:**
```
Generic server error - handled as "Terminology server error"
```

### Application Error Mapping

**Client Error Handling:**
- **404 Response** → "Code does not exist in terminology server"
- **401 Response** → Automatic token refresh attempted once
- **422 Response** → "Invalid concept or request format"
- **500+ Response** → "Terminology server error"
- **Network Exception** → "Connection error: {details}"
- **Timeout** → "Request timed out"

### Rate Limiting and Performance

**API Constraints:**
- **Token Expiry**: 30 minutes (1800 seconds)
- **Request Timeout**: 30 seconds per request
- **Batch Limit**: 1000 concepts per expansion request
- **Pagination**: Offset-based for large result sets

**Application Optimizations:**
- Automatic token refresh on 401 responses
- Progress tracking for batch operations
- Graceful timeout handling with partial results
- Session state caching to prevent duplicate API calls

## Technical Architecture

### Cache Integration
- **EMIS Lookup Table**: Uses cache-first approach (local cache → GitHub cache → API fallback)
- **Session State**: Expansion results cached for UI persistence
- **Download Persistence**: Results remain available during export operations

### Data Flow
1. **Detection**: Automatic identification of <includeChildren>true</includeChildren> codes
2. **Authentication**: System-to-system OAuth2 with NHS England
3. **Expansion**: FHIR R4 API calls for hierarchical concept retrieval
4. **Integration**: EMIS GUID mapping using cached lookup table
5. **Export**: Multiple format generation with clean, professional output

### Export Formats
- **CSV Summary**: Expansion results with EMIS vs terminology server comparison
- **CSV Child Codes**: Clean SNOMED codes and descriptions
- **CSV EMIS Import**: Child codes with EMIS GUID mappings
- **JSON Hierarchical**: Parent-child relationships with source file tracking
- **XML Output**: Copy-paste ready XML for EMIS query implementation

---

This integration provides comprehensive NHS terminology server capabilities with optimized performance, multiple export options, and full EMIS lookup table integration.
