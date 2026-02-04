"""Debug tabs module."""

from .debug_tab import render_debug_tab
from .memory_tab import render_memory_content
from .plugins_tab import render_plugins_content

__all__ = [
    "render_debug_tab",
    "render_memory_content",
    "render_plugins_content",
]
