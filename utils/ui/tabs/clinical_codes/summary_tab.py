import streamlit as st
from ...theme import info_box, success_box, warning_box, create_info_box_style, ComponentThemes, ThemeColours, ThemeSpacing
from .codes_common import get_unified_clinical_data
from ....system.session_state import SessionStateKeys


def render_summary_tab(results=None):
    """
    Summary tab sourced from the unified pipeline.
    """
    @st.fragment
    def summary_fragment():
        unified_results = get_unified_clinical_data()
        if not unified_results:
            st.markdown(info_box("📋 Upload and process an XML file to view summary statistics."), unsafe_allow_html=True)
            return

        all_codes = unified_results.get("all_codes", [])
        if not all_codes:
            st.markdown(info_box("📋 No clinical content found in this XML."), unsafe_allow_html=True)
            return

        def _is_truthy(value) -> bool:
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"true", "1", "yes"}

        # Filter out EMISINTERNAL codes before bucketing
        filtered_codes = [
            row for row in all_codes
            if str(row.get("code_system", "")).upper() != "EMISINTERNAL"
        ]

        # Buckets
        clinical = [
            row for row in filtered_codes
            if not any([
                _is_truthy(row.get("is_medication")),
                row.get("is_refset"),
                _is_truthy(row.get("is_pseudorefset")),
                _is_truthy(row.get("is_pseudomember")),
            ])
        ]
        meds = [
            row for row in filtered_codes
            if _is_truthy(row.get("is_medication"))
            and not _is_truthy(row.get("is_pseudorefset"))
            and not _is_truthy(row.get("is_pseudomember"))
        ]
        refsets = [
            row for row in filtered_codes
            if row.get("is_refset") and not _is_truthy(row.get("is_pseudorefset"))
        ]
        pseudo_refsets = [row for row in filtered_codes if _is_truthy(row.get("is_pseudorefset"))]
        pseudo_members = [row for row in filtered_codes if _is_truthy(row.get("is_pseudomember"))]
        pseudo_members_clinical = [row for row in pseudo_members if not _is_truthy(row.get("is_medication"))]
        pseudo_members_meds = [row for row in pseudo_members if _is_truthy(row.get("is_medication"))]

        # Source split for clinical (handle report subtypes)
        def _is_report(row):
            stype = str(row.get("source_type", "") or "").lower()
            rtype = str(row.get("report_type", "") or "").lower()
            # Treat any explicit report type or container containing "report" as a report
            return ("report" in stype) or ("report" in rtype and rtype != "search")

        def _is_search(row):
            stype = str(row.get("source_type", "") or "").lower()
            rtype = str(row.get("report_type", "") or "").lower()
            return ("search" in stype) or rtype == "search"

        search_clinical = sum(1 for r in clinical if _is_search(r))
        report_clinical = sum(1 for r in clinical if _is_report(r))
        report_meds = sum(1 for r in meds if _is_report(r))
        report_refsets = sum(1 for r in refsets if _is_report(r))
        report_pseudo_refsets = sum(1 for r in pseudo_refsets if _is_report(r))

        total_clinical = len(clinical)
        total_meds = len(meds)
        total_clinical_display = total_clinical + len(pseudo_members_clinical)
        total_meds_display = total_meds + len(pseudo_members_meds)
        total_items = total_clinical_display + total_meds_display + len(refsets) + len(pseudo_refsets)

        # XML structure breakdown
        entities = st.session_state.get(SessionStateKeys.PIPELINE_ENTITIES) or []
        folders = st.session_state.get(SessionStateKeys.PIPELINE_FOLDERS) or []

        search_count = 0
        report_count = 0
        for ent in entities:
            flags = ent.get("flags", {}) or {}
            etype = flags.get("element_type") or flags.get("source_type")
            if etype == "search":
                search_count += 1
            elif etype in {"list_report", "audit_report", "aggregate_report", "report"}:
                report_count += 1

        total_codes = len(filtered_codes)
        codes_from_searches = sum(
            1 for c in filtered_codes
            if (c.get("Source Type") or c.get("source_type") or "").lower() == "search"
        )
        search_code_pct = (codes_from_searches / total_codes * 100) if total_codes else 0

        st.markdown("")
        st.subheader("📊 XML Breakdown")

        with st.container(horizontal=True, vertical_alignment="distribute", gap="small"):
            with st.container(width="stretch", border=True):
                st.metric("Searches", search_count)
            with st.container(width="stretch", border=True):
                st.metric("Reports", report_count)
            with st.container(width="stretch", border=True):
                st.metric("Folders", len(folders))
            with st.container(width="stretch", border=True):
                st.metric("Codes from Searches", f"{search_code_pct:.1f}%")

        spacer = "\u00a0" * 2
        clinical_delta_parts = []
        if report_clinical > 0:
            clinical_delta_parts.append(f"{report_clinical} from reports")
        if pseudo_members_clinical:
            clinical_delta_parts.append(f"{len(pseudo_members_clinical)} from pseudo-refsets")
        clinical_delta = f"{spacer}|{spacer}".join(clinical_delta_parts) if clinical_delta_parts else None

        meds_delta_parts = []
        if report_meds > 0:
            meds_delta_parts.append(f"{report_meds} from reports")
        if pseudo_members_meds:
            meds_delta_parts.append(f"{len(pseudo_members_meds)} from pseudo-refsets")
        meds_delta = f"{spacer}|{spacer}".join(meds_delta_parts) if meds_delta_parts else None

        refsets_delta = f"{report_refsets} from reports" if report_refsets > 0 else None
        pseudo_refsets_delta = f"{report_pseudo_refsets} from reports" if report_pseudo_refsets > 0 else None

        with st.container(horizontal=True, vertical_alignment="distribute", gap="small"):
            with st.container(width="stretch", height="stretch", border=True):
                st.metric(
                    "Total Clinical Codes",
                    total_clinical_display,
                    delta=clinical_delta,
                    delta_color="off",
                    height="stretch",
                )
                if not clinical_delta:
                    st.markdown('<span class="metric-spacer">&nbsp;</span>', unsafe_allow_html=True)
            with st.container(width="stretch", height="stretch", border=True):
                st.metric(
                    "Total Medications",
                    total_meds_display,
                    delta=meds_delta,
                    delta_color="off",
                    height="stretch",
                )
                if not meds_delta:
                    st.markdown('<span class="metric-spacer">&nbsp;</span>', unsafe_allow_html=True)
            with st.container(width="stretch", height="stretch", border=True):
                st.metric(
                    "True Refsets",
                    len(refsets),
                    delta=refsets_delta,
                    delta_color="off",
                    height="stretch",
                )
                if not refsets_delta:
                    st.markdown('<span class="metric-spacer">&nbsp;</span>', unsafe_allow_html=True)
            with st.container(width="stretch", height="stretch", border=True):
                st.metric(
                    "Pseudo-Refsets",
                    len(pseudo_refsets),
                    delta=pseudo_refsets_delta,
                    delta_color="off",
                    height="stretch",
                )
                if not pseudo_refsets_delta:
                    st.markdown('<span class="metric-spacer">&nbsp;</span>', unsafe_allow_html=True)


        st.markdown("")
        # Row: clinical mapping + pseudo clinical (only if clinical exist)
        if clinical:
            clinical_found = sum(1 for c in clinical if c.get("Mapping Found") == "Found")
            c_row_left, c_row_right = st.columns([6, 2])
            with c_row_left:
                st.markdown(
                    create_info_box_style(
                        ComponentThemes.CLINICAL_MAPPING_SUCCESS,
                        f"Search clinical codes mapping success: {clinical_found}/{total_clinical} "
                        f"({(clinical_found/total_clinical*100):.1f}%)"
                    ),
                    unsafe_allow_html=True,
                )
            with c_row_right:
                pseudo_clinical_count = len(pseudo_members_clinical)
                if pseudo_clinical_count:
                    st.markdown(
                        warning_box(f"📋 {pseudo_clinical_count} clinical codes in pseudo-refsets"),
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        success_box("📋 0 clinical codes in pseudo-refsets"),
                        unsafe_allow_html=True,
                    )

        # Row: medication mapping + pseudo meds
        if meds or pseudo_members_meds:
            meds_found = sum(1 for m in meds if m.get("Mapping Found") == "Found")
            meds_total = len(meds)
            meds_pct = (meds_found / meds_total * 100) if meds_total else None
            m_row_left, m_row_right = st.columns([6, 2])
            with m_row_left:
                meds_label = (
                    f"Standalone medications mapping success: {meds_found}/{meds_total}"
                    if meds_pct is None
                    else f"Standalone medications mapping success: {meds_found}/{meds_total} ({meds_pct:.1f}%)"
                )
                st.markdown(
                    create_info_box_style(
                        ComponentThemes.MEDICATIONS_MAPPING_SUCCESS,
                        meds_label,
                        margin_bottom=ThemeSpacing.MARGIN_EXTENDED,
                    ),
                    unsafe_allow_html=True,
                )
            with m_row_right:
                pseudo_med_count = len(pseudo_members_meds)
                if pseudo_med_count:
                    st.markdown(
                        warning_box(f"📋 {pseudo_med_count} medication codes in pseudo-refsets", margin_bottom=ThemeSpacing.MARGIN_EXTENDED),
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        create_info_box_style(ThemeColours.GREEN, "💊 0 medications in pseudo-refsets", margin_bottom=ThemeSpacing.MARGIN_EXTENDED),
                        unsafe_allow_html=True,
                    )

    summary_fragment()
