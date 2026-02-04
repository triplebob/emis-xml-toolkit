"""
Population reference pattern detectors.
"""

from .registry import register_pattern
from .base import (
    PatternContext,
    PatternResult,
    PluginMetadata,
    PluginPriority,
)


@register_pattern(
    PluginMetadata(
        id="population_references",
        version="1.0.0",
        description="Detects population criterion references by GUID",
        priority=PluginPriority.NORMAL,
        tags=["population", "reference"],
    )
)
def detect_population_references(ctx: PatternContext):
    ns = ctx.namespaces
    pop_refs = ctx.element.findall(".//populationCriterion", ns) + ctx.element.findall(".//emis:populationCriterion", ns)
    if not pop_refs:
        return None

    refs = []
    for ref in pop_refs:
        guid = ref.get("reportGuid") or ""
        if guid:
            refs.append(guid)

    if not refs:
        return None

    return PatternResult(
        id="population_references",
        description="Population references detected",
        flags={"population_reference_guid": refs},
        confidence="medium",
    )
