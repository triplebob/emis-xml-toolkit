"""
Lineage trace workflow for building hierarchical trees from flat descendant lists.
Pure business logic with no Streamlit dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable

from .service import get_expansion_service


def _is_inactive(value: Any) -> bool:
    """Check if a value represents an inactive status."""
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in {"true", "1", "yes"}


def _ensure_credentials(service, client_id: Optional[str], client_secret: Optional[str]) -> Optional[str]:
    """Ensure service has valid credentials configured."""
    if service.client:
        return None
    if not client_id or not client_secret:
        return "NHS Terminology Server credentials not configured."
    service.configure_credentials(client_id, client_secret)
    return None


@dataclass
class LineageNode:
    """A node in the lineage tree."""
    code: str
    display: str
    emis_guid: Optional[str]
    inactive: bool
    depth: int
    direct_parent_code: Optional[str]
    lineage_path: str
    shared_lineage: bool = False
    all_paths: Optional[List[str]] = None
    children: Optional[List["LineageNode"]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        result = {
            "code": self.code,
            "display": self.display,
            "emis_guid": self.emis_guid,
            "inactive": self.inactive,
            "depth": self.depth,
            "direct_parent_code": self.direct_parent_code,
            "lineage_path": self.lineage_path,
        }
        if self.shared_lineage:
            result["shared_lineage"] = True
            result["all_paths"] = self.all_paths or []
        if self.children:
            result["children"] = [c.to_dict() for c in self.children]
        return result


@dataclass
class LineageTraceResult:
    """Result of a lineage trace operation."""
    root_code: str
    root_display: str
    tree: Optional[LineageNode]
    flat_nodes: List[LineageNode]
    shared_lineage_codes: List[str]
    total_nodes: int
    max_depth_reached: int
    api_calls_made: int
    truncated: bool = False
    truncation_reason: Optional[str] = None
    error: Optional[str] = None

    def to_hierarchical_json(self, source_filename: Optional[str] = None) -> Dict[str, Any]:
        """Export as hierarchical JSON."""
        metadata = {
            "export_type": "lineage_hierarchy",
            "export_timestamp": datetime.now().isoformat(),
            "source": "ClinXML™ EMIS XML Toolkit (https://clinxml.streamlit.app)",
            "root_code": self.root_code,
            "root_display": self.root_display,
            "total_nodes": self.total_nodes,
            "max_depth": self.max_depth_reached,
            "shared_lineage_count": len(self.shared_lineage_codes),
            "truncated": self.truncated,
            "truncation_reason": self.truncation_reason,
        }
        if source_filename:
            metadata["source_file"] = source_filename
        return {
            "export_metadata": metadata,
            "hierarchy": self.tree.to_dict() if self.tree else None,
            "shared_lineage_codes": self.shared_lineage_codes,
        }


@dataclass
class FullLineageTraceResult:
    """Result of tracing lineage for all parent codes in an expansion."""
    trees: List[LineageNode]
    total_nodes: int
    max_depth_reached: int
    total_api_calls: int
    shared_lineage_codes: List[str]
    parent_count: int
    errors: List[str]
    truncated_parent_codes: Optional[List[str]] = None
    truncation_reasons: Optional[Dict[str, str]] = None
    error: Optional[str] = None

    def to_hierarchical_json(self, source_filename: Optional[str] = None) -> Dict[str, Any]:
        """Export as hierarchical JSON."""
        metadata = {
            "export_type": "full_lineage_hierarchy",
            "export_timestamp": datetime.now().isoformat(),
            "source": "ClinXML™ EMIS XML Toolkit (https://clinxml.streamlit.app)",
            "parent_count": self.parent_count,
            "total_nodes": self.total_nodes,
            "max_depth": self.max_depth_reached,
            "shared_lineage_count": len(self.shared_lineage_codes),
            "truncated_parent_count": len(self.truncated_parent_codes or []),
        }
        if source_filename:
            metadata["source_file"] = source_filename
        return {
            "export_metadata": metadata,
            "trees": [t.to_dict() for t in self.trees],
            "shared_lineage_codes": self.shared_lineage_codes,
            "truncated_parent_codes": self.truncated_parent_codes or [],
            "truncation_reasons": self.truncation_reasons or {},
        }


def trace_lineage(
    root_code: str,
    root_display: str,
    descendant_codes: set,
    emis_lookup: Dict[str, str],
    display_lookup: Dict[str, str],
    inactive_lookup: Dict[str, bool],
    include_inactive: bool = False,
    max_depth: int = 10,
    max_api_calls: int = 100,
    max_nodes: Optional[int] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> LineageTraceResult:
    """
    Build a lineage tree from cached flat descendants using direct-children queries.

    This function takes the flat list of descendants (already expanded and cached)
    and discovers the parent-child relationships to build a tree structure.

    Args:
        root_code: The XML parent code (root of the tree)
        root_display: Display name of the root code
        descendant_codes: Set of all descendant codes from the flat expansion
        emis_lookup: Cached SNOMED -> EMIS GUID mapping
        display_lookup: Cached code -> display name mapping
        inactive_lookup: Cached code -> inactive status mapping
        include_inactive: Include inactive concepts
        max_depth: Maximum tree depth to traverse
        max_api_calls: Maximum number of API calls to make
        max_nodes: Maximum number of descendant nodes to emit
        client_id: NHS Terminology Server client ID
        client_secret: NHS Terminology Server client secret
        progress_callback: Optional callback(status_message, current, total)

    Returns:
        LineageTraceResult with tree structure and metadata
    """
    service = get_expansion_service()
    credential_error = _ensure_credentials(service, client_id, client_secret)
    if credential_error:
        return LineageTraceResult(
            root_code=root_code,
            root_display=root_display,
            tree=None,
            flat_nodes=[],
            shared_lineage_codes=[],
            total_nodes=0,
            max_depth_reached=0,
            api_calls_made=0,
            error=credential_error,
        )

    if not service.client:
        return LineageTraceResult(
            root_code=root_code,
            root_display=root_display,
            tree=None,
            flat_nodes=[],
            shared_lineage_codes=[],
            total_nodes=0,
            max_depth_reached=0,
            api_calls_made=0,
            error="Terminology server client not configured.",
        )

    # Track which codes we've seen and their paths
    code_paths: Dict[str, List[str]] = {}  # code -> list of paths (for shared lineage)
    flat_nodes: List[LineageNode] = []
    api_calls = 0
    max_depth_reached = 0
    truncated = False
    truncation_reason: Optional[str] = None

    def build_subtree(
        parent_code: str,
        parent_display: str,
        current_path: str,
        depth: int,
    ) -> Optional[LineageNode]:
        nonlocal api_calls, max_depth_reached
        nonlocal truncated, truncation_reason

        if depth > max_depth:
            truncated = True
            truncation_reason = (
                truncation_reason
                or f"Depth cap reached ({max_depth}) for {root_code}"
            )
            return None
        if api_calls >= max_api_calls:
            truncated = True
            truncation_reason = (
                truncation_reason
                or f"API call cap reached ({max_api_calls}) for {root_code}"
            )
            return None
        if max_nodes is not None and len(flat_nodes) >= max_nodes:
            truncated = True
            truncation_reason = (
                truncation_reason
                or f"Node cap reached ({max_nodes}) for {root_code}"
            )
            return None

        max_depth_reached = max(max_depth_reached, depth)

        # Get direct children of this code
        if progress_callback:
            progress_callback(f"Tracing children of {parent_code}...", api_calls, max_api_calls)

        children_result, error = service.client.get_direct_children(
            parent_code,
            include_inactive=include_inactive
        )
        api_calls += 1

        if error:
            # Non-fatal - just means no children at this level
            return None

        # Filter to only codes in our descendant set
        relevant_children = [
            c for c in children_result
            if c.code in descendant_codes
        ]

        if not relevant_children:
            return None

        child_nodes = []
        for child in relevant_children:
            if max_nodes is not None and len(flat_nodes) >= max_nodes:
                truncated = True
                truncation_reason = (
                    truncation_reason
                    or f"Node cap reached ({max_nodes}) for {root_code}"
                )
                break

            child_code = child.code
            child_display = display_lookup.get(child_code, child.display)
            child_path = f"{current_path} > {child_display}"

            # Track paths for shared lineage detection
            if child_code not in code_paths:
                code_paths[child_code] = []
            code_paths[child_code].append(child_path)

            # Create node
            node = LineageNode(
                code=child_code,
                display=child_display,
                emis_guid=emis_lookup.get(child_code),
                inactive=inactive_lookup.get(child_code, child.inactive),
                depth=depth,
                direct_parent_code=parent_code,
                lineage_path=child_path,
                shared_lineage=False,  # Will update later
                all_paths=None,
                children=None,
            )

            # Recursively build subtree
            if api_calls < max_api_calls and depth < max_depth and not truncated:
                sub_result = build_subtree(child_code, child_display, child_path, depth + 1)
                if sub_result and sub_result.children:
                    node.children = sub_result.children

            flat_nodes.append(node)
            child_nodes.append(node)

        if child_nodes:
            # Create a container node for the children
            return LineageNode(
                code=parent_code,
                display=parent_display,
                emis_guid=emis_lookup.get(parent_code),
                inactive=inactive_lookup.get(parent_code, False),
                depth=depth - 1 if depth > 0 else 0,
                direct_parent_code=None,
                lineage_path=current_path,
                children=child_nodes,
            )
        return None

    # Build tree starting from root
    root_path = root_display
    root_tree = build_subtree(root_code, root_display, root_path, 1)

    # Create root node
    root_node = LineageNode(
        code=root_code,
        display=root_display,
        emis_guid=emis_lookup.get(root_code),
        inactive=inactive_lookup.get(root_code, False),
        depth=0,
        direct_parent_code=None,
        lineage_path=root_display,
        children=root_tree.children if root_tree else None,
    )

    # Identify shared lineage codes
    shared_lineage_codes = [
        code for code, paths in code_paths.items()
        if len(paths) > 1
    ]

    # Update nodes with shared lineage info
    for node in flat_nodes:
        if node.code in shared_lineage_codes:
            node.shared_lineage = True
            node.all_paths = code_paths.get(node.code, [])

    covered_codes = {n.code for n in flat_nodes}
    missing_descendants = descendant_codes - covered_codes
    if (
        missing_descendants
        and not truncated
        and max_depth_reached >= max_depth
    ):
        truncated = True
        truncation_reason = (
            f"Depth cap reached ({max_depth}) for {root_code}; "
            f"{len(missing_descendants)} descendant(s) omitted"
        )

    return LineageTraceResult(
        root_code=root_code,
        root_display=root_display,
        tree=root_node,
        flat_nodes=flat_nodes,
        shared_lineage_codes=shared_lineage_codes,
        total_nodes=len(flat_nodes),
        max_depth_reached=max_depth_reached,
        api_calls_made=api_calls,
        truncated=truncated,
        truncation_reason=truncation_reason,
    )


def trace_lineage_for_expansion(
    expansion_result,
    parent_code: str,
    include_inactive: bool = False,
    max_depth: int = 10,
    max_api_calls: int = 100,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> LineageTraceResult:
    """
    Convenience function to trace lineage for a specific parent from expansion results.

    Uses cached data from the expansion to avoid redundant lookups.
    """
    # Extract data for this parent from the expansion
    parent_display = ""
    descendant_codes = set()
    emis_lookup = {}
    display_lookup = {}
    inactive_lookup = {}

    for row in expansion_result.processed_children:
        if row.get("Parent Code") == parent_code:
            if not parent_display:
                parent_display = row.get("Parent Display", parent_code)

            child_code = row.get("Child Code")
            if child_code:
                descendant_codes.add(child_code)
                emis_lookup[child_code] = row.get("EMIS GUID")
                display_lookup[child_code] = row.get("Child Display", "")
                inactive_lookup[child_code] = _is_inactive(row.get("Inactive"))

    if not descendant_codes:
        return LineageTraceResult(
            root_code=parent_code,
            root_display=parent_display or parent_code,
            tree=None,
            flat_nodes=[],
            shared_lineage_codes=[],
            total_nodes=0,
            max_depth_reached=0,
            api_calls_made=0,
            error="No descendants found for this parent code.",
        )

    return trace_lineage(
        root_code=parent_code,
        root_display=parent_display or parent_code,
        descendant_codes=descendant_codes,
        emis_lookup=emis_lookup,
        display_lookup=display_lookup,
        inactive_lookup=inactive_lookup,
        include_inactive=include_inactive,
        max_depth=max_depth,
        max_api_calls=max_api_calls,
        client_id=client_id,
        client_secret=client_secret,
        progress_callback=progress_callback,
    )


def trace_full_lineage(
    processed_children: List[Dict[str, Any]],
    include_inactive: bool = False,
    max_depth: int = 10,
    max_depth_per_parent: Optional[Dict[str, int]] = None,
    max_api_calls_per_parent: int = 50,
    max_nodes_per_parent: Optional[int] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> FullLineageTraceResult:
    """
    Trace lineage for ALL parent codes in expansion results.

    Builds a combined tree with all XML parent codes as roots and their
    descendants organised by SNOMED lineage.

    Args:
        processed_children: Child rows from expansion (with Parent Code, Child Code, etc.)
        include_inactive: Include inactive concepts
        max_depth: Maximum tree depth per parent
        max_depth_per_parent: Optional per-parent depth limits
        max_api_calls_per_parent: API call limit per parent (controls cost)
        max_nodes_per_parent: Optional node cap per parent tree
        client_id: NHS Terminology Server client ID
        client_secret: NHS Terminology Server client secret
        progress_callback: Optional callback(message, current, total)

    Returns:
        FullLineageTraceResult with combined trees
    """
    service = get_expansion_service()
    credential_error = _ensure_credentials(service, client_id, client_secret)
    if credential_error:
        return FullLineageTraceResult(
            trees=[],
            total_nodes=0,
            max_depth_reached=0,
            total_api_calls=0,
            shared_lineage_codes=[],
            parent_count=0,
            errors=[],
            error=credential_error,
        )

    # Build lookups from all processed children
    parent_codes = sorted(set(
        row.get("Parent Code") for row in processed_children
        if row.get("Parent Code")
    ))

    if not parent_codes:
        return FullLineageTraceResult(
            trees=[],
            total_nodes=0,
            max_depth_reached=0,
            total_api_calls=0,
            shared_lineage_codes=[],
            parent_count=0,
            errors=[],
            error="No parent codes found in expansion results.",
        )

    # Build global lookups
    emis_lookup = {}
    display_lookup = {}
    inactive_lookup = {}
    parent_display_lookup = {}

    for row in processed_children:
        parent_code = row.get("Parent Code")
        child_code = row.get("Child Code")

        if parent_code and not parent_display_lookup.get(parent_code):
            parent_display_lookup[parent_code] = row.get("Parent Display", parent_code)

        if child_code:
            emis_lookup[str(child_code)] = row.get("EMIS GUID")
            display_lookup[str(child_code)] = row.get("Child Display", "")
            inactive_lookup[str(child_code)] = _is_inactive(row.get("Inactive"))

    # Trace lineage for each parent
    all_trees = []
    total_nodes = 0
    max_depth_reached = 0
    total_api_calls = 0
    all_shared_codes = set()
    errors = []
    truncated_parent_codes: List[str] = []
    truncation_reasons: Dict[str, str] = {}

    total_parents = len(parent_codes)
    for idx, parent_code in enumerate(parent_codes):
        if progress_callback:
            progress_callback(
                f"Tracing parent {idx + 1}/{total_parents}: {parent_code}...",
                idx,
                total_parents
            )

        # Get descendants for this specific parent
        parent_descendants = set(
            str(row.get("Child Code"))
            for row in processed_children
            if row.get("Parent Code") == parent_code and row.get("Child Code")
        )

        if not parent_descendants:
            continue

        parent_depth_limit = max_depth
        if max_depth_per_parent is not None:
            parent_depth_limit = max_depth_per_parent.get(parent_code, max_depth)
        parent_depth_limit = max(1, int(parent_depth_limit))

        result = trace_lineage(
            root_code=parent_code,
            root_display=parent_display_lookup.get(parent_code, parent_code),
            descendant_codes=parent_descendants,
            emis_lookup=emis_lookup,
            display_lookup=display_lookup,
            inactive_lookup=inactive_lookup,
            include_inactive=include_inactive,
            max_depth=parent_depth_limit,
            max_api_calls=max_api_calls_per_parent,
            max_nodes=max_nodes_per_parent,
            client_id=client_id,
            client_secret=client_secret,
        )

        if result.error:
            errors.append(f"{parent_code}: {result.error}")
        elif result.tree:
            all_trees.append(result.tree)
            total_nodes += result.total_nodes
            max_depth_reached = max(max_depth_reached, result.max_depth_reached)
            total_api_calls += result.api_calls_made
            all_shared_codes.update(result.shared_lineage_codes)
            if result.truncated:
                truncated_parent_codes.append(parent_code)
                truncation_reasons[parent_code] = (
                    result.truncation_reason or "Hierarchy was truncated"
                )

    if progress_callback:
        progress_callback("Complete", total_parents, total_parents)

    return FullLineageTraceResult(
        trees=all_trees,
        total_nodes=total_nodes,
        max_depth_reached=max_depth_reached,
        total_api_calls=total_api_calls,
        shared_lineage_codes=list(all_shared_codes),
        parent_count=len(all_trees),
        errors=errors,
        truncated_parent_codes=truncated_parent_codes,
        truncation_reasons=truncation_reasons,
    )
