"""
Logic/negation pattern detectors.
"""

from .registry import register_pattern
from .base import PatternContext, PatternResult, find_first, tag_local


@register_pattern("logic_negation_and_actions")
def detect_logic_and_actions(ctx: PatternContext):
    if tag_local(ctx.element) != "criterion":
        return None
    ns = ctx.namespaces
    negation = find_first(ctx.element, ns, ".//negation", ".//emis:negation")
    member_op = find_first(ctx.element, ns, ".//memberOperator", ".//emis:memberOperator")
    action_true = find_first(ctx.element, ns, ".//actionIfTrue", ".//emis:actionIfTrue")
    action_false = find_first(ctx.element, ns, ".//actionIfFalse", ".//emis:actionIfFalse")

    if all(node is None for node in (negation, member_op, action_true, action_false)):
        return None

    flags = {}
    if negation is not None and negation.text:
        flags["negation"] = negation.text.strip().lower() == "true"
    if member_op is not None and member_op.text:
        flags["member_operator"] = member_op.text.strip().upper()
    if action_true is not None and action_true.text:
        flags["action_if_true"] = action_true.text.strip().upper()
    if action_false is not None and action_false.text:
        flags["action_if_false"] = action_false.text.strip().upper()

    return PatternResult(
        id="logic_negation_and_actions",
        description="Logical operators and actions detected",
        flags=flags,
        confidence="medium",
    )
