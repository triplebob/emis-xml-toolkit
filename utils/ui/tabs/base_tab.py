from ...ui.theme import info_box, success_box, warning_box, error_box
"""
Base classes and common functionality for tab rendering.

This module provides abstract base classes and shared utilities that all
tab rendering modules can inherit from or use.
"""

from abc import ABC, abstractmethod
from .common_imports import *
from ...core.session_state import SessionStateKeys
from typing import Dict, Any, Optional
import streamlit as st


class BaseTab(ABC):
    """Abstract base class for all tab renderers"""
    
    def __init__(self, session_state: Optional[Dict[str, Any]] = None):
        """
        Initialize the tab with session state
        
        Args:
            session_state: Streamlit session state dict. If None, uses st.session_state
        """
        self.session_state = session_state or st.session_state
    
    @abstractmethod
    def render(self, *args, **kwargs) -> None:
        """
        Render the tab content
        
        Must be implemented by all subclasses
        """
        pass
    
    def _get_cached_analysis(self) -> Optional[Any]:
        """
        Common method to get cached analysis from session state
        
        Returns:
            Analysis object if available, None otherwise
        """
        return (self.session_state.get('search_analysis') or 
                self.session_state.get('xml_structure_analysis'))
    
    def _handle_missing_data(self, message: str, icon: str = "📋") -> None:
        """
        Standardized missing data handling
        
        Args:
            message: Message to display to user
            icon: Icon to show with the message
        """
        st.markdown(info_box(f"{icon} {message}"), unsafe_allow_html=True)
    
    def _handle_error(self, error: Exception, context: str = "processing") -> None:
        """
        Standardized error handling for tabs
        
        Args:
            error: The exception that occurred
            context: Description of what was being done when error occurred
        """
        st.markdown(error_box(f"❌ Error during {context}: {str(error)}"), unsafe_allow_html=True)
        
        # Show detailed error in expander for debugging
        with st.expander("🔍 Error Details", expanded=False):
            import traceback
            st.code(traceback.format_exc())
    
    def _get_current_deduplication_mode(self) -> str:
        """
        Get current deduplication mode from session state
        
        Returns:
            Current deduplication mode, defaults to 'unique_codes'
        """
        return self.session_state.get('current_deduplication_mode', 'unique_codes')
    
    def _create_deduplication_toggle(self, key: str, help_text: str) -> str:
        """
        Create standardized deduplication mode toggle
        
        Args:
            key: Unique key for the selectbox
            help_text: Help text for the selectbox
            
        Returns:
            Selected deduplication mode
        """
        current_mode = self._get_current_deduplication_mode()
        
        col1, col2 = st.columns([4, 1])
        with col2:
            dedup_mode = st.selectbox(
                "Code Display Mode (will trigger reprocessing):",
                options=['unique_codes', 'unique_per_entity'],
                format_func=lambda x: {
                    'unique_codes': '🔀 Unique Codes', 
                    'unique_per_entity': '📍 Per Source'
                }[x],
                index=0 if current_mode == 'unique_codes' else 1,
                key=key,
                help=help_text
            )
        
        # Check if mode changed and trigger reprocessing
        if dedup_mode != current_mode:
            self.session_state.current_deduplication_mode = dedup_mode
            # Trigger reprocessing with new mode if we have the necessary data
            if ('emis_guids' in self.session_state and 'lookup_df' in self.session_state):
                self._reprocess_with_new_mode(dedup_mode)
        
        return dedup_mode
    
    def _reprocess_with_new_mode(self, mode: str) -> None:
        """
        Trigger reprocessing when deduplication mode changes
        
        Args:
            mode: New deduplication mode
        """
        # Import here to avoid circular imports
        from ...core.translator import translate_emis_to_snomed
        
        try:
            emis_guids = self.session_state.get('emis_guids', [])
            lookup_df = self.session_state.get('lookup_df')
            
            if emis_guids and lookup_df is not None:
                # Trigger reprocessing with new deduplication mode
                new_results = translate_emis_to_snomed(
                    emis_guids, 
                    lookup_df, 
                    deduplication_mode=mode
                )
                
                # Update session state with new results
                for key, value in new_results.items():
                    self.session_state[key] = value
                
                st.rerun()  # Force page refresh to show updated data
        except Exception as e:
            self._handle_error(e, "reprocessing with new deduplication mode")


class TabRenderer:
    """
    Utility class for rendering tabs without inheritance
    
    Use this for simple functional tabs that don't need the full BaseTab interface
    """
    
    @staticmethod
    def handle_missing_data(message: str, icon: str = "📋") -> None:
        """Static version of missing data handler"""
        st.markdown(info_box(f"{icon} {message}"), unsafe_allow_html=True)
    
    @staticmethod
    def handle_error(error: Exception, context: str = "processing") -> None:
        """Static version of error handler"""
        st.markdown(error_box(f"❌ Error during {context}: {str(error)}"), unsafe_allow_html=True)
        
        with st.expander("🔍 Error Details", expanded=False):
            import traceback
            st.code(traceback.format_exc())
    
    @staticmethod
    def get_cached_analysis() -> Optional[Any]:
        """Static version of analysis getter"""
        return (st.session_state.get(SessionStateKeys.SEARCH_ANALYSIS) or 
                st.session_state.get(SessionStateKeys.XML_STRUCTURE_ANALYSIS))
