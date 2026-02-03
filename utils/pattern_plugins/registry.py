"""
Pattern registry for the parsing pipeline.
Supports module auto-load and explicit registration of detectors.
"""

from importlib import import_module
from typing import Dict, List, Optional
from .base import PatternDetector, PatternContext, PatternResult
import pkgutil
import pathlib


class PatternRegistry:
    def __init__(self):
        self._patterns: Dict[str, PatternDetector] = {}
        self._loaded_packages: set = set()

    def register(self, pattern_id: str, detector: PatternDetector):
        if pattern_id in self._patterns:
            raise ValueError(f"Pattern '{pattern_id}' already registered")
        self._patterns[pattern_id] = detector

    def run_all(self, context: PatternContext) -> List[PatternResult]:
        results: List[PatternResult] = []
        for pattern_id, detector in self._patterns.items():
            result = detector(context)
            if result:
                if not result.id:
                    result.id = pattern_id
                results.append(result)
        return results

    def registered_ids(self) -> List[str]:
        return list(self._patterns.keys())

    def load_all_modules(self, package: str):
        """Import all modules in the package to trigger registrations.
        Skips filesystem traversal if the package has already been loaded."""
        if package in self._loaded_packages:
            return
        pkg = import_module(package)
        package_path = pathlib.Path(pkg.__file__).parent
        for _, module_name, is_pkg in pkgutil.iter_modules([str(package_path)]):
            if is_pkg:
                continue
            import_module(f"{package}.{module_name}")
        self._loaded_packages.add(package)


# Global registry instance
pattern_registry = PatternRegistry()


def register_pattern(pattern_id: str):
    """Decorator to register a pattern detector."""
    def decorator(func: PatternDetector):
        pattern_registry.register(pattern_id, func)
        return func
    return decorator
