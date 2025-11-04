"""
Layout utilities for complex UI arrangements
Handles navigation, folder hierarchies, and data presentation patterns
"""

import streamlit as st
from typing import Dict, List, Any, Optional, Callable


class NavigationManager:
    """Manages navigation state and dropdown selections"""
    
    @staticmethod
    def create_hierarchical_dropdown(hierarchy: Dict, 
                                   primary_label: str,
                                   secondary_label: str,
                                   primary_key: str,
                                   secondary_key: str,
                                   format_func: Optional[Callable] = None) -> tuple:
        """
        Create a hierarchical dropdown navigation system
        
        Args:
            hierarchy: Dictionary representing the hierarchy
            primary_label: Label for the primary dropdown
            secondary_label: Label for the secondary dropdown
            primary_key: Session state key for primary selection
            secondary_key: Session state key for secondary selection
            format_func: Optional function to format secondary options
            
        Returns:
            Tuple of (primary_selection, secondary_selection, secondary_index)
        """
        col1, col2 = st.columns([1, 1])
        
        with col1:
            primary_options = list(hierarchy.keys())
            default_index = 0 if primary_key not in st.session_state else None
            
            primary_selection = st.selectbox(
                primary_label,
                options=primary_options,
                index=default_index,
                key=primary_key
            )
        
        with col2:
            secondary_selection = None
            secondary_index = None
            
            if primary_selection and hierarchy[primary_selection]:
                secondary_options = hierarchy[primary_selection]
                
                if format_func:
                    display_options = [format_func(opt, i) for i, opt in enumerate(secondary_options)]
                    secondary_index = st.selectbox(
                        secondary_label,
                        options=range(len(secondary_options)),
                        format_func=lambda x: display_options[x] if x < len(display_options) else "None",
                        key=secondary_key
                    )
                    secondary_selection = secondary_options[secondary_index] if secondary_index is not None else None
                else:
                    secondary_selection = st.selectbox(
                        secondary_label,
                        options=secondary_options,
                        key=secondary_key
                    )
            else:
                st.selectbox(secondary_label, options=["No options available"], disabled=True)
        
        return primary_selection, secondary_selection, secondary_index


class DataRenderer:
    """Handles rendering of complex data structures"""
    
    @staticmethod
    def render_criteria_group(group: Any, group_index: int, expanded: bool = False) -> None:
        """
        Render a criteria group with standardized formatting
        
        Args:
            group: The criteria group object
            expanded: Whether to expand the section by default
        """
        # Build group title
        operator = getattr(group, 'member_operator', 'AND')
        criteria_count = len(getattr(group, 'criteria', []))
        
        title = f"Group {group_index + 1}: {operator} logic ({criteria_count} criteria)"
        
        with st.expander(title, expanded=expanded):
            # Render group details
            st.markdown(f"**Logic:** {operator}")
            st.markdown(f"**Criteria Count:** {criteria_count}")
            
            # Render actions
            action_true = getattr(group, 'action_if_true', 'SELECT')
            action_false = getattr(group, 'action_if_false', 'REJECT')
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**If True:** {action_true}")
            with col2:
                st.markdown(f"**If False:** {action_false}")
    
    @staticmethod
    def render_value_set_summary(value_sets: List[Dict], title: str = "Value Sets") -> None:
        """
        Render a summary of value sets
        
        Args:
            value_sets: List of value set dictionaries
            title: Title for the section
        """
        if not value_sets:
            return
            
        st.markdown(f"**{title}:**")
        
        for vs in value_sets:
            vs_desc = vs.get('description', 'Unknown')
            vs_count = len(vs.get('values', []))
            code_system = vs.get('code_system', 'Unknown')
            
            with st.expander(f"📋 {vs_desc} ({vs_count} codes)", expanded=False):
                st.markdown(f"**Code System:** {code_system}")
                st.markdown(f"**Description:** {vs_desc}")
                st.markdown(f"**Code Count:** {vs_count}")
                
                # Show sample codes if available
                values = vs.get('values', [])
                if values:
                    st.markdown("**Sample Codes:**")
                    for i, value in enumerate(values[:5]):  # Show first 5
                        code = value.get('value', 'N/A')
                        display_name = value.get('display_name', 'N/A')
                        st.markdown(f"- `{code}`: {display_name}")
                    
                    if len(values) > 5:
                        st.markdown(f"... and {len(values) - 5} more codes")
    
    @staticmethod
    def render_filter_conditions(filters: List[Dict], title: str = "Filter Conditions") -> None:
        """
        Render filter conditions with proper formatting
        
        Args:
            filters: List of filter dictionaries
            title: Title for the section
        """
        if not filters:
            return
            
        st.markdown(f"**{title}:**")
        
        for filter_item in filters:
            column = filter_item.get('column', 'Unknown')
            operator = filter_item.get('in_not_in', 'IN')
            
            st.markdown(f"- **{column}** {operator}")
            
            # Render range information if present
            range_info = filter_item.get('range')
            if range_info:
                DataRenderer._render_range_info(range_info)
    
    @staticmethod
    def _render_range_info(range_info: Dict) -> None:
        """Helper method to render range information"""
        if range_info.get('from'):
            from_info = range_info['from']
            operator = from_info.get('operator', '')
            value = from_info.get('value', '')
            unit = from_info.get('unit', '')
            st.markdown(f"  - From: {operator} {value} {unit}")
        
        if range_info.get('to'):
            to_info = range_info['to']
            operator = to_info.get('operator', '')
            value = to_info.get('value', '')
            unit = to_info.get('unit', '')
            st.markdown(f"  - To: {operator} {value} {unit}")


class StepRenderer:
    """Handles rendering of step-by-step processes"""
    
    @staticmethod
    def render_execution_step(step: Dict, step_number: int, expanded: bool = False) -> None:
        """
        Render an execution step with consistent formatting
        
        Args:
            step: Dictionary containing step information
            step_number: Step number for display
            expanded: Whether to expand the step by default
        """
        # Build step title
        step_name = step.get('name', f'Step {step_number}')
        step_type = step.get('type', 'Unknown')
        
        # Add emoji based on step type
        emoji_map = {
            'search': '🔍',
            'filter': '🔽',
            'population': '🧑‍🤝‍🧑',
            'report': '📊',
            'unknown': '❓'
        }
        emoji = emoji_map.get(step_type.lower(), '📋')
        
        title = f"{emoji} Step {step_number}: {step_name}"
        
        with st.expander(title, expanded=expanded):
            StepRenderer._render_step_content(step)
    
    @staticmethod
    def _render_step_content(step: Dict) -> None:
        """Render the content of a single step"""
        # Basic step information
        if step.get('description'):
            st.markdown(f"**Description:** {step['description']}")
        
        if step.get('type'):
            st.markdown(f"**Type:** {step['type']}")
        
        # Render step-specific content
        if step.get('criteria_count'):
            st.markdown(f"**Criteria:** {step['criteria_count']}")
        
        if step.get('dependencies'):
            st.markdown("**Dependencies:**")
            for dep in step['dependencies']:
                st.markdown(f"- {dep}")
        
        # Render actions
        if step.get('action_if_true') or step.get('action_if_false'):
            col1, col2 = st.columns(2)
            with col1:
                if step.get('action_if_true'):
                    action_color = StepRenderer._get_action_color(step['action_if_true'])
                    st.markdown(f"**If True:** {action_color} {step['action_if_true']}")
            with col2:
                if step.get('action_if_false'):
                    action_color = StepRenderer._get_action_color(step['action_if_false'])
                    st.markdown(f"**If False:** {action_color} {step['action_if_false']}")
    
    @staticmethod
    def _get_action_color(action: str) -> str:
        """Get color emoji for action type"""
        action_colors = {
            'SELECT': '🟢',
            'REJECT': '🔴',
            'NEXT': '🔀'
        }
        return action_colors.get(action.upper(), '⚪')


class TreeRenderer:
    """Handles rendering of tree-like hierarchical data"""
    
    @staticmethod
    def render_folder_tree(hierarchy: Dict, title: str = "Folder Structure") -> None:
        """
        Render a folder tree structure
        
        Args:
            hierarchy: Dictionary representing the folder hierarchy
            title: Title for the tree section
        """
        st.markdown(f"### {title}")
        
        for folder_name, folder_data in hierarchy.items():
            with st.expander(f"📁 {folder_name}", expanded=False):
                TreeRenderer._render_folder_contents(folder_data)
    
    @staticmethod
    def _render_folder_contents(folder_data: Dict) -> None:
        """Render contents of a folder"""
        # Render subfolders
        subfolders = folder_data.get('subfolders', {})
        if subfolders:
            st.markdown("**Subfolders:**")
            for subfolder_name in subfolders.keys():
                st.markdown(f"📁 {subfolder_name}")
        
        # Render searches
        searches = folder_data.get('searches', [])
        if searches:
            st.markdown("**Searches:**")
            for search in searches:
                search_name = getattr(search, 'name', 'Unknown')
                st.markdown(f"🔍 {search_name}")
        
        # Render reports
        reports = folder_data.get('reports', [])
        if reports:
            st.markdown("**Reports:**")
            for report in reports:
                report_name = getattr(report, 'name', 'Unknown')
                st.markdown(f"📊 {report_name}")