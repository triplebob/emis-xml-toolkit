"""
Canonical metadata models for the parsing pipeline.
These are shared across parsing, UI, and export layers.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
import hashlib
import xml.etree.ElementTree as ET


def _hash_text(text: str) -> str:
    """Stable content hash for caching and provenance."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


@dataclass
class DocumentMetadata:
    document_id: str
    creation_time: Optional[str]
    source_hash: str
    source_name: Optional[str] = None
    size_bytes: Optional[int] = None

    @classmethod
    def from_root(cls, root: ET.Element, raw_xml: str, source_name: Optional[str] = None) -> "DocumentMetadata":
        def _find_text(tag: str) -> Optional[str]:
            elem = root.find(tag) or root.find(f".//{tag}")
            return elem.text if elem is not None else None

        return cls(
            document_id=_find_text("id") or "Unknown",
            creation_time=_find_text("creationTime"),
            source_hash=_hash_text(raw_xml),
            source_name=source_name,
            size_bytes=len(raw_xml.encode("utf-8")) if raw_xml else None,
        )


@dataclass
class ElementBuckets:
    searches: List[ET.Element] = field(default_factory=list)
    list_reports: List[ET.Element] = field(default_factory=list)
    audit_reports: List[ET.Element] = field(default_factory=list)
    aggregate_reports: List[ET.Element] = field(default_factory=list)
    folders: List[ET.Element] = field(default_factory=list)

    def total_reports(self) -> int:
        return len(self.searches) + len(self.list_reports) + len(self.audit_reports) + len(self.aggregate_reports)


@dataclass
class ParsedDocument:
    metadata: DocumentMetadata
    buckets: ElementBuckets
    namespaces: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": asdict(self.metadata),
            "buckets": {
                "searches": len(self.buckets.searches),
                "list_reports": len(self.buckets.list_reports),
                "audit_reports": len(self.buckets.audit_reports),
                "aggregate_reports": len(self.buckets.aggregate_reports),
                "folders": len(self.buckets.folders),
            },
            "namespaces": self.namespaces,
        }
