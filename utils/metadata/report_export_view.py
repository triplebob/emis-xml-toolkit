"""
Build a report export view that mirrors the report UI content.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .description_generators import format_base_population
from .report_filtering import (
    build_aggregate_criteria_groups,
    build_audit_criteria_overview,
    build_report_filter_items,
    describe_group_criteria,
    has_embedded_report_code_rules,
    split_report_value_sets,
)
from ..parsing.node_parsers.linked_criteria_parser import get_temporal_relationship_description


def build_report_export_view(report: Dict[str, Any], id_to_name: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    report = report or {}
    report_type = _normalise_report_type(report.get("type") or report.get("type_label") or "")
    view: Dict[str, Any] = {
        "overview": _build_overview(report, id_to_name),
        "population": _build_population(report, id_to_name),
        "type": report_type,
        "name": report.get("name") or "",
        "id": report.get("id") or "",
    }

    if report_type == "list":
        view["list"] = _build_list_view(report)
    elif report_type == "audit":
        view["audit"] = _build_audit_view(report, id_to_name)
    elif report_type == "aggregate":
        view["aggregate"] = _build_aggregate_view(report)
    else:
        fallback_criteria = report.get("report_criteria") or report.get("aggregate_criteria") or []
        view["criteria"] = _build_criteria_list(fallback_criteria)

    return view


def _normalise_report_type(raw_type: str) -> str:
    text = str(raw_type or "").lower()
    if "list" in text:
        return "list"
    if "audit" in text:
        return "audit"
    if "aggregate" in text:
        return "aggregate"
    return text or "unknown"


def _build_overview(report: Dict[str, Any], id_to_name: Optional[Dict[str, str]]) -> Dict[str, Any]:
    parent_guid = report.get("parent_guid") or ""
    parent_name = id_to_name.get(parent_guid) if id_to_name and parent_guid else ""
    return {
        "report_name": report.get("name") or "",
        "report_type": report.get("type_label") or report.get("type") or "",
        "report_guid": report.get("id") or "",
        "description": report.get("description") or "",
        "folder_path": " / ".join(report.get("folder_path") or []),
        "parent_guid": parent_guid,
        "parent_name": parent_name or "",
        "author": report.get("author") or "",
        "creation_time": report.get("creation_time") or "",
    }


def _build_population(report: Dict[str, Any], id_to_name: Optional[Dict[str, str]]) -> Dict[str, Any]:
    parent_guid = report.get("parent_guid") or ""
    parent_name = id_to_name.get(parent_guid) if id_to_name and parent_guid else ""
    if parent_guid:
        population_text = parent_name or parent_guid
        population_type = "parent_search"
    else:
        parent_type = (
            report.get("parent_type")
            or report.get("parentType")
            or (report.get("flags") or {}).get("parent_type")
            or (report.get("flags") or {}).get("parentType")
        )
        population_text = format_base_population(parent_type)
        population_type = "base_population"
    return {
        "population_type": population_type,
        "population_text": population_text,
        "parent_guid": parent_guid,
        "parent_name": parent_name or "",
        "parent_type": report.get("parent_type") or report.get("parentType") or "",
    }


def _build_list_view(report: Dict[str, Any]) -> Dict[str, Any]:
    column_groups = report.get("column_groups") or []
    group_views: List[Dict[str, Any]] = []
    for idx, group in enumerate(column_groups, start=1):
        group_criteria = group.get("criteria") or []
        criteria_summary = group.get("criteria_summary")
        if not isinstance(criteria_summary, dict):
            criteria_summary = {"label": criteria_summary} if criteria_summary else {}
        if not criteria_summary and group_criteria:
            criteria_summary = {"label": describe_group_criteria(group_criteria)}
        group_views.append(
            {
                "group_index": idx,
                "display_name": group.get("display_name") or "",
                "logical_table": group.get("logical_table") or "",
                "table_type": group.get("table_type") or "",
                "columns": [
                    {"display_name": col.get("display_name") or "", "column": col.get("column") or ""}
                    for col in (group.get("columns") or [])
                ],
                "sort_configuration": group.get("sort_configuration") or {},
                "criteria_summary": criteria_summary,
                "criteria": _build_criteria_list(group_criteria),
            }
        )
    report_criteria = report.get("report_criteria") or []
    return {
        "column_groups": group_views,
        "report_criteria": _build_criteria_list(report_criteria),
    }


def _build_audit_view(report: Dict[str, Any], id_to_name: Optional[Dict[str, str]]) -> Dict[str, Any]:
    criteria = report.get("report_criteria") or []
    overview = build_audit_criteria_overview(criteria)
    population_refs = report.get("population_references") or []
    member_searches = [
        {"id": ref, "name": id_to_name.get(ref) if id_to_name else ""} for ref in population_refs
    ]
    return {
        "aggregate": report.get("aggregate") or {},
        "member_searches": member_searches,
        "additional_criteria": {
            "title": overview.get("title") or "",
            "summary": overview.get("summary") or "",
            "criteria": _build_criteria_list(overview.get("criteria") or []),
        },
    }


def _build_aggregate_view(report: Dict[str, Any]) -> Dict[str, Any]:
    criteria = report.get("aggregate_criteria") or []
    groups = build_aggregate_criteria_groups(criteria)
    criteria_groups = []
    for group in groups:
        criteria_groups.append(
            {
                "title": group.get("title") or "",
                "operator": group.get("operator") or "",
                "criteria": _build_criteria_list(group.get("criteria") or []),
            }
        )
    return {
        "aggregate": report.get("aggregate") or {},
        "built_in_criteria": criteria_groups,
        "has_embedded_report_code_rules": has_embedded_report_code_rules(criteria),
    }


def _build_criteria_list(criteria: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_build_criterion_view(criterion) for criterion in (criteria or [])]


def _build_criterion_view(criterion: Dict[str, Any]) -> Dict[str, Any]:
    flags = criterion.get("flags") or {}
    clinical_value_sets, emisinternal_value_sets = split_report_value_sets(criterion)
    filters = build_report_filter_items(criterion, clinical_value_sets, emisinternal_value_sets)
    return {
        "display_name": flags.get("display_name") or criterion.get("display_name") or "",
        "table": flags.get("logical_table_name") or criterion.get("table") or "",
        "action": "Exclude" if flags.get("negation") else "Include",
        "negation": bool(flags.get("negation")),
        "clinical_code_count": len(clinical_value_sets),
        "clinical_codes": _build_value_set_entries(clinical_value_sets),
        "filters": filters,
        "linked_criteria": _build_linked_criteria_view(criterion),
    }


def _build_linked_criteria_view(criterion: Dict[str, Any]) -> List[Dict[str, Any]]:
    linked_items = criterion.get("linked_criteria") or (criterion.get("flags") or {}).get("linked_criteria") or []
    output: List[Dict[str, Any]] = []
    for linked in linked_items:
        relationship = linked.get("relationship") or {}
        child = linked.get("criterion") or {}
        parent_col_display = relationship.get("parent_column_display_name") or relationship.get("parent_column") or "the field"
        child_col_display = relationship.get("child_column_display_name") or relationship.get("child_column") or "the linked field"
        temporal_desc = get_temporal_relationship_description(relationship)
        if temporal_desc:
            description = (
                f"{parent_col_display} is {temporal_desc} {child_col_display} from the above feature and where:"
            )
        else:
            description = f"{parent_col_display} is equal to the {child_col_display} from the above feature and where:"
        output.append(
            {
                "relationship_text": description,
                "relationship": relationship,
                "criterion": _build_criterion_view(child) if child else {},
            }
        )
    return output


def _build_value_set_entries(value_sets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    entries = []
    for entry in value_sets or []:
        pseudo_member = entry.get("is_pseudomember")
        if pseudo_member is None:
            pseudo_member = entry.get("is_pseudo_member")
        if pseudo_member is None:
            pseudo_member = entry.get("is_pseudo_refset_member")
        entries.append(
            {
                "code_system": entry.get("code_system") or "",
                "code": entry.get("code_value") or "",
                "display_name": entry.get("display_name") or entry.get("valueSet_description") or "",
                "value_set_name": entry.get("valueSet_description") or "",
                "value_set_guid": entry.get("valueSet_guid") or entry.get("value_set_guid") or entry.get("id") or "",
                "include_children": bool(entry.get("include_children")),
                "is_refset": bool(entry.get("is_refset")),
                "pseudo_refset_member": bool(pseudo_member),
                "inactive": bool(entry.get("inactive")),
                "is_library_item": bool(entry.get("is_library_item")),
            }
        )
    return entries
