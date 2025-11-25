"""
Search Rule Visualizer UI Components
Creates interactive visualization of EMIS search rules and logic
"""

import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime
from .search_rule_analyzer import SearchRuleAnalysis
from .common_structures import CriteriaGroup
from .linked_criteria_handler import filter_top_level_criteria, has_linked_criteria
from ..xml_parsers.criterion_parser import SearchCriterion, check_criterion_parameters
from ..core import FolderManager, SearchManager
from ..core.session_state import SessionStateKeys
from ..utils.text_utils import pluralize_unit, format_operator_text
from ..ui.theme import info_box, success_box, warning_box, error_box
# Export functionality moved to centralized UIExportManager
from .linked_criteria_handler import (
    render_linked_criteria, 
    filter_linked_value_sets_from_main,
    filter_linked_column_filters_from_main
)
from .shared_render_utils import _render_rule_step, _render_rule_step_content, _is_parent_report, _render_report_type_specific_info
from ..ui.rendering_utils import apply_custom_styling


def _natural_sort_key(text):
    """
    Natural sort key that handles numbers and letters properly
    Numbers come first (1, 2, 3...) then letters (A, B, C...)
    """
    # Extract the leading number or letter from the name
    match = re.match(r'^(\d+)', text)
    if match:
        # If starts with number, sort by number first
        return (0, int(match.group(1)), text)
    else:
        # If starts with letter, sort after all numbers
        return (1, 0, text.lower())


def _lookup_snomed_for_ui(emis_guid: str) -> str:
    """Lookup SNOMED code for given EMIS GUID using XML-specific cached clinical data"""
    if not emis_guid or emis_guid == 'N/A':
        return 'N/A'
    
    # Use the XML-specific cached clinical data instead of going back to lookup table
    from ..ui.tabs.tab_helpers import get_unified_clinical_data
    
    try:
        unified_results = get_unified_clinical_data()
        if not unified_results:
            return 'Analysis unavailable'
        
        # Search all clinical data categories for this EMIS GUID
        for data_category in ['clinical_codes', 'medications', 'refsets', 'pseudo_refsets', 'clinical_pseudo_members']:
            if data_category in unified_results:
                for item in unified_results[data_category]:
                    if item.get('EMIS GUID', '').strip() == str(emis_guid).strip():
                        return item.get('SNOMED Code', 'Not found')
        
        return 'Not found'
    except Exception:
        return 'Lookup error'
# Imports moved to top of file

# render_search_rule_tab function moved to ui_tabs.py as render_xml_structure_tabs
# This module now only contains the individual rendering functions

def render_detailed_rules(reports, analysis=None):
    """
    Render detailed breakdown of all rules with folder navigation
    
    Args:
        reports: List of SearchReport objects (should be searches only, no list reports)
        analysis: Analysis object containing folder information (optional, will get from session state if not provided)
    """
    
    # Apply custom styling for better UI contrast
    apply_custom_styling()
    
    if not reports:
        st.markdown(info_box("No detailed rules found"), unsafe_allow_html=True)
        return
    
    # Use provided analysis or get from session state
    if analysis is None:
        analysis = st.session_state.get(SessionStateKeys.SEARCH_ANALYSIS)
    
    if not analysis:
        st.markdown(warning_box("⚠️ Analysis data missing - please refresh the page"), unsafe_allow_html=True)
        return
    
    # Ensure folders exist (orchestrated analysis should have this)
    if not hasattr(analysis, 'folders'):
        analysis.folders = []  # Set empty folders list for backward compatibility
    
    
    # Build folder hierarchy for dropdown navigation
    folder_map = {f.id: f for f in analysis.folders} if analysis.folders else {}
    
    folder_hierarchy = FolderManager.build_folder_hierarchy_for_dropdown(folder_map, reports, st.session_state.get(SessionStateKeys.DEBUG_MODE, False))
    
    st.markdown("**📋 Navigate to Search for Detailed Rule Analysis:**")
    
    # Three-column layout: folder selector, search selector, export buttons
    col1, col2, col3 = st.columns([3, 3, 1.5])
    
    
    with col1:
        
        if folder_hierarchy:
            # Folder selection when folders exist
            folder_options = ["All Folders"] + list(folder_hierarchy.keys())
            
            selected_folder_path = st.selectbox(
                "📁 Select Folder",
                options=folder_options,
                key="detailed_rules_folder"
            )
        else:
            # No folders - show message
            st.selectbox(
                "📁 Select Folder",
                ["All Searches (No Folders)"],
                disabled=True,
                key="detailed_rules_folder_none"
            )
            selected_folder_path = "All Searches (No Folders)"
    
    with col2:
        
        # Get searches based on folder selection
        if folder_hierarchy and selected_folder_path != "All Folders" and selected_folder_path in folder_hierarchy:
            folder_searches = folder_hierarchy[selected_folder_path]['searches']
        else:
            # All searches (either no folders or "All Folders" selected)
            folder_searches = reports
        
        
        # Search selection dropdown
        if folder_searches:
            search_options = []
            for i, search in enumerate(folder_searches):
                clean_name = SearchManager.clean_search_name(search.name)
                classification = "🔍"  # All items in search analysis are searches
                search_options.append(f"{classification} {clean_name}")
            
            
            selected_search_index = st.selectbox(
                "🔍 Select Search for Details",
                options=range(len(search_options)),
                format_func=lambda x: search_options[x] if x < len(search_options) else "Select a search...",
                key="detailed_rules_search"
            )
        else:
            st.selectbox(
                "🔍 Select Search for Details",
                ["No searches in selected folder"],
                disabled=True,
                key="detailed_rules_search_empty"
            )
            selected_search_index = None
    
    # Determine selected search for export buttons
    selected_search = None
    if selected_search_index is not None and folder_searches:
        selected_search = folder_searches[selected_search_index]
    
    with col3:
        # All export buttons in one column
        # Master JSON Export - TRUE lazy generation only when button is clicked
        
        # Add spacing to align with selectbox height
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Three export buttons in a row within this column - wider Export ALL, compact Excel/JSON
        export_col1, export_col2, export_col3 = st.columns([1.5, 1, 1])
        
        with export_col1:
            # Master JSON Export using centralized UIExportManager
            if analysis:
                from ..export_handlers.ui_export_manager import UIExportManager
                export_manager = UIExportManager(analysis)
                xml_filename = st.session_state.get(SessionStateKeys.XML_FILENAME, 'unknown.xml')
                export_manager.render_lazy_master_json_export_button(reports, xml_filename)
            else:
                st.button("🗂️ Export ALL", disabled=True, help="Analysis data not available", key="export_master_json_disabled")
        
        with export_col2:
            # Excel export using centralized UIExportManager
            if selected_search and analysis:
                from ..export_handlers.ui_export_manager import UIExportManager
                export_manager = UIExportManager(analysis)
                clean_name = SearchManager.clean_search_name(selected_search.name)
                export_manager.render_lazy_excel_export_button(
                    selected_search, clean_name, selected_search.id, "search"
                )
            else:
                st.button(
                    "📊 Excel",
                    disabled=True,
                    help="Select a search to export to Excel",
                    key="export_excel_nav_no_search"
                )
        
        with export_col3:
            # JSON export using centralized UIExportManager
            if selected_search and analysis:
                from ..export_handlers.ui_export_manager import UIExportManager
                export_manager = UIExportManager(analysis)
                clean_name = SearchManager.clean_search_name(selected_search.name)
                xml_filename = st.session_state.get(SessionStateKeys.XML_FILENAME, 'unknown.xml')
                export_manager.render_lazy_json_export_button(
                    selected_search, clean_name, selected_search.id, "search", xml_filename
                )
            else:
                st.button(
                    "📋 JSON",
                    disabled=True,
                    help="Select a search to generate JSON export",
                    key="generate_json_no_search"
                )
    
    # Remove the "Show All Searches in Folder" checkbox as it's not useful on large files
    
    # Display selected search only
    if selected_search_index is not None and folder_searches:
        # Display individual search details
        selected_search = folder_searches[selected_search_index]
        render_individual_search_details(selected_search, reports, show_dependencies=False)
    else:
        st.markdown(info_box("👆 Select a search from the dropdown above to see detailed rule analysis"), unsafe_allow_html=True)
    


def _render_all_detailed_rules_simple(reports):
    """Fallback: render all rules in a simple list when no folder structure"""
    sorted_reports = SearchManager.sort_searches_numerically(reports)
    for report in sorted_reports:
        _render_single_detailed_rule(report, reports)


def _render_folder_detailed_rules(folder_searches, all_reports):
    """Render all detailed rules in a folder with proper hierarchy"""
    # Sort searches numerically
    sorted_searches = SearchManager.sort_searches_numerically(folder_searches)
    
    for i, search in enumerate(sorted_searches):
        # Add some spacing between searches
        if i > 0:
            st.markdown("---")
        _render_single_detailed_rule(search, all_reports)


def _render_single_detailed_rule(selected_search, reports):
    """Render detailed rule breakdown for a single search"""
    clean_name = SearchManager.clean_search_name(selected_search.name)
    classification = "🔍"  # All items in search analysis are searches
    
    # Header - export buttons are now in main navigation
    st.markdown(f"### {classification} {clean_name}")
    
    st.subheader(f"📋 {selected_search.name}")
    if selected_search.description:
        with st.container(border=True):
            st.write(selected_search.description)
    
    # Show parent context (always visible like in Rule Flow)
    if selected_search.parent_guid:
        parent_report = next((r for r in reports if r.id == selected_search.parent_guid), None)
        if parent_report:
            parent_clean_name = SearchManager.clean_search_name(parent_report.name)
            st.markdown(info_box(f"🔵 **Child Search!** Parent Search: {parent_clean_name}"), unsafe_allow_html=True)
        else:
            st.markdown(warning_box(f"🔵 **Child Search!** Parent search not found (ID: {selected_search.parent_guid[:8]}...)"), unsafe_allow_html=True)
    else:
        if selected_search.parent_type == 'ACTIVE':
            st.markdown("""
            <div style="
                background-color: #28546B;
                padding: 0.75rem;
                border-radius: 0.5rem;
                color: #FAFAFA;
                text-align: left;
                margin-bottom: 0.5rem;
            ">
                <strong>Base Population:</strong> All currently registered patients
            </div>
            """, unsafe_allow_html=True)
        elif selected_search.parent_type == 'ALL':
            st.markdown("""
            <div style="
                background-color: #28546B;
                padding: 0.75rem;
                border-radius: 0.5rem;
                color: #FAFAFA;
                text-align: left;
                margin-bottom: 0.5rem;
            ">
                <strong>Base Population:</strong> All patients (including left and deceased)
            </div>
            """, unsafe_allow_html=True)
        elif selected_search.parent_type:
            st.markdown(f"""
            <div style="
                background-color: #28546B;
                padding: 0.75rem;
                border-radius: 0.5rem;
                color: #FAFAFA;
                text-align: left;
                margin-bottom: 0.5rem;
            ">
                <strong>Base Population:</strong> {selected_search.parent_type} patients
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="
                background-color: #28546B;
                padding: 0.75rem;
                border-radius: 0.5rem;
                color: #FAFAFA;
                text-align: left;
                margin-bottom: 0.5rem;
            ">
                <strong>Base Population:</strong> Custom patient population
            </div>
            """, unsafe_allow_html=True)
    
    # Skip report type-specific information for searches - they don't need report classification
    
    # Process each criteria group
    if selected_search.criteria_groups:
        st.markdown("### 🔍 Rules")
        for j, group in enumerate(selected_search.criteria_groups):
            # Create more descriptive rule names
            rule_name = f"Rule {j+1}"
            if len(selected_search.criteria_groups) > 1:
                if j == 0:
                    rule_name += " (Primary Criteria)"
                else:
                    # Check if this rule has linked criteria
                    if has_linked_criteria(group):
                        rule_name += " (With Stop/Change Checking)"
                    else:
                        rule_name += " (Additional Criteria)"
            
            render_criteria_group(group, rule_name)
    else:
        st.markdown(f"""
                <div style="
                background-color: #660022;
                padding: 0.75rem;
                border-radius: 0.5rem;
                color: #FAFAFA;
                text-align: left;
                margin-bottom: 0.5rem;
                ">
                No search criteria found for this item.
                </div>
                """, unsafe_allow_html=True)


def render_individual_search_details(selected_search, reports, show_dependencies=False):
    """Render detailed information for a single selected search"""
    import streamlit as st
    from ..core import SearchManager
    # Searches don't need report classification
    
    # Export functionality is now handled in main navigation row
    
    st.subheader(f"📋 {selected_search.name}")
    if selected_search.description:
        with st.container(border=True):
            st.write(selected_search.description)
    
    # Show parent context (always visible like in Rule Flow)
    if selected_search.parent_guid:
        parent_report = next((r for r in reports if r.id == selected_search.parent_guid), None)
        if parent_report:
            parent_clean_name = SearchManager.clean_search_name(parent_report.name)
            st.markdown(info_box(f"🔵 **Child Search!** Parent Search: {parent_clean_name}"), unsafe_allow_html=True)
        else:
            st.markdown(warning_box(f"🔵 **Child Search!** Parent search not found (ID: {selected_search.parent_guid[:8]}...)"), unsafe_allow_html=True)
    else:
        if selected_search.parent_type == 'ACTIVE':
            st.markdown("""
            <div style="
                background-color: #28546B;
                padding: 0.75rem;
                border-radius: 0.5rem;
                color: #FAFAFA;
                text-align: left;
                margin-bottom: 0.5rem;
            ">
                <strong>Base Population:</strong> All currently registered patients
            </div>
            """, unsafe_allow_html=True)
        elif selected_search.parent_type == 'ALL':
            st.markdown("""
            <div style="
                background-color: #28546B;
                padding: 0.75rem;
                border-radius: 0.5rem;
                color: #FAFAFA;
                text-align: left;
                margin-bottom: 0.5rem;
            ">
                <strong>Base Population:</strong> All patients (including left and deceased)
            </div>
            """, unsafe_allow_html=True)
        elif selected_search.parent_type:
            st.markdown(f"""
            <div style="
                background-color: #28546B;
                padding: 0.75rem;
                border-radius: 0.5rem;
                color: #FAFAFA;
                text-align: left;
                margin-bottom: 0.5rem;
            ">
                <strong>Base Population:</strong> {selected_search.parent_type} patients
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="
                background-color: #28546B;
                padding: 0.75rem;
                border-radius: 0.5rem;
                color: #FAFAFA;
                text-align: left;
                margin-bottom: 0.5rem;
            ">
                <strong>Base Population:</strong> Custom patient population
            </div>
            """, unsafe_allow_html=True)
    
    # Skip report type-specific information for searches - they don't need report classification
    
    # Process each criteria group
    if selected_search.criteria_groups:
        st.markdown("### 🔍 Rules")
        for j, group in enumerate(selected_search.criteria_groups):
            # Create more descriptive rule names
            rule_name = f"Rule {j+1}"
            if len(selected_search.criteria_groups) > 1:
                if j == 0:
                    rule_name += " (Primary Criteria)"
                else:
                    # Check if this rule has linked criteria
                    if has_linked_criteria(group):
                        rule_name += " (With Stop/Change Checking)"
                    else:
                        rule_name += " (Additional Criteria)"
            
            render_criteria_group(group, rule_name)
    else:
        st.markdown(f"""
                <div style="
                background-color: #660022;
                padding: 0.75rem;
                border-radius: 0.5rem;
                color: #FAFAFA;
                text-align: left;
                margin-bottom: 0.5rem;
                ">
                No search criteria found for this item.
                </div>
                """, unsafe_allow_html=True)


def render_criteria_group(group: CriteriaGroup, rule_name: str):
    """Render individual rule with its criteria"""
    try:
        # Filter out linked criteria that should only appear within their parent criteria
        # This prevents linked criteria from being displayed as separate "Criterion 2" etc.
        displayed_criteria = filter_top_level_criteria(group)
    except Exception as e:
        st.markdown(error_box(f"Error filtering criteria for rule '{rule_name}': {str(e)}"), unsafe_allow_html=True)
        displayed_criteria = group.criteria if hasattr(group, 'criteria') else []
    
    # Build rule header with optional help icon for single-criterion AND logic
    rule_header = f"**{rule_name}** - Logic: `{group.member_operator}`"
    
    st.markdown(rule_header)
    
    # Action indicators with clinical terminology
    col1, col2 = st.columns(2)
    with col1:
        if group.action_if_true == "SELECT":
            action_color = "🟢"
            action_text = "Include in final result"
        elif group.action_if_true == "NEXT":
            action_color = "🔀"  # Flow control
            action_text = "Goto next rule"
        elif group.action_if_true == "REJECT":
            action_color = "🔴"  # Exclusion
            action_text = "Exclude from final result"
        else:
            action_color = "⚪"  # Unknown
            action_text = group.action_if_true
        st.markdown(f"{action_color} If rule passed: **{action_text}**")
            
    with col2:
        if group.action_if_false == "SELECT":
            action_color = "🟢"
            action_text = "Include in final result"
        elif group.action_if_false == "NEXT":
            action_color = "🔀"  # Flow control
            action_text = "Goto next rule"
        elif group.action_if_false == "REJECT":
            action_color = "🔴"  # Exclusion
            action_text = "Exclude from final result"
        else:
            action_color = "⚪"  # Unknown
            action_text = group.action_if_false
        st.markdown(f"{action_color} If rule failed: **{action_text}**")
    
    # Show when this rule uses results from another search
    if group.population_criteria:
        st.markdown("**🔗 Using Another Search** - This rule uses the results from search below instead of hard coded criteria:")
        for pop_crit in group.population_criteria:
            # Try to find the referenced search
            analysis = st.session_state.get(SessionStateKeys.SEARCH_ANALYSIS)
            if analysis:
                ref_report = next((r for r in analysis.reports if r.id == pop_crit.report_guid), None)
                if ref_report:
                    from ..core import SearchManager
                    ref_clean_name = SearchManager.clean_search_name(ref_report.name)
                    st.markdown(info_box(f"🔍 **{ref_clean_name}**"), unsafe_allow_html=True)
                else:
                    # Try to find in all reports (including member searches)
                    all_reports = []
                    def collect_all_reports(reports):
                        for report in reports:
                            all_reports.append(report)
                            if hasattr(report, 'member_searches') and report.member_searches:
                                collect_all_reports(report.member_searches)
                    
                    collect_all_reports(analysis.reports)
                    ref_report = next((r for r in all_reports if r.id == pop_crit.report_guid), None)
                    
                    if ref_report:
                        from ..core import SearchManager
                        ref_clean_name = SearchManager.clean_search_name(ref_report.name)
                        st.markdown(info_box(f"🔍 **{ref_clean_name}**"), unsafe_allow_html=True)
                    else:
                        st.caption(f"• Search ID: {pop_crit.report_guid[:8]}...")
            else:
                st.caption(f"• Search ID: {pop_crit.report_guid[:8]}...")
    
    # Display the pre-calculated non-duplicate criteria
    if not displayed_criteria:
        # Check if we have original criteria but they were all filtered out as duplicates
        if len(group.criteria) > 0:
            # All criteria were filtered as linked duplicates - this rule's criteria are shown elsewhere
            if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
                st.markdown(warning_box(f"⚠️ **Debug:** Rule has {len(group.criteria)} criteria but all filtered as linked duplicates"), unsafe_allow_html=True)
                for i, crit in enumerate(group.criteria):
                    st.caption(f"Debug: Criterion {i+1}: {crit.display_name} (Table: {crit.table}) - filtered as duplicate")
            else:
                st.markdown(info_box("ℹ️ **This rule's criteria are displayed under linked criteria in other rules.** The criteria for this rule are shown as part of complex linked relationships in previous rules."), unsafe_allow_html=True)
        elif group.population_criteria:
            # This case is already handled above with the "Using Another Search" section
            pass
        else:
            # This should not happen with proper filtering - all searches in EMIS must have criteria
            if st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
                st.markdown(error_box(f"⚠️ **Debug:** Unexpected empty rule found after filtering. This suggests a filtering issue."), unsafe_allow_html=True)
                st.write(f"Debug: Original criteria count: {len(group.criteria)}")
                st.write(f"Debug: Displayed criteria count: {len(displayed_criteria)}")
                st.write(f"Debug: Population criteria: {group.population_criteria}")
                for i, crit in enumerate(group.criteria):
                    st.write(f"Debug: Criterion {i+1}: {crit.display_name}, Table: {crit.table}, ValueSets: {len(crit.value_sets) if hasattr(crit, 'value_sets') else 'N/A'}")
            else:
                st.markdown(warning_box("⚠️ **Unexpected empty rule.** This should not occur with proper search filtering."), unsafe_allow_html=True)
    else:
        for k, criterion in enumerate(displayed_criteria):
            try:
                render_search_criterion(criterion, f"Criterion {k+1}")
            except Exception as e:
                st.markdown(error_box(f"Error rendering criterion {k+1}: {str(e)}"), unsafe_allow_html=True)
                st.write(f"Criterion details: {getattr(criterion, 'display_name', 'No display name')}")
        
    st.markdown("---")


@st.cache_data(ttl=1800, max_entries=5000)  # Cache for 30 minutes with max 5000 entries (supports multiple large XMLs)
def _generate_code_data_for_value_set(vs_values, vs_description, emis_guids, snomed_lookup_cache_key):
    """Generate code data for a value set using the XML-specific cached clinical data"""
    # Use the XML-specific cached clinical data instead of going back to lookup table
    from ..ui.tabs.tab_helpers import get_unified_clinical_data
    
    # Get the already-processed clinical data for this XML
    unified_results = get_unified_clinical_data()
    if not unified_results:
        # Fallback to basic format if no unified data available
        return _generate_basic_code_data(vs_values, vs_description)
    
    # Build a lookup from all clinical data categories
    emis_to_clinical_data = {}
    
    # Index all clinical data by EMIS GUID for fast lookup
    for data_category in ['clinical_codes', 'medications', 'refsets', 'pseudo_refsets', 'clinical_pseudo_members']:
        if data_category in unified_results:
            for item in unified_results[data_category]:
                emis_guid = item.get('EMIS GUID', '').strip()
                if emis_guid:
                    emis_to_clinical_data[emis_guid] = item
    
    code_data = []
    for j, value in enumerate(vs_values):
        code_value = value['value'] if value['value'] else "No code specified"
        code_name = value.get('display_name', '')
        
        # Special handling for library items
        if value.get('is_library_item', False):
            code_data.append({
                'EMIS Code': code_value,
                'SNOMED Code': 'Library Item',
                'Description': value['display_name'],
                'Scope': '📚 Library',
                'Is Refset': 'No'
            })
        else:
            # Handle refsets differently - they have direct SNOMED codes
            if value['is_refset']:
                # For refsets: EMIS Code = SNOMED Code, Description from XML
                snomed_code = code_value  # Refset codes are direct SNOMED codes
                scope = '🎯 Refset'
                # Use the valueset description as the code description for refsets
                description = vs_description if vs_description != code_name else code_name
            else:
                # Look up in the already-processed XML clinical data
                clinical_item = emis_to_clinical_data.get(str(code_value).strip())
                if clinical_item:
                    snomed_code = clinical_item.get('SNOMED Code', 'Not found')
                    # Use description from XML first, fall back to lookup description
                    description = code_name if code_name else clinical_item.get('SNOMED Description', 'No description')
                else:
                    snomed_code = 'Not found' if code_value != "No code specified" else 'N/A'
                    description = code_name
                
                if value['include_children']:
                    scope = '👪 + Children'
                else:
                    scope = '🎯 Exact'
            
            code_data.append({
                'EMIS Code': code_value,
                'SNOMED Code': snomed_code,
                'Description': description,
                'Scope': scope,
                'Is Refset': 'Yes' if value['is_refset'] else 'No'
            })
    
    return code_data


def _generate_basic_code_data(vs_values, vs_description):
    """Fallback function for when unified clinical data is not available"""
    code_data = []
    for value in vs_values:
        code_value = value['value'] if value['value'] else "No code specified"
        code_name = value.get('display_name', '')
        
        if value.get('is_library_item', False):
            code_data.append({
                'EMIS Code': code_value,
                'SNOMED Code': 'Library Item',
                'Description': value['display_name'],
                'Scope': '📚 Library',
                'Is Refset': 'No'
            })
        else:
            if value['is_refset']:
                snomed_code = code_value
                scope = '🎯 Refset'
                description = vs_description if vs_description != code_name else code_name
            else:
                snomed_code = 'Analysis unavailable'
                description = code_name
                scope = '👪 + Children' if value['include_children'] else '🎯 Exact'
            
            code_data.append({
                'EMIS Code': code_value,
                'SNOMED Code': snomed_code,
                'Description': description,
                'Scope': scope,
                'Is Refset': 'Yes' if value['is_refset'] else 'No'
            })
    
    return code_data


def render_search_criterion(criterion: SearchCriterion, criterion_name: str):
    """Render individual search criterion with all its details"""
    try:
        with st.expander(f"{criterion_name}: {criterion.display_name}", expanded=False):
            
            # Basic info
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Table:** `{criterion.table}`")
                # Note: We should show the search/report description, not the criterion description
                # The criterion description is often inaccurate/misleading
            with col2:
                negation_text = "🚫 Not" if criterion.negation else "✅ Include"
                st.markdown(f"**Action:** {negation_text}")
                if criterion.exception_code:
                    st.markdown(f"**EMIS Internal Flag:** `{criterion.exception_code}`")
        
            # Check for parameters and show warning
            parameter_info = check_criterion_parameters(criterion)
            if parameter_info['has_parameters']:
                param_type = "Global" if parameter_info['has_global'] else "Local"
                param_names = "', '".join(parameter_info['parameter_names'])
                if parameter_info['has_global'] and not parameter_info['has_local']:
                    warning_text = f"⚠️ **Parameter Warning:** This search uses Global parameter(s): '{param_names}'"
                elif parameter_info['has_local'] and not parameter_info['has_global']:
                    warning_text = f"⚠️ **Parameter Warning:** This search uses Local parameter(s): '{param_names}'"
                else:
                    warning_text = f"⚠️ **Parameter Warning:** This search uses parameter(s): '{param_names}'"
                st.markdown(warning_box(warning_text), unsafe_allow_html=True)
        
            # Value sets (codes being searched for) - exclude linked criteria value sets
            main_value_sets = filter_linked_value_sets_from_main(criterion)
            
            # Separate EMISINTERNAL codes from clinical codes
            clinical_value_sets = []
            emisinternal_value_sets = []
            
            for vs in main_value_sets:
                if vs.get('code_system') == 'EMISINTERNAL':
                    emisinternal_value_sets.append(vs)
                else:
                    clinical_value_sets.append(vs)
            
            # Display clinical codes only (no EMISINTERNAL)
            if clinical_value_sets:
                st.markdown("**🔍 Clinical Codes:**")
                for i, vs in enumerate(clinical_value_sets):
                    # Create a title for the expandable section
                    vs_title = vs['description'] if vs['description'] else f"Value Set {i+1}"
                    vs_count = len(vs['values'])
                    
                    # Check if this is a library item
                    is_library_item = vs.get('code_system') == 'LIBRARY_ITEM'
                    icon = "📚" if is_library_item else "📋"
                    
                    with st.expander(f"{icon} {vs_title} ({vs_count} codes)", expanded=False):
                        # Enhanced code system descriptions
                        code_system = vs['code_system']
                        system_display = code_system
                        if 'SNOMED_CONCEPT' in code_system:
                            system_display = "SNOMED Clinical Terminology"
                        elif 'SCT_DRGGRP' in code_system:
                            system_display = "Drug Group Classification"
                        elif 'EMISINTERNAL' in code_system:
                            system_display = "EMIS Internal Classifications"
                        elif 'SCT_APPNAME' in code_system:
                            system_display = "Medical Appliance Names"
                        elif code_system == 'LIBRARY_ITEM':
                            system_display = "EMIS Internal Library"
                        
                        st.caption(f"**System:** {system_display}")
                        if vs['id']:
                            st.caption(f"**ID:** {vs['id']}")
                        
                        # Display codes as scrollable dataframe with icons - using cached function
                        import pandas as pd
                        
                        # PERFORMANCE OPTIMIZATION: Use cached function for SNOMED lookups
                        # Extract all non-library EMIS GUIDs from the value set for cache key
                        emis_guids = [value['value'] for value in vs['values'] if value['value'] and not value.get('is_library_item', False)]
                        
                        # Create cache key based on the value set and lookup availability
                        cache_key = f"{vs.get('id', 'unknown')}_{len(vs['values'])}_{len(emis_guids)}"
                        
                        # Use cached function to generate code data
                        code_data = _generate_code_data_for_value_set(
                            vs['values'], 
                            vs.get('description', ''),
                            emis_guids,
                            cache_key
                        )
                        
                        if code_data:
                            # Create and display dataframe
                            codes_df = pd.DataFrame(code_data)
                            
                            st.dataframe(
                                codes_df,
                                width='stretch',
                                hide_index=True,
                                column_config={
                                    "EMIS Code": st.column_config.TextColumn(
                                        "🔍 EMIS Code",
                                        width="medium"
                                    ),
                                    "SNOMED Code": st.column_config.TextColumn(
                                        "⚕️ SNOMED Code", 
                                        width="medium"
                                    ),
                                    "Description": st.column_config.TextColumn(
                                        "📝 Description",
                                        width="large"
                                    ),
                                    "Scope": st.column_config.TextColumn(
                                        "🔗 Scope",
                                        width="small"
                                    ),
                                    "Is Refset": st.column_config.TextColumn(
                                        "🎯 Refset",
                                        width="small"
                                    )
                                }
                            )
            
            # Column filters (age, date restrictions, etc.) with smart deduplication
            # Filter out column filters that are used in linked criteria
            main_column_filters = filter_linked_column_filters_from_main(criterion)
            
            if main_column_filters:
                st.markdown("**⚙️ Filters:**")
                
                # Group filters by type to avoid duplicates
                filter_groups = {}
                for cf in main_column_filters:
                    column = cf.get('column', 'Unknown')
                    # Convert list to tuple for hashing if needed
                    column_key = tuple(column) if isinstance(column, list) else column
                    if column_key not in filter_groups:
                        filter_groups[column_key] = []
                    filter_groups[column_key].append(cf)
                
                for column_key, filters in filter_groups.items():
                    # Convert tuple back to list if needed for processing
                    column = list(column_key) if isinstance(column_key, tuple) else column_key
                    # Handle both single column (string) and multiple columns (list)
                    if isinstance(column, list):
                        # Multiple columns - combine for display
                        column_names = column
                        column_upper_list = [col.upper() for col in column_names]
                        column_display = " + ".join(column_names)
                    else:
                        # Single column - existing logic
                        column_names = [column]
                        column_upper_list = [column.upper()]
                        column_display = column
                    
                    # Create detailed description based on column type and actual values
                    if any(col in ['READCODE', 'SNOMEDCODE'] for col in column_upper_list):
                        # Count clinical codes for display
                        total_clinical_codes = sum(len(vs.get('values', [])) for vs in clinical_value_sets)
                        if total_clinical_codes > 0:
                            st.caption(f"• Include {total_clinical_codes} specified clinical codes")
                        else:
                            st.caption("• Include specified clinical codes")
                    elif any(col in ['DRUGCODE'] for col in column_upper_list):
                        # Count medication codes for display
                        total_medication_codes = sum(len(vs.get('values', [])) for vs in clinical_value_sets)
                        if total_medication_codes > 0:
                            st.caption(f"• Include {total_medication_codes} specified medication codes")
                        else:
                            st.caption("• Include specified medication codes")
                    elif any(col == 'NUMERIC_VALUE' for col in column_upper_list):
                        # Show detailed numeric value filter with actual values
                        filter_desc = render_column_filter(filters[0])
                        if filter_desc:
                            st.caption(f"• {filter_desc}")
                        else:
                            st.caption("• Numeric value filtering")
                    elif any(col in ['DATE', 'ISSUE_DATE', 'AGE'] for col in column_upper_list):
                        # Show detailed date/age filters with actual ranges
                        filter_desc = render_column_filter(filters[0])
                        if filter_desc:
                            st.caption(f"• {filter_desc}")
                        else:
                            generic_desc = {
                                'DATE': 'Date filtering',
                                'ISSUE_DATE': 'Issue date filtering', 
                                'AGE': 'Patient age filtering'
                            }.get(column_upper_list[0], f'{column_display} filtering')
                            st.caption(f"• {generic_desc}")
                    elif any(col in ['AUTHOR', 'CURRENTLY_CONTRACTED'] for col in column_upper_list):
                        # EMISINTERNAL multi-column pattern for user authorization
                        st.caption("• User authorization: Active users only")
                    elif any(filters[0].get('column_type') == 'patient_demographics' for _ in filters):
                        # Patient demographics filters (LSOA codes, etc.)
                        filter_desc = render_patient_demographics_filter(filters[0])
                        if filter_desc:
                            st.caption(f"• {filter_desc}")
                        else:
                            st.caption("• Patient demographics filtering")
                    else:
                        # Use the existing render_column_filter function for other types
                        filter_desc = render_column_filter(filters[0])
                        if filter_desc:
                            st.caption(f"• {filter_desc}")
            
            # Convert EMISINTERNAL codes to filter descriptions using display names
            if emisinternal_value_sets:
                st.markdown("**&nbsp;&nbsp;&nbsp;&nbsp;⚙️ Additional Filters:**")
                for vs in emisinternal_value_sets:
                    vs_description = vs.get('description', '')
                    
                    # Use the value set description if available for context
                    if vs_description and vs_description.lower() not in ['', 'none']:
                        filter_context = vs_description.lower()
                    else:
                        filter_context = "internal classification"
                    
                    # Find the corresponding column filter to get the correct in_not_in value and column context
                    column_filter_in_not_in = "IN"  # Default
                    column_name = ""
                    column_display_name = ""
                    for cf in main_column_filters:
                        cf_value_sets = cf.get('value_sets', [])
                        for cf_vs in cf_value_sets:
                            if cf_vs.get('id') == vs.get('id'):
                                column_filter_in_not_in = cf.get('in_not_in', 'IN')
                                column_name = cf.get('column', '').upper()
                                column_display_name = cf.get('display_name', '').lower()
                                break
                    
                    for value in vs['values']:
                        display_name = value.get('display_name', '')
                        code_value = value.get('value', '')
                        
                        # Determine action based on in_not_in value
                        action = "Include" if column_filter_in_not_in == "IN" else "Exclude"
                        
                        # Determine proper context based on column name
                        if column_name == 'ISSUE_METHOD':
                            context = "issue method"
                        elif column_name == 'IS_PRIVATE':
                            context = "private prescriptions"
                        elif column_name in ['AUTHOR', 'CURRENTLY_CONTRACTED']:
                            context = "user authorization"
                        elif 'consultation' in column_display_name or 'heading' in column_display_name:
                            context = "consultation heading"
                        else:
                            context = column_display_name if column_display_name else filter_context
                        
                        # Use display name when available, fall back to code
                        if display_name and display_name.strip():
                            # Special handling for specific column types
                            if column_name == 'ISSUE_METHOD':
                                st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;• {action} {context}: {display_name}")
                            elif code_value.upper() == 'PROBLEM' and 'consultation' in context:
                                st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;• {action} consultations where the consultation heading is: {display_name}")
                            elif code_value.upper() in ['COMPLICATION', 'ONGOING', 'RESOLVED']:
                                status_descriptions = {
                                    'COMPLICATION': f"{action} complications only: {display_name}",
                                    'ONGOING': f"{action} ongoing conditions: {display_name}",
                                    'RESOLVED': f"{action} resolved conditions: {display_name}"
                                }
                                st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;• {status_descriptions.get(code_value.upper(), f'{action} {context}: {display_name}')}")
                            else:
                                st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;• {action} {context}: {display_name}")
                        elif code_value:
                            st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;• {action} internal code: {code_value}")
                        else:
                            st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;• {action} EMIS internal classification")
            
            # Restrictions (Latest 1, etc.)
            if criterion.restrictions:
                st.markdown("**🎯 Restrictions:**")
                for restriction in criterion.restrictions:
                    if restriction.type == "latest_records":
                        icon = "📅" if "Latest" in restriction.description else "🔼"
                        st.caption(f"{icon} {restriction.description}")
                    else:
                        st.caption(f"⚙️ {restriction.description}")
                    
                    # Show clinical codes in restrictions if they contain value sets
                    if restriction.conditions:
                        for condition in restriction.conditions:
                            if condition.get('value_set_elements'):
                                st.markdown("**🔍 Clinical Codes:**")
                                # Parse and render the actual value set elements using existing logic
                                for vs_elem in condition['value_set_elements']:
                                    render_restriction_value_set_element(vs_elem)
            
            # Linked criteria (complex relationships)
            render_linked_criteria(criterion, criterion)
        
    except Exception as e:
        import traceback
        st.markdown(error_box(f"Error rendering criterion: {str(e)}"), unsafe_allow_html=True)
        with st.expander("Debug Information", expanded=False):
            st.code(traceback.format_exc())
        raise  # Re-raise to see the original error


def render_column_filter(column_filter):
    """Render column filter description with actual values"""
    column = column_filter['column']
    
    # Handle both single column (string) and multiple columns (list)
    if isinstance(column, list):
        column_display = " + ".join(column)
        column_check = column  # List for checking
    else:
        column_display = column
        column_check = [column]  # Make it a list for consistent checking
    
    in_not_in = column_filter['in_not_in']
    range_info = column_filter.get('range')
    parameter_info = column_filter.get('parameter')
    display_name = column_filter.get('display_name', column_display)
    value_sets = column_filter.get('value_sets', [])
    
    def _get_value_set_summary(value_sets, max_display=3):
        """Extract actual values from value sets for display"""
        all_values = []
        for vs in value_sets:
            for value_item in vs.get('values', []):
                value = value_item.get('value', '')
                display_name = value_item.get('display_name', '')
                if display_name and display_name != value:
                    all_values.append(display_name)
                elif value:
                    all_values.append(value)
        
        if not all_values:
            return None
            
        if len(all_values) <= max_display:
            return ", ".join(all_values)
        else:
            shown = ", ".join(all_values[:max_display])
            remaining = len(all_values) - max_display
            return f"{shown} and {remaining} more"
    
    
    # Handle parameterized filters (runtime user input)
    if parameter_info:
        param_name = parameter_info.get('name', 'Unknown Parameter')
        is_global = parameter_info.get('allow_global', False)
        scope = "Global Parameter" if is_global else "Search Parameter"
        
        # For date parameters, show the constraint format with placeholder
        # User selects the operator (before/after/on/etc.) at runtime
        if any(col in ['DATE', 'ISSUE_DATE', 'DOB', 'GMS_DATE_OF_REGISTRATION'] for col in column_check):
            column_display = display_name if display_name != column_display else "Date"
            return f"{column_display} [{param_name}]"
        else:
            action = "Include" if in_not_in == "IN" else "Exclude"
            return f"{action} {display_name.lower()} using [{param_name}]"
    
    # Handle range-based filters (numeric values, dates, etc.)
    if range_info:
        if 'AGE' in column_check:
            age_filters = []
            
            # Handle age range from
            if range_info.get('from'):
                age_value = range_info['from']['value']
                operator = range_info['from']['operator']
                unit = range_info['from']['unit']
                
                op_text = format_operator_text(operator, is_numeric=True)
                
                # Default to 'year' for AGE fields when unit is empty or missing
                display_unit = unit if unit and unit.strip() else 'year'
                unit_text = pluralize_unit(age_value, display_unit)
                age_filters.append(f"{op_text} {age_value} {unit_text}")
            
            # Handle age range to
            if range_info.get('to'):
                age_value = range_info['to']['value']
                operator = range_info['to']['operator']
                unit = range_info['to']['unit']
                
                op_text = format_operator_text(operator, is_numeric=True)
                
                # Default to 'year' for AGE fields when unit is empty or missing
                display_unit = unit if unit and unit.strip() else 'year'
                unit_text = pluralize_unit(age_value, display_unit)
                age_filters.append(f"{op_text} {age_value} {unit_text}")
            
            if age_filters:
                return f"Age {' and '.join(age_filters)}"
        
        elif any(col in ['DATE', 'ISSUE_DATE', 'DOB', 'GMS_DATE_OF_REGISTRATION'] for col in column_check):
            date_filters = []
            relative_to = range_info.get('relative_to', 'search date')
            column_display = display_name if display_name != column_display else "Date"
            
            # Handle date range from
            if range_info.get('from'):
                from_info = range_info['from']
                op_text = format_operator_text(from_info['operator'], is_numeric=False)
                
                date_value = from_info.get('value')
                if date_value:  # Only process if value exists
                    unit = from_info.get('unit', 'DATE')
                    
                    # Handle numeric offset patterns first (to catch -6, 7, etc.)
                    if unit and date_value and (date_value.lstrip('-').isdigit()):
                        # Handle numeric offset patterns to match EMIS exactly
                        if date_value.startswith('-'):
                            # Negative relative date (before search date)
                            abs_value = date_value[1:]  # Remove the minus sign
                            unit_text = pluralize_unit(abs_value, unit)
                            if op_text == 'on or after':
                                date_filters.append(f"and the {column_display} is after or on {abs_value} {unit_text} before the search date")
                            elif op_text == 'on or before':
                                date_filters.append(f"and the {column_display} is before or on {abs_value} {unit_text} before the search date")
                            else:
                                date_filters.append(f"and the {column_display} is on {abs_value} {unit_text} before the search date")
                        else:
                            # Positive relative date (after search date) or zero (on search date)
                            unit_text = pluralize_unit(date_value, unit)
                            if date_value == '0':
                                # Special case for zero offset - means "on the search date"
                                if op_text == 'on or after':
                                    date_filters.append(f"and the {column_display} is after or on the search date")
                                elif op_text == 'on or before':
                                    date_filters.append(f"and the {column_display} is before or on the search date")
                                else:
                                    date_filters.append(f"and the {column_display} is on the search date")
                            else:
                                # Non-zero positive relative date (after search date)
                                if op_text == 'on or after':
                                    date_filters.append(f"and the {column_display} is after or on {date_value} {unit_text} after the search date")
                                elif op_text == 'on or before':
                                    date_filters.append(f"and the {column_display} is before or on {date_value} {unit_text} after the search date")
                                else:
                                    date_filters.append(f"and the {column_display} is on {date_value} {unit_text} after the search date")
                    # Handle temporal variable patterns (Last/This/Next + time unit)
                    elif unit and unit.upper() in ['DAY', 'WEEK', 'MONTH', 'QUARTER', 'YEAR', 'FISCALYEAR']:
                        if date_value.lower() == 'last':
                            if unit.upper() == 'FISCALYEAR':
                                date_filters.append(f"and the {column_display} is last fiscal year")
                            elif unit.upper() == 'QUARTER':
                                date_filters.append(f"and the {column_display} is last yearly quarter")
                            else:
                                date_filters.append(f"and the {column_display} is last {unit.lower()}")
                        elif date_value.lower() == 'this':
                            if unit.upper() == 'FISCALYEAR':
                                date_filters.append(f"and the {column_display} is this fiscal year")
                            elif unit.upper() == 'QUARTER':
                                date_filters.append(f"and the {column_display} is this yearly quarter")
                            else:
                                date_filters.append(f"and the {column_display} is this {unit.lower()}")
                        elif date_value.lower() == 'next':
                            if unit.upper() == 'FISCALYEAR':
                                date_filters.append(f"and the {column_display} is next fiscal year")
                            elif unit.upper() == 'QUARTER':
                                date_filters.append(f"and the {column_display} is next yearly quarter")
                            else:
                                date_filters.append(f"and the {column_display} is next {unit.lower()}")
                        else:
                            date_filters.append(f"and the {column_display} is {date_value} {unit.lower()}")
                    # Handle absolute dates (including empty unit which should default to DATE format)
                    elif (unit == 'DATE' or not unit) and date_value:
                        date_filters.append(f"{column_display} {op_text} {date_value} (Hardcoded Date)")
            
            # Handle date range to with full temporal variable support
            if range_info.get('to'):
                to_info = range_info['to']
                op_text = format_operator_text(to_info['operator'], is_numeric=False)
                
                date_value = to_info.get('value', '')  # Get value or empty string
                unit = to_info.get('unit', '').strip()
                
                # Handle case where range boundary has no value (operator-only)
                if not date_value:
                    if op_text == 'on or before':
                        date_filters.append(f"and the {column_display} is on or before the search date")
                    elif op_text == 'on or after':
                        date_filters.append(f"and the {column_display} is on or after the search date")
                    elif op_text == 'before':
                        date_filters.append(f"and the {column_display} is before the search date")
                    elif op_text == 'after':
                        date_filters.append(f"and the {column_display} is after the search date")
                    else:
                        date_filters.append(f"and the {column_display} is on the search date")
                # Handle numeric offset patterns first (to catch -6, 7, etc.)  
                elif unit and date_value and (date_value.lstrip('-').isdigit()):
                    # Handle numeric offset patterns to match EMIS exactly
                    if date_value.startswith('-'):
                        # Negative relative date (before search date)
                        abs_value = date_value[1:]  # Remove the minus sign
                        unit_text = pluralize_unit(abs_value, unit)
                        if op_text == 'on or before':
                            date_filters.append(f"and the {column_display} is before or on {abs_value} {unit_text} before the search date")
                        elif op_text == 'on or after':
                            date_filters.append(f"and the {column_display} is after or on {abs_value} {unit_text} before the search date")
                        else:
                            date_filters.append(f"and the {column_display} {op_text} {abs_value} {unit_text} before the search date")
                    else:
                        # Positive relative date (after search date) or zero (on search date)
                        unit_text = pluralize_unit(date_value, unit)
                        if date_value == '0':
                            # Special case for zero offset - means "on the search date"
                            if op_text == 'on or before':
                                date_filters.append(f"and the {column_display} is before or on the search date")
                            elif op_text == 'on or after':
                                date_filters.append(f"and the {column_display} is after or on the search date")
                            else:
                                date_filters.append(f"and the {column_display} is on the search date")
                        else:
                            # Non-zero positive relative date (after search date)
                            if op_text == 'on or before':
                                date_filters.append(f"and the {column_display} is before or on {date_value} {unit_text} after the search date")
                            elif op_text == 'on or after':
                                date_filters.append(f"and the {column_display} is after or on {date_value} {unit_text} after the search date")
                            else:
                                date_filters.append(f"and the {column_display} {op_text} {date_value} {unit_text} after the search date")
                # Handle temporal variable patterns (Last/This/Next + time unit) in 'to' range
                elif unit and unit.upper() in ['DAY', 'WEEK', 'MONTH', 'QUARTER', 'YEAR', 'FISCALYEAR']:
                    if date_value.lower() == 'last':
                        if unit.upper() == 'FISCALYEAR':
                            date_filters.append(f"and the {column_display} {op_text} last fiscal year")
                        elif unit.upper() == 'QUARTER':
                            date_filters.append(f"and the {column_display} {op_text} last yearly quarter")
                        else:
                            date_filters.append(f"and the {column_display} {op_text} last {unit.lower()}")
                    elif date_value.lower() == 'this':
                        if unit.upper() == 'FISCALYEAR':
                            date_filters.append(f"and the {column_display} {op_text} this fiscal year")
                        elif unit.upper() == 'QUARTER':
                            date_filters.append(f"and the {column_display} {op_text} this yearly quarter")
                        else:
                            date_filters.append(f"and the {column_display} {op_text} this {unit.lower()}")
                    elif date_value.lower() == 'next':
                        if unit.upper() == 'FISCALYEAR':
                            date_filters.append(f"and the {column_display} {op_text} next fiscal year")
                        elif unit.upper() == 'QUARTER':
                            date_filters.append(f"and the {column_display} {op_text} next yearly quarter")
                        else:
                            date_filters.append(f"and the {column_display} {op_text} next {unit.lower()}")
                    else:
                        date_filters.append(f"and the {column_display} {op_text} {date_value} {unit.lower()}")
                # Handle absolute dates in 'to' range
                elif (unit == 'DATE' or not unit) and date_value:
                    date_filters.append(f"{column_display} {op_text} {date_value} (Hardcoded Date)")
                else:
                    # Fallback for 'to' range
                    if to_info['operator'] == 'LTEQ':
                        if relative_to == 'BASELINE':
                            date_filters.append(f"{column_display} is before or on the search date")
                        else:
                            date_filters.append(f"{column_display} is before or on {relative_to}")
                    elif to_info['operator'] == 'LT':
                        if relative_to == 'BASELINE':
                            date_filters.append(f"{column_display} is before the search date")
                        else:
                            date_filters.append(f"{column_display} is before {relative_to}")
            
            if date_filters:
                return " and ".join(date_filters)
            else:
                # Fallback for date columns that didn't match any patterns
                if 'ISSUE_DATE' in column_check:
                    return f"{column_display} filters applied"
                else:
                    return f"{column_display} filters applied"
        
        elif any(col in ['NUMERIC_VALUE', 'VALUE'] for col in column_check):
            # Handle numeric value filters (like spirometry <0.7, DEXA scores ≤-2.5, BMI ≥30)
            range_desc = []
            
            if range_info.get('from'):
                from_info = range_info['from']
                value = from_info['value']
                operator = from_info['operator']
                
                
                # Only add if value is not empty
                if value and str(value).strip():
                    op_text = format_operator_text(operator, is_numeric=True)
                    
                    range_desc.append(f"{op_text} {value}")
                else:
                    # Handle case where from_info doesn't have expected structure
                    pass
            
            if range_info.get('to'):
                to_info = range_info['to']
                value = to_info['value']
                operator = to_info['operator']
                
                # Only add if value is not empty
                if value and str(value).strip():
                    op_text = format_operator_text(operator, is_numeric=True)
                    
                    range_desc.append(f"{op_text} {value}")
            
            if range_desc:
                # Add context for common clinical values
                context = ""
                all_values = []
                if range_info.get('from') and range_info['from']['value'] and range_info['from']['value'].strip():
                    try:
                        all_values.append(float(range_info['from']['value']))
                    except (ValueError, TypeError) as e:
                        pass  # Skip invalid values
                if range_info.get('to') and range_info['to']['value'] and range_info['to']['value'].strip():
                    try:
                        all_values.append(float(range_info['to']['value']))
                    except (ValueError, TypeError) as e:
                        pass  # Skip invalid values
                
                if range_desc:
                    numeric_filter = " AND ".join(range_desc)
                    return f"Value {numeric_filter}"
                else:
                    return f"Value filtering applied"
        
        elif any(col in ['AGE', 'AGE_AT_EVENT'] for col in column_check):
            # Handle age-based filtering
            range_desc = []
            if range_info.get('from'):
                from_info = range_info['from']
                age_from = from_info['value']
                operator = from_info['operator']
                unit = from_info.get('unit', 'YEAR')
                
                # Use the existing operator text utility
                op_text = format_operator_text(operator, is_numeric=True)
                
                if unit.upper() == 'DAY':
                    unit_text = pluralize_unit(age_from, 'day')
                    if age_from == '248':
                        range_desc.append(f"{op_text} {age_from} {unit_text} (8 months)")
                    else:
                        range_desc.append(f"{op_text} {age_from} {unit_text}")
                else:
                    unit_text = pluralize_unit(age_from, 'year')
                    range_desc.append(f"{op_text} {age_from} {unit_text} old")
            
            if range_info.get('to'):
                to_info = range_info['to']
                age_to = to_info['value']
                operator = to_info['operator']
                unit = to_info.get('unit', 'YEAR')
                
                # Use the existing operator text utility
                op_text = format_operator_text(operator, is_numeric=True)
                
                if unit.upper() == 'DAY':
                    unit_text = pluralize_unit(age_to, 'day')
                    range_desc.append(f"{op_text} {age_to} {unit_text}")
                else:
                    unit_text = pluralize_unit(age_to, 'year')
                    range_desc.append(f"{op_text} {age_to} {unit_text} old")
            
            if range_desc:
                age_range = " AND ".join(range_desc)
                if column == 'AGE_AT_EVENT':
                    return f"Patient age at event: {age_range}"
                else:
                    return f"Patient age: {age_range}"
            
        elif 'EPISODE' in column_check:
            # Handle episode filtering
            action = "Include" if in_not_in == "IN" else "Exclude"
            return f"{action} specific episode types"
        
        else:
            # Generic range handling
            range_desc = []
            if range_info.get('from'):
                from_info = range_info['from']
                op_text = format_operator_text(from_info['operator'], is_numeric=True)
                range_desc.append(f"{display_name} {op_text} {from_info['value']}")
            
            if range_desc:
                return " and ".join(range_desc)
    
    # Handle CONSULTATION_HEADING with EMISINTERNAL values specially
    if 'CONSULTATION_HEADING' in column_check and value_sets:
        action = "Include" if in_not_in == "IN" else "Exclude"
        
        for vs in value_sets:
            if vs.get('code_system') == 'EMISINTERNAL':
                for value in vs.get('values', []):
                    code_value = value.get('value', '')
                    display_name = value.get('display_name', '')
                    
                    if code_value.upper() == 'PROBLEM':
                        return f"{action} Consultations where the consultation heading is: {display_name}"
                    else:
                        return f"{action} consultations where heading is: {display_name}"
        
        # Fallback for non-EMISINTERNAL consultation heading filters
        return f"{action} specific consultation headings"
    
    # Handle non-range filters - show actual values when available
    elif any(col in ['READCODE', 'DRUGCODE', 'EPISODE', 'ISSUE_METHOD', 'DISPLAYTERM'] for col in column_check):
        action = "Include" if in_not_in == "IN" else "Exclude"
        
        # Count the values instead of listing them
        total_values = sum(len(vs.get('values', [])) for vs in value_sets)
        if total_values > 0:
            if 'READCODE' in column_check:
                return f"{action} {total_values} specified clinical codes"
            elif 'DRUGCODE' in column_check:
                return f"{action} {total_values} specified medication codes"
            elif 'EPISODE' in column_check:
                return f"{action} {total_values} specified episode types"
            elif 'ISSUE_METHOD' in column_check:
                return f"{action} {total_values} specified issue methods"
            elif 'DISPLAYTERM' in column_check:
                return f"{action} {total_values} specified medication names"
        else:
            # Fallback to generic descriptions
            if 'READCODE' in column_check:
                return f"{action} specific clinical codes"
            elif 'DRUGCODE' in column_check:
                return f"{action} specific medication codes"
            elif 'EPISODE' in column_check:
                return f"{action} episode types"
            elif 'ISSUE_METHOD' in column_check:
                return f"{action} specific issue methods"
            elif 'DISPLAYTERM' in column_check:
                return f"{action} specific medication names"
    
    elif any(col in ['DOB', 'GMS_DATE_OF_REGISTRATION'] for col in column_check):
        action = "Include" if in_not_in == "IN" else "Exclude"
        field_name = "birth dates" if 'DOB' in column_check else "registration dates"
        return f"{action} specific {field_name}"
    
    else:
        action = "Include" if in_not_in == "IN" else "Exclude"
        # Use display name if available, otherwise use column name
        field_name = display_name.lower() if display_name and display_name != column_display else column_display.lower().replace('_', ' ')
        return f"{action} {field_name}"


def render_complexity_analysis(metrics, analysis=None):
    """Render complexity analysis breakdown"""
    # Quick fix: If we have access to search reports, count parameters
    if analysis is None:
        analysis = st.session_state.get(SessionStateKeys.SEARCH_ANALYSIS)
    
    # Use the new unified pipeline to get correct search count (only if metrics shows 0 or is missing)
    if metrics.get('total_searches', 0) == 0:
        report_results = st.session_state.get(SessionStateKeys.REPORT_RESULTS)
        if report_results and hasattr(report_results, 'report_breakdown'):
            actual_search_count = len(report_results.report_breakdown.get('search', []))
            # Update metrics with correct search count only if it was missing/zero
            metrics['total_searches'] = actual_search_count
    
    if analysis and hasattr(analysis, 'orchestrated_results') and analysis.orchestrated_results:
        searches = analysis.orchestrated_results.searches
        if searches and metrics.get('total_parameters', 0) == 0:
            # Count parameters from actual search reports
            total_params = 0
            searches_with_params = 0
            global_params = set()
            
            for search in searches:
                search_has_params = False
                if hasattr(search, 'criteria_groups'):
                    for group in search.criteria_groups:
                        for criterion in group.criteria:
                            from ..xml_parsers.criterion_parser import check_criterion_parameters
                            param_info = check_criterion_parameters(criterion)
                            if param_info['has_parameters']:
                                search_has_params = True
                                total_params += len(param_info['parameter_names'])
                                if param_info['has_global']:
                                    global_params.update(param_info['parameter_names'])
                
                if search_has_params:
                    searches_with_params += 1
            
            # Update metrics with actual parameter counts
            if total_params > 0:
                metrics['total_parameters'] = total_params
                metrics['searches_with_parameters'] = searches_with_params
                metrics['global_parameters'] = len(global_params)
    
    st.markdown("**🎯 Complexity Breakdown:**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Searches", metrics.get('total_searches', 0))
        st.metric("Search Criteria", metrics.get('total_criteria', 0))
        st.metric("Value Sets", metrics.get('total_value_sets', 0))
        st.metric("Folder Structure", metrics.get('total_folders', 0))
        st.metric("Dependencies", metrics.get('total_dependencies', 0))
    
    with col2:
        st.metric("Filtering Rules", metrics.get('total_restrictions', 0))
        st.metric("Linked Criteria", metrics.get('linked_criteria_count', 0))
        st.metric("Population Refs", metrics.get('population_criteria_count', 0))
        st.metric("Parameters", metrics.get('total_parameters', 0))
        st.metric("Searches w/ Params", metrics.get('searches_with_parameters', 0))
        
        complexity_color = {
            'Basic': '🟢',
            'Moderate': '🟡',
            'Complex': '🟠',
            'Very Complex': '🔴'
        }
        
        st.markdown(f"**Overall Complexity:** {complexity_color.get(metrics['complexity_level'], '⚪')} {metrics['complexity_level']}")
        st.caption(f"Score: {metrics['complexity_score']}")
    
    # Complexity factors
    st.markdown("**🔍 What makes this complex:**")
    factors = []
    
    if metrics.get('total_reports', 0) > 10:
        factors.append(f"📊 Many reports ({metrics.get('total_reports', 0)})")
    if metrics.get('total_folders', 0) > 0:
        factors.append(f"📁 Folder structure ({metrics.get('total_folders', 0)} folders)")
    if metrics.get('total_dependencies', 0) > 0:
        factors.append(f"🔗 Report dependencies ({metrics.get('total_dependencies', 0)})")
    if metrics.get('population_criteria_count', 0) > 0:
        factors.append(f"🧑‍🤝‍🧑 Population references ({metrics.get('population_criteria_count', 0)})")
    if metrics.get('has_negation', False):
        factors.append("🚫 Exclusion logic")
    if metrics.get('has_latest_restrictions', False):
        factors.append("📅 Latest filtering")
    if metrics.get('has_branching_logic', False):
        factors.append("⚡ Branching logic (NEXT actions)")
    if metrics.get('total_parameters', 0) > 0:
        param_count = metrics.get('total_parameters', 0)
        global_count = metrics.get('global_parameters', 0)
        local_count = metrics.get('local_parameters', 0)
        if global_count > 0 and local_count > 0:
            factors.append(f"⚙️ Runtime parameters ({param_count} total: {global_count} global, {local_count} local)")
        elif global_count > 0:
            factors.append(f"🌐 Global parameters ({global_count} parameters)")
        else:
            factors.append(f"🏠 Local parameters ({local_count} parameters)")
    
    if factors:
        for factor in factors:
            st.caption(f"• {factor}")
    else:
        st.caption("• 🟢 Basic straightforward search")


def generate_rule_analysis_report(analysis, xml_filename: str):
    """Generate rule analysis report data for download"""
    # Works with both SearchRuleAnalysis (legacy) and CompleteAnalysisResult (orchestrated)
    
    # Extract the right attributes based on analysis type
    if hasattr(analysis, 'overall_complexity'):
        # CompleteAnalysisResult from orchestrated analysis
        complexity_metrics = analysis.overall_complexity
        rule_flow = analysis.rule_flow
        # Filter to only actual searches for detailed breakdown
        from ..core.report_classifier import ReportClassifier
        search_reports = ReportClassifier.filter_searches_only(analysis.reports)
    else:
        # SearchRuleAnalysis (legacy format)
        complexity_metrics = analysis.complexity_metrics
        rule_flow = analysis.rule_flow
        search_reports = analysis.reports
    
    # Create detailed analysis report
    report_lines = [
        f"EMIS Search Rule Analysis Report",
        f"Source File: {xml_filename}",
        f"Document ID: {analysis.document_id}",
        f"Created: {analysis.creation_time}",
        f"",
        f"COMPLEXITY OVERVIEW:",
        f"Level: {complexity_metrics.get('complexity_level', 'Basic')}",
        f"Score: {complexity_metrics.get('complexity_score', 0)}",
        f"",
        f"SEARCH EXECUTION FLOW:",
    ]
    
    for i, step in enumerate(rule_flow, 1):
        step_type = step.get('report_type', 'Search')
        report_lines.append(f"Step {i} - {step_type}: {step.get('report_name', 'Unknown')}")
        report_lines.append(f"  Action: {step.get('action', 'Unknown')}")
        description = step.get('description', '')
        if description:
            report_lines.append(f"  Description: {description}")
        report_lines.append("")
    
    report_lines.append("DETAILED RULE BREAKDOWN:")
    
    # Sort reports alphabetically with natural number ordering
    try:
        sorted_reports = sorted(search_reports, key=lambda x: _natural_sort_key(x.name))
    except (AttributeError, TypeError):
        sorted_reports = search_reports
    
    for report in sorted_reports:
        report_lines.append(f"\nREPORT: {report.name}")
        report_lines.append(f"Description: {getattr(report, 'description', 'No description')}")
        
        if hasattr(report, 'criteria_groups') and report.criteria_groups:
            for i, group in enumerate(report.criteria_groups):
                report_lines.append(f"\n  Criteria Group {i+1} (Logic: {group.member_operator}):")
                report_lines.append(f"  Action if matched: {group.action_if_true}")
                report_lines.append(f"  Action if not matched: {group.action_if_false}")
                
                for j, criterion in enumerate(group.criteria):
                    report_lines.append(f"\n    Rule {j+1}: {criterion.display_name}")
                    report_lines.append(f"    Table: {criterion.table}")
                    # Note: Criterion descriptions are often inaccurate, removed
                    if criterion.negation:
                        report_lines.append(f"    Action: Exclude (NOT)")
                    else:
                        report_lines.append(f"    Action: Include")
                    
                    if criterion.restrictions:
                        for restriction in criterion.restrictions:
                            report_lines.append(f"    Restriction: {restriction.description}")
        else:
            report_lines.append("  No criteria groups found")
    
    report_text = "\n".join(report_lines)
    filename = f"search_rule_analysis_{xml_filename.replace('.xml', '.txt')}"
    
    # Return the report data and filename for direct download
    return report_text, filename


def render_restriction_value_set_element(vs_elem):
    """Render a value set element found in a restriction using existing parsing logic"""
    try:
        from ..xml_parsers.value_set_parser import parse_value_set
        from ..xml_parsers.base_parser import get_namespaces
        
        # Parse the value set element using the existing parser
        namespaces = get_namespaces()
        parsed_vs = parse_value_set(vs_elem, namespaces)
        
        if parsed_vs:
            # Use the same rendering logic as main value sets
            vs_title = parsed_vs['description'] if parsed_vs['description'] else "Value Set"
            vs_count = len(parsed_vs['values'])
            icon = "📋"
            
            with st.expander(f"{icon} {vs_title} ({vs_count} codes)", expanded=False):
                # Enhanced code system descriptions (same as main)
                code_system = parsed_vs['code_system']
                system_display = code_system
                if 'SNOMED_CONCEPT' in code_system:
                    system_display = "SNOMED Clinical Terminology"
                elif 'SCT_DRGGRP' in code_system:
                    system_display = "Drug Group Classification"
                elif 'EMISINTERNAL' in code_system:
                    system_display = "EMIS Internal Classifications"
                elif 'SCT_APPNAME' in code_system:
                    system_display = "Medical Appliance Names"
                elif code_system == 'LIBRARY_ITEM':
                    system_display = "EMIS Internal Library"
                
                st.caption(f"**System:** {system_display}")
                if parsed_vs['id']:
                    st.caption(f"**ID:** {parsed_vs['id']}")
                
                # Use the EXACT same code data logic as main value sets
                import pandas as pd
                code_data = []
                
                # Get lookup data from session state (same as main)
                lookup_df = st.session_state.get(SessionStateKeys.LOOKUP_DF)
                emis_guid_col = st.session_state.get(SessionStateKeys.EMIS_GUID_COL)
                snomed_code_col = st.session_state.get(SessionStateKeys.SNOMED_CODE_COL)
                
                # Batch lookup preparation (same as main)
                emis_codes_to_lookup = []
                for value in parsed_vs['values']:
                    if not value['is_refset']:
                        emis_codes_to_lookup.append(str(value['value']).strip())
                
                # Perform batch lookup if we have lookup data
                snomed_lookup = {}
                if lookup_df is not None and emis_guid_col and snomed_code_col and emis_codes_to_lookup:
                    lookup_subset = lookup_df[lookup_df[emis_guid_col].isin(emis_codes_to_lookup)]
                    snomed_lookup = dict(zip(lookup_subset[emis_guid_col].astype(str).str.strip(), 
                                           lookup_subset[snomed_code_col].astype(str).str.strip()))
                
                # Process each value (EXACT same logic as main)
                for value in parsed_vs['values']:
                    code_value = value['value']
                    code_name = value.get('display_name', code_value)
                    
                    if value['is_refset']:
                        # For refsets: EMIS Code = SNOMED Code, Description from XML
                        snomed_code = code_value  # Refset codes are direct SNOMED codes
                        scope = '🎯 Refset'
                        # Use the valueset description as the code description for refsets
                        description = parsed_vs.get('description', code_name) if parsed_vs.get('description') != code_name else code_name
                    else:
                        # Use batch lookup result or fallback for regular codes
                        snomed_code = snomed_lookup.get(str(code_value).strip(), 'Not found' if code_value != "No code specified" else 'N/A')
                        description = code_name
                        
                        if value['include_children']:
                            scope = '👪 + Children'
                        else:
                            scope = '🎯 Exact'
                    
                    code_data.append({
                        'EMIS Code': code_value,
                        'SNOMED Code': snomed_code,
                        'Description': description,
                        'Scope': scope,
                        'Is Refset': 'Yes' if value['is_refset'] else 'No'
                    })
                
                if code_data:
                    # Create and display dataframe (same as main)
                    codes_df = pd.DataFrame(code_data)
                    
                    st.dataframe(
                        codes_df,
                        width='stretch',
                        hide_index=True,
                        column_config={
                            "EMIS Code": st.column_config.TextColumn(
                                "🔍 EMIS Code",
                                width="medium"
                            ),
                            "SNOMED Code": st.column_config.TextColumn(
                                "⚕️ SNOMED Code", 
                                width="medium"
                            ),
                            "Description": st.column_config.TextColumn(
                                "📝 Description",
                                width="large"
                            ),
                            "Scope": st.column_config.TextColumn(
                                "🔗 Scope",
                                width="small"
                            ),
                            "Is Refset": st.column_config.TextColumn(
                                "🎯 Refset",
                                width="small"
                            )
                        }
                    )
                else:
                    st.markdown(info_box("No codes found for this value set"), unsafe_allow_html=True)
        
    except Exception as e:
        st.caption(f"⚠️ Error displaying restriction codes: {str(e)}")


def render_restriction_value_set(vs_description):
    """Render a value set found in a restriction - with same formatting as main value sets"""
    try:
        # Determine if this is a refset (SNOMED code) or EMIS code based on the format
        # EMIS codes are numeric (like 2738571000000112), refsets are alphanumeric (like AST_COD)
        is_refset = not vs_description.isdigit()
        
        # Create a fake value set object to reuse the existing rendering logic
        fake_vs = {
            'description': vs_description,
            'code_system': 'SNOMED_CONCEPT',
            'id': vs_description,
            'values': [{
                'value': vs_description,
                'display_name': vs_description,
                'include_children': False,
                'is_refset': is_refset,  # Detect based on code format
                'is_library_item': False
            }]
        }
        
        # Use the same rendering logic as main value sets
        vs_title = fake_vs['description'] if fake_vs['description'] else "Value Set"
        vs_count = len(fake_vs['values'])
        icon = "📋"
        
        with st.expander(f"{icon} {vs_title} ({vs_count} codes)", expanded=False):
            # Enhanced code system descriptions
            code_system = fake_vs['code_system']
            system_display = "SNOMED Clinical Terminology"
            
            st.caption(f"**System:** {system_display}")
            if fake_vs['id']:
                st.caption(f"**ID:** {fake_vs['id']}")
            
            # Display codes as scrollable dataframe with icons
            import pandas as pd
            code_data = []
            
            # Get lookup table from session state
            lookup_df = st.session_state.get(SessionStateKeys.LOOKUP_DF)
            lookup = st.session_state.get(SessionStateKeys.LOOKUP, {})
            
            for value in fake_vs['values']:
                code_value = value['value']
                code_name = value.get('display_name', code_value)
                
                if value['is_refset']:
                    # For refsets: EMIS Code = SNOMED Code (1:1 match)
                    snomed_code = code_value  # Refset codes are direct SNOMED codes
                    scope = '🎯 Refset'
                    # Use the value set description, not the code itself
                    description = fake_vs.get('description', code_value)
                    
                    code_data.append({
                        'EMIS Code': code_value,
                        'SNOMED Code': snomed_code,
                        'Description': description,
                        'Scope': scope,
                        'Is Refset': 'Yes'
                    })
                else:
                    # Regular lookup
                    if lookup and code_value in lookup:
                        lookup_entry = lookup[code_value]
                        snomed_code = lookup_entry.get('EMIS Code', code_value)
                        description = lookup_entry.get('Description', code_name)
                        scope = get_code_scope(lookup_entry)
                        is_refset = 'Yes' if scope == '🎯 Refset' else 'No'
                    else:
                        snomed_code = 'Not found'
                        description = code_name
                        scope = '❓ Unknown'
                        is_refset = 'Unknown'
                    
                    code_data.append({
                        'EMIS Code': code_value,
                        'SNOMED Code': snomed_code,
                        'Description': description,
                        'Scope': scope,
                        'Is Refset': is_refset
                    })
            
            if code_data:
                df = pd.DataFrame(code_data)
                st.dataframe(
                    df,
                    width='stretch',
                    hide_index=True,
                    column_config={
                        "EMIS Code": st.column_config.TextColumn(
                            "🔍 EMIS Code",
                            width="medium"
                        ),
                        "SNOMED Code": st.column_config.TextColumn(
                            "⚕️ SNOMED Code", 
                            width="medium"
                        ),
                        "Description": st.column_config.TextColumn(
                            "📝 Description",
                            width="large"
                        ),
                        "Scope": st.column_config.TextColumn(
                            "🔗 Scope",
                            width="small"
                        ),
                        "Is Refset": st.column_config.TextColumn(
                            "🎯 Refset",
                            width="small"
                        )
                    }
                )
            else:
                st.markdown(info_box("No codes found for this value set"), unsafe_allow_html=True)
        
    except Exception as e:
        st.caption(f"⚠️ Error displaying restriction codes: {str(e)}")


def export_rule_analysis(analysis, xml_filename: str):
    """Legacy export function - replaced by generate_rule_analysis_report"""
    # This function is kept for backward compatibility but should not be used
    # Now works with both SearchRuleAnalysis and CompleteAnalysisResult
    report_text, filename = generate_rule_analysis_report(analysis, xml_filename)
    st.markdown(success_box("✅ Analysis report ready for download!"), unsafe_allow_html=True)
    return report_text, filename


def render_patient_demographics_filter(column_filter):
    """Render patient demographics column filter description with area codes using EMIS-style phrasing"""
    column_display = column_filter.get('column_display', column_filter.get('column_name', 'Unknown'))
    in_not_in = column_filter.get('in_not_in', 'IN')
    
    # Extract year from column name for EMIS-style display
    year_match = None
    column_upper = column_display.upper()
    if '2011' in column_upper:
        year_match = '2011'
    elif '2015' in column_upper:
        year_match = '2015'
    elif '2021' in column_upper:
        year_match = '2021'
    elif '2031' in column_upper:
        year_match = '2031'
    
    year_text = f" ({year_match})" if year_match else ""
    action = "Include" if in_not_in == "IN" else "Exclude"
    
    # Check for grouped patient demographics values
    grouped_values = column_filter.get('grouped_demographics_values', [])
    demographics_count = column_filter.get('demographics_count', 0)
    
    if grouped_values and demographics_count > 1:
        # Multiple LSOA codes - show first few and count
        if demographics_count <= 5:
            # Show all values for small lists
            all_codes = ", ".join(grouped_values)
            return f"{action} Patients where the Lower Layer Area{year_text} is in: {all_codes}"
        else:
            # Show first 3 and count for larger lists
            first_few = ", ".join(grouped_values[:3])
            remaining = demographics_count - 3
            summary_text = f"{action} Patients where the Lower Layer Area{year_text} is in {demographics_count} areas:"
            return f"{summary_text} {first_few} and {remaining} other LSOA areas"
    else:
        # Single or fallback patient demographics code
        values = column_filter.get('values', [])
        if values and len(values) > 0:
            if len(values) == 1:
                return f"{action} Patients where the Lower Layer Area{year_text} is in: {values[0]}"
            else:
                return f"{action} Patients where the Lower Layer Area{year_text} is in: {', '.join(values[:3])}{'...' if len(values) > 3 else ''}"
        else:
            return f"{action} Patients where the Lower Layer Area{year_text} meets specified criteria"
