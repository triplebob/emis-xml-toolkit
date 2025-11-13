"""
General utilities for the EMIS XML Converter application
Provides text processing, GitHub integration, debugging, and audit functionality
"""

# Only import what we know exists and works
from .text_utils import pluralize_unit, format_operator_text, format_clinical_description
from .debug_logger import get_debug_logger, render_debug_controls, run_test_suite
from .github_loader import GitHubLookupLoader
from .audit import create_processing_stats

__all__ = [
    # Text utilities
    'pluralize_unit',
    'format_operator_text', 
    'format_clinical_description',
    
    # GitHub integration
    'GitHubLookupLoader',
    
    # Debug and logging
    'get_debug_logger',
    'render_debug_controls',
    'run_test_suite',
    
    # Audit
    'create_processing_stats'
]
