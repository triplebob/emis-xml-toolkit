"""
Core modules for EMIS XML search analysis.
Contains business logic separated from UI and export components.
"""

from .report_classifier import ReportClassifier, classify_report_type, is_actual_search
from .folder_manager import FolderManager 
from .search_manager import SearchManager
from .translator import translate_emis_to_snomed

__all__ = [
    'ReportClassifier',
    'classify_report_type', 
    'is_actual_search',
    'FolderManager',
    'SearchManager',
    'translate_emis_to_snomed'
]
