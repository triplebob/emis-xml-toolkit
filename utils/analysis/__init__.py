"""
Analysis utilities for EMIS XML processing
Handles search rule visualization, linked criteria analysis, and performance optimization
"""

# Import core functions
from .xml_structure_analyzer import analyze_search_rules
from .performance_optimizer import render_performance_controls, display_performance_metrics

__all__ = [
    'analyze_search_rules',
    'render_performance_controls',
    'display_performance_metrics'
]
