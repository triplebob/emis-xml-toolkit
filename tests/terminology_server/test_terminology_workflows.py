import unittest

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

from utils.terminology_server.expansion_workflow import (
    build_emis_xml_export,
    build_hierarchical_json,
    prepare_child_codes_view,
    prepare_expansion_selection,
)
from utils.terminology_server.lineage_workflow import (
    FullLineageTraceResult,
    LineageNode,
    LineageTraceResult,
)


class TestExpansionWorkflow(unittest.TestCase):
    def test_prepare_expansion_selection_deduplicates_and_filters_zero_descendants(self):
        clinical_data = [
            {
                "SNOMED Code": "73211009",
                "code_system": "SNOMED_CONCEPT",
                "include_children": True,
                "Descendants": "12",
                "Source Type": "Search",
                "Source Name": "S1",
            },
            {
                "SNOMED Code": "73211009",
                "code_system": "SNOMED_CONCEPT",
                "include_children": True,
                "Descendants": "12",
                "Source Type": "Report",
                "Source Name": "R1",
            },
            {
                "SNOMED Code": "44054006",
                "code_system": "SNOMED_CONCEPT",
                "include_children": True,
                "Descendants": "0",
                "Source Type": "Search",
                "Source Name": "S2",
            },
            {
                "SNOMED Code": "X1",
                "code_system": "EMISINTERNAL",
                "include_children": True,
                "Descendants": "4",
            },
        ]

        selection = prepare_expansion_selection(clinical_data)

        self.assertEqual(selection.stats["original_count"], 3)
        self.assertEqual(selection.stats["unique_count"], 2)
        self.assertEqual(selection.stats["dedupe_savings"], 1)
        self.assertEqual(selection.stats["zero_descendant_count"], 1)
        self.assertEqual(selection.stats["remaining_count"], 1)
        self.assertEqual(len(selection.expandable_codes), 1)
        self.assertEqual(selection.expandable_codes[0]["SNOMED Code"], "73211009")
        self.assertEqual(len(selection.code_sources["73211009"]), 2)

    def test_prepare_child_codes_view_unique_and_per_source_modes(self):
        rows = [
            {
                "Parent Code": "73211009",
                "Parent Display": "Diabetes mellitus",
                "Child Code": "111",
                "Child Display": "Child A",
                "Inactive": False,
                "Source Type": "Search",
                "Source Name": "Search One",
            },
            {
                "Parent Code": "73211009",
                "Parent Display": "Diabetes mellitus",
                "Child Code": "111",
                "Child Display": "Child A",
                "Inactive": False,
                "Source Type": "Report",
                "Source Name": "Report One",
            },
        ]

        unique_view = prepare_child_codes_view(rows, view_mode="unique")
        per_source_view = prepare_child_codes_view(rows, view_mode="per_source")

        self.assertEqual(unique_view["total_count"], 2)
        self.assertEqual(unique_view["filtered_count"], 1)
        self.assertEqual(len(unique_view["rows"]), 1)
        self.assertEqual(len(per_source_view["rows"]), 2)

    def test_build_hierarchical_json_deduplicates_child_codes(self):
        rows = [
            {"Parent Code": "73211009", "Parent Display": "Diabetes mellitus", "Child Code": "111", "Child Display": "Child", "EMIS GUID": "GUID1", "Inactive": False},
            {"Parent Code": "73211009", "Parent Display": "Diabetes mellitus", "Child Code": "111", "Child Display": "Child", "EMIS GUID": "GUID1", "Inactive": False},
        ]

        payload = build_hierarchical_json(rows)
        parent = payload["hierarchy"]["73211009"]

        self.assertEqual(payload["export_metadata"]["total_children"], 2)
        self.assertEqual(len(parent["children"]), 1)
        self.assertEqual(parent["children"][0]["code"], "111")

    def test_build_emis_xml_export_excludes_unmatched_rows(self):
        rows = [
            {"Child Display": "Matched Child", "EMIS GUID": "ABC123"},
            {"Child Display": "Missing Child", "EMIS GUID": "Not in EMIS lookup table"},
        ]

        xml_text = build_emis_xml_export(rows)

        self.assertIn("<value>ABC123</value>", xml_text)
        self.assertNotIn("Not in EMIS lookup table", xml_text)


class TestLineageJsonExport(unittest.TestCase):
    def test_lineage_result_json_export(self):
        child = LineageNode(
            code="111",
            display="Child",
            emis_guid="GUID1",
            inactive=False,
            depth=1,
            direct_parent_code="73211009",
            lineage_path="73211009 > 111",
        )
        root = LineageNode(
            code="73211009",
            display="Diabetes mellitus",
            emis_guid=None,
            inactive=False,
            depth=0,
            direct_parent_code=None,
            lineage_path="73211009",
            children=[child],
        )

        result = LineageTraceResult(
            root_code="73211009",
            root_display="Diabetes mellitus",
            tree=root,
            flat_nodes=[child],
            shared_lineage_codes=[],
            total_nodes=1,
            max_depth_reached=1,
            api_calls_made=3,
        )
        payload = result.to_hierarchical_json(source_filename="test.xml")

        self.assertEqual(payload["export_metadata"]["root_code"], "73211009")
        self.assertEqual(payload["export_metadata"]["source_file"], "test.xml")
        self.assertEqual(payload["hierarchy"]["code"], "73211009")

    def test_full_lineage_result_json_export(self):
        root = LineageNode(
            code="73211009",
            display="Diabetes mellitus",
            emis_guid=None,
            inactive=False,
            depth=0,
            direct_parent_code=None,
            lineage_path="73211009",
            children=[],
        )

        result = FullLineageTraceResult(
            trees=[root],
            total_nodes=10,
            max_depth_reached=4,
            total_api_calls=20,
            shared_lineage_codes=["111"],
            parent_count=1,
            errors=[],
            truncated_parent_codes=["73211009"],
            truncation_reasons={"73211009": "Depth cap reached"},
        )
        payload = result.to_hierarchical_json(source_filename="full.xml")

        self.assertEqual(payload["export_metadata"]["parent_count"], 1)
        self.assertEqual(payload["export_metadata"]["source_file"], "full.xml")
        self.assertEqual(payload["truncated_parent_codes"], ["73211009"])
        self.assertEqual(payload["trees"][0]["code"], "73211009")


if __name__ == "__main__":
    unittest.main()
