import streamlit as st
from ...theme import ThemeColours, success_box
from ....system.session_state import SessionStateKeys
from .codes_common import get_unified_clinical_data, apply_deduplication_mode, render_mode_selector, format_boolean_columns
from ....exports import render_export_controls


def render_clinical_codes_tab(results=None):
    unified_results = get_unified_clinical_data()
    if not unified_results:
        st.write("❌ No analysis data found - please run XML analysis first")
        return

    def _is_truthy(value) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"true", "1", "yes"}

    # Pre-categorised by _category_split: includes pseudo members
    base_clinical = unified_results.get("clinical_codes", [])

    base_clinical_without_pseudo = [
        row
        for row in base_clinical
        if not _is_truthy(row.get("is_pseudomember") or row.get("is_pseudo_member"))
    ]

    @st.fragment
    def clinical_codes_display_fragment():
        col1, col2, col3 = st.columns([4, 1.5, 1])
        with col1:
            st.markdown("")
            st.markdown("### 📋 Standalone Clinical Codes")
        with col2:
            st.markdown("")
            st.markdown("")
            include_pseudo = st.checkbox(
                "Include Pseduo-Refset Members",
                value=True,
                key="include_pseudo_members_clinical",
            )
        with col3:
            tab_mode = render_mode_selector(
                "clinical_codes",
                "🔀 Unique Codes: Show each code once\n📍 Per Source: Show codes per search/report",
            )

        # Use common.py for deduplication and filtering
        filtered_clinical = base_clinical if include_pseudo else base_clinical_without_pseudo
        clinical_data = apply_deduplication_mode(filtered_clinical, tab_mode)

        # Clean display using only common.py pipeline
        if clinical_data:
            from ...theme import info_box
            
            # Info box using theme
            from ...theme import ThemeSpacing
            info_text = (
                "These are clinical codes that are NOT part of any pseudo-refset and can be used directly."
                if not include_pseudo
                else "These clinical codes can be used directly in EMIS clinical searches."
            )
            st.markdown(
                info_box(info_text, margin_bottom=ThemeSpacing.MARGIN_EXTENDED),
                unsafe_allow_html=True
            )
            
            st.markdown("")
            # Simple table display with proper formatting
            import pandas as pd
            df = pd.DataFrame(clinical_data)
            
            
            # Define columns based on mode
            current_mode = tab_mode
            debug_mode = st.session_state.get(SessionStateKeys.DEBUG_MODE, False)
            
            # Core display columns (is_emisinternal used for filtering only, not display)
            # Core display columns using snake_case backend field names
            base_columns = [
                'ValueSet Description', 'EMIS GUID', 'SNOMED Code', 'SNOMED Description', 
                'Mapping Found', 'include_children', 'Descendants', 'Has Qualifier', 'code_system'
            ]
            
            if current_mode == "unique_codes":
                # Unique Codes mode - core columns only
                desired_columns = base_columns.copy()
            else:
                # Per Source mode - core columns + source information  
                desired_columns = base_columns + ['Source Type', 'Source Name', 'Source Container']
            
            # Add debug column if debug mode is enabled
            if debug_mode:
                desired_columns.append('debug_fields')
            
            # Select only the desired columns that exist in the DataFrame
            available_columns = [col for col in desired_columns if col in df.columns]
            export_df = df[available_columns].copy()
            display_df = export_df.copy()

            include_pseudo_column = include_pseudo and "is_pseudomember" in df.columns
            if include_pseudo_column:
                export_df["Is Pseduo Refset Member"] = df["is_pseudomember"].astype(str).str.lower().isin(["true", "1", "yes"])
            
            # Add emoji indicators for EMIS GUID and SNOMED Code columns
            if 'EMIS GUID' in display_df.columns:
                display_df['EMIS GUID'] = '🔍 ' + display_df['EMIS GUID'].astype(str)
            if 'SNOMED Code' in display_df.columns:
                display_df['SNOMED Code'] = '⚕️ ' + display_df['SNOMED Code'].astype(str)
            
            # Rename columns to user-friendly names
            column_mapping = {
                'include_children': 'Include Children',
                'code_system': 'Code System'
            }
            export_df = export_df.rename(columns=column_mapping)
            display_df = display_df.rename(columns=column_mapping)
            
            # Format boolean columns using shared function
            export_df = format_boolean_columns(export_df)
            display_df = format_boolean_columns(display_df)

            if "SNOMED Description" in display_df.columns:
                display_df = display_df.sort_values(by="SNOMED Description", kind="stable", na_position="last")
            if "SNOMED Description" in export_df.columns:
                export_df = export_df.sort_values(by="SNOMED Description", kind="stable", na_position="last")
            
            # Apply row highlighting based on mapping status
            def highlight_mapping_status(row):
                base_row = df.loc[row.name] if row.name in df.index else {}
                is_pseudo_member = bool(base_row.get("is_pseudomember") or base_row.get("is_pseudo_member"))
                mapping = str(row.get('Mapping Found', '')).strip().lower()
                is_found = mapping == 'found'
                if is_pseudo_member and is_found:
                    colour = ThemeColours.AMBER
                elif is_found:
                    colour = ThemeColours.GREEN
                else:
                    colour = ThemeColours.RED
                return [f"background-color: {colour}; color: #FAFAFA"] * len(row)
            
            
            # Display with highlighting
            styled_df = display_df.style.apply(highlight_mapping_status, axis=1)
            st.dataframe(styled_df, width="stretch")

            # Export controls
            render_export_controls(
                export_df=export_df,
                base_label="Clinical Codes",
                current_mode=current_mode,
                key_prefix="clinical_codes",
            )
        else:
            from ...theme import info_box
            if not include_pseudo and base_clinical and not base_clinical_without_pseudo:
                st.markdown(info_box("No standalone clinical codes found in this XML file"), unsafe_allow_html=True)
            else:
                st.markdown(info_box("No clinical codes found in this XML file"), unsafe_allow_html=True)

    clinical_codes_display_fragment()

    include_pseudo = st.session_state.get("include_pseudo_members_clinical", True)
    pseudo_in_clinical = [
        row for row in base_clinical
        if _is_truthy(row.get("is_pseudomember") or row.get("is_pseudo_member"))
    ]
    pseudo_members_count = len(apply_deduplication_mode(pseudo_in_clinical))
    clinical_data = apply_deduplication_mode(base_clinical if include_pseudo else base_clinical_without_pseudo)
    
    if pseudo_members_count > 0 and not include_pseudo:
        from ...theme import warning_box
        st.markdown(
            warning_box(f"⚠️ {pseudo_members_count} clinical codes are part of pseudo-refsets - View and export them from the 'Pseudo-Refset Members' tab."),
            unsafe_allow_html=True,
        )
    elif clinical_data and pseudo_members_count == 0:  # Only show success message if there ARE clinical codes
        st.markdown(
            success_box("✓\u00a0\u00a0All clinical codes are properly mapped! This means all codes in your XML are either standard refsets (directly usable in EMIS) or standalone codes (also directly usable)."),
            unsafe_allow_html=True,
        )
