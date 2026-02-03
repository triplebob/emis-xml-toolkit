"""
Helpers to describe base population types and references to other population criteria.

Examples:
>>> describe_population_type("ACTIVE")
"All currently registered patients"
>>> describe_population_type("custom_cohort")
"custom_cohort patients"
>>> id_to_name = {"guid-123": "Diabetes Search"}
>>> format_population_reference("guid-123", id_to_name, [])
"🔍 Diabetes Search"
>>> format_population_reference("unknown-guid", {}, [])
"Search ID: unknown-g..."
"""

from typing import Dict, List, Optional


_POPULATION_MAP = {
    "ACTIVE": "All currently registered patients",
    "ALL": "All patients (including left and deceased)",
    "DECEASED": "Deceased patients",
    "LEFT": "Patients who have left the practice",
}


def describe_population_type(parent_type: Optional[str]) -> str:
    """
    Produce a user-friendly description for a population type token.

    Examples:
    >>> describe_population_type("ACTIVE")
    "All currently registered patients"
    >>> describe_population_type("custom_cohort")
    "custom_cohort patients"
    """
    if parent_type is None:
        return "Custom patient population"

    text = str(parent_type).strip()
    if not text:
        return "Custom patient population"

    mapped = _POPULATION_MAP.get(text.upper())
    if mapped:
        return mapped
    return f"{text} patients"


def _coerce_guid(value: Optional[str]) -> str:
    """Normalise GUID text for comparison while preserving original caller casing."""
    if value is None:
        return ""
    return str(value).strip()


def _match_search_by_guid(all_searches: List[Dict], guid_text: str) -> Optional[str]:
    """Scan search dicts for a matching GUID and return a friendly name when available."""
    for search in all_searches or []:
        search_guid = (
            search.get("guid")
            or search.get("GUID")
            or search.get("Guid")
            or search.get("id")
            or search.get("ID")
            or search.get("search_id")
            or search.get("searchId")
            or search.get("SearchId")
            or search.get("SearchID")
        )
        if _coerce_guid(search_guid) == guid_text:
            name = (
                search.get("name")
                or search.get("Name")
                or search.get("search_name")
                or search.get("title")
            )
            if name:
                return str(name)
    return None


def format_population_reference(
    ref_guid: Optional[str], id_to_name: Dict[str, str], all_searches: List[Dict]
) -> str:
    """
    Format a population reference to show a search name or a short GUID fallback.

    Examples:
    >>> id_to_name = {"guid-123": "Diabetes Search"}
    >>> format_population_reference("guid-123", id_to_name, [])
    "🔍 Diabetes Search"
    >>> format_population_reference("unknown-guid", {}, [])
    "Search ID: unknown-g..."
    """
    guid_text = _coerce_guid(ref_guid)
    if not guid_text:
        return ""

    search_name = id_to_name.get(guid_text) or id_to_name.get(guid_text.lower()) or id_to_name.get(guid_text.upper())
    if search_name:
        return f"🔍 {search_name}"

    matched_name = _match_search_by_guid(all_searches, guid_text)
    if matched_name:
        return f"🔍 {matched_name}"

    return f"Search ID: {guid_text[:8]}..."
