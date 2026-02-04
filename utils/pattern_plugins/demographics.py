"""
Demographics and LSOA pattern detectors.
"""

import re
from .registry import register_pattern
from .base import (
    PatternContext,
    PatternResult,
    PluginMetadata,
    PluginPriority,
    find_first,
    tag_local,
)


LSOA_REGEX = re.compile(r"_LOWER_AREA_", re.IGNORECASE)


@register_pattern(
    PluginMetadata(
        id="demographics_lsoa",
        version="1.0.0",
        description="Detects LSOA and geographic demographics columns",
        priority=PluginPriority.NORMAL,
        tags=["demographics", "lsoa", "geographic"],
    )
)
def detect_demographics_lsoa(ctx: PatternContext):
    if tag_local(ctx.element) != "criterion":
        return None
    ns = ctx.namespaces
    column = find_first(ctx.element, ns, ".//column", ".//emis:column")
    if column is None or not column.text:
        return None

    col_text = column.text.strip()
    if not col_text:
        return None

    if LSOA_REGEX.search(col_text):
        return PatternResult(
            id="demographics_lsoa",
            description="LSOA demographics column detected",
            flags={
                "is_patient_demographics": True,
                "demographics_type": "LSOA",
                "demographics_confidence": "high",
            },
            confidence="high",
        )

    # Broader geo detection
    geo_keywords = ["MSOA", "WARD", "POSTCODE", "AREA", "BOUNDARY"]
    if any(k in col_text.upper() for k in geo_keywords):
        return PatternResult(
            id="demographics_lsoa",
            description="Geographic demographics column detected",
            flags={
                "is_patient_demographics": True,
                "demographics_type": "geographical",
                "demographics_confidence": "medium",
            },
            confidence="medium",
        )

    return None
