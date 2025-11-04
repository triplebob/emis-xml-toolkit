"""
Report Export Handler for EMIS Reports
Handles export of all 4 report types: Search, List, Audit, and Aggregate reports
"""

import io
import pandas as pd
from datetime import datetime
from typing import Optional

from ..common.export_utils import sanitize_dataframe_for_excel
from ..core.search_manager import SearchManager


class ReportExportHandler:
    """Export handler specifically for EMIS reports (all 4 types)"""
    
    def __init__(self, analysis):
        self.analysis = analysis
        self.reports = analysis.reports if analysis else []
    
    def generate_report_export(self, report, include_parent_info=True):
        """Generate comprehensive export for any report type"""
        
        
        # Route to appropriate export method based on report type
        if report.report_type == 'search':
            return self._generate_search_report_export(report, include_parent_info)
        elif report.report_type == 'list':
            return self._generate_list_report_export(report, include_parent_info)
        elif report.report_type == 'audit':
            return self._generate_audit_report_export(report, include_parent_info)
        elif report.report_type == 'aggregate':
            return self._generate_aggregate_report_export(report, include_parent_info)
        else:
            # Default to basic search export for unknown types
            return self._generate_search_report_export(report, include_parent_info)
    
    def _generate_aggregate_report_export(self, aggregate_report, include_parent_info=True):
        """Generate comprehensive export for Aggregate Report"""
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # 1. Overview Sheet - Report Structure
            overview_data = [
                ['Report Type', 'Aggregate Report'],
                ['Report Name', aggregate_report.name],
                ['Description', aggregate_report.description or 'N/A'],
                ['Parent Search', self._get_parent_display_name(aggregate_report)],
                ['Search Date', aggregate_report.search_date],
                ['Logical Table', getattr(aggregate_report, 'logical_table', 'N/A')],
                ['Export Date', datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            ]
            
            overview_df = pd.DataFrame(overview_data, columns=['Property', 'Value'])
            overview_df_safe = sanitize_dataframe_for_excel(overview_df)
            overview_df_safe.to_excel(writer, sheet_name='Report_Overview', index=False)
            
            # 2. Statistical Configuration Sheet
            self._create_statistical_config_sheet(writer, aggregate_report)
            
            # 3. Aggregate Groups Sheet  
            self._create_aggregate_groups_sheet(writer, aggregate_report)
            
            # 4. Built-in Filters Sheets (if present)
            if hasattr(aggregate_report, 'aggregate_criteria') and aggregate_report.aggregate_criteria:
                self._create_builtin_filters_sheets(writer, aggregate_report)
            
            # 5. Clinical Codes Sheets (from built-in filters)
            if aggregate_report.criteria_groups:
                self._create_clinical_codes_sheets(writer, aggregate_report)
        
        output.seek(0)
        
        # Generate filename
        clean_name = SearchManager.clean_search_name(aggregate_report.name)
        safe_name = "".join(c for c in clean_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"AggregateReport_{safe_name}_{timestamp}.xlsx"
        
        return filename, output.getvalue()
    
    def _create_statistical_config_sheet(self, writer, report):
        """Create statistical configuration sheet"""
        if not hasattr(report, 'statistical_groups') or not report.statistical_groups:
            return
        
        stats_data = []
        for stat in report.statistical_groups:
            stat_info = {
                'Configuration': stat.get('type', '').title(),
                'Group Name': stat.get('group_name', f"Group {stat.get('group_id', 'Unknown')}"),
                'Group ID': stat.get('group_id', ''),
                'Source': stat.get('source', 'N/A'),
                'Calculation Type': stat.get('calculation_type', 'N/A'),
                'Description': f"This group defines the {stat.get('type', 'unknown')} configuration for the aggregate report"
            }
            stats_data.append(stat_info)
        
        stats_df = pd.DataFrame(stats_data)
        stats_df_safe = sanitize_dataframe_for_excel(stats_df)
        stats_df_safe.to_excel(writer, sheet_name='Statistical_Setup', index=False)
    
    def _create_aggregate_groups_sheet(self, writer, report):
        """Create aggregate groups definition sheet"""
        if not hasattr(report, 'aggregate_groups') or not report.aggregate_groups:
            return
        
        groups_data = []
        for i, group in enumerate(report.aggregate_groups, 1):
            group_info = {
                'Group Number': i,
                'Group ID': group.get('id', ''),
                'Display Name': group.get('display_name', 'Unnamed Group'),
                'Grouping Columns': ', '.join(group.get('grouping_columns', [])),
                'Sub Totals': 'Yes' if group.get('sub_totals', False) else 'No',
                'Repeat Header': 'Yes' if group.get('repeat_header', False) else 'No',
                'Purpose': f"Groups data by: {', '.join(group.get('grouping_columns', []))}"
            }
            groups_data.append(group_info)
        
        groups_df = pd.DataFrame(groups_data)
        groups_df_safe = sanitize_dataframe_for_excel(groups_df)
        groups_df_safe.to_excel(writer, sheet_name='Grouping_Definitions', index=False)
    
    def _create_builtin_filters_sheets(self, writer, report):
        """Create built-in filters overview and detail sheets"""
        if not hasattr(report, 'aggregate_criteria') or not report.aggregate_criteria:
            return
        
        criteria_data = report.aggregate_criteria
        
        # Create structured filter overview like List Reports
        filter_data = []
        
        for i, criteria_group in enumerate(criteria_data.get('criteria_groups', []), 1):
            # Add filter group header
            filter_data.append(['FILTER GROUP STRUCTURE', '', ''])
            filter_data.append([f'Group {i}', criteria_group.get('display_name', 'Unnamed Group'), criteria_group.get('table', 'N/A')])
            
            for j, criterion in enumerate(criteria_group.get('criteria', []), 1):
                filter_data.append([f'Filter {j}', criterion.get('display_name', 'Unnamed Filter'), criterion.get('table', 'N/A')])
            
            # Add filtering rules section
            filter_data.append(['', '', ''])
            filter_data.append(['FILTERING RULES', '', ''])
            
            for j, criterion in enumerate(criteria_group.get('criteria', []), 1):
                # Clinical codes filter
                value_sets = criterion.get('value_sets', [])
                if value_sets and any(vs.get('values') for vs in value_sets):
                    total_codes = sum(len(vs.get('values', [])) for vs in value_sets)
                    if total_codes > 0:
                        filter_data.append(['Rule', f'Include {total_codes} specified clinical codes', ''])
                    else:
                        filter_data.append(['Rule', 'Include specified clinical codes', ''])
                
                # Column filters (date restrictions, etc.)
                column_filters = criterion.get('column_filters', [])
                for filter_item in column_filters:
                    filter_column = filter_item.get('column', '')
                    if isinstance(filter_column, list):
                        filter_column = ' + '.join(filter_column) if filter_column else ''
                    filter_column = filter_column.upper()
                    if 'DATE' in filter_column:
                        range_info = filter_item.get('range', {})
                        if range_info:
                            range_from = range_info.get('from', {}) or range_info.get('range_from', {})
                            if range_from:
                                value = range_from.get('value', '-1')
                                unit = range_from.get('unit', 'YEAR')
                                display_value = value.replace('-', '') if value.startswith('-') else value
                                filter_data.append(['Rule', f'Date is after {display_value} {unit.lower()} before search date', ''])
                            else:
                                filter_data.append(['Rule', 'Date filtering applied', ''])
                
                # Restrictions
                restrictions = criterion.get('restrictions', [])
                for restriction in restrictions:
                    # Handle both SearchRestriction objects and dictionary format
                    if hasattr(restriction, 'record_count'):
                        # SearchRestriction object
                        count = restriction.record_count
                        column = getattr(restriction, 'ordering_column', None)
                    elif isinstance(restriction, dict) and restriction.get('record_count'):
                        # Dictionary format
                        count = restriction.get('record_count')
                        column = restriction.get('ordering_column')
                    else:
                        continue
                        
                    if count:
                        if column and column != 'None':
                            filter_data.append(['Rule', f'Ordering by: {column}, select latest {count}', ''])
                        else:
                            filter_data.append(['Rule', f'Ordering by: Date, select latest {count}', ''])
            
            # Add spacer between groups
            if i < len(criteria_data.get('criteria_groups', [])):
                filter_data.append(['', '', ''])
        
        if filter_data:
            filters_df = pd.DataFrame(filter_data, columns=['Type', 'Description', 'Technical'])
            filters_df_safe = sanitize_dataframe_for_excel(filters_df)
            filters_df_safe.to_excel(writer, sheet_name='Builtin_Filters_Overview', index=False)
    
    def _create_clinical_codes_sheets(self, writer, report):
        """Create clinical codes sheets from criteria groups"""
        if not report.criteria_groups:
            return
        
        # Collect all clinical codes from all criteria groups
        all_codes = []
        
        for group_idx, group in enumerate(report.criteria_groups, 1):
            for criterion_idx, criterion in enumerate(group.criteria, 1):
                # Extract clinical codes from value sets
                for value_set in criterion.value_sets:
                    # Transform code system name to user-friendly format
                    code_system = value_set.get('code_system', 'Unknown')
                    system_display = self._transform_code_system_name(code_system)
                    
                    for value in value_set.get('values', []):
                        # Get EMIS GUID and lookup SNOMED code
                        emis_guid = value.get('value', 'N/A')
                        snomed_code = self._lookup_snomed_code(emis_guid)
                        
                        # Check for refset status
                        is_refset = value.get('is_refset', False)
                        include_children = value.get('include_children', False)
                        
                        code_info = {
                            'Filter Group': group_idx,
                            'Filter Number': criterion_idx,
                            'Filter Name': criterion.display_name,
                            'Table': criterion.table,
                            'Code System': system_display,
                            'EMIS GUID': emis_guid,
                            'SNOMED Code': snomed_code,
                            'Display Name': value.get('display_name', 'N/A'),
                            'Include Children': 'Yes' if include_children else 'No',
                            'Is Refset': 'True' if is_refset else 'False'
                        }
                        all_codes.append(code_info)
        
        if all_codes:
            codes_df = pd.DataFrame(all_codes)
            codes_df_safe = sanitize_dataframe_for_excel(codes_df)
            codes_df_safe.to_excel(writer, sheet_name='Clinical_Codes', index=False)
    
    def _export_criteria_clinical_codes(self, writer, criteria_groups, sheet_name):
        """Export clinical codes from criteria groups to specified sheet"""
        if not criteria_groups:
            return
        
        # Collect all clinical codes from all criteria groups
        all_codes = []
        
        for group_idx, group in enumerate(criteria_groups, 1):
            for criterion_idx, criterion in enumerate(group.criteria, 1):
                # Extract clinical codes from value sets
                for value_set in criterion.value_sets:
                    # Transform code system name to user-friendly format
                    code_system = value_set.get('code_system', 'Unknown')
                    system_display = self._transform_code_system_name(code_system)
                    
                    for value in value_set.get('values', []):
                        # Skip internal system codes that aren't clinical codes
                        if (value_set.get('code_system') == 'EMISINTERNAL' and 
                            value.get('value') in ['Currrent', 'Active', 'Current']):
                            continue
                        
                        # Get EMIS GUID and lookup SNOMED code
                        emis_guid = value.get('value', 'N/A')
                        snomed_code = self._lookup_snomed_code(emis_guid)
                        
                        # Check for refset status
                        is_refset = value.get('is_refset', False)
                        include_children = value.get('include_children', False)
                        
                        code_info = {
                            'Group': group_idx,
                            'Criterion': criterion_idx,
                            'Criterion Name': criterion.display_name,
                            'Table': criterion.table,
                            'Code System': system_display,
                            'EMIS GUID': emis_guid,
                            'SNOMED Code': snomed_code,
                            'Display Name': value.get('display_name', 'N/A'),
                            'Include Children': 'Yes' if include_children else 'No',
                            'Is Refset': 'True' if is_refset else 'False'
                        }
                        all_codes.append(code_info)
        
        if all_codes:
            codes_df = pd.DataFrame(all_codes)
            codes_df_safe = sanitize_dataframe_for_excel(codes_df)
            codes_df_safe.to_excel(writer, sheet_name=sheet_name, index=False)
    
    def _export_criteria_filters(self, writer, criteria_groups, sheet_name):
        """Export filters from criteria groups to specified sheet"""
        if not criteria_groups:
            return
        
        # Collect all filters from all criteria groups
        all_filters = []
        
        for group_idx, group in enumerate(criteria_groups, 1):
            for criterion_idx, criterion in enumerate(group.criteria, 1):
                # Extract column filters
                for col_filter in criterion.column_filters:
                    filter_info = {
                        'Group': group_idx,
                        'Criterion': criterion_idx,
                        'Criterion Name': criterion.display_name,
                        'Table': criterion.table,
                        'Column': col_filter.get('column', 'N/A'),
                        'Operator': col_filter.get('operator', 'N/A'),
                        'Value': col_filter.get('value', 'N/A'),
                        'Context': col_filter.get('context', 'N/A')
                    }
                    all_filters.append(filter_info)
        
        if all_filters:
            filters_df = pd.DataFrame(all_filters)
            filters_df_safe = sanitize_dataframe_for_excel(filters_df)
            filters_df_safe.to_excel(writer, sheet_name=sheet_name, index=False)
    
    def _generate_list_report_export(self, list_report, include_parent_info=True):
        """Generate comprehensive List Report export with detailed column analysis and clinical codes"""
        
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # 1. Overview Sheet
            overview_data = [
                ['Report Type', 'List Report'],
                ['Report Name', list_report.name],
                ['Description', list_report.description or 'N/A'],
                ['Parent Search', self._get_parent_display_name(list_report)],
                ['Search Date', list_report.search_date],
                ['Total Column Groups', len(list_report.column_groups) if list_report.column_groups else 0]
            ]
            
            if hasattr(list_report, 'enterprise_reporting_level') and list_report.enterprise_reporting_level:
                overview_data.append(['Enterprise Reporting Level', list_report.enterprise_reporting_level])
            
            overview_df = pd.DataFrame(overview_data, columns=['Property', 'Value'])
            overview_df_safe = sanitize_dataframe_for_excel(overview_df)
            overview_df_safe.to_excel(writer, sheet_name='Overview', index=False)
            
            # 2. Column Groups Summary
            if list_report.column_groups:
                groups_data = []
                for i, group in enumerate(list_report.column_groups, 1):
                    groups_data.append({
                        'Group Number': i,
                        'Display Name': group.get('display_name', 'N/A'),
                        'Logical Table': group.get('logical_table', 'N/A'),
                        'Column Count': len(group.get('columns', [])),
                        'Has Filtering': 'Yes' if group.get('has_criteria', False) else 'No'
                    })
                
                groups_df = pd.DataFrame(groups_data)
                groups_df_safe = sanitize_dataframe_for_excel(groups_df)
                groups_df_safe.to_excel(writer, sheet_name='Column_Groups', index=False)
                
                # 3. Individual Column Tabs with detailed rules
                for group_idx, group in enumerate(list_report.column_groups, 1):
                    group_name = group.get('display_name', f'Group_{group_idx}')
                    safe_name = self._make_safe_sheet_name(f"Col_{group_idx}_{group_name}")
                    
                    # Column structure and rules
                    column_data = []
                    for col in group.get('columns', []):
                        column_data.append({
                            'Display Name': col.get('display_name', 'N/A'),
                            'Column Name': col.get('column', 'N/A'),
                            'Column Type': col.get('column_type', 'standard')
                        })
                    
                    # Add filtering rules if present
                    filter_rules = []
                    if group.get('has_criteria', False) and group.get('criteria_details'):
                        criteria_details = group['criteria_details']
                        for criterion in criteria_details.get('criteria', []):
                            # Check for value sets to count clinical codes
                            value_sets = criterion.get('value_sets', [])
                            total_codes = sum(len(vs.get('values', [])) for vs in value_sets) if value_sets else 0
                            
                            # Extract actual filter information
                            column_filters = criterion.get('column_filters', [])
                            for filter_item in column_filters:
                                filter_column = filter_item.get('column', '')
                                if isinstance(filter_column, list):
                                    filter_column = ' + '.join(filter_column) if filter_column else ''
                                filter_column = filter_column.upper()
                                if 'DATE' in filter_column:
                                    range_info = filter_item.get('range', {})
                                    if range_info:
                                        range_from = range_info.get('from', {}) or range_info.get('range_from', {})
                                        if range_from:
                                            value = range_from.get('value', '-1')
                                            unit = range_from.get('unit', 'YEAR')
                                            display_value = value.replace('-', '') if value.startswith('-') else value
                                            filter_rules.append(f"Date is after {display_value} {unit.lower()} before search date")
                                        else:
                                            filter_rules.append("Date filtering applied")
                                else:
                                    # Use count if available
                                    if total_codes > 0:
                                        filter_rules.append(f"Include {total_codes} specified clinical codes")
                                    else:
                                        filter_rules.append("Include specified clinical codes")
                            
                            # Add restriction information
                            restrictions = criterion.get('restrictions', [])
                            for restriction in restrictions:
                                # Handle both SearchRestriction objects and dictionary format
                                if hasattr(restriction, 'record_count'):
                                    # SearchRestriction object
                                    count = restriction.record_count
                                    column = getattr(restriction, 'ordering_column', None)
                                elif isinstance(restriction, dict) and restriction.get('record_count'):
                                    # Dictionary format
                                    count = restriction.get('record_count')
                                    column = restriction.get('ordering_column')
                                else:
                                    continue
                                    
                                if count:
                                    if column and column != 'None':
                                        filter_rules.append(f"Ordering by: {column}, select latest {count}")
                                    else:
                                        filter_rules.append(f"Ordering by: Date, select latest {count}")
                    
                    # Combine column structure and rules
                    sheet_data = []
                    sheet_data.append(['COLUMN STRUCTURE', '', ''])
                    for i, col in enumerate(column_data):
                        sheet_data.append([f'Column {i+1}', col['Display Name'], col['Column Name']])
                    
                    if filter_rules:
                        sheet_data.append(['', '', ''])
                        sheet_data.append(['FILTERING RULES', '', ''])
                        for rule in filter_rules:
                            sheet_data.append(['Rule', rule, ''])
                    
                    if sheet_data:
                        column_df = pd.DataFrame(sheet_data, columns=['Type', 'Description', 'Technical'])
                        column_df_safe = sanitize_dataframe_for_excel(column_df)
                        column_df_safe.to_excel(writer, sheet_name=safe_name, index=False)
                
                # 4. Clinical Codes Tabs (per column group with criteria)
                for group_idx, group in enumerate(list_report.column_groups, 1):
                    if not group.get('has_criteria', False):
                        continue
                        
                    group_name = group.get('display_name', f'Group_{group_idx}')
                    safe_name = self._make_safe_sheet_name(f"Codes_{group_idx}_{group_name}")
                    
                    codes_data = []
                    if group.get('criteria_details'):
                        criteria_details = group['criteria_details']
                        for criterion in criteria_details.get('criteria', []):
                            value_sets = criterion.get('value_sets', [])
                            for vs in value_sets:
                                code_system = vs.get('code_system', 'Unknown')
                                system_display = self._transform_code_system_name(code_system)
                                
                                for code in vs.get('values', []):
                                    emis_guid = code.get('value', 'N/A')
                                    snomed_code = self._lookup_snomed_code(emis_guid)
                                    
                                    # Check for refset status
                                    is_refset = code.get('is_refset', False)
                                    include_children = code.get('include_children', False)
                                    
                                    codes_data.append({
                                        'Code System': system_display,
                                        'EMIS GUID': emis_guid,
                                        'SNOMED Code': snomed_code,
                                        'Display Name': code.get('display_name', 'N/A'),
                                        'Include Children': 'Yes' if include_children else 'No',
                                        'Is Refset': 'True' if is_refset else 'False'
                                    })
                    
                    if codes_data:
                        codes_df = pd.DataFrame(codes_data)
                        codes_df_safe = sanitize_dataframe_for_excel(codes_df)
                        codes_df_safe.to_excel(writer, sheet_name=safe_name, index=False)
        
        # Generate filename and return
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = SearchManager.clean_search_name(list_report.name)
        filename = f"ListReport_{safe_name}_{timestamp}.xlsx"
        
        output.seek(0)
        return filename, output.getvalue()
    
    def _make_safe_sheet_name(self, name: str) -> str:
        """Create Excel-safe sheet name"""
        # Remove invalid characters and limit length
        safe_chars = "".join(c for c in name if c.isalnum() or c in (' ', '_', '-'))
        return safe_chars.replace(' ', '_')[:31]  # Excel sheet name limit is 31 chars
    
    def _transform_code_system_name(self, code_system: str) -> str:
        """Transform internal code system names to user-friendly labels"""
        if 'SNOMED_CONCEPT' in code_system:
            return "SNOMED CT"
        elif 'SCT_DRGGRP' in code_system:
            return "Drug Group Classification"
        elif 'EMISINTERNAL' in code_system:
            return "EMIS Internal Classifications"
        else:
            return code_system
    
    def _get_parent_display_name(self, report):
        """Get meaningful parent display name using same logic as JSON export"""
        # Try to resolve parent search name from session state (same as JSON export)
        try:
            import streamlit as st
            analysis = st.session_state.get('search_analysis')
            
            if analysis and hasattr(analysis, 'reports'):
                # Try direct dependencies first
                if hasattr(report, 'direct_dependencies') and report.direct_dependencies:
                    parent_guid = report.direct_dependencies[0]
                    for parent_report in analysis.reports:
                        if parent_report.id == parent_guid:
                            return f"Parent Search: {parent_report.name}"
                
                # Try parent_guid as fallback
                elif hasattr(report, 'parent_guid') and report.parent_guid:
                    for parent_report in analysis.reports:
                        if parent_report.id == report.parent_guid:
                            return f"Parent Search: {parent_report.name}"
        except Exception:
            pass
        
        # Fallback to meaningful parent type descriptions
        if report.parent_type == 'ACTIVE':
            return "Population: All currently registered regular patients"
        elif report.parent_type == 'ALL':
            return "Population: All patients (including left and deceased)"
        elif report.parent_type == 'POP':
            return "Population: Population-based (filtered)"
        elif hasattr(report, 'parent_guid') and report.parent_guid:
            return f"Parent Search: Custom search ({report.parent_guid[:8]}...)"
        elif report.parent_type:
            return f"Parent Type: {report.parent_type}"
        else:
            return "No parent specified"
    
    def _format_restriction_simple(self, restriction):
        """Format restriction details in a simple, user-friendly way (from search_export.py)"""
        if not restriction:
            return "No limit"
        
        # Handle SearchRestriction objects
        if hasattr(restriction, 'type'):
            restriction_type = restriction.type
            if restriction_type == "latest_records":
                if hasattr(restriction, 'record_count') and hasattr(restriction, 'direction'):
                    count = restriction.record_count
                    direction = restriction.direction
                    
                    if direction == "DESC":
                        return f"Latest {count}" if count != 1 else "Latest 1"
                    elif direction == "ASC":
                        return f"Earliest {count}" if count != 1 else "Earliest 1"
                    else:
                        return f"{count} records"
                else:
                    return "Record limit applied"
            elif restriction_type == "current_status":
                return "Current records only"
            elif restriction_type == "medication_current":
                return "Current medications only"
            elif hasattr(restriction, 'description') and restriction.description:
                return restriction.description
        
        # Handle dictionary format
        if isinstance(restriction, dict):
            if 'record_count' in restriction:
                count = restriction['record_count']
                direction = restriction.get('direction', 'DESC')
                order_text = "Latest" if direction == "DESC" else "Earliest"
                return f"{order_text} {count}"
        
        return "Record limit applied"
    
    def _format_filter_summary(self, col_filter):
        """Format column filter in EMIS clinical style (from search_export.py)"""
        if not col_filter:
            return "No filter"
        
        column = col_filter.get('column', 'Unknown')
        
        # Handle case where column might be a list
        if isinstance(column, list):
            if len(column) > 1:
                # Special case for complex filters like AUTHOR + CURRENTLY_CONTRACTED
                if 'AUTHOR' in column and 'CURRENTLY_CONTRACTED' in column:
                    return "User Details Currently Contracted is Active"
                else:
                    column = ' + '.join(column)  # Join multiple columns
            else:
                column = column[0] if column else 'Unknown'
        column = str(column)
        
        # EMIS-style clinical filter descriptions
        if column.upper() in ['READCODE', 'SNOMEDCODE']:
            # Count value sets to show how many codes
            value_count = 0
            if 'value_sets' in col_filter:
                value_sets = col_filter.get('value_sets', [])
                for vs in value_sets:
                    if 'values' in vs:
                        value_count += len(vs['values'])
            
            in_not_in = col_filter.get('in_not_in', 'IN')
            action = "Include" if in_not_in.upper() == "IN" else "Exclude"
            
            if value_count > 0:
                return f"{action} {value_count} specified clinical codes"
            else:
                return f"{action} specified clinical codes"
                
        elif column.upper() == 'CONSULTATION_HEADING':
            # Check for specific consultation types
            in_not_in = col_filter.get('in_not_in', 'IN')
            heading_types = []
            
            # Extract values from value_sets
            if 'value_sets' in col_filter:
                value_sets = col_filter.get('value_sets', [])
                for vs in value_sets:
                    if 'values' in vs:
                        for v in vs['values']:
                            if isinstance(v, dict):
                                heading_types.append(v.get('displayName', v.get('value', str(v))))
                            else:
                                heading_types.append(str(v))
            
            action = "Include" if in_not_in.upper() == "IN" else "Exclude"
            
            if heading_types:
                if len(heading_types) == 1:
                    return f"{action} consultations where the consultation heading is: {heading_types[0]}"
                else:
                    return f"{action} consultations with heading types: {', '.join(heading_types)}"
            else:
                return f"{action} consultations with specified heading types"
                
        elif column.upper() == 'DATE':
            # Check for range information
            if 'range' in col_filter and col_filter['range']:
                range_desc = self._format_range_emis_style(col_filter['range'])
                return range_desc if range_desc else "Date is after/before search date"
            return "Date filter applied"
        elif column.upper() == 'NUMERIC_VALUE':
            # Numeric value ranges
            if 'range' in col_filter and col_filter['range']:
                range_desc = self._format_range_emis_style(col_filter['range'], is_numeric=True)
                return range_desc if range_desc else "Numeric value range filter"
            return "Numeric value range filter"
        else:
            return f"{column} filter applied"
    
    def _format_range_emis_style(self, range_data, is_numeric=False):
        """Format range information in EMIS clinical style with full temporal pattern support"""
        if not range_data:
            return None
        
        # Handle NUMERIC_VALUE filters with direct operator/value structure
        if is_numeric:
            # Check for direct operator/value structure (alternative format)
            if 'operator' in range_data and 'value' in range_data:
                operator = range_data.get('operator', 'GTEQ')
                value = range_data.get('value', '')
                if value:
                    op_text = "greater than" if operator == "GT" else "greater than or equal to" if operator == "GTEQ" else "less than" if operator == "LT" else "less than or equal to" if operator == "LTEQ" else "equal to"
                    return f"Value {op_text} {value}"
            
            # Check for alternative range structures (rangeTo, rangeFrom, etc.)
            if 'rangeTo' in range_data or 'range_to' in range_data:
                to_data = range_data.get('rangeTo') or range_data.get('range_to')
                if to_data and isinstance(to_data, dict):
                    operator = to_data.get('operator', 'LTEQ')
                    value = to_data.get('value', '')
                    if value:
                        op_text = "less than" if operator == "LT" else "less than or equal to" if operator == "LTEQ" else "equal to"
                        return f"Value {op_text} {value}"
            
            if 'rangeFrom' in range_data or 'range_from' in range_data:
                from_data = range_data.get('rangeFrom') or range_data.get('range_from')
                if from_data and isinstance(from_data, dict):
                    operator = from_data.get('operator', 'GTEQ')
                    value = from_data.get('value', '')
                    if value:
                        op_text = "greater than" if operator == "GT" else "greater than or equal to" if operator == "GTEQ" else "equal to"
                        return f"Value {op_text} {value}"
            
            # Check for any nested value that might contain operator/value directly
            for key in range_data:
                if isinstance(range_data[key], dict) and 'operator' in range_data[key] and 'value' in range_data[key]:
                    nested = range_data[key]
                    operator = nested.get('operator', 'GTEQ')
                    value = nested.get('value', '')
                    if value:
                        op_text = "greater than" if operator == "GT" else "greater than or equal to" if operator == "GTEQ" else "less than" if operator == "LT" else "less than or equal to" if operator == "LTEQ" else "equal to"
                        return f"Value {op_text} {value}"
        
        date_filters = []
        
        # Helper function for temporal pattern formatting with EMIS terminology
        def format_relative_date(value, unit, relation=None, operator=None):
            unit = unit.lower()
            
            # Convert operator to EMIS format
            if operator == 'GTEQ':
                op_text = 'after or on'
            elif operator == 'LTEQ':
                op_text = 'before or on'
            elif operator == 'GT':
                op_text = 'after'
            elif operator == 'LT':
                op_text = 'before'
            else:
                op_text = 'on'
            
            # Handle numeric offset patterns first (to catch -6, 7, etc.)
            if value and value.lstrip('-').isdigit():
                if value.startswith('-'):
                    # Negative relative date (before search date)
                    abs_value = value[1:]  # Remove the minus sign
                    unit_text = f"{unit.lower()}s" if abs_value != '1' else unit.lower()
                    return f"and the Date is {op_text} {abs_value} {unit_text} before the search date"
                else:
                    # Positive relative date (after search date)
                    unit_text = f"{unit.lower()}s" if value != '1' else unit.lower()
                    return f"and the Date is {op_text} {value} {unit_text} after the search date"
            
            # Handle temporal variable patterns (Last/This/Next + time unit)  
            elif unit.lower() in ['day', 'week', 'month', 'quarter', 'year', 'fiscalyear']:
                if value.lower() == 'last':
                    if unit.lower() == 'fiscalyear':
                        return "and the Date is last fiscal year"
                    elif unit.lower() == 'quarter':
                        return "and the Date is last yearly quarter"
                    else:
                        return f"and the Date is last {unit.lower()}"
                elif value.lower() == 'this':
                    if unit.lower() == 'fiscalyear':
                        return "and the Date is this fiscal year"
                    elif unit.lower() == 'quarter':
                        return "and the Date is this yearly quarter"
                    else:
                        return f"and the Date is this {unit.lower()}"
                elif value.lower() == 'next':
                    if unit.lower() == 'fiscalyear':
                        return "and the Date is next fiscal year"
                    elif unit.lower() == 'quarter':
                        return "and the Date is next yearly quarter"
                    else:
                        return f"and the Date is next {unit.lower()}"
                else:
                    return f"and the Date is {value} {unit.lower()}"
            
            # Handle absolute dates (like 01/04/2023)
            elif relation == 'ABSOLUTE' or unit == 'date':
                return f"absolute date {value}"
            
            # Handle age values (for demographics)
            elif unit in ['year', 'years'] and relation == 'RELATIVE':
                unit_str = 'years old' if value != '1' else 'year old'
                return f"{value} {unit_str}"
            
            # Fallback for unhandled patterns
            else:
                return f"Date filter: {value} {unit}"
        
        # Process range from
        if range_data.get('from'):
            from_data = range_data['from']
            value = from_data.get('value', '')
            unit = from_data.get('unit', '')
            relation = from_data.get('relation', '')
            operator = from_data.get('operator', 'GTEQ')
            
            # Handle numeric values without units (common for NUMERIC_VALUE filters)
            if value and (unit or is_numeric):
                if is_numeric and not unit:
                    # Pure numeric value without unit
                    op_text = "greater than" if operator == "GT" else "greater than or equal to" if operator == "GTEQ" else "equal to"
                    return f"Value {op_text} {value}"
                else:
                    # Date/time value with unit
                    date_str = format_relative_date(value, unit, relation, operator)
                    op_text = "on or after" if operator == 'GTEQ' else "after" if operator == 'GT' else "on"
                    # Handle zero case for dates
                    if value == '0' and relation == 'RELATIVE':
                        op_text_zero = "on or after" if operator == 'GTEQ' else "after" if operator == 'GT' else "on"
                        date_filters.append(f"Date is {op_text_zero} the search date")
                    else:
                        date_filters.append(f"Date is {op_text} {date_str}")
        
        # Process range to
        if range_data.get('to'):
            to_data = range_data['to']
            value = to_data.get('value', '')
            unit = to_data.get('unit', '')
            relation = to_data.get('relation', '')
            operator = to_data.get('operator', 'LTEQ')
            
            # Handle numeric values without units (common for NUMERIC_VALUE filters)
            if value and (unit or is_numeric):
                if is_numeric and not unit:
                    # Pure numeric value without unit
                    op_text = "less than" if operator == "LT" else "less than or equal to" if operator == "LTEQ" else "equal to"
                    return f"Value {op_text} {value}"
                else:
                    # Date/time value with unit
                    date_str = format_relative_date(value, unit, relation, operator)
                    op_text = "on or before" if operator == 'LTEQ' else "before" if operator == 'LT' else "on"
                    # Handle zero case for dates
                    if value == '0' and relation == 'RELATIVE':
                        op_text_zero = "on or before" if operator == 'LTEQ' else "before" if operator == 'LT' else "on"
                        date_filters.append(f"Date is {op_text_zero} the search date")
                    else:
                        date_filters.append(f"Date is {op_text} {date_str}")
        
        # Return results or appropriate fallback
        if date_filters:
            return " and ".join(date_filters)
        elif is_numeric:
            return "Numeric value range filter"
        else:
            return "Date/value range filter applied"
    
    def _get_main_criterion_filters(self, criterion):
        """Get filters that belong to main criterion (excluding linked ones)"""
        if not criterion.column_filters:
            return []
        
        # Get filters that belong to linked criteria
        linked_filters = []
        for linked_crit in criterion.linked_criteria:
            if hasattr(linked_crit, 'column_filters'):
                linked_filters.extend(linked_crit.column_filters)
        
        # Filter out linked criterion filters from main criterion
        main_filters = []
        for col_filter in criterion.column_filters:
            # Simple comparison - if filter doesn't match any linked filter exactly, include it
            is_linked_filter = False
            for linked_filter in linked_filters:
                if (col_filter.get('column') == linked_filter.get('column') and 
                    col_filter.get('id') == linked_filter.get('id')):
                    is_linked_filter = True
                    break
            
            if not is_linked_filter:
                main_filters.append(col_filter)
        
        return main_filters
    
    def _is_linked_criterion(self, criterion, all_criteria):
        """Check if this criterion is a linked criterion (appears in another criterion's linked_criteria)"""
        if not hasattr(criterion, 'id') or not criterion.id:
            return False
            
        # Check if this criterion's ID appears in any other criterion's linked_criteria
        for other_criterion in all_criteria:
            if hasattr(other_criterion, 'linked_criteria'):
                for linked_crit in other_criterion.linked_criteria:
                    if hasattr(linked_crit, 'id') and linked_crit.id == criterion.id:
                        return True
        return False

    def _lookup_snomed_code(self, emis_guid: str) -> str:
        """Lookup SNOMED code for given EMIS GUID using session state lookup table"""
        import streamlit as st
        
        # Get lookup table from session state
        lookup_df = st.session_state.get('lookup_df')
        emis_guid_col = st.session_state.get('emis_guid_col')
        snomed_code_col = st.session_state.get('snomed_code_col')
        
        if lookup_df is None or emis_guid_col is None or snomed_code_col is None:
            return 'Lookup table not available'
        
        if not emis_guid or emis_guid == 'N/A':
            return 'N/A'
        
        # Lookup the SNOMED code
        try:
            matching_rows = lookup_df[lookup_df[emis_guid_col].astype(str).str.strip() == str(emis_guid).strip()]
            if not matching_rows.empty:
                snomed_code = str(matching_rows.iloc[0][snomed_code_col]).strip()
                return snomed_code if snomed_code and snomed_code != 'nan' else 'Not found'
            else:
                return 'Not found'
        except Exception:
            return 'Lookup error'
    
    def _get_healthcare_context(self, column_type: str) -> str:
        """Get healthcare context description for column types"""
        context_map = {
            'age_at_event': 'Patient age calculation for healthcare pathways',
            'organisation': 'Healthcare organization/practice information',
            'practitioner': 'General practitioner/clinician details',
            'medication_date': 'Medication prescribing and dispensing dates',
            'associated_text': 'Clinical notes and associated documentation',
            'quantity': 'Medication quantity and dosing information',
            'standard': 'Standard clinical data column'
        }
        return context_map.get(column_type, 'Standard clinical data column')
    
    def _generate_audit_report_export(self, audit_report, include_parent_info=True):
        """Generate comprehensive export for Audit Report"""
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Collect overview data first
            overview_data = [
                ['Report Type', 'Audit Report'],
                ['Report Name', audit_report.name],
                ['Description', audit_report.description or 'N/A'],
                ['Creation Time', audit_report.creation_time or 'N/A'],
                ['Author', audit_report.author or 'N/A'],
                ['Population Type', audit_report.population_type or ''],
                ['Search Date', audit_report.search_date],
                ['Export Generated', datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                ['Export Tool', 'EMIS XML Toolkit']
            ]
            
            # Add parent information
            if include_parent_info:
                parent_display = self._get_parent_display_name(audit_report)
                overview_data.append(['Parent Information', parent_display])
            
            # Add aggregation configuration
            if hasattr(audit_report, 'custom_aggregate') and audit_report.custom_aggregate:
                agg = audit_report.custom_aggregate
                overview_data.extend([
                    ['Logical Table', agg.get('logical_table', 'N/A')],
                    ['Result Source', agg.get('result', {}).get('source', 'N/A')],
                    ['Calculation Type', agg.get('result', {}).get('calculation_type', 'N/A')]
                ])
                
                # Add organizational grouping
                groups = agg.get('groups', [])
                if groups:
                    group_columns = []
                    for group in groups:
                        grouping_cols = group.get('grouping_column', [])
                        if isinstance(grouping_cols, str):
                            grouping_cols = [grouping_cols]
                        group_columns.extend(grouping_cols)
                    overview_data.append(['Organizational Grouping', ', '.join(group_columns)])
            
            # Member searches will be added after we collect the names
            member_count = len(audit_report.population_references) if hasattr(audit_report, 'population_references') else 0
            
            # Add criteria count
            criteria_count = len(audit_report.criteria_groups) if hasattr(audit_report, 'criteria_groups') and audit_report.criteria_groups else 0
            overview_data.append(['Additional Criteria Groups', criteria_count])
            
            # 2. Member Searches Sheet (enhanced with full search details)
            member_search_names = []
            if hasattr(audit_report, 'population_references') and audit_report.population_references:
                member_data = []
                for i, pop_guid in enumerate(audit_report.population_references, 1):
                    # Find the search by GUID
                    search_report = next((r for r in self.reports if r.id == pop_guid), None)
                    if search_report:
                        member_search_names.append(search_report.name)
                        member_data.append({
                            'Index': i,
                            'Search Name': search_report.name,
                            'Description': search_report.description or 'N/A',
                            'Creation Time': search_report.creation_time or 'N/A',
                            'Author': search_report.author or 'N/A',
                            'Parent Type': search_report.parent_type or 'N/A',
                            'Population Type': search_report.population_type or 'N/A',
                            'Criteria Groups': len(search_report.criteria_groups) if hasattr(search_report, 'criteria_groups') else 0,
                            'Search ID': pop_guid
                        })
                    else:
                        member_search_names.append(f"Search {pop_guid[:8]}...")
                        member_data.append({
                            'Index': i,
                            'Search Name': f"Search {pop_guid[:8]}...",
                            'Description': 'Search not found in current analysis',
                            'Creation Time': 'N/A',
                            'Author': 'N/A',
                            'Parent Type': 'Unknown',
                            'Population Type': 'N/A',
                            'Criteria Groups': 0,
                            'Search ID': pop_guid
                        })
                
                member_df = pd.DataFrame(member_data)
                member_df_safe = sanitize_dataframe_for_excel(member_df)
                member_df_safe.to_excel(writer, sheet_name='Member_Searches', index=False)
            
            # Add member search count to overview (names are in separate tab)
            overview_data.append(['Member Searches Count', member_count])
            
            # 1. Create Overview Sheet FIRST (primary tab)
            overview_df = pd.DataFrame(overview_data, columns=['Property', 'Value'])
            overview_df_safe = sanitize_dataframe_for_excel(overview_df)
            overview_df_safe.to_excel(writer, sheet_name='Overview', index=False)
            
            # 3. Embedded Rules Sheet (detailed rule analysis like search exports)
            if hasattr(audit_report, 'criteria_groups') and audit_report.criteria_groups:
                rule_data = []
                
                for group_idx, group in enumerate(audit_report.criteria_groups, 1):
                    # Rule header
                    rule_data.extend([
                        ['Rule Number', group_idx],
                        ['Logic', group.member_operator],
                        ['Action if True', group.action_if_true],
                        ['Action if False', group.action_if_false],
                        ['Number of Criteria', len(group.criteria)],
                        ['', ''],  # Spacer
                    ])
                    
                    # Process main criteria (excluding linked ones)
                    main_criteria = [c for c in group.criteria if not self._is_linked_criterion(c, group.criteria)]
                    
                    for i, criterion in enumerate(main_criteria, 1):
                        rule_data.extend([
                            [f'Main Criterion {i}', criterion.display_name or 'Clinical Codes'],
                            ['  Table', criterion.table],
                            ['  Action', 'Exclude' if criterion.negation else 'Include'],
                            ['  Clinical Code Sets', len(criterion.value_sets) if criterion.value_sets else 0],
                            ['  Additional Filters', len(criterion.column_filters) if criterion.column_filters else 0],
                            ['  Linked Criteria', 'Yes' if criterion.linked_criteria else 'No'],
                            ['', '']
                        ])
                        
                        # Add restriction details
                        if criterion.restrictions:
                            for j, restriction in enumerate(criterion.restrictions, 1):
                                restriction_details = self._format_restriction_simple(restriction)
                                rule_data.extend([
                                    ['  Record Limit', restriction_details],
                                ])
                        
                        # Add main criterion filters (excluding linked ones)
                        if criterion.column_filters:
                            main_filters = self._get_main_criterion_filters(criterion)
                            for j, col_filter in enumerate(main_filters, 1):
                                filter_summary = self._format_filter_summary(col_filter)
                                rule_data.extend([
                                    [f'  Filter {j}', filter_summary],
                                ])
                            
                            if main_filters:
                                rule_data.append(['', ''])  # Spacer
                        
                        # Add linked criteria details
                        if criterion.linked_criteria:
                            for j, linked_crit in enumerate(criterion.linked_criteria, 1):
                                rule_data.extend([
                                    [f'  Linked Criterion {j}', linked_crit.display_name or 'Clinical Codes'],
                                    [f'    Table', linked_crit.table],
                                    [f'    Action', 'Exclude' if linked_crit.negation else 'Include'],
                                ])
                                
                                # Add linked criterion's restrictions
                                if linked_crit.restrictions:
                                    for k, restriction in enumerate(linked_crit.restrictions, 1):
                                        restriction_details = self._format_restriction_simple(restriction)
                                        rule_data.extend([
                                            [f'    Record Limit', restriction_details],
                                        ])
                                
                                # Add linked criterion's column filters
                                if linked_crit.column_filters:
                                    for k, col_filter in enumerate(linked_crit.column_filters, 1):
                                        filter_summary = self._format_filter_summary(col_filter)
                                        rule_data.extend([
                                            [f'    Filter {k}', filter_summary],
                                        ])
                                
                                rule_data.append(['', ''])  # Spacer after each linked criterion
                    
                    rule_data.append(['', ''])  # Spacer after each rule
                
                rule_df = pd.DataFrame(rule_data, columns=['Property', 'Value'])
                rule_df_safe = sanitize_dataframe_for_excel(rule_df)
                rule_df_safe.to_excel(writer, sheet_name='Embedded_Rules', index=False)
                
                # 4. Clinical Codes Sheet (if criteria has value sets)
                self._export_criteria_clinical_codes(writer, audit_report.criteria_groups, 'Rule_Codes')
        
        output.seek(0)
        
        # Generate filename
        clean_name = SearchManager.clean_search_name(audit_report.name)
        safe_name = "".join(c for c in clean_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"AuditReport_{safe_name}_{timestamp}.xlsx"
        
        return filename, output.getvalue()
    
    def _generate_search_report_export(self, search_report, include_parent_info=True):
        """Generate comprehensive export for Search Report"""
        # TODO: Implement search report export or delegate to existing SearchExportHandler
        return self._generate_basic_report_export(search_report, "SearchReport")
    
    def _generate_basic_report_export(self, report, report_type_prefix):
        """Generate basic export for report types not yet fully implemented"""
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Basic overview
            overview_data = [
                ['Report Type', report.report_type.title() if report.report_type else 'Unknown'],
                ['Report Name', report.name],
                ['Description', report.description or 'N/A'],
                ['Parent Type', report.parent_type or 'N/A'],
                ['Search Date', report.search_date],
                ['Export Date', datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                ['Note', f'Full {report_type_prefix} export implementation coming soon']
            ]
            
            overview_df = pd.DataFrame(overview_data, columns=['Property', 'Value'])
            overview_df_safe = sanitize_dataframe_for_excel(overview_df)
            overview_df_safe.to_excel(writer, sheet_name='Overview', index=False)
        
        output.seek(0)
        
        # Generate filename
        clean_name = SearchManager.clean_search_name(report.name)
        safe_name = "".join(c for c in clean_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"{report_type_prefix}_{safe_name}_{timestamp}.xlsx"
        
        return filename, output.getvalue()