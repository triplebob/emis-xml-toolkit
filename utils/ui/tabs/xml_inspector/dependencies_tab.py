import streamlit as st
from typing import List, Dict, Any, Set, Tuple
from ...theme import info_box


def render_dependencies_tab(nodes: List[Dict[str, Any]], deps: Dict[str, List[str]], dependents: Dict[str, List[str]], id_to_name: Dict[str, str]):
    """
    Render combined search/report dependency and dependent views.
    """
    @st.fragment
    def dependencies_fragment():
        if not nodes:
            st.markdown(info_box("No structure elements detected."), unsafe_allow_html=True)
            return

        # Deduplicate nodes by GUID
        node_map: Dict[str, Dict[str, Any]] = {}
        for node in nodes:
            nid = node.get("id")
            if not nid or nid in node_map:
                continue
            node_map[nid] = node

        st.markdown("🔗 Report dependency relationships:")
        _render_dependency_ascii(node_map, deps, dependents)

    dependencies_fragment()


def _render_dependency_graph(node_map: Dict[str, Dict[str, Any]], deps: Dict[str, List[str]]):
    try:
        import plotly.graph_objects as go
    except ImportError:
        st.caption("Plotly not available; dependency graph skipped.")
        return

    nodes: List[str] = []
    node_index: Dict[str, int] = {}
    for nid, node in node_map.items():
        label = node.get("name") or nid
        type_label = node.get("type_label")
        if type_label:
            label = f"[{type_label}] {label}"
        node_index[nid] = len(nodes)
        nodes.append(label)

    sources: List[int] = []
    targets: List[int] = []
    values: List[int] = []
    seen_edges = set()

    for src, dep_ids in deps.items():
        if src not in node_index:
            continue
        for tgt in dep_ids:
            if tgt not in node_index:
                continue
            edge = (src, tgt)
            if edge in seen_edges:
                continue
            seen_edges.add(edge)
            sources.append(node_index[src])
            targets.append(node_index[tgt])
            values.append(1)

    if not sources:
        st.caption("No dependency edges to visualise.")
        return

    fig = go.Figure(
        go.Sankey(
            node=dict(label=nodes, pad=15, thickness=15),
            link=dict(source=sources, target=targets, value=values),
            arrangement="snap",
        )
    )
    fig.update_layout(margin=dict(t=10, l=10, r=10, b=10), height=400)
    st.plotly_chart(fig, width='stretch')


def _build_dependency_tree(node_map: Dict[str, Dict[str, Any]], deps: Dict[str, List[str]], dependents: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    """Build tree roots based on nodes participating in the graph (deps or dependents)."""
    involved: Set[str] = set()
    for src, targets in deps.items():
        involved.add(src)
        involved.update(targets)
    for tgt, children in dependents.items():
        involved.add(tgt)
        involved.update(children)

    # If nothing is involved, return empty tree to allow missing count to show all
    if not involved:
        return []

    roots: List[str] = [nid for nid in involved if not deps.get(nid)]
    if not roots:
        roots = sorted(involved)

    def walk(nid: str, visited: Set[str]) -> Dict[str, Any]:
        children = []
        for child in sorted(dependents.get(nid, [])):
            if child in visited:
                continue
            visited.add(child)
            children.append(walk(child, visited))
        return {"id": nid, "children": children}

    tree = []
    for idx, root_id in enumerate(sorted(roots)):
        tree.append(walk(root_id, {root_id}))
    return tree


def _render_dependency_ascii(node_map: Dict[str, Dict[str, Any]], deps: Dict[str, List[str]], dependents: Dict[str, List[str]]):
    tree = _build_dependency_tree(node_map, deps, dependents)

    def _label(nid: str) -> str:
        node = node_map.get(nid, {})
        name = node.get("name") or nid
        tlabel = node.get("type_label") or ""
        # Compatibility-style: [Type].[Name]
        if tlabel:
            return f"[{tlabel}].[{name}]"
        return name

    def _walk(node: Dict[str, Any], prefix: str, is_last: bool, is_root: bool, lines: List[str]):
        connector = "+-- " if is_last else "|-- "
        tag = "[R] > " if is_root else "[D] > "
        lines.append(f"{prefix}{connector}{tag}{_label(node['id'])}")
        extension = "    " if is_last else "|   "
        new_prefix = prefix + extension
        children = node.get("children") or []
        for idx, child in enumerate(children):
            _walk(child, new_prefix, idx == len(children) - 1, False, lines)

    # Summary
    def _plural(count: int, singular: str) -> str:
        return f"{count} {singular}" if count == 1 else f"{count} {singular}s"

    root_searches = sum(1 for r in tree if (node_map.get(r["id"], {}).get("type_label") or "").lower() == "search")
    root_reports = sum(1 for r in tree if (node_map.get(r["id"], {}).get("type_label") or "").lower() != "search")

    def _depth(node: Dict[str, Any]) -> int:
        if not node.get("children"):
            return 1
        return 1 + max(_depth(child) for child in node["children"])

    max_depth = max((_depth(r) for r in tree), default=0)

    # Independent = unique GUIDs that have no dependencies (not in deps or dependents)
    involved: Set[str] = set()
    for src, targets in deps.items():
        involved.add(src)
        involved.update(targets)
    for tgt, children in dependents.items():
        involved.add(tgt)
        involved.update(children)
    isolated = sorted([nid for nid in node_map.keys() if nid not in involved])
    independent_count = len(isolated)

    lines: List[str] = []

    def _title_case(text: str) -> str:
        parts = text.split(" ")
        return " ".join(p.capitalize() for p in parts)

    summary = f"{_title_case(_plural(root_searches, 'root search'))} and {_title_case(_plural(root_reports, 'root report'))}. Max Depth: {max_depth}. Independent: {independent_count}"
    lines.append(f"🔗 {summary}")
    lines.append("")

    for idx, root in enumerate(tree):
        _walk(root, "", idx == len(tree) - 1, True, lines)
        if idx < len(tree) - 1:
            lines.append("")

    if isolated:
        labels = []
        for mid in isolated:
            node = node_map.get(mid, {})
            mlabel = node.get("name") or mid
            mtype = node.get("type_label") or ""
            suffix = f" ({mtype})" if mtype else ""
            labels.append(f"{mlabel}{suffix}")
        lines.append("")
        lines.append(f"ℹ️ {len(isolated)} item(s) have no dependency links:")
        for label in labels:
            lines.append(f"- {label}")

    if lines:
        st.code("\n".join(lines))
