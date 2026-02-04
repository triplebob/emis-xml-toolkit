"""
NHS Terminology Server Integration for ClinXML

Provides SNOMED concept expansion using NHS England Terminology Server.

Main Components:
- NHSTerminologyClient: API client with OAuth2 authentication
- ExpansionService: Service layer with persistent caching

Usage:
    from utils.terminology_server import get_expansion_service

    # Configure service
    service = get_expansion_service()
    service.configure_credentials(client_id, client_secret)

    # Expand codes
    from utils.terminology_server import ExpansionConfig
    config = ExpansionConfig(include_inactive=False, use_cache=True)
    results = service.expand_codes_batch(["73211009"], config)
"""

from .client import (
    NHSTerminologyClient,
    TerminologyServerConfig,
    ExpansionResult,
    ExpandedConcept,
    ErrorCategory,
    TerminologyError,
    ERROR_MESSAGES,
)
from .service import (
    ExpansionService,
    ExpansionConfig,
    get_expansion_service
)
from .expansion_workflow import (
    ExpansionSelection,
    ExpansionRunResult,
    prepare_expansion_selection,
    run_expansion,
    prepare_child_codes_view,
    build_child_code_exports,
    build_child_code_export_options,
    build_hierarchical_json,
    build_emis_xml_export,
    build_expansion_summary_rows,
    expand_single_code,
    lookup_concept_display,
)
from .connection import test_connection

__all__ = [
    # Client
    "NHSTerminologyClient",
    "TerminologyServerConfig",
    "ExpansionResult",
    "ExpandedConcept",
    "ErrorCategory",
    "TerminologyError",
    "ERROR_MESSAGES",
    # Service
    "ExpansionService",
    "ExpansionConfig",
    "get_expansion_service",
    # Workflow
    "ExpansionSelection",
    "ExpansionRunResult",
    "prepare_expansion_selection",
    "run_expansion",
    "prepare_child_codes_view",
    "build_child_code_exports",
    "build_child_code_export_options",
    "build_hierarchical_json",
    "build_emis_xml_export",
    "build_expansion_summary_rows",
    "expand_single_code",
    "lookup_concept_display",
    "test_connection",
]
