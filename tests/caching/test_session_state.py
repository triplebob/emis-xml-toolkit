"""
Session State Management Testing
Tests for centralised session state key management and cache utilities.
"""

import unittest
from unittest.mock import patch
import streamlit as st

from utils.system.session_state import (
    SessionStateKeys,
    SessionStateGroups,
    clear_all_except_core,
    get_cached_snomed_mappings,
    update_snomed_cache,
    clear_expired_snomed_cache,
)


class TestSessionStateKeys(unittest.TestCase):
    """Test session state key constants and validation."""

    def test_session_state_keys_exist(self):
        self.assertTrue(hasattr(SessionStateKeys, "XML_CONTENT"))
        self.assertTrue(hasattr(SessionStateKeys, "XML_FILENAME"))
        self.assertTrue(hasattr(SessionStateKeys, "UPLOADED_FILENAME"))
        self.assertTrue(hasattr(SessionStateKeys, "LOOKUP_ENCRYPTED_BYTES"))
        self.assertTrue(hasattr(SessionStateKeys, "EMIS_GUID_COL"))
        self.assertTrue(hasattr(SessionStateKeys, "SNOMED_CODE_COL"))
        self.assertTrue(hasattr(SessionStateKeys, "CURRENT_DEDUPLICATION_MODE"))
        self.assertTrue(hasattr(SessionStateKeys, "DEBUG_MODE"))

    def test_session_state_key_values(self):
        self.assertEqual(SessionStateKeys.XML_CONTENT, "xml_content")
        self.assertEqual(SessionStateKeys.XML_FILENAME, "xml_filename")
        self.assertEqual(SessionStateKeys.LOOKUP_ENCRYPTED_BYTES, "lookup_encrypted_bytes")
        self.assertEqual(SessionStateKeys.CURRENT_DEDUPLICATION_MODE, "current_deduplication_mode")
        self.assertEqual(SessionStateKeys.DEBUG_MODE, "debug_mode")


class TestSessionStateGroups(unittest.TestCase):
    """Test session state groups."""

    def test_session_state_groups_defined(self):
        self.assertTrue(hasattr(SessionStateGroups, "CORE_DATA"))
        self.assertTrue(hasattr(SessionStateGroups, "LOOKUP_DATA"))
        self.assertTrue(hasattr(SessionStateGroups, "USER_PREFERENCES"))

        self.assertIn(SessionStateKeys.UPLOADED_FILE, SessionStateGroups.CORE_DATA)
        self.assertIn(SessionStateKeys.LOOKUP_ENCRYPTED_BYTES, SessionStateGroups.LOOKUP_DATA)
        self.assertIn(SessionStateKeys.DEBUG_MODE, SessionStateGroups.USER_PREFERENCES)


class TestSessionStateCleanup(unittest.TestCase):
    """Test session state cleanup utilities."""

    @patch("streamlit.session_state", new_callable=dict)
    def test_clear_all_except_core(self, mock_state):
        mock_state[SessionStateKeys.XML_FILENAME] = "test.xml"
        mock_state[SessionStateKeys.LOOKUP_ENCRYPTED_BYTES] = b"encrypted_data"
        mock_state[SessionStateKeys.DEBUG_MODE] = True
        mock_state["temporary_key"] = "temp"

        clear_all_except_core()

        self.assertIn(SessionStateKeys.XML_FILENAME, mock_state)
        self.assertIn(SessionStateKeys.LOOKUP_ENCRYPTED_BYTES, mock_state)
        self.assertIn(SessionStateKeys.DEBUG_MODE, mock_state)
        self.assertNotIn("temporary_key", mock_state)


class TestSnomedCache(unittest.TestCase):
    """Test SNOMED cache helpers."""

    @patch("streamlit.session_state", new_callable=dict)
    def test_snomed_cache_roundtrip(self, mock_state):
        update_snomed_cache({"emis_guid_1": "123"})
        cached = get_cached_snomed_mappings()
        self.assertEqual(cached.get("emis_guid_1"), "123")

    @patch("streamlit.session_state", new_callable=dict)
    def test_clear_expired_cache(self, mock_state):
        mock_state[SessionStateKeys.MATCHED_EMIS_SNOMED_CACHE] = {"emis_guid_2": "456"}
        mock_state[SessionStateKeys.MATCHED_EMIS_SNOMED_TIMESTAMP] = "2000-01-01T00:00:00"

        cleared = clear_expired_snomed_cache()
        self.assertTrue(cleared)
        self.assertNotIn(SessionStateKeys.MATCHED_EMIS_SNOMED_CACHE, mock_state)
        self.assertNotIn(SessionStateKeys.MATCHED_EMIS_SNOMED_TIMESTAMP, mock_state)


if __name__ == "__main__":
    unittest.main(verbosity=2)
