import unittest
from unittest.mock import patch

from utils.caching.code_store import CodeStore


class TestCodeStore(unittest.TestCase):
    def setUp(self):
        self.store = CodeStore()
        self.code_dict = {
            "code_value": "12345",
            "valueSet_guid": "VS-1",
            "code_system": "SNOMED_CONCEPT",
            "display_name": "Test code",
            "valueSet_description": "Test valueset",
        }

    def test_add_or_ref_deduplicates_same_entity_and_context(self):
        context = {"criterion": "1"}

        key_one = self.store.add_or_ref(
            self.code_dict,
            entity_id="ENTITY-1",
            entity_type="criterion",
            entity_name="Criterion One",
            criterion_context=context,
        )
        key_two = self.store.add_or_ref(
            self.code_dict,
            entity_id="ENTITY-1",
            entity_type="criterion",
            entity_name="Criterion One",
            criterion_context=context,
        )

        self.assertEqual(key_one, key_two)
        stats = self.store.get_stats()
        self.assertEqual(stats["unique_codes"], 1)
        self.assertEqual(stats["total_references"], 1)
        self.assertEqual(stats["entities_tracked"], 1)

    def test_add_or_ref_keeps_multiple_contexts_for_same_entity(self):
        self.store.add_or_ref(
            self.code_dict,
            entity_id="ENTITY-1",
            entity_type="criterion",
            criterion_context={"criterion": "1"},
        )
        self.store.add_or_ref(
            self.code_dict,
            entity_id="ENTITY-1",
            entity_type="criterion",
            criterion_context={"criterion": "2"},
        )

        stats = self.store.get_stats()
        self.assertEqual(stats["unique_codes"], 1)
        self.assertEqual(stats["total_references"], 2)
        self.assertEqual(len(self.store.get_codes_for_entity("ENTITY-1")), 1)

    def test_add_reference_handles_missing_and_duplicate_keys(self):
        missing_key = self.store.make_key("x", "y", "z")
        self.assertFalse(self.store.add_reference(missing_key, "E1", "criterion"))

        key = self.store.add_or_ref(self.code_dict, "ENTITY-1", "criterion")
        self.assertTrue(self.store.add_reference(key, "ENTITY-2", "criterion"))
        self.assertFalse(self.store.add_reference(key, "ENTITY-2", "criterion"))

    def test_update_pseudo_member_context_updates_fallback_description_only(self):
        key = self.store.add_or_ref(
            {
                **self.code_dict,
                "valueSet_description": "No embedded ValueSet name",
                "is_pseudo_member": False,
            },
            "ENTITY-1",
            "criterion",
        )

        updated = self.store.update_pseudo_member_context(key, "Preferred Name")
        self.assertTrue(updated)

        code = self.store.get_code(key)
        self.assertIsNotNone(code)
        self.assertTrue(code["is_pseudo_member"])
        self.assertEqual(code["valueSet_description"], "Preferred Name")

    def test_debug_logging_uses_global_decisions_when_enabled(self):
        store = CodeStore(enable_debug=True)
        with patch("utils.caching.code_store.emit_debug") as debug_mock:
            key = store.add_or_ref(self.code_dict, "ENTITY-1", "criterion", criterion_context={"criterion": "1"})
            # Duplicate add to trigger duplicate reference path
            store.add_or_ref(self.code_dict, "ENTITY-1", "criterion", criterion_context={"criterion": "1"})
            # Missing key path
            missing_key = store.make_key("missing", "VS-X", "SNOMED_CONCEPT")
            store.add_reference(missing_key, "ENTITY-9", "criterion")
            # Pseudo-member update path
            store.update_pseudo_member_context(key, "Preferred Name")
            store.emit_debug_summary()

            logged_messages = [call.args[1] for call in debug_mock.call_args_list]
            self.assertTrue(any(msg.startswith("summary |") for msg in logged_messages))
            self.assertTrue(any(msg.startswith("skipped/dropped detail |") for msg in logged_messages))


if __name__ == "__main__":
    unittest.main()
