"""
Thin UI wrappers for the clinical code tabs.

All business logic lives in utils/ui/tabs/clinical_codes/*.py.
"""

from .summary_tab import render_summary_tab as _render_summary_tab_impl
from .clinicalcodes_tab import render_clinical_codes_tab as _render_clinical_codes_tab_impl
from .medications_tab import render_medications_tab as _render_medications_tab_impl
from .refsets_tab import render_refsets_tab as _render_refsets_tab_impl
from .pseudo_refsets_tab import render_pseudo_refsets_tab as _render_pseudo_refsets_tab_impl
from .pseudo_members_tab import render_pseudo_refset_members_tab as _render_pseudo_refset_members_tab_impl
from ..terminology_server import render_expansion_tab_content as _render_expansion_tab_impl


def render_summary_tab(*_args, **_kwargs):
    """Delegate to summary implementation."""
    _render_summary_tab_impl()


def render_clinical_codes_tab(*_args, **_kwargs):
    """Delegate to the clinical codes implementation."""
    _render_clinical_codes_tab_impl()


def render_medications_tab(*_args, **_kwargs):
    """Delegate to the medications implementation."""
    _render_medications_tab_impl()


def render_refsets_tab(*_args, **_kwargs):
    """Delegate to the refsets implementation."""
    _render_refsets_tab_impl()


def render_pseudo_refsets_tab(*_args, **_kwargs):
    """Delegate to the pseudo-refsets implementation."""
    _render_pseudo_refsets_tab_impl()


def render_pseudo_refset_members_tab(*_args, **_kwargs):
    """Delegate to the pseudo-refset members implementation."""
    _render_pseudo_refset_members_tab_impl()


def render_expansion_tab_content(clinical_data=None):
    """Delegate to expansion tab implementation."""
    if clinical_data is None:
        clinical_data = []
    _render_expansion_tab_impl(clinical_data)


# Note: render_list_reports_tab, render_audit_reports_tab, render_aggregate_reports_tab,
# and render_search_analysis_tab are implemented in report_viewer/ and search_browser/
