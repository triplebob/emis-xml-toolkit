"""
Report-specific helpers for criteria filtering and filter text generation.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from .column_name_mapper import get_column_display_name
from .emisinternal_describer import describe_emisinternal_filter
from .temporal_describer import describe_age_filter, describe_date_filter, describe_numeric_filter
from .value_set_resolver import resolve_value_sets


_CODE_COLUMNS = {"CODE", "CLINICAL_CODE", "READ_CODE", "READCODE", "DRUGCODE", "DRUG_CODE"}


def split_report_value_sets(criterion: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    value_sets = resolve_value_sets(criterion)
    clinical: List[Dict[str, Any]] = []
    internal: List[Dict[str, Any]] = []
    for vs in value_sets:
        if str(vs.get("code_system") or "").upper() == "EMISINTERNAL":
            internal.append(vs)
        else:
            clinical.append(vs)
    return clinical, internal


def build_report_filter_items(
    criterion: Dict[str, Any],
    clinical_value_sets: List[Dict[str, Any]] | None = None,
    emisinternal_value_sets: List[Dict[str, Any]] | None = None,
) -> List[str]:
    flags = criterion.get("flags") or {}

    if clinical_value_sets is None or emisinternal_value_sets is None:
        clinical_value_sets, emisinternal_value_sets = split_report_value_sets(criterion)

    code_count = len(clinical_value_sets)
    filters: List[str] = []
    if code_count:
        negation = flags.get("negation")
        include_word = "Exclude" if negation is True else "Include"
        filters.append(f"{include_word} {code_count} specified clinical codes")

    column_filters = _filter_linked_column_filters(criterion)
    for column_filter in column_filters:
        value_sets_in_filter = column_filter.get("value_sets") or []
        filter_type = (column_filter.get("filter_type") or "").lower()
        column_raw = column_filter.get("column_name") or column_filter.get("column") or ""
        column_norm = str(column_raw).upper()
        if any(str(vs.get("code_system") or "").upper() == "EMISINTERNAL" for vs in value_sets_in_filter):
            continue
        if filter_type in {"readcode", "drugcode", "emisinternal"}:
            continue
        if column_norm in _CODE_COLUMNS:
            continue

        range_info = column_filter.get("range_info") or {}
        column_display_raw = column_filter.get("column_display") or column_filter.get("display_name") or column_raw
        column_display = get_column_display_name(column_display_raw) or column_display_raw or column_raw

        desc = ""
        if filter_type == "age":
            desc = describe_age_filter(range_info, column_raw)
        elif filter_type == "date":
            desc = describe_date_filter(
                range_info,
                column_display,
                column_raw,
                column_filter.get("relative_to"),
            )
        elif filter_type == "numeric":
            desc = describe_numeric_filter(range_info)
        elif range_info:
            desc = describe_numeric_filter(range_info)

        if desc:
            filters.append(desc)

    column_filters = criterion.get("column_filters") or []
    emisinternal_descriptions = _get_emisinternal_descriptions(flags, emisinternal_value_sets, column_filters)
    if emisinternal_descriptions:
        filters.extend(emisinternal_descriptions)

    record_count = flags.get("record_count")
    if record_count:
        direction = str(flags.get("ordering_direction") or "").upper()
        ordering_column_raw = flags.get("ordering_column") or "DATE"
        ordering_column = get_column_display_name(ordering_column_raw) or ordering_column_raw
        qualifier = "first" if direction == "ASC" else "latest"
        filters.append(f"Ordering by: {ordering_column}, select the {qualifier} {record_count}")

    return _dedupe_strings(filters)


def describe_group_criteria(criteria: List[Dict[str, Any]]) -> str:
    base_count = len(criteria or [])
    linked_count = sum(len(c.get("linked_criteria") or []) for c in (criteria or []))
    total_count = base_count + linked_count
    verb = "determines" if total_count == 1 else "determine"
    filter_count = _count_main_filters(criteria)

    base_word = _pluralise(base_count, "criterion", "criteria")
    linked_word = _pluralise(linked_count, "linked criterion", "linked criteria")
    filter_word = _pluralise(filter_count, "filter", "filters")

    parts = [f"{base_count} {base_word}"]
    if filter_count:
        parts.append(f"{filter_count} {filter_word}")
    if linked_count:
        parts.append(f"{linked_count} {linked_word}")

    joined = ", ".join(parts[:-1]) + f" and {parts[-1]}" if len(parts) > 1 else parts[0]
    return f"This column group has {joined} that {verb} which records appear in this column section."


def build_audit_criteria_overview(criteria: List[Dict[str, Any]]) -> Dict[str, Any]:
    count = len(criteria or [])
    if not count:
        return {"title": "", "summary": "", "criteria": []}

    rule_word = _pluralise(count, "rule", "rules")
    summary = f"This Audit Report applies {count} additional filtering {rule_word} across all member searches."
    return {
        "title": "🔍 Additional Report Criteria",
        "summary": summary,
        "criteria": criteria,
    }


def has_embedded_report_code_rules(criteria: List[Dict[str, Any]]) -> bool:
    def _criterion_has_codes(criterion: Dict[str, Any]) -> bool:
        for vs in resolve_value_sets(criterion):
            if not bool(vs.get("is_emisinternal", False)):
                return True
        linked = (criterion.get("flags") or {}).get("linked_criteria") or criterion.get("linked_criteria") or []
        for entry in linked:
            linked_criterion = None
            if isinstance(entry, dict):
                linked_criterion = entry.get("criterion") or entry
            if linked_criterion and _criterion_has_codes(linked_criterion):
                return True
        return False

    return any(_criterion_has_codes(criterion) for criterion in criteria)


def build_aggregate_criteria_groups(criteria: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not criteria:
        return []
    return [
        {
            "title": "Built-in Criteria 1 - Logic: AND",
            "operator": "AND",
            "criteria": criteria,
        }
    ]


def _count_main_filters(criteria: List[Dict[str, Any]]) -> int:
    total = 0
    for criterion in criteria or []:
        clinical_value_sets, emisinternal_value_sets = split_report_value_sets(criterion)
        filters = build_report_filter_items(criterion, clinical_value_sets, emisinternal_value_sets)
        count = len(filters)
        if clinical_value_sets:
            code_count = len(clinical_value_sets)
            negation = (criterion.get("flags") or {}).get("negation")
            include_word = "Exclude" if negation is True else "Include"
            code_line = f"{include_word} {code_count} specified clinical codes"
            if code_line in filters:
                count -= 1
        if count > 0:
            total += count
    return total


def _pluralise(count: int, singular: str, plural: str) -> str:
    return singular if count == 1 else plural

def _get_emisinternal_descriptions(
    flags: Dict[str, Any],
    emisinternal_value_sets: List[Dict[str, Any]],
    column_filters: List[Dict[str, Any]],
) -> List[str]:
    descriptions: List[str] = []
    column_display_lookup = _build_column_display_lookup(column_filters)
    entries = flags.get("emisinternal_entries") or []
    for entry in entries:
        column_raw = entry.get("column") or ""
        column_display = (
            entry.get("display_name")
            or column_display_lookup.get(column_raw)
            or get_column_display_name(column_raw)
            or column_raw
            or "Internal classification"
        )
        vs_like = [{"values": entry.get("values") or []}]
        in_not_in = str(entry.get("in_not_in", "")).upper()
        desc = describe_emisinternal_filter(column_display, vs_like, in_not_in=in_not_in)
        if entry.get("has_all_values"):
            desc = f"{desc} (all values)"
        if desc:
            descriptions.append(desc)

    if not descriptions and emisinternal_value_sets:
        for vs in emisinternal_value_sets:
            column_raw = vs.get("column_display_name") or vs.get("column_name") or vs.get("column") or ""
            column_display = (
                column_display_lookup.get(column_raw)
                or get_column_display_name(column_raw)
                or column_raw
                or "Internal classification"
            )
            values = [
                {
                    "value": vs.get("code_value"),
                    "displayName": vs.get("display_name") or vs.get("code_value"),
                }
            ]
            in_not_in = str(vs.get("in_not_in", "")).upper()
            desc = describe_emisinternal_filter(column_display, [{"values": values}], in_not_in=in_not_in)
            if desc:
                descriptions.append(desc)

    return _dedupe_strings(descriptions)


def _build_column_display_lookup(column_filters: List[Dict[str, Any]]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for entry in column_filters or []:
        display = entry.get("display_name") or ""
        if not display:
            continue
        for column in entry.get("columns") or [entry.get("column")]:
            if column and column not in lookup:
                lookup[column] = display
    return lookup


def _filter_linked_column_filters(criterion: Dict[str, Any]) -> List[Dict[str, Any]]:
    column_filters = criterion.get("column_filters") or []
    linked_items = criterion.get("linked_criteria") or []
    if not linked_items:
        return column_filters

    linked_filters: List[Dict[str, Any]] = []
    for linked in linked_items:
        child = linked.get("criterion") or {}
        linked_filters.extend(child.get("column_filters") or [])

    if not linked_filters:
        return column_filters

    linked_signatures = {_column_filter_signature(entry) for entry in linked_filters}
    return [
        entry
        for entry in column_filters
        if _column_filter_signature(entry) not in linked_signatures
    ]


def _column_filter_signature(entry: Dict[str, Any]) -> Tuple[Any, ...]:
    column = entry.get("column_name") or entry.get("column") or ""
    in_not_in = entry.get("in_not_in") or ""
    filter_type = entry.get("filter_type") or ""
    range_info = _normalise_structure(entry.get("range_info") or {})
    value_sets = _normalise_structure(entry.get("value_sets") or [])
    return (column, filter_type, in_not_in, range_info, value_sets)


def _normalise_structure(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple((key, _normalise_structure(value[key])) for key in sorted(value))
    if isinstance(value, list):
        return tuple(_normalise_structure(item) for item in value)
    return value


def _dedupe_strings(items: Iterable[str]) -> List[str]:
    seen = set()
    unique: List[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique
