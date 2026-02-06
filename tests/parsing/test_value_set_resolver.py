import unittest
from unittest.mock import patch

from utils.caching.code_store import CodeStore
from utils.metadata.value_set_resolver import _get_code_store
from utils.system.session_state import SessionStateKeys


class TestValueSetResolverCodeStoreInvalidation(unittest.TestCase):
    @patch("streamlit.session_state", new_callable=dict)
    def test_get_code_store_returns_store_when_hash_matches(self, mock_state):
        store = CodeStore()
        mock_state[SessionStateKeys.CODE_STORE] = store
        mock_state[SessionStateKeys.CODE_STORE_SOURCE_HASH] = "abc123"
        mock_state["last_processed_hash"] = "abc123"

        resolved = _get_code_store()
        self.assertIs(resolved, store)
        self.assertIn(SessionStateKeys.CODE_STORE, mock_state)

    @patch("streamlit.session_state", new_callable=dict)
    def test_get_code_store_invalidates_on_hash_mismatch(self, mock_state):
        store = CodeStore()
        mock_state[SessionStateKeys.CODE_STORE] = store
        mock_state[SessionStateKeys.CODE_STORE_SOURCE_HASH] = "old-hash"
        mock_state["last_processed_hash"] = "new-hash"

        resolved = _get_code_store()
        self.assertIsNone(resolved)
        self.assertNotIn(SessionStateKeys.CODE_STORE, mock_state)
        self.assertNotIn(SessionStateKeys.CODE_STORE_SOURCE_HASH, mock_state)

    @patch("streamlit.session_state", new_callable=dict)
    def test_get_code_store_invalidates_when_source_hash_missing(self, mock_state):
        store = CodeStore()
        mock_state[SessionStateKeys.CODE_STORE] = store
        mock_state["last_processed_hash"] = "active-hash"

        resolved = _get_code_store()
        self.assertIsNone(resolved)
        self.assertNotIn(SessionStateKeys.CODE_STORE, mock_state)


if __name__ == "__main__":
    unittest.main()
