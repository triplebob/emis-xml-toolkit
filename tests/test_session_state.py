"""
Session State Management Testing
Tests for centralized session state key management and utilities.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import streamlit as st

# Import session state components
from utils.core.session_state import (
    SessionStateKeys, 
    SessionStateGroups,
    clear_processing_state,
    clear_results_state,
    clear_export_state,
    clear_ui_state,
    clear_report_state,
    get_state_debug_info,
    validate_state_keys
)


class TestSessionStateKeys(unittest.TestCase):
    """Test session state key constants and validation."""
    
    def test_session_state_keys_exist(self):
        """Test that all required session state keys are defined."""
        # Core data keys
        self.assertTrue(hasattr(SessionStateKeys, 'XML_CONTENT'))
        self.assertTrue(hasattr(SessionStateKeys, 'XML_FILENAME'))
        self.assertTrue(hasattr(SessionStateKeys, 'UPLOADED_FILENAME'))
        
        # Results data keys
        self.assertTrue(hasattr(SessionStateKeys, 'RESULTS'))
        self.assertTrue(hasattr(SessionStateKeys, 'SEARCH_RESULTS'))
        self.assertTrue(hasattr(SessionStateKeys, 'REPORT_RESULTS'))
        
        # Lookup data keys
        self.assertTrue(hasattr(SessionStateKeys, 'LOOKUP_DF'))
        self.assertTrue(hasattr(SessionStateKeys, 'EMIS_GUID_COL'))
        self.assertTrue(hasattr(SessionStateKeys, 'SNOMED_CODE_COL'))
        
        # UI preference keys
        self.assertTrue(hasattr(SessionStateKeys, 'CURRENT_DEDUPLICATION_MODE'))
        self.assertTrue(hasattr(SessionStateKeys, 'DEBUG_MODE'))
        self.assertTrue(hasattr(SessionStateKeys, 'CHILD_VIEW_MODE'))
    
    def test_session_state_key_values(self):
        """Test that session state keys have expected string values."""
        # Test core keys
        self.assertEqual(SessionStateKeys.XML_CONTENT, 'xml_content')
        self.assertEqual(SessionStateKeys.XML_FILENAME, 'xml_filename')
        self.assertEqual(SessionStateKeys.LOOKUP_DF, 'lookup_df')
        self.assertEqual(SessionStateKeys.CURRENT_DEDUPLICATION_MODE, 'current_deduplication_mode')
        self.assertEqual(SessionStateKeys.DEBUG_MODE, 'debug_mode')
    
    def test_session_state_groups_defined(self):
        """Test that session state groups are properly defined."""
        # Test group existence
        self.assertTrue(hasattr(SessionStateGroups, 'CORE_DATA'))
        self.assertTrue(hasattr(SessionStateGroups, 'PROCESSING_STATE'))
        self.assertTrue(hasattr(SessionStateGroups, 'RESULTS_DATA'))
        self.assertTrue(hasattr(SessionStateGroups, 'LOOKUP_DATA'))
        self.assertTrue(hasattr(SessionStateGroups, 'USER_PREFERENCES'))
        
        # Test groups contain proper keys
        self.assertIn(SessionStateKeys.XML_CONTENT, SessionStateGroups.CORE_DATA)
        self.assertIn(SessionStateKeys.RESULTS, SessionStateGroups.RESULTS_DATA)
        self.assertIn(SessionStateKeys.LOOKUP_DF, SessionStateGroups.LOOKUP_DATA)
        self.assertIn(SessionStateKeys.DEBUG_MODE, SessionStateGroups.USER_PREFERENCES)
    
    def test_no_duplicate_keys_across_groups(self):
        """Test that session state keys are not duplicated across groups."""
        all_keys = []
        for group_name in ['CORE_DATA', 'PROCESSING_STATE', 'RESULTS_DATA', 
                          'LOOKUP_DATA', 'USER_PREFERENCES', 'NHS_TERMINOLOGY', 
                          'SYSTEM_MONITORING']:
            if hasattr(SessionStateGroups, group_name):
                group_keys = getattr(SessionStateGroups, group_name)
                all_keys.extend(group_keys)
        
        # No duplicates
        self.assertEqual(len(all_keys), len(set(all_keys)))


class TestSessionStateClearingUtilities(unittest.TestCase):
    """Test session state clearing utilities."""
    
    def setUp(self):
        """Set up test fixtures with mock session state."""
        self.mock_session_state = {}
        
        # Populate mock session state with test data
        self.mock_session_state[SessionStateKeys.XML_CONTENT] = "test_xml"
        self.mock_session_state[SessionStateKeys.RESULTS] = {"test": "data"}
        self.mock_session_state[SessionStateKeys.LOOKUP_DF] = "test_df"
        self.mock_session_state[SessionStateKeys.DEBUG_MODE] = True
        self.mock_session_state['excel_export_test'] = "test_export"
        self.mock_session_state['json_export_test'] = "test_json"
        self.mock_session_state['cache_test'] = "test_cache"
    
    @patch('streamlit.session_state')
    def test_clear_processing_state(self, mock_st_session):
        """Test clearing processing-related session state."""
        mock_st_session.__contains__ = lambda key: key in self.mock_session_state
        mock_st_session.__delitem__ = lambda key: self.mock_session_state.pop(key)
        
        # Add processing state keys
        self.mock_session_state[SessionStateKeys.IS_PROCESSING] = True
        self.mock_session_state['progress_placeholder'] = "test"
        
        clear_processing_state()
        
        # Processing keys should be removed
        self.assertNotIn(SessionStateKeys.IS_PROCESSING, self.mock_session_state)
        self.assertNotIn('progress_placeholder', self.mock_session_state)
        
        # Other keys should remain
        self.assertIn(SessionStateKeys.XML_CONTENT, self.mock_session_state)
        self.assertIn(SessionStateKeys.DEBUG_MODE, self.mock_session_state)
    
    @patch('streamlit.session_state')
    def test_clear_results_state(self, mock_st_session):
        """Test clearing results and analysis data."""
        mock_st_session.__contains__ = lambda key: key in self.mock_session_state
        mock_st_session.__delitem__ = lambda key: self.mock_session_state.pop(key)
        
        clear_results_state()
        
        # Results keys should be removed
        self.assertNotIn(SessionStateKeys.RESULTS, self.mock_session_state)
        
        # Core data should remain
        self.assertIn(SessionStateKeys.XML_CONTENT, self.mock_session_state)
        self.assertIn(SessionStateKeys.DEBUG_MODE, self.mock_session_state)
    
    @patch('streamlit.session_state')
    @patch('utils.utils.caching.cache_manager.CacheManager.clear_all_export_cache')
    def test_clear_export_state(self, mock_clear_cache, mock_st_session):
        """Test clearing export-related cache keys."""
        # Mock session state iteration
        mock_st_session.keys.return_value = list(self.mock_session_state.keys())
        mock_st_session.__contains__ = lambda key: key in self.mock_session_state
        mock_st_session.__delitem__ = lambda key: self.mock_session_state.pop(key)
        
        clear_export_state()
        
        # Export cache should be cleared
        mock_clear_cache.assert_called_once()
    
    @patch('streamlit.session_state')
    def test_clear_ui_state(self, mock_st_session):
        """Test clearing UI state without affecting user preferences."""
        mock_st_session.keys.return_value = list(self.mock_session_state.keys())
        mock_st_session.__contains__ = lambda key: key in self.mock_session_state
        mock_st_session.__delitem__ = lambda key: self.mock_session_state.pop(key)
        
        # Add UI state keys
        self.mock_session_state['cached_selected_report_test'] = "test"
        self.mock_session_state['selected_test_text'] = "test"
        
        clear_ui_state()
        
        # UI state keys should be removed
        self.assertNotIn('cached_selected_report_test', self.mock_session_state)
        self.assertNotIn('selected_test_text', self.mock_session_state)
        
        # User preferences should remain
        self.assertIn(SessionStateKeys.DEBUG_MODE, self.mock_session_state)


class TestSessionStateValidation(unittest.TestCase):
    """Test session state validation utilities."""
    
    @patch('streamlit.session_state')
    def test_validate_state_keys_valid_state(self, mock_st_session):
        """Test validation with valid session state."""
        # Mock valid session state
        mock_st_session.keys.return_value = [
            SessionStateKeys.XML_CONTENT,
            SessionStateKeys.LOOKUP_DF,
            SessionStateKeys.DEBUG_MODE
        ]
        mock_st_session.__contains__ = lambda key: key in mock_st_session.keys()
        
        # Validation should pass
        is_valid, issues = validate_state_keys()
        self.assertTrue(is_valid)
        self.assertEqual(len(issues), 0)
    
    @patch('streamlit.session_state')
    def test_get_state_debug_info(self, mock_st_session):
        """Test getting debug information about session state."""
        # Mock session state
        test_keys = [
            SessionStateKeys.XML_CONTENT,
            SessionStateKeys.LOOKUP_DF,
            SessionStateKeys.DEBUG_MODE,
            'unknown_key'
        ]
        mock_st_session.keys.return_value = test_keys
        mock_st_session.__getitem__ = lambda key: f"value_for_{key}"
        
        debug_info = get_state_debug_info()
        
        # Should return comprehensive debug information
        self.assertIn('total_keys', debug_info)
        self.assertIn('core_data', debug_info)
        self.assertIn('lookup_data', debug_info)
        self.assertIn('user_preferences', debug_info)
        self.assertIn('unknown_keys', debug_info)
        
        # Should categorize keys correctly
        self.assertIn(SessionStateKeys.XML_CONTENT, debug_info['core_data'])
        self.assertIn(SessionStateKeys.LOOKUP_DF, debug_info['lookup_data'])
        self.assertIn(SessionStateKeys.DEBUG_MODE, debug_info['user_preferences'])
        self.assertIn('unknown_key', debug_info['unknown_keys'])


class TestSessionStateIntegration(unittest.TestCase):
    """Test session state integration scenarios."""
    
    @patch('streamlit.session_state')
    def test_new_xml_upload_workflow(self, mock_st_session):
        """Test session state management during new XML upload."""
        # Simulate existing session state
        existing_state = {
            SessionStateKeys.XML_CONTENT: "old_xml",
            SessionStateKeys.RESULTS: {"old": "results"},
            SessionStateKeys.DEBUG_MODE: True,
            SessionStateKeys.LOOKUP_DF: "existing_lookup"
        }
        
        mock_st_session.__contains__ = lambda key: key in existing_state
        mock_st_session.__delitem__ = lambda key: existing_state.pop(key)
        mock_st_session.keys.return_value = list(existing_state.keys())
        
        # Clear results for new upload
        clear_results_state()
        clear_export_state()
        
        # Results should be cleared but core preferences preserved
        self.assertNotIn(SessionStateKeys.RESULTS, existing_state)
        self.assertIn(SessionStateKeys.DEBUG_MODE, existing_state)  # User preference preserved
        self.assertIn(SessionStateKeys.LOOKUP_DF, existing_state)   # Lookup preserved
    
    @patch('streamlit.session_state')
    def test_tab_switching_state_management(self, mock_st_session):
        """Test session state during tab switching scenarios."""
        # Mock session state for tab switching
        tab_state = {
            SessionStateKeys.XML_CONTENT: "test_xml",
            SessionStateKeys.RESULTS: {"clinical": []},
            'cached_selected_report_clinical': "test_report",
            'rendering_clinical': True
        }
        
        mock_st_session.__contains__ = lambda key: key in tab_state
        mock_st_session.__delitem__ = lambda key: tab_state.pop(key)
        mock_st_session.keys.return_value = list(tab_state.keys())
        
        # Clear UI state for new tab
        clear_ui_state()
        
        # UI cache should be cleared but core data preserved
        self.assertNotIn('cached_selected_report_clinical', tab_state)
        self.assertNotIn('rendering_clinical', tab_state)
        self.assertIn(SessionStateKeys.XML_CONTENT, tab_state)
        self.assertIn(SessionStateKeys.RESULTS, tab_state)


if __name__ == '__main__':
    # Run session state tests with verbose output
    unittest.main(verbosity=2)