"""
Common imports used across tab modules.

This module centralizes all the common imports to reduce duplication
and make dependency management easier.
"""

# Standard library imports
import streamlit as st
import pandas as pd
import io
import json
import copy
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable

# UI helpers - import from parent directory
from ..ui_helpers import (
    render_section_with_data, 
    render_metrics_row, 
    render_success_rate_metric,
    get_success_highlighting_function,
    get_warning_highlighting_function,
    create_expandable_sections,
    render_info_section
)

# Core modules - import from utils root
from ...core.report_classifier import ReportClassifier
from ...core.folder_manager import FolderManager
from ...core.search_manager import SearchManager

# Analysis modules
from ...analysis.search_rule_visualizer import (
    render_detailed_rules, 
    render_complexity_analysis, 
    export_rule_analysis,
    generate_rule_analysis_report
)
from ...analysis.report_structure_visualizer import (
    render_dependency_tree,
    render_folder_structure
)

# Export handlers
from ...export_handlers import UIExportManager
from ...export_handlers.report_export import ReportExportHandler

# Core translation and lookup
from ...core.translator import translate_emis_to_snomed
from ...utils.lookup import get_optimized_lookup_cache

# Re-export commonly used functions for convenience
__all__ = [
    # Standard library
    'st', 'pd', 'io', 'json', 'copy', 'datetime', 'Dict', 'Any', 'Optional', 'List', 'Callable',
    
    # UI helpers
    'render_section_with_data', 'render_metrics_row', 'render_success_rate_metric',
    'get_success_highlighting_function', 'get_warning_highlighting_function',
    'create_expandable_sections', 'render_info_section',
    
    # Core modules
    'ReportClassifier', 'FolderManager', 'SearchManager',
    
    # Analysis modules  
    'render_detailed_rules', 'render_complexity_analysis', 'export_rule_analysis',
    'generate_rule_analysis_report', 'render_dependency_tree', 'render_folder_structure',
    
    # Export handlers
    'UIExportManager', 'ReportExportHandler',
    
    # Translation and lookup
    'translate_emis_to_snomed', 'get_optimized_lookup_cache'
]
