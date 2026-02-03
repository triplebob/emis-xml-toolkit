import streamlit as st
from ....system.session_state import SessionStateKeys


def get_unified_clinical_data():
    """Get clinical data from orchestrated analysis using the centralised cache manager."""
    cache_key_name = 'unified_clinical_data_cache'
    current_file = st.session_state.get(SessionStateKeys.XML_FILENAME)
    cached_entry = st.session_state.get(cache_key_name)

    # Normalise compatibility cache shape
    if cached_entry is not None and not isinstance(cached_entry, dict):
        cached_entry = None
        st.session_state.pop(cache_key_name, None)

    if cached_entry:
        cached_file = cached_entry.get("file_hash")
        cached_data = cached_entry.get("data")
        if cached_data is not None and cached_file and cached_file == current_file:
            return cached_data
    
    # Prefer parsing pipeline clinical codes if present
    pipeline_codes = st.session_state.get(SessionStateKeys.PIPELINE_CODES)
    if pipeline_codes:
        try:
            def _is_truthy(value) -> bool:
                if isinstance(value, bool):
                    return value
                return str(value).strip().lower() in {"true", "1", "yes"}

            def _should_exclude(code: dict) -> bool:
                """Filter out demographics/library items/EMISINTERNAL to match compatibility clinical tabs."""
                code_system = str(code.get("code_system", "")).upper()
                if code_system == "EMISINTERNAL":
                    return True
                # Table/column contexts for demographics
                table_ctx = str(code.get("Table Context") or code.get("table_context") or "").upper()
                column_ctx = str(code.get("Column Context") or code.get("column_context") or "").upper()
                if table_ctx == "PATIENTS":
                    return True
                if column_ctx in {"SEX", "AGE", "DOB", "GENDER"}:
                    return True
                # Library items (GUID-shaped) are not clinical codes
                if _is_truthy(code.get("is_pseudorefset") or code.get("is_pseudo_refset")):
                    return False
                code_val = str(code.get("EMIS GUID") or code.get("emis_guid") or "")
                if code_val and "-" in code_val and len(code_val) == 36:
                    return True
                return False

            filtered_codes = [c for c in pipeline_codes if not _should_exclude(c)]

            def _category_split(codes: list[dict]):
                meds, refsets, pseudo_refs, pseudo_members, clinical = [], [], [], [], []
                for code in codes:
                    is_pseudo_refset = _is_truthy(code.get("is_pseudorefset") or code.get("is_pseudo_refset"))
                    is_pseudo_member = _is_truthy(code.get("is_pseudomember") or code.get("is_pseudo_member"))
                    is_med = _is_truthy(code.get("is_medication") or code.get("is_medication_code"))

                    if is_pseudo_refset:
                        pseudo_refs.append(code)
                        continue
                    if code.get("is_refset") and not is_pseudo_refset:
                        refsets.append(code)
                        continue

                    # Pseudo members go to both pseudo_members AND their type list
                    if is_pseudo_member:
                        pseudo_members.append(code)

                    if is_med:
                        meds.append(code)
                    else:
                        clinical.append(code)
                return meds, refsets, pseudo_refs, pseudo_members, clinical

            meds, refsets, pseudo_refs, pseudo_members, clinical = _category_split(filtered_codes)

            result = {
                "all_codes": filtered_codes,
                "medications": meds,
                "refsets": refsets,
                "pseudo_refsets": pseudo_refs,
                "pseudo_members": pseudo_members,
                "clinical_codes": clinical,
            }
            
            # Cache the result
            st.session_state[cache_key_name] = {
                "file_hash": current_file,
                "data": result,
            }
            return result
            
        except Exception:
            return None
    
    return None


def apply_deduplication_mode(rows: list[dict], mode: str = None) -> list[dict]:
    """Apply deduplication mode to a list of code rows."""
    if mode is None:
        mode = "unique_codes"  # Default mode
    
    def is_emisinternal_code(row):
        """Check if code is EMISINTERNAL by flag."""
        return bool(row.get("is_emisinternal"))
    
    # UI-level filter: drop EMISINTERNAL rows using flag
    filtered = [r for r in rows if not is_emisinternal_code(r)]
    
    # Clean up Source Type values for display
    for row in filtered:
        src_type = row.get('Source Type')
        report_type = row.get('report_type')
        if report_type:
            pretty = report_type.replace('_', ' ').title()
            row['Source Type'] = pretty
        elif src_type:
            # handle raw 'report'/'search' values
            stype = str(src_type).strip()
            if stype.lower().endswith('report'):
                row['Source Type'] = stype.replace('_', ' ').title()
            else:
                row['Source Type'] = stype.capitalize()
    
    def _is_pseudo(row):
        val = row.get("is_pseudomember") or row.get("is_pseudo_member")
        if isinstance(val, bool):
            return val
        return str(val).strip().lower() in {"true", "1", "yes"}

    if mode == "unique_per_entity":
        result = filtered
    else:
        best = {}
        # Deduplicate: prefer pseudo member versions, then highest completeness
        # Sort by: pseudo member status (True first), then completeness score
        for row in sorted(filtered, key=lambda r: (not _is_pseudo(r), -r.get("_completeness_score", 0))):
            key = row.get("EMIS GUID") or row.get("emis_guid")
            if key and key not in best:
                best[key] = row
        result = list(best.values())
    
    
    return result


def format_boolean_columns(display_df):
    """Format boolean columns to display as text.

    Converts to string first to handle all value types (Python bool, numpy bool,
    int, float, str) before mapping to readable True/False text.
    """
    _bool_map = {
        'True': 'True', 'False': 'False',
        '1': 'True', '0': 'False',
        '1.0': 'True', '0.0': 'False',
        'Yes': 'True', 'No': 'False',
        'yes': 'True', 'no': 'False',
    }
    if 'Has Qualifier' in display_df.columns:
        display_df['Has Qualifier'] = display_df['Has Qualifier'].astype(str).map(_bool_map)
    if 'Include Children' in display_df.columns:
        display_df['Include Children'] = display_df['Include Children'].astype(str).map(_bool_map)
    return display_df


def render_mode_selector(unique_key: str, help_text: str) -> str:
    """Render a per-tab mode selector."""
    # Use tab-specific session state
    tab_mode = st.session_state.get(f"tab_mode_{unique_key}", "unique_codes")
    
    selected = st.selectbox(
        "Code Display Mode:",
        options=["unique_codes", "unique_per_entity"],
        format_func=lambda x: {
            "unique_codes": "🔀 Unique Codes",
            "unique_per_entity": "📍 Per Source",
        }[x],
        index=0 if tab_mode == "unique_codes" else 1,
        key=f"mode_selector_{unique_key}",
        help=help_text,
    )
    
    # Update tab-specific mode
    st.session_state[f"tab_mode_{unique_key}"] = selected
    return selected
