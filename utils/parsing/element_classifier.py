"""
Element classifier for the parsing pipeline.
Separates searches, list/audit/aggregate reports, and folders.
"""

import xml.etree.ElementTree as ET
from typing import Dict, List
from ..metadata.models import ElementBuckets


class ElementClassifier:
    def __init__(self, namespaces: Dict[str, str]):
        self.namespaces = namespaces or {"emis": "http://www.e-mis.com/emisopen"}

    def _findall(self, root: ET.Element, path: str) -> List[ET.Element]:
        elems = root.findall(path, self.namespaces)
        plain_path = path.replace("emis:", "")
        elems.extend(root.findall(plain_path))
        # Deduplicate by memory id
        seen = set()
        unique = []
        for elem in elems:
            if id(elem) not in seen:
                unique.append(elem)
                seen.add(id(elem))
        return unique

    def classify(self, root: ET.Element) -> ElementBuckets:
        buckets = ElementBuckets()
        # Categorise report elements by contained child nodes
        report_elems = self._findall(root, ".//emis:report")
        list_reports = []
        audit_reports = []
        aggregate_reports = []
        generic_reports = []
        for rep in report_elems:
            if self._has_child(rep, "listReport"):
                list_reports.append(rep)
            elif self._has_child(rep, "auditReport"):
                audit_reports.append(rep)
            elif self._has_child(rep, "aggregateReport"):
                aggregate_reports.append(rep)
            else:
                generic_reports.append(rep)

        buckets.list_reports = list_reports
        buckets.audit_reports = audit_reports
        buckets.aggregate_reports = aggregate_reports

        searches = self._findall(root, ".//emis:search")
        # searches + generic reports (search-like) form search bucket
        buckets.searches = searches + generic_reports

        buckets.folders = self._findall(root, ".//emis:reportFolder")
        return buckets

    def _has_child(self, report_elem: ET.Element, local_tag: str) -> bool:
        return (
            report_elem.find(f"emis:{local_tag}", self.namespaces) is not None
            or report_elem.find(local_tag) is not None
        )
