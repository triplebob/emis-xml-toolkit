"""
Helpers to describe EMISINTERNAL classifications in friendly wording.
"""

from typing import Dict, List, Any


_VALUE_LABELS = {
    "FIRST": "First",
    "NEW": "New",
    "REVIEW": "Review",
    "ENDED": "Ended",
    "NONE": "None",
    "AUTO": "Automatic",
    "MANUAL": "Manual",
    "ELECTRONIC": "Electronic",
    "CURRENTLY_CONTRACTED": "Currently contracted user",
    "IS_PRIVATE": "Private record",
    "NOT_PRIVATE": "Not private",
    "ACUTE": "Acute",
    "REPEAT": "Repeat",
    "ELECTRONIC_ISSUE": "Electronic issue",
    "PAPER": "Paper",
}

_COLUMN_LABELS = {
    "EPISODE": "Episode",
    "CONSULTATION_HEADING": "Consultation heading",
    "ISSUE_METHOD": "Issue method",
    "USER_AUTH": "User authorisation",
    "IS_PRIVATE": "Privately Prescribed",
    "CONSULTATION_HEADING": "Consultation heading",
    "STATUS": "Status",
    "AUTHOR": "Author",
    "CURRENTLY_CONTRACTED": "User authorisation",
}

_CONSULTATION_HEADINGS = {
    "PROBLEM": "Problem",
    "PROBLEMS": "Problem",
    "MEDICATION": "Medication",
    "MEDICATIONS": "Medication",
    "IMMUNISATION": "Immunisation",
    "IMMUNISATIONS": "Immunisation",
    "ADMIN": "Administrative",
    "DIARY": "Diary",
    "PATHOLOGY": "Pathology",
    "CLINICAL_DOCUMENT": "Clinical document",
    "CONSULTATION": "Consultation",
    "DEFAULT": "Consultation",
}

_ISSUE_METHODS = {
    "A": "Automatic",
    "AUTO": "Automatic",
    "D": "Dispensing",
    "E": "Electronic",
    "ELECTRONIC": "Electronic",
    "H": "Handwritten",
    "OUTSIDEOUTOFHOURS": "Out Of Hours",
    "OutsideHospitalIssue": "Hospital",
    "P": "Printed Script",
    "Q": "Record for Notes",
    "PAPER": "Paper",
    "MANUAL": "Manual",
}

_USER_AUTH = {
    "CURRENTLY_CONTRACTED": "Currently contracted user",
    "AUTHOR": "Author",
    "USER_NAME": "User",
}

_STATUS = {
    "IS_PRIVATE": "Private record",
    "NOT_PRIVATE": "Not private",
    "TRUE": "True",
    "FALSE": "False",
    "ACTIVE": "Active",
    "INACTIVE": "Inactive",
}


def _extract_values(value_sets: List[Dict[str, Any]]) -> List[str]:
    """Pull value strings or display names from EMISINTERNAL value sets."""
    collected: List[str] = []
    seen: set = set()
    for vs in value_sets or []:
        for val in vs.get("values") or []:
            if isinstance(val, dict):
                display = val.get("displayName") or val.get("display_name")
                raw = val.get("value")
                label = display or raw
            else:
                label = val
            if label and label not in seen:
                seen.add(label)
                collected.append(str(label))
    return collected


def _map_value(value: str) -> str:
    """Normalise a single value token."""
    if value is None:
        return ""
    key = str(value).strip().upper()
    return (
        _VALUE_LABELS.get(key)
        or _CONSULTATION_HEADINGS.get(key)
        or _ISSUE_METHODS.get(key)
        or _USER_AUTH.get(key)
        or _STATUS.get(key)
        or str(value).strip()
    )


def describe_emisinternal_filter(column_name: str, value_sets: List[Dict[str, Any]], in_not_in: str = "") -> str:
    """
    Produce a friendly description for EMISINTERNAL classifications.
    """
    # Normalise column_name to string if it's a list
    if isinstance(column_name, list):
        column_name = column_name[0] if column_name else ""

    if not value_sets:
        return f"{column_name or 'Internal classification'}: (unspecified)"
    values = _extract_values(value_sets)
    mapped_values = [_map_value(v) for v in values] if values else []

    # Use provided column_name (which should be display name from XML)
    # Only fallback to hardcoded mapping if it's a known raw column code
    column_key = (column_name or "").strip().upper()
    if column_key in _COLUMN_LABELS:
        column_label = _COLUMN_LABELS[column_key]
    else:
        column_label = column_name or "Internal classification"

    if mapped_values:
        joined = ", ".join(mapped_values)
        # Add prefix based on in_not_in
        if in_not_in.upper() == "NOTIN":
            prefix = "Exclude "
        elif in_not_in.upper() == "IN":
            prefix = "Include "
        else:
            prefix = ""
        return f"{prefix}{column_label}: {joined}"
    return f"{column_label}: (unspecified)"
