import unittest
import xml.etree.ElementTree as ET

from utils.parsing.node_parsers.search_parser import parse_search
from utils.caching.code_store import CodeStore


class TestSearchParser(unittest.TestCase):
    def test_search_parser_captures_groups_and_dependencies(self):
        xml = """
        <emis:search xmlns:emis="http://www.e-mis.com/emisopen">
          <emis:id>SEARCH-1</emis:id>
          <emis:name>Test Search</emis:name>
          <emis:folder>F1</emis:folder>
          <emis:parent>
            <emis:SearchIdentifier reportGuid="PARENT-SEARCH"/>
          </emis:parent>
          <emis:criteriaGroup>
            <emis:id>G1</emis:id>
            <emis:actionIfTrue>SELECT</emis:actionIfTrue>
            <emis:actionIfFalse>REJECT</emis:actionIfFalse>
            <emis:definition>
              <emis:memberOperator>OR</emis:memberOperator>
              <emis:criteria>
                <emis:criterion>
                  <emis:table>EVENTS</emis:table>
                  <emis:valueSet>
                    <emis:values>
                      <emis:value>111</emis:value>
                      <emis:displayName>Code One</emis:displayName>
                    </emis:values>
                  </emis:valueSet>
                </emis:criterion>
              </emis:criteria>
              <emis:populationCriterion id="POP1" reportGuid="SEARCH-REF" />
            </emis:definition>
          </emis:criteriaGroup>
        </emis:search>
        """
        ns = {"emis": "http://www.e-mis.com/emisopen"}
        elem = ET.fromstring(xml)
        code_store = CodeStore()
        parsed = parse_search(elem, ns, code_store=code_store)

        flags = parsed["flags"]
        self.assertEqual(flags["element_id"], "SEARCH-1")
        self.assertEqual(flags["folder_id"], "F1")
        self.assertEqual(flags["parent_search_guid"], "PARENT-SEARCH")

        groups = parsed["criteria_groups"]
        self.assertEqual(len(groups), 1)
        gf = groups[0]["group_flags"]
        self.assertEqual(gf["criteria_group_id"], "G1")
        self.assertEqual(gf["member_operator"], "OR")
        self.assertEqual(gf["action_if_true"], "SELECT")
        self.assertEqual(gf["action_if_false"], "REJECT")

        pop = groups[0]["population_criteria"]
        self.assertTrue(pop and pop[0]["report_guid"] == "SEARCH-REF")

        criteria = groups[0]["criteria"]
        self.assertEqual(len(criteria), 1)
        self.assertEqual(criteria[0]["flags"]["logical_table_name"], "EVENTS")
        keys = criteria[0]["value_set_keys"]
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0][0], "111")
        stored = code_store.get_code(keys[0])
        self.assertTrue(stored and stored.get("code_value") == "111")

        deps = parsed["dependencies"]
        self.assertIn("PARENT-SEARCH", deps)
        self.assertIn("SEARCH-REF", deps)


if __name__ == "__main__":
    unittest.main()
