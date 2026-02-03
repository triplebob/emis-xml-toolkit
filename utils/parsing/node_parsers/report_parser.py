"""
Report parser for list/audit/aggregate reports (structural flags + criteria).
Supports early deduplication via CodeStore for performance optimisation.
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Tuple, Optional, TYPE_CHECKING
from ...pattern_plugins.registry import pattern_registry
from ...pattern_plugins.base import PatternContext
from ...metadata.flag_mapper import map_element_flags
from .criterion_parser import parse_criterion
from ..namespace_utils import findall_ns, find_ns, get_text_ns

if TYPE_CHECKING:
    from ...caching.code_store import CodeStore


def parse_report(
    report_elem: ET.Element,
    namespaces: Dict[str, str],
    report_type: str,
    code_store: "CodeStore",
) -> Dict[str, Any]:
    pattern_registry.load_all_modules("utils.pattern_plugins")
    pattern_results = pattern_registry.run_all(PatternContext(element=report_elem, namespaces=namespaces, path=report_elem.tag))
    flags = map_element_flags(report_elem, namespaces, pattern_results)
    flags["element_type"] = report_type
    if not flags.get("element_id"):
        rid = report_elem.get("id")
        if rid:
            flags["element_id"] = rid

    name = get_text_ns(report_elem, "name", namespaces)
    desc = get_text_ns(report_elem, "description", namespaces)
    folder_id = get_text_ns(report_elem, "folder", namespaces)
    search_date = get_text_ns(report_elem, "searchDate", namespaces)
    creation_time = get_text_ns(report_elem, "creationTime", namespaces)
    if folder_id:
        flags["folder_id"] = folder_id
    if search_date:
        flags["search_date"] = search_date
    if creation_time:
        flags["report_creation_time"] = creation_time
    parent = find_ns(report_elem, "parent", namespaces)
    if parent is not None:
        parent_type = parent.get("parentType") or parent.get("parent_type")
        if parent_type:
            flags["parent_type"] = parent_type
        search_identifier = find_ns(parent, "SearchIdentifier", namespaces)
        if search_identifier is not None:
            parent_guid = search_identifier.get("reportGuid")
            if parent_guid:
                flags["parent_search_guid"] = parent_guid

    if name:
        flags["display_name"] = name
        flags["source_name"] = name
    if desc:
        flags["description"] = desc
    if flags.get("element_id"):
        flags["source_guid"] = flags["element_id"]

    author_elem = find_ns(report_elem, "author", namespaces)
    if author_elem is not None:
        author_name = get_text_ns(author_elem, "authorName", namespaces)
        user_in_role = get_text_ns(author_elem, "userInRole", namespaces)
        if author_name:
            flags["report_author_name"] = author_name
        if user_in_role:
            flags["report_author_user_id"] = user_in_role

    aggregate_criteria_flags: List[Dict[str, Any]] = []
    report_criteria_flags: List[Dict[str, Any]] = []
    column_groups: List[Dict[str, Any]] = []
    aggregate_info: Optional[Dict[str, Any]] = None

    if report_type == "list_report":
        list_report_elem = find_ns(report_elem, "listReport", namespaces)
        if list_report_elem is None:
            list_report_elem = report_elem
        column_groups, group_criteria = _parse_list_report(list_report_elem, namespaces, parent_flags=flags, code_store=code_store)
        direct_criteria = _parse_direct_criteria(
            list_report_elem,
            namespaces,
            parent_ctx={
                "container_type": "Report Main Criteria",
                "source_name": name,
                "source_guid": flags.get("element_id"),
                "source_type": report_type,
            },
            code_store=code_store,
        )
        report_criteria_flags.extend(direct_criteria)
    elif report_type == "audit_report":
        audit_elem = find_ns(report_elem, "auditReport", namespaces)
        if audit_elem is None:
            audit_elem = report_elem
        population_refs = _parse_population_references(audit_elem, namespaces)
        if population_refs:
            flags["population_reference_guid"] = population_refs
        aggregate_info, aggregate_criteria = _parse_custom_aggregate(audit_elem, namespaces, code_store=code_store)
        if aggregate_info:
            aggregate_info["type"] = "audit_custom_aggregate"
        if aggregate_criteria:
            aggregate_criteria_flags.extend(aggregate_criteria)
        direct_criteria = _parse_direct_criteria(audit_elem, namespaces, code_store=code_store)
        report_criteria_flags.extend(direct_criteria)
    elif report_type == "aggregate_report":
        aggregate_elem = find_ns(report_elem, "aggregateReport", namespaces)
        if aggregate_elem is None:
            aggregate_elem = report_elem
        aggregate_info, aggregate_criteria = _parse_aggregate_report(aggregate_elem, namespaces, code_store=code_store)
        if aggregate_info is not None and "type" not in aggregate_info:
            aggregate_info["type"] = report_type
        if aggregate_criteria:
            aggregate_criteria_flags.extend(aggregate_criteria)
    else:
        report_criteria_flags.extend(_parse_direct_criteria(report_elem, namespaces, code_store=code_store))

    result: Dict[str, Any] = {
        "id": flags.get("element_id") or report_elem.get("id") or "",
        "flags": flags,
    }
    if column_groups:
        result["column_groups"] = column_groups
    if aggregate_info:
        result["aggregate"] = aggregate_info
    if aggregate_criteria_flags:
        result["aggregate_criteria"] = aggregate_criteria_flags
    if report_criteria_flags:
        result["report_criteria"] = report_criteria_flags
    return result


def _parse_list_report(
    list_report_elem: ET.Element,
    namespaces: Dict[str, str],
    parent_flags: Dict[str, Any],
    code_store: Optional["CodeStore"] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    column_groups: List[Dict[str, Any]] = []
    criteria_flags: List[Dict[str, Any]] = []

    for column_group in findall_ns(list_report_elem, ".//columnGroup", namespaces):
        logical_table = get_text_ns(column_group, "logicalTableName", namespaces)
        group_data: Dict[str, Any] = {
            "id": column_group.get("id", ""),
            "logical_table": logical_table,
            "display_name": get_text_ns(column_group, "displayName", namespaces),
            "container_type": "Report Column Group",
            "source_name": get_text_ns(column_group, "displayName", namespaces) or parent_flags.get("source_name"),
            "source_guid": column_group.get("id", "") or parent_flags.get("source_guid", ""),
            "table_type": _classify_table_type(logical_table),
        }
        columns = _parse_list_columns(column_group, namespaces)
        if columns:
            group_data["columns"] = columns

        sort_config = _parse_sort_configuration(column_group, namespaces)
        if sort_config:
            group_data["sort_configuration"] = sort_config

        group_ctx = {
            "container_type": "Report Column Group",
            "source_name": group_data.get("display_name") or parent_flags.get("source_name"),
            "source_guid": group_data.get("id") or parent_flags.get("source_guid"),
            "source_type": parent_flags.get("element_type"),
        }
        group_criteria = _parse_direct_criteria(column_group, namespaces, parent_ctx=group_ctx, code_store=code_store)
        if group_criteria:
            group_data["criteria"] = group_criteria
            criteria_flags.extend(group_criteria)
            summary = _criteria_summary_from_restrictions(group_criteria)
            if summary:
                group_data["criteria_summary"] = summary

        column_groups.append(group_data)

    return column_groups, criteria_flags


def _parse_list_columns(column_group: ET.Element, namespaces: Dict[str, str]) -> List[Dict[str, Any]]:
    columnar = find_ns(column_group, "columnar", namespaces)
    if columnar is None:
        return []

    columns: List[Dict[str, Any]] = []
    for list_column in findall_ns(columnar, ".//listColumn", namespaces):
        column_name = get_text_ns(list_column, "column", namespaces)
        columns.append(
            {
                "id": list_column.get("id", ""),
                "column": column_name,
                "display_name": get_text_ns(list_column, "displayName", namespaces),
                "column_type": _classify_column_type(column_name),
                "is_enhanced_column": _is_enhanced_column(column_name),
            }
        )
    return columns


def _classify_table_type(logical_table: str) -> str:
    if not logical_table:
        return "unknown"
    table_upper = logical_table.upper()
    if "MEDICATION_COURSES" in table_upper:
        return "medication_courses"
    if "MEDICATION_ISSUES" in table_upper:
        return "medication_issues"
    if "PATIENT" in table_upper:
        return "patient"
    if "ORGANISATION" in table_upper or "ORGANISATION" in table_upper:
        return "organisation"
    return "standard"


def _classify_column_type(column_text: str) -> str:
    if not column_text:
        return "standard"
    column_upper = column_text.upper()
    if "AGE_AT_EVENT" in column_upper:
        return "age_at_event"
    if "ORGANISATION_TERM" in column_upper or "ORGANISATION_TERM" in column_upper:
        return "organisation"
    if "USUAL_GP" in column_upper:
        return "practitioner"
    if "COMMENCE_DATE" in column_upper or "LASTISSUE_DATE" in column_upper:
        return "medication_date"
    if "ASSOCIATEDTEXT" in column_upper:
        return "associated_text"
    if "QUANTITY_UNIT" in column_upper:
        return "quantity"
    return "standard"


def _is_enhanced_column(column_text: str) -> bool:
    if not column_text:
        return False
    enhanced_columns = [
        "ORGANISATION_TERM",
        "ORGANISATION_TERM",
        "USUAL_GP.USER_NAME",
        "COMMENCE_DATE",
        "LASTISSUE_DATE",
        "ASSOCIATEDTEXT",
        "QUANTITY_UNIT",
        "AGE_AT_EVENT",
    ]
    column_upper = column_text.upper()
    return any(token in column_upper for token in enhanced_columns)


def _criteria_summary_from_restrictions(criteria: List[Dict[str, Any]]) -> Dict[str, Any]:
    for crit in criteria:
        flags = crit.get("flags") or {}
        record_count = flags.get("record_count")
        direction = flags.get("ordering_direction") or ""
        if not record_count:
            continue
        label = "Latest"
        if str(direction).upper() == "ASC":
            label = "First"
        return {
            "label": f"{label} {record_count}",
            "record_count": record_count,
            "direction": direction,
            "ordering_column": flags.get("ordering_column") or "",
        }
    return {}


def _parse_sort_configuration(column_group: ET.Element, namespaces: Dict[str, str]) -> Optional[Dict[str, Any]]:
    sort_elem = find_ns(column_group, "sort", namespaces)
    if sort_elem is None:
        return None

    sort_config = {
        "column_id": get_text_ns(sort_elem, "columnId", namespaces),
        "direction": get_text_ns(sort_elem, "direction", namespaces),
    }
    return sort_config if any(sort_config.values()) else None


def _parse_aggregate_report(
    aggregate_elem: ET.Element,
    namespaces: Dict[str, str],
    code_store: Optional["CodeStore"] = None,
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    if aggregate_elem is None:
        return None, []

    info: Dict[str, Any] = {
        "logical_table": get_text_ns(aggregate_elem, "logicalTable", namespaces),
    }

    groups = _parse_aggregate_groups(aggregate_elem, namespaces)
    if groups:
        info["groups"] = groups

    statistical = _parse_statistical_groups(aggregate_elem, namespaces, groups)
    if statistical:
        info["statistical_groups"] = statistical

    result = _parse_result_block(aggregate_elem, namespaces)
    if result:
        info["result"] = result

    criteria_flags = _parse_direct_criteria(aggregate_elem, namespaces, code_store=code_store)

    has_payload = any(bool(info.get(key)) for key in ["logical_table", "groups", "statistical_groups", "result"])
    return (info if has_payload else None), criteria_flags


def _parse_custom_aggregate(
    audit_elem: ET.Element,
    namespaces: Dict[str, str],
    code_store: Optional["CodeStore"] = None,
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    custom_aggregate = find_ns(audit_elem, "customAggregate", namespaces)
    if custom_aggregate is None:
        return None, []
    return _parse_aggregate_report(custom_aggregate, namespaces, code_store=code_store)


def _parse_aggregate_groups(container: ET.Element, namespaces: Dict[str, str]) -> List[Dict[str, Any]]:
    groups: List[Dict[str, Any]] = []
    for group in findall_ns(container, ".//group", namespaces):
        group_id = get_text_ns(group, "id", namespaces) or group.get("id", "")
        display_name = get_text_ns(group, "displayName", namespaces)

        group_data: Dict[str, Any] = {
            "id": group_id,
            "display_name": display_name,
            "grouping_columns": [],
        }

        for grouping_col in findall_ns(group, ".//groupingColumn", namespaces):
            if grouping_col.text:
                group_data["grouping_columns"].append(grouping_col.text.strip())

        sub_totals = get_text_ns(group, "subTotals", namespaces)
        repeat_header = get_text_ns(group, "repeatHeader", namespaces)
        if sub_totals:
            group_data["sub_totals"] = sub_totals.lower() == "true"
        if repeat_header:
            group_data["repeat_header"] = repeat_header.lower() == "true"

        groups.append(group_data)

    return groups


def _parse_statistical_groups(container: ET.Element, namespaces: Dict[str, str], aggregate_groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    statistical: List[Dict[str, Any]] = []
    group_lookup = {g.get("id"): g.get("display_name") for g in aggregate_groups if g.get("id")}

    rows_elem = find_ns(container, "rows", namespaces)
    if rows_elem is not None:
        group_id = get_text_ns(rows_elem, "groupId", namespaces)
        if group_id:
            statistical.append(
                {
                    "type": "rows",
                    "group_id": group_id,
                    "group_name": group_lookup.get(group_id, group_id),
                }
            )

    columns_elem = find_ns(container, "columns", namespaces)
    if columns_elem is not None:
        group_id = get_text_ns(columns_elem, "groupId", namespaces)
        if group_id:
            statistical.append(
                {
                    "type": "columns",
                    "group_id": group_id,
                    "group_name": group_lookup.get(group_id, group_id),
                }
            )

    return statistical


def _parse_result_block(container: ET.Element, namespaces: Dict[str, str]) -> Optional[Dict[str, Any]]:
    result_elem = find_ns(container, "result", namespaces)
    if result_elem is None:
        return None
    result = {
        "source": get_text_ns(result_elem, "source", namespaces),
        "calculation_type": get_text_ns(result_elem, "calculationType", namespaces),
    }
    return result if any(result.values()) else None


def _parse_population_references(audit_elem: ET.Element, namespaces: Dict[str, str]) -> List[str]:
    references: List[str] = []
    for pop in findall_ns(audit_elem, ".//population", namespaces):
        if pop.text and pop.text.strip():
            references.append(pop.text.strip())
    return references


def _parse_direct_criteria(
    parent_elem: ET.Element,
    namespaces: Dict[str, str],
    parent_ctx: Optional[Dict[str, Any]] = None,
    code_store: Optional["CodeStore"] = None,
) -> List[Dict[str, Any]]:
    criteria_flags: List[Dict[str, Any]] = []
    for container in findall_ns(parent_elem, "criteria", namespaces):
        for criterion in findall_ns(container, "criterion", namespaces):
            criteria_flags.append(parse_criterion(criterion, namespaces, parent_context=parent_ctx, code_store=code_store))
    return criteria_flags
