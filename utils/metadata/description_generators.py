"""
Shared description helpers for parsing pipeline outputs.

These functions create EMIS-style display strings for clinical codes and value sets.
"""

from typing import Dict, Any, Optional

from .population_describer import describe_population_type


def format_code_description(code: Dict[str, Any]) -> str:
    """
    Build a concise EMIS-style description for a clinical code row.
    """
    display = code.get("Display Name") or code.get("xml_display_name") or ""
    code_val = code.get("EMIS GUID") or code.get("emis_guid") or ""
    code_system = code.get("code_system") or ""
    parts = []
    if display:
        parts.append(display)
    if code_system:
        parts.append(code_system)
    if code_val:
        parts.append(code_val)
    return " | ".join(parts) if parts else ""


def format_value_set_label(code: Dict[str, Any]) -> str:
    """
    Build a label for value set context, reusing EMIS valueSet description when present.
    """
    vs_desc = code.get("ValueSet Description") or code.get("valueSet_description") or ""
    vs_guid = code.get("ValueSet GUID") or code.get("valueSet_guid") or ""
    if vs_desc and vs_guid:
        return f"{vs_desc} ({vs_guid})"
    if vs_desc:
        return vs_desc
    return vs_guid or ""


def format_emis_style_description(code: Dict[str, Any]) -> str:
    """
    Compose an EMIS-style description that blends value set context, code system, and code value.
    """
    parts = []
    vs_label = format_value_set_label(code)
    if vs_label:
        parts.append(vs_label)
    if code.get("code_system"):
        parts.append(code["code_system"])
    if code.get("EMIS GUID"):
        parts.append(str(code["EMIS GUID"]))
    return " | ".join(parts) if parts else ""


def format_base_population(parent_type: Optional[str]) -> str:
    """
    Return friendly population text (delegates to describe_population_type).

    Examples:
    >>> format_base_population("ACTIVE")
    "All currently registered patients"
    >>> format_base_population(None)
    "Custom patient population"
    """
    return describe_population_type(parent_type)


def format_action_indicator(action: Optional[str]) -> str:
    """
    Format action with emoji colour-coding (case-insensitive).

    Examples:
    >>> format_action_indicator("INCLUDE")
    "🟢 Include"
    >>> format_action_indicator("exclude")
    "🔴 Exclude"
    """
    if not action:
        return ""

    value = str(action).strip().lower()
    # Support compatibility EMIS action codes
    mapping = {
        "include": "🟢 Include",
        "select": "🟢 Include",
        "exclude": "🔴 Exclude",
        "reject": "🔴 Exclude",
        "ignore": "⚪ Ignore",
        "next": "🟠 Next rule",
    }
    return mapping.get(value, "")


def _index_to_letters(index: int) -> str:
    """
    Convert 1-based index to Excel-style letters (1→A, 27→AA).

    Examples:
    >>> _index_to_letters(1)
    'A'
    >>> _index_to_letters(27)
    'AA'
    """
    if index <= 0:
        return str(index)
    index -= 1
    quotient, remainder = divmod(index, 26)
    letter = chr(ord("A") + remainder)
    return _index_to_letters(quotient) + letter if quotient else letter


def format_rule_name(name: Optional[str], index: int, use_letters: bool = False) -> str:
    """
    Format criterion name with numeric/letter prefix.

    Examples:
    >>> format_rule_name("Age > 65", 1, use_letters=False)
    "1. Age > 65"
    >>> format_rule_name(None, 3, use_letters=False)
    "Rule 3"
    """
    prefix = _index_to_letters(index) if use_letters else str(index)
    display_name = (name or "").strip()
    if not display_name:
        return f"Rule {prefix}"
    return f"{prefix}. {display_name}"


def format_member_operator(member_test: Optional[str]) -> str:
    """
    Format member operator test results (case-insensitive).

    Examples:
    >>> format_member_operator("EXISTS")
    "Exists"
    >>> format_member_operator("not_exists")
    "Not Exists"
    """
    if not member_test:
        return ""

    value = str(member_test).strip().upper()
    mapping = {
        "EXISTS": "Exists",
        "NOT_EXISTS": "Not Exists",
        "TRUE": "True",
        "FALSE": "False",
    }
    return mapping.get(value, "")
