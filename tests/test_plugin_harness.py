"""
Standalone plugin harness tests.

These tests demonstrate that a detector can be authored outside the core
codebase and executed against XML input without modifying application modules.
"""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

from utils.parsing.document_loader import load_document
from utils.pattern_plugins.base import PatternContext, PatternResult
from utils.pattern_plugins.registry import PatternRegistry


def _write_temp_plugin(source_code: str) -> Path:
    fd, path = tempfile.mkstemp(suffix="_external_plugin.py")
    os.close(fd)
    plugin_path = Path(path)
    plugin_path.write_text(source_code, encoding="utf-8")
    return plugin_path


def _load_detector(plugin_path: Path, detector_name: str):
    spec = importlib.util.spec_from_file_location("external_plugin_test", plugin_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    detector = getattr(module, detector_name, None)
    if detector is None:
        raise AttributeError(f"Detector '{detector_name}' not found in {plugin_path}")
    return detector


def _first_element_by_localname(root, local_name: str):
    for elem in root.iter():
        tag_local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag_local == local_name:
            return elem
    return None


class TestStandalonePluginHarness(unittest.TestCase):
    def test_external_plugin_runs_against_inline_xml(self):
        xml = """
        <emis:search xmlns:emis="http://www.e-mis.com/emisopen">
          <emis:criterion>
            <emis:table>EVENTS</emis:table>
          </emis:criterion>
        </emis:search>
        """
        root, namespaces, _ = load_document(xml, source_name="inline_plugin_test")
        criterion = _first_element_by_localname(root, "criterion")
        self.assertIsNotNone(criterion)

        plugin_code = """
from utils.pattern_plugins.base import PatternResult

def detect_external_smoke(ctx):
    elem = ctx.element
    local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
    if local != "criterion":
        return None
    return PatternResult(
        id="external_smoke",
        description="External plugin smoke match",
        flags={"display_name": "External plugin matched"},
        confidence="high",
    )
"""
        plugin_path = _write_temp_plugin(plugin_code)
        try:
            detector = _load_detector(plugin_path, "detect_external_smoke")

            result = detector(PatternContext(element=criterion, namespaces=namespaces, path=criterion.tag))
            self.assertIsInstance(result, PatternResult)
            self.assertEqual(result.id, "external_smoke")
            self.assertEqual(result.flags.get("display_name"), "External plugin matched")
        finally:
            plugin_path.unlink(missing_ok=True)

    def test_external_plugin_runs_against_xml_examples_fixture(self):
        xml_dir = Path("xml_examples")
        xml_files = sorted(xml_dir.glob("*.xml"))
        self.assertTrue(xml_files, "Expected at least one XML fixture in xml_examples/")

        xml_text = xml_files[0].read_text(encoding="utf-8")
        root, namespaces, _ = load_document(xml_text, source_name=xml_files[0].name)
        criterion = _first_element_by_localname(root, "criterion")
        self.assertIsNotNone(criterion, f"No criterion element found in fixture: {xml_files[0].name}")

        plugin_code = """
from utils.pattern_plugins.base import PatternResult

def detect_external_fixture(ctx):
    elem = ctx.element
    local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
    if local != "criterion":
        return None
    return PatternResult(
        id="external_fixture",
        description="Fixture criterion detected",
        flags={"xml_tag_name": local},
        confidence="high",
    )
"""
        plugin_path = _write_temp_plugin(plugin_code)
        try:
            detector = _load_detector(plugin_path, "detect_external_fixture")

            result = detector(PatternContext(element=criterion, namespaces=namespaces, path=criterion.tag))
            self.assertIsNotNone(result)
            self.assertEqual(result.id, "external_fixture")
            self.assertEqual(result.flags.get("xml_tag_name"), "criterion")
        finally:
            plugin_path.unlink(missing_ok=True)

    def test_registry_supports_standalone_detector_registration(self):
        registry = PatternRegistry()

        def detector(ctx):
            return PatternResult(
                id="standalone_registry_test",
                description="Registry smoke test",
                flags={"xml_tag_name": "criterion"},
                confidence="high",
            )

        registry.register("standalone_registry_test", detector)
        self.assertIn("standalone_registry_test", registry.registered_ids())

        xml = """
        <emis:search xmlns:emis="http://www.e-mis.com/emisopen">
          <emis:criterion />
        </emis:search>
        """
        root, namespaces, _ = load_document(xml, source_name="registry_smoke")
        criterion = _first_element_by_localname(root, "criterion")
        self.assertIsNotNone(criterion)

        results = registry.run_all(PatternContext(element=criterion, namespaces=namespaces, path=criterion.tag))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "standalone_registry_test")


if __name__ == "__main__":
    unittest.main()
