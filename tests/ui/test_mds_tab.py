"""Tests for MDS tab preview transform and styling logic."""

import unittest

import pandas as pd

from utils.ui.tabs.analytics.mds_tab import _prepare_preview_dataframe, _highlight_mapping_status


class TestMdsPreviewTransform(unittest.TestCase):
    """Tests for _prepare_preview_dataframe column transforms."""

    def test_column_renames_snake_to_friendly(self):
        """snake_case columns are renamed to friendly display names."""
        rows = [
            {
                "emis_guid": "123",
                "snomed_code": "456",
                "description": "Test",
                "code_type": "clinical",
                "mapping_status": "found",
            }
        ]

        df = _prepare_preview_dataframe(rows)

        self.assertIn("EMIS GUID", df.columns)
        self.assertIn("SNOMED Code", df.columns)
        self.assertIn("SNOMED Description", df.columns)
        self.assertIn("Code Type", df.columns)
        self.assertIn("Mapping Found", df.columns)
        self.assertNotIn("emis_guid", df.columns)
        self.assertNotIn("snomed_code", df.columns)

    def test_emis_guid_gets_emoji_prefix(self):
        """Non-empty EMIS GUID values get search emoji prefix."""
        rows = [{"emis_guid": "ABC123", "snomed_code": "", "description": "", "code_type": "clinical", "mapping_status": "found"}]

        df = _prepare_preview_dataframe(rows)

        self.assertTrue(df["EMIS GUID"].iloc[0].startswith("🔍 "))
        self.assertIn("ABC123", df["EMIS GUID"].iloc[0])

    def test_empty_emis_guid_no_emoji(self):
        """Empty EMIS GUID values should not show lonely emoji."""
        rows = [{"emis_guid": "", "snomed_code": "123", "description": "", "code_type": "clinical", "mapping_status": "found"}]

        df = _prepare_preview_dataframe(rows)

        self.assertEqual(df["EMIS GUID"].iloc[0], "")

    def test_snomed_code_gets_emoji_prefix(self):
        """Non-empty SNOMED codes get medical emoji prefix."""
        rows = [{"emis_guid": "123", "snomed_code": "73211009", "description": "", "code_type": "clinical", "mapping_status": "found"}]

        df = _prepare_preview_dataframe(rows)

        self.assertTrue(df["SNOMED Code"].iloc[0].startswith("⚕️ "))
        self.assertIn("73211009", df["SNOMED Code"].iloc[0])

    def test_empty_snomed_code_no_emoji(self):
        """Empty SNOMED codes should not show lonely emoji."""
        rows = [{"emis_guid": "123", "snomed_code": "", "description": "", "code_type": "clinical", "mapping_status": "not_found"}]

        df = _prepare_preview_dataframe(rows)

        self.assertEqual(df["SNOMED Code"].iloc[0], "")

    def test_code_type_capitalisation(self):
        """Code types are capitalised correctly."""
        rows = [
            {"emis_guid": "1", "snomed_code": "", "description": "", "code_type": "clinical", "mapping_status": "found"},
            {"emis_guid": "2", "snomed_code": "", "description": "", "code_type": "medication", "mapping_status": "found"},
            {"emis_guid": "3", "snomed_code": "", "description": "", "code_type": "refset", "mapping_status": "found"},
        ]

        df = _prepare_preview_dataframe(rows)

        self.assertEqual(df["Code Type"].iloc[0], "Clinical")
        self.assertEqual(df["Code Type"].iloc[1], "Medication")
        self.assertEqual(df["Code Type"].iloc[2], "RefSet")

    def test_mapping_status_capitalisation(self):
        """Mapping status values are title-cased with underscores removed."""
        rows = [
            {"emis_guid": "1", "snomed_code": "", "description": "", "code_type": "clinical", "mapping_status": "found"},
            {"emis_guid": "2", "snomed_code": "", "description": "", "code_type": "clinical", "mapping_status": "not_found"},
        ]

        df = _prepare_preview_dataframe(rows)

        self.assertEqual(df["Mapping Found"].iloc[0], "Found")
        self.assertEqual(df["Mapping Found"].iloc[1], "Not Found")

    def test_source_type_capitalisation(self):
        """Source type values are title-cased with underscores removed."""
        rows = [
            {"emis_guid": "1", "snomed_code": "", "description": "", "code_type": "clinical", "mapping_status": "found", "source_type": "list_report"},
        ]

        df = _prepare_preview_dataframe(rows)

        self.assertEqual(df["Source Type"].iloc[0], "List Report")

    def test_emis_xml_column_dropped_from_preview(self):
        """The emis_xml column should be dropped from preview display."""
        rows = [
            {"emis_guid": "1", "snomed_code": "", "description": "", "code_type": "clinical", "mapping_status": "found", "emis_xml": "<value>1</value>"},
        ]

        df = _prepare_preview_dataframe(rows)

        self.assertNotIn("EMIS XML", df.columns)
        self.assertNotIn("emis_xml", df.columns)

    def test_column_ordering(self):
        """Columns appear in expected order."""
        rows = [
            {
                "emis_guid": "1",
                "snomed_code": "123",
                "description": "Test",
                "code_type": "clinical",
                "mapping_status": "found",
                "source_type": "search",
                "source_name": "My Search",
                "source_guid": "search-1",
            }
        ]

        df = _prepare_preview_dataframe(rows)
        cols = list(df.columns)

        # Core columns should come first in order
        self.assertEqual(cols[0], "EMIS GUID")
        self.assertEqual(cols[1], "SNOMED Code")
        self.assertEqual(cols[2], "SNOMED Description")
        self.assertEqual(cols[3], "Code Type")
        self.assertEqual(cols[4], "Mapping Found")

    def test_empty_rows_returns_empty_dataframe(self):
        """Empty input returns empty DataFrame."""
        df = _prepare_preview_dataframe([])

        self.assertTrue(df.empty)


class TestMdsRowHighlighting(unittest.TestCase):
    """Tests for _highlight_mapping_status row styling."""

    def test_found_status_uses_green(self):
        """Rows with 'Found' mapping status use green background."""
        row = pd.Series({"EMIS GUID": "123", "Mapping Found": "Found"})

        styles = _highlight_mapping_status(row)

        self.assertEqual(len(styles), 2)
        for style in styles:
            self.assertIn("background-color:", style)
            # Should be green (ThemeColours.GREEN)
            self.assertIn("#", style)

    def test_not_found_status_uses_red(self):
        """Rows with 'Not Found' mapping status use red background."""
        row = pd.Series({"EMIS GUID": "123", "Mapping Found": "Not Found"})

        styles = _highlight_mapping_status(row)

        self.assertEqual(len(styles), 2)
        for style in styles:
            self.assertIn("background-color:", style)


if __name__ == "__main__":
    unittest.main()
