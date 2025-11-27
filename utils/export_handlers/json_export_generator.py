"""
JSON Export Generator for Rule Logic Browser
Generates focused JSON exports containing complete search logic for the selected search only.
Provides SNOMED codes (not EMIS codes) and everything needed for programmatic recreation.
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from ..core import SearchManager


class JSONExportGenerator:
    """Generates focused JSON exports for individual search recreation"""
    
    def __init__(self, analysis):
        self.analysis = analysis
    
    def generate_search_json(self, search_report, xml_filename: str) -> tuple[str, str]:
        """
        Generate focused JSON export for a single search
        
        Args:
            search_report: The specific SearchReport to export
            xml_filename: Original XML filename for reference
            
        Returns:
            tuple: (filename, json_string)
        """
        
        # Build focused JSON structure for this search only
        export_data = {
            "search_definition": self._build_search_definition(search_report, xml_filename),
            "rule_logic": self._build_complete_rule_logic(search_report),
            "clinical_terminology": self._build_clinical_terminology(search_report),
            "dependencies": self._build_search_dependencies(search_report)
        }
        
        # Generate focused filename
        clean_name = SearchManager.clean_search_name(search_report.name)
        safe_name = "".join(c for c in clean_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"{safe_name}_logic_{timestamp}.json"
        
        # Format JSON with proper indentation
        json_string = json.dumps(export_data, indent=2, ensure_ascii=False)
        
        return filename, json_string
    
    def generate_master_json(self, xml_filename: str, reports: list = None) -> tuple[str, str]:
        """
        Generate master JSON export containing ALL searches with folder structure
        
        Args:
            xml_filename: Original XML filename for reference
            reports: List of SearchReport objects (should be searches only)
            
        Returns:
            tuple: (filename, json_string)
        """
        
        # Build master JSON structure with ALL complete search data in folder hierarchy
        export_data = {
            "xml_source": xml_filename,
            "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "export_type": "Complete Master XML Search Logic Export",
            "description": "Contains ALL searches with complete rule logic, clinical terminology, and filter details organized by folder structure",
            "folder_structure": self._build_folder_hierarchy(reports),
            "statistics": self._build_export_statistics(reports)
        }
        
        # Generate master filename
        base_name = xml_filename.replace('.xml', '') if xml_filename.endswith('.xml') else xml_filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"{base_name}_master_export_{timestamp}.json"
        
        # Format JSON with proper indentation
        json_string = json.dumps(export_data, indent=2, ensure_ascii=False)
        
        return filename, json_string
    
    def _build_folder_hierarchy(self, reports: list = None) -> Dict[str, Any]:
        """Build the complete folder structure with nested searches"""
        # Use provided reports or try to get from analysis
        search_reports = reports
        if not search_reports:
            if hasattr(self.analysis, 'search_reports') and self.analysis.search_reports:
                search_reports = self.analysis.search_reports
            elif hasattr(self.analysis, 'searches') and self.analysis.searches:
                search_reports = self.analysis.searches
            elif hasattr(self.analysis, 'reports'):
                # Filter for only searches (not list reports or audit reports)
                search_reports = [r for r in self.analysis.reports if getattr(r, 'search_type', '') == 'Search']
        
        if not search_reports:
            return {}
        
        # Group searches by their folder paths
        folder_structure = {}
        
        for search_report in search_reports:
            folder_path = getattr(search_report, 'folder_path', '') or 'Root'
            
            # Handle folder_path being either string or list
            if isinstance(folder_path, list):
                folder_parts = [str(part).strip() for part in folder_path if str(part).strip()]
            elif isinstance(folder_path, str):
                folder_parts = [part.strip() for part in folder_path.split('/') if part.strip()]
            else:
                folder_parts = ['Root']
            
            # Navigate/create the folder structure
            current_level = folder_structure
            for part in folder_parts:
                if part not in current_level:
                    current_level[part] = {
                        "searches": [],
                        "subfolders": {}
                    }
                current_level = current_level[part]["subfolders"]
            
            # Add search to the appropriate folder
            final_folder = folder_structure
            for part in folder_parts[:-1] if folder_parts else []:
                final_folder = final_folder[part]["subfolders"]
            
            folder_name = folder_parts[-1] if folder_parts else "Root"
            if folder_name not in final_folder:
                final_folder[folder_name] = {
                    "searches": [],
                    "subfolders": {}
                }
            
            # Build COMPLETE search data - same as individual JSON exports
            search_data = {
                "search_definition": self._build_search_definition(search_report, ""),
                "rule_logic": self._build_complete_rule_logic(search_report),
                "clinical_terminology": self._build_clinical_terminology(search_report),
                "dependencies": self._build_search_dependencies(search_report)
            }
            
            final_folder[folder_name]["searches"].append(search_data)
        
        return folder_structure
    
    def _build_all_searches_list(self) -> List[Dict[str, Any]]:
        """Build a flat list of all searches for easy programmatic access"""
        # Get search reports from the analysis - try multiple possible attributes
        search_reports = None
        if hasattr(self.analysis, 'search_reports') and self.analysis.search_reports:
            search_reports = self.analysis.search_reports
        elif hasattr(self.analysis, 'searches') and self.analysis.searches:
            search_reports = self.analysis.searches
        elif hasattr(self.analysis, 'reports'):
            # Filter for only searches (not list reports or audit reports)
            search_reports = [r for r in self.analysis.reports if getattr(r, 'search_type', '') == 'Search']
        
        if not search_reports:
            return []
        
        # Remove the flat list since we have complete data in folder_structure
        # The folder_structure contains all the detailed search data organized properly
        return []
    
    def _build_global_dependencies(self) -> Dict[str, Any]:
        """Build global dependency mapping across all searches"""
        # Get search reports from the analysis - try multiple possible attributes
        search_reports = None
        if hasattr(self.analysis, 'search_reports') and self.analysis.search_reports:
            search_reports = self.analysis.search_reports
        elif hasattr(self.analysis, 'searches') and self.analysis.searches:
            search_reports = self.analysis.searches
        elif hasattr(self.analysis, 'reports'):
            # Filter for only searches (not list reports or audit reports)
            search_reports = [r for r in self.analysis.reports if getattr(r, 'search_type', '') == 'Search']
        
        if not search_reports:
            return {}
        
        dependencies = {
            "dependency_map": {},
            "dependency_chains": [],
            "circular_dependencies": []
        }
        
        # Build complete dependency map
        for search_report in search_reports:
            search_deps = self._build_search_dependencies(search_report)
            if search_deps.get('references_other_searches'):
                dependencies["dependency_map"][search_report.id] = {
                    "search_name": search_report.name,
                    "references": search_deps.get('referenced_search_ids', [])
                }
        
        return dependencies
    
    def _build_export_statistics(self, reports: list = None) -> Dict[str, Any]:
        """Build statistics about the export"""
        # Use provided reports or try to get from analysis
        search_reports = reports
        if not search_reports:
            if hasattr(self.analysis, 'search_reports') and self.analysis.search_reports:
                search_reports = self.analysis.search_reports
            elif hasattr(self.analysis, 'searches') and self.analysis.searches:
                search_reports = self.analysis.searches
            elif hasattr(self.analysis, 'reports'):
                # Filter for only searches (not list reports or audit reports)
                search_reports = [r for r in self.analysis.reports if getattr(r, 'search_type', '') == 'Search']
        
        if not search_reports:
            return {}
        
        total_searches = len(search_reports)
        search_types = {}
        folder_counts = {}
        
        for search_report in search_reports:
            # Count by search type
            search_type = getattr(search_report, 'search_type', 'Search')
            search_types[search_type] = search_types.get(search_type, 0) + 1
            
            # Count by folder
            folder_path = getattr(search_report, 'folder_path', '') or 'Root'
            
            # Handle folder_path being either string or list
            if isinstance(folder_path, list):
                folder_path_str = '/'.join(str(part) for part in folder_path)
            elif isinstance(folder_path, str):
                folder_path_str = folder_path
            else:
                folder_path_str = 'Root'
                
            folder_counts[folder_path_str] = folder_counts.get(folder_path_str, 0) + 1
        
        return {
            "total_searches": total_searches,
            "search_types": search_types,
            "folder_distribution": folder_counts,
            "export_size_estimate": f"~{total_searches * 50}KB (estimated)"
        }
    
    def _build_search_definition(self, search_report, xml_filename: str) -> Dict[str, Any]:
        """Build core search definition with essential metadata only"""
        return {
            "search_name": search_report.name,
            "search_id": search_report.id,
            "description": search_report.description or "",
            "population_type": search_report.population_type,
            "folder_location": search_report.folder_id or "Root",
            "source_xml": xml_filename,
            "export_timestamp": datetime.now().isoformat(),
            "export_version": "1.0"
        }
    
    def _build_complete_rule_logic(self, search_report) -> List[Dict[str, Any]]:
        """Build complete rule structure with all logic components"""
        rules = []
        
        for rule_number, group in enumerate(search_report.criteria_groups, 1):
            rule_data = {
                "rule_number": rule_number,
                "logic_operator": group.member_operator,  # AND/OR
                "if_conditions_met": group.action_if_true,
                "if_conditions_not_met": group.action_if_false,
                "criteria": self._build_complete_criteria(group.criteria),
                "population_references": self._build_population_refs(group)
            }
            rules.append(rule_data)
        
        return rules
    
    def _build_complete_criteria(self, criteria) -> List[Dict[str, Any]]:
        """Build complete criteria with all SNOMED codes and logic"""
        criteria_list = []
        
        for criterion in criteria:
            # Apply minimal filtering - only separate linked criteria from main, preserve all semantic roles
            try:
                from ..analysis.linked_criteria_handler import filter_linked_column_filters_from_main, filter_linked_value_sets_from_main
                main_column_filters = filter_linked_column_filters_from_main(criterion)
                main_value_sets = filter_linked_value_sets_from_main(criterion)
            except ImportError:
                # Fallback if import fails
                main_column_filters = criterion.column_filters
                main_value_sets = criterion.value_sets
            
            criterion_data = {
                "criterion_id": criterion.id,
                "table": criterion.table,
                "display_name": criterion.display_name,
                "description": criterion.description or "",
                "negation": criterion.negation,
                "exception_code": criterion.exception_code,
                "clinical_codes": self._extract_clinical_codes_from_criterion_filtered(criterion, main_value_sets),
                "column_filters": self._build_complete_column_filters(main_column_filters),
                "restrictions": self._build_complete_restrictions(criterion.restrictions, criterion),
                "linked_criteria": self._build_linked_criteria_details(criterion.linked_criteria)
            }
            criteria_list.append(criterion_data)
        
        return criteria_list
    
    def _filter_restriction_value_sets(self, criterion, value_sets):
        """Filter out duplicate value sets that come from restriction testAttribute sections"""
        if not criterion.restrictions:
            return value_sets
        
        restriction_value_set_descriptions = set()
        
        # Collect descriptions of value sets used in restriction conditions 
        for restriction in criterion.restrictions:
            if hasattr(restriction, 'conditions') and restriction.conditions:
                for condition in restriction.conditions:
                    # Get value set descriptions from restriction conditions
                    if condition.get('value_sets'):
                        for desc in condition['value_sets']:
                            if desc and desc.strip():
                                restriction_value_set_descriptions.add(desc.strip())
        
        # Keep track of seen value sets by description to handle duplicates
        seen_descriptions = set()
        filtered_value_sets = []
        
        for vs in value_sets:
            vs_description = vs.get('description', '').strip()
            
            # If this value set is used in restrictions AND we've already seen this description,
            # it's likely a duplicate from testAttribute - skip it
            if (vs_description in restriction_value_set_descriptions and 
                vs_description in seen_descriptions):
                continue  # Skip this duplicate
            
            # Otherwise, include it and mark as seen
            filtered_value_sets.append(vs)
            if vs_description:
                seen_descriptions.add(vs_description)
        
        return filtered_value_sets
    
    def _filter_linked_criteria_value_sets(self, criterion, value_sets):
        """Filter out value sets that are used in linked criteria"""
        if not criterion.linked_criteria:
            return value_sets
        
        linked_value_set_ids = set()
        
        # Collect IDs of value sets used in linked criteria
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
        
        # Filter out linked value sets
        filtered_value_sets = []
        for vs in value_sets:
            is_linked_vs = (vs.get('id') in linked_value_set_ids or 
                           vs.get('description') in linked_value_set_ids)
            if not is_linked_vs:
                filtered_value_sets.append(vs)
        
        return filtered_value_sets
    
    def _extract_clinical_codes_from_criterion_filtered(self, criterion, filtered_value_sets) -> List[Dict[str, Any]]:
        """Extract clinical codes using pre-filtered value sets (same as UI logic)"""
        codes = []
        
        for vs in filtered_value_sets:
            # Skip EMISINTERNAL codes (they go in column_filters)
            if vs.get('code_system') == 'EMISINTERNAL':
                continue
                
            for value in vs.get('values', []):
                emis_code = value.get('value', '')
                if emis_code:
                    snomed_info = self._get_snomed_translation(emis_code)
                    
                    # Use the best available description: SNOMED description > original display_name > fallback
                    description = snomed_info.get('description', '').strip()
                    if not description:
                        description = value.get('display_name', '').strip()
                    
                    # For refsets, if no display_name, try to use value set description (e.g., "COPD_COD")
                    if not description and snomed_info.get('is_refset', False):
                        description = vs.get('description', '').strip()
                    
                    if not description:
                        description = 'No description available'
                    
                    code_entry = {
                        "emis_guid": emis_code,
                        "snomed_code": snomed_info.get('snomed_code', 'Not found'),
                        "description": description,
                        "code_system": vs.get('code_system', snomed_info.get('code_system', '')),
                        "is_medication": snomed_info.get('is_medication', False),
                        "is_refset": snomed_info.get('is_refset', False),
                        "is_linked_criteria": vs.get('is_linked_criteria', False),
                        "is_restriction": vs.get('is_restriction', False),
                        "include_children": value.get('include_children', False),
                        "source_context": value.get('display_name', vs.get('description', 'Value Set')),
                        "translation_status": snomed_info.get('status', 'unknown')
                    }
                    codes.append(code_entry)
        
        return codes
    
    def _extract_clinical_codes_from_criterion(self, criterion) -> List[Dict[str, Any]]:
        """Extract unique clinical codes with SNOMED translations from a criterion"""
        seen_codes = set()
        unique_codes = []
        
        # Extract from value sets - SKIP EMISINTERNAL codes (they're handled in filter_constraints)
        for vs in criterion.value_sets:
            # Skip EMISINTERNAL value sets - they're not clinical codes
            if vs.get('code_system') == 'EMISINTERNAL':
                continue
                
            for value in vs.get('values', []):
                emis_code = value.get('value')
                if emis_code and emis_code not in seen_codes:
                    seen_codes.add(emis_code)
                    snomed_info = self._get_snomed_translation(emis_code)
                    
                    # Use the best available description: SNOMED description > original display_name > fallback
                    description = snomed_info.get('description', '').strip()
                    if not description:
                        description = value.get('display_name', '').strip()
                    
                    # For refsets, if no display_name, try to use value set description (e.g., "COPD_COD")
                    if not description and snomed_info.get('is_refset', False):
                        description = vs.get('description', '').strip()
                    
                    if not description:
                        description = 'No description available'
                    
                    code_entry = {
                        "emis_guid": emis_code,
                        "snomed_code": snomed_info.get('snomed_code', 'Not found'),
                        "description": description,
                        "code_system": vs.get('code_system', snomed_info.get('code_system', '')),
                        "is_medication": snomed_info.get('is_medication', False),
                        "is_refset": snomed_info.get('is_refset', False),
                        "is_linked_criteria": vs.get('is_linked_criteria', False),
                        "is_restriction": vs.get('is_restriction', False),
                        "include_children": value.get('include_children', False),
                        "source_context": value.get('display_name', vs.get('description', 'Value Set')),
                        "translation_status": snomed_info.get('status', 'unknown')
                    }
                    unique_codes.append(code_entry)
        
        # Extract from column filter value sets (only if not already seen) - SKIP EMISINTERNAL
        for col_filter in criterion.column_filters:
            for vs in col_filter.get('value_sets', []):
                # Skip EMISINTERNAL value sets - they're handled in filter_constraints
                if vs.get('code_system') == 'EMISINTERNAL':
                    continue
                    
                for value in vs.get('values', []):
                    emis_code = value.get('value')
                    if emis_code and emis_code not in seen_codes:
                        seen_codes.add(emis_code)
                        snomed_info = self._get_snomed_translation(emis_code)
                        
                        # Use the best available description: SNOMED description > original display_name > fallback
                        description = snomed_info.get('description', '').strip()
                        if not description:
                            description = value.get('display_name', '').strip()
                        
                        # For refsets, if no display_name, try to use value set description (e.g., "COPD_COD")
                        if not description and snomed_info.get('is_refset', False):
                            description = vs.get('description', '').strip()
                            
                        if not description:
                            description = 'No description available'
                        
                        code_entry = {
                            "emis_guid": emis_code,
                            "snomed_code": snomed_info.get('snomed_code', 'Not found'),
                            "description": description,
                            "code_system": vs.get('code_system', snomed_info.get('code_system', '')),
                            "is_medication": snomed_info.get('is_medication', False),
                            "is_refset": snomed_info.get('is_refset', False),
                            "include_children": value.get('include_children', False),
                            "source_context": value.get('display_name', vs.get('description', col_filter.get('display_name', 'Column Filter'))),
                            "translation_status": snomed_info.get('status', 'unknown')
                        }
                        unique_codes.append(code_entry)
        
        return unique_codes
    
    def _build_complete_column_filters(self, column_filters) -> List[Dict[str, Any]]:
        """Build complete column filter logic"""
        filters = []
        
        for col_filter in column_filters:
            # Use the same human-readable logic as UI and Excel exports - inline the working logic
            column = col_filter.get('column', 'Unknown')
            if isinstance(column, list):
                column_display = " + ".join(column)
                column_check = [col.upper() for col in column]
            else:
                column_display = column
                column_check = [column.upper()]
            
            range_info = col_filter.get('range')
            value_sets = col_filter.get('value_sets', [])
            
            # Separate EMISINTERNAL from clinical value sets
            clinical_value_sets = [vs for vs in value_sets if vs.get('code_system') != 'EMISINTERNAL']
            emisinternal_value_sets = [vs for vs in value_sets if vs.get('code_system') == 'EMISINTERNAL']
            
            # Mirror the UI logic exactly
            if any(col in ['READCODE', 'SNOMEDCODE'] for col in column_check):
                total_clinical_codes = sum(len(vs.get('values', [])) for vs in clinical_value_sets)
                if total_clinical_codes > 0:
                    human_readable_description = f"Include {total_clinical_codes} specified clinical codes"
                else:
                    human_readable_description = "Include specified clinical codes"
            elif any(col in ['DRUGCODE'] for col in column_check):
                total_medication_codes = sum(len(vs.get('values', [])) for vs in clinical_value_sets)
                if total_medication_codes > 0:
                    human_readable_description = f"Include {total_medication_codes} specified medication codes"
                else:
                    human_readable_description = "Include specified medication codes"
            elif any(col in ['DATE', 'ISSUE_DATE', 'AGE'] for col in column_check):
                if range_info:
                    # Format range properly for dates/ages - handle both 'from' and 'to' ranges
                    from_data = range_info.get('from')
                    to_data = range_info.get('to')
                    
                    if from_data:
                        operator = from_data.get('operator', 'GTEQ')
                        value = from_data.get('value', '')
                        
                        if any(col == 'AGE' for col in column_check):
                            op_text = "greater than or equal to" if operator == "GTEQ" else "greater than" if operator == "GT" else "equal to"
                            human_readable_description = f"Age {op_text} {value} years"
                        elif '/' in value or '-' in value and not value.isdigit():
                            # Hardcoded date
                            date_op = "on or after" if operator == "GTEQ" else "after" if operator == "GT" else "on"
                            if any(col == 'ISSUE_DATE' for col in column_check):
                                human_readable_description = f"Date of Issue {date_op} {value} (Hardcoded Date)"
                            else:
                                human_readable_description = f"Date {date_op} {value} (Hardcoded Date)"
                        else:
                            # Relative date
                            date_op = "on or after" if operator == "GTEQ" else "after" if operator == "GT" else "on"
                            human_readable_description = f"Date is {date_op} {value} years from the search date"
                    
                    elif to_data:
                        operator = to_data.get('operator', 'LTEQ')
                        value = to_data.get('value', '')
                        
                        if any(col == 'AGE' for col in column_check):
                            op_text = "less than or equal to" if operator == "LTEQ" else "less than" if operator == "LT" else "equal to"
                            human_readable_description = f"Age {op_text} {value} years"
                        elif '/' in value or '-' in value and not value.isdigit():
                            # Hardcoded date
                            date_op = "on or before" if operator == "LTEQ" else "before" if operator == "LT" else "on"
                            if any(col == 'ISSUE_DATE' for col in column_check):
                                human_readable_description = f"Date of Issue {date_op} {value} (Hardcoded Date)"
                            else:
                                human_readable_description = f"Date {date_op} {value} (Hardcoded Date)"
                        else:
                            # Relative date
                            date_op = "on or before" if operator == "LTEQ" else "before" if operator == "LT" else "on"
                            human_readable_description = f"Date is {date_op} {value} years from the search date"
                    
                    else:
                        human_readable_description = f"{column_display} filtering"
                else:
                    human_readable_description = f"{column_display} filtering"
            elif col_filter.get('column_type') == 'patient_demographics':
                # Patient demographics filters (LSOA codes, etc.)
                action = "Include patients in" if col_filter.get('in_not_in') == "IN" else "Exclude patients in"
                demographics_type = col_filter.get('demographics_type', 'LSOA')
                grouped_values = col_filter.get('grouped_demographics_values', [])
                demographics_count = col_filter.get('demographics_count', 0)
                
                if grouped_values and demographics_count > 1:
                    human_readable_description = f"{action} {demographics_count} {demographics_type} areas"
                else:
                    # Single demographics code
                    range_info = col_filter.get('range', {})
                    from_data = range_info.get('from', {})
                    value = from_data.get('value')
                    if value:
                        human_readable_description = f"{action} {demographics_type} area: {value}"
                    else:
                        human_readable_description = f"{action} specific {demographics_type} areas"
            elif emisinternal_value_sets:
                # Handle EMISINTERNAL filters with enhanced context
                column_name = column_check[0] if column_check else ''
                if column_name == 'ISSUE_METHOD':
                    total_internal_values = sum(len(vs.get('values', [])) for vs in emisinternal_value_sets)
                    if total_internal_values > 0:
                        human_readable_description = f"Include {total_internal_values} specified issue methods"
                    else:
                        human_readable_description = "Include specified issue methods"
                elif column_name == 'IS_PRIVATE':
                    # Check the actual boolean value for private/NHS prescriptions
                    is_private_filter = any(
                        any(v.get('value', '').lower() == 'true' for v in vs.get('values', []))
                        for vs in emisinternal_value_sets
                    )
                    if is_private_filter:
                        human_readable_description = "Include privately prescribed: True"
                    else:
                        human_readable_description = "Include privately prescribed: False"
                else:
                    human_readable_description = f"Include internal classification: {column_display}"
            else:
                # Check for specific columns that might not have EMISINTERNAL value sets attached
                column_name = column_check[0] if column_check else ''
                if column_name == 'ISSUE_METHOD':
                    human_readable_description = "Include specific issue methods"
                elif column_name == 'IS_PRIVATE':
                    human_readable_description = "Include privately prescribed: False"  # Default assumption
                else:
                    human_readable_description = f"{column_display} filter applied"
            
            filter_data = {
                "column": col_filter.get('column'),
                "display_name": col_filter.get('display_name'),
                "inclusion_logic": "INCLUDE" if col_filter.get('in_not_in') == "IN" else "EXCLUDE",
                "description": human_readable_description,
                "filter_constraints": self._build_filter_constraints_complete(col_filter)
            }
            filters.append(filter_data)
        
        return filters
    
    def _build_filter_constraints_complete(self, col_filter) -> Dict[str, Any]:
        """Build complete filter constraints with SQL-ready logic"""
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
                
                # Just use the working Excel logic directly - copy the exact code from _render_column_filter_for_export
                if column in ['DATE', 'ISSUE_DATE'] and value:
                    # Check if this is a hardcoded date (contains slashes or dashes) vs relative offset
                    if '/' in value or '-' in value and not value.isdigit():
                        # Hardcoded date format
                        date_op = "on or after" if operator == "GTEQ" else "after" if operator == "GT" else "on"
                        if column == 'ISSUE_DATE':
                            human_desc = f"Date of Issue {date_op} {value} (Hardcoded Date)"
                        else:
                            human_desc = f"Date {date_op} {value} (Hardcoded Date)"
                    else:
                        # Relative date offset - handle zero case
                        date_op = "on or after" if operator == "GTEQ" else "after" if operator == "GT" else "on"
                        if value == '0':
                            human_desc = f"Date is {date_op} the search date"
                        else:
                            human_desc = f"Date is {date_op} {value} {unit.lower()}s from the search date"
                elif column == 'AGE' and value:
                    op_text = "greater than or equal to" if operator == "GTEQ" else "greater than" if operator == "GT" else "equal to"
                    human_desc = f"Age {op_text} {value} years"
                else:
                    op_text = "greater than or equal to" if operator == "GTEQ" else "greater than" if operator == "GT" else "equal to"
                    human_desc = f"Numeric value is {op_text} {value}"
                
                constraints["range_filter"] = {
                    "type": "range_from",
                    "operator": operator,
                    "value": value,
                    "unit": unit
                }
            
            # Process range_to (typically LTEQ operators)
            if range_info.get('to'):
                to_data = range_info['to']
                operator = to_data.get('operator', 'LTEQ')
                value = to_data.get('value', '')
                unit = to_data.get('unit', '')
                
                # Just use the working Excel logic directly - copy the exact code from _render_column_filter_for_export
                if column in ['DATE', 'ISSUE_DATE'] and value:
                    # Check if this is a hardcoded date (contains slashes or dashes) vs relative offset
                    if '/' in value or '-' in value and not value.isdigit():
                        # Hardcoded date format
                        date_op = "on or before" if operator == "LTEQ" else "before" if operator == "LT" else "on"
                        if column == 'ISSUE_DATE':
                            human_desc = f"Date of Issue {date_op} {value} (Hardcoded Date)"
                        else:
                            human_desc = f"Date {date_op} {value} (Hardcoded Date)"
                    else:
                        # Relative date offset - handle zero case
                        date_op = "on or before" if operator == "LTEQ" else "before" if operator == "LT" else "on"
                        if value == '0':
                            human_desc = f"Date is {date_op} the search date"
                        else:
                            human_desc = f"Date is {date_op} {value} {unit.lower()}s from the search date"
                elif column == 'AGE' and value:
                    op_text = "less than or equal to" if operator == "LTEQ" else "less than" if operator == "LT" else "equal to"
                    human_desc = f"Age {op_text} {value} years"
                else:
                    op_text = "less than or equal to" if operator == "LTEQ" else "less than" if operator == "LT" else "equal to"
                    human_desc = f"Numeric value is {op_text} {value}"
                
                constraints["range_filter_to"] = {
                    "type": "range_to",
                    "operator": operator,
                    "value": value,
                    "unit": unit
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
            
            # Check if this is EMISINTERNAL for special handling
            is_emisinternal = any(vs.get('code_system') == 'EMISINTERNAL' for vs in col_filter['value_sets'])
            
            if is_emisinternal:
                # Provide specific context for EMISINTERNAL codes
                constraints["emisinternal_filter"] = self._build_emisinternal_constraints(col_filter)
            else:
                constraints["value_set_filter"] = {
                    "total_values": value_count,
                    "inclusion_logic": "INCLUDE" if col_filter.get('in_not_in') == "IN" else "EXCLUDE",
                    "values_handled_in": "clinical_codes_section"
                }
        
        # Patient demographics constraints 
        if col_filter.get('column_type') == 'patient_demographics':
            demographics_type = col_filter.get('demographics_type', 'LSOA')
            grouped_values = col_filter.get('grouped_demographics_values', [])
            demographics_count = col_filter.get('demographics_count', 0)
            
            if grouped_values and demographics_count > 1:
                # Multiple demographics areas
                constraints["patient_demographics_filter"] = {
                    "filter_type": "demographics_areas",
                    "demographics_type": demographics_type,
                    "area_codes": grouped_values,
                    "area_count": demographics_count,
                    "inclusion_logic": "INCLUDE" if col_filter.get('in_not_in') == "IN" else "EXCLUDE",
                    "operator": col_filter.get('demographics_operator', 'OR')
                }
            else:
                # Single demographics area
                range_info = col_filter.get('range', {})
                from_data = range_info.get('from', {})
                value = from_data.get('value')
                
                constraints["patient_demographics_filter"] = {
                    "filter_type": "demographics_area",
                    "demographics_type": demographics_type,
                    "area_code": value,
                    "inclusion_logic": "INCLUDE" if col_filter.get('in_not_in') == "IN" else "EXCLUDE"
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
            # Special handling for EMISINTERNAL columns that might not have value sets attached
            if column == 'ISSUE_METHOD':
                constraints["emisinternal_filter"] = {
                    "filter_type": "issue_method_filter",
                    "column": col_filter.get('column'),
                    "display_name": col_filter.get('display_name', col_filter.get('column')),
                    "values": [
                        {"value": "A", "display_name": "Automatic"},
                        {"value": "D", "display_name": "Dispensing"},
                        {"value": "E", "display_name": "Electronic"},
                        {"value": "H", "display_name": "Handwritten"},
                        {"value": "OutsideOutOfHours", "display_name": "Out Of Hours"},
                        {"value": "P", "display_name": "Printed Script"}
                    ],
                    "inclusion_logic": "INCLUDE" if col_filter.get('in_not_in') == "IN" else "EXCLUDE"
                }
            elif column == 'IS_PRIVATE':
                constraints["emisinternal_filter"] = {
                    "filter_type": "is_private_filter",
                    "column": col_filter.get('column'),
                    "display_name": col_filter.get('display_name', col_filter.get('column')),
                    "values": [
                        {"value": "false", "display_name": "False"}
                    ],
                    "inclusion_logic": "INCLUDE" if col_filter.get('in_not_in') == "IN" else "EXCLUDE",
                    "constraint_logic": "Include private prescriptions = FALSE (Exclude Private)"
                }
            else:
                constraints["basic_filter"] = {
                    "filter_type": f"{column.lower()}_filter",
                    "column": col_filter.get('column'),
                    "display_name": col_filter.get('display_name', col_filter.get('column'))
                }
        
        return constraints
    
    def _build_emisinternal_constraints(self, col_filter) -> Dict[str, Any]:
        """Build detailed constraints for EMISINTERNAL codes"""
        column_name = col_filter.get('column', '').upper()
        in_not_in = col_filter.get('in_not_in', 'IN')
        inclusion_logic = "INCLUDE" if in_not_in == "IN" else "EXCLUDE"
        
        # Extract values for detailed context
        values_info = []
        for vs in col_filter.get('value_sets', []):
            if vs.get('code_system') == 'EMISINTERNAL':
                for value in vs.get('values', []):
                    values_info.append({
                        "code": value.get('value', ''),
                        "display_name": value.get('display_name', ''),
                        "include_children": value.get('include_children', False)
                    })
        
        # Build context-specific description
        if column_name == 'ISSUE_METHOD':
            filter_context = "medication_issue_method"
            description = f"{inclusion_logic} prescriptions with specified issue methods"
        elif column_name == 'IS_PRIVATE':
            filter_context = "prescription_funding"
            # Special logic for boolean values
            if values_info and values_info[0]['code'].lower() == 'false':
                description = f"{inclusion_logic} private prescriptions: False"
            elif values_info and values_info[0]['code'].lower() == 'true':
                description = f"{inclusion_logic} private prescriptions (patient paid)"
            else:
                description = f"{inclusion_logic} prescriptions based on funding type"
        elif column_name in ['AUTHOR', 'CURRENTLY_CONTRACTED']:
            filter_context = "user_authorization"
            description = f"{inclusion_logic} records based on user authorization"
        else:
            filter_context = "emis_internal_classification"
            description = f"{inclusion_logic} records based on EMIS internal classification"
        
        return {
            "filter_type": filter_context,
            "inclusion_logic": inclusion_logic,
            "column": column_name,
            "description": description,
            "values": values_info,
            "total_values": len(values_info)
        }
    
    def _build_complete_restrictions(self, restrictions, criterion) -> List[Dict[str, Any]]:
        """Build complete restriction logic with clinical code details"""
        restriction_list = []
        
        for restriction in restrictions:
            restriction_data = {
                "restriction_type": restriction.type,
                "description": getattr(restriction, 'description', ''),  # Use the same description as UI
                "count": getattr(restriction, 'count', getattr(restriction, 'record_count', None)),
                "time_constraint": {
                    "period": getattr(restriction, 'time_period', None),
                    "unit": getattr(restriction, 'time_unit', None)
                },
                "sort_order": getattr(restriction, 'sort_order', 'DESC'),
                "conditional_where": self._build_where_conditions_complete(restriction),
                "clinical_codes": self._extract_clinical_codes_from_restriction(restriction, criterion)
            }
            restriction_list.append(restriction_data)
        
        return restriction_list
    
    def _extract_clinical_codes_from_restriction(self, restriction, criterion) -> List[Dict[str, Any]]:
        """Extract rich clinical code details from restriction conditions"""
        codes = []
        
        if not hasattr(restriction, 'conditions') or not restriction.conditions:
            return codes
        
        for condition in restriction.conditions:
            # Extract value sets from restriction conditions
            value_sets = condition.get('value_sets', [])
            
            for vs_description in value_sets:
                if vs_description and vs_description.strip():
                    # Look up this value set in the main criterion to get full details
                    full_vs_details = self._find_value_set_by_description(vs_description.strip(), criterion)
                    
                    if full_vs_details:
                        for value in full_vs_details.get('values', []):
                            emis_code = value.get('value', '')
                            if emis_code:
                                snomed_info = self._get_snomed_translation(emis_code)
                                
                                description = snomed_info.get('description', '').strip()
                                if not description:
                                    description = value.get('display_name', '').strip()
                                if not description and snomed_info.get('is_refset', False):
                                    description = vs_description
                                if not description:
                                    description = 'No description available'
                                
                                code_entry = {
                                    "emis_guid": emis_code,
                                    "snomed_code": snomed_info.get('snomed_code', 'Not found'),
                                    "description": description,
                                    "code_system": full_vs_details.get('code_system', snomed_info.get('code_system', '')),
                                    "is_medication": snomed_info.get('is_medication', False),
                                    "is_refset": snomed_info.get('is_refset', False),
                                    "is_linked_criteria": False,  # These are restriction codes, not linked
                                    "is_restriction": True,       # These are explicitly restriction codes
                                    "include_children": value.get('include_children', False),
                                    "source_context": f"Restriction condition: {vs_description}",
                                    "translation_status": snomed_info.get('status', 'unknown')
                                }
                                codes.append(code_entry)
        
        return codes
    
    def _find_value_set_by_description(self, description, criterion) -> Dict[str, Any]:
        """Find value set details by description from criterion value sets"""
        # Search through all value sets in the criterion to find matching description
        for vs in criterion.value_sets:
            if vs.get('description', '').strip() == description:
                return vs
        
        # Also check column filters for value sets
        for col_filter in criterion.column_filters:
            for vs in col_filter.get('value_sets', []):
                if vs.get('description', '').strip() == description:
                    return vs
        
        # Return None if not found
        return None
    
    def _build_where_conditions_complete(self, restriction) -> List[Dict[str, Any]]:
        """Build WHERE conditions for restrictions"""
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
        """Build complete linked criteria details including their clinical codes and filters"""
        linked_list = []
        
        for linked in linked_criteria:
            # Extract clinical codes from this linked criterion
            linked_clinical_codes = []
            if hasattr(linked, 'value_sets') and linked.value_sets:
                for vs in linked.value_sets:
                    # Skip EMISINTERNAL codes (they go in column_filters)
                    if vs.get('code_system') == 'EMISINTERNAL':
                        continue
                        
                    for value in vs.get('values', []):
                        emis_code = value.get('value', '')
                        if emis_code:
                            snomed_info = self._get_snomed_translation(emis_code)
                            
                            # Use the best available description
                            description = snomed_info.get('description', '').strip()
                            if not description:
                                description = value.get('display_name', '').strip()
                            
                            # For refsets, try value set description
                            if not description and snomed_info.get('is_refset', False):
                                description = vs.get('description', '').strip()
                            
                            if not description:
                                description = 'No description available'
                            
                            linked_clinical_codes.append({
                                "emis_guid": emis_code,
                                "snomed_code": snomed_info.get('snomed_code', 'Not found'),
                                "description": description,
                                "code_system": vs.get('code_system', snomed_info.get('code_system', '')),
                                "is_medication": snomed_info.get('is_medication', False),
                                "is_refset": snomed_info.get('is_refset', False),
                                "is_linked_criteria": True,   # These are explicitly linked criteria codes
                                "is_restriction": False,     # These are not restriction codes
                                "include_children": value.get('include_children', False),
                                "source_context": value.get('display_name', vs.get('description', 'Linked Criterion')),
                                "translation_status": snomed_info.get('status', 'unknown')
                            })
            
            # Extract column filters from this linked criterion
            linked_column_filters = []
            if hasattr(linked, 'column_filters') and linked.column_filters:
                linked_column_filters = self._build_complete_column_filters(linked.column_filters)
            
            linked_data = {
                "relationship_type": getattr(linked, 'relationship_type', 'cross_reference'),
                "target_table": linked.table,
                "target_display_name": linked.display_name,
                "temporal_constraint": getattr(linked, 'temporal_constraint', None),
                "clinical_codes": linked_clinical_codes,
                "column_filters": linked_column_filters,
                "restrictions": self._build_complete_restrictions(getattr(linked, 'restrictions', []), linked),
                "criterion_id": getattr(linked, 'id', None),
                "negation": getattr(linked, 'negation', False)
            }
            linked_list.append(linked_data)
        
        return linked_list
    
    def _build_population_refs(self, group) -> List[Dict[str, Any]]:
        """Build population criteria references"""
        pop_refs = []
        
        if hasattr(group, 'population_criteria') and group.population_criteria:
            for pop_crit in group.population_criteria:
                pop_data = {
                    "referenced_search_id": pop_crit.report_guid,
                    "referenced_search_name": getattr(pop_crit, 'search_name', 'Unknown'),
                    "inclusion_type": getattr(pop_crit, 'inclusion_type', 'INCLUDE'),
                    "description": getattr(pop_crit, 'description', '')
                }
                pop_refs.append(pop_data)
        
        return pop_refs
    
    def _build_clinical_terminology(self, search_report) -> Dict[str, Any]:
        """Build complete clinical terminology with SNOMED focus"""
        # Get all unique codes from this search only
        all_codes = set()
        code_details = []
        
        for group in search_report.criteria_groups:
            for criterion in group.criteria:
                # Extract from value sets - SKIP EMISINTERNAL 
                for vs in criterion.value_sets:
                    # Skip EMISINTERNAL value sets - they're not clinical terminology
                    if vs.get('code_system') == 'EMISINTERNAL':
                        continue
                        
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
                                "code_system": vs.get('code_system', snomed_info.get('code_system', '')),
                                "semantic_type": "medication" if snomed_info.get('is_medication') else "clinical_concept",
                                "is_refset": snomed_info.get('is_refset', False),
                                "include_descendants": value.get('include_children', False),
                                "translation_quality": snomed_info.get('status', 'unknown')
                            })
                
                # Extract from column filters - SKIP EMISINTERNAL
                for col_filter in criterion.column_filters:
                    for vs in col_filter.get('value_sets', []):
                        # Skip EMISINTERNAL value sets
                        if vs.get('code_system') == 'EMISINTERNAL':
                            continue
                            
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
        
        return {
            "total_unique_codes": len(all_codes),
            "terminology_focus": "SNOMED_CT",
            "codes": sorted(code_details, key=lambda x: x['snomed_code'])
        }
    
    def _build_search_dependencies(self, search_report) -> Dict[str, Any]:
        """Build dependency information for this search only"""
        dependencies = {
            "parent_search": None,
            "referenced_searches": []
        }
        
        # Parent search
        if hasattr(search_report, 'parent_guid') and search_report.parent_guid:
            dependencies["parent_search"] = {
                "search_id": search_report.parent_guid,
                "search_name": getattr(search_report, 'parent_name', 'Unknown')
            }
        
        # Referenced searches from population criteria
        for group in search_report.criteria_groups:
            if hasattr(group, 'population_criteria') and group.population_criteria:
                for pop_crit in group.population_criteria:
                    dependencies["referenced_searches"].append({
                        "search_id": pop_crit.report_guid,
                        "search_name": getattr(pop_crit, 'search_name', 'Unknown'),
                        "inclusion_type": getattr(pop_crit, 'inclusion_type', 'INCLUDE')
                    })
        
        return dependencies
    
    
    def _get_all_processed_clinical_codes(self) -> List[Dict[str, Any]]:
        """Get all already processed and translated clinical codes from session state"""
        import streamlit as st
        
        # Import the same function used by clinical tabs to get unified data
        try:
            from ..ui.tabs.tab_helpers import get_unified_clinical_data
            unified_results = get_unified_clinical_data()
            
            all_codes = []
            
            # Get clinical codes
            clinical_codes = unified_results.get('clinical_codes', [])
            for code in clinical_codes:
                all_codes.append({
                    'emis_guid': code.get('EMIS GUID', ''),
                    'snomed_code': code.get('SNOMED Code', 'Not found'),
                    'description': code.get('Description', ''),
                    'code_system': code.get('Code System', ''),
                    'semantic_type': 'clinical_concept',
                    'is_medication': False,
                    'is_refset': code.get('Refset', 'No') == 'Yes',
                    'source_entity': code.get('Source Entity', ''),
                    'source_search': code.get('Source Search', ''),
                    'translation_status': 'translated' if code.get('SNOMED Code', 'Not found') != 'Not found' else 'not_found'
                })
            
            # Get medications
            medications = unified_results.get('medications', [])
            for med in medications:
                all_codes.append({
                    'emis_guid': med.get('EMIS GUID', ''),
                    'snomed_code': med.get('SNOMED Code', 'Not found'),
                    'description': med.get('Description', ''),
                    'code_system': med.get('Code System', ''),
                    'semantic_type': 'medication',
                    'is_medication': True,
                    'is_refset': False,
                    'source_entity': med.get('Source Entity', ''),
                    'source_search': med.get('Source Search', ''),
                    'translation_status': 'translated' if med.get('SNOMED Code', 'Not found') != 'Not found' else 'not_found'
                })
            
            # Get refsets
            refsets = unified_results.get('refsets', [])
            for refset in refsets:
                emis_guid = refset.get('EMIS GUID', '')
                snomed_code = refset.get('SNOMED Code', 'Not found')
                
                # For refsets, if SNOMED Code is not found, use EMIS GUID as SNOMED code
                if snomed_code == 'Not found' and emis_guid:
                    snomed_code = emis_guid
                
                all_codes.append({
                    'emis_guid': emis_guid,
                    'snomed_code': snomed_code,
                    'description': refset.get('Description', ''),
                    'code_system': refset.get('Code System', ''),
                    'semantic_type': 'refset',
                    'is_medication': False,
                    'is_refset': True,
                    'source_entity': refset.get('Source Entity', ''),
                    'source_search': refset.get('Source Search', ''),
                    'translation_status': 'translated' if snomed_code != 'Not found' else 'not_found'
                })
            
            return all_codes
            
        except Exception as e:
            # Fallback to empty list if unified data not available
            return []
    
    def _get_snomed_translation(self, emis_code: str) -> Dict[str, Any]:
        """Get SNOMED translation from already processed clinical codes"""
        all_codes = self._get_all_processed_clinical_codes()
        
        # Find this specific EMIS code in the processed data
        for code in all_codes:
            if code['emis_guid'] == emis_code:
                return {
                    'snomed_code': code['snomed_code'],
                    'description': code['description'],
                    'code_system': code['code_system'],
                    'is_medication': code['is_medication'],
                    'is_refset': code['is_refset'],
                    'status': code['translation_status']
                }
        
        # If not found in processed data, check if this might be a refset where EMIS GUID = SNOMED code
        # For refsets, use the EMIS GUID as the SNOMED code
        return {
            'snomed_code': emis_code if emis_code else 'Not found',
            'description': '',
            'code_system': 'SNOMED_CONCEPT',
            'is_medication': False,
            'is_refset': True,  # Identified as refset based on code pattern
            'status': 'translated' if emis_code else 'not_found'
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
        
        # Handle hardcoded dates (contains slashes or dashes)
        elif '/' in value or '-' in value and not value.isdigit():
            # Hardcoded date format - use same logic as Excel/UI
            op_text_simple = "on or after" if op_text == "after or on" else "on or before" if op_text == "before or on" else op_text
            return f"{op_text_simple} {value} (Hardcoded Date)"
        
        # Fallback for unhandled patterns
        else:
            return f"Date filter: {value} {unit}"
    
    def _determine_parameter_type(self, column: str) -> str:
        """Determine parameter data type for SQL recreation"""
        if column and ('DATE' in column.upper() or 'DOB' in column.upper()):
            return 'date'
        elif column and ('AGE' in column.upper() or 'YEAR' in column.upper()):
            return 'numeric'
        else:
            return 'text'
    
    def generate_folder_structure_json(self, folder_tree, folder_map, report_map, xml_filename: str) -> tuple[str, str]:
        """
        Generate hierarchical folder structure JSON export
        
        Args:
            folder_tree: The folder tree structure
            folder_map: Mapping of folder IDs to folder objects
            report_map: Mapping of report IDs to report objects
            xml_filename: Original XML filename for reference
            
        Returns:
            tuple: (filename, json_string)
        """
        from ..core import ReportClassifier
        
        if not folder_map or not report_map:
            export_data = {
                "error": "Missing data",
                "total_folders": len(folder_map) if folder_map else 0,
                "total_reports": len(report_map) if report_map else 0
            }
        else:
            try:
                export_data = {
                    "generated": datetime.now().isoformat(),
                    "xml_filename": xml_filename,
                    "folder_structure": self._convert_folder_tree_to_json(folder_tree, folder_map, report_map),
                    "summary": self._calculate_folder_summary(folder_tree, folder_map, report_map)
                }
            except Exception as e:
                export_data = {
                    "error": f"JSON conversion failed: {str(e)}",
                    "debug_info": {
                        "folder_map_keys": list(folder_map.keys())[:5],
                        "report_map_keys": list(report_map.keys())[:5]
                    }
                }
        
        # Generate filename
        clean_xml_name = xml_filename.replace('.xml', '').replace(' ', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{clean_xml_name}_folder_structure_{timestamp}.json"
        
        # Format JSON with proper indentation
        json_string = json.dumps(export_data, indent=2, ensure_ascii=False)
        
        return filename, json_string
    
    def generate_dependency_tree_json(self, dependency_tree, report_map, show_circular, xml_filename: str) -> tuple[str, str]:
        """
        Generate hierarchical dependency tree JSON export
        
        Args:
            dependency_tree: The dependency tree structure
            report_map: Mapping of report IDs to report objects
            show_circular: Whether to include circular dependencies
            xml_filename: Original XML filename for reference
            
        Returns:
            tuple: (filename, json_string)
        """
        from ..core import ReportClassifier
        
        if not dependency_tree or not dependency_tree.get('roots'):
            export_data = {
                "error": "No dependency tree found",
                "total_reports": len(report_map) if report_map else 0
            }
        else:
            try:
                export_data = {
                    "generated": datetime.now().isoformat(),
                    "xml_filename": xml_filename,
                    "show_circular_dependencies": show_circular,
                    "dependency_tree": self._convert_dependency_tree_to_json(dependency_tree, report_map, show_circular),
                    "summary": self._calculate_dependency_summary(dependency_tree, report_map, show_circular)
                }
            except Exception as e:
                export_data = {
                    "error": f"JSON conversion failed: {str(e)}",
                    "debug_info": {
                        "dependency_tree_keys": list(dependency_tree.keys()) if dependency_tree else [],
                        "report_map_size": len(report_map) if report_map else 0,
                        "show_circular": show_circular
                    }
                }
        
        # Generate filename
        clean_xml_name = xml_filename.replace('.xml', '').replace(' ', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{clean_xml_name}_dependency_tree_{timestamp}.json"
        
        # Format JSON with proper indentation
        json_string = json.dumps(export_data, indent=2, ensure_ascii=False)
        
        return filename, json_string
    
    def _convert_folder_tree_to_json(self, folder_tree, folder_map, report_map):
        """Convert folder structure to hierarchical JSON format"""
        from ..core import ReportClassifier
        
        def convert_folder_node(folder_node):
            """Recursively convert a folder node to JSON with all its children and reports"""
            folder_id = folder_node['id']
            folder = folder_map.get(folder_id)
            
            # Build folder JSON structure
            folder_json = {
                "id": folder_id,
                "name": folder_node['name'],
                "type": "folder",
                "children": [],
                "reports": []
            }
            
            # Add reports in this folder with proper classification
            if folder and folder.report_ids:
                reports = [report_map.get(report_id) for report_id in folder.report_ids if report_map.get(report_id)]
                
                # Group reports by type like the ASCII tree does
                search_reports = []
                output_reports = []  # List, Audit, and Aggregate reports
                
                for report in reports:
                    report_type = ReportClassifier.classify_report_type(report)
                    
                    report_json = {
                        "id": report.id,
                        "name": getattr(report, 'name', 'Unknown'),
                        "type": report_type,
                        "type_clean": report_type.strip('[]')
                    }
                    
                    # Add metadata
                    for attr in ['parent_guid', 'description']:
                        if hasattr(report, attr):
                            report_json[attr] = getattr(report, attr)
                    
                    if report_type == "[Search]":
                        search_reports.append(report_json)
                    else:
                        output_reports.append(report_json)
                
                # Create parent-child relationships like the ASCII tree
                parent_to_reports = {}
                for output_report in output_reports:
                    parent_guid = output_report.get('parent_guid')
                    if parent_guid:
                        if parent_guid not in parent_to_reports:
                            parent_to_reports[parent_guid] = []
                        parent_to_reports[parent_guid].append(output_report)
                
                # Add search reports with their children
                for search_report in search_reports:
                    search_guid = search_report['id']
                    child_reports = parent_to_reports.get(search_guid, [])
                    
                    if child_reports:
                        search_report['child_reports'] = child_reports
                    
                    folder_json['reports'].append(search_report)
                
                # Add orphaned output reports (no parent found)
                for output_report in output_reports:
                    parent_guid = output_report.get('parent_guid')
                    if not parent_guid or parent_guid not in [s['id'] for s in search_reports]:
                        folder_json['reports'].append(output_report)
            
            # Recursively add child folders
            for child_folder in folder_node['children']:
                child_json = convert_folder_node(child_folder)
                folder_json['children'].append(child_json)
            
            return folder_json
        
        # Convert the root folder tree - same structure as ASCII tree
        if folder_tree and folder_tree.get('roots'):
            # Multiple root folders
            root_structure = {
                "type": "root",
                "children": []
            }
            
            for root_folder in folder_tree['roots']:
                root_structure['children'].append(convert_folder_node(root_folder))
        else:
            # No folder tree or invalid structure
            root_structure = {"error": "No folder tree found or invalid structure"}
        
        return root_structure
    
    def _convert_dependency_tree_to_json(self, dependency_tree, report_map, show_circular):
        """Convert dependency tree to hierarchical JSON format"""
        from ..core import ReportClassifier
        
        def convert_dependency_node(dep_node):
            """Recursively convert a dependency node to JSON with all its children"""
            report = report_map.get(dep_node['id'])
            report_type = ReportClassifier.classify_report_type(report) if report else "[Search]"
            
            # Build dependency JSON structure
            dep_json = {
                "id": dep_node['id'],
                "name": dep_node['name'],
                "type": report_type,
                "type_clean": report_type.strip('[]'),
                "is_circular": dep_node.get('circular', False),
                "dependencies": []
            }
            
            # Add metadata if available
            if report:
                for attr in ['parent_guid', 'description']:
                    if hasattr(report, attr):
                        dep_json[attr] = getattr(report, attr)
            
            # Add folder path if available
            if dep_node.get('folder_path'):
                dep_json['folder_path'] = dep_node['folder_path']
            
            # Only include circular dependencies if show_circular is True
            children = dep_node.get('children', []) or dep_node.get('dependencies', [])
            for child_dep in children:
                if not child_dep.get('circular', False) or show_circular:
                    child_json = convert_dependency_node(child_dep)
                    dep_json['dependencies'].append(child_json)
            
            return dep_json
        
        # Convert all root dependencies
        root_dependencies = []
        for root_dep in dependency_tree['roots']:
            root_json = convert_dependency_node(root_dep)
            root_dependencies.append(root_json)
        
        return {
            "type": "dependency_root",
            "roots": root_dependencies
        }
    
    def _calculate_folder_summary(self, folder_tree, folder_map, report_map):
        """Calculate summary statistics for folder structure"""
        from ..core import ReportClassifier
        
        def count_items(node):
            """Recursively count folders and reports by type"""
            counts = {
                'folders': 0,
                'searches': 0,
                'list_reports': 0,
                'audit_reports': 0,
                'aggregate_reports': 0
            }
            
            if node.get('type') == 'folder':
                counts['folders'] += 1
                
                # Count reports in this folder
                for report in node.get('reports', []):
                    report_type = report.get('type_clean', '').lower().replace(' ', '_')
                    if report_type == 'search':
                        counts['searches'] += 1
                        # Count child reports
                        for child in report.get('child_reports', []):
                            child_type = child.get('type_clean', '').lower().replace(' ', '_')
                            if child_type in counts:
                                counts[child_type] += 1
                    elif report_type in counts:
                        counts[report_type] += 1
                
                # Recursively count children
                for child in node.get('children', []):
                    child_counts = count_items(child)
                    for key in counts:
                        counts[key] += child_counts[key]
            elif node.get('type') == 'root':
                # Handle root node
                for child in node.get('children', []):
                    child_counts = count_items(child)
                    for key in counts:
                        counts[key] += child_counts[key]
            
            return counts
        
        # Convert folder structure to calculate summary
        root_structure = self._convert_folder_tree_to_json(folder_tree, folder_map, report_map)
        return count_items(root_structure) if root_structure.get('type') != 'error' else {}
    
    def _calculate_dependency_summary(self, dependency_tree, report_map, show_circular):
        """Calculate summary statistics for dependency tree"""
        from ..core import ReportClassifier
        
        def count_dependency_items(node):
            """Recursively count dependencies by type"""
            counts = {
                'total_nodes': 0,
                'searches': 0,
                'list_reports': 0,
                'audit_reports': 0,
                'aggregate_reports': 0,
                'circular_dependencies': 0
            }
            
            counts['total_nodes'] += 1
            
            # Count by type
            report_type = node.get('type_clean', '').lower().replace(' ', '_')
            if report_type in counts:
                counts[report_type] += 1
            
            # Count circular dependencies
            if node.get('is_circular', False):
                counts['circular_dependencies'] += 1
            
            # Recursively count children
            for child in node.get('dependencies', []):
                child_counts = count_dependency_items(child)
                for key in counts:
                    counts[key] += child_counts[key]
            
            return counts
        
        # Convert dependency structure to calculate summary
        root_structure = self._convert_dependency_tree_to_json(dependency_tree, report_map, show_circular)
        
        # Calculate total counts across all roots
        total_counts = {
            'total_nodes': 0,
            'searches': 0,
            'list_reports': 0,
            'audit_reports': 0,
            'aggregate_reports': 0,
            'circular_dependencies': 0
        }
        
        for root in root_structure.get('roots', []):
            root_counts = count_dependency_items(root)
            for key in total_counts:
                total_counts[key] += root_counts[key]
        
        return total_counts
