import unittest

from utils.metadata.mds_provider import build_mds_dataset


class TestMdsProvider(unittest.TestCase):
    def _build_entities(self):
        search_entity = {
            "id": "search-1",
            "name": "Search One",
            "flags": {"element_type": "search"},
            "criteria_groups": [
                {
                    "criteria": [
                        {
                            "flags": {"logical_table_name": "OBS", "column_name": "CODE"},
                            "value_sets": [
                                {
                                    "code_system": "SNOMED_CONCEPT",
                                    "code_value": "111",
                                    "display_name": "Clinical One",
                                },
                                {
                                    "code_system": "EMISINTERNAL",
                                    "code_value": "INT1",
                                    "display_name": "Internal",
                                },
                                {
                                    "code_system": "SNOMED_CONCEPT",
                                    "code_value": "222",
                                    "display_name": "Pseudo Medication",
                                    "is_pseudo_member": True,
                                    "is_medication": True,
                                },
                                {
                                    "code_system": "SNOMED_CONCEPT",
                                    "code_value": "333",
                                    "display_name": "Pseudo Container",
                                    "is_pseudo_refset": True,
                                    "is_pseudo_member": False,
                                },
                                {
                                    "code_system": "SNOMED_CONCEPT",
                                    "code_value": "",
                                    "display_name": "Missing Guid",
                                },
                            ],
                            "linked_criteria": [
                                {
                                    "criterion": {
                                        "value_sets": [
                                            {
                                                "code_system": "SNOMED_CONCEPT",
                                                "code_value": "444",
                                                "display_name": "Linked Child",
                                            }
                                        ]
                                    }
                                }
                            ],
                        }
                    ]
                }
            ],
        }

        report_entity = {
            "id": "report-1",
            "name": "List Report",
            "flags": {"element_type": "list_report"},
            "report_criteria": [
                {
                    "value_sets": [
                        {
                            "code_system": "SNOMED_CONCEPT",
                            "code_value": "111",
                            "display_name": "Clinical One (report)",
                        }
                    ]
                }
            ],
        }

        return [search_entity, report_entity]

    def _build_pipeline_codes(self):
        return [
            {
                "EMIS GUID": "111",
                "SNOMED Code": "73211009",
                "Mapping Found": "Not Found",
                "SNOMED Description": "Lower quality mapping",
            },
            {
                "EMIS GUID": "111",
                "SNOMED Code": "73211009",
                "Mapping Found": "Found",
                "SNOMED Description": "Best mapping",
            },
            {
                "EMIS GUID": "444",
                "SNOMED Code": "44054006",
                "Mapping Found": "Found",
                "SNOMED Description": "Linked mapping",
            },
        ]

    def test_filters_and_classification(self):
        dataset = build_mds_dataset(
            pipeline_entities=self._build_entities(),
            pipeline_codes=self._build_pipeline_codes(),
            view_mode="unique_codes",
            include_emis_xml=False,
        )

        rows = dataset["rows"]
        summary = dataset["summary"]

        guid_set = {row["emis_guid"] for row in rows}
        self.assertEqual(guid_set, {"111", "222", "444"})

        row_by_guid = {row["emis_guid"]: row for row in rows}
        self.assertEqual(row_by_guid["222"]["code_type"], "medication")
        self.assertEqual(row_by_guid["111"]["code_type"], "clinical")

        self.assertEqual(summary["skipped"]["emisinternal"], 1)
        self.assertEqual(summary["skipped"]["missing_guid"], 1)
        self.assertEqual(summary["skipped"]["pseudo_containers"], 1)

    def test_linked_criteria_are_included(self):
        dataset = build_mds_dataset(
            pipeline_entities=self._build_entities(),
            pipeline_codes=self._build_pipeline_codes(),
            view_mode="unique_codes",
        )

        guid_set = {row["emis_guid"] for row in dataset["rows"]}
        self.assertIn("444", guid_set)

    def test_per_source_mode_dedupes_by_source_and_code(self):
        dataset = build_mds_dataset(
            pipeline_entities=self._build_entities(),
            pipeline_codes=self._build_pipeline_codes(),
            view_mode="per_source",
        )

        rows = dataset["rows"]
        rows_111 = [row for row in rows if row["emis_guid"] == "111"]
        self.assertEqual(len(rows_111), 2)
        self.assertTrue(all("source_guid" in row for row in rows_111))

    def test_enrichment_and_emis_xml_column(self):
        dataset = build_mds_dataset(
            pipeline_entities=self._build_entities(),
            pipeline_codes=self._build_pipeline_codes(),
            view_mode="unique_codes",
            include_emis_xml=True,
        )

        row_111 = next(row for row in dataset["rows"] if row["emis_guid"] == "111")
        self.assertEqual(row_111["snomed_code"], "73211009")
        self.assertEqual(row_111["mapping_status"], "found")
        # Full EMIS-compatible XML block with value, displayName, includeChildren
        self.assertIn("<value>111</value>", row_111["emis_xml"])
        self.assertIn("<displayName>", row_111["emis_xml"])
        self.assertIn("<includeChildren>false</includeChildren>", row_111["emis_xml"])

    def test_include_children_preserved_in_per_source_mode(self):
        """Per-source mode preserves original include_children flag."""
        entities = [
            {
                "id": "search-1",
                "name": "Search One",
                "flags": {"element_type": "search"},
                "criteria_groups": [
                    {
                        "criteria": [
                            {
                                "value_sets": [
                                    {
                                        "code_system": "SNOMED_CONCEPT",
                                        "code_value": "555",
                                        "display_name": "Code with children",
                                        "include_children": True,
                                    }
                                ]
                            }
                        ]
                    }
                ],
            }
        ]

        dataset = build_mds_dataset(
            pipeline_entities=entities,
            view_mode="per_source",
            include_emis_xml=True,
        )

        row = dataset["rows"][0]
        self.assertIn("<includeChildren>true</includeChildren>", row["emis_xml"])

    def test_include_children_defaults_false_on_conflict_in_unique_mode(self):
        """Unique mode defaults to include_children=false when conflicting values exist."""
        entities = [
            {
                "id": "search-1",
                "name": "Search One",
                "flags": {"element_type": "search"},
                "criteria_groups": [
                    {
                        "criteria": [
                            {
                                "value_sets": [
                                    {
                                        "code_system": "SNOMED_CONCEPT",
                                        "code_value": "666",
                                        "display_name": "Same code true",
                                        "include_children": True,
                                    }
                                ]
                            }
                        ]
                    }
                ],
            },
            {
                "id": "search-2",
                "name": "Search Two",
                "flags": {"element_type": "search"},
                "criteria_groups": [
                    {
                        "criteria": [
                            {
                                "value_sets": [
                                    {
                                        "code_system": "SNOMED_CONCEPT",
                                        "code_value": "666",
                                        "display_name": "Same code false",
                                        "include_children": False,
                                    }
                                ]
                            }
                        ]
                    }
                ],
            },
        ]

        dataset = build_mds_dataset(
            pipeline_entities=entities,
            view_mode="unique_codes",
            include_emis_xml=True,
        )

        # Should have one row for code 666
        self.assertEqual(len(dataset["rows"]), 1)
        row = dataset["rows"][0]
        # Should default to false when there's a conflict
        self.assertIn("<includeChildren>false</includeChildren>", row["emis_xml"])

    def test_refset_emis_xml_includes_isrefset_tag(self):
        """Refset codes should include <isRefset>true</isRefset> in EMIS XML output."""
        entities = [
            {
                "id": "search-1",
                "name": "Search One",
                "flags": {"element_type": "search"},
                "criteria_groups": [
                    {
                        "criteria": [
                            {
                                "value_sets": [
                                    {
                                        "code_system": "SNOMED_CONCEPT",
                                        "code_value": "777",
                                        "display_name": "Refset Code",
                                        "is_refset": True,
                                    }
                                ]
                            }
                        ]
                    }
                ],
            }
        ]

        dataset = build_mds_dataset(
            pipeline_entities=entities,
            view_mode="unique_codes",
            include_emis_xml=True,
        )

        self.assertEqual(len(dataset["rows"]), 1)
        row = dataset["rows"][0]
        self.assertEqual(row["code_type"], "refset")
        self.assertIn("<isRefset>true</isRefset>", row["emis_xml"])
        self.assertIn("<value>777</value>", row["emis_xml"])

    def test_clinical_code_emis_xml_no_isrefset_tag(self):
        """Clinical codes should NOT include <isRefset> tag in EMIS XML output."""
        entities = [
            {
                "id": "search-1",
                "name": "Search One",
                "flags": {"element_type": "search"},
                "criteria_groups": [
                    {
                        "criteria": [
                            {
                                "value_sets": [
                                    {
                                        "code_system": "SNOMED_CONCEPT",
                                        "code_value": "888",
                                        "display_name": "Clinical Code",
                                    }
                                ]
                            }
                        ]
                    }
                ],
            }
        ]

        dataset = build_mds_dataset(
            pipeline_entities=entities,
            view_mode="unique_codes",
            include_emis_xml=True,
        )

        self.assertEqual(len(dataset["rows"]), 1)
        row = dataset["rows"][0]
        self.assertEqual(row["code_type"], "clinical")
        self.assertNotIn("<isRefset>", row["emis_xml"])


if __name__ == "__main__":
    unittest.main()
