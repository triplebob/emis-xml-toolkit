import streamlit as st
from ...theme import ThemeColours, info_box
from ....system.session_state import SessionStateKeys
from .codes_common import get_unified_clinical_data, apply_deduplication_mode, render_mode_selector, format_boolean_columns
from ....exports import render_export_controls


def render_medications_tab(results=None):
    unified_results = get_unified_clinical_data()
    if not unified_results:
        st.write("❌ No analysis data found - please run XML analysis first")
        return

    def _is_truthy(value) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"true", "1", "yes"}

    # Pre-categorised by _category_split: includes pseudo members
    base_medications = unified_results.get("medications", [])

    base_medications_without_pseudo = [
        row
        for row in base_medications
        if not _is_truthy(row.get("is_pseudomember") or row.get("is_pseudo_member"))
    ]
    
    @st.fragment
    def medications_display_fragment():
        col1, col2, col3 = st.columns([4, 1.5, 1])
        with col1:
            st.markdown("")
            st.markdown("### 💊 Standalone Medications")
        with col2:
            st.markdown("")
            st.markdown("")
            include_pseudo = st.checkbox(
                "Include Pseduo-Refset Members",
                value=True,
                key="include_pseudo_members_medications",
            )
        with col3:
            tab_mode = render_mode_selector(
                "medications",
                "🔀 Unique Codes: Show each code once\n📍 Per Source: Show codes per search/report",
            )

        # Get medications data with tab-specific mode
        filtered_medications = base_medications if include_pseudo else base_medications_without_pseudo
        medications_data = apply_deduplication_mode(filtered_medications, tab_mode)

        if medications_data:
            import pandas as pd
            
            df = pd.DataFrame(medications_data)
            
            # Define columns based on mode
            current_mode = tab_mode
            debug_mode = st.session_state.get(SessionStateKeys.DEBUG_MODE, False)
            
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
                desired_columns.append('_original_fields')
            
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
            
            # Info box using theme
            from ...theme import ThemeSpacing
            st.markdown(
                info_box("These medications can be used directly as drug codes in EMIS clinical searches.", margin_bottom=ThemeSpacing.MARGIN_EXTENDED),
                unsafe_allow_html=True
            )
            
            st.markdown("")
            # Display with highlighting
            styled_df = display_df.style.apply(highlight_mapping_status, axis=1)
            st.dataframe(styled_df, width="stretch")

            render_export_controls(
                export_df=export_df,
                base_label="Medications",
                current_mode=current_mode,
                key_prefix="medications",
            )
        else:
            if not include_pseudo and base_medications and not base_medications_without_pseudo:
                st.markdown(info_box("No standalone medications found in this XML file"), unsafe_allow_html=True)
            else:
                st.markdown(info_box("No medications found in this XML file"), unsafe_allow_html=True)

    medications_display_fragment()
    
    # Show help sections when medications exist
    if base_medications:
        # Check if we have pseudo-medications in the unified data
        pseudo_medications = [
            row for row in base_medications
            if _is_truthy(row.get("is_pseudomember") or row.get("is_pseudo_member"))
        ]
        
        # Add helpful tooltip information
        with st.expander("ℹ️ Medication Type Flags Help"):
            st.markdown("""
            **Medication Type Flags:**
            - **SCT_CONST** (Constituent): Active ingredients or components
            - **SCT_DRGGRP** (Drug Group): Groups of related medications  
            - **SCT_PREP** (Preparation): Specific medication preparations
            - **Standard Medication**: General medication codes from lookup table
            """)
        
        include_pseudo = st.session_state.get("include_pseudo_members_medications", True)
        if pseudo_medications and not include_pseudo:
            from ...theme import warning_box
            st.markdown(
                warning_box("⚠️ Pseudo-refset medication members are hidden. Enable the toggle above to include them."),
                unsafe_allow_html=True
            )
