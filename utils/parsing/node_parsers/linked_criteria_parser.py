"""
Utilities for handling linked criteria relationships in parsed search structures.
"""

from typing import Dict, List, Any, Optional

from ...metadata.operator_translator import pluralise_unit
from ...metadata.value_set_resolver import resolve_value_sets


def _extract_linked_children(group: Dict) -> List[str]:
    """Collect child column names from linked criteria across a group."""
    group = group or {}
    children: List[str] = []
    for criterion in (group.get("criteria") or []):
        flags = criterion.get("flags") or {}
        for linked in flags.get("linked_criteria") or []:
            child_col = (linked.get("child_column") or "").strip()
            if child_col:
                children.append(child_col)
    return children


def _coerce_int(value: Any) -> Optional[int]:
    """Convert to int where possible for comparison/pluralisation."""
    try:
        text = str(value).strip()
        if not text:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _format_duration(value: Any, unit: Optional[str]) -> str:
    """Render a duration with pluralised units."""
    value_text = str(value).strip() if value is not None else ""
    if not value_text:
        return ""
    plural_value = _coerce_int(value_text)
    unit_text = pluralise_unit(plural_value if plural_value is not None else value_text, unit or "")
    if not unit_text:
        return value_text
    return f"{value_text} {unit_text}"


def filter_top_level_criteria(group: Dict) -> List[Dict]:
    """
    Filter out linked criteria that should only appear nested under parents.

    Example:
    >>> filter_top_level_criteria({"criteria": [{"column": "A"}, {"column": "B", "flags": {"linked_criteria": [{"child_column": "C"}]}}, {"column": "C"}]})
    [{'column': 'A'}, {'column': 'B', 'flags': {'linked_criteria': [{'child_column': 'C'}]}}]
    """
    group = group or {}
    criteria = group.get("criteria") or []
    linked_children = set(_extract_linked_children(group))

    filtered: List[Dict] = []
    for criterion in criteria:
        column_name = (criterion.get("column") or "").strip()
        if column_name and column_name in linked_children:
            continue
        filtered.append(criterion)
    return filtered


def has_linked_criteria(group: Dict) -> bool:
    """
    Check if any criterion in group has linked criteria.
    """
    group = group or {}
    for criterion in (group.get("criteria") or []):
        flags = criterion.get("flags") or {}
        linked = flags.get("linked_criteria") or []
        if linked:
            return True
    return False


def filter_linked_value_sets_from_main(criterion: Dict) -> List[Dict]:
    """
    Filter value sets that belong to the main criterion only (exclude linked children and EMISINTERNAL).
    EMISINTERNAL value sets are column filters, not clinical codes.
    """
    criterion = criterion or {}
    value_sets = resolve_value_sets(criterion)

    # Filter out EMISINTERNAL value sets (these are column filters, not clinical codes)
    non_internal = []
    for vs in value_sets:
        code_system = str(vs.get("code_system") or "").upper()
        if code_system != "EMISINTERNAL":
            non_internal.append(vs)

    # If no linked criteria, return all non-EMISINTERNAL value sets
    linked_criteria = (criterion.get("flags") or {}).get("linked_criteria") or []
    if not linked_criteria:
        return non_internal

    # If there are linked criteria, filter by column
    main_column = (criterion.get("column") or
                   (criterion.get("flags") or {}).get("column_name") or "")
    if isinstance(main_column, list):
        main_column = main_column[0] if main_column else ""
    main_column = str(main_column).strip()

    linked_children = {
        (lc.get("child_column") or "").strip()
        for lc in linked_criteria
        if lc
    }

    filtered: List[Dict] = []
    for vs in non_internal:
        column_name = vs.get("column_name") or ""
        if isinstance(column_name, list):
            column_name = column_name[0] if column_name else ""
        column_name = str(column_name).strip()
        if column_name == main_column:
            filtered.append(vs)
    return filtered


def filter_linked_column_filters_from_main(criterion: Dict) -> List[Dict]:
    """
    Filter column filters that belong to the main criterion only (exclude linked children).
    """
    criterion = criterion or {}
    column_filters = criterion.get("column_filters") or []

    # If no linked criteria, return all column filters
    linked_criteria = (criterion.get("flags") or {}).get("linked_criteria") or []
    if not linked_criteria:
        return column_filters

    # If there are linked criteria, filter by column
    main_column = (criterion.get("column") or
                   (criterion.get("flags") or {}).get("column_name") or "")
    if isinstance(main_column, list):
        main_column = main_column[0] if main_column else ""
    main_column = str(main_column).strip()

    linked_children = {
        (lc.get("child_column") or "").strip()
        for lc in linked_criteria
        if lc
    }

    filtered: List[Dict] = []
    for col_filter in column_filters:
        column_name = (col_filter.get("column_name") or "").strip()
        if column_name == main_column:
            filtered.append(col_filter)
    return filtered


def get_temporal_relationship_description(linked_crit: Dict) -> str:
    """
    Generate user-friendly temporal relationship description in EMIS standard format.

    Examples:
    >>> get_temporal_relationship_description({"temporal_range": {"from": {"operator": "GT", "value": "0", "unit": "DAY"}}})
    'more than 0 days after'
    >>> get_temporal_relationship_description({"temporal_range": {"from": {"operator": "LTEQ", "value": "28", "unit": "DAY"}}})
    'less than or equal to 28 days before'
    """
    if not linked_crit:
        return ""

    temporal_range = linked_crit.get("temporal_range") or {}
    if not temporal_range:
        return ""

    from_bound = temporal_range.get("from") or {}
    to_bound = temporal_range.get("to") or {}

    # Process 'from' bound (primary)
    if from_bound and from_bound.get("value") is not None:
        operator = (from_bound.get("operator") or "").strip().upper()
        value = from_bound.get("value")
        unit = (from_bound.get("unit") or "DAY").strip().lower()

        # Pluralise unit
        unit_text = f"{unit}s" if not unit.endswith("s") else unit

        # Map operators to EMIS-standard phrases
        if operator == "GT":
            return f"more than {value} {unit_text} after"
        elif operator in ("GTE", "GTEQ"):
            return f"more than or equal to {value} {unit_text} after"
        elif operator == "LT":
            return f"less than {value} {unit_text} before"
        elif operator in ("LTE", "LTEQ"):
            return f"less than or equal to {value} {unit_text} before"
        elif operator == "EQ":
            value_int = _coerce_int(value)
            if value_int == 0:
                return "at the same time as"
            return f"exactly {value} {unit_text} after"

    # Process 'to' bound if no 'from' bound
    if to_bound and to_bound.get("value") is not None:
        operator = (to_bound.get("operator") or "").strip().upper()
        value = to_bound.get("value")
        unit = (to_bound.get("unit") or "DAY").strip().lower()

        unit_text = f"{unit}s" if not unit.endswith("s") else unit

        if operator == "LT":
            return f"less than {value} {unit_text} before"
        elif operator in ("LTE", "LTEQ"):
            return f"less than or equal to {value} {unit_text} before"
        elif operator == "GT":
            return f"more than {value} {unit_text} after"
        elif operator in ("GTE", "GTEQ"):
            return f"more than or equal to {value} {unit_text} after"

    return ""
