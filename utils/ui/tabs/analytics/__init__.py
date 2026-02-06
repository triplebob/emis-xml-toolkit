"""
Analytics tab package.

Provides high-level analytics and reporting views:
- XML Overview: Processing metrics, quality indicators, code system breakdowns
- MDS (Minimum Dataset): Entity-first code extraction + lazy CSV export
"""

from .xml_overview_tab import render_xml_overview_tab
from .mds_tab import render_mds_tab

__all__ = [
    "render_xml_overview_tab",
    "render_mds_tab",
]
