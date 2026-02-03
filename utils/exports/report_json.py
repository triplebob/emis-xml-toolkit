"""
JSON export for reports.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Tuple, Optional
import json

from .report_export_common import build_report_filename
from ..metadata.report_export_view import build_report_export_view


def build_report_json(
    report: Dict[str, Any],
    id_to_name: Optional[Dict[str, str]] = None,
) -> Tuple[str, str]:
    report_view = build_report_export_view(report, id_to_name)
    payload = {
        "export_metadata": {
            "export_datetime": datetime.now().isoformat(),
            "export_type": "report",
            "report_id": report_view.get("id") or "",
            "report_name": report_view.get("name") or "",
        },
        "report": report_view,
    }
    filename = build_report_filename(report, "report", "json")
    return filename, json.dumps(payload, indent=2, default=str)
