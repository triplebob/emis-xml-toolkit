"""
Linked Criteria Handler Module
Handles the display and logic for linked criteria in EMIS search rules
"""

import streamlit as st
from ..xml_parsers.criterion_parser import SearchCriterion


def render_linked_criteria(criterion, main_criterion):
    """
    Render linked criteria section with proper temporal relationships and code separation
    
    Args:
        criterion: The main criterion that has linked criteria
        main_criterion: Reference to the main criterion (same as criterion, for context)
    """
    if not criterion.linked_criteria:
        return
    
    st.markdown("---")
    st.markdown("**🔗 Linked Criteria:**")
    st.caption("Then include additional conditions where:")
    
    for i, linked_criterion in enumerate(criterion.linked_criteria):
        # Show temporal relationship description
        temporal_desc = generate_temporal_relationship_description(linked_criterion, criterion)
        if temporal_desc:
            st.markdown(f"**📅 {temporal_desc}**")
        
        # Show what codes/conditions to look for
        st.markdown(f"**{linked_criterion.display_name}** where:")
        
        # Show linked criteria value sets - separate EMISINTERNAL from clinical codes
        if linked_criterion.value_sets:
            # Separate EMISINTERNAL codes from clinical codes
            clinical_value_sets = []
            emisinternal_value_sets = []
            
            for vs in linked_criterion.value_sets:
                if vs.get('code_system') == 'EMISINTERNAL':
                    emisinternal_value_sets.append(vs)
                else:
                    clinical_value_sets.append(vs)
            
            # Display clinical codes in expandable format with counts
            if clinical_value_sets:
                for vs_idx, vs in enumerate(clinical_value_sets, 1):
                    vs_title = vs['description'] if vs['description'] else "Value Set"
                    vs_count = len(vs['values'])
                    
                    with st.expander(f"📋 {vs_title} ({vs_count} codes)", expanded=False):
                        st.caption(f"**System:** {vs['code_system']}")
                        if vs['id']:
                            st.caption(f"**ID:** {vs['id']}")
                        
                        # Display codes as scrollable dataframe with standard format
                        import pandas as pd
                        code_data = []
                        
                        # PERFORMANCE OPTIMIZATION: Batch SNOMED lookups instead of individual lookups
                        # Get lookup table from session state
                        lookup_df = st.session_state.get('lookup_df')
                        emis_guid_col = st.session_state.get('emis_guid_col')
                        snomed_code_col = st.session_state.get('snomed_code_col')
                        
                        # Create lookup dictionary for batch processing
                        snomed_lookup = {}
                        if lookup_df is not None and emis_guid_col is not None and snomed_code_col is not None:
                            try:
                                # Extract all EMIS GUIDs from the value set
                                emis_guids = [value['value'] for value in vs['values'] if value['value']]
                                
                                if emis_guids:
                                    # Single DataFrame operation to lookup all codes at once
                                    matching_rows = lookup_df[lookup_df[emis_guid_col].astype(str).str.strip().isin([str(guid).strip() for guid in emis_guids])]
                                    snomed_lookup = dict(zip(matching_rows[emis_guid_col].astype(str).str.strip(), matching_rows[snomed_code_col]))
                            except Exception:
                                # Fallback to individual lookups if batch fails
                                pass
                        
                        for j, value in enumerate(vs['values']):
                            code_value = value['value'] if value['value'] else "No code specified"
                            code_name = value.get('display_name', '')
                            
                            # Use batch lookup result or fallback
                            snomed_code = snomed_lookup.get(str(code_value).strip(), 'Not found' if code_value != "No code specified" else 'N/A')
                            
                            # Determine scope indicator
                            if value.get('is_refset', False):
                                scope = '🎯 Refset'
                            elif value.get('include_children', False):
                                scope = '👪 + Children'
                            else:
                                scope = '🎯 Exact'
                            
                            code_data.append({
                                'EMIS Code': code_value,
                                'SNOMED Code': snomed_code,
                                'Description': code_name,
                                'Scope': scope,
                                'Is Refset': 'Yes' if value.get('is_refset', False) else 'No'
                            })
                        
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
            
            # EMISINTERNAL codes will be shown in Additional Filters section below
        
        # Show additional filters (both column filters and EMISINTERNAL codes)
        # But avoid duplicating CONSULTATION_HEADING that appears in both places
        if linked_criterion.column_filters or emisinternal_value_sets:
            st.markdown("**⚙️ Additional Filters:**")
            
            # Check if we have CONSULTATION_HEADING column filters to avoid duplication
            has_consultation_heading_filter = any(
                cf.get('column') == 'CONSULTATION_HEADING' 
                for cf in linked_criterion.column_filters
            ) if linked_criterion.column_filters else False
            
            # Show column filters
            if linked_criterion.column_filters:
                # Import here to avoid circular imports
                from .search_rule_visualizer import render_column_filter
                for cf in linked_criterion.column_filters:
                    filter_desc = render_column_filter(cf)
                    if filter_desc:
                        st.caption(f"• {filter_desc}")
            
            # Show EMISINTERNAL codes as filter descriptions, but skip PROBLEM if we already have CONSULTATION_HEADING
            if emisinternal_value_sets:
                for vs in emisinternal_value_sets:
                    for value in vs['values']:
                        # Convert EMISINTERNAL codes to descriptive filters
                        code_value = value['value'] if value['value'] else "Unknown"
                        display_name = value['display_name'] if value['display_name'] else code_value
                        
                        # Skip PROBLEM if we already have CONSULTATION_HEADING filter (they're the same thing)
                        if code_value.upper() == 'PROBLEM' and has_consultation_heading_filter:
                            continue
                        
                        # Generic EMISINTERNAL handling for value sets in linked criteria
                        # Specific column filter handling (like CONSULTATION_HEADING) happens in render_column_filter
                        if code_value.upper() in ['COMPLICATION', 'ONGOING', 'RESOLVED']:
                            status_descriptions = {
                                'COMPLICATION': f'Include complications: {display_name}',
                                'ONGOING': f'Include ongoing conditions: {display_name}',
                                'RESOLVED': f'Include resolved conditions: {display_name}'
                            }
                            filter_desc = status_descriptions.get(code_value.upper(), f"Include {display_name.lower()}")
                        else:
                            # Generic EMISINTERNAL classification for other types (PROBLEM, etc.)
                            filter_desc = f"Include EMISINTERNAL classification: {display_name}" if display_name else f"Include internal code: {code_value}"
                        
                        st.caption(f"• {filter_desc}")
        
        # Dynamic explanation (removed for cleaner display)
        # explanation = generate_linked_criteria_explanation(linked_criterion, criterion)


def generate_temporal_relationship_description(linked_criterion, main_criterion):
    """
    Generate description of temporal relationship between criteria
    
    Args:
        linked_criterion: The linked criterion being checked
        main_criterion: The main criterion it's linked to
        
    Returns:
        str: Human-readable description of the temporal relationship
    """
    # Check if the linked criterion has relationship information parsed from XML
    if hasattr(linked_criterion, 'relationship') and linked_criterion.relationship:
        relationship = linked_criterion.relationship
        parent_col = relationship.get('parent_column_display_name', 'Date')
        child_col = relationship.get('child_column_display_name', 'Date')
        
        # Check for range value with operator
        range_value = relationship.get('range_value', {})
        if range_value:
            # Parse the operator and create appropriate description
            operator_desc = _parse_relationship_operator(range_value)
            if operator_desc:
                return f"The {child_col} is {operator_desc} the {parent_col} from the above feature and where:"
        
        # If no range specified, default to "equal to"
        return f"The {child_col} is equal to the {parent_col} from the above feature and where:"
    
    # Fallback to pattern-based logic for backwards compatibility
    main_table = main_criterion.table.lower()
    linked_table = linked_criterion.table.lower()
    
    if "medication" in main_table and "event" in linked_table:
        return "The Date is more than 0 days after the Date of Issue from the above feature and where:"
    elif "event" in main_table and "event" in linked_table:
        return "The Date is equal to the Date from the above feature and where:"
    else:
        return "This condition is checked in relation to the main criterion above and where:"


def _parse_relationship_operator(range_value):
    """
    Parse relationship range value to generate human-readable operator description
    
    Args:
        range_value: Dictionary containing 'from' and/or 'to' range information
        
    Returns:
        str: Human-readable operator description (e.g., "more than 0 days after", "equal to")
    """
    try:
        # Check for 'from' range (typically used for GT, GTE operators)
        if 'from' in range_value:
            from_info = range_value['from']
            operator = from_info.get('operator', '')
            value = from_info.get('value', '')
            unit = from_info.get('unit', '')
            
            if operator and value:
                # Handle different operators
                if operator.upper() == 'GT':
                    if value == '0' and unit.upper() in ['DAY', 'DAYS']:
                        return "more than 0 days after"
                    else:
                        return f"more than {value} {unit.lower()}{'s' if unit.lower() not in ['days', 'months', 'years'] and value != '1' else ''} after"
                elif operator.upper() == 'GTE' or operator.upper() == 'GTEQ':
                    return f"more than or equal to {value} {unit.lower()}{'s' if unit.lower() not in ['days', 'months', 'years'] and value != '1' else ''} after"
                elif operator.upper() == 'LT':
                    return f"less than {value} {unit.lower()}{'s' if unit.lower() not in ['days', 'months', 'years'] and value != '1' else ''} before"
                elif operator.upper() == 'LTE' or operator.upper() == 'LTEQ':
                    return f"less than or equal to {value} {unit.lower()}{'s' if unit.lower() not in ['days', 'months', 'years'] and value != '1' else ''} before"
                elif operator.upper() == 'EQ':
                    if value == '0' and unit.upper() in ['DAY', 'DAYS']:
                        return "equal to"
                    else:
                        return f"exactly {value} {unit.lower()}{'s' if unit.lower() not in ['days', 'months', 'years'] and value != '1' else ''} after"
        
        # Check for 'to' range (less common but possible)
        if 'to' in range_value:
            to_info = range_value['to']
            operator = to_info.get('operator', '')
            value = to_info.get('value', '')
            unit = to_info.get('unit', '')
            
            if operator and value:
                if operator.upper() == 'LT':
                    return f"less than {value} {unit.lower()}{'s' if unit.lower() not in ['days', 'months', 'years'] and value != '1' else ''} after"
                elif operator.upper() == 'LTE' or operator.upper() == 'LTEQ':
                    return f"less than or equal to {value} {unit.lower()}{'s' if unit.lower() not in ['days', 'months', 'years'] and value != '1' else ''} after"
        
        return None
    except Exception:
        return None


def generate_linked_criteria_explanation(linked_criterion, main_criterion):
    """
    Generate dynamic explanation for linked criteria based on content
    
    Args:
        linked_criterion: The linked criterion to explain
        main_criterion: The main criterion it's linked to
        
    Returns:
        str: Human-readable explanation of what the linked criteria does
    """
    main_table = main_criterion.table.lower()
    linked_table = linked_criterion.table.lower()
    linked_desc = linked_criterion.description.lower() if linked_criterion.description else ""
    
    # Medication-related scenarios
    if "medication" in main_table or "drug" in main_table:
        if "stop" in linked_desc or "discontinu" in linked_desc:
            return "Medication stopped/discontinued"
        elif "change" in linked_desc or "switch" in linked_desc:
            return "Medication changed/switched"
        else:
            return f"Related to medication: {linked_criterion.description}" if linked_criterion.description else "Related medication criteria"
    
    # Clinical event scenarios
    elif "event" in main_table or "clinical" in main_table:
        if "event" in linked_table or "clinical" in linked_table:
            if linked_criterion.description and linked_criterion.description.strip():
                return f"Additional criteria: {linked_criterion.description}"
            else:
                return "Additional clinical criteria"
        else:
            if linked_criterion.description and linked_criterion.description.strip():
                return f"Related condition: {linked_criterion.description}"
            else:
                return "Related clinical condition"
    
    # Patient scenarios
    elif "patient" in main_table:
        if linked_criterion.description and linked_criterion.description.strip():
            return f"Patient criteria: {linked_criterion.description}"
        else:
            return "Additional patient criteria"
    
    # Generic fallback
    else:
        if linked_criterion.description and linked_criterion.description.strip():
            return f"Related: {linked_criterion.description}"
        else:
            return "Additional linked criteria"


def filter_linked_value_sets_from_main(criterion):
    """
    Filter out value sets that are used in linked criteria from the main criterion display
    
    Special handling for baseCriteriaGroup structures: When a criterion has multiple value sets
    and linked criteria, it likely comes from baseCriteriaGroup parsing where the main criterion
    should show the unified pool of all value sets.
    
    Args:
        criterion: The main criterion to filter
        
    Returns:
        list: Filtered list of value sets that should be shown in the main display
    """
    if not criterion.value_sets:
        return []
    
    # Special case: If criterion has multiple value sets (2+) and linked criteria,
    # it's likely from baseCriteriaGroup parsing - show unified pool without filtering
    if len(criterion.value_sets) >= 2 and criterion.linked_criteria:
        return criterion.value_sets
    
    # Standard filtering for other cases
    main_value_sets = []
    linked_value_set_ids = set()
    
    # Collect IDs of value sets used in linked criteria (both in value_sets and column filters)
    if criterion.linked_criteria:
        for linked in criterion.linked_criteria:
            # Check value sets directly on linked criteria
            for linked_vs in linked.value_sets:
                if linked_vs.get('id'):
                    linked_value_set_ids.add(linked_vs['id'])
                if linked_vs.get('description'):
                    linked_value_set_ids.add(linked_vs['description'])
            
            # Check value sets within column filters
            for column_filter in linked.column_filters:
                for cf_vs in column_filter.get('value_sets', []):
                    if cf_vs.get('id'):
                        linked_value_set_ids.add(cf_vs['id'])
                    if cf_vs.get('description'):
                        linked_value_set_ids.add(cf_vs['description'])
    
    # Only return value sets that aren't used in linked criteria
    for vs in criterion.value_sets:
        is_linked_vs = (vs.get('id') in linked_value_set_ids or 
                       vs.get('description') in linked_value_set_ids)
        if not is_linked_vs:
            main_value_sets.append(vs)
    
    return main_value_sets


def filter_linked_column_filters_from_main(criterion):
    """
    Filter out column filters that are used in linked criteria from the main criterion display
    
    Args:
        criterion: The main criterion to filter
        
    Returns:
        list: Filtered list of column filters that should be shown in the main display
    """
    if not criterion.column_filters:
        return []
    
    # If no linked criteria, return all column filters
    if not criterion.linked_criteria:
        return criterion.column_filters
    
    main_column_filters = []
    linked_column_signatures = set()
    
    # Collect signatures of column filters used in linked criteria
    if criterion.linked_criteria:
        for linked in criterion.linked_criteria:
            for column_filter in linked.column_filters:
                # Create a signature for the column filter to identify duplicates
                column = column_filter.get('column', '')
                display_name = column_filter.get('display_name', '')
                in_not_in = column_filter.get('in_not_in', '')
                
                # Handle both single column strings and multi-column lists
                if isinstance(column, list):
                    column_key = '_'.join(sorted(column))
                else:
                    column_key = column
                
                # Create signature from key attributes
                signature = f"{column_key}:{display_name}:{in_not_in}"
                
                # Also include value set signatures if present
                if 'value_sets' in column_filter:
                    for vs in column_filter['value_sets']:
                        vs_id = vs.get('id', '')
                        vs_desc = vs.get('description', '')
                        signature += f":{vs_id}:{vs_desc}"
                
                linked_column_signatures.add(signature)
    
    # Only return column filters that aren't used in linked criteria
    for cf in criterion.column_filters:
        column = cf.get('column', '')
        display_name = cf.get('display_name', '')
        in_not_in = cf.get('in_not_in', '')
        
        # Handle both single column strings and multi-column lists
        if isinstance(column, list):
            column_key = '_'.join(sorted(column))
        else:
            column_key = column
        
        # Create signature from key attributes
        signature = f"{column_key}:{display_name}:{in_not_in}"
        
        # Also include value set signatures if present
        if 'value_sets' in cf:
            for vs in cf['value_sets']:
                vs_id = vs.get('id', '')
                vs_desc = vs.get('description', '')
                signature += f":{vs_id}:{vs_desc}"
        
        # Only include if not found in linked criteria
        if signature not in linked_column_signatures:
            main_column_filters.append(cf)
    
    return main_column_filters


def filter_top_level_criteria(criteria_group):
    """
    Filter out criteria that are already included as linked criteria in other criteria
    
    Args:
        criteria_group: The criteria group to filter
        
    Returns:
        list: Top-level criteria that should be displayed (excluding linked criteria as separate items)
    """
    if not criteria_group or not criteria_group.criteria:
        return []
    
    # Collect IDs of all linked criteria
    linked_criteria_ids = set()
    for criterion in criteria_group.criteria:
        if hasattr(criterion, 'linked_criteria') and criterion.linked_criteria:
            for linked_criterion in criterion.linked_criteria:
                if hasattr(linked_criterion, 'id') and linked_criterion.id:
                    linked_criteria_ids.add(linked_criterion.id)
    
    # Return only top-level criteria (not appearing as linked criteria in others)
    top_level_criteria = []
    for criterion in criteria_group.criteria:
        # If this criterion is not a linked criterion of another, include it
        if not hasattr(criterion, 'id') or criterion.id not in linked_criteria_ids:
            top_level_criteria.append(criterion)
    
    return top_level_criteria


def has_linked_criteria(criteria_group):
    """
    Check if a criteria group has any linked criteria
    
    Args:
        criteria_group: The criteria group to check
        
    Returns:
        bool: True if any criterion in the group has linked criteria
    """
    return any(criterion.linked_criteria for criterion in criteria_group.criteria)