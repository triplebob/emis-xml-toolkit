"""
Report Parser for EMIS XML
Handles parsing of all 4 EMIS report types: Search, List, Audit, and Aggregate reports
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
from .base_parser import XMLParserBase
from .criterion_parser import CriterionParser


class ReportParser(XMLParserBase):
    """Parser for different EMIS report types"""
    
    def parse_report_structure(self, report_elem: ET.Element) -> Dict[str, Any]:
        """
        Parse a report element and determine its type and structure
        
        Args:
            report_elem: The <report> XML element
            
        Returns:
            Dict containing report type and parsed structure
        """
        result = {
            'report_type': 'search',  # Default
            'parent_type': None,
            'column_groups': [],
            'custom_aggregate': None,
            'aggregate_groups': [],
            'statistical_groups': [],
            # Enterprise reporting enhancements
            'report_folder': None,
            'enterprise_reporting_level': None,
            'organization_associations': [],
            'version_independent_guid': None,
            'qmas_indicator': None
        }
        
        # Get parent type indicator - handle both namespaced and non-namespaced
        parent_elem = report_elem.find('.//emis:parent', self.namespaces) or report_elem.find('.//parent')
        if parent_elem is not None:
            result['parent_type'] = parent_elem.get('parentType')
        
        # Parse enterprise reporting elements
        self._parse_enterprise_elements(report_elem, result)
        
        # Check for list report structure
        list_report = report_elem.find('.//emis:listReport', self.namespaces)
        # Fallback: try without namespace prefix for default namespace elements
        if list_report is None:
            list_report = report_elem.find('.//listReport')
        if list_report is not None:
            result['report_type'] = 'list'
            result['column_groups'] = self._parse_list_report_columns(list_report)
        
        # Check for audit report structure  
        audit_report = report_elem.find('.//emis:auditReport', self.namespaces)
        # Fallback: try without namespace prefix for default namespace elements
        if audit_report is None:
            audit_report = report_elem.find('.//auditReport')
        if audit_report is not None:
            result['report_type'] = 'audit'
            result['custom_aggregate'] = self._parse_audit_report_aggregate(audit_report)
            
            # Parse population references (multiple populations for Audit Reports)
            populations = audit_report.findall('emis:population', self.namespaces)
            if not populations:
                populations = audit_report.findall('population')  # Fallback for default namespace
            result['population_references'] = [pop.text.strip() for pop in populations if pop.text]
            
            # Parse criteria from customAggregate if present (same structure as aggregate reports)
            custom_aggregate = audit_report.find('emis:customAggregate', self.namespaces)
            if custom_aggregate is None:
                custom_aggregate = audit_report.find('customAggregate')  # Fallback
            if custom_aggregate is not None:
                # Audit reports can have the same criteria structure as aggregate reports
                audit_criteria = self._parse_aggregate_criteria(custom_aggregate)
                if audit_criteria:
                    result['criteria_groups'] = audit_criteria.get('criteria_groups', [])
        
        # Check for aggregate report structure
        aggregate_report = report_elem.find('.//emis:aggregateReport', self.namespaces)
        # Fallback: try without namespace prefix for default namespace elements
        if aggregate_report is None:
            aggregate_report = report_elem.find('.//aggregateReport')
        if aggregate_report is not None:
            result['report_type'] = 'aggregate'
            result['aggregate_groups'] = self._parse_aggregate_report_groups(aggregate_report)
            result['statistical_groups'] = self._parse_statistical_groups(aggregate_report, result['aggregate_groups'])
            logical_table_elem = aggregate_report.find('emis:logicalTable', self.namespaces)
            if logical_table_elem is None:
                logical_table_elem = aggregate_report.find('logicalTable')
            result['logical_table'] = self.get_text(logical_table_elem)
            result['aggregate_criteria'] = self._parse_aggregate_criteria(aggregate_report)
        
        return result
    
    def _parse_list_report_columns(self, list_report_elem: ET.Element) -> List[Dict]:
        """Parse list report column structure with enhanced enterprise patterns support"""
        column_groups = []
        
        # Handle both namespaced and non-namespaced column groups
        namespaced_groups = list_report_elem.findall('.//emis:columnGroup', self.namespaces)
        non_namespaced_groups = list_report_elem.findall('.//columnGroup')
        all_groups = non_namespaced_groups + [g for g in namespaced_groups if g not in non_namespaced_groups]
        
        for column_group in all_groups:
            # Handle mixed namespace XML - parent may be namespaced but children are not
            logical_table_elem = column_group.find('logicalTableName')
            if logical_table_elem is None:
                logical_table_elem = column_group.find('emis:logicalTableName', self.namespaces)
            logical_table = self.get_text(logical_table_elem)
            
            display_name_elem = column_group.find('displayName')
            if display_name_elem is None:
                display_name_elem = column_group.find('emis:displayName', self.namespaces)
            group_data = {
                'id': column_group.get('id', ''),
                'logical_table': logical_table,
                'display_name': self.get_text(display_name_elem),
                'columns': [],
                'table_type': self._classify_table_type(logical_table),
                'sort_configuration': None
            }
            
            # Parse sorting configuration if present - handle mixed namespaces
            sort_elem = column_group.find('sort')
            if sort_elem is None:
                sort_elem = column_group.find('emis:sort', self.namespaces)
            if sort_elem is not None:
                group_data['sort_configuration'] = self._parse_sort_configuration(sort_elem)
            
            # Parse individual columns with enhanced column types - handle mixed namespaces
            columnar = column_group.find('columnar')
            if columnar is None:
                columnar = column_group.find('emis:columnar', self.namespaces)
            if columnar is not None:
                namespaced_cols = columnar.findall('emis:listColumn', self.namespaces)
                non_namespaced_cols = columnar.findall('listColumn')
                all_cols = non_namespaced_cols + [c for c in namespaced_cols if c not in non_namespaced_cols]
                
                for list_column in all_cols:
                    # Handle mixed namespaces for column elements
                    column_elem = list_column.find('column')
                    if column_elem is None:
                        column_elem = list_column.find('emis:column', self.namespaces)
                    column_text = self.get_text(column_elem)
                    
                    display_name_elem = list_column.find('displayName')
                    if display_name_elem is None:
                        display_name_elem = list_column.find('emis:displayName', self.namespaces)
                    column_data = {
                        'id': list_column.get('id', ''),
                        'column': column_text,
                        'display_name': self.get_text(display_name_elem),
                        'column_type': self._classify_column_type(column_text),
                        'is_enhanced_column': self._is_enhanced_column(column_text)
                    }
                    group_data['columns'].append(column_data)
            
            # Parse criteria if present (for filtered list reports) - handle mixed namespaces
            criteria_elem = column_group.find('criteria')
            if criteria_elem is None:
                criteria_elem = column_group.find('emis:criteria', self.namespaces)
            if criteria_elem is not None:
                group_data['has_criteria'] = True
                group_data['criteria_details'] = self._parse_column_group_criteria(criteria_elem)
            else:
                group_data['has_criteria'] = False
                group_data['criteria_details'] = None
            
            column_groups.append(group_data)
        
        return column_groups
    
    def _classify_table_type(self, logical_table: str) -> str:
        """Classify the logical table type for enhanced reporting"""
        if not logical_table:
            return 'unknown'
        
        table_upper = logical_table.upper()
        if 'MEDICATION_COURSES' in table_upper:
            return 'medication_courses'
        elif 'MEDICATION_ISSUES' in table_upper:
            return 'medication_issues'
        elif 'PATIENT' in table_upper:
            return 'patient'
        elif 'ORGANISATION' in table_upper:
            return 'organisation'
        else:
            return 'standard'
    
    def _classify_column_type(self, column_text: str) -> str:
        """Classify column types for enhanced display"""
        if not column_text:
            return 'standard'
        
        column_upper = column_text.upper()
        if 'AGE_AT_EVENT' in column_upper:
            return 'age_at_event'
        elif 'ORGANISATION_TERM' in column_upper:
            return 'organisation'
        elif 'USUAL_GP' in column_upper:
            return 'practitioner'
        elif 'COMMENCE_DATE' in column_upper or 'LASTISSUE_DATE' in column_upper:
            return 'medication_date'
        elif 'ASSOCIATEDTEXT' in column_upper:
            return 'associated_text'
        elif 'QUANTITY_UNIT' in column_upper:
            return 'quantity'
        else:
            return 'standard'
    
    def _is_enhanced_column(self, column_text: str) -> bool:
        """Check if this is one of the enhanced output columns from enterprise patterns"""
        if not column_text:
            return False
        
        enhanced_columns = [
            'ORGANISATION_TERM', 'USUAL_GP.USER_NAME', 'COMMENCE_DATE', 
            'LASTISSUE_DATE', 'ASSOCIATEDTEXT', 'QUANTITY_UNIT', 'AGE_AT_EVENT'
        ]
        
        return any(enhanced_col in column_text.upper() for enhanced_col in enhanced_columns)
    
    def _parse_sort_configuration(self, sort_elem: ET.Element) -> Dict[str, Any]:
        """Parse List Report column sorting configuration"""
        sort_config = {}
        
        column_id_elem = sort_elem.find('columnId')
        if column_id_elem is None:
            column_id_elem = sort_elem.find('emis:columnId', self.namespaces)
        if column_id_elem is not None:
            sort_config['column_id'] = self.get_text(column_id_elem)
        
        direction_elem = sort_elem.find('direction')
        if direction_elem is None:
            direction_elem = sort_elem.find('emis:direction', self.namespaces)
        if direction_elem is not None:
            sort_config['direction'] = self.get_text(direction_elem)
        
        return sort_config if sort_config else None
    
    def _parse_column_group_criteria(self, criteria_elem: ET.Element) -> Dict[str, Any]:
        """Parse criteria within column groups for filtered List Reports with full clinical details"""
        from .criterion_parser import CriterionParser
        
        try:
            # Handle namespace fallback for criteria elements
            criterion_elements = criteria_elem.findall('emis:criterion', self.namespaces)
            if not criterion_elements:
                criterion_elements = criteria_elem.findall('criterion')  # Fallback for default namespace
            
            criterion_parser = CriterionParser(self.namespaces)
            criteria_details = {
                'has_criteria': True,
                'criteria_count': len(criterion_elements),
                'criteria': []
            }
            
            # Parse individual criteria using the sophisticated parser
            for criterion_elem in criterion_elements:
                parsed_criterion = criterion_parser.parse_criterion(criterion_elem)
                if parsed_criterion:
                    # Build comprehensive criterion details for UI display
                    criterion_data = {
                        'id': parsed_criterion.id,
                        'table': parsed_criterion.table,
                        'display_name': parsed_criterion.display_name,
                        'description': parsed_criterion.description,
                        'negation': parsed_criterion.negation,
                        'exception_code': parsed_criterion.exception_code,
                        'value_sets': [],
                        'column_filters': [],
                        'restrictions': [],
                        'linked_criteria': [],
                        'clinical_codes': []
                    }
                    
                    # Extract value sets with clinical codes
                    for value_set in parsed_criterion.value_sets:
                        value_set_data = {
                            'id': value_set.get('id', ''),
                            'code_system': value_set.get('code_system', ''),
                            'description': value_set.get('description', ''),
                            'values': []
                        }
                        
                        # Extract individual clinical codes
                        for value in value_set.get('values', []):
                            code_data = {
                                'value': value.get('value', ''),
                                'display_name': value.get('display_name', ''),
                                'include_children': value.get('include_children', False),
                                'is_refset': value.get('is_refset', False),
                                'code_system': value_set.get('code_system', ''),
                                'valueSet_guid': value_set.get('id', ''),
                                'valueSet_description': value_set.get('description', '')
                            }
                            value_set_data['values'].append(code_data)
                            criterion_data['clinical_codes'].append(code_data)
                        
                        criterion_data['value_sets'].append(value_set_data)
                    
                    # Extract column filters (date ranges, etc.)
                    for column_filter in parsed_criterion.column_filters:
                        filter_data = {
                            'column': column_filter.get('column', ''),
                            'display_name': column_filter.get('display_name', ''),
                            'in_not_in': column_filter.get('in_not_in', ''),
                            'range': column_filter.get('range', {})
                        }
                        criterion_data['column_filters'].append(filter_data)
                    
                    # Extract restrictions (Latest 1, etc.)
                    for restriction in parsed_criterion.restrictions:
                        if hasattr(restriction, '__dict__'):
                            restriction_data = {
                                'type': getattr(restriction, 'type', 'unknown'),
                                'record_count': getattr(restriction, 'record_count', None),
                                'ordering_column': 'DATE',  # List Report restrictions typically order by DATE
                                'direction': getattr(restriction, 'direction', None),
                                'description': getattr(restriction, 'description', str(restriction))
                            }
                        else:
                            restriction_data = {'description': str(restriction)}
                        
                        criterion_data['restrictions'].append(restriction_data)
                    
                    # Extract linked criteria (cross-table relationships)
                    for linked_criterion in parsed_criterion.linked_criteria:
                        linked_data = {
                            'id': linked_criterion.id,
                            'table': linked_criterion.table,
                            'display_name': linked_criterion.display_name,
                            'description': linked_criterion.description,
                            'negation': linked_criterion.negation,
                            'value_sets_count': len(linked_criterion.value_sets),
                            'column_filters_count': len(linked_criterion.column_filters),
                            'restrictions_count': len(linked_criterion.restrictions)
                        }
                        criterion_data['linked_criteria'].append(linked_data)
                    
                    criteria_details['criteria'].append(criterion_data)
            
            return criteria_details
        except Exception as e:
            return {
                'has_criteria': True,
                'criteria_count': 0,
                'criteria': [],
                'parse_error': str(e)
            }
    
    def _parse_audit_report_aggregate(self, audit_report_elem: ET.Element) -> Optional[Dict]:
        """Parse audit report aggregation structure"""
        custom_aggregate = audit_report_elem.find('customAggregate')
        if custom_aggregate is None:
            custom_aggregate = audit_report_elem.find('emis:customAggregate', self.namespaces)
        if custom_aggregate is None:
            return None
        
        logical_table_elem = custom_aggregate.find('logicalTable')
        if logical_table_elem is None:
            logical_table_elem = custom_aggregate.find('emis:logicalTable', self.namespaces)
        aggregate_data = {
            'logical_table': self.get_text(logical_table_elem),
            'groups': [],
            'rows': [],
            'result': {}
        }
        
        # Parse grouping information
        for group in custom_aggregate.findall('emis:group', self.namespaces):
            group_data = {
                'id': group.get('id', ''),
                'display_name': self.get_text(group.find('emis:displayName', self.namespaces)),
                'grouping_column': self.get_text(group.find('emis:groupingColumn', self.namespaces)),
                'sub_totals': self.get_text(group.find('emis:subTotals', self.namespaces)) == 'true',
                'repeat_header': self.get_text(group.find('emis:repeatHeader', self.namespaces)) == 'true'
            }
            aggregate_data['groups'].append(group_data)
        
        # Parse rows configuration
        rows_elem = custom_aggregate.find('emis:rows', self.namespaces)
        if rows_elem is not None:
            group_id = self.get_text(rows_elem.find('emis:groupId', self.namespaces))
            aggregate_data['rows'].append({'group_id': group_id})
        
        # Parse result configuration
        result_elem = custom_aggregate.find('emis:result', self.namespaces)
        if result_elem is not None:
            aggregate_data['result'] = {
                'source': self.get_text(result_elem.find('emis:source', self.namespaces)),
                'calculation_type': self.get_text(result_elem.find('emis:calculationType', self.namespaces))
            }
        
        # Parse population reference
        population_elem = audit_report_elem.find('emis:population', self.namespaces)
        if population_elem is not None:
            aggregate_data['population_reference'] = population_elem.text
        
        return aggregate_data
    
    def _parse_aggregate_report_groups(self, aggregate_report_elem: ET.Element) -> List[Dict]:
        """Parse aggregate report grouping structure"""
        groups = []
        
        for group in aggregate_report_elem.findall('emis:group', self.namespaces):
            group_id_elem = group.find('emis:id', self.namespaces)
            group_id = self.get_text(group_id_elem)
            display_name_elem = group.find('emis:displayName', self.namespaces)
            display_name = self.get_text(display_name_elem)
            
            group_data = {
                'id': group_id,
                'display_name': display_name,
                'grouping_columns': [],
                'sub_totals': self.get_text(group.find('emis:subTotals', self.namespaces)) == 'true',
                'repeat_header': self.get_text(group.find('emis:repeatHeader', self.namespaces)) == 'true'
            }
            
            # Parse multiple grouping columns
            for grouping_col in group.findall('emis:groupingColumn', self.namespaces):
                if grouping_col.text:
                    group_data['grouping_columns'].append(grouping_col.text)
            
            groups.append(group_data)
        
        return groups
    
    def _parse_statistical_groups(self, aggregate_report_elem: ET.Element, aggregate_groups: List[Dict]) -> List[Dict]:
        """Parse statistical grouping and calculation structure with group name resolution"""
        statistical_groups = []
        
        # Create group ID to name mapping for resolution from aggregate_groups
        group_lookup = {group['id']: group['display_name'] for group in aggregate_groups if group.get('id') and group.get('display_name')}
        
        # Alternative: Parse group names directly from XML if lookup fails
        # This is a fallback to ensure we get the names even if the aggregate_groups parsing had issues
        if not group_lookup:
            for group_elem in aggregate_report_elem.findall('emis:group', self.namespaces):
                group_id_elem = group_elem.find('emis:id', self.namespaces)
                group_id = self.get_text(group_id_elem)
                display_name_elem = group_elem.find('emis:displayName', self.namespaces)
                display_name = self.get_text(display_name_elem)
                if group_id and display_name:
                    group_lookup[group_id] = display_name
        
        # Parse rows configuration
        rows_elem = aggregate_report_elem.find('emis:rows', self.namespaces)
        if rows_elem is not None:
            group_id = self.get_text(rows_elem.find('emis:groupId', self.namespaces))
            group_name = group_lookup.get(group_id, f"Group {group_id}")
            statistical_groups.append({
                'type': 'rows',
                'group_id': group_id,
                'group_name': group_name
            })
        
        # Parse columns configuration  
        columns_elem = aggregate_report_elem.find('emis:columns', self.namespaces)
        if columns_elem is not None:
            group_id = self.get_text(columns_elem.find('emis:groupId', self.namespaces))
            group_name = group_lookup.get(group_id, f"Group {group_id}")
            statistical_groups.append({
                'type': 'columns', 
                'group_id': group_id,
                'group_name': group_name
            })
        
        # Parse result configuration
        result_elem = aggregate_report_elem.find('emis:result', self.namespaces)
        if result_elem is not None:
            statistical_groups.append({
                'type': 'result',
                'source': self.get_text(result_elem.find('emis:source', self.namespaces)),
                'calculation_type': self.get_text(result_elem.find('emis:calculationType', self.namespaces))
            })
        
        return statistical_groups
    
    def _parse_aggregate_criteria(self, aggregate_report_elem: ET.Element) -> Optional[Dict]:
        """Parse aggregate report built-in criteria using full criterion parser for complete feature support"""
        criteria_elem = aggregate_report_elem.find('emis:criteria', self.namespaces)
        if criteria_elem is None:
            return None
        
        # Use the full criterion parser for sophisticated parsing
        criterion_parser = CriterionParser()
        
        criteria_data = {
            'has_criteria': True,
            'criteria_groups': []
        }
        
        # Aggregate reports have direct <criteria><criterion> structure
        # Create a single group to contain all criteria with full parsing
        group_data = {
            'id': 'aggregate_filters',
            'member_operator': 'AND',  # Default for aggregate filters
            'action_if_true': 'SELECT',  # Aggregate filters select matching records
            'action_if_false': 'REJECT',
            'criteria': []
        }
        
        # Parse individual criteria directly under <criteria> using full parser
        for criterion_elem in criteria_elem.findall('emis:criterion', self.namespaces):
            # Use the sophisticated criterion parser that handles all patterns:
            # - Clinical codes (SNOMED/Read) with GUID extraction
            # - Medications (dm+d codes) 
            # - Patient criteria (age, gender, registration)
            # - Date filters (relative dates, before/after)
            # - Restrictions ("Latest 1", conditional logic)
            # - Linked criteria
            # - Value sets with includeChildren
            # - All operators (IN/NOT IN, etc.)
            parsed_criterion = criterion_parser.parse_criterion(criterion_elem)
            
            if parsed_criterion:
                # Convert the parsed criterion to the format expected by the UI
                criterion_data = {
                    'id': parsed_criterion.id,
                    'table': parsed_criterion.table,
                    'display_name': parsed_criterion.display_name,
                    'description': parsed_criterion.description,
                    'negation': parsed_criterion.negation,
                    'column_filters': parsed_criterion.column_filters,
                    'value_sets': parsed_criterion.value_sets,
                    'restrictions': parsed_criterion.restrictions,
                    'linked_criteria': parsed_criterion.linked_criteria,
                    'parameters': []  # SearchCriterion doesn't have parameters attribute
                }
                
                group_data['criteria'].append(criterion_data)
        
        # Only add the group if it has criteria
        if group_data['criteria']:
            criteria_data['criteria_groups'].append(group_data)
        
        return criteria_data if criteria_data['criteria_groups'] else None
    
    def get_report_dependencies(self, report_elem: ET.Element) -> List[str]:
        """
        Extract report dependencies (references to other reports)
        
        Returns:
            List of referenced report GUIDs
        """
        dependencies = []
        
        # Check for SearchIdentifier in list reports (try both with and without namespace)
        search_id = report_elem.find('.//emis:SearchIdentifier', self.namespaces)
        if search_id is None:
            search_id = report_elem.find('.//SearchIdentifier')  # Fallback for default namespace
        if search_id is not None:
            report_guid = search_id.get('reportGuid')
            if report_guid:
                dependencies.append(report_guid)
        
        # Check for population references in audit reports - can have multiple populations
        # Try both with and without namespace
        populations = report_elem.findall('.//emis:population', self.namespaces)
        if not populations:
            populations = report_elem.findall('.//population')  # Fallback for default namespace
        
        for population in populations:
            if population is not None and population.text:
                pop_guid = population.text.strip()
                if pop_guid:
                    dependencies.append(pop_guid)
        
        return dependencies
    
    def _parse_enterprise_elements(self, report_elem: ET.Element, result: Dict[str, Any]) -> None:
        """Parse enterprise reporting elements added for advanced healthcare patterns"""
        
        # Parse report folder hierarchy (with parent folder nesting)
        report_folder_elem = report_elem.find('.//emis:reportFolder', self.namespaces)
        if report_folder_elem is not None:
            folder_data = {
                'name': self.get_text(report_folder_elem.find('emis:name', self.namespaces)),
                'parent_folder': None
            }
            
            # Check for parent folder nesting
            parent_folder_elem = report_folder_elem.find('emis:parentFolder', self.namespaces)
            if parent_folder_elem is not None:
                folder_data['parent_folder'] = {
                    'name': self.get_text(parent_folder_elem.find('emis:name', self.namespaces)),
                    'id': parent_folder_elem.get('id', '')
                }
            
            result['report_folder'] = folder_data
        
        # Parse enterprise reporting level
        enterprise_level_elem = report_elem.find('.//emis:enterpriseReportingLevel', self.namespaces)
        if enterprise_level_elem is not None:
            result['enterprise_reporting_level'] = self.get_text(enterprise_level_elem)
        
        # Parse organization associations (multiple organizations)
        associations = []
        for assoc_elem in report_elem.findall('.//emis:association', self.namespaces):
            org_elem = assoc_elem.find('emis:organisation', self.namespaces)
            if org_elem is not None:
                associations.append({
                    'organisation_guid': org_elem.text,
                    'type': assoc_elem.get('type', 'unknown')
                })
        result['organization_associations'] = associations
        
        # Parse version independent GUID for cross-version compatibility
        version_guid_elem = report_elem.find('.//emis:VersionIndependentGUID', self.namespaces)
        if version_guid_elem is not None:
            result['version_independent_guid'] = self.get_text(version_guid_elem)
        
        # Parse QMAS indicator for QOF integration
        qmas_elem = report_elem.find('.//emis:qmasIndicator', self.namespaces)
        if qmas_elem is not None:
            result['qmas_indicator'] = self.get_text(qmas_elem).lower() == 'true'
