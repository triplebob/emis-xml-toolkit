import unittest
from unittest import mock

import pandas as pd

# Importing status_bar first avoids lookup_manager import-order issues in bare test mode.
import utils.ui.status_bar  # noqa: F401
from utils.metadata import snomed_translation


class TestSnomedTranslation(unittest.TestCase):
    def setUp(self):
        snomed_translation.translate_emis_to_snomed.clear()
        self.lookup_df = pd.DataFrame(
            [
                {
                    "EMIS_GUID": "C1",
                    "SNOMED_Code": 111111111,
                    "Source_Type": "Clinical",
                    "HasQualifier": "No",
                    "IsParent": "No",
                    "Descendants": "0",
                    "CodeType": "Concept",
                },
                {
                    "EMIS_GUID": "M1",
                    "SNOMED_Code": 222222222,
                    "Source_Type": "Medication",
                    "HasQualifier": "No",
                    "IsParent": "No",
                    "Descendants": "0",
                    "CodeType": "Concept",
                },
            ]
        )

    def test_translate_emis_to_snomed_classifies_clinical_and_medication(self):
        emis_guids = [
            {
                "emis_guid": "C1",
                "valueSet_guid": "VS-CLIN",
                "code_system": "SNOMED_CONCEPT",
                "xml_display_name": "Clinical Term",
                "source_guid": "SEARCH-1",
            },
            {
                "emis_guid": "M1",
                "valueSet_guid": "VS-MED",
                "code_system": "SCT_PREP",
                "xml_display_name": "Medication Term",
                "source_guid": "SEARCH-1",
            },
        ]

        with mock.patch.object(snomed_translation, "clear_expired_snomed_cache"), mock.patch.object(
            snomed_translation, "get_cached_snomed_mappings", return_value={}
        ), mock.patch.object(snomed_translation, "update_snomed_cache") as mock_update:
            output = snomed_translation.translate_emis_to_snomed(
                emis_guids, self.lookup_df, "EMIS_GUID", "SNOMED_Code", deduplication_mode="unique_codes"
            )

        self.assertEqual(len(output["clinical"]), 1)
        self.assertEqual(len(output["medications"]), 1)
        self.assertEqual(output["clinical"][0]["SNOMED Code"], "111111111")
        self.assertEqual(output["medications"][0]["SNOMED Code"], "222222222")
        self.assertEqual(output["medications"][0]["Medication Type"], "SCT_PREP (Preparation)")

        mock_update.assert_called_once()
        cached = mock_update.call_args.args[0]
        self.assertEqual(set(cached.keys()), {"C1", "M1"})

    def test_deduplication_mode_unique_vs_per_entity(self):
        emis_guids = [
            {
                "emis_guid": "C1",
                "valueSet_guid": "VS-1",
                "code_system": "SNOMED_CONCEPT",
                "xml_display_name": "Clinical Term",
                "source_guid": "SEARCH-A",
            },
            {
                "emis_guid": "C1",
                "valueSet_guid": "VS-1",
                "code_system": "SNOMED_CONCEPT",
                "xml_display_name": "Clinical Term",
                "source_guid": "SEARCH-B",
            },
        ]

        with mock.patch.object(snomed_translation, "clear_expired_snomed_cache"), mock.patch.object(
            snomed_translation, "get_cached_snomed_mappings", return_value={}
        ), mock.patch.object(snomed_translation, "update_snomed_cache"):
            unique_codes = snomed_translation.translate_emis_to_snomed(
                emis_guids, self.lookup_df, "EMIS_GUID", "SNOMED_Code", deduplication_mode="unique_codes"
            )

        snomed_translation.translate_emis_to_snomed.clear()

        with mock.patch.object(snomed_translation, "clear_expired_snomed_cache"), mock.patch.object(
            snomed_translation, "get_cached_snomed_mappings", return_value={}
        ), mock.patch.object(snomed_translation, "update_snomed_cache"):
            unique_per_entity = snomed_translation.translate_emis_to_snomed(
                emis_guids, self.lookup_df, "EMIS_GUID", "SNOMED_Code", deduplication_mode="unique_per_entity"
            )

        self.assertEqual(len(unique_codes["clinical"]), 1)
        self.assertEqual(len(unique_per_entity["clinical"]), 2)

    def test_emisinternal_entries_are_not_exported_or_cached(self):
        emis_guids = [
            {
                "emis_guid": "C1",
                "valueSet_guid": "VS-CLIN",
                "code_system": "SNOMED_CONCEPT",
                "xml_display_name": "Clinical Term",
                "source_guid": "SEARCH-1",
            },
            {
                "emis_guid": "M1",
                "valueSet_guid": "VS-INTERNAL",
                "code_system": "EMISINTERNAL",
                "xml_display_name": "Internal Flag",
                "source_guid": "SEARCH-1",
            },
        ]

        with mock.patch.object(snomed_translation, "clear_expired_snomed_cache"), mock.patch.object(
            snomed_translation, "get_cached_snomed_mappings", return_value={}
        ), mock.patch.object(snomed_translation, "update_snomed_cache") as mock_update:
            output = snomed_translation.translate_emis_to_snomed(
                emis_guids, self.lookup_df, "EMIS_GUID", "SNOMED_Code", deduplication_mode="unique_codes"
            )

        all_rows = (
            output["clinical"]
            + output["medications"]
            + output["clinical_pseudo_members"]
            + output["medication_pseudo_members"]
        )
        self.assertEqual(len(all_rows), 1)
        self.assertEqual(all_rows[0]["EMIS GUID"], "C1")
        cached = mock_update.call_args.args[0]
        self.assertEqual(set(cached.keys()), {"C1"})


if __name__ == "__main__":
    unittest.main()
