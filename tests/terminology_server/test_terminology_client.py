import unittest
from unittest.mock import patch

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

from utils.terminology_server.client import (
    ErrorCategory,
    NHSTerminologyClient,
    TerminologyServerConfig,
    _parse_fhir_error,
    _validate_snomed_code,
)


class TestTerminologyClientHelpers(unittest.TestCase):
    def test_validate_snomed_code(self):
        self.assertIsNone(_validate_snomed_code("73211009"))
        self.assertIn("only numbers", _validate_snomed_code("ABC123"))
        self.assertIn("too short", _validate_snomed_code("123"))
        self.assertIn("too long", _validate_snomed_code("1" * 19))

    def test_parse_fhir_error_no_matches(self):
        outcome = (
            '{"resourceType":"OperationOutcome","issue":[{"diagnostics":"No match",'
            '"details":{"text":"ValueSet contains 0 codes"}}]}'
        )
        category, detail = _parse_fhir_error(outcome)
        self.assertEqual(category, ErrorCategory.NO_MATCHES)
        self.assertIn("No match", detail)


class TestNHSTerminologyClient(unittest.TestCase):
    def setUp(self):
        config = TerminologyServerConfig(client_id="client", client_secret="secret")
        self.client = NHSTerminologyClient(config)

    def test_lookup_concept_returns_display(self):
        with patch.object(
            self.client,
            "_make_request",
            return_value=({"parameter": [{"name": "display", "valueString": "Diabetes mellitus"}]}, None),
        ):
            display, error = self.client.lookup_concept("73211009")

        self.assertEqual(display, "Diabetes mellitus")
        self.assertIsNone(error)

    def test_lookup_concept_not_found_error_passthrough(self):
        with patch.object(self.client, "_make_request", return_value=(None, "not found")):
            display, error = self.client.lookup_concept("999999999")

        self.assertIsNone(display)
        self.assertIn("not found", error.lower())

    def test_get_direct_children_treats_leaf_as_no_error(self):
        with patch.object(self.client, "_make_request", return_value=(None, "No match for expression")):
            children, error = self.client.get_direct_children("73211009")

        self.assertEqual(children, [])
        self.assertIsNone(error)

    def test_expand_concept_invalid_code_returns_error(self):
        with patch.object(self.client, "_make_request") as mock_request:
            result = self.client.expand_concept("NOT-A-CODE")

        self.assertIsNotNone(result.error)
        self.assertIn("Invalid SNOMED code format", result.error)
        mock_request.assert_not_called()

    def test_expand_concept_with_source_display_skips_lookup(self):
        response = {
            "expansion": {
                "total": 1,
                "contains": [{"code": "111111111", "display": "Child concept"}],
            }
        }
        with patch.object(self.client, "lookup_concept") as mock_lookup, patch.object(
            self.client, "_make_request", return_value=(response, None)
        ):
            result = self.client.expand_concept("73211009", source_display="Diabetes mellitus")

        self.assertIsNone(result.error)
        self.assertEqual(result.source_display, "Diabetes mellitus")
        self.assertEqual(len(result.children), 1)
        mock_lookup.assert_not_called()


if __name__ == "__main__":
    unittest.main()
