"""
Medication pattern detectors (code systems and MHRA alert contexts).
"""

from .registry import register_pattern
from .base import (
    PatternContext,
    PatternResult,
    PluginMetadata,
    PluginPriority,
    find_first,
    tag_local,
)


@register_pattern(
    PluginMetadata(
        id="medication_code_system",
        version="1.0.0",
        description="Identifies medication code systems (SCT_CONST, SCT_DRGGRP, etc.)",
        priority=PluginPriority.HIGH,
        tags=["medication", "code-system", "classification"],
    )
)
def detect_medication_code_system(ctx: PatternContext):
    if tag_local(ctx.element) != "criterion":
        return None
    ns = ctx.namespaces
    code_system = find_first(ctx.element, ns, ".//codeSystem", ".//emis:codeSystem")
    if code_system is None or not code_system.text:
        return None

    system_text = code_system.text.strip().upper()
    medication_systems = ["SCT_CONST", "SCT_DRGGRP", "SCT_PREP", "SCT_APPNAME"]
    if system_text in medication_systems:
        flags = {
            "is_medication_code": True,
            "code_system": system_text,
            "medication_type_flag": _map_med_flag(system_text),
        }
        return PatternResult(
            id="medication_code_system",
            description="Medication code system detected",
            flags=flags,
            confidence="high",
        )

    return None


def _map_med_flag(system_text: str) -> str:
    if system_text == "SCT_CONST":
        return "SCT_CONST (Constituent)"
    if system_text == "SCT_DRGGRP":
        return "SCT_DRGGRP (Drug Group)"
    if system_text == "SCT_PREP":
        return "SCT_PREP (Preparation)"
    if system_text == "SCT_APPNAME":
        return "Brand-specific medication"
    return "Standard Medication"
