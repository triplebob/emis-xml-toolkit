"""
StructureEnricher: builds folder trees and enriches parsed structure metadata for UI consumption.
"""

from typing import Dict, Any, List, Set


def _pretty_type(raw: str) -> str:
    if not raw:
        return ""
    return raw.replace("_", " ").title()


class StructureEnricher:
    def __init__(self, structure_data: Dict[str, Any]):
        self.folders = structure_data.get("folders") or []
        self.entities = structure_data.get("entities") or []
        self.id_to_entity = {e.get("id"): e for e in self.entities if e.get("id")}
        self._folder_map = {f.get("id"): f for f in self.folders if f.get("id")}

    def id_to_name(self) -> Dict[str, str]:
        return {eid: (ent.get("name") or eid) for eid, ent in self.id_to_entity.items()}

    def folder_paths(self) -> Dict[str, List[str]]:
        """Build breadcrumb paths for folders."""
        paths: Dict[str, List[str]] = {}
        for fid, folder in self._folder_map.items():
            path: List[str] = []
            current = folder
            while current:
                label = current.get("name") or current.get("id") or ""
                if label:
                    path.insert(0, label)
                parent_id = current.get("parent_id")
                current = self._folder_map.get(parent_id) if parent_id else None
            paths[fid] = path
        return paths

    def get_searches(self) -> List[Dict[str, Any]]:
        return [e for e in self.entities if e.get("source_type") == "search"]

    def get_reports(self) -> List[Dict[str, Any]]:
        return [e for e in self.entities if e.get("source_type") in {"list_report", "audit_report", "aggregate_report"}]

    def dependency_graph(self) -> Dict[str, List[str]]:
        """Combined dependency graph (searches + reports)."""
        graph: Dict[str, List[str]] = {}
        # Searches
        for ent in self.get_searches():
            eid = ent.get("id")
            if not eid:
                continue
            deps = []
            parent_guid = ent.get("parent_guid")
            if parent_guid:
                deps.append(parent_guid)
            deps.extend(ent.get("dependencies") or [])
            # Only add to graph if there are actual dependencies
            if deps:
                graph[eid] = list(dict.fromkeys(deps))
        # Reports
        for rep in self.get_reports():
            rid = rep.get("id")
            if not rid:
                continue
            deps = rep.get("dependencies") or []
            parent = rep.get("parent_guid")
            if parent:
                deps = [parent] + deps
            # Only add to graph if there are actual dependencies
            if deps:
                graph[rid] = list(dict.fromkeys(deps))
        return graph

    def dependents(self) -> Dict[str, List[str]]:
        deps = self.dependency_graph()
        rev: Dict[str, List[str]] = {}
        for src, targets in deps.items():
            for tgt in targets:
                rev.setdefault(tgt, []).append(src)
        return rev

    def folder_tree(self) -> Dict[str, Any]:
        fmap = {f.get("id"): dict(f, children=[], searches=[], reports=[]) for f in self.folders if f.get("id")}
        # attach children
        for fid, folder in fmap.items():
            parent = folder.get("parent_id")
            if parent and parent in fmap:
                fmap[parent]["children"].append(folder)

        # Build search lookup within folder
        for s in self.get_searches():
            fid = s.get("folder_id")
            node = fmap.get(fid)
            if node is not None:
                node["searches"].append(
                    {
                        "id": s.get("id"),
                        "name": s.get("name"),
                        "type_label": _pretty_type(s.get("source_type") or "search"),
                        "parent_guid": s.get("parent_guid"),
                        "folder_id": fid,
                        "dependencies": s.get("dependencies") or [],
                        "reports": [],
                        "children": [],
                    }
                )

        # Map search id to search ref to attach reports
        search_ref_map: Dict[str, Dict[str, Any]] = {}
        for folder in fmap.values():
            for sref in folder.get("searches") or []:
                if sref.get("id"):
                    search_ref_map[sref["id"]] = sref

        # attach reports: nest under parent if in same folder; otherwise show at folder level
        for r in self.get_reports():
            fid = r.get("folder_id")
            node = fmap.get(fid)
            label = _pretty_type(r.get("source_type"))
            report_ref = {
                "id": r.get("id"),
                "name": r.get("name"),
                "type_label": label,
                "parent_guid": r.get("parent_guid"),
                "folder_id": fid,
            }
            parent_guid = r.get("parent_guid")
            deps = r.get("dependencies") or []
            target_search = None
            if parent_guid and parent_guid in search_ref_map:
                target_search = search_ref_map[parent_guid]
            else:
                for d in deps:
                    if d in search_ref_map:
                        target_search = search_ref_map[d]
                        break

            # Check if parent search is in the same folder
            parent_in_same_folder = False
            if target_search is not None:
                parent_folder_id = target_search.get("folder_id")
                if parent_folder_id == fid:
                    parent_in_same_folder = True

            # Add to folder-level ONLY if no parent OR parent in different folder
            if node is not None and not parent_in_same_folder:
                existing = {rep.get("id") for rep in node.get("reports", [])}
                if not node.get("reports"):
                    node["reports"] = []
                if report_ref["id"] not in existing:
                    node["reports"].append(report_ref)

            # Nest under parent search when applicable
            if target_search is not None:
                target_search.setdefault("reports", [])
                if report_ref not in target_search["reports"]:
                    target_search["reports"].append(report_ref)

        roots = [f for f in fmap.values() if not f.get("parent_id") or f.get("parent_id") not in fmap]

        def _unassigned_searches():
            out = []
            for s in self.get_searches():
                if s.get("folder_id") not in fmap:
                    out.append(
                        {
                            "id": s.get("id"),
                            "name": s.get("name"),
                            "type_label": _pretty_type(s.get("source_type") or "search"),
                            "parent_guid": s.get("parent_guid"),
                            "dependencies": s.get("dependencies") or [],
                            "reports": [],
                            "children": [],
                        }
                    )
            return out

        def _unassigned_reports():
            out = []
            for r in self.get_reports():
                if r.get("folder_id") not in fmap and not (r.get("parent_guid") and r.get("parent_guid") in search_ref_map):
                    out.append({"id": r.get("id"), "name": r.get("name"), "type_label": _pretty_type(r.get("source_type"))})
            return out

        unassigned_searches = _unassigned_searches()
        unassigned_reports = _unassigned_reports()
        if unassigned_searches or unassigned_reports:
            roots.insert(
                0,
                {
                    "id": "__root__",
                    "name": "Root",
                    "children": [],
                    "searches": unassigned_searches,
                    "reports": unassigned_reports,
                },
            )

        # Nest searches under parent searches within the same folder
        def _nest_searches(searches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            """Nest searches under parents within the same collection using parent_guid or dependencies."""
            if not searches:
                return searches
            id_to_search = {s.get("id"): s for s in searches if s.get("id")}
            to_remove: Set[str] = set()
            for s in searches:
                pid = s.get("parent_guid")
                if not pid:
                    # Fall back to first dependency that exists locally
                    for dep in s.get("dependencies") or []:
                        if dep in id_to_search:
                            pid = dep
                            break
                if pid and pid in id_to_search:
                    parent = id_to_search[pid]
                    parent.setdefault("children", []).append(s)
                    to_remove.add(s.get("id"))
            return [s for s in searches if s.get("id") not in to_remove]

        for folder in fmap.values():
            folder["searches"] = _nest_searches(folder.get("searches", []))

        # Also nest searches inside the synthetic root node (unassigned) if present
        for root in roots:
            root["searches"] = _nest_searches(root.get("searches", []))

        return {"roots": roots, "total_folders": len(fmap)}

    def enrich_searches(self) -> List[Dict[str, Any]]:
        id_lookup = self.id_to_name()
        folder_paths = self.folder_paths()
        deps = self.dependency_graph()
        dependents = self.dependents()
        enriched = []
        for s in self.get_searches():
            sid = s.get("id")
            dep_ids = deps.get(sid, [])
            dep_names = [id_lookup.get(d, d) for d in dep_ids]
            depd_ids = dependents.get(sid, [])
            depd_names = [id_lookup.get(d, d) for d in depd_ids]
            enriched.append(
                {
                    **s,
                    "dependency_names": dep_names,
                    "dependents": depd_ids,
                    "dependent_names": depd_names,
                    "folder_path": folder_paths.get(s.get("folder_id"), []),
                    "type_label": _pretty_type(s.get("source_type")),
                }
            )
        return enriched

    def enrich_reports(self) -> List[Dict[str, Any]]:
        id_lookup = self.id_to_name()
        folder_paths = self.folder_paths()
        deps = self.dependency_graph()
        dependents = self.dependents()
        enriched = []
        for r in self.get_reports():
            rid = r.get("id")
            dep_ids = deps.get(rid, [])
            dep_names = [id_lookup.get(d, d) for d in dep_ids]
            depd_ids = dependents.get(rid, [])
            depd_names = [id_lookup.get(d, d) for d in depd_ids]
            enriched.append(
                {
                    **r,
                    "dependency_names": dep_names,
                    "dependents": depd_ids,
                    "dependent_names": depd_names,
                    "folder_path": folder_paths.get(r.get("folder_id"), []),
                    "type_label": _pretty_type(r.get("source_type")),
                }
            )
        return enriched
