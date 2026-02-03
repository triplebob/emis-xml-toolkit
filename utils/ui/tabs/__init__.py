"""
Tab rendering modules for the EMIS XML Toolkit UI.

This package contains modular tab rendering functions split from the original
monolithic ui_tabs.py file for better maintainability and organisation.

Modules:
- clinical_codes/clinical_tabs: Clinical codes, medications, refsets, and pseudo-refsets
- report_viewer: List, audit, and aggregate reports
- search_browser/analysis_tabs: Search analysis, XML structure, and detailed rules
- search_browser/search_tabs: Search tabs and related controls
- xml_inspector/xml_tab: XML browser and dependencies view
- analytics_tab: Processing analytics and quality metrics
"""

# Import all functions from the modular structure
from .clinical_codes.clinical_tabs import (
    render_summary_tab,
    render_clinical_codes_tab,
    render_medications_tab,
    render_refsets_tab,
    render_pseudo_refsets_tab,
    render_pseudo_refset_members_tab,
    render_analytics_tab,
    render_expansion_tab_content,
)
from .search_browser.analysis_tabs import render_search_analysis_tab
from .search_browser.search_tabs import render_search_tabs
from .xml_inspector.xml_tab import render_xml_tab
from .report_viewer import (
    render_list_reports_tab,
    render_audit_reports_tab,
    render_aggregate_reports_tab,
    render_reports_tab,
)

__all__ = [
    'render_summary_tab',
    'render_clinical_codes_tab',
    'render_medications_tab',
    'render_refsets_tab',
    'render_pseudo_refsets_tab',
    'render_pseudo_refset_members_tab',
    'render_analytics_tab',
    'render_expansion_tab_content',
    'render_search_tabs',
    'render_xml_tab',
    'render_list_reports_tab',
    'render_audit_reports_tab',
    'render_aggregate_reports_tab',
    'render_reports_tab',
    'render_search_analysis_tab',
]
