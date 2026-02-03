"""
Helpers to translate XML operators and pluralise time units for the search viewer UI.

Examples:
>>> format_operator_text("GTEQ", is_numeric=True)
">="
>>> format_operator_text("GTEQ", is_numeric=False)
"on or after"
>>> pluralise_unit(1, "year")
"year"
>>> pluralise_unit(2, "year")
"years"
>>> pluralise_unit("1", "month")
"month"
"""

from typing import Optional, Union

_NUMERIC_OPERATORS = {
    # EMIS standard: numeric/age operators are spelled out in full
    "GTEQ": "greater than or equal to",
    "LTEQ": "less than or equal to",
    "GT": "greater than",
    "LT": "less than",
    "EQ": "equal to",
    "NEQ": "not equal to",
}

_DATE_OPERATORS = {
    # EMIS standard: date operators use concise temporal phrasing
    "GTEQ": "on or after",
    "LTEQ": "on or before",
    "GT": "after",
    "LT": "before",
    "EQ": "on",
    "NEQ": "not on",
}

_VERBOSE_OPERATORS = {
    "GTEQ": "greater than or equal to",
    "LTEQ": "less than or equal to",
    "GT": "greater than",
    "LT": "less than",
    "EQ": "equal to",
    "NEQ": "not equal to",
}

_UNIT_PLURALS = {
    "year": "years",
    "month": "months",
    "week": "weeks",
    "day": "days",
    "hour": "hours",
    "minute": "minutes",
    "second": "seconds",
}


def format_operator_text(operator: str, is_numeric: bool = False) -> str:
    """
    Translate an XML operator token into user-friendly text for numeric or date contexts.

    Examples:
    >>> format_operator_text("GTEQ", is_numeric=True)
    ">="
    >>> format_operator_text("GTEQ", is_numeric=False)
    "on or after"
    """
    if operator is None:
        return ""

    original_text = str(operator)
    cleaned = original_text.strip()
    if not cleaned:
        return ""

    lookup = _NUMERIC_OPERATORS if is_numeric else _DATE_OPERATORS
    return lookup.get(cleaned.upper(), original_text)


def format_operator_verbose(operator: str) -> str:
    """
    Translate an XML operator token into verbose English.

    Examples:
    >>> format_operator_verbose("GTEQ")
    "greater than or equal to"
    >>> format_operator_verbose("LT")
    "less than"
    """
    if operator is None:
        return ""

    original_text = str(operator)
    cleaned = original_text.strip()
    if not cleaned:
        return ""

    return _VERBOSE_OPERATORS.get(cleaned.upper(), original_text)


def _safe_int(value: Union[str, int, None]) -> Optional[int]:
    """Convert incoming values to int where possible, handling blanks and None."""
    if value is None:
        return None
    try:
        text_value = str(value).strip()
        if not text_value:
            return None
        return int(text_value)
    except (TypeError, ValueError):
        return None


def pluralise_unit(value: Union[str, int], unit: str) -> str:
    """
    Pluralises a time unit based on the provided value, keeping unrecognised units unchanged.

    Examples:
    >>> pluralise_unit(1, "year")
    "year"
    >>> pluralise_unit(2, "year")
    "years"
    >>> pluralise_unit("1", "month")
    "month"
    """
    if unit is None:
        return ""

    unit_text = str(unit).strip()
    if not unit_text:
        return ""

    unit_key = unit_text.lower()
    plural_form = _UNIT_PLURALS.get(unit_key)
    if not plural_form:
        return unit_text

    numeric_value = _safe_int(value)
    if numeric_value is None:
        return unit_text

    return unit_text if numeric_value == 1 else plural_form
