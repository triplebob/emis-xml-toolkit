"""
Metadata provider for UI tabs using the parsing pipeline.
Currently focuses on searches: folder hierarchy, dependency graph, and criteria summaries.
"""

from typing import Dict, Any, List, Tuple
import streamlit as st
from ....system.session_state import SessionStateKeys


def _folder_map(folders: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {f.get("id"): f for f in folders if f.get("id")}


def _build_folder_tree(folders: List[Dict[str, Any]], unassigned_searches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build a lightweight folder tree (id, name, children, report counts).
    """
    fmap = _folder_map(folders)
    for folder in fmap.values():
        folder.setdefault("children", [])
        folder.setdefault("searches", [])
    # attach children
    for folder in fmap.values():
        parent_id = folder.get("parent_id")
        if parent_id and parent_id in fmap:
            fmap[parent_id].setdefault("children", []).append(folder)
    roots = [f for f in fmap.values() if not f.get("parent_id") or f.get("parent_id") not in fmap]
    if unassigned_searches:
        roots.append(
            {
                "id": "__unassigned__",
                "name": "Unassigned",
                "children": [],
                "searches": unassigned_searches,
                "path": ["Unassigned"],
            }
        )
    return {
        "roots": roots,
        "total_folders": len(fmap),
    }


def _build_folder_paths(folders: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    fmap = _folder_map(folders)
    paths: Dict[str, List[str]] = {}
    for fid in fmap:
        path: List[str] = []
        current = fmap.get(fid)
        while current:
            name = current.get("name") or current.get("id") or ""
            path.insert(0, name)
            parent_id = current.get("parent_id")
            current = fmap.get(parent_id) if parent_id else None
        paths[fid] = path
    return paths


def _extract_search_entities() -> List[Dict[str, Any]]:
    entities = st.session_state.get(SessionStateKeys.PIPELINE_ENTITIES) or []
    searches = []
    seen_ids = set()

    for ent in entities:
        flags = ent.get("flags", {}) or {}
        etype = flags.get("element_type") or flags.get("source_type")
        if etype != "search":
            continue

        search_id = flags.get("element_id") or ""
        if not search_id or search_id in seen_ids:
            continue

        seen_ids.add(search_id)
        searches.append(
            {
                "id": search_id,
                "name": flags.get("display_name") or "",
                "description": flags.get("description") or "",
                "folder_id": flags.get("folder_id") or "",
                "parent_guid": flags.get("parent_search_guid") or "",
                "dependencies": ent.get("dependencies") or [],
                "criteria_groups": ent.get("criteria_groups") or [],
                "raw_flags": flags,
                "source_type": etype,
            }
        )
    return searches


def _extract_report_entities() -> List[Dict[str, Any]]:
    entities = st.session_state.get(SessionStateKeys.PIPELINE_ENTITIES) or []
    reports = []
    seen_ids = set()

    for ent in entities:
        flags = ent.get("flags", {}) or {}
        etype = flags.get("element_type") or flags.get("source_type")
        if etype not in {"list_report", "audit_report", "aggregate_report"}:
            continue

        report_id = flags.get("element_id") or ""
        if not report_id or report_id in seen_ids:
            continue

        seen_ids.add(report_id)
        reports.append(
            {
                "id": report_id,
                "name": flags.get("display_name") or "",
                "description": flags.get("description") or "",
                "folder_id": flags.get("folder_id") or "",
                "parent_guid": flags.get("parent_search_guid") or "",
                "type": etype,
                "raw_flags": flags,
                "source_type": etype,
            }
        )
    return reports


def _build_dependency_graph(searches: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    graph: Dict[str, List[str]] = {}
    for s in searches:
        sid = s.get("id")
        deps = s.get("dependencies") or []
        if not sid:
            continue
        graph[sid] = deps
    return graph


def _build_dependents(graph: Dict[str, List[str]]) -> Dict[str, List[str]]:
    dependents: Dict[str, List[str]] = {}
    for src, targets in graph.items():
        for tgt in targets:
            dependents.setdefault(tgt, []).append(src)
    return dependents


def _attach_searches_to_folders(searches: List[Dict[str, Any]], folders: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Attach search references to folders and return unassigned list."""
    fmap = _folder_map(folders)
    unassigned: List[Dict[str, Any]] = []
    seen_in_folders: Dict[str, set] = {}

    for s in searches:
        fid = s.get("folder_id")
        sid = s.get("id")
        if not sid:
            continue

        ref = {"id": sid, "name": s.get("name")}

        if fid and fid in fmap:
            if fid not in seen_in_folders:
                seen_in_folders[fid] = set()

            if sid not in seen_in_folders[fid]:
                fmap[fid].setdefault("searches", []).append(ref)
                seen_in_folders[fid].add(sid)
        else:
            if not any(u.get("id") == sid for u in unassigned):
                unassigned.append(ref)
    return folders, unassigned


def _attach_reports_to_folders(reports: List[Dict[str, Any]], folders: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Attach report references to folders and return unassigned list."""
    fmap = _folder_map(folders)
    unassigned: List[Dict[str, Any]] = []
    seen: set = set()
    for r in reports:
        rid = r.get("id")
        if not rid:
            continue
        if rid in seen:
            continue
        seen.add(rid)
        fid = r.get("folder_id")
        ref = {"id": rid, "name": r.get("name"), "type": r.get("type"), "source_type": r.get("source_type")}
        if fid and fid in fmap:
            fmap[fid].setdefault("reports", []).append(ref)
        else:
            unassigned.append(ref)
    return folders, unassigned


def get_search_metadata() -> Dict[str, Any]:
    """
    Return search-focused metadata for UI tabs.
    """
    searches = _extract_search_entities()
    reports = _extract_report_entities()
    folders = st.session_state.get(SessionStateKeys.PIPELINE_FOLDERS) or []

    folders, unassigned_searches = _attach_searches_to_folders(searches, folders)
    folders, unassigned_reports = _attach_reports_to_folders(reports, folders)

    folder_tree = _build_folder_tree(folders, unassigned_searches)
    folder_paths = _build_folder_paths(folders)

    dependency_graph = _build_dependency_graph(searches)
    dependents = _build_dependents(dependency_graph)

    return {
        "searches": searches,
        "reports": reports,
        "folders": folders,
        "folder_tree": folder_tree,
        "folder_paths": folder_paths,
        "dependency_graph": dependency_graph,
        "dependents": dependents,
        "unassigned_reports": unassigned_reports,
        "unassigned_searches": unassigned_searches,
    }
