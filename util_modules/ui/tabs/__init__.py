"""
Tab rendering modules for the EMIS XML Toolkit UI.

This package contains modular tab rendering functions split from the original
monolithic ui_tabs.py file for better maintainability and organization.

Modules:
- clinical_tabs: Clinical codes, medications, refsets, and pseudo-refsets
- report_tabs: List, audit, and aggregate reports 
- analysis_tabs: Search analysis, XML structure, and detailed rules
- analytics_tab: Processing analytics and quality metrics
"""

# Import all functions from the new modular structure
from .clinical_tabs import (
    render_summary_tab,
    render_clinical_codes_tab,
    render_medications_tab,
    render_refsets_tab,
    render_pseudo_refsets_tab,
    render_pseudo_refset_members_tab,
    render_results_tabs,
    render_clinical_codes_main_tab
)

# Import tab functions from specialized modules
from .list_report_tab import render_list_reports_tab
from .audit_report_tab import render_audit_reports_tab  
from .aggregate_report_tab import render_aggregate_reports_tab

from .report_tabs import (
    render_report_type_browser,
    render_reports_tab
)

from .analysis_tabs import (
    render_search_analysis_tab,
    render_xml_structure_tabs,
    render_folder_structure_tab,
    render_dependencies_tab,
    render_detailed_rules_tab
)

from .analytics_tab import render_analytics_tab

# For legacy compatibility - all functions available at package level
__all__ = [
    'render_summary_tab',
    'render_clinical_codes_tab',
    'render_medications_tab',
    'render_refsets_tab',
    'render_pseudo_refsets_tab',
    'render_pseudo_refset_members_tab',
    'render_results_tabs',
    'render_clinical_codes_main_tab',
    'render_list_reports_tab',
    'render_audit_reports_tab',
    'render_aggregate_reports_tab',
    'render_report_type_browser',
    'render_reports_tab',
    'render_search_analysis_tab',
    'render_xml_structure_tabs',
    'render_folder_structure_tab',
    'render_dependencies_tab',
    'render_detailed_rules_tab',
    'render_analytics_tab'
]