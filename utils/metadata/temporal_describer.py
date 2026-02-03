"""
Helpers to describe temporal filters (date, age, numeric) for search viewer outputs.

Examples:
>>> describe_date_filter({"from": {"operator": "GTEQ", "value": "-6", "unit": "MONTH"}}, "Date", "date_col")
"and the Date is after or on 6 months before the search date"
>>> describe_date_filter({"from": {"value": "this", "unit": "MONTH"}}, "Date", "date_col")
"and the Date is this month"
>>> describe_date_filter({"from": {"operator": "GTEQ", "value": "2024-01-01"}}, "Date", "date_col")
"The Date >= 2024-01-01 (Hardcoded Date)"
>>> describe_age_filter({"from": {"operator": "GTEQ", "value": "65", "unit": "YEAR"}})
"Age >= 65 years of age"
>>> describe_numeric_filter({"from": {"operator": "LT", "value": "0.7"}})
"Value < 0.7"
"""

from typing import Dict, Optional

from .operator_translator import format_operator_text, format_operator_verbose, pluralise_unit


_TEMPORAL_KEYWORDS = {"last", "this", "next"}


def _coerce_int(value: Optional[str]) -> Optional[int]:
    """Convert values to int where possible."""
    try:
        text = str(value).strip()
        if not text:
            return None
        return int(text)
    except (TypeError, ValueError):
        return None


def _is_temporal_variable(value: Optional[str]) -> bool:
    """Identify temporal keywords such as last/this/next."""
    if value is None:
        return False
    return str(value).strip().lower() in _TEMPORAL_KEYWORDS


def _format_temporal_unit(unit: Optional[str]) -> str:
    """Normalise temporal units to user-friendly text."""
    if not unit:
        return "period"
    cleaned = str(unit).strip().replace("_", "").replace("-", "").lower()
    mapping = {
        "fiscalyear": "fiscal year",
        "quarter": "quarter",
        "month": "month",
        "week": "week",
        "day": "day",
        "year": "year",
    }
    if cleaned in mapping:
        return mapping[cleaned]
    fallback = str(unit).strip().replace("_", " ").replace("-", " ").lower()
    return fallback or "period"


def _normalise_date_operator_text(text: str) -> str:
    """Tweak operator wording to match natural phrasing."""
    if text == "on or after":
        return "after or on"
    if text == "on or before":
        return "before or on"
    return text


def _build_relative_description(
    operator: Optional[str],
    value: Optional[str],
    unit: Optional[str],
    base_label: str,
) -> str:
    """Construct relative date wording based on offset from a base date label."""
    offset = _coerce_int(value)
    if offset is None:
        return ""

    unit_key = str(unit or "").strip().lower()
    unit_text = pluralise_unit(abs(offset), unit_key) if unit_key else ""

    if offset == 0:
        base = base_label
    else:
        direction = "before" if offset < 0 else "after"
        amount = f"{abs(offset)} {unit_text}".strip()
        base = f"{amount} {direction} {base_label}" if amount else f"{direction} {base_label}"

    operator_text = _normalise_date_operator_text(format_operator_text(operator or "", is_numeric=False))

    # EMIS uses specific wording for GT/GTEQ with negative offsets
    if operator and offset < 0:
        op_upper = operator.upper()
        if op_upper == "GT":
            operator_text = "on"
        elif op_upper == "GTEQ":
            operator_text = "after or on"

    return f"{operator_text} {base}".strip() if operator_text else base


def describe_date_filter(
    range_info: Dict, column_display: str, column_name: str, relative_to: Optional[str] = None
) -> str:
    """
    Build a user-friendly description for date filters.

    Handles relative offsets, temporal keywords, and hardcoded dates.

    Examples:
    >>> describe_date_filter({"from": {"operator": "GTEQ", "value": "-6", "unit": "MONTH"}}, "Date", "date_col")
    "and the Date is after or on 6 months before the search date"
    >>> describe_date_filter({"from": {"value": "this", "unit": "MONTH"}}, "Date", "date_col")
    "and the Date is this month"
    >>> describe_date_filter({"from": {"operator": "GTEQ", "value": "2024-01-01"}}, "Date", "date_col")
    "The Date >= 2024-01-01 (Hardcoded Date)"
    """
    if not range_info:
        return ""

    label = f"the {column_display}" if column_display else "the Date"
    base_label = "the search date"
    relative_hint = (range_info or {}).get("relative_to") or (range_info or {}).get("relativeTo") or relative_to
    if relative_hint and str(relative_hint).upper() == "BASELINE":
        base_label = "the baseline date"
    conditions = []

    def build_condition(bound: Dict) -> str:
        if not isinstance(bound, dict):
            return ""

        value = bound.get("value")
        operator = bound.get("operator") or ""
        unit = bound.get("unit")

        if _is_temporal_variable(value):
            keyword = str(value).strip().lower()
            unit_text = _format_temporal_unit(unit)
            return f"{label} is {keyword} {unit_text}"

        relative_text = _build_relative_description(operator, value, unit, base_label)
        if relative_text:
            return f"{label} is {relative_text}"

        value_text = str(value).strip() if value is not None else ""

        # Handle operator with no value (e.g., LTEQ with no value = "on or before the search date")
        if not value_text and operator:
            op_text = format_operator_text(operator, is_numeric=False)
            if op_text:
                return f"{label} is {op_text} {base_label}"

        if not value_text:
            return ""

        # Hardcoded dates use date operators (not numeric)
        op_text = format_operator_text(operator, is_numeric=False) or operator
        # Use column_display directly for proper title casing
        date_label = column_display if column_display else "Date"
        return f"{date_label} is {op_text} {value_text} (Hardcoded Date)"

    for key in ("from", "to"):
        bound = range_info.get(key)
        condition_text = build_condition(bound)
        if condition_text:
            # If this is an upper bound only, and numeric is negative, tweak phrasing to "before"
            if key == "to" and isinstance(bound, dict):
                val_int = _coerce_int(bound.get("value"))
                if val_int is not None and val_int < 0 and "after" in condition_text:
                    condition_text = condition_text.replace("after", "before", 1)
            conditions.append(condition_text)

    if not conditions:
        return ""

    joined = " and ".join(conditions)
    if joined.lower().startswith("the date is"):
        return f"and {joined}"
    return joined


def describe_age_filter(range_info: Dict, column_name: Optional[str] = None) -> str:
    """
    Build a user-friendly description for age filters.

    Examples:
    >>> describe_age_filter({"from": {"operator": "GTEQ", "value": "65", "unit": "YEAR"}})
    "Age >= 65 years of age"
    >>> describe_age_filter({"from": {"operator": "GTEQ", "value": "18"}, "to": {"operator": "LTEQ", "value": "75"}})
    "Age >= 18 years of age AND <= 75 years of age"
    >>> describe_age_filter({"from": {"operator": "GT", "value": "248", "unit": "DAY"}})
    "Age > 248 days (8 months)"
    """
    if not range_info:
        return ""

    def build_age_condition(bound: Dict) -> str:
        if not isinstance(bound, dict):
            return ""

        value = bound.get("value")
        value_text = str(value).strip() if value is not None else ""
        if not value_text:
            return ""

        unit = bound.get("unit") or "YEAR"
        unit_key = str(unit).strip().lower()
        operator_text = format_operator_verbose(bound.get("operator"))
        operator_display = operator_text or str(bound.get("operator") or "").strip()

        # Convert days to months if appropriate
        if unit_key == "day":
            days_value = _coerce_int(value)
            if days_value is not None:
                approx_months = round(days_value / 30)
                if approx_months >= 1:
                    # Use months instead of days
                    value_text = str(approx_months)
                    unit_key = "month"

        unit_text = pluralise_unit(value_text, unit_key)
        suffix = f"{unit_text} old"

        return f"{operator_display} {value_text} {suffix}".strip()

    conditions = []
    from_cond = build_age_condition(range_info.get("from") or {})
    to_cond = build_age_condition(range_info.get("to") or {})

    if from_cond:
        conditions.append(from_cond)
    if to_cond:
        conditions.append(to_cond)

    if not conditions:
        return ""

    conditions[0] = f"Patient age: {conditions[0]}"
    return " AND ".join(conditions)  # Uppercase AND per EMIS standard


def describe_numeric_filter(range_info: Dict) -> str:
    """
    Build a description for generic numeric filters.

    Examples:
    >>> describe_numeric_filter({"from": {"operator": "LT", "value": "0.7"}})
    "Value < 0.7"
    >>> describe_numeric_filter({"from": {"operator": "GT", "value": "30"}, "to": {"operator": "LT", "value": "40"}})
    "Value > 30 AND < 40"
    """
    if not range_info:
        return ""

    def build_numeric_condition(bound: Dict) -> str:
        if not isinstance(bound, dict):
            return ""
        value = bound.get("value")
        value_text = str(value).strip() if value is not None else ""
        if not value_text:
            return ""
        operator_text = format_operator_text(bound.get("operator"), is_numeric=True)
        operator_display = operator_text or str(bound.get("operator") or "").strip()
        return f"{operator_display} {value_text}".strip()

    conditions = []
    from_cond = build_numeric_condition(range_info.get("from") or {})
    to_cond = build_numeric_condition(range_info.get("to") or {})

    if from_cond:
        conditions.append(from_cond)
    if to_cond:
        conditions.append(to_cond)

    if not conditions:
        return ""

    conditions[0] = f"Value {conditions[0]}"
    return " AND ".join(conditions)
