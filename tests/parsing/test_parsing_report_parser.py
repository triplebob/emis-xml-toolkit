"""Tests for the report parser covering list/audit/aggregate structures."""

import unittest
import xml.etree.ElementTree as ET

from utils.parsing.node_parsers.report_parser import parse_report
from utils.caching.code_store import CodeStore


class TestReportParser(unittest.TestCase):
    def setUp(self):
        self.ns = {"emis": "http://www.e-mis.com/emisopen"}

    def test_list_report_parses_column_groups_and_criteria(self):
        xml = """
        <emis:report xmlns:emis="http://www.e-mis.com/emisopen">
          <emis:name>List Example</emis:name>
          <emis:listReport>
            <emis:columnGroup id="cg1">
              <emis:logicalTableName>PATIENTS</emis:logicalTableName>
              <emis:displayName>Patients</emis:displayName>
              <emis:columnar>
                <emis:listColumn id="c1">
                  <emis:column>NHS_NUMBER</emis:column>
                  <emis:displayName>NHS</emis:displayName>
                </emis:listColumn>
              </emis:columnar>
              <emis:sort>
                <emis:columnId>c1</emis:columnId>
                <emis:direction>ASC</emis:direction>
              </emis:sort>
              <emis:criteria>
                <emis:criterion>
                  <emis:table>PATIENTS</emis:table>
                  <emis:displayName>Patients</emis:displayName>
                  <emis:filterAttribute>
                    <emis:columnValue>
                      <emis:column>GENDER</emis:column>
                      <emis:displayName>Gender</emis:displayName>
                      <emis:inNotIn>IN</emis:inNotIn>
                      <emis:valueSet>
                        <emis:values>
                          <emis:value>123</emis:value>
                          <emis:displayName>Male</emis:displayName>
                        </emis:values>
                      </emis:valueSet>
                    </emis:columnValue>
                  </emis:filterAttribute>
                </emis:criterion>
              </emis:criteria>
            </emis:columnGroup>
          </emis:listReport>
        </emis:report>
        """

        root = ET.fromstring(xml)
        code_store = CodeStore()
        result = parse_report(root, self.ns, "list_report", code_store=code_store)

        self.assertIn("column_groups", result)
        self.assertEqual(len(result["column_groups"]), 1)
        group = result["column_groups"][0]
        self.assertEqual(group.get("logical_table"), "PATIENTS")
        self.assertEqual(group.get("display_name"), "Patients")
        self.assertEqual(len(group.get("columns", [])), 1)
        self.assertEqual(group["columns"][0].get("column"), "NHS_NUMBER")
        self.assertEqual(group["columns"][0].get("display_name"), "NHS")

        # Sort config captured
        self.assertEqual(group.get("sort_configuration", {}).get("column_id"), "c1")
        self.assertEqual(group.get("sort_configuration", {}).get("direction"), "ASC")

        # Column-group criteria parsed with value set and column filter flags
        self.assertTrue(group.get("criteria"))
        criterion = group["criteria"][0]
        self.assertEqual(criterion["flags"].get("logical_table_name"), "PATIENTS")
        self.assertEqual(criterion["flags"].get("column_name"), ["GENDER"])
        keys = criterion["value_set_keys"]
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0][0], "123")
        stored = code_store.get_code(keys[0])
        self.assertEqual(stored.get("code_value"), "123")

    def test_aggregate_report_parses_groups_and_result(self):
        xml = """
        <emis:report xmlns:emis="http://www.e-mis.com/emisopen">
          <emis:aggregateReport>
            <emis:logicalTable>EVENTS</emis:logicalTable>
            <emis:group>
              <emis:id>g1</emis:id>
              <emis:displayName>Group 1</emis:displayName>
              <emis:groupingColumn>SEX</emis:groupingColumn>
            </emis:group>
            <emis:rows>
              <emis:groupId>g1</emis:groupId>
            </emis:rows>
            <emis:result>
              <emis:source>g1</emis:source>
              <emis:calculationType>COUNT</emis:calculationType>
            </emis:result>
            <emis:criteria>
              <emis:criterion>
                <emis:table>EVENTS</emis:table>
                <emis:filterAttribute>
                  <emis:columnValue>
                    <emis:column>CODE</emis:column>
                    <emis:valueSet>
                      <emis:values>
                        <emis:value>ABC</emis:value>
                        <emis:displayName>Test Code</emis:displayName>
                      </emis:values>
                    </emis:valueSet>
                  </emis:columnValue>
                </emis:filterAttribute>
              </emis:criterion>
            </emis:criteria>
          </emis:aggregateReport>
        </emis:report>
        """
        root = ET.fromstring(xml)
        code_store = CodeStore()
        result = parse_report(root, self.ns, "aggregate_report", code_store=code_store)

        self.assertIn("aggregate", result)
        aggregate = result["aggregate"]
        self.assertEqual(aggregate.get("logical_table"), "EVENTS")
        self.assertEqual(len(aggregate.get("groups", [])), 1)
        self.assertEqual(aggregate["groups"][0].get("display_name"), "Group 1")

        # Statistical groups capture rows mapping
        self.assertEqual(len(aggregate.get("statistical_groups", [])), 1)
        self.assertEqual(aggregate["statistical_groups"][0].get("type"), "rows")
        self.assertEqual(aggregate["statistical_groups"][0].get("group_id"), "g1")

        # Result block captured
        self.assertEqual(aggregate.get("result", {}).get("source"), "g1")
        self.assertEqual(aggregate.get("result", {}).get("calculation_type"), "COUNT")

        # Aggregate criteria parsed with codes
        self.assertTrue(result["aggregate_criteria"])
        criterion = result["aggregate_criteria"][0]
        self.assertEqual(criterion["flags"].get("logical_table_name"), "EVENTS")
        keys = criterion["value_set_keys"]
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0][0], "ABC")
        stored = code_store.get_code(keys[0])
        self.assertEqual(stored.get("code_value"), "ABC")

    def test_audit_report_parses_population_and_custom_aggregate(self):
        xml = """
        <emis:report xmlns:emis="http://www.e-mis.com/emisopen">
          <emis:auditReport>
            <emis:population>POP-1</emis:population>
            <emis:customAggregate>
              <emis:logicalTable>PATIENTS</emis:logicalTable>
              <emis:criteria>
                <emis:criterion>
                  <emis:table>PATIENTS</emis:table>
                  <emis:filterAttribute>
                    <emis:columnValue>
                      <emis:column>CODE</emis:column>
                      <emis:valueSet>
                        <emis:values>
                          <emis:value>XYZ</emis:value>
                          <emis:displayName>Example Code</emis:displayName>
                        </emis:values>
                      </emis:valueSet>
                    </emis:columnValue>
                  </emis:filterAttribute>
                </emis:criterion>
              </emis:criteria>
            </emis:customAggregate>
          </emis:auditReport>
        </emis:report>
        """

        root = ET.fromstring(xml)
        code_store = CodeStore()
        result = parse_report(root, self.ns, "audit_report", code_store=code_store)

        flags = result.get("flags", {})
        self.assertEqual(flags.get("population_reference_guid"), ["POP-1"])
        self.assertIn("aggregate", result)
        self.assertEqual(result["aggregate"].get("type"), "audit_custom_aggregate")
        self.assertTrue(result.get("aggregate_criteria"))


if __name__ == "__main__":
    unittest.main()
