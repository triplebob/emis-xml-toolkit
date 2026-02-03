"""
Value set parsing using the pipeline.
Extracts code systems, refset/pseudo-refset status, and value-level flags.
Supports early deduplication via CodeStore for performance optimisation.
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional, Set, TYPE_CHECKING
from ...metadata.flag_mapper import map_value_set_flags
from ..namespace_utils import get_child_text_any, get_attr_any, findall_ns, find_ns

if TYPE_CHECKING:
    from ...caching.code_store import CodeStore


def _clean_refset_label(text: Optional[str]) -> str:
    """Clean refset labels to extract just the meaningful name."""
    if not text:
        return ""
    cleaned = text.strip()

    # Remove "Refset:" prefix if present
    if cleaned.lower().startswith("refset"):
        cleaned = cleaned.split(":", 1)[-1].strip()

    # Remove code in brackets at the end
    if "[" in cleaned:
        cleaned = cleaned.split("[", 1)[0].strip()

    return cleaned


def _is_guid_like(text: str) -> bool:
    """Check if text looks like a GUID (contains hyphens and is long)."""
    return (text and
            len(text) > 30 and
            text.count('-') >= 4 and
            all(c.isalnum() or c == '-' for c in text))


def _extract_cluster_code(valueset: ET.Element, values_blocks: List[ET.Element], namespaces: Dict[str, str]) -> str:
    """Extract clusterCode from valueSet or values blocks if present."""
    cluster_code = get_child_text_any(valueset, ["clusterCode"], namespaces)
    if cluster_code:
        return cluster_code
    for block in values_blocks:
        cluster_code = get_child_text_any(block, ["clusterCode"], namespaces)
        if cluster_code:
            return cluster_code
    return ""


def parse_value_sets(
    column_values: List[ET.Element],
    namespaces: Dict[str, str],
    code_store: "CodeStore",
    value_sets_direct: Optional[List[ET.Element]] = None,
    parent_flags: Optional[Dict[str, Any]] = None,
    entity_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Parse value sets that are direct children of the provided columnValue nodes.
    This avoids double counting value sets from nested criteria.

    Codes already in store are not re-parsed (just referenced).
    Unseen codes are added to the store.
    Returns {"keys": [...], "store_mode": True}.
    """
    value_set_keys: List[tuple] = []
    local_seen = set()

    targets: List[ET.Element] = []
    for cv in column_values:
        targets.extend(findall_ns(cv, "valueSet", namespaces))

    if value_sets_direct:
        targets.extend(value_sets_direct)

    for valueset in targets:
        valueset_id = get_child_text_any(valueset, ["id"], namespaces) or get_attr_any(valueset, ["id"])
        valueset_desc = get_child_text_any(valueset, ["description"], namespaces) or get_attr_any(valueset, ["description"])
        code_system = get_child_text_any(valueset, ["codeSystem"], namespaces) or get_attr_any(valueset, ["codeSystem"])

        values_blocks = findall_ns(valueset, "values", namespaces) + findall_ns(valueset, "allValues/values", namespaces)
        cluster_code = _extract_cluster_code(valueset, values_blocks, namespaces)

        # Detect pseudo-refsets by structure or explicit clusterCode
        refset_blocks = 0
        member_blocks = 0
        value_count = 0
        for block in values_blocks:
            value_nodes = findall_ns(block, "value", namespaces)
            if value_nodes:
                value_count += len(value_nodes)
            is_refset_node = find_ns(block, "isRefset", namespaces)
            if is_refset_node is not None and is_refset_node.text and is_refset_node.text.strip().lower() == "true":
                refset_blocks += 1
            elif value_nodes:
                member_blocks += 1

        pseudo_refset_by_refset = refset_blocks > 0 and member_blocks > 0
        pseudo_refset_by_cluster = bool(
            cluster_code
            and cluster_code.strip().lower() == "flattenedcodelist"
            and value_count > 1
        )

        # Determine proper valueSet description - never use GUID
        proper_valueset_desc = ""
        if valueset_desc and not _is_guid_like(valueset_desc):
            proper_valueset_desc = valueset_desc

        # For pseudo_refset_by_refset, extract the refset's display name to use as description for members
        # (since the valueSet description may be empty but the refset code has a meaningful display name)
        pseudo_refset_display_name = ""
        if pseudo_refset_by_refset:
            for block in values_blocks:
                is_refset_node = find_ns(block, "isRefset", namespaces)
                if is_refset_node is not None and is_refset_node.text and is_refset_node.text.strip().lower() == "true":
                    block_display = find_ns(block, "displayName", namespaces)
                    if block_display is not None and block_display.text:
                        pseudo_refset_display_name = _clean_refset_label(block_display.text.strip())
                        break

        base_flags = {
            "valueSet_guid": valueset_id,
            "valueSet_description": proper_valueset_desc,
            "code_system": code_system,
        }
        if cluster_code:
            base_flags["cluster_code"] = cluster_code
        if parent_flags:
            for k, v in parent_flags.items():
                if k not in base_flags:
                    base_flags[k] = v

        # Create a pseudo-refset container for clusterCode-style pseudo-refsets
        if pseudo_refset_by_cluster and valueset_id:
            container_desc = proper_valueset_desc or "No embedded ValueSet name"
            container_display = container_desc if not _is_guid_like(container_desc) else "Pseudo Refset"
            container_flags = dict(base_flags)
            container_flags.update(
                {
                    "code_value": valueset_id,
                    "display_name": container_display,
                    "valueSet_description": container_desc,
                    "is_refset": False,
                    "is_pseudo_refset": True,
                    "is_pseudo_member": False,
                }
            )
            if entity_context is None:
                raise ValueError("Entity context is required for pseudo-refset containers.")
            code_store.add_or_ref(
                container_flags,
                entity_id=entity_context.get("entity_id", ""),
                entity_type=entity_context.get("entity_type", ""),
                entity_name=entity_context.get("entity_name", ""),
                criterion_context=entity_context.get("criterion_context"),
            )

        for block in values_blocks:
            # For refsets, we'll get the cleaned description from the display name later
            block_flags = dict(base_flags)

            is_refset_node = find_ns(block, "isRefset", namespaces)
            if is_refset_node is not None and is_refset_node.text:
                block_flags["is_refset"] = is_refset_node.text.strip().lower() == "true"

            # Set is_emisinternal flag based on code_system at parsing stage
            if code_system and str(code_system).strip().upper() == "EMISINTERNAL":
                block_flags["is_emisinternal"] = True
            else:
                block_flags["is_emisinternal"] = False

            include_children_node = find_ns(block, "includeChildren", namespaces)
            if include_children_node is not None and include_children_node.text:
                block_flags["include_children"] = include_children_node.text.strip().lower() == "true"

            value_nodes = findall_ns(block, "value", namespaces)
            block_display = find_ns(block, "displayName", namespaces)
            if block_display is None:
                block_display = find_ns(valueset, "displayName", namespaces)

            for val in value_nodes:
                # Get code value early for key generation
                code_val = (val.text or "").strip()
                if not code_val:
                    continue

                key = (code_val, valueset_id or "", code_system or "")

                # Local dedup within this parse call
                if key in local_seen:
                    continue
                local_seen.add(key)

                # Check whether this code already exists in the store
                if code_store.has_code(key):
                    # Code already parsed by another entity - just add reference (no fetch needed)
                    if entity_context:
                        code_store.add_reference(
                            key,
                            entity_id=entity_context.get("entity_id", ""),
                            entity_type=entity_context.get("entity_type", ""),
                            entity_name=entity_context.get("entity_name", ""),
                            criterion_context=entity_context.get("criterion_context"),
                        )
                    # If this is a pseudo member context, update the existing entry
                    if pseudo_refset_by_cluster or pseudo_refset_by_refset:
                        # Use proper_valueset_desc, or fall back to pseudo_refset_display_name
                        member_desc = proper_valueset_desc or pseudo_refset_display_name
                        code_store.update_pseudo_member_context(
                            key,
                            valueSet_description=member_desc,
                        )
                    value_set_keys.append(key)
                    continue  # Skip full parsing when the code is already present

                # Full parsing for unseen codes
                entry_flags = map_value_set_flags(val, namespaces, block_flags, block)
                if not entry_flags.get("display_name"):
                    raw_dn = find_ns(val, "displayName", namespaces)
                    if raw_dn is not None and raw_dn.text:
                        entry_flags["display_name"] = raw_dn.text.strip()
                if not entry_flags.get("display_name") and block_display is not None and block_display.text:
                    entry_flags["display_name"] = block_display.text.strip()

                # Clean the display name if it looks like a refset label
                display_name = entry_flags.get("display_name", "")
                if display_name and ("refset" in display_name.lower() or "[" in display_name):
                    cleaned_display = _clean_refset_label(display_name)
                    if cleaned_display:
                        entry_flags["display_name"] = cleaned_display

                # Handle valueSet_description - never use GUID, for refsets use cleaned display name
                if not entry_flags.get("valueSet_description") or _is_guid_like(entry_flags.get("valueSet_description", "")):
                    if entry_flags.get("is_refset") and display_name:
                        # For refsets, use the cleaned display name as valueSet description
                        cleaned_for_vs = _clean_refset_label(display_name)
                        entry_flags["valueSet_description"] = cleaned_for_vs if cleaned_for_vs else "Refset"
                    elif block_flags.get("valueSet_description") and not _is_guid_like(block_flags["valueSet_description"]):
                        entry_flags["valueSet_description"] = block_flags["valueSet_description"]
                    else:
                        # No proper valueSet description available - be explicit about it
                        entry_flags["valueSet_description"] = "No embedded ValueSet name"

                if pseudo_refset_by_cluster:
                    entry_flags["is_pseudo_refset"] = False
                    entry_flags["is_pseudo_member"] = True
                    # Pseudo members inherit valueSet_description from parent pseudo refset
                    member_desc = proper_valueset_desc or pseudo_refset_display_name
                    if member_desc and member_desc != "No embedded ValueSet name":
                        entry_flags["valueSet_description"] = member_desc
                elif pseudo_refset_by_refset:
                    if entry_flags.get("is_refset"):
                        entry_flags["is_pseudo_refset"] = True
                        entry_flags["is_pseudo_member"] = False
                    else:
                        entry_flags["is_pseudo_refset"] = False
                        entry_flags["is_pseudo_member"] = True
                        # Pseudo members inherit valueSet_description from parent pseudo refset
                        member_desc = proper_valueset_desc or pseudo_refset_display_name
                        if member_desc and member_desc != "No embedded ValueSet name":
                            entry_flags["valueSet_description"] = member_desc

                if entity_context is None:
                    raise ValueError("Entity context is required for CodeStore parsing.")
                code_store.add_or_ref(
                    entry_flags,
                    entity_id=entity_context.get("entity_id", ""),
                    entity_type=entity_context.get("entity_type", ""),
                    entity_name=entity_context.get("entity_name", ""),
                    criterion_context=entity_context.get("criterion_context"),
                )
                value_set_keys.append(key)

    return {"keys": value_set_keys, "store_mode": True}


def parse_library_items(
    criterion_elem: ET.Element,
    namespaces: Dict[str, str],
    code_store: "CodeStore",
    entity_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Parse libraryItem entries directly under this criterion (excluding nested criteria).

    Uses early deduplication via CodeStore.
    """
    item_keys: List[tuple] = []
    local_seen: Set[tuple] = set()

    stack = list(criterion_elem)
    while stack:
        node = stack.pop()
        tag_local = node.tag.split('}')[-1] if '}' in node.tag else node.tag
        if tag_local.lower() == "criterion" and node is not criterion_elem:
            continue
        if tag_local == "libraryItem" and node.text:
            guid = node.text.strip()
            key = (guid, "LIBRARY_ITEM", "LIBRARY_ITEM")

            # Local deduplication
            if key in local_seen:
                continue
            local_seen.add(key)

            item_dict = {
                "code_system": "LIBRARY_ITEM",
                "code_value": guid,
                "display_name": f"Library Item: {guid}",
                "is_library_item": True,
                "valueSet_guid": "LIBRARY_ITEM",
            }

            # Check store for early deduplication
            if entity_context is None:
                raise ValueError("Entity context is required for library item parsing.")
            if code_store.has_code(key):
                # Already exists - just add reference (no fetch needed)
                code_store.add_reference(
                    key,
                    entity_id=entity_context.get("entity_id", ""),
                    entity_type=entity_context.get("entity_type", ""),
                    entity_name=entity_context.get("entity_name", ""),
                )
                item_keys.append(key)
            else:
                # Unseen item: add to store
                code_store.add_or_ref(
                    item_dict,
                    entity_id=entity_context.get("entity_id", ""),
                    entity_type=entity_context.get("entity_type", ""),
                    entity_name=entity_context.get("entity_name", ""),
                )
                item_keys.append(key)

        stack.extend(list(node))

    return {"keys": item_keys, "store_mode": True}
