import streamlit as st
from typing import Dict, Any, List
from ...theme import info_box


def render_file_browser(folder_tree: Dict[str, Any]):
    """
    Render a directory-style browser of the XML folder structure.
    Shows searches and reports only in their source folders.
    """
    @st.fragment
    def file_browser_fragment():
        roots = folder_tree.get("roots") or []
        if not roots:
            st.markdown(info_box("No folders found in this XML."), unsafe_allow_html=True)
            return

        _render_ascii_tree(roots)

    file_browser_fragment()


def _pretty_type(type_str: str) -> str:
    if not type_str:
        return "Report"
    type_lower = type_str.lower()
    if "list" in type_lower:
        return "List Report"
    if "audit" in type_lower:
        return "Audit Report"
    if "aggregate" in type_lower:
        return "Aggregate Report"
    if "search" in type_lower:
        return "Search"
    return "Report"


def _count_items_recursive(node: Dict[str, Any]) -> Dict[str, int]:
    """Count searches (including nested) and report types recursively."""
    counts = {"searches": 0, "list": 0, "audit": 0, "aggregate": 0}

    def count_search(search: Dict[str, Any]):
        counts["searches"] += 1
        for rep in search.get("reports") or []:
            rtype = rep.get("type_label") or rep.get("source_type") or rep.get("type") or ""
            if "list" in rtype.lower():
                counts["list"] += 1
            elif "audit" in rtype.lower():
                counts["audit"] += 1
            elif "aggregate" in rtype.lower():
                counts["aggregate"] += 1
        for child in search.get("children") or []:
            count_search(child)

    for s in node.get("searches") or []:
        count_search(s)

    for rep in node.get("reports") or []:
        rtype = rep.get("type_label") or rep.get("source_type") or rep.get("type") or ""
        if "list" in rtype.lower():
            counts["list"] += 1
        elif "audit" in rtype.lower():
            counts["audit"] += 1
        elif "aggregate" in rtype.lower():
            counts["aggregate"] += 1

    for child_folder in node.get("children") or []:
        child_counts = _count_items_recursive(child_folder)
        for key in counts:
            counts[key] += child_counts[key]

    return counts


def _render_ascii_tree(roots: List[Dict[str, Any]]):
    def _plural(count: int, singular: str) -> str:
        return f"{count} {singular}" if count == 1 else f"{count} {singular}s"

    def walk(node: Dict[str, Any], prefix: str, is_last_folder: bool, lines: List[str]):
        connector = "+--"
        name = node.get("name") or node.get("id") or "Unnamed"

        counts = _count_items_recursive(node)
        total_reports = counts["list"] + counts["audit"] + counts["aggregate"]
        breakdown_parts = []
        if counts["list"]:
            breakdown_parts.append(_plural(counts["list"], "List"))
        if counts["audit"]:
            breakdown_parts.append(_plural(counts["audit"], "Audit"))
        if counts["aggregate"]:
            breakdown_parts.append(_plural(counts["aggregate"], "Aggregate"))

        count_str = ""
        if counts["searches"] or total_reports:
            base = f"{_plural(counts['searches'], 'Search')} and {_plural(total_reports, 'Report')}"
            if total_reports:
                base += f": {', '.join(breakdown_parts)}"
            count_str = f" ({base})"

        lines.append(f"{prefix}{connector} [+].[{name}]{count_str}")

        extension = "    " if is_last_folder else "|   "
        child_prefix = prefix + extension
        item_prefix = child_prefix + "    "

        searches = node.get("searches") or []
        reports = node.get("reports") or []
        children = node.get("children") or []

        def render_search(search: Dict[str, Any], prefix: str, is_last: bool):
            connector_type = "+--" if is_last else "|--"
            label = search.get("name") or search.get("id") or "Unnamed"
            lines.append(f"{prefix}{connector_type} * [Search].[{label}]")

            child_prefix = prefix + ("    " if is_last else "|   ")
            children = search.get("children") or []
            reports = search.get("reports") or []
            combined = []
            combined.extend([("search", s) for s in children])
            combined.extend([("report", r) for r in reports])
            for idx, (ctype, child) in enumerate(combined):
                last_child = idx == len(combined) - 1
                if ctype == "search":
                    render_search(child, child_prefix, last_child)
                else:
                    c_label = child.get("name") or child.get("id") or "Unnamed"
                    rtype = _pretty_type(child.get("type_label") or child.get("source_type") or child.get("type") or "")
                    child_connector = "+--" if last_child else "|--"
                    lines.append(f"{child_prefix}{child_connector} * [{rtype}].[{c_label}]")

        # Render searches first (preserving order), then reports, then child folders
        for idx, search in enumerate(searches):
            render_search(search, item_prefix, idx == len(searches) - 1 and not reports and not children)

        for idx, report in enumerate(reports):
            connector_type = "+--" if idx == len(reports) - 1 and not children else "|--"
            label = report.get("name") or report.get("id") or "Unnamed"
            report_type = _pretty_type(report.get("type_label") or report.get("source_type") or report.get("type") or "")
            lines.append(f"{item_prefix}{connector_type} * [{report_type}].[{label}]")

        for idx, child_folder in enumerate(children):
            walk(child_folder, child_prefix, idx == len(children) - 1, lines)

    lines: List[str] = []
    for idx, root in enumerate(roots):
        walk(root, "", idx == len(roots) - 1, lines)
        if idx < len(roots) - 1:
            lines.append("")

    if lines:
        st.code("\n".join(lines))
