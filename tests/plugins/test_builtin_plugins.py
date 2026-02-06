import unittest
import xml.etree.ElementTree as ET

from utils.pattern_plugins.base import PatternContext
from utils.pattern_plugins import (
    restrictions,
    temporal,
    demographics,
    relationships,
    value_sets,
    refsets,
    medication,
    logic,
    population,
    enterprise,
    parameters,
    column_filters,
    emisinternal,
    source_containers,
)


NS = {"emis": "http://www.e-mis.com/emisopen"}


def _criterion(inner_xml: str) -> ET.Element:
    xml = f'<emis:criterion xmlns:emis="{NS["emis"]}">{inner_xml}</emis:criterion>'
    return ET.fromstring(xml)


def _ctx(inner_xml: str) -> PatternContext:
    elem = _criterion(inner_xml)
    return PatternContext(element=elem, namespaces=NS)


class TestBuiltinPlugins(unittest.TestCase):
    def test_restriction_plugins(self):
        ctx = _ctx(
            """
            <emis:restriction>
              <emis:columnOrder>
                <emis:recordCount>1</emis:recordCount>
                <emis:direction>ASC</emis:direction>
                <emis:column>EVENT_DATE</emis:column>
              </emis:columnOrder>
              <emis:testAttribute>
                <emis:columnValue>
                  <emis:column>AGE</emis:column>
                  <emis:operator>GT</emis:operator>
                </emis:columnValue>
              </emis:testAttribute>
            </emis:restriction>
            """
        )

        latest = restrictions.detect_latest_earliest(ctx)
        test_attr = restrictions.detect_test_attribute(ctx)

        self.assertIsNotNone(latest)
        self.assertEqual(latest.flags["restriction_type"], "earliest_records")
        self.assertEqual(latest.flags["ordering_column"], "EVENT_DATE")

        self.assertIsNotNone(test_attr)
        self.assertEqual(test_attr.flags["test_condition_column"], "AGE")
        self.assertEqual(test_attr.flags["test_condition_operator"], "GT")

    def test_temporal_plugins(self):
        single = temporal.detect_temporal_single_value(
            _ctx(
                """
                <emis:singleValue>
                  <emis:variable>
                    <emis:value>Last</emis:value>
                    <emis:unit>MONTH</emis:unit>
                    <emis:relation>RELATIVE</emis:relation>
                  </emis:variable>
                </emis:singleValue>
                """
            )
        )
        ranged = temporal.detect_temporal_range(
            _ctx(
                """
                <emis:rangeValue relativeTo="NOW">
                  <emis:rangeFrom>
                    <emis:operator>GTEQ</emis:operator>
                    <emis:value>
                      <emis:value>0</emis:value>
                      <emis:unit>DAY</emis:unit>
                    </emis:value>
                  </emis:rangeFrom>
                  <emis:rangeTo>
                    <emis:operator>LTEQ</emis:operator>
                    <emis:value>
                      <emis:value>28</emis:value>
                      <emis:unit>DAY</emis:unit>
                    </emis:value>
                  </emis:rangeTo>
                </emis:rangeValue>
                """
            )
        )

        self.assertIsNotNone(single)
        self.assertEqual(single.flags["temporal_variable_value"], "Last")
        self.assertEqual(single.flags["temporal_unit"], "MONTH")

        self.assertIsNotNone(ranged)
        self.assertEqual(ranged.flags["relative_to"], "NOW")
        self.assertEqual(ranged.flags["range_from_value"], "0")
        self.assertEqual(ranged.flags["range_to_value"], "28")

    def test_demographics_and_relationship_plugins(self):
        demo = demographics.detect_demographics_lsoa(
            _ctx("<emis:column>PATIENT_LOWER_AREA_CODE</emis:column>")
        )
        relation = relationships.detect_linked_relationship(
            _ctx(
                """
                <emis:relationship>
                  <emis:parentColumn>EVENT_DATE</emis:parentColumn>
                  <emis:childColumn>DRUG_DATE</emis:childColumn>
                </emis:relationship>
                """
            )
        )

        self.assertIsNotNone(demo)
        self.assertEqual(demo.flags["demographics_type"], "LSOA")
        self.assertIsNotNone(relation)
        self.assertEqual(relation.flags["relationship_type"], "date_based")

    def test_valueset_refset_and_medication_plugins(self):
        vs_props = value_sets.detect_value_set_properties(
            _ctx(
                """
                <emis:valueSet>
                  <emis:libraryItem>true</emis:libraryItem>
                  <emis:inactive>true</emis:inactive>
                </emis:valueSet>
                """
            )
        )
        vs_desc = value_sets.detect_value_set_description_handling(
            _ctx(
                """
                <emis:valueSet>
                  <emis:id>VS-1</emis:id>
                  <emis:values>
                    <emis:displayName>Code A</emis:displayName>
                  </emis:values>
                </emis:valueSet>
                """
            )
        )
        refset_result = refsets.detect_refset(
            _ctx(
                """
                <emis:valueSet>
                  <emis:values>
                    <emis:isRefset>true<emis:marker /></emis:isRefset>
                  </emis:values>
                  <emis:values>
                    <emis:value>ABC</emis:value>
                  </emis:values>
                </emis:valueSet>
                """
            )
        )
        med_result = medication.detect_medication_code_system(
            _ctx("<emis:codeSystem>SCT_CONST</emis:codeSystem>")
        )

        self.assertIsNotNone(vs_props)
        self.assertTrue(vs_props.flags["is_library_item"])
        self.assertTrue(vs_props.flags["inactive"])

        self.assertIsNotNone(vs_desc)
        self.assertTrue(vs_desc.flags["use_guid_as_valueset_description"])
        self.assertTrue(vs_desc.flags["has_individual_code_display_names"])

        self.assertIsNotNone(refset_result)
        self.assertTrue(refset_result.flags["is_refset"])
        self.assertTrue(refset_result.flags["is_pseudo_refset"])

        self.assertIsNotNone(med_result)
        self.assertTrue(med_result.flags["is_medication_code"])

    def test_logic_population_enterprise_and_qof_plugins(self):
        logic_result = logic.detect_logic_and_actions(
            _ctx(
                """
                <emis:negation>true</emis:negation>
                <emis:memberOperator>OR</emis:memberOperator>
                <emis:actionIfTrue>SELECT<emis:marker /></emis:actionIfTrue>
                <emis:actionIfFalse>REJECT</emis:actionIfFalse>
                """
            )
        )
        pop_result = population.detect_population_references(
            _ctx('<emis:populationCriterion reportGuid="SEARCH-1" />')
        )
        enterprise_result = enterprise.detect_enterprise_metadata(
            _ctx(
                """
                <emis:enterpriseReportingLevel>organisation</emis:enterpriseReportingLevel>
                <emis:VersionIndependentGUID>VIG-1</emis:VersionIndependentGUID>
                <emis:association>
                  <emis:organisation>ORG-1</emis:organisation>
                  <emis:type>PRIMARY</emis:type>
                </emis:association>
                """
            )
        )
        qof_result = enterprise.detect_qof_contract(
            _ctx(
                """
                <emis:qmasIndicator>Y</emis:qmasIndicator>
                <emis:contractInformation>
                  <emis:scoreNeeded>true</emis:scoreNeeded>
                  <emis:target>5</emis:target>
                </emis:contractInformation>
                """
            )
        )

        self.assertIsNotNone(logic_result)
        self.assertTrue(logic_result.flags["negation"])
        self.assertEqual(logic_result.flags["member_operator"], "OR")

        self.assertIsNotNone(pop_result)
        self.assertEqual(pop_result.flags["population_reference_guid"], ["SEARCH-1"])

        self.assertIsNotNone(enterprise_result)
        self.assertEqual(enterprise_result.flags["version_independent_guid"], "VIG-1")
        self.assertEqual(len(enterprise_result.flags["organisation_associations"]), 1)

        self.assertIsNotNone(qof_result)
        self.assertTrue(qof_result.flags["contract_information_needed"])
        self.assertEqual(qof_result.flags["contract_target"], 5)

    def test_parameters_column_filters_emisinternal_and_container_plugins(self):
        params_result = parameters.detect_parameters(
            _ctx(
                """
                <emis:parameter name="AgeMin" allowGlobal="true" />
                <emis:parameter name="AgeMax" />
                """
            )
        )
        column_filter_result = column_filters.detect_column_filters(
            _ctx(
                """
                <emis:columnValue>
                  <emis:column>AGE</emis:column>
                  <emis:displayName>Age at Event</emis:displayName>
                  <emis:inNotIn>IN</emis:inNotIn>
                  <emis:rangeValue>
                    <emis:rangeFrom>
                      <emis:operator>GTEQ</emis:operator>
                      <emis:value>
                        <emis:value>18</emis:value>
                      </emis:value>
                    </emis:rangeFrom>
                  </emis:rangeValue>
                </emis:columnValue>
                """
            )
        )
        emisinternal_result = emisinternal.detect_emisinternal(
            _ctx(
                """
                <emis:filterAttribute>
                  <emis:columnValue>
                    <emis:column>PATIENT_STATUS</emis:column>
                    <emis:inNotIn>IN</emis:inNotIn>
                    <emis:valueSet>
                      <emis:codeSystem>EMISINTERNAL</emis:codeSystem>
                      <emis:values>
                        <emis:value>ACTIVE</emis:value>
                        <emis:displayName>Active</emis:displayName>
                      </emis:values>
                    </emis:valueSet>
                  </emis:columnValue>
                </emis:filterAttribute>
                """
            )
        )
        container_result = source_containers.container_heuristics(
            _ctx("<emis:table>MEDICATION_ISSUES</emis:table>")
        )

        self.assertIsNotNone(params_result)
        self.assertTrue(params_result.flags["has_parameter"])
        self.assertTrue(params_result.flags["has_global_parameters"])

        self.assertIsNotNone(column_filter_result)
        self.assertEqual(column_filter_result.flags["column_filters"][0]["filter_type"], "age")

        self.assertIsNotNone(emisinternal_result)
        self.assertTrue(emisinternal_result.flags["has_emisinternal_filters"])
        self.assertIn("ACTIVE", emisinternal_result.flags["emisinternal_values"])

        self.assertIsNotNone(container_result)
        self.assertEqual(container_result.flags["container_type"], "Search Rule Medication Issues")


if __name__ == "__main__":
    unittest.main()
