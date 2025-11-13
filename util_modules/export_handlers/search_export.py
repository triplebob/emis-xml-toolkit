"""
Search Export Handler
Handles detailed per-search export functionality with comprehensive breakdowns
"""

import io
from datetime import datetime
import pandas as pd
from typing import List, Dict, Any, Optional
from ..utils.text_utils import pluralize_unit, format_operator_text
from ..core import ReportClassifier, SearchManager
from ..common.export_utils import sanitize_dataframe_for_excel


class SearchExportHandler:
    """Handles comprehensive export of individual search details"""
    
    def __init__(self, analysis):
        self.analysis = analysis
        
    def generate_search_export(self, search_report, include_parent_info=True):
        """
        Generate comprehensive export for any report type (Search, List, Audit, Aggregate)
        
        Args:
            search_report: The SearchReport to export
            include_parent_info: Whether to include parent search reference info
            
        Returns:
            tuple: (filename, file_content) ready for download
        """
        # Route to appropriate export method based on report type
        if hasattr(search_report, 'report_type'):
            if search_report.report_type == 'list':
                return self._generate_list_report_export(search_report, include_parent_info)
            elif search_report.report_type == 'audit':
                return self._generate_audit_report_export(search_report, include_parent_info)
            elif search_report.report_type == 'aggregate':
                return self._generate_aggregate_report_export(search_report, include_parent_info)
        
        # Default to search export for backward compatibility
        export_data = self._build_search_export_data(search_report, include_parent_info)
        
        # Create Excel file in memory
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Overview sheet
            overview_df = self._create_overview_sheet(search_report, include_parent_info)
            overview_df_safe = sanitize_dataframe_for_excel(overview_df)
            overview_df_safe.to_excel(writer, sheet_name='Overview', index=False)
            
            # Rules and criteria sheets
            for i, group in enumerate(search_report.criteria_groups, 1):
                rule_df = self._create_rule_sheet(group, i)
                rule_df_safe = sanitize_dataframe_for_excel(rule_df)
                rule_df_safe.to_excel(writer, sheet_name=f'Rule_{i}', index=False)
                
                # Clinical codes sheet for each rule
                codes_df = self._create_clinical_codes_sheet(group, i)
                if not codes_df.empty:
                    sheet_name = f'Rule_{i}_Codes'[:31]  # Excel sheet name limit
                    codes_df_safe = sanitize_dataframe_for_excel(codes_df)
                    codes_df_safe.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # All clinical codes summary
            all_codes_df = self._create_all_codes_summary(search_report)
            if not all_codes_df.empty:
                all_codes_df_safe = sanitize_dataframe_for_excel(all_codes_df)
                all_codes_df_safe.to_excel(writer, sheet_name='All_Clinical_Codes', index=False)
        
        output.seek(0)
        
        # Generate filename
        clean_name = SearchManager.clean_search_name(search_report.name)
        safe_name = "".join(c for c in clean_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"{safe_name}_{timestamp}.xlsx"
        
        return filename, output.getvalue()
    
    def _build_search_export_data(self, search_report, include_parent_info):
        """Build comprehensive data structure for export"""
        export_data = {
            'search_info': {
                'id': search_report.id,
                'name': search_report.name,
                'description': search_report.description,
                'folder': search_report.folder_id,
                'search_date': search_report.search_date,
                'creation_time': search_report.creation_time or '',
                'author': search_report.author or '',
                'population_type': search_report.population_type
            },
            'rules': [],
            'all_clinical_codes': []
        }
        
        if include_parent_info and search_report.parent_guid:
            export_data['parent_info'] = {
                'type': search_report.parent_type or '',
                'reference': search_report.parent_guid or 'Unknown parent search'
            }
        
        # Process each rule/criteria group
        for i, group in enumerate(search_report.criteria_groups, 1):
            rule_data = self._process_rule_for_export(group, i)
            export_data['rules'].append(rule_data)
            
            # Collect all clinical codes
            for criterion in group.criteria:
                self._collect_clinical_codes(criterion, export_data['all_clinical_codes'], i)
        
        return export_data
    
    def _process_rule_for_export(self, group, rule_number):
        """Process a rule/criteria group for export"""
        rule_data = {
            'rule_number': rule_number,
            'logic': group.member_operator,
            'action_if_true': group.action_if_true,
            'action_if_false': group.action_if_false,
            'criteria_count': len(group.criteria),
            'uses_another_search': bool(hasattr(group, 'population_criteria') and group.population_criteria),
            'criteria': [self._process_criterion_for_export(crit, i+1) for i, crit in enumerate(group.criteria)]
        }
        
        # Add population criteria details if present
        if hasattr(group, 'population_criteria') and group.population_criteria:
            rule_data['referenced_searches'] = []
            for pop_crit in group.population_criteria:
                ref_search_name = "Unknown Search"
                if hasattr(self.analysis, 'reports') and self.analysis.reports:
                    ref_report = next((r for r in self.analysis.reports if r.id == pop_crit.report_guid), None)
                    if ref_report:
                        from ..core import SearchManager
                        ref_search_name = SearchManager.clean_search_name(ref_report.name)
                
                rule_data['referenced_searches'].append({
                    'search_id': pop_crit.report_guid,
                    'search_name': ref_search_name
                })
        
        return rule_data
    
    def _process_criterion_for_export(self, criterion, criterion_number):
        """Process individual criterion for export"""
        criterion_data = {
            'criterion_number': criterion_number,
            'id': criterion.id,
            'table': criterion.table,
            'display_name': criterion.display_name,
            'description': criterion.description,
            'negation': criterion.negation,
            'exception_code': criterion.exception_code,
            'value_sets_count': len(criterion.value_sets) if criterion.value_sets else 0,
            'column_filters_count': len(criterion.column_filters) if criterion.column_filters else 0,
            'linked_criteria_count': len(criterion.linked_criteria) if criterion.linked_criteria else 0
        }
        
        # Add value sets details
        if criterion.value_sets:
            criterion_data['value_sets'] = [
                {
                    'id': vs.get('id', ''),
                    'code_system': vs.get('code_system', ''),
                    'description': vs.get('description', ''),
                    'values_count': len(vs.get('values', []))
                }
                for vs in criterion.value_sets
            ]
        
        # Add column filters details
        if criterion.column_filters:
            criterion_data['column_filters'] = [
                self._process_column_filter_for_export(cf)
                for cf in criterion.column_filters
            ]
        
        # Add linked criteria details
        if criterion.linked_criteria:
            criterion_data['linked_criteria'] = [
                self._process_criterion_for_export(linked, i+1)
                for i, linked in enumerate(criterion.linked_criteria)
            ]
        
        return criterion_data
    
    def _process_column_filter_for_export(self, column_filter):
        """Process column filter for export"""
        return {
            'column': column_filter.get('column', ''),
            'display_name': column_filter.get('display_name', ''),
            'type': column_filter.get('type', ''),
            'in_not_in': column_filter.get('in_not_in', ''),
            'operator': column_filter.get('operator', ''),
            'values': column_filter.get('values', []),
            'range_description': column_filter.get('range_description', ''),
            'restriction_type': column_filter.get('restriction_type', '')
        }
    
    def _collect_clinical_codes(self, criterion, codes_list, rule_number):
        """Collect all clinical codes from a criterion - EXCLUDE EMISINTERNAL codes"""
        if not criterion.value_sets:
            return
            
        for vs in criterion.value_sets:
            # Skip EMISINTERNAL value sets - they're not clinical codes
            if vs.get('code_system') == 'EMISINTERNAL':
                continue
                
            if not vs.get('values'):
                continue
                
            for value in vs['values']:
                codes_list.append({
                    'rule_number': rule_number,
                    'criterion_description': criterion.description,
                    'value_set_id': vs.get('id', ''),
                    'value_set_description': vs.get('description', ''),
                    'code_system': vs.get('code_system', ''),
                    'code_value': value.get('value', ''),
                    'display_name': value.get('display_name', ''),
                    'include_children': value.get('include_children', False),
                    'is_refset': value.get('is_refset', False)
                })
    
    def _create_overview_sheet(self, search_report, include_parent_info):
        """Create overview sheet for the search"""
        data = [
            ['Search Name', search_report.name],
            ['Description', search_report.description or 'N/A'],
            ['Creation Time', search_report.creation_time or 'N/A'],
            ['Author', search_report.author or 'N/A'],
            ['Population Type', search_report.population_type or ''],
            ['Search Date', search_report.search_date or ''],
            ['Number of Rules', len(search_report.criteria_groups)]
        ]
        
        if include_parent_info and search_report.parent_guid:
            data.extend([
                ['Parent Search Type', search_report.parent_type or ''],
                ['Parent Reference', search_report.parent_guid or '']
            ])
        
        data.extend([
            ['Export Generated', datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ['Export Tool', 'ClinXML']
        ])
        
        return pd.DataFrame(data, columns=['Property', 'Value'])
    
    def _create_rule_sheet(self, group, rule_number):
        """Create detailed rule sheet"""
        data = []
        
        # Count only main criteria (not linked ones that appear as separate criteria)
        main_criteria = [c for c in group.criteria if not self._is_linked_criterion(c, group.criteria)]
        main_criteria_count = len(main_criteria)
        
        # Rule header info
        data.extend([
            ['Rule Number', rule_number],
            ['Logic', group.member_operator],
            ['Action if True', group.action_if_true],
            ['Action if False', group.action_if_false],
            ['Number of Main Criteria', main_criteria_count],
            ['', '']  # Spacer
        ])
        
        # Check for population criteria (references to other searches)
        if hasattr(group, 'population_criteria') and group.population_criteria:
            data.extend([
                ['Uses Another Search', 'YES'],
                ['', '']  # Spacer
            ])
            
            for i, pop_crit in enumerate(group.population_criteria, 1):
                # Try to find the referenced search name - use fresh analysis from session state if available
                ref_search_name = "Unknown Search"
                analysis_to_use = self.analysis
                
                # Try to get fresh analysis from session state
                try:
                    import streamlit as st
                    fresh_analysis = st.session_state.get('search_analysis')
                    if fresh_analysis and hasattr(fresh_analysis, 'reports') and fresh_analysis.reports:
                        analysis_to_use = fresh_analysis
                except:
                    pass  # Fallback to self.analysis if streamlit not available
                
                if hasattr(analysis_to_use, 'reports') and analysis_to_use.reports:
                    ref_report = next((r for r in analysis_to_use.reports if r.id == pop_crit.report_guid), None)
                    if ref_report:
                        from ..core import SearchManager
                        ref_search_name = SearchManager.clean_search_name(ref_report.name)
                    else:
                        # Try to find in all reports (including member searches)
                        all_reports = []
                        def collect_all_reports(reports):
                            for report in reports:
                                all_reports.append(report)
                                if hasattr(report, 'member_searches') and report.member_searches:
                                    collect_all_reports(report.member_searches)
                        
                        collect_all_reports(analysis_to_use.reports)
                        ref_report = next((r for r in all_reports if r.id == pop_crit.report_guid), None)
                        
                        if ref_report:
                            from ..core import SearchManager
                            ref_search_name = SearchManager.clean_search_name(ref_report.name)
                
                data.extend([
                    [f'Referenced Search {i}', ref_search_name],
                    [f'  Search ID', pop_crit.report_guid[:8] + '...'],
                    ['', '']  # Spacer
                ])
        else:
            data.extend([
                ['Uses Another Search', 'NO'],
                ['', '']  # Spacer
            ])
        
        # Criteria details - show only main criteria (skip those that are linked to others)
        main_criteria = [c for c in group.criteria if not self._is_linked_criterion(c, group.criteria)]
        
        for i, criterion in enumerate(main_criteria, 1):
            criterion_label = f'Main Criterion {i}'
            
            # Use the same filtering logic as the UI to avoid showing all filters from baseCriteriaGroup
            try:
                from ..analysis.linked_criteria_handler import filter_linked_column_filters_from_main, filter_linked_value_sets_from_main
                main_column_filters = filter_linked_column_filters_from_main(criterion)
                main_value_sets = filter_linked_value_sets_from_main(criterion)
                additional_filters_count = len(main_column_filters)
                # Count only non-EMISINTERNAL value sets as clinical codes
                clinical_code_sets_count = len([vs for vs in main_value_sets if vs.get('code_system') != 'EMISINTERNAL'])
            except ImportError:
                # Fallback to original logic if import fails
                additional_filters_count = len(criterion.column_filters) if criterion.column_filters else 0
                # Count only non-EMISINTERNAL value sets as clinical codes
                if criterion.value_sets:
                    clinical_code_sets_count = len([vs for vs in criterion.value_sets if vs.get('code_system') != 'EMISINTERNAL'])
                else:
                    clinical_code_sets_count = 0
            
            data.extend([
                [criterion_label, criterion.display_name or ''],
                ['  Table', criterion.table],
                ['  Action', 'Exclude' if criterion.negation else 'Include'],
                ['  Clinical Code Sets', clinical_code_sets_count],
                ['  Additional Filters', additional_filters_count],
                ['  Linked Criteria', 'Yes' if criterion.linked_criteria else 'No'],
                ['', '']  # Spacer
            ])
            
            # Add restriction details (like "Latest 1") 
            if criterion.restrictions:
                for j, restriction in enumerate(criterion.restrictions, 1):
                    restriction_details = self._format_restriction_simple(restriction)
                    data.extend([
                        ['  Record Limit', restriction_details],
                    ])
            
            # Add main criterion filters (excluding those that belong to linked criteria)
            if criterion.column_filters:
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
                
                # Mirror UI two-tier filter structure
                if main_filters:
                    # First tier: Main Filters (aggregated summaries)
                    main_filter_summaries = self._generate_main_filter_summaries(main_filters)
                    for j, summary in enumerate(main_filter_summaries, 1):
                        data.extend([
                            [f'  Filter {j}', summary],
                        ])
                    
                    # Second tier: Additional Filters (individual EMISINTERNAL breakdown)
                    additional_filters = self._generate_additional_filter_details(main_filters)
                    if additional_filters:
                        data.append(['', ''])  # Spacer
                        data.extend([
                            ['  Additional Filters', ''],
                        ])
                        for k, detail in enumerate(additional_filters, 1):
                            data.extend([
                                [f'    Detail {k}', detail],
                            ])
                    
                    data.append(['', ''])  # Spacer
            
            # Add simplified linked criteria details
            if criterion.linked_criteria:
                for j, linked_crit in enumerate(criterion.linked_criteria, 1):
                    data.extend([
                        [f'  Linked Criterion {j}', linked_crit.display_name or 'Clinical Codes'],
                        [f'    Table', linked_crit.table],
                        [f'    Action', 'Exclude' if linked_crit.negation else 'Include'],
                    ])
                    
                    # Add linked criterion's restrictions
                    if linked_crit.restrictions:
                        for k, restriction in enumerate(linked_crit.restrictions, 1):
                            restriction_details = self._format_restriction_simple(restriction)
                            data.extend([
                                [f'    Record Limit', restriction_details],
                            ])
                    
                    # Add linked criterion's column filters
                    if linked_crit.column_filters:
                        for k, col_filter in enumerate(linked_crit.column_filters, 1):
                            filter_summary = self._render_column_filter_for_export(col_filter)
                            data.extend([
                                [f'    Filter {k}', filter_summary],
                            ])
                    
                    data.append(['', ''])  # Spacer after each linked criterion
        
        
        return pd.DataFrame(data, columns=['Property', 'Value'])
    
    def _create_clinical_codes_sheet(self, group, rule_number):
        """Create clinical codes sheet for a rule"""
        codes_data = []
        
        # Only process main criteria (not those that are linked to others)
        main_criteria = [c for c in group.criteria if not self._is_linked_criterion(c, group.criteria)]
        
        for i, criterion in enumerate(main_criteria, 1):
            # This is a main criterion
            if not criterion.value_sets:
                continue
                
            for vs in criterion.value_sets:
                # Skip EMISINTERNAL value sets - they're not clinical codes
                if vs.get('code_system') == 'EMISINTERNAL':
                    continue
                    
                if not vs.get('values'):
                    continue
                    
                for value in vs['values']:
                    emis_code = value.get('value', '')
                    snomed_info = self._get_snomed_translation(emis_code)
                    
                    codes_data.append({
                        'Rule Number': rule_number,
                        'Criterion Number': i,
                        'Criterion Type': "MAIN CRITERION",
                        'Criterion Description': criterion.description,
                        'Exception Code': criterion.exception_code or '',
                        'Value Set ID': vs.get('id', ''),
                        'Value Set Description': vs.get('description', ''),
                        'Code System': vs.get('code_system', ''),
                        'EMIS GUID': emis_code,
                        'SNOMED Code': snomed_info.get('snomed_code', 'Not found'),
                        'SNOMED Description': snomed_info.get('description', value.get('display_name', '')),
                        'Display Name': value.get('display_name', ''),
                        'Include Children': value.get('include_children', False),
                        'Is Refset': value.get('is_refset', False)
                    })
            
            # Include codes from linked criteria within this criterion
            if criterion.linked_criteria:
                for j, linked_crit in enumerate(criterion.linked_criteria, 1):
                    if linked_crit.value_sets:
                        for vs in linked_crit.value_sets:
                            # Skip EMISINTERNAL value sets - they're not clinical codes
                            if vs.get('code_system') == 'EMISINTERNAL':
                                continue
                                
                            if not vs.get('values'):
                                continue
                                
                            for value in vs['values']:
                                emis_code = value.get('value', '')
                                snomed_info = self._get_snomed_translation(emis_code)
                                
                                codes_data.append({
                                    'Rule Number': rule_number,
                                    'Criterion Number': f"{i}.{j}",
                                    'Criterion Type': f"LINKED TO CRITERION {i}",
                                    'Criterion Description': linked_crit.description,
                                    'Exception Code': linked_crit.exception_code or '',
                                    'Value Set ID': vs.get('id', ''),
                                    'Value Set Description': vs.get('description', ''),
                                    'Code System': vs.get('code_system', ''),
                                    'EMIS GUID': emis_code,
                                    'SNOMED Code': snomed_info.get('snomed_code', 'Not found'),
                                    'SNOMED Description': snomed_info.get('description', value.get('display_name', '')),
                                    'Display Name': value.get('display_name', ''),
                                    'Include Children': value.get('include_children', False),
                                    'Is Refset': value.get('is_refset', False)
                                })
        
        return pd.DataFrame(codes_data) if codes_data else pd.DataFrame()
    
    def _create_all_codes_summary(self, search_report):
        """Create summary of all clinical codes across all rules"""
        all_codes = []
        
        for rule_num, group in enumerate(search_report.criteria_groups, 1):
            # Only process main criteria (not those that are linked to others)
            main_criteria = [c for c in group.criteria if not self._is_linked_criterion(c, group.criteria)]
            
            for crit_num, criterion in enumerate(main_criteria, 1):
                # This is a main criterion
                if not criterion.value_sets:
                    continue
                    
                for vs in criterion.value_sets:
                    # Skip EMISINTERNAL value sets - they're not clinical codes
                    if vs.get('code_system') == 'EMISINTERNAL':
                        continue
                        
                    if not vs.get('values'):
                        continue
                        
                    for value in vs['values']:
                        emis_code = value.get('value', '')
                        snomed_info = self._get_snomed_translation(emis_code)
                        
                        all_codes.append({
                            'Rule': rule_num,
                            'Criterion': crit_num,
                            'Criterion Type': "MAIN CRITERION",
                            'Criterion Description': criterion.description,
                            'Exception Code': criterion.exception_code or '',
                            'Value Set': vs.get('description', vs.get('id', 'Unknown')),
                            'Code System': vs.get('code_system', ''),
                            'EMIS GUID': emis_code,
                            'SNOMED Code': snomed_info.get('snomed_code', 'Not found'),
                            'SNOMED Description': snomed_info.get('description', value.get('display_name', '')),
                            'Display Name': value.get('display_name', ''),
                            'Include Children': value.get('include_children', False),
                            'Is Refset': value.get('is_refset', False)
                        })
                
                # Include codes from linked criteria within this criterion
                if criterion.linked_criteria:
                    for j, linked_crit in enumerate(criterion.linked_criteria, 1):
                        if linked_crit.value_sets:
                            for vs in linked_crit.value_sets:
                                # Skip EMISINTERNAL value sets - they're not clinical codes
                                if vs.get('code_system') == 'EMISINTERNAL':
                                    continue
                                    
                                if not vs.get('values'):
                                    continue
                                    
                                for value in vs['values']:
                                    emis_code = value.get('value', '')
                                    snomed_info = self._get_snomed_translation(emis_code)
                                    
                                    all_codes.append({
                                        'Rule': rule_num,
                                        'Criterion': f"{crit_num}.{j}",
                                        'Criterion Type': f"LINKED TO CRITERION {crit_num}",
                                        'Criterion Description': linked_crit.description,
                                        'Exception Code': linked_crit.exception_code or '',
                                        'Value Set': vs.get('description', vs.get('id', 'Unknown')),
                                        'Code System': vs.get('code_system', ''),
                                        'EMIS GUID': emis_code,
                                        'SNOMED Code': snomed_info.get('snomed_code', 'Not found'),
                                        'SNOMED Description': snomed_info.get('description', value.get('display_name', '')),
                                        'Display Name': value.get('display_name', ''),
                                        'Include Children': value.get('include_children', False),
                                        'Is Refset': value.get('is_refset', False)
                                    })
        
        return pd.DataFrame(all_codes) if all_codes else pd.DataFrame()
    
    def _is_linked_criterion(self, criterion, all_criteria):
        """Check if a criterion appears as a linked criterion in another criterion within the same rule"""
        for other_criterion in all_criteria:
            if other_criterion.id != criterion.id and other_criterion.linked_criteria:
                for linked in other_criterion.linked_criteria:
                    if linked.id == criterion.id:
                        return True
        return False
    
    def _get_snomed_translation(self, emis_code: str) -> Dict[str, Any]:
        """Get SNOMED translation from already processed clinical codes"""
        try:
            # Import the same function used by clinical tabs to get unified data
            from ..ui.tabs.tab_helpers import get_unified_clinical_data
            unified_results = get_unified_clinical_data()
            
            # Search through clinical codes
            clinical_codes = unified_results.get('clinical_codes', [])
            for code in clinical_codes:
                if code.get('EMIS GUID', '') == emis_code:
                    return {
                        'snomed_code': code.get('SNOMED Code', 'Not found'),
                        'description': code.get('Description', ''),
                        'code_system': code.get('Code System', ''),
                        'is_medication': False,
                        'is_refset': code.get('Refset', 'No') == 'Yes',
                        'status': 'translated' if code.get('SNOMED Code', 'Not found') != 'Not found' else 'not_found'
                    }
            
            # Search through medications
            medications = unified_results.get('medications', [])
            for med in medications:
                if med.get('EMIS GUID', '') == emis_code:
                    return {
                        'snomed_code': med.get('SNOMED Code', 'Not found'),
                        'description': med.get('Description', ''),
                        'code_system': med.get('Code System', ''),
                        'is_medication': True,
                        'is_refset': False,
                        'status': 'translated' if med.get('SNOMED Code', 'Not found') != 'Not found' else 'not_found'
                    }
            
            # Search through refsets
            refsets = unified_results.get('refsets', [])
            for refset in refsets:
                if refset.get('EMIS GUID', '') == emis_code:
                    return {
                        'snomed_code': refset.get('SNOMED Code', 'Not found'),
                        'description': refset.get('Description', ''),
                        'code_system': refset.get('Code System', ''),
                        'is_medication': False,
                        'is_refset': True,
                        'status': 'translated' if refset.get('SNOMED Code', 'Not found') != 'Not found' else 'not_found'
                    }
            
        except Exception:
            # Fallback to not found if unified data not available
            pass
        
        # If not found in processed data, return not found
        return {
            'snomed_code': 'Not found',
            'description': '',
            'code_system': '',
            'is_medication': False,
            'is_refset': False,
            'status': 'not_found'
        }
    
    def _format_column_filter_details(self, col_filter):
        """Format column filter details into a comprehensive, rebuild-ready description"""
        details = []
        
        # Basic filter info - essential for rebuilding
        column = col_filter.get('column', 'Unknown')
        display_name = col_filter.get('display_name', column)
        details.append(f"Column: {display_name} ({column})")
        
        # In/Not In - critical for rebuild
        in_not_in = col_filter.get('in_not_in', '')
        if in_not_in:
            action = "Include" if in_not_in.upper() == "IN" else "Exclude" if in_not_in.upper() == "NOTIN" else in_not_in
            details.append(f"Action: {action} ({in_not_in})")
        
        # Enhanced range information with specific values for rebuild
        if 'range' in col_filter and col_filter['range']:
            range_description = self._format_range_description_from_parsed(col_filter['range'])
            if range_description:
                details.append(f"Range: {range_description}")
        
        # Relationship information for linked criteria - essential for rebuild
        if 'relationship' in col_filter:
            relationship_desc = self._format_relationship_description(col_filter['relationship'])
            if relationship_desc:
                details.append(f"Relationship: {relationship_desc}")
        
        # Values list with complete details for rebuild
        if 'values' in col_filter and col_filter['values']:
            values = col_filter['values']
            details.append(f"Values Count: {len(values)}")
            if len(values) <= 10:  # Show more values for rebuild purposes
                values_str = ', '.join(str(v) for v in values)
                details.append(f"Values: {values_str}")
            else:
                values_str = f"{', '.join(str(v) for v in values[:5])}... (showing 5 of {len(values)})"
                details.append(f"Values (partial): {values_str}")
        
        # Context-specific rebuild instructions based on column type
        column_name = col_filter.get('column', '')
        
        # Handle case where column might be a list
        if isinstance(column_name, list):
            column_name = ' + '.join(column_name) if column_name else ''
        
        column_name = column_name.upper()
        
        # Clinical coding - specific instructions for rebuild
        if column_name in ['READCODE', 'SNOMEDCODE']:
            details.append("Filter Type: Clinical codes - Use Clinical Code column in EMIS search builder")
            details.append("Rebuild: Select 'Clinical Codes' table, choose appropriate value sets")
        elif column_name in ['DRUGCODE']:
            details.append("Filter Type: Medication codes - Use Drug column in EMIS search builder")
            details.append("Rebuild: Select 'Medication Issues' table, choose drug codes/groups")
        elif column_name in ['DISPLAYTERM', 'NAME']:
            details.append("Filter Type: Medication names - Use drug name/description filtering")
        
        # Date/time columns with specific rebuild instructions
        elif column_name in ['DATE']:
            details.append("Filter Type: General date - Use Date column with range settings")
            details.append("Rebuild: Set date range relative to search date or absolute dates")
        elif column_name in ['ISSUE_DATE', 'PRESCRIPTION_DATE']:
            details.append("Filter Type: Medication dates - Use Issue Date in medication table")
        elif column_name in ['CONSULTATION_DATE', 'EPISODE_DATE']:
            details.append("Filter Type: Episode dates - Use consultation/episode date filtering")
        elif column_name in ['DATE_OF_BIRTH', 'DOB']:
            details.append("Filter Type: Birth date - Use Date of Birth in patient demographics")
        elif column_name == 'GMS_DATE_OF_REGISTRATION':
            details.append("Filter Type: Registration date - Use GMS registration date from patient table")
        
        # Demographics and age with rebuild guidance
        elif column_name in ['AGE']:
            details.append("Filter Type: Patient age - Use Age column in patient demographics")
            details.append("Rebuild: Set age range (years) with >= or <= operators")
        elif column_name == 'AGE_AT_EVENT':
            details.append("Filter Type: Age at event - Use Age at Event for vaccination/procedure timing")
            details.append("Rebuild: Specify age at time of specific clinical event")
        
        # Clinical values and measurements
        elif column_name == 'NUMERIC_VALUE':
            details.append("Filter Type: Numeric values - Use Value column for test results")
            details.append("Rebuild: Set numeric range for lab results, spirometry, BMI, etc.")
        
        # Episode and workflow states
        elif column_name in ['EPISODE']:
            details.append("Filter Type: Episode states - Use Episode column for workflow status")
            details.append("Rebuild: Select episode types (FIRST, NEW, REVIEW, ENDED, NONE)")
        
        # Record count and sorting - critical for rebuild
        if 'record_count' in col_filter:
            count = col_filter['record_count']
            details.append(f"Record Limit: Latest {count} records")
            details.append(f"Rebuild: Set restriction to 'Latest {count}' in search builder")
        
        # Sort direction - essential for rebuild
        if 'direction' in col_filter:
            direction = col_filter['direction']
            direction_text = "Most recent first (DESC)" if direction == "DESC" else "Earliest first (ASC)" if direction == "ASC" else direction
            details.append(f"Sort Direction: {direction_text}")
            details.append(f"Rebuild: Set sort order to {direction}")
        
        # Test attributes and complex conditions
        if 'test_attribute' in col_filter:
            details.append("Complex Conditions: Test attributes applied")
            details.append("Rebuild: Use advanced restrictions with conditional logic")
        
        # Enhanced restriction type descriptions with rebuild instructions
        if 'restriction_type' in col_filter:
            restriction = col_filter['restriction_type']
            details.append(f"Restriction Type: {restriction}")
            if restriction.lower() in ['current', 'is_current']:
                details.append("Rebuild: Add restriction for 'Current/Active records only'")
            elif restriction.lower() in ['latest', 'most_recent']:
                details.append("Rebuild: Add restriction for 'Latest records only'")
            elif restriction.lower() in ['earliest', 'first']:
                details.append("Rebuild: Add restriction for 'Earliest records only'")
        
        # Current status indicators
        column_check = col_filter.get('column', '')
        if isinstance(column_check, list):
            column_check = ' + '.join(column_check) if column_check else ''
        
        if column_check.upper() in ['CURRENT', 'IS_CURRENT', 'STATUS']:
            details.append("Status Filter: Current/Active records only")
            details.append("Rebuild: Enable 'Current records only' checkbox")
        elif column_name == 'EPISODE':
            details.append("Episode type filtering (FIRST, NEW, REVIEW, ENDED, NONE)")
        
        # NHS/system identifiers
        elif column_name in ['NHS_NO', 'NHS_NUMBER']:
            details.append("NHS number filtering")
        elif column_name in ['ORGANISATION_NPC', 'ORGANISATION_CODE']:
            details.append("Organisation code filtering")
        
        # Value set and code system context
        if 'code_system' in col_filter:
            code_system = col_filter.get('code_system', '').upper()
            if 'SCT_DRGGRP' in code_system:
                details.append("Drug group classification")
            elif 'EMISINTERNAL' in code_system:
                # Extract specific EMISINTERNAL context
                emisinternal_context = self._get_emisinternal_context(col_filter)
                details.append(emisinternal_context)
            elif 'SNOMED_CONCEPT' in code_system:
                details.append("SNOMED clinical terminology")
        
        return ' | '.join(details) if details else 'No filter details available'
    
    def _get_emisinternal_context(self, col_filter):
        """Extract specific context for EMISINTERNAL codes"""
        column_name = col_filter.get('column', '').upper()
        column_display = col_filter.get('display_name', '').lower()
        in_not_in = col_filter.get('in_not_in', 'IN')
        action = "Include" if in_not_in == "IN" else "Exclude"
        
        # Get the actual values being filtered
        value_sets = col_filter.get('value_sets', [])
        if value_sets:
            # Get first value set for context
            vs = value_sets[0]
            values = vs.get('values', [])
            if values:
                value = values[0]
                code_value = value.get('value', '').lower()
                display_name = value.get('display_name', '')
                
                # Specific column context mapping
                if column_name == 'ISSUE_METHOD':
                    return f"{action} issue method: {display_name}" if display_name else f"{action} issue methods"
                elif column_name == 'IS_PRIVATE':
                    if code_value == 'false':
                        return f"{action} NHS prescriptions: False (not privately paid)"
                    elif code_value == 'true':
                        return f"{action} private prescriptions: True (patient paid)"
                    else:
                        return f"{action} prescription funding type: {display_name or code_value}"
                elif column_name in ['AUTHOR', 'CURRENTLY_CONTRACTED']:
                    return f"{action} user authorization: {display_name}" if display_name else f"{action} user authorization"
                elif 'consultation' in column_display or 'heading' in column_display:
                    return f"{action} consultation heading: {display_name}" if display_name else f"{action} consultation headings"
                else:
                    context = column_display if column_display else "internal classification"
                    return f"{action} {context}: {display_name}" if display_name else f"{action} {context}"
        
        # Fallback for column-level context
        if column_name == 'ISSUE_METHOD':
            return f"{action} issue methods"
        elif column_name == 'IS_PRIVATE':
            return f"{action} prescription funding type (NHS vs private)"
        elif column_name in ['AUTHOR', 'CURRENTLY_CONTRACTED']:
            return f"{action} user authorization filters"
        else:
            return f"{action} EMIS internal classification"
    
    def _format_range_description(self, col_filter):
        """Format range information into human-readable descriptions"""
        range_parts = []
        
        
        # Helper function to format relative dates
        def format_relative_date_emis(value_dict, operator='GTEQ'):
            val = value_dict.get('value', '')
            unit = value_dict.get('unit', '').lower()
            
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
            if val and val.lstrip('-').isdigit():
                if val.startswith('-'):
                    # Negative relative date (before search date)
                    abs_value = val[1:]  # Remove the minus sign
                    from ..utils.text_utils import pluralize_unit
                    unit_text = pluralize_unit(abs_value, unit)
                    return f"and the Date is {op_text} {abs_value} {unit_text} before the search date"
                else:
                    # Positive relative date (after search date)
                    from ..utils.text_utils import pluralize_unit
                    unit_text = pluralize_unit(val, unit)
                    return f"and the Date is {op_text} {val} {unit_text} after the search date"
            
            # Handle temporal variable patterns (Last/This/Next + time unit)  
            elif unit.lower() in ['day', 'week', 'month', 'quarter', 'year', 'fiscalyear']:
                if val.lower() == 'last':
                    if unit.lower() == 'fiscalyear':
                        return "and the Date is last fiscal year"
                    elif unit.lower() == 'quarter':
                        return "and the Date is last yearly quarter"
                    else:
                        return f"and the Date is last {unit.lower()}"
                elif val.lower() == 'this':
                    if unit.lower() == 'fiscalyear':
                        return "and the Date is this fiscal year"
                    elif unit.lower() == 'quarter':
                        return "and the Date is this yearly quarter"
                    else:
                        return f"and the Date is this {unit.lower()}"
                elif val.lower() == 'next':
                    if unit.lower() == 'fiscalyear':
                        return "and the Date is next fiscal year"
                    elif unit.lower() == 'quarter':
                        return "and the Date is next yearly quarter"
                    else:
                        return f"and the Date is next {unit.lower()}"
                else:
                    return f"and the Date is {val} {unit.lower()}"
            
            # Fallback for unrecognized patterns
            return f"Date filter: {val} {unit}"
        
        # Process range_from
        if 'range_from' in col_filter:
            from_val = col_filter['range_from']
            operator = from_val.get('operator', 'GTEQ')
            op_text = translate_operator(operator, is_numeric=False)  # Default to date format
            value = from_val.get('value', {})
            
            if isinstance(value, dict) and value.get('relation') == 'RELATIVE':
                date_desc = format_relative_date_emis(value, operator)
                range_parts.append(f"{op_text} {date_desc}")
            else:
                range_parts.append(f"{op_text} {value}")
        
        # Process range_to  
        if 'range_to' in col_filter:
            to_val = col_filter['range_to']
            operator = to_val.get('operator', 'LTEQ')
            op_text = translate_operator(operator, is_numeric=False)  # Default to date format
            value = to_val.get('value', {})
            
            if isinstance(value, dict) and value.get('relation') == 'RELATIVE':
                date_desc = format_relative_date_emis(value, operator)
                range_parts.append(f"{op_text} {date_desc}")
            elif not value:  # Empty value for "up to baseline"
                range_parts.append(f"{op_text} the search date")
            else:
                range_parts.append(f"{op_text} {value}")
        
        return f"Range: {' AND '.join(range_parts)}" if range_parts else None
    
    def _format_range_description_from_parsed(self, range_data):
        """Format range information from the parsed data structure"""
        if not range_data:
            return None
        
        range_parts = []
        
        # Use shared operator formatting function
        def translate_operator(op, is_numeric=False):
            return format_operator_text(op, is_numeric)
        
        # Helper function to format relative dates and age values  
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
                    unit_text = pluralize_unit(abs_value, unit)
                    return f"and the Date is {op_text} {abs_value} {unit_text} before the search date"
                else:
                    # Positive relative date (after search date)
                    unit_text = pluralize_unit(value, unit)
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
            
            # Fallback for any unhandled patterns
            else:
                return f"Date filter: {value} {unit}"
        
        # Process range from
        if range_data.get('from'):
            from_data = range_data['from']
            operator = from_data.get('operator', 'GTEQ')
            value = from_data.get('value', '')
            unit = from_data.get('unit', '')
            relation = from_data.get('relation', '')
            
            if value and unit:
                date_desc = format_relative_date(value, unit, relation, operator)
                op_text = translate_operator(operator, is_numeric=False)
                range_parts.append(f"{op_text} {date_desc}")
            elif value:
                # Handle numeric values (like spirometry results, BMI scores)
                op_text = translate_operator(operator, is_numeric=True)
                if value.replace('.', '').replace('-', '').isdigit():
                    range_parts.append(f"{op_text} {value}")
                else:
                    range_parts.append(f"{op_text} {value}")
        
        # Process range to  
        if range_data.get('to'):
            to_data = range_data['to']
            operator = to_data.get('operator', 'LTEQ')
            value = to_data.get('value', '')
            unit = to_data.get('unit', '')
            relation = to_data.get('relation', '')
            
            # Always define op_text first
            op_text = translate_operator(operator, is_numeric=False)
            
            if value and unit:
                date_desc = format_relative_date(value, unit, relation, operator)
                range_parts.append(f"{op_text} {date_desc}")
            elif value:
                # Handle numeric values (like spirometry results, BMI scores)
                op_text = translate_operator(operator, is_numeric=True)
                if value.replace('.', '').isdigit():
                    range_parts.append(f"{op_text} {value}")
                else:
                    range_parts.append(f"{op_text} {value}")
            elif range_data.get('relative_to') == 'BASELINE':
                range_parts.append(f"{op_text} the search date")
            else:
                range_parts.append(f"{op_text}")
        
        return f"Range: {' AND '.join(range_parts)}" if range_parts else None
    
    def _format_relationship_description(self, relationship):
        """Format relationship information for linked criteria"""
        if not relationship:
            return None
        
        parent_col = relationship.get('parent_column', 'Unknown')
        child_col = relationship.get('child_column', 'Unknown')
        
        # Check for range relationship
        if 'range_from' in relationship:
            from_val = relationship['range_from']
            operator = from_val.get('operator', 'GT')
            value = from_val.get('value', {})
            
            if isinstance(value, dict):
                val_str = value.get('value', '0')
                unit = value.get('unit', 'DAY').lower()
                
                if operator == 'GT' and val_str == '0' and unit == 'day':
                    return f"Relationship: The {child_col} is more than 0 days after the {parent_col} from the above feature"
        
        return f"Relationship: {child_col} relates to {parent_col}"
    
    def _format_restriction_details(self, restriction):
        """Format comprehensive restriction details including latest/earliest, current status, etc."""
        if not restriction:
            return "Unknown restriction"
        
        # Handle SearchRestriction objects
        if hasattr(restriction, 'type'):
            restriction_type = restriction.type
            if restriction_type == "latest_records":
                # Enhanced description for record restrictions
                if hasattr(restriction, 'record_count') and hasattr(restriction, 'direction'):
                    count = restriction.record_count
                    direction = restriction.direction
                    
                    details = []
                    if direction == "DESC":
                        if count == 1:
                            details.append("Latest 1 record only")
                        else:
                            details.append(f"Latest {count} records only")
                        details.append("Ordered by: most recent first")
                    elif direction == "ASC":
                        if count == 1:
                            details.append("Earliest 1 record only")
                        else:
                            details.append(f"Earliest {count} records only")
                        details.append("Ordered by: earliest first")
                    else:
                        details.append(f"{count} records with {direction} ordering")
                        
                    return " | ".join(details)
                elif hasattr(restriction, 'description'):
                    return restriction.description
                else:
                    return "Record count restriction applied"
                    
            elif restriction_type == "conditional_latest":
                # Complex restriction with conditional logic (like AST005)
                if hasattr(restriction, 'description') and restriction.description:
                    details = [restriction.description]
                    if hasattr(restriction, 'record_count') and hasattr(restriction, 'direction'):
                        direction_text = "most recent first" if restriction.direction == "DESC" else "earliest first"
                        details.append(f"Ordered by: {direction_text}")
                    return " | ".join(details)
                else:
                    return "Conditional record filtering applied"
                    
            elif restriction_type == "test_condition":
                # Test condition descriptions
                if hasattr(restriction, 'description') and restriction.description:
                    return restriction.description
                else:
                    details = ["Additional filtering condition"]
                    if hasattr(restriction, 'conditions') and restriction.conditions:
                        details.append("Complex test criteria applied")
                    return " | ".join(details)
                
            elif restriction_type == "current_status":
                return "Only current/active records included"
                
            elif restriction_type == "date_range":
                return "Date range filtering applied"
                
            elif restriction_type == "medication_current":
                return "Only current medications included"
                
            elif restriction_type == "latest_issue":
                if hasattr(restriction, 'issue_count'):
                    count = restriction.issue_count
                    return f"Latest issue is {count}"
                return "Latest issue restriction"
                
            elif restriction_type == "episode_based":
                return "Episode-based filtering (FIRST, NEW, REVIEW, etc.)"
                
            elif restriction_type == "age_range":
                return "Age range restriction applied"
                
            elif restriction_type == "demographic":
                return "Patient demographic filtering"
                
            else:
                # Fallback to description if available
                if hasattr(restriction, 'description') and restriction.description:
                    return restriction.description
                return f"Restriction type: {restriction_type}"
        
        # Handle dictionary format (legacy support)
        if isinstance(restriction, dict):
            if 'record_count' in restriction:
                count = restriction['record_count']
                direction = restriction.get('direction', 'DESC')
                order_text = "latest" if direction == "DESC" else "earliest"
                return f"{order_text.title()} {count} records only"
            elif 'type' in restriction:
                return f"Restriction: {restriction['type']}"
        
        return str(restriction)
    
    def _format_restriction_simple(self, restriction):
        """Format restriction details in a simple, user-friendly way"""
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
        """Format column filter in EMIS clinical style"""
        if not col_filter:
            return "No filter"
        
        column = col_filter.get('column', 'Unknown')
        
        # Handle case where column might be a list
        if isinstance(column, list):
            column = ' + '.join(column) if column else 'Unknown'
        
        display_name = col_filter.get('display_name', column)
        
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
                
        elif column.upper() in ['DATE', 'ISSUE_DATE']:
            # Check for range information
            if 'range' in col_filter and col_filter['range']:
                range_desc = self._format_range_emis_style(col_filter['range'])
                return range_desc if range_desc else "Date is after/before search date"
            return f"{display_name} filter applied"
            
        elif column.upper() == 'AGE':
            # Age range information
            if 'range' in col_filter and col_filter['range']:
                range_desc = self._format_range_emis_style(col_filter['range'], is_age=True)
                return range_desc if range_desc else "Age filter applied"
            return "Age filter applied"
            
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
                                # Handle dict format with displayName
                                heading_types.append(v.get('displayName', v.get('value', str(v))))
                            else:
                                # Handle simple string format
                                heading_types.append(str(v))
            
            action = "Include" if in_not_in.upper() == "IN" else "Exclude"
            
            if heading_types:
                if len(heading_types) == 1:
                    return f"{action} consultations where the consultation heading is: {heading_types[0]}"
                else:
                    return f"{action} consultations with heading types: {', '.join(heading_types)}"
            else:
                return f"{action} consultations with specified heading types"
                
        elif column.upper() == 'NUMERIC_VALUE':
            # Numeric value ranges
            if 'range' in col_filter and col_filter['range']:
                range_desc = self._format_range_emis_style(col_filter['range'], is_numeric=True)
                return range_desc if range_desc else "Numeric value range filter"
            return "Numeric value range filter"
            
        elif column.upper() == 'EPISODE':
            # Episode type filtering
            values = col_filter.get('values', [])
            in_not_in = col_filter.get('in_not_in', 'IN')
            
            if values:
                episode_types = [str(v) for v in values]
                action = "Include" if in_not_in.upper() == "IN" else "Exclude"
                return f"{action} episodes of type: {', '.join(episode_types)}"
            else:
                return "Episode type filter applied"
                
        elif 'DRUG' in column.upper():
            # Drug/medication codes
            value_count = len(col_filter.get('values', []))
            if value_count > 0:
                return f"Include {value_count} specified medication codes"
            else:
                return "Include specified medication codes"
        else:
            # Check if this is an EMISINTERNAL filter for enhanced context
            if col_filter.get('value_sets'):
                is_emisinternal = any(vs.get('code_system') == 'EMISINTERNAL' for vs in col_filter['value_sets'])
                if is_emisinternal:
                    # Use the enhanced EMISINTERNAL context
                    return self._get_emisinternal_context(col_filter)
            
            return f"{display_name} filter applied"
    
    def _format_range_simple(self, range_data):
        """Format range information in a simple way"""
        if not range_data:
            return None
        
        parts = []
        
        # Process range from
        if range_data.get('from'):
            from_data = range_data['from']
            value = from_data.get('value', '')
            unit = from_data.get('unit', '')
            
            if value and unit:
                if value.startswith('-'):
                    val_num = value[1:]
                    parts.append(f"{val_num} {unit}s ago")
                else:
                    parts.append(f"{value} {unit}s")
        
        # Process range to
        if range_data.get('to'):
            to_data = range_data['to']
            value = to_data.get('value', '')
            unit = to_data.get('unit', '')
            
            if value and unit:
                if value.startswith('-'):
                    val_num = value[1:]
                    parts.append(f"to {val_num} {unit}s ago")
                else:
                    parts.append(f"to {value} {unit}s")
            else:
                parts.append("to search date")
        
        return " ".join(parts) if parts else "Date range"
    
    def _format_range_emis_style(self, range_data, is_age=False, is_numeric=False):
        """Format range information in EMIS clinical style"""
        if not range_data:
            return None
        
        # Debug: Check what structure we're getting for numeric filters
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
        
        # Process range from
        if range_data.get('from'):
            from_data = range_data['from']
            operator = from_data.get('operator', 'GTEQ')
            value = from_data.get('value', '')
            unit = from_data.get('unit', '')
            
            # Handle numeric values without units (common for NUMERIC_VALUE filters)
            if value and (unit or is_numeric):
                if value.startswith('-'):
                    # Past dates/ages
                    val_num = value[1:]
                    if is_age:
                        op_text = "greater than" if operator == "GT" else "greater than or equal to" if operator == "GTEQ" else "equal to"
                        return f"Age {op_text} {val_num} {unit.lower()}s"
                    elif unit and unit.upper() == 'YEAR':
                        date_op = "on or after" if operator == "GTEQ" else "after" if operator == "GT" else "on"
                        return f"Date is {date_op} {val_num} year{'s' if val_num != '1' else ''} before the search date"
                    elif unit and unit.upper() == 'MONTH':
                        date_op = "on or after" if operator == "GTEQ" else "after" if operator == "GT" else "on"
                        return f"Date is {date_op} {val_num} month{'s' if val_num != '1' else ''} before the search date"
                    elif unit and unit.upper() == 'DAY':
                        date_op = "on or after" if operator == "GTEQ" else "after" if operator == "GT" else "on"
                        return f"Date is {date_op} {val_num} day{'s' if val_num != '1' else ''} before the search date"
                else:
                    # Future dates or positive values
                    if is_numeric:
                        op_text = "greater than" if operator == "GT" else "greater than or equal to" if operator == "GTEQ" else "equal to"
                        return f"Value {op_text} {value}"
                    elif is_age:
                        op_text = "greater than" if operator == "GT" else "greater than or equal to" if operator == "GTEQ" else "equal to"
                        return f"Age {op_text} {value} {unit.lower()}s"
                    else:
                        # Check if this is a hardcoded date (contains slashes or dashes) vs relative offset
                        if '/' in value or '-' in value and not value.isdigit():
                            # Hardcoded date format
                            date_op = "on or after" if operator == "GTEQ" else "after" if operator == "GT" else "on"
                            return f"Date {date_op} {value} (Hardcoded Date)"
                        else:
                            # Relative date offset - handle zero case
                            if value == '0':
                                date_op = "on or after" if operator == "GTEQ" else "after" if operator == "GT" else "on"
                                return f"Date is {date_op} the search date"
                            else:
                                date_op = "on or after" if operator == "GTEQ" else "after" if operator == "GT" else "on"
                                return f"Date is {date_op} {value} {unit.lower()}s from the search date"
        
        # Process range to
        if range_data.get('to'):
            to_data = range_data['to']
            operator = to_data.get('operator', 'LTEQ')
            value = to_data.get('value', '')
            unit = to_data.get('unit', '')
            
            # Handle numeric values without units (common for NUMERIC_VALUE filters)
            if value and (unit or is_numeric):
                if value.startswith('-'):
                    val_num = value[1:]
                    if is_age:
                        op_text = "less than" if operator == "LT" else "less than or equal to" if operator == "LTEQ" else "equal to"
                        return f"Age {op_text} {val_num} {unit.lower()}s"
                    elif unit and unit.upper() == 'YEAR':
                        date_op = "on or before" if operator == "LTEQ" else "before" if operator == "LT" else "on"
                        return f"Date is {date_op} {val_num} year{'s' if val_num != '1' else ''} before the search date"
                    else:
                        date_op = "on or before" if operator == "LTEQ" else "before" if operator == "LT" else "on"
                        return f"Date is {date_op} {val_num} {unit.lower()}{'s' if val_num != '1' else ''} before the search date"
                else:
                    if is_numeric:
                        op_text = "less than" if operator == "LT" else "less than or equal to" if operator == "LTEQ" else "equal to"
                        return f"Value {op_text} {value}"
                    elif is_age:
                        op_text = "less than" if operator == "LT" else "less than or equal to" if operator == "LTEQ" else "equal to"
                        return f"Age {op_text} {value} {unit.lower()}s"
                    else:
                        # Check if this is a hardcoded date (contains slashes or dashes) vs relative offset
                        if '/' in value or '-' in value and not value.isdigit():
                            # Hardcoded date format
                            date_op = "on or before" if operator == "LTEQ" else "before" if operator == "LT" else "on"
                            return f"Date {date_op} {value} (Hardcoded Date)"
                        else:
                            # Relative date offset - handle zero case
                            if value == '0':
                                date_op = "on or before" if operator == "LTEQ" else "before" if operator == "LT" else "on"
                                return f"Date is {date_op} the search date"
                            else:
                                date_op = "on or before" if operator == "LTEQ" else "before" if operator == "LT" else "on"
                                return f"Date is {date_op} {value} {unit.lower()}s from the search date"
            else:
                # Empty value for "up to baseline"
                return "Date is before the search date"
        
        # If we reach here, the range structure wasn't processed successfully
        if is_numeric:
            return "Numeric value range filter"
        else:
            return "Date/value range filter applied"
    
    def _generate_main_filter_summaries(self, main_filters):
        """Generate main filter summaries matching UI aggregated view"""
        summaries = []
        
        # Group filters by column type to generate aggregated summaries
        filter_groups = {}
        for cf in main_filters:
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
                column_upper_list = [col.upper() for col in column]
                column_display = " + ".join(column)
            else:
                column_upper_list = [column.upper()]
                column_display = column
            
            # Get all value sets from all filters in this group
            all_value_sets = []
            for filter_item in filters:
                all_value_sets.extend(filter_item.get('value_sets', []))
            
            # Separate EMISINTERNAL from clinical value sets for main summary
            clinical_value_sets = [vs for vs in all_value_sets if vs.get('code_system') != 'EMISINTERNAL']
            emisinternal_value_sets = [vs for vs in all_value_sets if vs.get('code_system') == 'EMISINTERNAL']
            
            # Generate main filter summary based on column type
            if any(col in ['READCODE', 'SNOMEDCODE'] for col in column_upper_list):
                total_clinical_codes = sum(len(vs.get('values', [])) for vs in clinical_value_sets)
                if total_clinical_codes > 0:
                    summaries.append(f"Include {total_clinical_codes} specified clinical codes")
                else:
                    summaries.append("Include specified clinical codes")
                    
            elif any(col in ['DRUGCODE'] for col in column_upper_list):
                total_medication_codes = sum(len(vs.get('values', [])) for vs in clinical_value_sets)
                if total_medication_codes > 0:
                    summaries.append(f"Include {total_medication_codes} specified medication codes")
                else:
                    summaries.append("Include specified medication codes")
                    
            elif any(col in ['DATE', 'ISSUE_DATE', 'AGE'] for col in column_upper_list):
                # For date/age filters, use the specific range description
                range_info = filters[0].get('range')
                if range_info:
                    is_age = any(col == 'AGE' for col in column_upper_list)
                    range_desc = self._format_range_emis_style(range_info, is_age=is_age)
                    if range_desc:
                        # Customize the prefix for specific column types
                        if any(col == 'ISSUE_DATE' for col in column_upper_list):
                            if range_desc.startswith('Date '):
                                range_desc = range_desc.replace('Date ', 'Date of Issue ', 1)
                        summaries.append(range_desc)
                    else:
                        summaries.append(f"{column_display} filtering")
                else:
                    generic_desc = {
                        'DATE': 'Date filtering',
                        'ISSUE_DATE': 'Issue date filtering', 
                        'AGE': 'Patient age filtering'
                    }.get(column_upper_list[0], f'{column_display} filtering')
                    summaries.append(generic_desc)
                    
            elif any(col == 'NUMERIC_VALUE' for col in column_upper_list):
                # For NUMERIC_VALUE filters, use the specific range description
                range_info = filters[0].get('range')
                if range_info:
                    range_desc = self._format_range_emis_style(range_info, is_numeric=True)
                    if range_desc:
                        summaries.append(range_desc)
                    else:
                        summaries.append("Numeric value range filter")
                else:
                    summaries.append("Numeric value range filter")
                    
            elif any('LOWER_AREA' in col for col in column_upper_list):
                # For patient demographics filtering columns (LSOA codes)
                # Check both value_sets and grouped demographic values
                total_areas = sum(len(vs.get('values', [])) for vs in all_value_sets)
                
                # Also check for grouped demographics values (from analyzer)
                grouped_demographics = []
                for filter_item in filters:
                    grouped_demographics.extend(filter_item.get('grouped_demographics_values', []))
                
                if grouped_demographics:
                    total_areas = len(grouped_demographics)
                
                if total_areas > 0:
                    # Determine the year from column name for context
                    year_match = None
                    for col in column_upper_list:
                        if '2011' in col:
                            year_match = '2011'
                        elif '2015' in col:
                            year_match = '2015'
                        elif '2021' in col:
                            year_match = '2021'
                        elif '2031' in col:
                            year_match = '2031'
                        break
                    
                    year_text = f" ({year_match} boundaries)" if year_match else ""
                    summaries.append(f"Include {total_areas} Lower Layer Super Output Areas{year_text}")
                else:
                    summaries.append("Include specified patient demographic areas (LSOA)")
                    
            elif emisinternal_value_sets:
                # For EMISINTERNAL columns, show aggregated summary
                total_internal_values = sum(len(vs.get('values', [])) for vs in emisinternal_value_sets)
                
                # Special handling for known EMISINTERNAL column types
                column_name = column_upper_list[0] if column_upper_list else ''
                if column_name == 'ISSUE_METHOD':
                    if total_internal_values > 0:
                        summaries.append(f"Include {total_internal_values} specified issue methods")
                    else:
                        summaries.append("Include specified issue methods")
                elif column_name == 'IS_PRIVATE':
                    # Check if this is for private or NHS prescriptions
                    is_private_filter = any(
                        any(v.get('value', '').lower() == 'true' for v in vs.get('values', []))
                        for vs in emisinternal_value_sets
                    )
                    if is_private_filter:
                        summaries.append("Include privately prescribed")
                    else:
                        summaries.append("Include privately prescribed")
                else:
                    summaries.append(f"Include internal classification: {column_display}")
            else:
                # Fallback for other column types
                summaries.append(f"{column_display} filter applied")
        
        return summaries
    
    def _generate_additional_filter_details(self, main_filters):
        """Generate detailed breakdown of EMISINTERNAL and patient demographics filters matching UI Additional Filters section"""
        details = []
        
        # Collect all relevant value sets from all filters (EMISINTERNAL + patient demographics)
        filter_data = []
        for cf in main_filters:
            column = cf.get('column', '')
            column_name = column.upper() if isinstance(column, str) else column[0].upper() if column else ''
            in_not_in = cf.get('in_not_in', 'IN')
            column_display_name = cf.get('display_name', '').lower()
            
            value_sets = cf.get('value_sets', [])
            for vs in value_sets:
                # Include EMISINTERNAL and patient demographics filters
                if vs.get('code_system') == 'EMISINTERNAL' or 'LOWER_AREA' in column_name:
                    for value in vs.get('values', []):
                        filter_data.append({
                            'column_name': column_name,
                            'column_display_name': column_display_name,
                            'in_not_in': in_not_in,
                            'value': value,
                            'vs_description': vs.get('description', ''),
                            'code_system': vs.get('code_system', ''),
                            'is_patient_demographics': 'LOWER_AREA' in column_name
                        })
            
            # Also handle grouped patient demographics values (from analyzer)
            if 'LOWER_AREA' in column_name:
                grouped_demographics = cf.get('grouped_demographics_values', [])
                for area_code in grouped_demographics:
                    filter_data.append({
                        'column_name': column_name,
                        'column_display_name': column_display_name,
                        'in_not_in': in_not_in,
                        'value': {'value': area_code, 'display_name': area_code},
                        'vs_description': '',
                        'code_system': '',
                        'is_patient_demographics': True
                    })
        
        # Generate individual filter descriptions
        for item in filter_data:
            display_name = item['value'].get('display_name', '')
            code_value = item['value'].get('value', '')
            column_name = item['column_name']
            column_display_name = item['column_display_name']
            in_not_in = item['in_not_in']
            
            # Determine action based on in_not_in value
            action = "Include" if in_not_in == "IN" else "Exclude"
            
            # Handle patient demographics filters (LSOA codes) with EMIS-style phrasing
            if item.get('is_patient_demographics', False):
                # Extract year from column name
                year_match = None
                if '2011' in column_name:
                    year_match = '2011'
                elif '2015' in column_name:
                    year_match = '2015'
                elif '2021' in column_name:
                    year_match = '2021'
                elif '2031' in column_name:
                    year_match = '2031'
                
                year_text = f" ({year_match})" if year_match else ""
                # Simplified EMIS phrasing: "Include Patients where the Lower Layer Area (2011) is: E01012571"
                details.append(f"{action} Patients where the Lower Layer Area{year_text} is: {code_value}")
                continue
            
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
                context = column_display_name if column_display_name else "internal classification"
            
            # Generate description matching UI format
            if display_name and display_name.strip():
                if column_name == 'ISSUE_METHOD':
                    details.append(f"{action} {context}: {display_name}")
                elif code_value.upper() == 'PROBLEM' and 'consultation' in context:
                    details.append(f"{action} consultations where the consultation heading is: {display_name}")
                elif code_value.upper() in ['COMPLICATION', 'ONGOING', 'RESOLVED']:
                    status_descriptions = {
                        'COMPLICATION': f"{action} complications only: {display_name}",
                        'ONGOING': f"{action} ongoing conditions: {display_name}",
                        'RESOLVED': f"{action} resolved conditions: {display_name}"
                    }
                    details.append(status_descriptions.get(code_value.upper(), f'{action} {context}: {display_name}'))
                else:
                    details.append(f"{action} {context}: {display_name}")
            elif code_value:
                details.append(f"{action} internal code: {code_value}")
            else:
                details.append(f"{action} EMIS internal classification")
        
        return details
    
    def _render_column_filter_for_export(self, column_filter):
        """Mirror the UI search visualizer column filter logic for all exports (Excel and JSON)"""
        if not column_filter:
            return "No filter"
        
        column = column_filter.get('column', 'Unknown')
        
        # Handle both single column (string) and multiple columns (list)
        if isinstance(column, list):
            column_display = " + ".join(column)
            column_check = [col.upper() for col in column]
        else:
            column_display = column
            column_check = [column.upper()]
        
        in_not_in = column_filter.get('in_not_in', 'IN')
        range_info = column_filter.get('range')
        display_name = column_filter.get('display_name', column_display)
        value_sets = column_filter.get('value_sets', [])
        
        # Separate EMISINTERNAL from clinical value sets
        clinical_value_sets = [vs for vs in value_sets if vs.get('code_system') != 'EMISINTERNAL']
        emisinternal_value_sets = [vs for vs in value_sets if vs.get('code_system') == 'EMISINTERNAL']
        
        # Mirror the UI logic exactly
        if any(col in ['READCODE', 'SNOMEDCODE'] for col in column_check):
            total_clinical_codes = sum(len(vs.get('values', [])) for vs in clinical_value_sets)
            if total_clinical_codes > 0:
                return f"Include {total_clinical_codes} specified clinical codes"
            else:
                return "Include specified clinical codes"
                
        elif any(col in ['DRUGCODE'] for col in column_check):
            total_medication_codes = sum(len(vs.get('values', [])) for vs in clinical_value_sets)
            if total_medication_codes > 0:
                return f"Include {total_medication_codes} specified medication codes"
            else:
                return "Include specified medication codes"
                
        elif any(col == 'NUMERIC_VALUE' for col in column_check):
            if range_info:
                range_desc = self._format_range_emis_style(range_info, is_numeric=True)
                return range_desc if range_desc else "Numeric value range filter"
            else:
                return "Numeric value range filter"
                
        elif any(col in ['DATE', 'ISSUE_DATE', 'AGE'] for col in column_check):
            if range_info:
                is_age = any(col == 'AGE' for col in column_check)
                range_desc = self._format_range_emis_style(range_info, is_age=is_age)
                if range_desc:
                    # Customize the prefix for specific column types
                    if any(col == 'ISSUE_DATE' for col in column_check):
                        # Replace "Date" with "Date of Issue" for issue date columns
                        if range_desc.startswith('Date '):
                            range_desc = range_desc.replace('Date ', 'Date of Issue ', 1)
                    return range_desc
                else:
                    return f"{display_name} filtering"
            else:
                generic_desc = {
                    'DATE': 'Date filtering',
                    'ISSUE_DATE': 'Issue date filtering', 
                    'AGE': 'Patient age filtering'
                }.get(column_check[0], f'{column_display} filtering')
                return generic_desc
                
        elif any(col in ['AUTHOR', 'CURRENTLY_CONTRACTED'] for col in column_check):
            return "User authorization: Active users only"
            
        elif column_filter.get('column_type') == 'patient_demographics':
            # Patient demographics filters (LSOA codes, etc.)
            action = "Include patients in" if in_not_in == "IN" else "Exclude patients in"
            demographics_type = column_filter.get('demographics_type', 'LSOA')
            grouped_values = column_filter.get('grouped_demographics_values', [])
            demographics_count = column_filter.get('demographics_count', 0)
            
            if grouped_values and demographics_count > 1:
                if demographics_count <= 5:
                    # Show all codes if 5 or fewer
                    area_list = ", ".join(grouped_values)
                    return f"{action} {demographics_type} areas: {area_list}"
                else:
                    # Show summary with count
                    return f"{action} {demographics_count} {demographics_type} areas"
            else:
                # Single demographics code
                if range_info:
                    from_data = range_info.get('from', {})
                    value = from_data.get('value')
                    if value:
                        return f"{action} {demographics_type} area: {value}"
                return f"{action} specific {demographics_type} areas"
            
        else:
            # Check for EMISINTERNAL filters and use enhanced context
            if emisinternal_value_sets:
                return self._get_emisinternal_context(column_filter)
            
            # Default fallback using display name
            return f"{display_name} filter applied"
    
    def _generate_list_report_export(self, list_report, include_parent_info=True):
        """Generate export for List Report type"""
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Overview sheet
            overview_data = [
                ['Report Type', 'List Report'],
                ['Report Name', list_report.name],
                ['Description', list_report.description or 'N/A'],
                ['Parent Type', list_report.parent_type or 'N/A'],
                ['Search Date', list_report.search_date],
                ['Export Date', datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            ]
            
            if include_parent_info and list_report.direct_dependencies:
                overview_data.extend([
                    ['', ''],
                    ['Parent Dependencies', ''],
                    ['Referenced Search IDs', ', '.join(list_report.direct_dependencies)]
                ])
            
            overview_df = pd.DataFrame(overview_data, columns=['Property', 'Value'])
            overview_df_safe = sanitize_dataframe_for_excel(overview_df)
            overview_df_safe.to_excel(writer, sheet_name='Overview', index=False)
            
            # Column groups sheet
            if list_report.column_groups:
                columns_data = []
                for group in list_report.column_groups:
                    group_info = {
                        'Group ID': group.get('id', ''),
                        'Logical Table': group.get('logical_table', ''),
                        'Display Name': group.get('display_name', ''),
                        'Has Criteria': group.get('has_criteria', False),
                        'Column Count': len(group.get('columns', []))
                    }
                    columns_data.append(group_info)
                    
                    # Add individual columns
                    for col in group.get('columns', []):
                        col_info = {
                            'Group ID': f"  └─ {col.get('id', '')}",
                            'Logical Table': col.get('column', ''),
                            'Display Name': col.get('display_name', ''),
                            'Has Criteria': '',
                            'Column Count': ''
                        }
                        columns_data.append(col_info)
                
                columns_df = pd.DataFrame(columns_data)
                columns_df_safe = sanitize_dataframe_for_excel(columns_df)
                columns_df_safe.to_excel(writer, sheet_name='Column_Structure', index=False)
        
        output.seek(0)
        
        # Generate filename
        clean_name = SearchManager.clean_search_name(list_report.name)
        safe_name = "".join(c for c in clean_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"ListReport_{safe_name}_{timestamp}.xlsx"
        
        return filename, output.getvalue()
    
    def _generate_audit_report_export(self, audit_report, include_parent_info=True):
        """Generate export for Audit Report type"""
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Overview sheet
            overview_data = [
                ['Report Type', 'Audit Report'],
                ['Report Name', audit_report.name],
                ['Description', audit_report.description or 'N/A'],
                ['Parent Type', audit_report.parent_type or 'N/A'],
                ['Search Date', audit_report.search_date],
                ['Export Date', datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            ]
            
            if include_parent_info and audit_report.direct_dependencies:
                overview_data.extend([
                    ['', ''],
                    ['Population References', ''],
                    ['Referenced Population IDs', ', '.join(audit_report.direct_dependencies)]
                ])
            
            overview_df = pd.DataFrame(overview_data, columns=['Property', 'Value'])
            overview_df_safe = sanitize_dataframe_for_excel(overview_df)
            overview_df_safe.to_excel(writer, sheet_name='Overview', index=False)
            
            # Aggregation logic sheet
            if audit_report.custom_aggregate:
                agg = audit_report.custom_aggregate
                agg_data = [
                    ['Logical Table', agg.get('logical_table', '')],
                    ['Result Source', agg.get('result', {}).get('source', '')],
                    ['Calculation Type', agg.get('result', {}).get('calculation_type', '')],
                    ['Population Reference', agg.get('population_reference', '')]
                ]
                
                # Add grouping information
                groups = agg.get('groups', [])
                if groups:
                    agg_data.extend([['', ''], ['Grouping Configuration', '']])
                    for i, group in enumerate(groups, 1):
                        agg_data.extend([
                            [f'Group {i} ID', group.get('id', '')],
                            [f'Group {i} Display Name', group.get('display_name', '')],
                            [f'Group {i} Grouping Column', group.get('grouping_column', '')],
                            [f'Group {i} Sub Totals', str(group.get('sub_totals', False))],
                            [f'Group {i} Repeat Header', str(group.get('repeat_header', False))]
                        ])
                
                agg_df = pd.DataFrame(agg_data, columns=['Property', 'Value'])
                agg_df_safe = sanitize_dataframe_for_excel(agg_df)
                agg_df_safe.to_excel(writer, sheet_name='Aggregation_Logic', index=False)
        
        output.seek(0)
        
        # Generate filename
        clean_name = SearchManager.clean_search_name(audit_report.name)
        safe_name = "".join(c for c in clean_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"AuditReport_{safe_name}_{timestamp}.xlsx"
        
        return filename, output.getvalue()
    
    def _generate_aggregate_report_export(self, aggregate_report, include_parent_info=True):
        """Generate export for Aggregate Report type"""
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Overview sheet
            overview_data = [
                ['Report Type', 'Aggregate Report'],
                ['Report Name', aggregate_report.name],
                ['Description', aggregate_report.description or 'N/A'],
                ['Parent Type', aggregate_report.parent_type or 'N/A'],
                ['Search Date', aggregate_report.search_date],
                ['Export Date', datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            ]
            
            overview_df = pd.DataFrame(overview_data, columns=['Property', 'Value'])
            overview_df_safe = sanitize_dataframe_for_excel(overview_df)
            overview_df_safe.to_excel(writer, sheet_name='Overview', index=False)
            
            # Aggregate groups sheet
            if aggregate_report.aggregate_groups:
                groups_data = []
                for group in aggregate_report.aggregate_groups:
                    group_info = {
                        'Group ID': group.get('id', ''),
                        'Display Name': group.get('display_name', ''),
                        'Grouping Columns': ', '.join(group.get('grouping_columns', [])),
                        'Sub Totals': str(group.get('sub_totals', False)),
                        'Repeat Header': str(group.get('repeat_header', False))
                    }
                    groups_data.append(group_info)
                
                groups_df = pd.DataFrame(groups_data)
                groups_df_safe = sanitize_dataframe_for_excel(groups_df)
                groups_df_safe.to_excel(writer, sheet_name='Aggregate_Groups', index=False)
            
            # Statistical configuration sheet
            if aggregate_report.statistical_groups:
                stats_data = []
                for stat in aggregate_report.statistical_groups:
                    stat_info = {
                        'Type': stat.get('type', ''),
                        'Group ID': stat.get('group_id', ''),
                        'Source': stat.get('source', ''),
                        'Calculation Type': stat.get('calculation_type', '')
                    }
                    stats_data.append(stat_info)
                
                stats_df = pd.DataFrame(stats_data)
                stats_df_safe = sanitize_dataframe_for_excel(stats_df)
                stats_df_safe.to_excel(writer, sheet_name='Statistical_Config', index=False)
            
            # Include criteria if present (aggregate reports can have their own criteria)
            if aggregate_report.criteria_groups:
                for i, group in enumerate(aggregate_report.criteria_groups, 1):
                    rule_df = self._create_rule_sheet(group, i)
                    rule_df_safe = sanitize_dataframe_for_excel(rule_df)
                    rule_df_safe.to_excel(writer, sheet_name=f'Criteria_Rule_{i}', index=False)
        
        output.seek(0)
        
        # Generate filename
        clean_name = SearchManager.clean_search_name(aggregate_report.name)
        safe_name = "".join(c for c in clean_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"AggregateReport_{safe_name}_{timestamp}.xlsx"
        
        return filename, output.getvalue()
