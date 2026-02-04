"""
Console debug output helpers for consistent runtime logging.
"""

from __future__ import annotations

import sys
from typing import Any

try:
    import streamlit as st
except Exception:  # pragma: no cover - streamlit not available in all contexts
    st = None


def is_debug_enabled() -> bool:
    """Return True when the global debug toggle is enabled."""
    if st is None:
        return False
    try:
        return bool(st.session_state.get("debug_mode", False))
    except Exception:
        return False


def emit_console(level: str, source: str, message: str, *, force: bool = False) -> None:
    """
    Emit a consistently formatted console message.

    Args:
        level: Log level label (for example DEBUG, INFO, WARNING, ERROR).
        source: Source label shown in the second bracket.
        message: Message content.
        force: Emit even when debug mode is disabled.
    """
    if not force and not is_debug_enabled():
        return

    level_label = str(level).upper()
    source_label = str(source).strip().replace(" ", "_")
    print(f"[{level_label}][{source_label}] {message}", file=sys.stderr)


def emit_debug(source: str, message: str) -> None:
    """Emit a debug message in the standard console format."""
    emit_console("DEBUG", source, message)


def emit_error(source: str, message: str, *, force: bool = False) -> None:
    """Emit an error message in the standard console format."""
    emit_console("ERROR", source, message, force=force)

