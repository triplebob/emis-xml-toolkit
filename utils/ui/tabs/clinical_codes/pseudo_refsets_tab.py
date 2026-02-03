import streamlit as st
from ...theme import ThemeColours, success_box, warning_box
from ....system.session_state import SessionStateKeys
from .codes_common import get_unified_clinical_data, apply_deduplication_mode, render_mode_selector, format_boolean_columns
from ....exports import render_export_controls


def render_pseudo_refsets_tab(results=None):
    unified_results = get_unified_clinical_data()
    if not unified_results:
        st.write("❌ No analysis data found - please run XML analysis first")
        return

    # Pre-categorised by _category_split: only pseudo refset containers
    base_pseudo_refsets = unified_results.get("pseudo_refsets", [])

    @st.fragment
    def pseudo_refsets_display_fragment():
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown("")
            st.markdown("### 🔍 Pseudo RefSets")
        with col2:
            tab_mode = render_mode_selector(
                "pseudo_refsets",
                "🔀 Unique Codes: Show each pseudo-refset once\n📍 Per Source: Show pseudo-refsets per search/report",
            )

        # Use common.py for deduplication and filtering
        pseudo_refsets_data = apply_deduplication_mode(base_pseudo_refsets, tab_mode)

        if not pseudo_refsets_data:
            st.markdown(
                success_box("✓\u00a0\u00a0No pseudo-refsets found - all codes are either standard refsets (directly usable in EMIS) or standalone codes (also directly usable)."),
                unsafe_allow_html=True,
            )
            return

        if pseudo_refsets_data:
            import pandas as pd
            
            df = pd.DataFrame(pseudo_refsets_data)

            if 'Include Children' not in df.columns and 'include_children' in df.columns:
                df = df.rename(columns={'include_children': 'Include Children'})
            if 'Code System' not in df.columns and 'code_system' in df.columns:
                df = df.rename(columns={'code_system': 'Code System'})
            
            # Define columns based on mode
            current_mode = tab_mode
            debug_mode = st.session_state.get(SessionStateKeys.DEBUG_MODE, False)
            
            # Core display columns (flags used for filtering only, not display)
            base_columns = [
                'ValueSet Description', 'EMIS GUID', 'SNOMED Description',
                'Include Children', 'Descendants', 'Has Qualifier', 'Code System'
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
            
            # Apply warning highlighting for pseudo-refsets
            def highlight_mapping_status(row):
                return [f"background-color: {ThemeColours.AMBER}; color: #FAFAFA"] * len(row)  # Warning highlighting
            
            # Warning box using theme
            st.markdown(
                warning_box("⚠️ Pseudo-refsets detected. These containers are not directly usable in EMIS; use member codes instead."),
                unsafe_allow_html=True,
            )
            
            st.markdown("")
            # Display with highlighting
            styled_df = display_df.style.apply(highlight_mapping_status, axis=1)
            st.dataframe(styled_df, width="stretch")

            render_export_controls(
                export_df=export_df,
                base_label="Pseudo Refsets",
                current_mode=current_mode,
                key_prefix="pseudo_refsets",
            )
        else:
            from ...theme import info_box
            st.markdown(info_box("No pseudo-refsets found in this XML file"), unsafe_allow_html=True)

    pseudo_refsets_display_fragment()
