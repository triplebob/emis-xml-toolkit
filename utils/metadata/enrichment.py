"""
Lookup enrichment for pipeline code rows.
Uses pre-built lookup dictionaries for SNOMED enrichment.
"""

from typing import List, Dict, Any


def _normalise_code_value(value: Any) -> str:
    """Normalise code values to clean strings (strip .0 from integer-like floats)."""
    try:
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        text = str(value)
        if text.endswith(".0") and text.replace(".", "", 1).isdigit():
            return text[:-2]
        return text
    except Exception:
        return str(value)


def enrich_with_lookup_dicts(
    codes: List[Dict[str, Any]],
    lookup_dicts: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Enrich codes using pre-built lookup dictionaries.

    Args:
        codes: List of code dicts from XML parsing
        lookup_dicts: Dict with 'guid_to_snomed' and 'guid_to_record' from filtered lookup

    Returns:
        Enriched list of codes (copied list, original untouched)
    """
    guid_to_snomed = lookup_dicts.get("guid_to_snomed", {})
    guid_to_record = lookup_dicts.get("guid_to_record", {})

    enriched: List[Dict[str, Any]] = []

    for code in codes:
        guid = _normalise_code_value(code.get("EMIS GUID") or code.get("emis_guid") or "").strip()
        new_code = dict(code)

        is_refset = bool(code.get("is_refset", False))

        if guid:
            if is_refset:
                # For true refsets, EMIS GUID IS the SNOMED code
                new_code["SNOMED Code"] = guid
                new_code["Mapping Found"] = "Found"
            else:
                # Look up SNOMED from dict
                snomed_code = guid_to_snomed.get(guid)
                if snomed_code:
                    new_code["SNOMED Code"] = _normalise_code_value(snomed_code)
                    new_code["Mapping Found"] = "Found"

            # Add additional metadata from record
            record = guid_to_record.get(guid, {})
            if record:
                if record.get("descendants"):
                    new_code["Descendants"] = record["descendants"]
                if record.get("has_qualifier"):
                    new_code["Has Qualifier"] = str(record["has_qualifier"])
                if record.get("code_type"):
                    new_code["Code Type"] = record["code_type"]
                if record.get("source_type") and not new_code.get("Source Type"):
                    new_code["Source Type"] = record["source_type"]

        enriched.append(new_code)

    return enriched


def enrich_codes_from_xml(
    codes: List[Dict[str, Any]],
    emis_guids: List[str],
) -> List[Dict[str, Any]]:
    """
    Enrich codes by loading filtered lookup for the given GUIDs.

    This is the main entry point for XML processing. It:
    1. Gets filtered lookup dicts for the EMIS GUIDs
    2. Enriches codes using those dicts

    Args:
        codes: List of code dicts from XML parsing
        emis_guids: List of all EMIS GUIDs found in the XML

    Returns:
        Enriched list of codes
    """
    from ..caching.lookup_manager import get_lookup_for_guids

    # Get lookup dicts filtered to just these GUIDs
    lookup_dicts = get_lookup_for_guids(emis_guids)

    # Enrich using the dicts
    return enrich_with_lookup_dicts(codes, lookup_dicts)
