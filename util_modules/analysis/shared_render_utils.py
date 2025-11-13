"""
Shared Render Utilities for Search Rule Visualization
Contains utility functions used by both search rule and report structure visualizers
"""

import streamlit as st
from ..core import SearchManager, ReportClassifier


def _render_rule_step(step, reports, show_sequence_number=False):
    """Render a single rule step"""
    # Find the corresponding report for details
    report = next((r for r in reports if r.id == step.get('report_id')), None)
    
    # Create expandable section for each step - handle missing keys safely
    step_num = step.get('step', '?')
    report_name = step.get('report_name', 'Unknown Report')
    step_title = f"Search {step_num}: {report_name}" if show_sequence_number else report_name
    
    # Add icons and parent information
    if step.get('is_parent', False):
        step_title += " 🔵 (Base Population)"
    else:
        step_title += " ⚡"
        if step.get('parent_name'):
            step_title += f" → child of: {step.get('parent_name')}"
    
    with st.expander(step_title, expanded=False):
        _render_rule_step_content(report, step)


def _render_rule_step_content(report, step):
    """Render the content of a rule step"""
    col1, col2 = st.columns([1, 2])
    
    with col1:
        if step and step.get('is_parent', False):
            st.info("**Type:** Base Population")
            st.caption("🔵 Base population that children filter from")
        else:
            st.warning("**Type:** Clinical Search")
            st.caption("⚡ Applies specific clinical criteria")
            
            # Show parent relationship
            if step and step.get('parent_name'):
                st.caption(f"📋 **Inherits from:** {step.get('parent_name')}")
    
    with col2:
        if step:
            description = step.get('description', 'No description available')
            st.markdown(f"**Description:** {description}")
        
        if report and hasattr(report, 'criteria_groups') and report.criteria_groups:
            st.markdown("**Contains:**")
            for i, group in enumerate(report.criteria_groups):
                criteria_count = len(group.criteria) if hasattr(group, 'criteria') and group.criteria else 0
                group_summary = f"• Group {i+1}: {criteria_count} rule(s)"
                
                member_op = getattr(group, 'member_operator', 'AND')
                if member_op != "AND":
                    group_summary += f" ({member_op} logic)"
                
                # Add action summary
                action_if_true = getattr(group, 'action_if_true', 'SELECT')
                if action_if_true == "SELECT":
                    group_summary += " → ✅ Include if matched"
                else:
                    group_summary += " → ❌ Exclude if matched"
                
                st.caption(group_summary)
                
                # Show what each rule is looking for
                if hasattr(group, 'criteria') and group.criteria:
                    for j, criterion in enumerate(group.criteria):
                        criterion_table = getattr(criterion, 'table', 'Unknown')
                        criterion_name = getattr(criterion, 'display_name', 'Unnamed criterion')
                        
                        if criterion_table == "EVENTS" and hasattr(criterion, 'value_sets') and criterion.value_sets:
                            # Count total codes in this criterion
                            total_codes = 0
                            try:
                                total_codes = sum(len(vs.get('values', [])) for vs in criterion.value_sets if isinstance(vs, dict))
                            except (TypeError, AttributeError):
                                total_codes = 0
                            st.caption(f"  ├─ Rule {j+1}: {criterion_name} ({total_codes} codes)")
                        elif criterion_table == "PATIENTS":
                            # Patient criteria (age, registration, etc.)
                            st.caption(f"  ├─ Rule {j+1}: {criterion_name} (patient criteria)")
                        else:
                            # Other table types
                            st.caption(f"  ├─ Rule {j+1}: {criterion_name}")


def _is_parent_report(report):
    """Check if a report is a parent report (base population)"""
    # A report is a base population (parent) only if:
    # 1. It has parent_type 'ACTIVE' (active patient list) - these are true base populations
    # 2. It's named "All currently registered patients" or similar base population patterns
    
    is_base_population = (
        report.parent_type == 'ACTIVE' or
        'All currently registered patients' in report.name or
        'Active patients' in report.name
    )
    
    return is_base_population


def _render_report_type_specific_info(selected_search, report_type):
    """Render report type-specific information for List, Audit, and Aggregate reports"""
    
    if report_type == "[List Report]":
        if hasattr(selected_search, 'column_groups') and selected_search.column_groups:
            st.markdown("### 📊 List Report Structure")
            for i, column_group in enumerate(selected_search.column_groups):
                with st.expander(f"📋 Column Group {i+1}: {column_group.get('display_name', 'Unnamed Group')}", expanded=i==0):
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        st.markdown(f"**Logical Table:** {column_group.get('logical_table', 'Not specified')}")
                        if column_group.get('has_criteria'):
                            st.info("🔍 Has filtering criteria")
                    with col2:
                        if column_group.get('columns'):
                            st.markdown("**Columns to display:**")
                            for col in column_group['columns']:
                                st.markdown(f"• {col.get('display_name', col.get('column', 'Unnamed column'))}")
    
    elif report_type == "[Audit Report]":
        if hasattr(selected_search, 'custom_aggregate') and selected_search.custom_aggregate:
            st.markdown("### 📈 Audit Report Structure")
            agg_data = selected_search.custom_aggregate
            
            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown(f"**Logical Table:** {agg_data.get('logical_table', 'Not specified')}")
                if agg_data.get('population_reference'):
                    st.markdown(f"**Population Reference:** {agg_data['population_reference'][:8]}...")
            
            with col2:
                result_info = agg_data.get('result', {})
                st.markdown(f"**Result Source:** {result_info.get('source', 'Not specified')}")
                st.markdown(f"**Calculation:** {result_info.get('calculation_type', 'Not specified')}")
            
            if agg_data.get('groups'):
                st.markdown("**Grouping:**")
                for group in agg_data['groups']:
                    st.markdown(f"• {group.get('display_name', 'Unnamed group')}: {group.get('grouping_column', 'No column')}")
    
    elif report_type == "[Aggregate Report]":
        if hasattr(selected_search, 'statistical_groups') and selected_search.statistical_groups:
            st.markdown("### 📊 Aggregate Report Structure")
            
            # Display logical table
            if hasattr(selected_search, 'logical_table') and selected_search.logical_table:
                st.markdown(f"**Logical Table:** {selected_search.logical_table}")
            
            # Display statistical setup with resolved names
            rows_group = next((g for g in selected_search.statistical_groups if g.get('type') == 'rows'), None)
            cols_group = next((g for g in selected_search.statistical_groups if g.get('type') == 'columns'), None)
            result_group = next((g for g in selected_search.statistical_groups if g.get('type') == 'result'), None)
            
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if rows_group:
                    st.info(f"**Rows:** {rows_group.get('group_name', 'Not specified')}")
                else:
                    st.warning("**Rows:** Not configured")
            
            with col2:
                if cols_group:
                    st.info(f"**Columns:** {cols_group.get('group_name', 'Not specified')}")
                else:
                    st.warning("**Columns:** Not configured")
            
            with col3:
                if result_group:
                    calc_type = result_group.get('calculation_type', 'count')
                    st.success(f"**Result:** {calc_type.title()}")
                else:
                    st.error("**Result:** Not configured")
            
            # Display aggregate groups (the actual grouping definitions)
            if hasattr(selected_search, 'aggregate_groups') and selected_search.aggregate_groups:
                st.markdown("**Available Groups:**")
                for i, group in enumerate(selected_search.aggregate_groups):
                    group_name = group.get('display_name', f"Group {i+1}")
                    columns = ', '.join(group.get('grouping_columns', []))
                    st.markdown(f"• **{group_name}:** {columns}")
            
            # Display built-in criteria if present
            if hasattr(selected_search, 'aggregate_criteria') and selected_search.aggregate_criteria:
                st.markdown("### 🔍 Built-in Report Filters")
                st.info("This aggregate report has its own built-in criteria that filters the data before aggregation.")
                
                criteria_data = selected_search.aggregate_criteria
                for i, criteria_group in enumerate(criteria_data.get('criteria_groups', [])):
                    with st.expander(f"Filter Group {i+1} - Logic: {criteria_group.get('member_operator', 'AND')}", expanded=True):
                        for j, criterion in enumerate(criteria_group.get('criteria', [])):
                            st.markdown(f"**Filter {j+1}: {criterion.get('display_name', 'Unnamed filter')}**")
                            st.markdown(f"• Table: {criterion.get('table', 'Not specified')}")
                            
                            for k, filter_item in enumerate(criterion.get('filters', [])):
                                if filter_item.get('value_type') == 'valueSet':
                                    st.markdown(f"• {filter_item.get('display_name', 'Column')}: {filter_item.get('code_description', filter_item.get('code', 'No code'))}")
                                elif filter_item.get('value_type') == 'rangeValue':
                                    # Format the range value properly
                                    value = filter_item.get('value', '')
                                    unit = filter_item.get('unit', '')
                                    relation = filter_item.get('relation', '')
                                    operator = filter_item.get('operator', '')
                                    
                                    # Convert to EMIS-style format
                                    if operator == 'GT' and relation == 'RELATIVE' and value.startswith('-'):
                                        display_text = f"after {value[1:]} {unit.lower()} before the search date"
                                    else:
                                        display_text = f"{operator} {value} {unit}"
                                    
                                    st.markdown(f"• {filter_item.get('display_name', 'Date')}: {display_text}")
