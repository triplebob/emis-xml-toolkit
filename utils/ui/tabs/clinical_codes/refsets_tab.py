import streamlit as st
from ...theme import info_box, success_box
from ....system.session_state import SessionStateKeys
from .codes_common import get_unified_clinical_data, apply_deduplication_mode, render_mode_selector, format_boolean_columns
from ....exports import render_export_controls


def render_refsets_tab(results=None):
    unified_results = get_unified_clinical_data()
    if not unified_results:
        st.write("❌ No analysis data found - please run XML analysis first")
        return

    # Pre-categorised by _category_split: true refsets only
    base_refsets = unified_results.get("refsets", [])

    @st.fragment
    def refsets_display_fragment():
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown("")
            st.markdown("### 📋 RefSets")
        with col2:
            tab_mode = render_mode_selector(
                "refsets",
                "🔀 Unique Codes: Show each refset once\n📍 Per Source: Show refsets per search/report",
            )

        # Use common.py for deduplication and filtering
        refsets_data = apply_deduplication_mode(base_refsets, tab_mode)

        if refsets_data:
            import pandas as pd
            
            df = pd.DataFrame(refsets_data)

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
                'Mapping Found', 'Include Children', 'Descendants', 'Code System'
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
            
            # Apply row highlighting (refsets use success highlighting)
            def highlight_mapping_status(row):
                return ['background-color: #1F4E3D; color: #FAFAFA'] * len(row)  # Success highlighting
            
            # Info box using theme
            from ...theme import ThemeSpacing
            st.markdown(
                info_box("These are true refsets that EMIS recognizes natively. They can be used directly by their SNOMED code in EMIS clinical searches.", margin_bottom=ThemeSpacing.MARGIN_EXTENDED),
                unsafe_allow_html=True
            )
            
            st.markdown("")
            # Display with highlighting
            styled_df = display_df.style.apply(highlight_mapping_status, axis=1)
            st.dataframe(styled_df, width="stretch")

            render_export_controls(
                export_df=export_df,
                base_label="Refsets",
                current_mode=current_mode,
                key_prefix="refsets",
            )
        else:
            st.markdown(info_box("No refsets found in this XML file"), unsafe_allow_html=True)

    refsets_display_fragment()
