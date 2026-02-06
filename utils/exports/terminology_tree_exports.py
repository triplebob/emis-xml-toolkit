"""Export helpers for terminology hierarchy tree views."""

from typing import Any, Dict, List, Optional

from .explorer_exports import render_explorer_tree_export_controls


def render_lookup_hierarchy_export_controls(
    *,
    lines: List[str],
    parent_code: str,
    json_data: Optional[Dict[str, Any]] = None,
) -> None:
    """Render lazy TXT/SVG/JSON export controls for hierarchy trees."""
    if not lines:
        return

    # Reuse explorer lazy export pipeline for immediate post-download cleanup.
    render_explorer_tree_export_controls(
        lines=lines,
        xml_filename=f"hierarchy_{parent_code}",
        tree_label="lineage_hierarchy",
        tree_display_name="Hierarchy Tree",
        expander_label="📥 Export Hierarchy",
        state_prefix=f"lookup_hierarchy_tree_{parent_code}",
        expander_expanded=True,
        json_data=json_data,
    )
