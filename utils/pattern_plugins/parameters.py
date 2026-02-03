"""
Detect parameter usage within criteria.
"""

import xml.etree.ElementTree as ET
from typing import List

from .registry import register_pattern
from .base import PatternContext, PatternResult, find_first, tag_local


def _child_text(elem: ET.Element, tag: str, namespaces) -> str:
    node = find_first(elem, namespaces, tag, f"emis:{tag}")
    return node.text.strip() if node is not None and node.text else ""


def _find_parameters(elem: ET.Element, namespaces) -> List[str]:
    names: List[str] = []
    has_global = False
    has_local = False
    for param in elem.findall(".//parameter", namespaces) + elem.findall(".//emis:parameter", namespaces):
        name_attr = param.attrib.get("name") or param.attrib.get("paramName") or ""
        if not name_attr:
            name_attr = _child_text(param, "name", namespaces)
        if name_attr:
            names.append(name_attr.strip())
        elif param.text and param.text.strip():
            names.append(param.text.strip())

        allow_global = param.attrib.get("allowGlobal") or param.attrib.get("allow_global") or _child_text(param, "allowGlobal", namespaces)
        if allow_global and str(allow_global).lower() == "true":
            has_global = True
        else:
            has_local = True
    return names, has_global, has_local


@register_pattern("parameters")
def detect_parameters(ctx: PatternContext):
    if tag_local(ctx.element) != "criterion":
        return None
    param_names, has_global, has_local = _find_parameters(ctx.element, ctx.namespaces)
    if not param_names:
        return None
    return PatternResult(
        id="parameters",
        description="Parameters detected",
        flags={
            "has_parameter": True,
            "parameter_names": param_names,
            "has_global_parameters": has_global,
            "has_local_parameters": has_local,
        },
        confidence="medium",
    )
