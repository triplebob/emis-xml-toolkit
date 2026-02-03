import streamlit as st
from ...theme import success_box, warning_box, info_box
from ....system.session_state import SessionStateKeys
from .codes_common import get_unified_clinical_data, apply_deduplication_mode, render_mode_selector, format_boolean_columns
from ....exports import render_export_controls


def render_pseudo_refset_members_tab(results=None):
    unified_results = get_unified_clinical_data()
    if not unified_results:
        st.write("❌ No analysis data found - please run XML analysis first")
        return

    # Pre-categorised by _category_split: all pseudo members (clinical + medication)
    base_pseudo_members = unified_results.get("pseudo_members", [])

    @st.fragment
    def pseudo_members_display_fragment():
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown("")
            st.markdown("### 📝 Pseudo RefSet Members")
        with col2:
            tab_mode = render_mode_selector(
                "pseudo_members",
                "🔀 Unique Codes: Show each code once\n📍 Per Source: Show codes per search/report",
            )

        # Use common.py for deduplication and filtering
        pseudo_members_data = apply_deduplication_mode(base_pseudo_members, tab_mode)

        if not pseudo_members_data:
            st.markdown(
                success_box("✓\u00a0\u00a0No pseudo-refset member codes found - all codes are either standard refsets (directly usable in EMIS) or standalone codes (also directly usable)."),
                unsafe_allow_html=True,
            )
            return

        if pseudo_members_data:
            import pandas as pd
            
            df = pd.DataFrame(pseudo_members_data)

            if 'Include Children' not in df.columns and 'include_children' in df.columns:
                df = df.rename(columns={'include_children': 'Include Children'})
            if 'Code System' not in df.columns and 'code_system' in df.columns:
                df = df.rename(columns={'code_system': 'Code System'})
            
            # Define columns based on mode
            current_mode = tab_mode
            debug_mode = st.session_state.get(SessionStateKeys.DEBUG_MODE, False)
            
            # Core display columns (flags used for filtering only, not display)
            base_columns = [
                'ValueSet Description', 'EMIS GUID', 'SNOMED Code', 'SNOMED Description',
                'Code Type', 'Mapping Found', 'Include Children', 'Descendants', 'Has Qualifier', 'Code System'
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

            code_type = df.get("is_medication").astype(str).str.lower().isin(["true", "1", "yes"])
            export_df["Code Type"] = code_type.map({True: "Medication", False: "Clinical Code"})
            display_df["Code Type"] = export_df["Code Type"]

            export_df = export_df.rename(columns={'ValueSet Description': 'Parent Pseudo-Refset'})
            display_df = display_df.rename(columns={'ValueSet Description': 'Parent Pseudo-Refset'})
            
            # Add emoji indicators for EMIS GUID and SNOMED Code columns
            if 'EMIS GUID' in display_df.columns:
                display_df['EMIS GUID'] = '🔍 ' + display_df['EMIS GUID'].astype(str)
            if 'SNOMED Code' in display_df.columns:
                display_df['SNOMED Code'] = '⚕️ ' + display_df['SNOMED Code'].astype(str)
            
            # Format boolean columns using shared function
            export_df = format_boolean_columns(export_df)
            display_df = format_boolean_columns(display_df)

            if "SNOMED Description" in display_df.columns:
                display_df = display_df.sort_values(by="SNOMED Description", kind="stable", na_position="last")
            if "SNOMED Description" in export_df.columns:
                export_df = export_df.sort_values(by="SNOMED Description", kind="stable", na_position="last")
            
            # Apply row highlighting based on mapping status
            def highlight_mapping_status(row):
                if row.get('Mapping Found') == 'Found':
                    return ['background-color: #1F4E3D; color: #FAFAFA'] * len(row)  # Success highlighting
                else:
                    return ['background-color: #4A2626; color: #FAFAFA'] * len(row)  # Error highlighting
            
            # Warning box using theme
            st.markdown(
                warning_box("⚠️ Pseudo-refset member codes must be added manually to clinical searches, as their 'refset' is NOT directly usable within EMIS."),
                unsafe_allow_html=True,
            )
            
            st.markdown("")
            # Display with highlighting
            styled_df = display_df.style.apply(highlight_mapping_status, axis=1)
            st.dataframe(styled_df, width="stretch")

            render_export_controls(
                export_df=export_df,
                base_label="Pseudo Refset Members",
                current_mode=current_mode,
                key_prefix="pseudo_members",
            )
        else:
            st.markdown(info_box("No pseudo-refset member codes found in this XML file"), unsafe_allow_html=True)

    pseudo_members_display_fragment()
