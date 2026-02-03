"""
Terminology server expansion workflow for on-demand child code discovery.
Pure business logic with no Streamlit dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Tuple

from .service import ExpansionConfig, get_expansion_service
from .client import ExpansionResult
from ..caching.lookup_cache import get_cached_emis_lookup


@dataclass
class ExpansionSelection:
    """Prepared expansion inputs with source tracking and summary stats."""
    all_expandable_codes: List[Dict[str, Any]]
    expandable_codes: List[Dict[str, Any]]
    unique_codes: Dict[str, Dict[str, Any]]
    code_sources: Dict[str, List[Dict[str, Any]]]
    stats: Dict[str, int]


@dataclass
class ExpansionRunResult:
    """Expanded results plus child code rows and summary rows."""
    expansion_results: Dict[str, ExpansionResult]
    processed_children: List[Dict[str, Any]]
    summary_rows: List[Dict[str, Any]]
    total_child_codes: int
    successful_expansions: int
    include_inactive: bool
    lookup_stats: Dict[str, Any]
    error: Optional[str] = None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y"}


def _is_expandable_entry(entry: Dict[str, Any]) -> bool:
    include_children = entry.get("include_children")
    if _truthy(include_children):
        return True

    for field in ("Include Children", "includechildren", "include_children"):
        if field in entry and _truthy(entry.get(field)):
            return True

    return False


def _is_snomed_entry(entry: Dict[str, Any]) -> bool:
    code_system = str(entry.get("code_system") or "").upper()
    return code_system in {"SNOMED_CONCEPT", "SNOMED"}


def _normalise_snomed_code(entry: Dict[str, Any]) -> str:
    raw = entry.get("SNOMED Code", "") or entry.get("snomed_code", "")
    return str(raw).strip()


def prepare_expansion_selection(
    clinical_data: List[Dict[str, Any]],
    filter_zero_descendants: bool = True,
) -> ExpansionSelection:
    """
    Prepare expansion candidates, deduplicate by SNOMED code,
    and gather source tracking.
    """
    clinical_data = clinical_data or []
    all_expandable = [
        entry for entry in clinical_data
        if _is_expandable_entry(entry) and _is_snomed_entry(entry)
    ]
    unique_codes: Dict[str, Dict[str, Any]] = {}
    code_sources: Dict[str, List[Dict[str, Any]]] = {}

    for entry in all_expandable:
        snomed_code = _normalise_snomed_code(entry)
        if not snomed_code:
            continue

        if snomed_code not in code_sources:
            code_sources[snomed_code] = []
            unique_codes[snomed_code] = entry

        code_sources[snomed_code].append({
            "Source Type": entry.get("Source Type", "Unknown"),
            "Source Name": entry.get("Source Name", "Unknown"),
            "Source Container": entry.get("Source Container", "Unknown"),
            "SNOMED Description": entry.get("SNOMED Description", ""),
            "Descendants": entry.get("Descendants", "")
        })

    zero_descendant_count = sum(
        1 for code in unique_codes.values()
        if str(code.get("Descendants", "")).strip() == "0"
    )

    if filter_zero_descendants:
        expandable_codes = [
            code for code in unique_codes.values()
            if str(code.get("Descendants", "")).strip() != "0"
        ]
    else:
        expandable_codes = list(unique_codes.values())

    stats = {
        "original_count": len(all_expandable),
        "unique_count": len(unique_codes),
        "dedupe_savings": len(all_expandable) - len(unique_codes),
        "zero_descendant_count": zero_descendant_count,
        "remaining_count": len(expandable_codes),
    }

    return ExpansionSelection(
        all_expandable_codes=all_expandable,
        expandable_codes=expandable_codes,
        unique_codes=unique_codes,
        code_sources=code_sources,
        stats=stats,
    )


def _ensure_credentials(service, client_id: Optional[str], client_secret: Optional[str]) -> Optional[str]:
    if service.client:
        return None
    if not client_id or not client_secret:
        return "NHS Terminology Server credentials not configured."
    service.configure_credentials(client_id, client_secret)
    return None


def run_expansion(
    selection: ExpansionSelection,
    lookup_df,
    snomed_code_col: Optional[str],
    emis_guid_col: Optional[str],
    version_info: Optional[Dict[str, Any]],
    include_inactive: bool = False,
    use_cache: bool = True,
    max_workers: int = 10,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
) -> ExpansionRunResult:
    """Run expansion for prepared codes and build child code rows."""
    if not selection.expandable_codes:
        return ExpansionRunResult(
            expansion_results={},
            processed_children=[],
            summary_rows=[],
            total_child_codes=0,
            successful_expansions=0,
            include_inactive=include_inactive,
            lookup_stats={},
            error="No expandable codes found."
        )

    service = get_expansion_service()
    credential_error = _ensure_credentials(service, client_id, client_secret)
    if credential_error:
        return ExpansionRunResult(
            expansion_results={},
            processed_children=[],
            summary_rows=[],
            total_child_codes=0,
            successful_expansions=0,
            include_inactive=include_inactive,
            lookup_stats={},
            error=credential_error,
        )

    try:
        cached_data = get_cached_emis_lookup(lookup_df, snomed_code_col, emis_guid_col, version_info)
    except Exception as exc:
        return ExpansionRunResult(
            expansion_results={},
            processed_children=[],
            summary_rows=[],
            total_child_codes=0,
            successful_expansions=0,
            include_inactive=include_inactive,
            lookup_stats={},
            error=f"EMIS lookup cache not available: {exc}",
        )
    if cached_data is None:
        return ExpansionRunResult(
            expansion_results={},
            processed_children=[],
            summary_rows=[],
            total_child_codes=0,
            successful_expansions=0,
            include_inactive=include_inactive,
            lookup_stats={},
            error="EMIS lookup cache not available.",
        )

    emis_lookup = cached_data.get("lookup_mapping", {}) or {}
    lookup_records = cached_data.get("lookup_records", {}) or {}

    codes = []
    for entry in selection.expandable_codes:
        snomed_code = _normalise_snomed_code(entry)
        if snomed_code:
            codes.append(snomed_code)
    codes = sorted(set(codes))

    config = ExpansionConfig(
        include_inactive=include_inactive,
        use_cache=use_cache,
        max_workers=max_workers
    )

    results = service.expand_codes_batch(codes, config, progress_callback)

    processed_children = _build_child_rows(results, selection.code_sources, emis_lookup)
    summary_rows = build_expansion_summary_rows(results, selection.expandable_codes, lookup_records)

    successful_expansions = sum(1 for result in results.values() if not result.error)
    lookup_stats = _build_lookup_stats(processed_children)

    return ExpansionRunResult(
        expansion_results=results,
        processed_children=processed_children,
        summary_rows=summary_rows,
        total_child_codes=len(processed_children),
        successful_expansions=successful_expansions,
        include_inactive=include_inactive,
        lookup_stats=lookup_stats,
    )


def _build_child_rows(
    results: Dict[str, ExpansionResult],
    code_sources: Dict[str, List[Dict[str, Any]]],
    emis_lookup: Dict[str, str],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for parent_code, result in results.items():
        if result.error:
            continue

        parent_sources = code_sources.get(parent_code, [])
        for child in result.children:
            child_code = str(child.code).strip()
            emis_guid = emis_lookup.get(child_code) or "Not in EMIS lookup table"
            if parent_sources:
                for source in parent_sources:
                    rows.append({
                        "Parent Code": parent_code,
                        "Parent Display": result.source_display,
                        "Child Code": child.code,
                        "Child Display": child.display,
                        "EMIS GUID": emis_guid,
                        "Inactive": bool(child.inactive),
                        "Source Type": source.get("Source Type", "Unknown"),
                        "Source Name": source.get("Source Name", "Unknown"),
                        "Source Container": source.get("Source Container", "Unknown"),
                    })
            else:
                rows.append({
                    "Parent Code": parent_code,
                    "Parent Display": result.source_display,
                    "Child Code": child.code,
                    "Child Display": child.display,
                    "EMIS GUID": emis_guid,
                    "Inactive": bool(child.inactive),
                    "Source Type": "Unknown",
                    "Source Name": "Unknown",
                    "Source Container": "Unknown",
                })

    return rows


def _build_lookup_stats(child_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_count = len(child_rows)
    matched_count = len([row for row in child_rows if row.get("EMIS GUID") != "Not in EMIS lookup table"])
    coverage_pct = (matched_count / total_count * 100) if total_count else 0
    return {
        "total_child_codes": total_count,
        "emis_guid_found": matched_count,
        "emis_guid_missing": total_count - matched_count,
        "coverage_pct": coverage_pct,
    }


def build_expansion_summary_rows(
    expansions: Dict[str, ExpansionResult],
    original_codes: Optional[List[Dict[str, Any]]] = None,
    lookup_records: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Build summary rows for expansion results."""
    original_descriptions: Dict[str, str] = {}
    original_descendants: Dict[str, str] = {}

    if original_codes:
        for code_entry in original_codes:
            snomed_code = _normalise_snomed_code(code_entry)
            if snomed_code:
                original_descriptions[snomed_code] = code_entry.get("SNOMED Description", snomed_code)
                original_descendants[snomed_code] = str(code_entry.get("Descendants", "N/A"))

    summary_rows: List[Dict[str, Any]] = []
    for code, result in expansions.items():
        description = original_descriptions.get(code, result.source_display)
        emis_child_count = original_descendants.get(code, "N/A")
        if lookup_records and code in lookup_records:
            descendants = lookup_records[code].get("descendants", "")
            if descendants:
                emis_child_count = str(descendants)

        term_server_count = len(result.children)

        if result.error:
            if "does not exist" in result.error.lower() or "not found" in result.error.lower() or "422" in str(result.error):
                result_status = "Unmatched - No concept found on terminology server for that ID"
            elif "connection" in result.error.lower() or "network" in result.error.lower():
                result_status = "Error - Failed to connect to terminology server"
            else:
                result_status = f"Error - {result.error}"
        elif term_server_count > 0:
            result_status = f"Matched - Found {term_server_count} children"
        elif result.source_display and result.source_display != code and result.source_display != "Unknown":
            result_status = "Matched - Valid concept but has no children"
        else:
            result_status = "Unmatched - No concept found on terminology server for that ID"

        summary_rows.append({
            "SNOMED Code": code,
            "Description": description,
            "EMIS Child Count": emis_child_count,
            "Term Server Child Count": term_server_count,
            "Result Status": result_status,
            "Expanded At": result.expansion_timestamp.strftime("%Y-%m-%d %H:%M:%S")
        })

    return summary_rows


def _is_inactive(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in {"true", "1", "yes"}


def prepare_child_codes_view(
    child_rows: List[Dict[str, Any]],
    search_term: str = "",
    show_inactive: bool = True,
    view_mode: str = "unique",
) -> Dict[str, Any]:
    """
    Filter and sort child rows for display.
    view_mode: "unique" or "per_source".
    """
    filtered = list(child_rows)
    term = search_term.strip().lower()

    if term:
        filtered = [
            row for row in filtered
            if term in str(row.get("Child Code", "")).lower()
            or term in str(row.get("Child Display", "")).lower()
            or term in str(row.get("Parent Code", "")).lower()
            or term in str(row.get("Parent Display", "")).lower()
            or term in str(row.get("Source Name", "")).lower()
        ]

    if not show_inactive:
        filtered = [row for row in filtered if not _is_inactive(row.get("Inactive"))]

    mode = (view_mode or "unique").strip().lower()
    if mode == "unique":
        seen = set()
        unique_rows = []
        for row in filtered:
            key = (row.get("Parent Code"), row.get("Child Code"))
            if key in seen:
                continue
            seen.add(key)
            unique_rows.append(row)
        filtered = sorted(unique_rows, key=lambda r: (r.get("Parent Code", ""), r.get("Child Code", "")))
    else:
        filtered = sorted(
            filtered,
            key=lambda r: (
                r.get("Source Type", "Unknown"),
                r.get("Source Name", "Unknown"),
                r.get("Parent Code", ""),
                r.get("Child Code", ""),
            ),
        )

    has_source_tracking = any(
        row.get("Source Type") or row.get("Source Name") or row.get("Source Container")
        for row in child_rows
    )

    return {
        "rows": filtered,
        "total_count": len(child_rows),
        "filtered_count": len(filtered),
        "has_source_tracking": has_source_tracking,
    }


def build_child_code_exports(
    child_rows: List[Dict[str, Any]],
    view_mode: str = "unique",
) -> Dict[str, List[Dict[str, Any]]]:
    """Build export filters for child codes."""
    exports: Dict[str, List[Dict[str, Any]]] = {}
    exports["All Child Codes"] = list(child_rows)
    exports["Only Matched"] = [row for row in child_rows if row.get("EMIS GUID") != "Not in EMIS lookup table"]
    exports["Only Unmatched"] = [row for row in child_rows if row.get("EMIS GUID") == "Not in EMIS lookup table"]

    return exports


def build_child_code_export_options(
    child_rows: List[Dict[str, Any]],
    view_mode: str = "unique",
) -> Tuple[List[str], Dict[str, int]]:
    """Return export filter options and summary counts."""
    total_count = len(child_rows)
    matched_count = len([row for row in child_rows if row.get("EMIS GUID") != "Not in EMIS lookup table"])
    unmatched_count = total_count - matched_count

    search_count = len([
        row for row in child_rows
        if "search" in str(row.get("Source Type", "")).lower()
    ])
    report_count = len([
        row for row in child_rows
        if "search" not in str(row.get("Source Type", "")).lower()
        and row.get("Source Type", "") != "Unknown"
    ])

    options = ["All Child Codes"]
    if matched_count > 0 and unmatched_count > 0:
        options.extend(["Only Matched", "Only Unmatched"])

    stats = {
        "total_count": total_count,
        "matched_count": matched_count,
        "unmatched_count": unmatched_count,
        "search_count": search_count,
        "report_count": report_count,
    }

    return options, stats


def build_hierarchical_json(child_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create hierarchical JSON with parent-child structure."""
    hierarchy: Dict[str, Any] = {}
    for child in child_rows:
        parent = str(child.get("Parent Code", "")).strip()
        if not parent:
            continue
        if parent not in hierarchy:
            hierarchy[parent] = {
                "parent_display": child.get("Parent Display", ""),
                "children": [],
                "_seen_codes": set(),
            }
        child_code = str(child.get("Child Code", "")).strip()
        if not child_code or child_code in hierarchy[parent]["_seen_codes"]:
            continue
        hierarchy[parent]["_seen_codes"].add(child_code)
        hierarchy[parent]["children"].append({
            "code": child_code,
            "display": child.get("Child Display", ""),
            "emis_guid": child.get("EMIS GUID"),
            "inactive": _is_inactive(child.get("Inactive")),
        })

    return {
        "export_metadata": {
            "export_type": "terminology_expansion",
            "export_timestamp": datetime.now().isoformat(),
            "source": "ClinXML EMIS XML Converter",
            "total_parents": len(hierarchy),
            "total_children": len(child_rows)
        },
        "hierarchy": {
            key: {k: v for k, v in value.items() if k != "_seen_codes"}
            for key, value in hierarchy.items()
        }
    }


def build_emis_xml_export(child_rows: List[Dict[str, Any]]) -> str:
    """Create EMIS-compatible XML for child codes."""
    def escape_xml(text: str) -> str:
        if text is None:
            return ""
        text = str(text)
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_lines.append('<valueSet>')
    xml_lines.append('  <description>Expanded Child Codes from NHS Terminology Server</description>')
    xml_lines.append('  <codeSystem>SNOMED</codeSystem>')
    xml_lines.append('  <values>')

    for row in child_rows:
        guid = row.get("EMIS GUID")
        if not guid or guid == "Not in EMIS lookup table":
            continue
        guid_text = str(guid).strip()
        display = escape_xml(row.get("Child Display", ""))
        xml_lines.append('    <values>')
        xml_lines.append(f'      <value>{guid_text}</value>')
        xml_lines.append(f'      <displayName>{display}</displayName>')
        xml_lines.append('      <includeChildren>false</includeChildren>')
        xml_lines.append('    </values>')

    xml_lines.append('  </values>')
    xml_lines.append('</valueSet>')

    return "\n".join(xml_lines)


def expand_single_code(
    snomed_code: str,
    include_inactive: bool = False,
    use_cache: bool = True,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
) -> Tuple[Optional[ExpansionResult], Optional[str]]:
    """Expand a single SNOMED code using the shared service."""
    snomed_code = (snomed_code or "").strip()
    if not snomed_code:
        return None, "SNOMED code is required."
    service = get_expansion_service()
    credential_error = _ensure_credentials(service, client_id, client_secret)
    if credential_error:
        return None, credential_error

    config = ExpansionConfig(
        include_inactive=include_inactive,
        use_cache=use_cache,
        max_workers=1
    )
    results = service.expand_codes_batch([snomed_code], config)
    return results.get(snomed_code), None


def lookup_concept_display(
    snomed_code: str,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Lookup a SNOMED concept display name without expanding children."""
    snomed_code = (snomed_code or "").strip()
    if not snomed_code:
        return None, "SNOMED code is required."
    service = get_expansion_service()
    credential_error = _ensure_credentials(service, client_id, client_secret)
    if credential_error:
        return None, credential_error
    if not service.client:
        return None, "Terminology server client not configured."
    display, error = service.client.lookup_concept(snomed_code)
    if error:
        return None, error
    return display, None
