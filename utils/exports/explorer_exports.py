"""
Export builders for XML Explorer views (Dependencies and File Browser).
"""

import gc
import json
import re
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import streamlit as st


def build_explorer_export_filenames(xml_filename: str = "", tree_label: str = "dependency_tree") -> Tuple[str, str, str]:
    """Build stable TXT/SVG/JSON filenames for an explorer tree export."""
    base_name = Path(str(xml_filename) or "clinxml").stem
    safe_label = str(tree_label or "explorer_tree").strip().lower().replace(" ", "_")
    export_base = f"{base_name}_{safe_label}"
    return f"{export_base}.txt", f"{export_base}.svg", f"{export_base}.json"


def build_explorer_tree_text(lines: List[str]) -> str:
    """Build plain text export content from rendered tree lines."""
    return "\n".join(lines) + "\n"


def build_explorer_tree_json(
    lines: List[str],
    json_data: Optional[Dict[str, Any]] = None,
    tree_label: str = "explorer_tree",
    source_filename: Optional[str] = None,
) -> str:
    """
    Build JSON export content from tree data.

    If json_data is provided (e.g. from LineageTraceResult.to_hierarchical_json()),
    use that directly. Otherwise, create a simple structure with the lines array.
    """
    if json_data is not None:
        return json.dumps(json_data, indent=2, ensure_ascii=False)

    # Fallback: simple JSON structure for explorer trees
    metadata = {
        "export_type": tree_label,
        "export_timestamp": datetime.now().isoformat(),
        "source": "ClinXML™ EMIS XML Toolkit (https://clinxml.streamlit.app)",
        "line_count": len(lines),
    }
    if source_filename:
        metadata["source_file"] = source_filename
    export_data = {
        "export_metadata": metadata,
        "tree_lines": lines,
    }
    return json.dumps(export_data, indent=2, ensure_ascii=False)


def build_explorer_tree_svg(lines: List[str]) -> str:
    """Render monospaced ASCII tree as SVG for exact visual preservation."""
    max_len = max((len(line) for line in lines), default=1)
    char_width = 8
    line_height = 20
    font_size = 14
    width = max(900, (max_len * char_width) + 40)
    height = max(200, (len(lines) * line_height) + 60)

    tspan_lines = []
    y_start = 36
    for idx, line in enumerate(lines):
        y = y_start + (idx * line_height)
        segments = _colourise_tree_line(line)
        line_parts = "".join(
            f'<tspan fill="{colour}">{escape(text)}</tspan>'
            for text, colour in segments
            if text is not None
        )
        if not line_parts:
            line_parts = '<tspan fill="#D4D4D4"> </tspan>'
        tspan_lines.append(f'<tspan x="20" y="{y}">{line_parts}</tspan>')

    tspans = "".join(tspan_lines)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<rect width="100%" height="100%" fill="#1e1e1e"/>'
        f'<text xml:space="preserve" font-family="Consolas, \'Courier New\', monospace" '
        f'font-size="{font_size}" fill="#d4d4d4">{tspans}</text>'
        f"</svg>"
    )


def _colourise_tree_line(line: str) -> List[Tuple[str, str]]:
    """Apply a VS-code style palette to explorer tree exports."""
    if not line:
        return [("", "#D4D4D4")]

    if line.startswith("🔗"):
        return [(line, "#4A9EFF")]
    if line.startswith("ℹ️"):
        return [(line, "#DCDCAA")]
    if line.lstrip().startswith("- "):
        return [(line, "#CE9178")]

    segments: List[Tuple[str, str]] = []
    remaining = line
    depth = 0

    prefix_match = re.match(r"^([| +\-]*)(.*)$", remaining)
    if prefix_match:
        connector_prefix, remaining = prefix_match.groups()
        if connector_prefix:
            segments.append((connector_prefix, "#D19A66"))
            depth = _estimate_depth(connector_prefix)

    if remaining.startswith("[R] > "):
        segments.append(("[R] > ", "#4EC9B0"))
        remaining = remaining[len("[R] > "):]
    elif remaining.startswith("[D] > "):
        segments.append(("[D] > ", "#DCDCAA"))
        remaining = remaining[len("[D] > "):]

    if remaining.startswith("* "):
        depth = max(0, depth - 1)

    folder_match = re.match(r"^(\[\+\]\.\[[^\]]+\])(.*)$", remaining)
    if folder_match:
        folder_token, rest = folder_match.groups()
        tag_match = re.match(r"^(\[\+\])\.\[([^\]]+)\]$", folder_token)
        if tag_match:
            tag_part, name_part = tag_match.groups()
            segments.append((tag_part, "#4A9EFF"))
            segments.append((".", "#D4D4D4"))
            segments.append((f"[{name_part}]", _depth_colour(depth)))
        else:
            segments.append((folder_token, "#4A9EFF"))
        if rest:
            segments.append((rest, "#D4D4D4"))
        return segments

    typed_match = re.match(r"^(\* )?(\[[^\]]+\])\.\[([^\]]+)\](.*)$", remaining)
    if typed_match:
        star_prefix, tag_token, name_token, rest = typed_match.groups()
        if star_prefix:
            segments.append((star_prefix, "#D4D4D4"))
        segments.append((tag_token, _type_colour(tag_token)))
        segments.append((".", "#D4D4D4"))
        segments.append((f"[{name_token}]", _depth_colour(depth)))
        if rest:
            segments.append((rest, "#D4D4D4"))
        return segments

    if remaining:
        segments.append((remaining, "#D4D4D4"))
    return segments


def _estimate_depth(connector_prefix: str) -> int:
    """Estimate node depth from ASCII connector indentation."""
    width = len(connector_prefix or "")
    if width < 4:
        return 0
    return max(0, (width - 4) // 4)


def _type_colour(tag_token: str) -> str:
    """Colour mapping for element type tags (for example [Search], [List Report])."""
    type_name = tag_token.strip("[]").strip().lower()
    mapping = {
        "+": "#4A9EFF",
        "search": "#4EC9B0",
        "list report": "#C586C0",
        "audit report": "#D7BA7D",
        "aggregate report": "#569CD6",
        "report": "#9CDCFE",
    }
    return mapping.get(type_name, "#9CDCFE")


def _depth_colour(depth: int) -> str:
    """Colour palette for names based on node depth."""
    palette = [
        "#D4D4D4",
        "#9CDCFE",
        "#B5CEA8",
        "#CE9178",
        "#DCDCAA",
        "#C586C0",
    ]
    if depth < 0:
        depth = 0
    return palette[depth % len(palette)]


def _render_lazy_tree_export_button(
    *,
    state_key: str,
    context_id: str,
    filename: str,
    mime_type: str,
    export_label: str,
    download_label: str,
    button_key_prefix: str,
    content_builder,
) -> None:
    state = st.session_state.get(state_key, {})
    if state.get("context") != context_id:
        state = {"context": context_id, "ready": False, "filename": filename, "content": ""}
        st.session_state[state_key] = state

    if state.get("ready"):
        download_help = f"Start Download: {filename}"
        downloaded = st.download_button(
            download_label,
            data=state.get("content", ""),
            file_name=state.get("filename") or filename,
            mime=mime_type,
            disabled=not state.get("content"),
            help=download_help,
            key=f"{button_key_prefix}_download_{filename}",
        )
        if downloaded:
            if state_key in st.session_state:
                del st.session_state[state_key]
            gc.collect()
            st.rerun()
    else:
        export_help = f"Generate: {filename}"
        generate_clicked = st.button(
            export_label,
            help=export_help,
            key=f"{button_key_prefix}_generate_{filename}",
        )
        if generate_clicked:
            st.session_state[state_key] = {
                "context": context_id,
                "ready": True,
                "filename": filename,
                "content": content_builder(),
            }
            st.rerun()


def render_explorer_tree_export_controls(
    *,
    lines: List[str],
    xml_filename: str,
    tree_label: str,
    tree_display_name: str,
    expander_label: str,
    state_prefix: str,
    expander_expanded: bool = False,
    json_data: Optional[Dict[str, Any]] = None,
) -> None:
    """Render lazy TXT/SVG/JSON export controls for explorer tree views."""
    if not lines:
        return

    txt_filename, svg_filename, json_filename = build_explorer_export_filenames(xml_filename, tree_label)
    context_id = f"{txt_filename}|{len(lines)}|{lines[0] if lines else ''}|{lines[-1] if lines else ''}"

    # Capture values in closure to avoid late binding issues
    _json_data = json_data
    _tree_label = tree_label
    _xml_filename = xml_filename

    with st.expander(expander_label, expanded=expander_expanded):
        col1, col2, col3, col4, col5, col6 = st.columns([3, 0.1, 3, 0.1, 3, 3])
        with col1:
            _render_lazy_tree_export_button(
                state_key=f"{state_prefix}_txt_export_state",
                context_id=context_id,
                filename=txt_filename,
                mime_type="text/plain",
                export_label=f"🔄 Export {tree_display_name} (TXT)",
                download_label=f"📥 Download {tree_display_name} (TXT)",
                button_key_prefix=f"{state_prefix}_txt",
                content_builder=lambda: build_explorer_tree_text(lines),
            )
        # col2 is spacer
        with col3:
            _render_lazy_tree_export_button(
                state_key=f"{state_prefix}_svg_export_state",
                context_id=context_id,
                filename=svg_filename,
                mime_type="image/svg+xml",
                export_label=f"🔄 Export {tree_display_name} (SVG)",
                download_label=f"📥 Download {tree_display_name} (SVG)",
                button_key_prefix=f"{state_prefix}_svg",
                content_builder=lambda: build_explorer_tree_svg(lines),
            )
        # col4 is spacer
        with col5:
            _render_lazy_tree_export_button(
                state_key=f"{state_prefix}_json_export_state",
                context_id=context_id,
                filename=json_filename,
                mime_type="application/json",
                export_label=f"🔄 Export {tree_display_name} (JSON)",
                download_label=f"📥 Download {tree_display_name} (JSON)",
                button_key_prefix=f"{state_prefix}_json",
                content_builder=lambda: build_explorer_tree_json(lines, _json_data, _tree_label, _xml_filename),
            )
        # col6 is spacer
