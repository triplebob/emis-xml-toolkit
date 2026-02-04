"""
Refset and pseudo-refset pattern detectors.
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
        id="refset_detection",
        version="1.0.0",
        description="Detects SNOMED refsets and pseudo-refsets in value sets",
        priority=PluginPriority.HIGH,
        tags=["refset", "snomed", "classification"],
    )
)
def detect_refset(ctx: PatternContext):
    if tag_local(ctx.element) != "criterion":
        return None
    ns = ctx.namespaces
    found_refset = False
    pseudo_refset = False

    value_sets = ctx.element.findall(".//valueSet", ns) + ctx.element.findall(".//emis:valueSet", ns)
    for valueset in value_sets:
        values_nodes = valueset.findall(".//values", ns) + valueset.findall(".//emis:values", ns)
        total_values = len(values_nodes)
        refset_flag_nodes = []
        for node in values_nodes:
            refset_node = find_first(node, ns, "isRefset", "emis:isRefset")
            if refset_node is not None and refset_node.text:
                refset_flag_nodes.append(node)
        if refset_flag_nodes:
            found_refset = True
            if total_values > 1:
                pseudo_refset = True

    if not found_refset:
        return None

    return PatternResult(
        id="refset_detection",
        description="Refset or pseudo-refset detected",
        flags={
            "is_refset": True,
            "is_pseudo_refset": pseudo_refset,
            "is_pseudo_member": False,  # Members handled at value level by mapper
        },
        confidence="high" if not pseudo_refset else "medium",
    )
