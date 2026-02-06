"""
Focused tests for plugin registry versioning and metadata behaviour.

Tests:
- Metadata registration via PluginMetadata
- Priority ordering and tie-breaking
- Version compatibility validation (valid and malformed)
- Enable/disable persistence
"""

import unittest
from unittest.mock import patch, MagicMock

from utils.pattern_plugins.base import (
    PatternContext,
    PatternResult,
    PluginMetadata,
    PluginPriority,
)
from utils.pattern_plugins.registry import PatternRegistry


def _dummy_detector(ctx: PatternContext) -> PatternResult:
    """Minimal detector for testing."""
    return PatternResult(
        id="test",
        description="Test result",
        flags={"test": True},
    )


class TestMetadataRegistration(unittest.TestCase):
    """Tests for plugin registration with PluginMetadata."""

    def test_register_with_string_id_creates_default_metadata(self):
        """String ID registration should create default PluginMetadata."""
        registry = PatternRegistry()
        registry.register("test_plugin", _dummy_detector)

        status = registry.get_plugin_status()
        self.assertIn("test_plugin", status)
        self.assertEqual(status["test_plugin"]["version"], "1.0.0")
        self.assertEqual(status["test_plugin"]["priority"], PluginPriority.DEFAULT)
        self.assertEqual(status["test_plugin"]["description"], "")
        self.assertEqual(status["test_plugin"]["tags"], [])

    def test_register_with_metadata_preserves_all_fields(self):
        """PluginMetadata registration should preserve all fields."""
        registry = PatternRegistry()
        metadata = PluginMetadata(
            id="full_metadata_plugin",
            version="2.1.0",
            description="A test plugin",
            author="Test Author",
            priority=PluginPriority.HIGH,
            min_app_version="3.0.0",
            tags=["test", "example"],
        )
        registry.register(metadata, _dummy_detector)

        status = registry.get_plugin_status()
        self.assertIn("full_metadata_plugin", status)
        self.assertEqual(status["full_metadata_plugin"]["version"], "2.1.0")
        self.assertEqual(status["full_metadata_plugin"]["priority"], PluginPriority.HIGH)
        self.assertEqual(status["full_metadata_plugin"]["description"], "A test plugin")
        self.assertEqual(status["full_metadata_plugin"]["tags"], ["test", "example"])

    def test_register_duplicate_id_raises_value_error(self):
        """Registering duplicate plugin ID should raise ValueError."""
        registry = PatternRegistry()
        registry.register("duplicate_id", _dummy_detector)

        with self.assertRaises(ValueError) as ctx:
            registry.register("duplicate_id", _dummy_detector)

        self.assertIn("already registered", str(ctx.exception))


class TestPriorityOrdering(unittest.TestCase):
    """Tests for priority-based execution ordering."""

    def test_plugins_execute_in_priority_order(self):
        """Plugins should execute in ascending priority order."""
        registry = PatternRegistry()

        # Register in non-priority order
        registry.register(
            PluginMetadata(id="low", priority=PluginPriority.LOW),
            _dummy_detector
        )
        registry.register(
            PluginMetadata(id="high", priority=PluginPriority.HIGH),
            _dummy_detector
        )
        registry.register(
            PluginMetadata(id="normal", priority=PluginPriority.NORMAL),
            _dummy_detector
        )
        registry.register(
            PluginMetadata(id="critical", priority=PluginPriority.CRITICAL),
            _dummy_detector
        )

        # Force order computation
        order = registry._compute_execution_order()

        self.assertEqual(order, ["critical", "high", "normal", "low"])

    def test_same_priority_sorted_alphabetically(self):
        """Plugins with same priority should be sorted by ID alphabetically."""
        registry = PatternRegistry()

        registry.register(
            PluginMetadata(id="zebra", priority=PluginPriority.NORMAL),
            _dummy_detector
        )
        registry.register(
            PluginMetadata(id="alpha", priority=PluginPriority.NORMAL),
            _dummy_detector
        )
        registry.register(
            PluginMetadata(id="beta", priority=PluginPriority.NORMAL),
            _dummy_detector
        )

        order = registry._compute_execution_order()

        self.assertEqual(order, ["alpha", "beta", "zebra"])

    def test_custom_priority_values_sort_correctly(self):
        """Custom priority values should sort numerically."""
        registry = PatternRegistry()

        registry.register(
            PluginMetadata(id="p40", priority=40),
            _dummy_detector
        )
        registry.register(
            PluginMetadata(id="p100", priority=100),
            _dummy_detector
        )
        registry.register(
            PluginMetadata(id="p25", priority=25),
            _dummy_detector
        )

        order = registry._compute_execution_order()

        self.assertEqual(order, ["p25", "p40", "p100"])


class TestVersionCompatibility(unittest.TestCase):
    """Tests for version compatibility checking."""

    @patch("utils.system.version.__version__", "99.99.99")
    def test_valid_version_formats_accepted(self):
        """Valid version formats should not raise errors."""
        registry = PatternRegistry()

        # These should all register without error
        valid_versions = ["1.0.0", "3.0.0", "10.20.30", "v3.0.0", "3.0.1-beta"]
        for i, version in enumerate(valid_versions):
            registry.register(
                PluginMetadata(id=f"plugin_{i}", min_app_version=version),
                _dummy_detector
            )

        self.assertEqual(len(registry.registered_ids()), len(valid_versions))

    def test_malformed_min_app_version_raises_value_error(self):
        """Malformed min_app_version should raise ValueError."""
        registry = PatternRegistry()

        malformed_versions = [
            "vX.Y.Z",      # No numeric segments
            "abc",         # Pure text
            "...",         # No numbers
            "",            # Empty string
        ]

        for i, version in enumerate(malformed_versions):
            with self.assertRaises(ValueError, msg=f"Expected error for: {version}"):
                registry.register(
                    PluginMetadata(id=f"bad_{i}", min_app_version=version),
                    _dummy_detector
                )

    def test_malformed_version_segments_fail_closed(self):
        """Malformed numeric segments should be rejected (fail closed)."""
        registry = PatternRegistry()

        malformed_versions = [
            "3.a.0",       # Alpha in numeric slot
            "3.-1",        # Invalid segment
            "3..1",        # Empty segment
            "1.2.3.4",     # Too many numeric segments
            "v3.a.1",      # Leading v but malformed core
        ]

        for i, version in enumerate(malformed_versions):
            with self.assertRaises(ValueError, msg=f"Expected error for: {version}"):
                registry.register(
                    PluginMetadata(id=f"bad_segment_{i}", min_app_version=version),
                    _dummy_detector
                )

    @patch("utils.system.version.__version__", "3.0.0")
    def test_compatible_version_registers_successfully(self):
        """Plugin with compatible min_app_version should register."""
        registry = PatternRegistry()

        # min_app_version <= app_version should succeed
        registry.register(
            PluginMetadata(id="compatible", min_app_version="3.0.0"),
            _dummy_detector
        )
        registry.register(
            PluginMetadata(id="compatible_older", min_app_version="2.0.0"),
            _dummy_detector
        )

        self.assertIn("compatible", registry.registered_ids())
        self.assertIn("compatible_older", registry.registered_ids())


class TestEnableDisable(unittest.TestCase):
    """Tests for plugin enable/disable functionality."""

    def test_enable_disable_toggles_plugin_state(self):
        """Enable/disable should toggle plugin enabled state."""
        registry = PatternRegistry()
        registry.register("toggle_test", _dummy_detector)

        # Initially enabled
        self.assertTrue(registry.get_plugin_status()["toggle_test"]["enabled"])

        # Disable
        result = registry.disable_plugin("toggle_test")
        self.assertTrue(result)
        self.assertFalse(registry.get_plugin_status()["toggle_test"]["enabled"])

        # Re-enable
        result = registry.enable_plugin("toggle_test")
        self.assertTrue(result)
        self.assertTrue(registry.get_plugin_status()["toggle_test"]["enabled"])

    def test_enable_disable_nonexistent_returns_false(self):
        """Enable/disable on nonexistent plugin should return False."""
        registry = PatternRegistry()

        self.assertFalse(registry.enable_plugin("nonexistent"))
        self.assertFalse(registry.disable_plugin("nonexistent"))

    def test_disabled_plugins_skipped_in_run_all(self):
        """Disabled plugins should not execute in run_all."""
        registry = PatternRegistry()

        call_log = []

        def logging_detector_a(ctx):
            call_log.append("a")
            return None

        def logging_detector_b(ctx):
            call_log.append("b")
            return None

        registry.register("detector_a", logging_detector_a)
        registry.register("detector_b", logging_detector_b)

        # Create minimal context
        import xml.etree.ElementTree as ET
        ctx = PatternContext(element=ET.Element("test"), namespaces={})

        # Both should run
        registry.run_all(ctx)
        self.assertEqual(sorted(call_log), ["a", "b"])

        # Disable one
        call_log.clear()
        registry.disable_plugin("detector_a")
        registry.run_all(ctx)
        self.assertEqual(call_log, ["b"])


class TestSessionStatePersistence(unittest.TestCase):
    """Tests for Streamlit session state persistence."""

    def test_persist_enabled_state_writes_to_session_state(self):
        """_persist_enabled_state should write to st.session_state."""
        registry = PatternRegistry()
        registry.register("persist_test", _dummy_detector)
        registry.disable_plugin("persist_test")

        # Mock streamlit
        mock_st = MagicMock()
        mock_st.session_state = {}

        with patch.dict("sys.modules", {"streamlit": mock_st}):
            registry._persist_enabled_state()

        self.assertIn("_plugin_enabled_state", mock_st.session_state)
        self.assertEqual(
            mock_st.session_state["_plugin_enabled_state"]["persist_test"],
            False
        )

    def test_restore_enabled_state_reads_from_session_state(self):
        """restore_enabled_state should restore from st.session_state."""
        registry = PatternRegistry()
        registry.register("restore_test", _dummy_detector)

        # Initially enabled
        self.assertTrue(registry.get_plugin_status()["restore_test"]["enabled"])

        # Mock streamlit with saved disabled state using a proper dict subclass
        class MockSessionState(dict):
            pass

        mock_session_state = MockSessionState({
            "_plugin_enabled_state": {"restore_test": False}
        })

        mock_st = MagicMock()
        mock_st.session_state = mock_session_state

        with patch.dict("sys.modules", {"streamlit": mock_st}):
            registry.restore_enabled_state()

        self.assertFalse(registry.get_plugin_status()["restore_test"]["enabled"])


if __name__ == "__main__":
    unittest.main()
