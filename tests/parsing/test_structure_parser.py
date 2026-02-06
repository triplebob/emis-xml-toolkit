import importlib.util
import unittest
from pathlib import Path

from utils.parsing.node_parsers.structure_parser import parse_structure


def _load_structure_enricher():
    """Load StructureEnricher without importing utils metadata __init__ (avoids UI deps during tests)."""
    module_path = Path(__file__).resolve().parents[1] / "utils" / "metadata" / "structure_enricher.py"
    spec = importlib.util.spec_from_file_location("structure_enricher_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.StructureEnricher


class TestStructureParser(unittest.TestCase):
    def test_structure_parser_handles_folder_and_reports(self):
        xml = """
        <emis:enquiryDocument xmlns:emis="http://www.e-mis.com/emisopen">
          <emis:reportFolder>
            <emis:id>F1</emis:id>
            <emis:name>Folder</emis:name>
          </emis:reportFolder>
          <emis:report>
            <emis:id>S1</emis:id>
            <emis:name>Search One</emis:name>
            <emis:folder>F1</emis:folder>
            <emis:population>
              <emis:criteriaGroup>
                <emis:definition>
                  <emis:populationCriterion reportGuid="S2" />
                </emis:definition>
              </emis:criteriaGroup>
            </emis:population>
          </emis:report>
          <emis:report>
            <emis:id>L1</emis:id>
            <emis:name>List One</emis:name>
            <emis:folder>F1</emis:folder>
            <emis:listReport/>
          </emis:report>
        </emis:enquiryDocument>
        """
        parsed = parse_structure(xml)
        folders = parsed["folders"]
        entities = parsed["entities"]

        self.assertEqual(len(folders), 1)
        self.assertEqual(folders[0]["id"], "F1")

        search = next(e for e in entities if e["source_type"] == "search")
        self.assertEqual(search["folder_id"], "F1")
        self.assertIn("S2", search["dependencies"])

        list_report = next(e for e in entities if e["source_type"] == "list_report")
        self.assertEqual(list_report["folder_id"], "F1")

    def test_structure_enricher_builds_nested_folder_tree(self):
        xml = """
        <emis:enquiryDocument xmlns:emis="http://www.e-mis.com/emisopen">
          <emis:reportFolder>
            <emis:id>F1</emis:id>
            <emis:name>Folder</emis:name>
          </emis:reportFolder>
          <emis:report>
            <emis:id>S1</emis:id>
            <emis:name>Search One</emis:name>
            <emis:folder>F1</emis:folder>
            <emis:population>
              <emis:criteriaGroup>
                <emis:definition>
                  <emis:populationCriterion reportGuid="S2" />
                </emis:definition>
              </emis:criteriaGroup>
            </emis:population>
          </emis:report>
          <emis:report>
            <emis:id>L1</emis:id>
            <emis:name>List One</emis:name>
            <emis:folder>F1</emis:folder>
            <emis:parent>
              <emis:SearchIdentifier reportGuid="S1" />
            </emis:parent>
            <emis:listReport/>
          </emis:report>
          <emis:report>
            <emis:id>A1</emis:id>
            <emis:name>Audit One</emis:name>
            <emis:folder>F1</emis:folder>
            <emis:auditReport>
              <emis:population>S1</emis:population>
            </emis:auditReport>
          </emis:report>
          <emis:report>
            <emis:id>G1</emis:id>
            <emis:name>Aggregate One</emis:name>
            <emis:folder>F1</emis:folder>
            <emis:aggregateReport />
          </emis:report>
        </emis:enquiryDocument>
        """
        data = parse_structure(xml)
        StructureEnricher = _load_structure_enricher()
        manager = StructureEnricher(data)
        tree = manager.folder_tree()
        root = tree["roots"][0]

        # Search nested in folder with its reports attached
        self.assertEqual(len(root["searches"]), 1)
        search_ref = root["searches"][0]
        nested_reports = {r["id"] for r in search_ref.get("reports", [])}
        self.assertEqual(nested_reports, {"L1", "A1"})

        # Aggregate stays at folder level
        folder_reports = {r["id"] for r in root.get("reports", [])}
        self.assertIn("G1", folder_reports)

        deps = manager.dependency_graph()
        self.assertEqual(deps.get("S1"), ["S2"])
        self.assertIn("S1", deps.get("A1", []))


if __name__ == "__main__":
    unittest.main()
