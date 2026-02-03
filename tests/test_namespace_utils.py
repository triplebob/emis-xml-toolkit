import unittest
import xml.etree.ElementTree as ET

from utils.parsing.namespace_utils import (
    _to_emis_path,
    findall_ns,
    find_ns,
    get_text_ns,
    unique_elements,
    get_child_text_any,
    get_attr_any,
    find_child_any,
)


NS = {"emis": "http://www.e-mis.com/emisopen"}


class TestNamespaceUtils(unittest.TestCase):
    def setUp(self):
        self.root = ET.fromstring(
            """
            <root xmlns:emis="http://www.e-mis.com/emisopen" xmlns:other="urn:other">
              <emis:criteria>
                <emis:name>Namespaced</emis:name>
              </emis:criteria>
              <criteria>
                <name>Bare</name>
              </criteria>
              <other:item other:flag="yes">OtherText</other:item>
            </root>
            """
        )

    def test_to_emis_path_transforms_common_xpath_forms(self):
        self.assertEqual(_to_emis_path("criteria"), "emis:criteria")
        self.assertEqual(_to_emis_path(".//criteria/name"), ".//emis:criteria/emis:name")
        self.assertEqual(_to_emis_path("./criteria"), "./emis:criteria")

    def test_find_ns_and_findall_ns_handle_bare_and_namespaced_tags(self):
        first = find_ns(self.root, "criteria", NS)
        self.assertIsNotNone(first)
        self.assertEqual(first.tag.split("}")[-1], "criteria")

        matches = findall_ns(self.root, "criteria", NS)
        self.assertEqual(len(matches), 2)
        self.assertEqual([m.tag.split("}")[-1] for m in matches], ["criteria", "criteria"])

    def test_get_text_ns_returns_trimmed_value(self):
        criteria = find_ns(self.root, "emis:criteria", NS)
        self.assertEqual(get_text_ns(criteria, "name", NS), "Namespaced")

    def test_unique_elements_deduplicates_by_identity(self):
        item = self.root.find(".//criteria")
        deduped = unique_elements([item, item, item])
        self.assertEqual(len(deduped), 1)

    def test_get_child_text_any_supports_localname_fallback(self):
        node = self.root.find(".//{urn:other}item")
        self.assertIsNotNone(node)
        self.assertEqual(get_child_text_any(self.root, ["item"]), "OtherText")
        self.assertEqual(get_child_text_any(node, ["missing"]), "")

    def test_get_attr_any_and_find_child_any_support_namespaced_data(self):
        node = self.root.find(".//{urn:other}item")
        self.assertIsNotNone(node)
        self.assertEqual(get_attr_any(node, ["flag"]), "yes")

        found = find_child_any(self.root, ["item"])
        self.assertIsNotNone(found)
        self.assertEqual(found.tag.split("}")[-1], "item")


if __name__ == "__main__":
    unittest.main()
