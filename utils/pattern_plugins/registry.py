"""
Pattern registry for the parsing pipeline.
Supports module auto-load, explicit registration, priority ordering,
and runtime enable/disable of detectors.
"""

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable, Dict, List, Optional, Union, overload
import pkgutil
import pathlib

from .base import PatternDetector, PatternContext, PatternResult, PluginMetadata


@dataclass
class RegisteredPlugin:
    """Container for a registered plugin with its metadata."""
    detector: PatternDetector
    metadata: PluginMetadata
    enabled: bool = True


class PatternRegistry:
    """Registry for pattern detector plugins with priority-based execution.

    Features:
    - Priority-ordered execution (lower priority values run first)
    - Runtime enable/disable of individual plugins
    - Version compatibility checking
    - Plugin status introspection
    """

    def __init__(self):
        self._plugins: Dict[str, RegisteredPlugin] = {}
        self._execution_order: List[str] = []
        self._order_dirty: bool = True
        self._loaded_packages: set = set()

    def register(
        self,
        id_or_meta: Union[str, PluginMetadata],
        detector: PatternDetector
    ) -> None:
        """Register a pattern detector with metadata.

        Args:
            id_or_meta: Plugin ID string or PluginMetadata instance
            detector: Callable that detects patterns in XML elements

        Raises:
            ValueError: If plugin ID already registered or version incompatible
        """
        if isinstance(id_or_meta, str):
            metadata = PluginMetadata(id=id_or_meta)
        else:
            metadata = id_or_meta

        if metadata.id in self._plugins:
            raise ValueError(f"Pattern '{metadata.id}' already registered")
        self._check_compatibility(metadata)
        self._plugins[metadata.id] = RegisteredPlugin(detector, metadata)
        self._order_dirty = True

    def _check_compatibility(self, metadata: PluginMetadata) -> None:
        """Validate plugin is compatible with current app version.

        Raises ValueError for malformed version strings (fail closed).
        """
        try:
            from ..system.version import __version__
        except ImportError:
            # Version module not available, skip check
            return

        import re

        def parse_version(v: str, context: str) -> tuple:
            """Parse version string to comparable tuple.

            Accepts semantic versions with optional leading 'v' and optional
            pre-release/build suffixes (e.g. '3.0.1-beta', 'v3.0.0').
            Fails closed for malformed segments.
            """
            if not v or not isinstance(v, str):
                raise ValueError(f"Invalid {context}: empty or non-string value")

            # Strip leading 'v' if present (e.g., "v3.0.0" -> "3.0.0")
            clean_v = v.strip().lstrip("v")

            # Must start with a digit
            if not clean_v or not clean_v[0].isdigit():
                raise ValueError(
                    f"Invalid {context} '{v}': must start with a digit"
                )

            # Drop optional pre-release/build suffixes and validate the numeric core.
            numeric_core = re.split(r"[-+]", clean_v, maxsplit=1)[0]
            parts = numeric_core.split(".")
            if len(parts) > 3 or any(not p.isdigit() for p in parts):
                raise ValueError(
                    f"Invalid {context} '{v}': expected format 'MAJOR[.MINOR[.PATCH]]'"
                )

            return tuple(int(p) for p in parts)

        try:
            app_version = parse_version(__version__, "app version")
            min_version = parse_version(
                metadata.min_app_version,
                f"min_app_version for plugin '{metadata.id}'"
            )
        except ValueError as e:
            # Re-raise with context - malformed versions should prevent registration
            raise ValueError(str(e)) from None

        if app_version < min_version:
            raise ValueError(
                f"Plugin '{metadata.id}' requires ClinXML >= {metadata.min_app_version}, "
                f"but running {__version__}"
            )

    def _compute_execution_order(self) -> List[str]:
        """Sort plugins by priority (ascending), then by ID for stability."""
        sorted_plugins = sorted(
            self._plugins.items(),
            key=lambda x: (x[1].metadata.priority, x[0])
        )
        return [pid for pid, _ in sorted_plugins]

    def run_all(self, context: PatternContext) -> List[PatternResult]:
        """Execute all enabled plugins in priority order.

        Args:
            context: Pattern context with element and namespaces

        Returns:
            List of pattern results from plugins that matched
        """
        if self._order_dirty:
            self._execution_order = self._compute_execution_order()
            self._order_dirty = False

        results: List[PatternResult] = []
        for plugin_id in self._execution_order:
            plugin = self._plugins[plugin_id]
            if not plugin.enabled:
                continue
            result = plugin.detector(context)
            if result:
                if not result.id:
                    result.id = plugin_id
                results.append(result)
        return results

    def registered_ids(self) -> List[str]:
        """Return list of all registered plugin IDs."""
        return list(self._plugins.keys())

    def get_plugin_status(self) -> Dict[str, Dict[str, Any]]:
        """Return status of all plugins for debugging/UI.

        Returns:
            Dict mapping plugin ID to status dict with version, enabled,
            priority, description, and tags.
        """
        return {
            pid: {
                "version": p.metadata.version,
                "enabled": p.enabled,
                "priority": p.metadata.priority,
                "description": p.metadata.description,
                "tags": p.metadata.tags,
            }
            for pid, p in self._plugins.items()
        }

    def enable_plugin(self, plugin_id: str) -> bool:
        """Enable a plugin. Returns True if successful."""
        if plugin_id not in self._plugins:
            return False
        self._plugins[plugin_id].enabled = True
        self._persist_enabled_state()
        return True

    def disable_plugin(self, plugin_id: str) -> bool:
        """Disable a plugin. Returns True if successful."""
        if plugin_id not in self._plugins:
            return False
        self._plugins[plugin_id].enabled = False
        self._persist_enabled_state()
        return True

    def _persist_enabled_state(self) -> None:
        """Persist enabled/disabled state to Streamlit session state."""
        try:
            import streamlit as st
            state = {pid: p.enabled for pid, p in self._plugins.items()}
            st.session_state["_plugin_enabled_state"] = state
        except Exception:
            pass  # Non-Streamlit context or import error

    def restore_enabled_state(self) -> None:
        """Restore enabled/disabled state from Streamlit session state."""
        try:
            import streamlit as st
            state = st.session_state.get("_plugin_enabled_state", {})
            for pid, enabled in state.items():
                if pid in self._plugins:
                    self._plugins[pid].enabled = enabled
        except Exception:
            pass  # Non-Streamlit context or import error

    def load_all_modules(self, package: str):
        """Import all modules in the package to trigger registrations.

        Skips filesystem traversal if the package has already been loaded.
        Always restores persisted enabled/disabled state on each call.
        """
        if package in self._loaded_packages:
            # Still restore state on reruns to preserve user's toggle choices
            self.restore_enabled_state()
            return
        pkg = import_module(package)
        package_path = pathlib.Path(pkg.__file__).parent
        for _, module_name, is_pkg in pkgutil.iter_modules([str(package_path)]):
            if is_pkg:
                continue
            import_module(f"{package}.{module_name}")
        self._loaded_packages.add(package)
        # Restore any persisted enabled/disabled state after loading
        self.restore_enabled_state()


# Global registry instance
pattern_registry = PatternRegistry()


@overload
def register_pattern(id_or_meta: str) -> Callable[[PatternDetector], PatternDetector]: ...
@overload
def register_pattern(id_or_meta: PluginMetadata) -> Callable[[PatternDetector], PatternDetector]: ...


def register_pattern(id_or_meta: Union[str, PluginMetadata]):
    """Decorator to register a pattern detector.

    Accepts either:
    - A plain string ID (backwards compatible, uses default metadata)
    - A PluginMetadata instance (full metadata control)

    Examples:
        # Simple registration (backwards compatible)
        @register_pattern("my_pattern")
        def detect_my_pattern(ctx: PatternContext):
            ...

        # Full metadata registration
        @register_pattern(PluginMetadata(
            id="my_pattern",
            version="1.0.0",
            description="Detects my pattern",
            priority=PluginPriority.NORMAL,
        ))
        def detect_my_pattern(ctx: PatternContext):
            ...
    """
    if isinstance(id_or_meta, str):
        metadata = PluginMetadata(id=id_or_meta)
    elif isinstance(id_or_meta, PluginMetadata):
        metadata = id_or_meta
    else:
        raise TypeError(
            f"register_pattern expects str or PluginMetadata, got {type(id_or_meta).__name__}"
        )

    def decorator(func: PatternDetector) -> PatternDetector:
        pattern_registry.register(metadata, func)
        return func
    return decorator
