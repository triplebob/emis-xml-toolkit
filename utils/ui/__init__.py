"""
UI utilities for the EMIS XML Converter application.
Exports the top-level entry points used by the app shell.
"""

from .ui_tabs import render_results_tabs
from .status_bar import render_status_bar, render_performance_controls, display_performance_metrics
from .theme import apply_custom_styling

__all__ = [
    'render_results_tabs',
    'render_status_bar',
    'render_performance_controls',
    'display_performance_metrics',
    'apply_custom_styling',
]
