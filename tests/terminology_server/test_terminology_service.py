import unittest
from datetime import datetime
from unittest.mock import Mock, patch

import streamlit as st

# Compatibility shim for environments where Streamlit cache decorators
# do not yet support the "scope" keyword.
if hasattr(st, "cache_data"):
    _orig_cache_data = st.cache_data

    def _cache_data_compat(*args, **kwargs):
        kwargs.pop("scope", None)
        return _orig_cache_data(*args, **kwargs)

    st.cache_data = _cache_data_compat
if hasattr(st, "cache_resource"):
    _orig_cache_resource = st.cache_resource

    def _cache_resource_compat(*args, **kwargs):
        kwargs.pop("scope", None)
        return _orig_cache_resource(*args, **kwargs)

    st.cache_resource = _cache_resource_compat

from utils.terminology_server.client import ExpandedConcept, ExpansionResult
from utils.terminology_server.service import (
    CachedExpansion,
    ExpansionCache,
    ExpansionConfig,
    ExpansionService,
    get_expansion_service,
)
import utils.terminology_server.service as terminology_service_module


class TestExpansionCache(unittest.TestCase):
    def setUp(self):
        self.streamlit_patcher = patch("utils.terminology_server.service.st", None)
        self.streamlit_patcher.start()

    def tearDown(self):
        self.streamlit_patcher.stop()

    def test_cache_put_get_roundtrip(self):
        cache = ExpansionCache(ttl_minutes=30)
        result = ExpansionResult(
            source_code="73211009",
            source_display="Diabetes mellitus",
            children=[ExpandedConcept(code="111", display="Child One")],
            total_count=1,
            expansion_timestamp=datetime.now(),
            error=None,
        )
        cache.put("73211009", include_inactive=False, result=result)
        cached = cache.get("73211009", include_inactive=False)

        self.assertIsNotNone(cached)
        self.assertEqual(cached.source_code, "73211009")
        self.assertEqual(cached.total_count, 1)
        self.assertEqual(cached.children[0].code, "111")

    def test_cache_evicts_invalid_entries(self):
        cache = ExpansionCache(ttl_minutes=30)
        key = "73211009_False"
        cache._cache[key] = CachedExpansion(
            source_code="73211009",
            source_display="Unknown",
            children=[],
            total_count=5,
            cached_at=datetime.now().isoformat(),
            error=None,
        )

        cached = cache.get("73211009", include_inactive=False)
        self.assertIsNone(cached)
        self.assertNotIn(key, cache._cache)


class TestExpansionService(unittest.TestCase):
    def setUp(self):
        self.streamlit_patcher = patch("utils.terminology_server.service.st", None)
        self.streamlit_patcher.start()
        terminology_service_module._expansion_service = None

    def tearDown(self):
        terminology_service_module._expansion_service = None
        self.streamlit_patcher.stop()

    def test_expand_codes_batch_requires_configured_client(self):
        service = ExpansionService()
        service.client = None
        with self.assertRaises(ValueError):
            service.expand_codes_batch(["73211009"], ExpansionConfig())

    def test_expand_codes_batch_uses_cache_then_api(self):
        service = ExpansionService()
        mock_client = Mock()
        mock_client.expand_concept.return_value = ExpansionResult(
            source_code="222",
            source_display="Code 222",
            children=[],
            total_count=0,
            expansion_timestamp=datetime.now(),
            error=None,
        )
        service.client = mock_client

        cached_result = ExpansionResult(
            source_code="111",
            source_display="Code 111",
            children=[ExpandedConcept(code="1111", display="Child")],
            total_count=1,
            expansion_timestamp=datetime.now(),
            error=None,
        )
        service.expansion_cache.put("111", include_inactive=False, result=cached_result)

        progress_calls = []
        results = service.expand_codes_batch(
            ["111", "222"],
            ExpansionConfig(include_inactive=False, use_cache=True, max_workers=1),
            progress_callback=lambda done, total: progress_calls.append((done, total)),
        )

        self.assertEqual(set(results.keys()), {"111", "222"})
        self.assertEqual(results["111"].source_display, "Code 111")
        self.assertEqual(results["222"].source_display, "Code 222")
        mock_client.expand_concept.assert_called_once_with("222", False)
        self.assertEqual(progress_calls[-1], (2, 2))

    def test_get_expansion_service_singleton_without_streamlit(self):
        first = get_expansion_service()
        second = get_expansion_service()
        self.assertIs(first, second)


if __name__ == "__main__":
    unittest.main()
