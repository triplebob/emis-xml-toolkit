"""
Serialisers for parsing pipeline outputs into UI/export friendly rows.
"""

from typing import List, Dict, Any
from .description_generators import format_code_description, format_value_set_label, format_emis_style_description
from .code_classification import is_medication_code_system


def _normalise_context(value: Any) -> str:
    """Normalise table/column context into a single string."""
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item not in (None, ""))
    return str(value)


def serialise_codes_for_ui(flattened: List[Dict[str, Any]], include_debug_fields: bool = False) -> List[Dict[str, Any]]:
    """
    Transform flattened pipeline code entries into the columns used by clinical tabs/exports.

    Args:
        flattened: List of code entries from the parsing pipeline
        include_debug_fields: If True, include _original_fields for debugging (memory intensive)
    """
    rows: List[Dict[str, Any]] = []
    for entry in flattened:
        code_system = entry.get("code_system", "")
        table_context = _normalise_context(entry.get("table_context") or entry.get("logical_table_name") or "")
        column_context = _normalise_context(entry.get("column_context") or entry.get("column_name") or "")
        is_medication = bool(entry.get("is_medication_code") or entry.get("is_medication"))
        if not is_medication:
            is_medication = is_medication_code_system(code_system, table_context, column_context)

        element_type = entry.get("source_type") or entry.get("element_type") or ""
        source_type = "search" if element_type == "search" else "report" if element_type else ""
        report_type = entry.get("report_type") or element_type

        # Descriptions come from XML; lookup does not provide descriptions
        # SNOMED description comes from the value-level XML displayName
        xml_desc = entry.get("xml_display_name") or entry.get("display_name") or ""
        # Clean refset labels like "Refset: LD_COD[999...]" -> "LD_COD"
        if entry.get("is_refset") and xml_desc.startswith("Refset:"):
            xml_desc = xml_desc.replace("Refset:", "", 1).split("[", 1)[0].strip()
        valueset_desc = (
            entry.get("valueSet_description")
            or entry.get("valueset_description")
            or entry.get("valueSet_guid")
            or entry.get("valueset_guid")
            or ""
        )

        row = {
            "EMIS GUID": entry.get("emis_guid") or entry.get("code_value", ""),
            "Display Name": xml_desc,
            "ValueSet GUID": entry.get("valueSet_guid", "") or entry.get("valueset_guid", ""),
            "ValueSet Description": valueset_desc,
            "Table Context": table_context,
            "Column Context": column_context,
            "Source Type": source_type,
            "Source Name": entry.get("source_name") or entry.get("display_name") or entry.get("description") or "",
            "Source Container": entry.get("source_container") or entry.get("container_type") or entry.get("element_type") or "",
            "Source GUID": entry.get("source_guid") or entry.get("element_id") or "",
            "Inactive": bool(entry.get("inactive", False)),
            "is_medication": is_medication,
            "report_type": report_type,
        }
        # Preserve lookup-enriched SNOMED fields if present
        snomed_code_val = entry.get("SNOMED Code") or entry.get("snomed_code") or row["EMIS GUID"]
        try:
            if isinstance(snomed_code_val, float) and snomed_code_val.is_integer():
                snomed_code_val = str(int(snomed_code_val))
            else:
                snomed_code_val = str(snomed_code_val)
            if snomed_code_val.endswith(".0") and snomed_code_val.replace(".", "", 1).isdigit():
                snomed_code_val = snomed_code_val[:-2]
        except Exception:
            snomed_code_val = str(snomed_code_val)

        row["SNOMED Code"] = snomed_code_val
        # Descriptions come from the XML value-level display name; lookup never provides descriptions
        row["SNOMED Description"] = xml_desc or entry.get("snomed_description") or ""
        # Mapping Found: default to Not Found when missing (translator sets true matches)
        mapping_flag = entry.get("Mapping Found") or entry.get("mapping_found") or "Not Found"
        row["Mapping Found"] = mapping_flag
        if "Descendants" in entry:
            row["Descendants"] = entry.get("Descendants")
        has_qualifier = entry.get("Has Qualifier")
        if has_qualifier is None:
            has_qualifier = entry.get("HasQualifier")
        if has_qualifier is None:
            has_qualifier = entry.get("has_qualifier")
        if has_qualifier is not None and has_qualifier != "":
            row["Has Qualifier"] = str(has_qualifier)
        # Duplicate lower-case keys for field mapping compatibility
        row["display_name"] = row["Display Name"]
        row["valueset_description"] = row["ValueSet Description"]
        row["snomed_code"] = row["SNOMED Code"]
        row["snomed_description"] = row["SNOMED Description"]
        # Canonical flags/fields preserved for downstream processing (pipeline-first naming)
        include_children = entry.get("include_children")
        row["include_children"] = include_children
        if include_children is not None:
            row["Include Children"] = include_children
        row["is_refset"] = bool(entry.get("is_refset", False))
        row["is_pseudorefset"] = bool(entry.get("is_pseudorefset", False) or entry.get("is_pseudo_refset", False))
        row["is_pseudomember"] = bool(entry.get("is_pseudomember", False) or entry.get("is_pseudo_member", False))
        # Ensure is_emisinternal column always exists, set from parsed flag or computed from code_system
        is_emisinternal_flag = bool(entry.get("is_emisinternal", False))
        if not is_emisinternal_flag and str(code_system).strip().upper() == "EMISINTERNAL":
            is_emisinternal_flag = True
        row["is_emisinternal"] = is_emisinternal_flag
        row["valueSet_guid"] = entry.get("valueSet_guid") or entry.get("valueset_guid") or row["ValueSet GUID"]
        row["valueSet_description"] = valueset_desc
        row["code_system"] = code_system
        row["Code System"] = code_system
        row["xml_display_name"] = xml_desc
        # Source count from CodeStore (number of entities referencing this code)
        if "source_count" in entry:
            row["source_count"] = entry.get("source_count")
        row["Code Description"] = format_code_description(row)
        row["ValueSet Label"] = format_value_set_label(row)
        row["EMIS Description"] = format_emis_style_description(row)
        # Score for "most complete" ordering (used by unique_codes mode to keep best entry first)
        score = 0
        if row.get("ValueSet GUID"):
            score += 10
        if row.get("ValueSet Description"):
            score += 8
        if row.get("SNOMED Description"):
            score += 6
        if row.get("Source Type") or row.get("Source Name"):
            score += 4
        if row.get("include_children"):
            score += 2
        if row.get("Column Context") or row.get("Table Context"):
            score += 1
        row["_completeness_score"] = score
        # Preserve original plus computed debug fields for inspection (memory intensive)
        if include_debug_fields:
            debug_fields = dict(entry)
            debug_fields.update({
                "_computed_source_container": row.get("Source Container"),
                "_computed_source_name": row.get("Source Name"),
                "_computed_source_guid": row.get("Source GUID"),
                "_computed_mapping_found": row.get("Mapping Found"),
                "_computed_is_emisinternal": bool(entry.get("is_emisinternal", False)),
            })
            row["_original_fields"] = debug_fields
        rows.append(row)

    # Order rows so the most complete version of a code appears first for downstream deduplication
    rows.sort(key=lambda r: r.get("_completeness_score", 0), reverse=True)
    return rows
