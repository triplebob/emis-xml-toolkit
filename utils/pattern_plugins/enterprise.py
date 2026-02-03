"""
Enterprise/QOF/contract pattern detectors.
"""

from .registry import register_pattern
from .base import PatternContext, PatternResult, find_first


@register_pattern("enterprise_metadata")
def detect_enterprise_metadata(ctx: PatternContext):
    ns = ctx.namespaces
    enterprise_level = find_first(
        ctx.element, ns, ".//enterpriseReportingLevel", ".//emis:enterpriseReportingLevel"
    )
    version_independent_guid = find_first(
        ctx.element, ns, ".//VersionIndependentGUID", ".//emis:VersionIndependentGUID"
    )
    associations = ctx.element.findall(".//association", ns) + ctx.element.findall(".//emis:association", ns)

    if enterprise_level is None and version_independent_guid is None and not associations:
        return None

    flags = {}
    if enterprise_level is not None and enterprise_level.text:
        flags["enterprise_reporting_level"] = enterprise_level.text.strip()
    if version_independent_guid is not None and version_independent_guid.text:
        flags["version_independent_guid"] = version_independent_guid.text.strip()
    if associations:
        flags["organisation_associations"] = []
        seen = set()
        for assoc in associations:
            org = find_first(assoc, ns, ".//organisation", ".//emis:organisation")
            type_elem = find_first(assoc, ns, ".//type", ".//emis:type")
            org_val = org.text.strip() if org is not None and org.text else ""
            type_val = type_elem.text.strip() if type_elem is not None and type_elem.text else ""
            key = (org_val, type_val)
            if key in seen:
                continue
            seen.add(key)
            flags["organisation_associations"].append(
                {
                    "organisation_guid": org_val,
                    "type": type_val,
                }
            )

    return PatternResult(
        id="enterprise_metadata",
        description="Enterprise reporting metadata detected",
        flags=flags,
        confidence="medium",
    )


@register_pattern("qof_contract")
def detect_qof_contract(ctx: PatternContext):
    ns = ctx.namespaces
    qmas = find_first(ctx.element, ns, ".//qmasIndicator", ".//emis:qmasIndicator")
    contract_info = find_first(ctx.element, ns, ".//contractInformation", ".//emis:contractInformation")

    if qmas is None and contract_info is None:
        return None

    flags = {}
    if qmas is not None and qmas.text:
        flags["qmas_indicator"] = qmas.text.strip()

    if contract_info is not None:
        score_needed = find_first(contract_info, ns, ".//scoreNeeded", ".//emis:scoreNeeded")
        target = find_first(contract_info, ns, ".//target", ".//emis:target")
        if score_needed is not None and score_needed.text:
            flags["contract_information_needed"] = score_needed.text.strip().lower() == "true"
        if target is not None and target.text and target.text.isdigit():
            flags["contract_target"] = int(target.text.strip())

    return PatternResult(
        id="qof_contract",
        description="QOF/contract indicators detected",
        flags=flags,
        confidence="medium",
    )
