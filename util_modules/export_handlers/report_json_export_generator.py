"""
Report JSON Export Generator for EMIS Reports
Generates focused JSON exports for List, Audit, and Aggregate reports with complete structure.
Provides all clinical codes, filters, aggregations, and logic needed for programmatic recreation.
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from ..core import SearchManager


class ReportJSONExportGenerator:
    """Generates focused JSON exports for individual report recreation"""
    
    def __init__(self, analysis):
        self.analysis = analysis
    
    def generate_report_json(self, report, xml_filename: str) -> tuple[str, str]:
        """
        Generate focused JSON export for any report type
        
        Args:
            report: The specific report to export (List/Audit/Aggregate)
            xml_filename: Original XML filename for reference
            
        Returns:
            tuple: (filename, json_string)
        """
        
        # Route to appropriate export method based on report type
        if report.report_type == 'list':
            return self._generate_list_report_json(report, xml_filename)
        elif report.report_type == 'audit':
            return self._generate_audit_report_json(report, xml_filename)
        elif report.report_type == 'aggregate':
            return self._generate_aggregate_report_json(report, xml_filename)
        else:
            # Fallback to generic report export
            return self._generate_generic_report_json(report, xml_filename)
    
    def _generate_list_report_json(self, list_report, xml_filename: str) -> tuple[str, str]:
        """Generate focused JSON export for List Report"""
        
        # Build focused JSON structure for this list report only
        export_data = {
            "report_definition": self._build_report_definition(list_report, xml_filename, "list"),
            "column_structure": self._build_column_structure(list_report),
            "data_filtering": self._build_data_filtering_logic(list_report),
            "clinical_terminology": self._build_clinical_terminology(list_report),
            "dependencies": self._build_report_dependencies(list_report),
            "output_configuration": self._build_output_configuration(list_report)
        }
        
        # Generate focused filename
        clean_name = SearchManager.clean_search_name(list_report.name)
        safe_name = "".join(c for c in clean_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"ListReport_{safe_name}_structure_{timestamp}.json"
        
        # Format JSON with proper indentation
        json_string = json.dumps(export_data, indent=2, ensure_ascii=False)
        
        return filename, json_string
    
    def _generate_audit_report_json(self, audit_report, xml_filename: str) -> tuple[str, str]:
        """Generate focused JSON export for Audit Report"""
        
        # Build focused JSON structure for this audit report only
        export_data = {
            "report_definition": self._build_report_definition(audit_report, xml_filename, "audit"),
            "aggregation_logic": self._build_aggregation_logic(audit_report),
            "organizational_grouping": self._build_organizational_grouping(audit_report),
            "member_searches": self._build_member_searches(audit_report),
            "embedded_criteria": self._build_embedded_criteria_logic(audit_report),
            "clinical_terminology": self._build_clinical_terminology(audit_report),
            "dependencies": self._build_report_dependencies(audit_report),
            "output_configuration": self._build_audit_output_configuration(audit_report)
        }
        
        # Generate focused filename
        clean_name = SearchManager.clean_search_name(audit_report.name)
        safe_name = "".join(c for c in clean_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"AuditReport_{safe_name}_structure_{timestamp}.json"
        
        # Format JSON with proper indentation
        json_string = json.dumps(export_data, indent=2, ensure_ascii=False)
        
        return filename, json_string
    
    def _generate_aggregate_report_json(self, aggregate_report, xml_filename: str) -> tuple[str, str]:
        """Generate focused JSON export for Aggregate Report"""
        
        # Build focused JSON structure for this aggregate report only
        export_data = {
            "report_definition": self._build_report_definition(aggregate_report, xml_filename, "aggregate"),
            "cross_tabulation_structure": self._build_cross_tabulation_structure(aggregate_report),
            "statistical_configuration": self._build_statistical_configuration(aggregate_report),
            "aggregate_grouping": self._build_aggregate_grouping(aggregate_report),
            "builtin_filters": self._build_builtin_filters_logic(aggregate_report),
            "clinical_terminology": self._build_clinical_terminology(aggregate_report),
            "dependencies": self._build_report_dependencies(aggregate_report),
            "output_configuration": self._build_aggregate_output_configuration(aggregate_report)
        }
        
        # Generate focused filename
        clean_name = SearchManager.clean_search_name(aggregate_report.name)
        safe_name = "".join(c for c in clean_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"AggregateReport_{safe_name}_structure_{timestamp}.json"
        
        # Format JSON with proper indentation
        json_string = json.dumps(export_data, indent=2, ensure_ascii=False)
        
        return filename, json_string
    
    def _generate_generic_report_json(self, report, xml_filename: str) -> tuple[str, str]:
        """Generate generic JSON export for unknown report types"""
        
        export_data = {
            "report_definition": self._build_report_definition(report, xml_filename, "unknown"),
            "raw_structure": self._build_raw_structure(report),
            "clinical_terminology": self._build_clinical_terminology(report),
            "dependencies": self._build_report_dependencies(report)
        }
        
        # Generate focused filename
        clean_name = SearchManager.clean_search_name(report.name)
        safe_name = "".join(c for c in clean_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"GenericReport_{safe_name}_structure_{timestamp}.json"
        
        # Format JSON with proper indentation
        json_string = json.dumps(export_data, indent=2, ensure_ascii=False)
        
        return filename, json_string
    
    def _build_report_definition(self, report, xml_filename: str, report_type: str) -> Dict[str, Any]:
        """Build core report definition with essential metadata"""
        return {
            "report_name": report.name,
            "report_id": report.id,
            "report_type": report_type,
            "description": report.description or "",
            "logical_table": getattr(report, 'logical_table', 'Unknown'),
            "folder_location": report.folder_id or "Root",
            "parent_search": self._get_parent_info(report),
            "source_xml": xml_filename,
            "export_timestamp": datetime.now().isoformat(),
            "export_version": "1.0"
        }
    
    def _build_column_structure(self, list_report) -> List[Dict[str, Any]]:
        """Build complete column structure for List Reports"""
        columns = []
        
        # List Reports use column_groups, not individual columns
        if hasattr(list_report, 'column_groups') and list_report.column_groups:
            for group_number, column_group in enumerate(list_report.column_groups, 1):
                group_data = {
                    "group_number": group_number,
                    "group_name": column_group.get('display_name', f'Group_{group_number}'),
                    "logical_table": column_group.get('logical_table', 'Unknown'),
                    "has_criteria": column_group.get('has_criteria', False),
                    "columns": self._build_group_columns(column_group.get('columns', [])),
                    "criteria": self._build_column_group_criteria(column_group),
                    "clinical_codes": self._extract_clinical_codes_from_column_group(column_group)
                }
                columns.append(group_data)
        elif hasattr(list_report, 'columns') and list_report.columns:
            # Fallback to individual columns if no column_groups
            for col_number, column in enumerate(list_report.columns, 1):
                column_data = {
                    "column_number": col_number,
                    "column_name": column.get('name', f'Column_{col_number}'),
                    "display_name": column.get('display_name', column.get('name', 'Unknown')),
                    "data_source": column.get('source', 'Unknown'),
                    "calculation_type": column.get('calculation_type', 'Direct'),
                    "column_filters": self._build_column_filters(column.get('filters', [])),
                    "sorting": self._build_column_sorting(column),
                    "formatting": self._build_column_formatting(column)
                }
                columns.append(column_data)
        
        return columns
    
    def _build_data_filtering_logic(self, list_report) -> Dict[str, Any]:
        """Build data filtering logic for List Reports"""
        filtering = {
            "base_population": self._get_parent_info(list_report),
            "additional_filters": [],
            "record_limits": [],
            "date_constraints": []
        }
        
        # Extract filters from criteria groups if present
        if hasattr(list_report, 'criteria_groups') and list_report.criteria_groups:
            for group_number, group in enumerate(list_report.criteria_groups, 1):
                group_data = {
                    "group_number": group_number,
                    "logic_operator": group.member_operator,
                    "criteria": self._build_complete_criteria(group.criteria)
                }
                filtering["additional_filters"].append(group_data)
        
        # Extract record limits from column groups
        if hasattr(list_report, 'column_groups') and list_report.column_groups:
            for group in list_report.column_groups:
                if hasattr(group, 'criteria_details') and group.criteria_details:
                    criteria_list = group.criteria_details.get('criteria', [])
                    for criterion in criteria_list:
                        restrictions = criterion.get('restrictions', [])
                        for restriction in restrictions:
                            if restriction.get('record_count'):
                                limit_data = {
                                    "column_group": getattr(group, 'display_name', 'Unknown'),
                                    "limit_type": restriction.get('type', 'latest_records'),
                                    "record_count": restriction.get('record_count'),
                                    "direction": restriction.get('direction', 'DESC'),
                                    "ordering_column": restriction.get('ordering_column', 'DATE'),
                                    "description": restriction.get('description', '')
                                }
                                filtering["record_limits"].append(limit_data)
        
        return filtering
    
    def _build_aggregation_logic(self, audit_report) -> Dict[str, Any]:
        """Build aggregation logic for Audit Reports"""
        aggregation = {
            "aggregation_type": "organizational_summary",
            "grouping_fields": [],
            "calculated_metrics": [],
            "organizational_hierarchy": []
        }
        
        # Extract aggregation configuration
        if hasattr(audit_report, 'aggregate_groups') and audit_report.aggregate_groups:
            for group in audit_report.aggregate_groups:
                group_data = {
                    "group_name": group.get('group_name', 'Unknown'),
                    "group_type": group.get('type', 'Unknown'),
                    "calculation_type": group.get('calculation_type', 'COUNT'),
                    "source_field": group.get('source', 'Unknown')
                }
                aggregation["grouping_fields"].append(group_data)
        
        return aggregation
    
    def _build_organizational_grouping(self, audit_report) -> Dict[str, Any]:
        """Build organizational grouping structure for Audit Reports"""
        return {
            "primary_grouping": getattr(audit_report, 'primary_grouping', 'Practice'),
            "secondary_grouping": getattr(audit_report, 'secondary_grouping', None),
            "totals_included": getattr(audit_report, 'include_totals', True),
            "percentage_calculations": getattr(audit_report, 'include_percentages', True)
        }
    
    def _build_member_searches(self, audit_report) -> Dict[str, Any]:
        """Build member searches list for Audit Reports using same logic as UI"""
        member_data = {
            "total_count": 0,
            "search_list": []
        }
        
        try:
            import streamlit as st
            analysis = st.session_state.get('search_analysis')
            
            if analysis:
                # Use the exact same function as the UI
                member_search_names = self._get_member_search_names(audit_report, analysis)
                member_data["total_count"] = len(member_search_names)
                
                # Build the search list with both names and GUIDs
                if hasattr(audit_report, 'population_references') and audit_report.population_references:
                    for i, (pop_guid, search_name) in enumerate(zip(audit_report.population_references, member_search_names)):
                        search_data = {
                            "index": i,
                            "search_id": pop_guid,
                            "search_name": search_name
                        }
                        member_data["search_list"].append(search_data)
        except Exception:
            pass
        
        return member_data
    
    def _get_member_search_names(self, report, analysis):
        """Same logic as UI function"""
        if not hasattr(report, 'population_references') or not report.population_references:
            return []
        
        member_searches = []
        for pop_guid in report.population_references:
            # Find the search by GUID
            search_report = next((r for r in analysis.reports if r.id == pop_guid), None)
            if search_report:
                member_searches.append(search_report.name)
            else:
                member_searches.append(f"Search {pop_guid[:8]}...")  # Fallback to shortened GUID
        
        return member_searches
    
    def _get_grouping_columns_for_group(self, aggregate_report, group_id) -> List[str]:
        """Get grouping columns for a specific group ID from aggregate_groups"""
        if hasattr(aggregate_report, 'aggregate_groups') and aggregate_report.aggregate_groups:
            for group in aggregate_report.aggregate_groups:
                if group.get('id') == group_id:
                    return group.get('grouping_columns', [])
        return []
    
    def _build_embedded_criteria_logic(self, audit_report) -> List[Dict[str, Any]]:
        """Build embedded criteria logic for Audit Reports"""
        criteria = []
        
        if hasattr(audit_report, 'criteria_groups') and audit_report.criteria_groups:
            for group_number, group in enumerate(audit_report.criteria_groups, 1):
                group_data = {
                    "group_number": group_number,
                    "logic_operator": group.member_operator,
                    "if_conditions_met": group.action_if_true,
                    "if_conditions_not_met": group.action_if_false,
                    "criteria": self._build_complete_criteria(group.criteria)
                }
                criteria.append(group_data)
        
        return criteria
    
    def _build_cross_tabulation_structure(self, aggregate_report) -> Dict[str, Any]:
        """Build cross-tabulation structure for Aggregate Reports"""
        crosstab = {
            "row_grouping": [],
            "column_grouping": [],
            "value_calculations": [],
            "statistical_functions": []
        }
        
        # Use the same logic as UI to extract statistical setup
        if hasattr(aggregate_report, 'statistical_groups') and aggregate_report.statistical_groups:
            # Find groups by type (same as UI lines 1305-1307)
            rows_group = next((g for g in aggregate_report.statistical_groups if g.get('type') == 'rows'), None)
            cols_group = next((g for g in aggregate_report.statistical_groups if g.get('type') == 'columns'), None)
            result_group = next((g for g in aggregate_report.statistical_groups if g.get('type') == 'result'), None)
            
            # Build row grouping (same as UI line 1312)
            if rows_group:
                group_name = rows_group.get('group_name', f"Group {rows_group.get('group_id', 'Unknown')}")
                # Get actual field names from aggregate_groups
                field_names = self._get_grouping_columns_for_group(aggregate_report, rows_group.get('group_id'))
                crosstab["row_grouping"].append({
                    "field": field_names[0] if field_names else rows_group.get('source', 'Unknown'),
                    "group_name": group_name,
                    "group_id": rows_group.get('group_id', 'Unknown'),
                    "grouping_columns": field_names
                })
            
            # Build column grouping (same as UI line 1319)
            if cols_group:
                group_name = cols_group.get('group_name', f"Group {cols_group.get('group_id', 'Unknown')}")
                # Get actual field names from aggregate_groups
                field_names = self._get_grouping_columns_for_group(aggregate_report, cols_group.get('group_id'))
                crosstab["column_grouping"].append({
                    "field": field_names[0] if field_names else cols_group.get('source', 'Unknown'),
                    "group_name": group_name,
                    "group_id": cols_group.get('group_id', 'Unknown'),
                    "grouping_columns": field_names
                })
            
            # Build value calculations (same as UI lines 1325-1327)
            if result_group:
                calc_type = result_group.get('calculation_type', 'count')
                source = result_group.get('source', 'record')
                
                # Use same logic as UI to determine what we're counting (lines 1329-1357)
                count_of_what = "Records"  # Default
                if hasattr(aggregate_report, 'logical_table'):
                    logical_table = getattr(aggregate_report, 'logical_table', '')
                    if logical_table == 'EVENTS':
                        count_of_what = "Clinical Codes"
                    elif logical_table == 'MEDICATION_ISSUES':
                        count_of_what = "Medication Issues"
                    elif logical_table == 'MEDICATION_COURSES':
                        count_of_what = "Medication Courses"
                    elif logical_table == 'PATIENTS':
                        count_of_what = "Patients"
                    elif logical_table:
                        count_of_what = logical_table.replace('_', ' ').title()
                
                result_text = f"{calc_type.title()} of {count_of_what}"
                crosstab["value_calculations"].append({
                    "field": logical_table if hasattr(aggregate_report, 'logical_table') else source,
                    "calculation_type": calc_type,
                    "description": result_text
                })
        
        return crosstab
    
    def _build_statistical_configuration(self, aggregate_report) -> Dict[str, Any]:
        """Build statistical configuration for Aggregate Reports"""
        stats = {
            "statistical_tests": [],
            "confidence_intervals": getattr(aggregate_report, 'confidence_interval', False),
            "significance_testing": getattr(aggregate_report, 'significance_testing', False),
            "statistical_groups": []
        }
        
        if hasattr(aggregate_report, 'statistical_groups') and aggregate_report.statistical_groups:
            for stat_group in aggregate_report.statistical_groups:
                stats["statistical_groups"].append({
                    "group_name": stat_group.get('group_name', 'Unknown'),
                    "group_type": stat_group.get('type', 'Unknown'),
                    "calculation_type": stat_group.get('calculation_type', 'Unknown'),
                    "source": stat_group.get('source', 'Unknown')
                })
        
        return stats
    
    def _build_aggregate_grouping(self, aggregate_report) -> List[Dict[str, Any]]:
        """Build aggregate grouping using same data as UI"""
        groups = []
        
        # Use the same data source as UI: report.aggregate_groups
        if hasattr(aggregate_report, 'aggregate_groups') and aggregate_report.aggregate_groups:
            for group_number, group in enumerate(aggregate_report.aggregate_groups, 1):
                group_data = {
                    "group_number": group_number,
                    "group_name": group.get('display_name', f'Group {group_number}'),  # Same as UI
                    "grouping_columns": group.get('grouping_columns', []),  # Same as UI
                    "sub_totals": group.get('sub_totals', False),  # Same as UI
                    "repeat_header": group.get('repeat_header', False),  # Same as UI
                    "group_id": group.get('id', f'group_{group_number}')
                }
                groups.append(group_data)
        
        return groups
    
    def _build_builtin_filters_logic(self, aggregate_report) -> Dict[str, Any]:
        """Build built-in filters logic for Aggregate Reports"""
        filters = {
            "has_builtin_filters": False,
            "filter_criteria": []
        }
        
        if hasattr(aggregate_report, 'criteria_groups') and aggregate_report.criteria_groups:
            filters["has_builtin_filters"] = True
            
            for group_number, group in enumerate(aggregate_report.criteria_groups, 1):
                group_data = {
                    "group_number": group_number,
                    "logic_operator": group.member_operator,
                    "criteria": self._build_complete_criteria(group.criteria)
                }
                filters["filter_criteria"].append(group_data)
        
        return filters
    
    def _build_complete_criteria(self, criteria) -> List[Dict[str, Any]]:
        """Build complete criteria with all clinical codes and logic (shared across report types)"""
        criteria_list = []
        
        for criterion in criteria:
            criterion_data = {
                "criterion_id": criterion.id,
                "table": criterion.table,
                "display_name": criterion.display_name,
                "description": criterion.description or "",
                "negation": criterion.negation,
                "exception_code": criterion.exception_code,
                "clinical_codes": self._extract_clinical_codes_from_criterion(criterion),
                "column_filters": self._build_complete_column_filters(criterion.column_filters),
                "restrictions": self._build_complete_restrictions(criterion.restrictions),
                "linked_criteria": self._build_linked_criteria_details(criterion.linked_criteria)
            }
            criteria_list.append(criterion_data)
        
        return criteria_list
    
    def _extract_clinical_codes_from_criterion(self, criterion) -> List[Dict[str, Any]]:
        """Extract unique clinical codes with SNOMED translations from a criterion"""
        seen_codes = set()
        unique_codes = []
        
        # Extract from value sets
        for vs in criterion.value_sets:
            for value in vs.get('values', []):
                emis_code = value.get('value')
                if emis_code and emis_code not in seen_codes:
                    seen_codes.add(emis_code)
                    snomed_info = self._get_snomed_translation(emis_code)
                    
                    # Use the best available description: SNOMED description > original display_name > fallback
                    description = snomed_info.get('description', '').strip()
                    if not description:
                        description = value.get('display_name', '').strip()
                    if not description:
                        description = 'No description available'
                    
                    code_entry = {
                        "emis_guid": emis_code,
                        "snomed_code": snomed_info.get('snomed_code', 'Not found'),
                        "description": description,
                        "code_system": snomed_info.get('code_system', ''),
                        "is_medication": snomed_info.get('is_medication', False),
                        "is_refset": snomed_info.get('is_refset', False),
                        "include_children": value.get('include_children', False),
                        "source_context": vs.get('description', 'Value Set'),
                        "translation_status": snomed_info.get('status', 'unknown')
                    }
                    unique_codes.append(code_entry)
        
        # Extract from column filter value sets (only if not already seen)
        for col_filter in criterion.column_filters:
            for vs in col_filter.get('value_sets', []):
                for value in vs.get('values', []):
                    emis_code = value.get('value')
                    if emis_code and emis_code not in seen_codes:
                        seen_codes.add(emis_code)
                        snomed_info = self._get_snomed_translation(emis_code)
                        
                        # Use the best available description: SNOMED description > original display_name > fallback
                        description = snomed_info.get('description', '').strip()
                        if not description:
                            description = value.get('display_name', '').strip()
                        if not description:
                            description = 'No description available'
                        
                        code_entry = {
                            "emis_guid": emis_code,
                            "snomed_code": snomed_info.get('snomed_code', 'Not found'),
                            "description": description,
                            "code_system": snomed_info.get('code_system', ''),
                            "is_medication": snomed_info.get('is_medication', False),
                            "is_refset": snomed_info.get('is_refset', False),
                            "include_children": value.get('include_children', False),
                            "source_context": f"{col_filter.get('display_name', 'Column Filter')} ({col_filter.get('in_not_in', 'UNKNOWN')})",
                            "translation_status": snomed_info.get('status', 'unknown')
                        }
                        unique_codes.append(code_entry)
        
        return unique_codes
    
    def _build_complete_column_filters(self, column_filters) -> List[Dict[str, Any]]:
        """Build complete column filter logic (shared across report types)"""
        filters = []
        
        for col_filter in column_filters:
            filter_data = {
                "column": col_filter.get('column'),
                "display_name": col_filter.get('display_name'),
                "inclusion_logic": "INCLUDE" if col_filter.get('in_not_in') == "IN" else "EXCLUDE",
                "filter_constraints": self._build_filter_constraints_complete(col_filter)
            }
            filters.append(filter_data)
        
        return filters
    
    def _build_filter_constraints_complete(self, col_filter) -> Dict[str, Any]:
        """Build complete filter constraints with SQL-ready logic (shared with search export)"""
        constraints = {}
        column = col_filter.get('column', '')
        
        # Handle case where column might be a list
        if isinstance(column, list):
            column = ' + '.join(column) if column else ''
        
        column = column.upper()
        
        # Date/range constraints using the same format as search_export.py
        if col_filter.get('range'):
            range_info = col_filter['range']
            
            # Process range_from (typically GTEQ operators like age >=18)
            if range_info.get('from'):
                from_data = range_info['from']
                operator = from_data.get('operator', 'GTEQ')
                value = from_data.get('value', '')
                unit = from_data.get('unit', '')
                
                # Format human-readable constraint
                if column == 'AGE' and value:
                    op_text = "greater than or equal to" if operator == "GTEQ" else "greater than" if operator == "GT" else "equal to"
                    unit_text = "years" if unit.upper() == "YEAR" else unit.lower()
                    human_desc = f"Age {op_text} {value} {unit_text}"
                elif column == 'DATE' and value:
                    op_text = self._format_date_operator(operator, value, unit)
                    human_desc = f"Date {op_text}"
                else:
                    op_text = "greater than or equal to" if operator == "GTEQ" else "greater than" if operator == "GT" else "equal to"
                    human_desc = f"{op_text} {value} {unit}"
                
                constraints["range_filter"] = {
                    "type": "range_from",
                    "operator": operator,
                    "value": value,
                    "unit": unit,
                    "human_readable": human_desc,
                    "sql_ready": bool(operator and value)
                }
            
            # Process range_to (typically LTEQ operators)
            if range_info.get('to'):
                to_data = range_info['to']
                operator = to_data.get('operator', 'LTEQ')
                value = to_data.get('value', '')
                unit = to_data.get('unit', '')
                
                # Format human-readable constraint
                if column == 'AGE' and value:
                    op_text = "less than or equal to" if operator == "LTEQ" else "less than" if operator == "LT" else "equal to"
                    unit_text = "years" if unit.upper() == "YEAR" else unit.lower()
                    human_desc = f"Age {op_text} {value} {unit_text}"
                elif column == 'DATE' and value:
                    op_text = self._format_date_operator(operator, value, unit)
                    human_desc = f"Date {op_text}"
                else:
                    op_text = "less than or equal to" if operator == "LTEQ" else "less than" if operator == "LT" else "equal to"
                    human_desc = f"{op_text} {value} {unit}"
                
                constraints["range_filter_to"] = {
                    "type": "range_to",
                    "operator": operator,
                    "value": value,
                    "unit": unit,
                    "human_readable": human_desc,
                    "sql_ready": bool(operator and value)
                }
        
        # Runtime parameters
        if col_filter.get('parameter'):
            param_info = col_filter['parameter']
            constraints["parameter_filter"] = {
                "parameter_name": param_info.get('name', 'UNKNOWN_PARAMETER'),
                "global_scope": param_info.get('allow_global', False),
                "data_type": self._determine_parameter_type(col_filter.get('column')),
                "requires_user_input": True
            }
        
        # Value set constraints (for completeness, even though handled in clinical_codes)
        if col_filter.get('value_sets'):
            value_count = sum(len(vs.get('values', [])) for vs in col_filter['value_sets'])
            constraints["value_set_filter"] = {
                "total_values": value_count,
                "inclusion_logic": "INCLUDE" if col_filter.get('in_not_in') == "IN" else "EXCLUDE",
                "values_handled_in": "clinical_codes_section"
            }
        
        # Text/string constraints
        if col_filter.get('text_value'):
            constraints["text_filter"] = {
                "value": col_filter['text_value'],
                "comparison": col_filter.get('text_operator', 'EQUALS'),
                "case_sensitive": col_filter.get('case_sensitive', False)
            }
        
        # If no specific constraints found but we have basic column info
        if not constraints and col_filter.get('column'):
            constraints["basic_filter"] = {
                "filter_type": f"{column.lower()}_filter",
                "column": col_filter.get('column'),
                "display_name": col_filter.get('display_name', col_filter.get('column'))
            }
        
        return constraints
    
    def _build_complete_restrictions(self, restrictions) -> List[Dict[str, Any]]:
        """Build complete restriction logic (shared across report types)"""
        restriction_list = []
        
        for restriction in restrictions:
            restriction_data = {
                "restriction_type": getattr(restriction, 'type', getattr(restriction, 'restriction_type', 'unknown')),
                "count": getattr(restriction, 'record_count', getattr(restriction, 'count', None)),
                "time_constraint": {
                    "period": getattr(restriction, 'time_period', None),
                    "unit": getattr(restriction, 'time_unit', None)
                },
                "sort_order": getattr(restriction, 'direction', getattr(restriction, 'sort_order', 'DESC')),
                "conditional_where": self._build_where_conditions_complete(restriction),
                "sql_pattern": f"{getattr(restriction, 'type', 'unknown')} {getattr(restriction, 'record_count', getattr(restriction, 'count', ''))}"
            }
            restriction_list.append(restriction_data)
        
        return restriction_list
    
    def _build_complete_restrictions_from_dict(self, restrictions) -> List[Dict[str, Any]]:
        """Build complete restriction logic from dictionary format (for column group criteria)"""
        restriction_list = []
        
        for restriction in restrictions:
            # Handle dictionary format from column group criteria
            if isinstance(restriction, dict):
                restriction_data = {
                    "restriction_type": restriction.get('type', 'unknown'),
                    "count": restriction.get('record_count', None),
                    "time_constraint": {
                        "period": None,
                        "unit": None
                    },
                    "sort_order": restriction.get('direction', 'DESC'),
                    "ordering_column": restriction.get('ordering_column', 'DATE'),
                    "description": restriction.get('description', ''),
                    "sql_pattern": self._build_restriction_sql_pattern(restriction)
                }
                restriction_list.append(restriction_data)
            else:
                # Fallback to object format if needed
                restriction_data = {
                    "restriction_type": getattr(restriction, 'type', 'unknown'),
                    "count": getattr(restriction, 'record_count', None),
                    "time_constraint": {
                        "period": getattr(restriction, 'time_period', None),
                        "unit": getattr(restriction, 'time_unit', None)
                    },
                    "sort_order": getattr(restriction, 'direction', 'DESC'),
                    "ordering_column": getattr(restriction, 'ordering_column', 'DATE'),
                    "description": getattr(restriction, 'description', ''),
                    "sql_pattern": f"{getattr(restriction, 'type', 'unknown')} {getattr(restriction, 'record_count', '')}"
                }
                restriction_list.append(restriction_data)
        
        return restriction_list
    
    def _build_restriction_sql_pattern(self, restriction_dict) -> str:
        """Build SQL pattern string for restriction"""
        restriction_type = restriction_dict.get('type', 'unknown')
        record_count = restriction_dict.get('record_count', '')
        direction = restriction_dict.get('direction', 'DESC')
        ordering_column = restriction_dict.get('ordering_column', 'DATE')
        
        if restriction_type == 'latest_records' and record_count:
            if direction == 'DESC':
                return f"SELECT TOP {record_count} * ORDER BY {ordering_column} DESC"
            else:
                return f"SELECT TOP {record_count} * ORDER BY {ordering_column} ASC"
        
        return f"{restriction_type} {record_count}"
    
    def _build_where_conditions_complete(self, restriction) -> List[Dict[str, Any]]:
        """Build WHERE conditions for restrictions (shared across report types)"""
        conditions = []
        
        if hasattr(restriction, 'where_conditions'):
            for condition in restriction.where_conditions:
                condition_data = {
                    "column": condition.get('column'),
                    "operator": condition.get('operator'),
                    "value": condition.get('value'),
                    "negation": condition.get('negation', False),
                    "sql_clause": f"{condition.get('column')} {condition.get('operator')} {condition.get('value')}"
                }
                conditions.append(condition_data)
        
        return conditions
    
    def _build_linked_criteria_details(self, linked_criteria) -> List[Dict[str, Any]]:
        """Build linked criteria relationships (shared across report types)"""
        linked_list = []
        
        for linked in linked_criteria:
            linked_data = {
                "relationship_type": getattr(linked, 'relationship_type', 'cross_reference'),
                "target_table": linked.table,
                "target_display_name": linked.display_name,
                "temporal_constraint": getattr(linked, 'temporal_constraint', None),
                "clinical_codes": self._extract_clinical_codes_from_criterion(linked),
                "column_filters": self._build_complete_column_filters(linked.column_filters),
                "restrictions": self._build_complete_restrictions(linked.restrictions)
            }
            linked_list.append(linked_data)
        
        return linked_list
    
    def _build_column_filters(self, filters) -> List[Dict[str, Any]]:
        """Build column-specific filters for List Reports"""
        filter_list = []
        
        for col_filter in filters:
            filter_data = {
                "filter_type": col_filter.get('type', 'Unknown'),
                "column": col_filter.get('column'),
                "operator": col_filter.get('operator', 'EQUALS'),
                "values": col_filter.get('values', []),
                "constraints": self._build_filter_constraints_complete(col_filter)
            }
            filter_list.append(filter_data)
        
        return filter_list
    
    def _build_column_sorting(self, column) -> Dict[str, Any]:
        """Build column sorting configuration"""
        return {
            "sort_enabled": column.get('sortable', False),
            "sort_direction": column.get('sort_direction', 'ASC'),
            "sort_priority": column.get('sort_priority', None)
        }
    
    def _build_column_formatting(self, column) -> Dict[str, Any]:
        """Build column formatting configuration"""
        return {
            "format_type": column.get('format', 'TEXT'),
            "date_format": column.get('date_format', None),
            "numeric_precision": column.get('precision', None),
            "display_width": column.get('width', None)
        }
    
    def _build_group_columns(self, columns) -> List[Dict[str, Any]]:
        """Build columns within a column group for List Reports"""
        column_list = []
        
        for column in columns:
            column_data = {
                "column_name": column.get('column', 'Unknown'),
                "display_name": column.get('display_name', column.get('column', 'Unknown')),
                "source_field": column.get('source_field', column.get('column', 'Unknown'))
            }
            column_list.append(column_data)
        
        return column_list
    
    def _build_column_group_criteria(self, column_group) -> List[Dict[str, Any]]:
        """Build criteria for a column group in List Reports using the same path as UI"""
        criteria_list = []
        
        # Use the same data path as the UI: group.get('criteria_details')
        if column_group.get('has_criteria', False) and column_group.get('criteria_details'):
            criteria_details = column_group['criteria_details']
            criteria = criteria_details.get('criteria', [])
            
            for criterion in criteria:
                criterion_data = {
                    "criterion_id": criterion.get('id', 'unknown'),
                    "table": criterion.get('table', 'Unknown'),
                    "display_name": criterion.get('display_name', 'Unknown'),
                    "description": criterion.get('description', ''),
                    "negation": criterion.get('negation', False),
                    "exception_code": criterion.get('exception_code', None),
                    "clinical_codes": self._extract_clinical_codes_from_column_group_criterion(criterion),
                    "column_filters": self._build_complete_column_filters(criterion.get('column_filters', [])),
                    "restrictions": self._build_complete_restrictions_from_dict(criterion.get('restrictions', [])),
                    "linked_criteria": []  # Column group criteria typically don't have linked criteria
                }
                criteria_list.append(criterion_data)
        
        return criteria_list
    
    def _extract_clinical_codes_from_column_group(self, column_group) -> List[Dict[str, Any]]:
        """Extract clinical codes from a column group in List Reports using the same path as UI"""
        clinical_codes = []
        
        # Use the same data path as the UI: group.get('criteria_details')
        if column_group.get('has_criteria', False) and column_group.get('criteria_details'):
            criteria_details = column_group['criteria_details']
            criteria = criteria_details.get('criteria', [])
            
            for criterion in criteria:
                clinical_codes.extend(self._extract_clinical_codes_from_column_group_criterion(criterion))
        
        return clinical_codes
    
    def _extract_clinical_codes_from_column_group_criterion(self, criterion) -> List[Dict[str, Any]]:
        """Extract clinical codes from a column group criterion using the same path as UI"""
        clinical_codes = []
        
        # Use the same data path as UI: criterion.get('value_sets', [])
        value_sets = criterion.get('value_sets', [])
        
        for value_set in value_sets:
            # Use the same data path as UI: value_set.get('values', [])
            codes = value_set.get('values', [])
            
            for code in codes:
                emis_guid = code.get('value', '')
                if emis_guid:
                    snomed_info = self._get_snomed_translation(emis_guid)
                    
                    # Use the same description logic as UI
                    code_name = code.get('display_name', '')
                    is_refset = code.get('is_refset', False)
                    include_children = code.get('include_children', False)
                    
                    # Handle refsets the same way as UI
                    if is_refset:
                        if code_name.startswith('Refset: ') and '[' in code_name and ']' in code_name:
                            # Extract just the name part before the bracket
                            clean_name = code_name.replace('Refset: ', '').split('[')[0]
                            code_name = clean_name
                    
                    # Use the best available description: SNOMED description > original display_name > fallback
                    description = snomed_info.get('description', '').strip()
                    if not description:
                        description = code_name.strip()
                    if not description:
                        description = 'No description available'
                    
                    code_entry = {
                        "emis_guid": emis_guid,
                        "snomed_code": snomed_info.get('snomed_code', 'Not found'),
                        "description": description,
                        "code_system": snomed_info.get('code_system', ''),
                        "is_medication": snomed_info.get('is_medication', False),
                        "is_refset": is_refset,
                        "include_children": include_children,
                        "scope": "refset" if is_refset else ("plus_children" if include_children else "exact"),
                        "source_context": value_set.get('description', 'Value Set'),
                        "translation_status": snomed_info.get('status', 'unknown')
                    }
                    clinical_codes.append(code_entry)
        
        return clinical_codes
    
    def _build_clinical_terminology(self, report) -> Dict[str, Any]:
        """Build complete clinical terminology with SNOMED focus (shared across report types)"""
        # Get all unique codes from this report only
        all_codes = set()
        code_details = []
        
        # Extract from criteria groups if present (Audit/Aggregate reports)
        if hasattr(report, 'criteria_groups') and report.criteria_groups:
            for group in report.criteria_groups:
                for criterion in group.criteria:
                    # Extract from value sets
                    for vs in criterion.value_sets:
                        for value in vs.get('values', []):
                            emis_code = value.get('value')
                            if emis_code and emis_code not in all_codes:
                                all_codes.add(emis_code)
                                snomed_info = self._get_snomed_translation(emis_code)
                                
                                # Use the best available description: SNOMED description > original display_name > fallback
                                description = snomed_info.get('description', '').strip()
                                if not description:
                                    description = value.get('display_name', '').strip()
                                if not description:
                                    description = 'No description available'
                                
                                code_details.append({
                                    "emis_guid": emis_code,
                                    "snomed_code": snomed_info.get('snomed_code', 'Not found'),
                                    "preferred_term": description,
                                    "code_system": snomed_info.get('code_system', ''),
                                    "semantic_type": "medication" if snomed_info.get('is_medication') else "clinical_concept",
                                    "is_refset": snomed_info.get('is_refset', False),
                                    "include_descendants": value.get('include_children', False),
                                    "translation_quality": snomed_info.get('status', 'unknown')
                                })
                    
                    # Extract from column filters
                    for col_filter in criterion.column_filters:
                        for vs in col_filter.get('value_sets', []):
                            for value in vs.get('values', []):
                                emis_code = value.get('value')
                                if emis_code and emis_code not in all_codes:
                                    all_codes.add(emis_code)
                                    snomed_info = self._get_snomed_translation(emis_code)
                                    
                                    # Use the best available description: SNOMED description > original display_name > fallback
                                    description = snomed_info.get('description', '').strip()
                                    if not description:
                                        description = value.get('display_name', '').strip()
                                    if not description:
                                        description = 'No description available'
                                    
                                    code_details.append({
                                        "emis_guid": emis_code,
                                        "snomed_code": snomed_info.get('snomed_code', 'Not found'),
                                        "preferred_term": description,
                                        "code_system": snomed_info.get('code_system', ''),
                                        "semantic_type": "medication" if snomed_info.get('is_medication') else "clinical_concept",
                                        "is_refset": snomed_info.get('is_refset', False),
                                        "filter_context": col_filter.get('display_name', ''),
                                        "translation_quality": snomed_info.get('status', 'unknown')
                                    })
        
        # Extract from column groups if present (List reports) - use same path as UI
        if hasattr(report, 'column_groups') and report.column_groups:
            for column_group in report.column_groups:
                if column_group.get('has_criteria', False) and column_group.get('criteria_details'):
                    criteria_details = column_group['criteria_details']
                    criteria = criteria_details.get('criteria', [])
                    
                    for criterion in criteria:
                        value_sets = criterion.get('value_sets', [])
                        
                        for value_set in value_sets:
                            codes = value_set.get('values', [])
                            
                            for code in codes:
                                emis_code = code.get('value')
                                if emis_code and emis_code not in all_codes:
                                    all_codes.add(emis_code)
                                    snomed_info = self._get_snomed_translation(emis_code)
                                    
                                    # Use the same description logic as UI
                                    code_name = code.get('display_name', '')
                                    is_refset = code.get('is_refset', False)
                                    include_children = code.get('include_children', False)
                                    
                                    # Handle refsets the same way as UI
                                    if is_refset:
                                        if code_name.startswith('Refset: ') and '[' in code_name and ']' in code_name:
                                            clean_name = code_name.replace('Refset: ', '').split('[')[0]
                                            code_name = clean_name
                                    
                                    # Use the best available description: SNOMED description > original display_name > fallback
                                    description = snomed_info.get('description', '').strip()
                                    if not description:
                                        description = code_name.strip()
                                    if not description:
                                        description = 'No description available'
                                    
                                    code_details.append({
                                        "emis_guid": emis_code,
                                        "snomed_code": snomed_info.get('snomed_code', 'Not found'),
                                        "preferred_term": description,
                                        "code_system": snomed_info.get('code_system', ''),
                                        "semantic_type": "medication" if snomed_info.get('is_medication') else "clinical_concept",
                                        "is_refset": is_refset,
                                        "include_descendants": include_children,
                                        "column_group": column_group.get('display_name', 'Unknown Group'),
                                        "translation_quality": snomed_info.get('status', 'unknown')
                                    })
        
        return {
            "total_unique_codes": len(all_codes),
            "terminology_focus": "SNOMED_CT",
            "codes": sorted(code_details, key=lambda x: x['snomed_code'])
        }
    
    def _build_report_dependencies(self, report) -> Dict[str, Any]:
        """Build dependency information for this report only (shared across report types)"""
        dependencies = {
            "parent_search": None,
            "referenced_searches": []
        }
        
        # Parent search - use same logic as _get_parent_info
        parent_info = self._get_parent_info(report)
        if parent_info:
            dependencies["parent_search"] = parent_info
        
        # Referenced searches from population criteria or embedded rules
        if hasattr(report, 'criteria_groups') and report.criteria_groups:
            for group in report.criteria_groups:
                if hasattr(group, 'population_criteria') and group.population_criteria:
                    for pop_crit in group.population_criteria:
                        dependencies["referenced_searches"].append({
                            "search_id": pop_crit.report_guid,
                            "search_name": getattr(pop_crit, 'search_name', 'Unknown'),
                            "inclusion_type": getattr(pop_crit, 'inclusion_type', 'INCLUDE')
                        })
        
        return dependencies
    
    def _build_output_configuration(self, list_report) -> Dict[str, Any]:
        """Build output configuration for List Reports"""
        return {
            "output_type": "tabular_list",
            "row_level_data": True,
            "column_headers": True,
            "sorting_enabled": getattr(list_report, 'sorting_enabled', True),
            "filtering_enabled": getattr(list_report, 'filtering_enabled', True),
            "export_formats": ["Excel", "CSV", "JSON"],
            "max_records": getattr(list_report, 'max_records', None)
        }
    
    def _build_audit_output_configuration(self, audit_report) -> Dict[str, Any]:
        """Build output configuration for Audit Reports"""
        return {
            "output_type": "organizational_summary",
            "aggregated_data": True,
            "organizational_grouping": True,
            "totals_included": getattr(audit_report, 'include_totals', True),
            "percentages_included": getattr(audit_report, 'include_percentages', True),
            "export_formats": ["Excel", "JSON"],
            "drill_down_capability": getattr(audit_report, 'drill_down', False)
        }
    
    def _build_aggregate_output_configuration(self, aggregate_report) -> Dict[str, Any]:
        """Build output configuration for Aggregate Reports"""
        return {
            "output_type": "cross_tabulation",
            "statistical_analysis": True,
            "cross_tabulation": True,
            "statistical_tests": getattr(aggregate_report, 'statistical_tests', False),
            "confidence_intervals": getattr(aggregate_report, 'confidence_intervals', False),
            "export_formats": ["Excel", "JSON"],
            "chart_generation": getattr(aggregate_report, 'charts_enabled', False)
        }
    
    def _build_raw_structure(self, report) -> Dict[str, Any]:
        """Build raw structure for unknown report types"""
        structure = {
            "available_attributes": [],
            "detected_components": []
        }
        
        # List all available attributes
        for attr in dir(report):
            if not attr.startswith('_') and not callable(getattr(report, attr)):
                try:
                    value = getattr(report, attr)
                    structure["available_attributes"].append({
                        "attribute": attr,
                        "type": type(value).__name__,
                        "has_content": bool(value)
                    })
                except:
                    continue
        
        # Detect common components
        if hasattr(report, 'criteria_groups'):
            structure["detected_components"].append("criteria_groups")
        if hasattr(report, 'columns'):
            structure["detected_components"].append("column_definitions")
        if hasattr(report, 'aggregate_groups'):
            structure["detected_components"].append("aggregate_groups")
        if hasattr(report, 'statistical_groups'):
            structure["detected_components"].append("statistical_groups")
        
        return structure
    
    def _get_parent_info(self, report) -> Optional[Dict[str, Any]]:
        """Get parent search information using same logic as UI"""
        try:
            import streamlit as st
            analysis = st.session_state.get('search_analysis')
            
            if analysis:
                # Use the exact same function as the UI
                parent_name = self._get_parent_search_name(report, analysis)
                if parent_name:
                    # Get the parent GUID for the JSON
                    parent_guid = None
                    if hasattr(report, 'direct_dependencies') and report.direct_dependencies:
                        parent_guid = report.direct_dependencies[0]
                    elif hasattr(report, 'parent_guid') and report.parent_guid:
                        parent_guid = report.parent_guid
                    
                    return {
                        "search_id": parent_guid,
                        "search_name": parent_name
                    }
        except Exception:
            pass
        return None
    
    def _get_parent_search_name(self, report, analysis):
        """Same logic as UI function"""
        if hasattr(report, 'direct_dependencies') and report.direct_dependencies:
            parent_guid = report.direct_dependencies[0]  # First dependency is usually the parent
            # Find the parent report by GUID
            for parent_report in analysis.reports:
                if parent_report.id == parent_guid:
                    return parent_report.name
            return f"Search {parent_guid[:8]}..."  # Fallback to shortened GUID
        return None
    
    def _resolve_search_name_from_guid(self, search_guid: str) -> Optional[str]:
        """Resolve search name from GUID using session state analysis data (same logic as UI)"""
        try:
            import streamlit as st
            
            # Use the exact same pattern as the UI - get 'search_analysis' from session state
            analysis = st.session_state.get('search_analysis')
            if analysis and hasattr(analysis, 'reports'):
                for search_report in analysis.reports:
                    if search_report.id == search_guid:
                        return search_report.name
                        
        except Exception as e:
            # For debugging - this will show in the console if something goes wrong
            print(f"Debug: Failed to resolve search name for {search_guid}: {e}")
            pass
        return None
    
    def _get_snomed_translation(self, emis_code: str) -> Dict[str, Any]:
        """Get SNOMED translation from already processed clinical codes (shared with search export)"""
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
    
    def _format_date_operator(self, operator: str, value: str, unit: str) -> str:
        """Format date operator for human readable descriptions with EMIS terminology"""
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
        elif unit and unit.upper() in ['DAY', 'WEEK', 'MONTH', 'QUARTER', 'YEAR', 'FISCALYEAR']:
            if value.lower() == 'last':
                if unit.upper() == 'FISCALYEAR':
                    return "and the Date is last fiscal year"
                elif unit.upper() == 'QUARTER':
                    return "and the Date is last yearly quarter"
                else:
                    return f"and the Date is last {unit.lower()}"
            elif value.lower() == 'this':
                if unit.upper() == 'FISCALYEAR':
                    return "and the Date is this fiscal year"
                elif unit.upper() == 'QUARTER':
                    return "and the Date is this yearly quarter"
                else:
                    return f"and the Date is this {unit.lower()}"
            elif value.lower() == 'next':
                if unit.upper() == 'FISCALYEAR':
                    return "and the Date is next fiscal year"
                elif unit.upper() == 'QUARTER':
                    return "and the Date is next yearly quarter"
                else:
                    return f"and the Date is next {unit.lower()}"
            else:
                return f"and the Date is {value} {unit.lower()}"
        
        # Fallback for other date patterns
        if '/' in value:  # Absolute date like "23/06/2025"
            if operator == 'GTEQ':
                return f"and the Date is on or after {value}"
            elif operator == 'GT':
                return f"and the Date is after {value}"
            elif operator == 'LTEQ':
                return f"and the Date is on or before {value}"
            elif operator == 'LT':
                return f"and the Date is before {value}"
            else:
                return f"and the Date is on {value}"
        
        # Default fallback
        return f"and the Date is {op_text} {value} {unit.lower() if unit else 'date'}"
    
    def _determine_parameter_type(self, column: str) -> str:
        """Determine parameter data type for SQL recreation (shared with search export)"""
        if column and ('DATE' in column.upper() or 'DOB' in column.upper()):
            return 'date'
        elif column and ('AGE' in column.upper() or 'YEAR' in column.upper()):
            return 'numeric'
        else:
            return 'text'
