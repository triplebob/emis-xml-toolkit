"""
Centralised code store for deduplicated clinical code storage.
Codes are stored once and referenced by multiple entities.
"""

import hashlib
import json
from typing import Dict, Any, List, Tuple, Optional, Set
from dataclasses import dataclass, field

try:
    import streamlit as st
except Exception:  # pragma: no cover - optional in non-UI contexts
    st = None

try:
    from ..system.session_state import SessionStateKeys
except Exception:  # pragma: no cover - fallback for isolated imports
    SessionStateKeys = None

from ..system.debug_output import emit_debug

# Type alias for code keys
CodeKey = Tuple[str, str, str]  # (code_value, valueSet_guid, code_system)


@dataclass(slots=True)
class CodeEntry:
    """Single code entry with full data and source tracking."""
    code_value: str
    valueSet_guid: str
    code_system: str
    display_name: str = ""
    valueSet_description: str = ""
    include_children: bool = False
    is_refset: bool = False
    is_pseudo_refset: bool = False
    is_pseudo_member: bool = False
    is_emisinternal: bool = False
    inactive: bool = False
    legacy_value: str = ""
    cluster_code: str = ""

    # Source tracking - which entities use this code
    source_entities: List[Dict[str, Any]] = field(default_factory=list)
    # Cached set of (entity_id, context_hash) for O(1) duplicate checking
    _source_keys: Set[Tuple[str, str]] = field(default_factory=set, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for compatibility."""
        return {
            "code_value": self.code_value,
            "valueSet_guid": self.valueSet_guid,
            "code_system": self.code_system,
            "display_name": self.display_name,
            "valueSet_description": self.valueSet_description,
            "include_children": self.include_children,
            "is_refset": self.is_refset,
            "is_pseudo_refset": self.is_pseudo_refset,
            "is_pseudo_member": self.is_pseudo_member,
            "is_emisinternal": self.is_emisinternal,
            "inactive": self.inactive,
            "legacy_value": self.legacy_value,
            "cluster_code": self.cluster_code,
            "source_entities": self.source_entities,
        }

    @classmethod
    def from_valueset_dict(cls, vs: Dict[str, Any]) -> "CodeEntry":
        """Create from parsed valueset dictionary."""
        return cls(
            code_value=str(vs.get("code_value", "") or ""),
            valueSet_guid=str(vs.get("valueSet_guid", "") or ""),
            code_system=str(vs.get("code_system", "") or ""),
            display_name=str(vs.get("display_name", "") or ""),
            valueSet_description=str(vs.get("valueSet_description", "") or ""),
            include_children=bool(vs.get("include_children", False)),
            is_refset=bool(vs.get("is_refset", False)),
            is_pseudo_refset=bool(vs.get("is_pseudo_refset", False)),
            is_pseudo_member=bool(vs.get("is_pseudo_member", False)),
            is_emisinternal=bool(vs.get("is_emisinternal", False)),
            inactive=bool(vs.get("inactive", False)),
            legacy_value=str(vs.get("legacy_value", "") or ""),
            cluster_code=str(vs.get("cluster_code", "") or ""),
        )


class CodeStore:
    """
    Central store for deduplicated clinical codes.

    Usage:
        store = CodeStore()
        key = store.add_or_ref(code_dict, entity_context)  # Returns key, skips parse if exists
        store.add_reference(key, entity_id, ...)  # Add ref to existing code
        code = store.get_code(key)
        codes_for_entity = store.get_codes_for_entity(entity_id)
    """

    def __init__(self, enable_debug: Optional[bool] = None) -> None:
        self._codes: Dict[CodeKey, CodeEntry] = {}
        self._entity_index: Dict[str, List[CodeKey]] = {}  # entity_id -> [keys]
        self._enable_debug: Optional[bool] = enable_debug
        self._skip_drop_details: List[Dict[str, Any]] = []
        self._skip_drop_overflow: int = 0
        self._max_skip_drop_details: int = 50
        self._decision_stats: Dict[str, int] = {
            "new_codes_added": 0,
            "references_added": 0,
            "duplicate_references_skipped": 0,
            "missing_reference_keys": 0,
            "pseudo_member_updates": 0,
        }

    def _debug_enabled(self) -> bool:
        """Resolve debug mode from explicit setting or global Streamlit toggle."""
        if self._enable_debug is not None:
            return bool(self._enable_debug)

        if st is None or SessionStateKeys is None:
            return False

        try:
            return bool(st.session_state.get(SessionStateKeys.DEBUG_MODE, False))
        except Exception:
            return False

    def _debug_log(self, message: str, **payload: Any) -> None:
        """Emit structured debug logs when global debug mode is enabled."""
        if not self._debug_enabled():
            return

        if payload:
            emit_debug("code_store", f"{message} | {json.dumps(payload, default=str, sort_keys=True)}")
        else:
            emit_debug("code_store", message)

    def _record_skip_or_drop(self, reason: str, **payload: Any) -> None:
        """Capture bounded details for skipped/dropped events for end-of-run reporting."""
        detail = {"reason": reason}
        detail.update(payload)
        if len(self._skip_drop_details) < self._max_skip_drop_details:
            self._skip_drop_details.append(detail)
        else:
            self._skip_drop_overflow += 1

    def make_key(self, code_value: str, valueSet_guid: str, code_system: str) -> CodeKey:
        """Generate unique key for a code."""
        return (code_value or "", valueSet_guid or "", code_system or "")

    def has_code(self, key: CodeKey) -> bool:
        """Check if code already exists in store."""
        return key in self._codes

    @staticmethod
    def _context_hash(criterion_context: Optional[Dict[str, Any]]) -> str:
        """Generate stable hash for criterion context to detect duplicates."""
        if not criterion_context:
            return ""
        try:
            raw = json.dumps(criterion_context, sort_keys=True, default=str)
            return hashlib.md5(raw.encode()).hexdigest()
        except (TypeError, ValueError):
            return hashlib.md5(str(criterion_context).encode()).hexdigest()

    def _add_source_reference(
        self,
        entry: CodeEntry,
        entity_id: str,
        entity_type: str,
        entity_name: str,
        criterion_context: Optional[Dict[str, Any]],
    ) -> bool:
        """
        Add source reference to entry if not duplicate.
        Returns True if reference was added, False if duplicate.
        """
        context_hash = self._context_hash(criterion_context)
        source_key = (entity_id, context_hash)

        # Check for duplicate using cached set (O(1))
        if source_key in entry._source_keys:
            self._decision_stats["duplicate_references_skipped"] += 1
            return False

        # Build reference dict
        source_ref: Dict[str, Any] = {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "entity_name": entity_name,
        }
        if criterion_context:
            source_ref["criterion_context"] = criterion_context

        # Add reference and update cache
        entry.source_entities.append(source_ref)
        entry._source_keys.add(source_key)
        self._decision_stats["references_added"] += 1
        return True

    def add_or_ref(
        self,
        code_dict: Dict[str, Any],
        entity_id: str,
        entity_type: str,
        entity_name: str = "",
        criterion_context: Optional[Dict[str, Any]] = None,
    ) -> CodeKey:
        """
        Add a code to the store OR just add a reference if it exists.

        Returns the code key for reference storage.
        This is the main method for early deduplication.
        """
        key = self.make_key(
            code_dict.get("code_value", ""),
            code_dict.get("valueSet_guid", ""),
            code_dict.get("code_system", ""),
        )

        if key not in self._codes:
            # First time seeing this code - create entry
            self._codes[key] = CodeEntry.from_valueset_dict(code_dict)
            self._decision_stats["new_codes_added"] += 1

        # Add source reference (handles duplicate detection internally)
        ref_added = self._add_source_reference(
            self._codes[key], entity_id, entity_type, entity_name, criterion_context
        )

        # Only update entity index if reference was actually added
        if ref_added:
            if entity_id not in self._entity_index:
                self._entity_index[entity_id] = []
            if key not in self._entity_index[entity_id]:
                self._entity_index[entity_id].append(key)

        return key

    def add_reference(
        self,
        key: CodeKey,
        entity_id: str,
        entity_type: str,
        entity_name: str = "",
        criterion_context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Add entity reference to existing code without needing full code dict.

        Returns True if reference was added, False if code doesn't exist or duplicate.
        """
        if key not in self._codes:
            self._decision_stats["missing_reference_keys"] += 1
            self._record_skip_or_drop(
                "missing_reference_key",
                key=key,
                entity_id=entity_id,
                entity_type=entity_type,
            )
            return False

        ref_added = self._add_source_reference(
            self._codes[key], entity_id, entity_type, entity_name, criterion_context
        )

        # Only update entity index if reference was actually added
        if ref_added:
            if entity_id not in self._entity_index:
                self._entity_index[entity_id] = []
            if key not in self._entity_index[entity_id]:
                self._entity_index[entity_id].append(key)

        return ref_added

    def update_pseudo_member_context(
        self,
        key: CodeKey,
        valueSet_description: str = "",
    ) -> bool:
        """
        Update an existing code entry with pseudo member context.

        Called when a code is encountered as a pseudo member but already exists in the store.
        Updates is_pseudo_member flag and valueSet_description if the existing one is a fallback label.

        Returns True if entry was updated, False if code doesn't exist.
        """
        if key not in self._codes:
            return False

        entry = self._codes[key]
        entry.is_pseudo_member = True
        self._decision_stats["pseudo_member_updates"] += 1

        # Update valueSet_description if existing is a fallback label and the incoming one is meaningful
        if valueSet_description and valueSet_description != "No embedded ValueSet name":
            if not entry.valueSet_description or entry.valueSet_description == "No embedded ValueSet name":
                entry.valueSet_description = valueSet_description

        return True

    def emit_debug_summary(self) -> None:
        """Emit end-of-run summary and skipped/dropped details when debug mode is enabled."""
        if not self._debug_enabled():
            return

        stats = self.get_stats()
        self._debug_log(
            "summary",
            unique_codes=stats["unique_codes"],
            total_references=stats["total_references"],
            entities_tracked=stats["entities_tracked"],
            new_codes_added=stats["new_codes_added"],
            references_added=stats["references_added"],
            duplicate_references_skipped=stats["duplicate_references_skipped"],
            missing_reference_keys=stats["missing_reference_keys"],
            pseudo_member_updates=stats["pseudo_member_updates"],
            skipped_dropped_detail_count=len(self._skip_drop_details),
            skipped_dropped_detail_overflow=self._skip_drop_overflow,
        )

        for detail in self._skip_drop_details:
            self._debug_log("skipped/dropped detail", **detail)

    def get_code(self, key: CodeKey) -> Optional[Dict[str, Any]]:
        """Get full code data by key."""
        entry = self._codes.get(key)
        return entry.to_dict() if entry else None

    def get_codes_for_entity(self, entity_id: str) -> List[Dict[str, Any]]:
        """Get all codes referenced by an entity."""
        keys = self._entity_index.get(entity_id, [])
        return [self._codes[k].to_dict() for k in keys if k in self._codes]

    def get_all_codes(self) -> List[Dict[str, Any]]:
        """Get all unique codes."""
        return [entry.to_dict() for entry in self._codes.values()]

    def get_stats(self) -> Dict[str, int]:
        """Get store statistics."""
        stats = {
            "unique_codes": len(self._codes),
            "total_references": sum(len(e.source_entities) for e in self._codes.values()),
            "entities_tracked": len(self._entity_index),
        }
        stats.update(self._decision_stats)
        return stats
