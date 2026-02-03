"""
General utilities for the EMIS XML Converter application
Provides GitHub integration and debugging functionality
"""

from .debug_logger import get_debug_logger, render_debug_controls, run_test_suite

__all__ = [
    # Debug and logging
    'get_debug_logger',
    'render_debug_controls',
    'run_test_suite',
    
]
