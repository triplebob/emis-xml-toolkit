"""
Value set and code system pattern detectors (clinical vs library vs inactive).
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
        id="value_set_properties",
        version="1.0.0",
        description="Detects value set properties (library items, inactive codes)",
        priority=40,  # Between HIGH and NORMAL
        tags=["value-set", "library", "inactive"],
    )
)
def detect_value_set_properties(ctx: PatternContext):
    if tag_local(ctx.element) != "criterion":
        return None
    ns = ctx.namespaces
    value_sets = ctx.element.findall(".//valueSet", ns) + ctx.element.findall(".//emis:valueSet", ns)
    if not value_sets:
        return None

    # Single aggregated result indicating presence of value sets with properties; detailed mapping handled later
    has_library = False
    has_inactive = False

    for valueset in value_sets:
        library = find_first(valueset, ns, ".//libraryItem", ".//emis:libraryItem")
        if library is not None and library.text:
            has_library = True
        inactive = find_first(valueset, ns, ".//inactive", ".//emis:inactive")
        if inactive is not None and inactive.text and inactive.text.strip().lower() == "true":
            has_inactive = True

    flags = {}
    if has_library:
        flags["is_library_item"] = True
    if has_inactive:
        flags["inactive"] = True

    if not flags:
        return None

    return PatternResult(
        id="value_set_properties",
        description="Value set/library/inactive flags detected",
        flags=flags,
        confidence="medium",
    )


@register_pattern(
    PluginMetadata(
        id="value_set_description_handling",
        version="1.0.0",
        description="Handles value set description vs GUID fallback patterns",
        priority=40,  # Between HIGH and NORMAL
        tags=["value-set", "description"],
    )
)
def detect_value_set_description_handling(ctx: PatternContext):
    """
    Detect valueSet patterns for proper description vs displayName separation.

    Pattern: valueSet may have <description> OR fall back to GUID.
    Individual codes have <displayName> which is separate from valueSet description.
    """
    if tag_local(ctx.element) != "criterion":
        return None
    ns = ctx.namespaces
    value_sets = ctx.element.findall(".//valueSet", ns) + ctx.element.findall(".//emis:valueSet", ns)
    if not value_sets:
        return None

    flags = {}
    
    for valueset in value_sets:
        # Check if this valueSet has explicit description
        description = find_first(valueset, ns, "description", "emis:description")
        valueset_id = find_first(valueset, ns, "id", "emis:id")
        
        if description is not None and description.text:
            # Has explicit description
            flags["has_explicit_valueset_description"] = True
        elif valueset_id is not None and valueset_id.text:
            # No description, should use GUID as valueSet description
            flags["use_guid_as_valueset_description"] = True
            
        # Check for individual value displayNames
        values_with_display = valueset.findall(".//values[displayName]", ns) + valueset.findall(".//emis:values[emis:displayName]", ns)
        if values_with_display:
            flags["has_individual_code_display_names"] = True

    if not flags:
        return None

    return PatternResult(
        id="value_set_description_handling", 
        description="ValueSet description pattern detected (explicit description vs GUID fallback)",
        flags=flags,
        confidence="high",
    )
