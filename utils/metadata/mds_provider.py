"""
Entity-first MDS (Minimum Dataset) provider.

Builds lightweight export rows from pipeline_entities with optional enrichment from
pipeline_codes. Designed to avoid DataFrame-heavy processing and support low-memory
preview/export workflows.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from .code_classification import is_medication_code_system
from .value_set_resolver import resolve_value_sets


_PLACEHOLDER_VALUES = {
    "",
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
    "not found",
    "not_found",
    "not in emis lookup table",
}


def _escape_xml(text: Any) -> str:
    """Escape XML special characters."""
    value = _clean_text(text)
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _is_placeholder(value: Any) -> bool:
    return _clean_text(value).lower() in _PLACEHOLDER_VALUES


def _normalise_guid(value: Any) -> str:
    guid = _clean_text(value)
    if _is_placeholder(guid):
        return ""
    return guid


def _normalise_mapping_status(value: Any) -> str:
    if isinstance(value, bool):
        return "found" if value else "not_found"
    text = _clean_text(value).lower()
    if not text:
        return "not_found"
    if text in {"found", "true", "1", "yes", "mapped"}:
        return "found"
    if "not" in text and "found" in text:
        return "not_found"
    if text in {"not_found", "false", "0", "no", "missing"}:
        return "not_found"
    return "found" if "found" in text else "not_found"


def _normalise_snomed_code(value: Any) -> str:
    text = _clean_text(value)
    if _is_placeholder(text):
        return ""
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def _best_description(*values: Any) -> str:
    for value in values:
        text = _clean_text(value)
        if not text or _is_placeholder(text):
            continue
        # Avoid verbose parser fallback labels in MDS output.
        if text.lower() == "no display name in xml":
            continue
        return text
    return ""


def _score_row_quality(row: Dict[str, Any]) -> int:
    score = 0
    if row.get("mapping_status") == "found":
        score += 4
    if row.get("snomed_code"):
        score += 2
    if row.get("description"):
        score += 1
    return score


def _coerce_column_context(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if _clean_text(v))
    return _clean_text(value)


def _build_mapping_index(pipeline_codes: Optional[List[Dict[str, Any]]]) -> Dict[str, Dict[str, str]]:
    """
    Build a best-effort lookup index keyed by EMIS GUID from serialised pipeline rows.
    """
    index: Dict[str, Dict[str, str]] = {}
    if not pipeline_codes:
        return index

    for row in pipeline_codes:
        guid = _normalise_guid(
            row.get("EMIS GUID")
            or row.get("emis_guid")
            or row.get("code_value")
        )
        if not guid:
            continue

        candidate = {
            "snomed_code": _normalise_snomed_code(row.get("SNOMED Code") or row.get("snomed_code")),
            "mapping_status": _normalise_mapping_status(row.get("Mapping Found") or row.get("mapping_found")),
            "description": _best_description(
                row.get("SNOMED Description"),
                row.get("snomed_description"),
                row.get("Display Name"),
                row.get("display_name"),
                row.get("ValueSet Description"),
                row.get("valueSet_description"),
                row.get("valueset_description"),
            ),
        }

        existing = index.get(guid)
        if not existing:
            index[guid] = candidate
            continue

        existing_score = _score_row_quality(existing)
        candidate_score = _score_row_quality(candidate)
        if candidate_score > existing_score:
            index[guid] = candidate

    return index


def _iter_criteria_recursive(criteria: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    yield criteria
    for linked in criteria.get("linked_criteria", []) or []:
        child = linked.get("criterion") if isinstance(linked, dict) else None
        if isinstance(child, dict):
            yield from _iter_criteria_recursive(child)


def _iter_entity_criteria(entity: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for group in entity.get("criteria_groups", []) or []:
        for criterion in group.get("criteria", []) or []:
            if isinstance(criterion, dict):
                yield from _iter_criteria_recursive(criterion)

    for criterion in entity.get("report_criteria", []) or []:
        if isinstance(criterion, dict):
            yield from _iter_criteria_recursive(criterion)

    for criterion in entity.get("aggregate_criteria", []) or []:
        if isinstance(criterion, dict):
            yield from _iter_criteria_recursive(criterion)

    for column_group in entity.get("column_groups", []) or []:
        for criterion in column_group.get("criteria", []) or []:
            if isinstance(criterion, dict):
                yield from _iter_criteria_recursive(criterion)


def _normalise_source_type(raw_type: Any) -> str:
    text = _clean_text(raw_type).lower()
    if text == "search":
        return "search"
    if text in {"list_report", "audit_report", "aggregate_report"}:
        return text
    if text.endswith("report"):
        return text
    return "search" if "search" in text else "unknown"


def _build_emis_xml_output(
    emis_guid: str,
    description: str,
    is_refset: bool,
    include_children: bool = False,
) -> str:
    """
    Build EMIS-compatible XML block for MDS export.

    Format:
      <values><value>...</value><displayName>...</displayName><includeChildren>true/false</includeChildren></values>
    For refsets:
      ...<isRefset>true</isRefset>...
    """
    safe_guid = _escape_xml(emis_guid)
    safe_desc = _escape_xml(description)
    include_children_str = "true" if include_children else "false"
    xml = (
        f"<values><value>{safe_guid}</value>"
        f"<displayName>{safe_desc}</displayName>"
        f"<includeChildren>{include_children_str}</includeChildren>"
    )
    if is_refset:
        xml += "<isRefset>true</isRefset>"
    xml += "</values>"
    return xml


def _classify_code_type(code: Dict[str, Any], table_context: str, column_context: str) -> str:
    code_system = _clean_text(code.get("code_system")).upper()
    is_refset = bool(code.get("is_refset")) and not bool(code.get("is_pseudo_refset"))
    is_medication = bool(code.get("is_medication")) or is_medication_code_system(
        code_system, table_context, column_context
    )

    if bool(code.get("is_pseudo_member")):
        if is_medication:
            return "medication"
        if is_refset:
            return "refset"
        return "clinical"

    if is_medication:
        return "medication"
    if is_refset:
        return "refset"
    return "clinical"


def build_mds_dataset(
    pipeline_entities: List[Dict[str, Any]],
    pipeline_codes: Optional[List[Dict[str, Any]]] = None,
    view_mode: str = "unique_codes",
    include_emis_xml: bool = False,
    code_store: Any = None,
) -> Dict[str, Any]:
    """
    Build MDS rows and summary from parsed entities (entity-first traversal).
    """
    mode = "per_source" if view_mode == "unique_per_source" else view_mode
    mode = "per_source" if mode in {"per_source", "unique_per_entity"} else "unique_codes"

    mapping_index = _build_mapping_index(pipeline_codes)

    candidates: List[Dict[str, Any]] = []
    criteria_processed = 0
    resolved_codes_count = 0
    skipped_emisinternal = 0
    skipped_missing_guid = 0
    skipped_pseudo_container = 0

    for entity in pipeline_entities or []:
        flags = entity.get("flags") or {}
        source_guid = _clean_text(entity.get("id") or flags.get("element_id"))
        source_name = _best_description(entity.get("name"), flags.get("display_name"), flags.get("description"))
        source_type = _normalise_source_type(flags.get("element_type"))

        for criterion in _iter_entity_criteria(entity):
            criteria_processed += 1
            criterion_flags = criterion.get("flags") or {}
            table_context = _coerce_column_context(criterion_flags.get("logical_table_name"))
            column_context = _coerce_column_context(criterion_flags.get("column_name"))

            resolved_codes = resolve_value_sets(criterion, code_store=code_store)
            resolved_codes_count += len(resolved_codes)

            for code in resolved_codes:
                code_system = _clean_text(code.get("code_system")).upper()
                if code_system == "EMISINTERNAL":
                    skipped_emisinternal += 1
                    continue

                # Drop pseudo-refset containers while keeping pseudo members.
                if bool(code.get("is_pseudo_refset")) and not bool(code.get("is_pseudo_member")):
                    skipped_pseudo_container += 1
                    continue

                emis_guid = _normalise_guid(code.get("code_value") or code.get("emis_guid"))
                if not emis_guid:
                    skipped_missing_guid += 1
                    continue

                mapping = mapping_index.get(emis_guid, {})
                description = _best_description(
                    code.get("display_name"),
                    mapping.get("description"),
                    code.get("valueSet_description"),
                )

                # Capture include_children from source data
                code_include_children = bool(code.get("include_children"))

                row = {
                    "emis_guid": emis_guid,
                    "snomed_code": _normalise_snomed_code(mapping.get("snomed_code")),
                    "description": description,
                    "code_type": _classify_code_type(code, table_context, column_context),
                    "mapping_status": _normalise_mapping_status(mapping.get("mapping_status")),
                    "source_type": source_type,
                    "source_name": source_name,
                    "source_guid": source_guid,
                    "_include_children": code_include_children,
                }

                candidates.append(row)

    deduped: Dict[Any, Dict[str, Any]] = {}
    for row in candidates:
        if mode == "per_source":
            dedupe_key = (row.get("source_guid") or "", row["emis_guid"])
        else:
            dedupe_key = row["emis_guid"]

        existing = deduped.get(dedupe_key)
        if existing is None:
            deduped[dedupe_key] = row
            continue

        # Compare row quality
        existing_score = _score_row_quality(existing)
        new_score = _score_row_quality(row)

        if new_score > existing_score:
            # Better quality row - but preserve include_children=False preference in unique mode
            if mode != "per_source" and existing.get("_include_children") is False and row.get("_include_children") is True:
                row["_include_children"] = False
            deduped[dedupe_key] = row
        elif new_score == existing_score and mode != "per_source":
            # Same quality - prefer include_children=False
            if existing.get("_include_children") is True and row.get("_include_children") is False:
                existing["_include_children"] = False

    rows = list(deduped.values())

    # Build EMIS XML after deduplication (so include_children reflects final decision)
    if include_emis_xml:
        for row in rows:
            row["emis_xml"] = _build_emis_xml_output(
                emis_guid=row["emis_guid"],
                description=row.get("description", ""),
                is_refset=(row.get("code_type") == "refset"),
                include_children=row.get("_include_children", False),
            )

    # Clean up internal fields and hide source columns in unique mode
    for row in rows:
        row.pop("_include_children", None)
        if mode != "per_source":
            row.pop("source_type", None)
            row.pop("source_name", None)
            row.pop("source_guid", None)

    rows.sort(key=lambda r: (r.get("code_type", ""), r.get("emis_guid", "")))

    type_counts = {"clinical": 0, "medication": 0, "refset": 0}
    for row in rows:
        code_type = row.get("code_type")
        if code_type in type_counts:
            type_counts[code_type] += 1

    summary = {
        "view_mode": mode,
        "entities_processed": len(pipeline_entities or []),
        "criteria_processed": criteria_processed,
        "resolved_codes": resolved_codes_count,
        "rows_pre_dedupe": len(candidates),
        "rows_returned": len(rows),
        "unique_codes": len({row["emis_guid"] for row in rows}),
        "mapping_found": sum(1 for row in rows if row.get("mapping_status") == "found"),
        "code_type_counts": type_counts,
        "skipped": {
            "emisinternal": skipped_emisinternal,
            "missing_guid": skipped_missing_guid,
            "pseudo_containers": skipped_pseudo_container,
        },
    }

    return {"rows": rows, "summary": summary}
