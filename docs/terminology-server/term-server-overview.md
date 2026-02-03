# NHS Terminology Server Integration - Overview

## What This Feature Provides

ClinXML integrates with the NHS terminology service to support:

- SNOMED concept lookup for individual codes
- Child code expansion for criteria using include-children semantics
- EMIS GUID mapping checks against the local lookup cache

The integration is optional. Core XML parsing and clinical translation still work without NHS credentials.

## Where It Appears in the App

- **Code Lookup** top-level tab: single-code lookup and child concept retrieval
- **Clinical Codes -> Child Code Finder** subtab: batch expansion for codes extracted from uploaded XML

## Basic Setup

Add credentials to `.streamlit/secrets.toml`:

```toml
NHSTSERVER_ID = "your_client_id"
NHSTSERVER_TOKEN = "your_client_secret"
```

## Typical Workflow

1. Upload and process an EMIS XML file.
2. Open **Clinical Codes -> Child Code Finder**.
3. Review detected expandable codes.
4. Configure options:
   - include inactive concepts
   - use cached expansion results
   - skip codes with zero known descendants
5. Run expansion and review summary + child rows.
6. Export filtered results (CSV) and optional XML snippet output.

For one-off checks, use the **Code Lookup** tab instead of uploading XML.

## What Is Returned

Expansion outputs include:

- Parent code + display
- Child code + display
- Inactive status
- EMIS GUID match (if present in lookup cache)
- Source tracking fields in per-source views

## Caching Behavior

- Expansion results use a session-state cache in `service.py`
- Default expansion cache TTL is 90 minutes
- Cache size is bounded (oldest entries are evicted when full)
- Optional "use cache" toggles allow reuse of prior results

## Reliability Characteristics

- OAuth2 client-credentials auth with token refresh behavior
- Request retry/backoff handling for common transient failures
- Rate limiting in the terminology client
- Structured error messages shown in the UI

## Security Notes

- Only terminology queries (SNOMED-related) are sent to NHS endpoints
- Uploaded XML content is not submitted to NHS APIs
- Credentials are read from Streamlit secrets at runtime

## Related Docs

- Technical implementation: `term-server-technical-guide.md`
- Main architecture context: `../architecture/modules.md`
- System architecture view: `../architecture/system-architecture-diagram.md`

---

*Last Updated: 2nd February 2026*  
*Application Version: 3.0.0*
