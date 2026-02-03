"""
NHS Terminology Server UI Components

Provides UI tabs for SNOMED concept expansion:
- expansion_tab: Integrated within Clinical Codes for batch expansion
- lookup_tab: Standalone top-level tab for single code lookup
"""

from .expansion_tab import render_expansion_tab_content
from .lookup_tab import render_individual_code_lookup

__all__ = [
    "render_expansion_tab_content",
    "render_individual_code_lookup",
]
