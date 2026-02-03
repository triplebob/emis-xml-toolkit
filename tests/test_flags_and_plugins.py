"""
Flags and plugin integration tests for v3 metadata contracts.
"""

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from utils.metadata.flag_registry import validate_flags
from utils.metadata.flag_mapper import map_element_flags
from utils.pattern_plugins.base import PatternContext, PatternResult
from utils.pattern_plugins.registry import PatternRegistry
from utils.parsing.pipeline import parse_xml


class TestFlagValidation(unittest.TestCase):
    def test_validate_flags_removes_unknown_and_invalid_values(self):
        raw = {
            "element_type": "search",
            "element_id": "ABC123",
            "include_children": "true",  # invalid: expects bool
            "unknown_flag": 123,
        }

        cleaned = validate_flags(raw)
        self.assertIn("element_type", cleaned)
        self.assertIn("element_id", cleaned)
        self.assertNotIn("include_children", cleaned)
        self.assertNotIn("unknown_flag", cleaned)

    def test_map_element_flags_applies_registry_validation(self):
        elem = ET.fromstring(
            '<emis:criterion xmlns:emis="http://www.e-mis.com/emisopen"><emis:id>C1</emis:id></emis:criterion>'
        )
        namespaces = {"emis": "http://www.e-mis.com/emisopen"}
        pattern_results = [
            PatternResult(
                id="test_plugin",
                description="test",
                flags={
                    "include_children": True,  # valid
                    "unknown_flag": "drop_me",  # invalid key
                },
                confidence="high",
            )
        ]

        flags = map_element_flags(elem, namespaces, pattern_results)
        self.assertEqual(flags.get("element_id"), "C1")
        self.assertTrue(flags.get("include_children"))
        self.assertNotIn("unknown_flag", flags)


class TestPluginRegistry(unittest.TestCase):
    def test_registry_rejects_duplicate_pattern_ids(self):
        registry = PatternRegistry()

        def detector(_ctx):
            return None

        registry.register("dup", detector)
        with self.assertRaises(ValueError):
            registry.register("dup", detector)

    def test_registry_runs_registered_detector(self):
        registry = PatternRegistry()

        def detector(ctx):
            return PatternResult(
                id="",
                description="registry run",
                flags={"xml_tag_name": ctx.element.tag.split("}")[-1]},
                confidence="high",
            )

        registry.register("registry_detector", detector)
        elem = ET.fromstring('<emis:criterion xmlns:emis="http://www.e-mis.com/emisopen" />')
        results = registry.run_all(PatternContext(element=elem, namespaces={"emis": "http://www.e-mis.com/emisopen"}))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "registry_detector")
        self.assertEqual(results[0].flags.get("xml_tag_name"), "criterion")


class TestPipelineSmoke(unittest.TestCase):
    def test_parse_xml_smoke_on_real_fixture(self):
        xml_dir = Path("xml_examples")
        xml_files = sorted(xml_dir.glob("*.xml"))
        self.assertTrue(xml_files, "Expected at least one XML fixture in xml_examples/")

        xml_text = xml_files[0].read_text(encoding="utf-8")
        parsed = parse_xml(xml_text, source_name=xml_files[0].name, run_patterns=False)

        self.assertIn("parsed_document", parsed)
        self.assertIn("entities", parsed)
        self.assertIn("code_store", parsed)


if __name__ == "__main__":
    unittest.main()
