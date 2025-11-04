"""
Caching utilities for EMIS XML Converter.

This module provides centralized caching functionality with properly sized limits
for different data types including SNOMED lookups, report rendering, and UI components.
"""

from .cache_manager import cache_manager

__all__ = ['cache_manager']