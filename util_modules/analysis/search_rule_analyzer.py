"""
Search Rule Analyzer for EMIS XML
Extracts and analyzes search logic, filtering rules, and criteria relationships
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

# Import new modular XML parsers
from ..xml_parsers.criterion_parser import CriterionParser, SearchCriterion as ParsedSearchCriterion
from ..xml_parsers.value_set_parser import ValueSetParser
from ..xml_parsers.restriction_parser import RestrictionParser, SearchRestriction as ParsedSearchRestriction
from ..xml_parsers.linked_criteria_parser import LinkedCriteriaParser
from ..xml_parsers.report_parser import ReportParser
from ..xml_parsers.namespace_handler import NamespaceHandler
from ..xml_parsers.base_parser import get_namespaces

@dataclass
class ReportFolder:
    """Represents a folder in the EMIS search directory structure"""
    id: str
    name: str
    parent_folder_id: Optional[str] = None
    child_folder_ids: List[str] = field(default_factory=list)
    report_ids: List[str] = field(default_factory=list)
    sequence: int = 0
    path: List[str] = field(default_factory=list)  # Full folder path

@dataclass
class PopulationCriterion:
    """Reference to another report used as a criterion"""
    id: str
    report_guid: str
    relationship_type: str = "population"  # population, linked, etc.

# Use dataclasses from the new modular parsers
SearchRestriction = ParsedSearchRestriction
SearchCriterion = ParsedSearchCriterion

@dataclass
class CriteriaGroup:
    """Group of criteria with AND/OR logic"""
    id: str
    member_operator: str  # AND/OR
    criteria: List[SearchCriterion]
    population_criteria: List[PopulationCriterion]  # References to other reports
    action_if_true: str  # SELECT/REJECT/NEXT
    action_if_false: str  # SELECT/REJECT/NEXT
    
@dataclass
class SearchReport:
    """Individual search report with its population logic"""
    id: str
    name: str
    description: str
    parent_type: Optional[str]
    parent_guid: Optional[str]
    folder_id: Optional[str]
    search_date: str
    criteria_groups: List[CriteriaGroup]
    sequence: int = 1
    # Enhanced relationship tracking
    direct_dependencies: List[str] = field(default_factory=list)  # Other reports this depends on
    dependents: List[str] = field(default_factory=list)  # Reports that depend on this one
    folder_path: List[str] = field(default_factory=list)  # Full folder path
    population_type: Optional[str] = None  # PATIENT, etc. - helps distinguish searches from reports
    # Report type classification (enhanced for 4 report types)
    report_type: Optional[str] = None  # 'search', 'list', 'audit', 'aggregate'
    is_list_report: bool = False  # Legacy compatibility - True if this is a list report
    is_audit_report: bool = False  # True if this is an audit report
    is_aggregate_report: bool = False  # True if this is an aggregate report
    # Report-specific content structures
    column_groups: List[Dict] = field(default_factory=list)  # List report column definitions
    custom_aggregate: Optional[Dict] = None  # Audit report aggregation logic
    aggregate_groups: List[Dict] = field(default_factory=list)  # Aggregate report groupings
    statistical_groups: List[Dict] = field(default_factory=list)  # Statistical analysis groups
    logical_table: Optional[str] = None  # Logical table for aggregate reports
    aggregate_criteria: Optional[Dict] = None  # Built-in criteria for aggregate reports

@dataclass
class SearchRuleAnalysis:
    """Complete analysis of search rules and logic"""
    document_id: str
    creation_time: str
    reports: List[SearchReport]
    folders: List[ReportFolder]
    rule_flow: List[Dict]  # Step-by-step execution flow
    dependency_tree: Dict[str, Any]  # Complex dependency relationships
    folder_tree: Dict[str, Any]  # Folder hierarchy structure
    complexity_metrics: Dict[str, Any]

def analyze_search_rules(xml_content: str) -> SearchRuleAnalysis:
    """Parse XML content and extract complete search rule analysis"""
    try:
        root = ET.fromstring(xml_content)
        
        # Define namespaces
        namespaces = {'emis': 'http://www.e-mis.com/emisopen'}
        
        # Extract document metadata using namespace handler
        ns = NamespaceHandler()
        doc_id_elem = ns.find(root, 'id')
        doc_id = doc_id_elem.text if doc_id_elem is not None else "Unknown"
        creation_time_elem = ns.find(root, 'creationTime')
        creation_time = creation_time_elem.text if creation_time_elem is not None else "Unknown"
        
        # Parse folders first
        folders = []
        # Try both namespaced and unnamespaced folder finding
        folder_elements = root.findall('.//emis:reportFolder', namespaces)
        if not folder_elements:
            folder_elements = root.findall('.//reportFolder')
        
        for folder_elem in folder_elements:
            folder = _parse_folder(folder_elem, namespaces)
            if folder:
                folders.append(folder)
        
        # Build folder relationships and paths
        folders = _build_folder_relationships(folders)
        
        # Parse reports
        reports = []
        # Try both namespaced and unnamespaced report finding
        report_elements = root.findall('.//emis:report', namespaces)
        if not report_elements:
            report_elements = root.findall('.//report')
        
        for report_elem in report_elements:
            report = _parse_report(report_elem, namespaces, folders)
            if report:
                reports.append(report)
        
        # Build report dependency relationships
        reports = _build_report_dependencies(reports)
        
        # Map reports to folders
        folders = _map_reports_to_folders(reports, folders)
        
        # Generate folder tree structure
        folder_tree = _build_folder_tree(folders)
        
        # Generate dependency tree
        dependency_tree = _build_dependency_tree(reports)
        
        # Generate rule flow (enhanced for complex relationships)
        rule_flow = _generate_rule_flow(reports, folders)
        
        # Calculate complexity metrics
        complexity_metrics = _calculate_complexity_metrics(reports, folders)
        
        return SearchRuleAnalysis(
            document_id=doc_id,
            creation_time=creation_time,
            reports=reports,
            folders=folders,
            rule_flow=rule_flow,
            dependency_tree=dependency_tree,
            folder_tree=folder_tree,
            complexity_metrics=complexity_metrics
        )
        
    except ET.ParseError as e:
        raise Exception(f"XML parsing error: {str(e)}")
    except Exception as e:
        raise Exception(f"Error analyzing search rules: {str(e)}")

def _parse_folder(folder_elem, namespaces) -> Optional[ReportFolder]:
    """Parse folder element from XML using namespace handler"""
    try:
        ns = NamespaceHandler()
        folder_id = ns.find(folder_elem, 'id')
        name_elem = ns.find(folder_elem, 'name')
        parent_folder_elem = ns.find(folder_elem, 'parentFolder')
        sequence_elem = ns.find(folder_elem, 'sequence')
        
        return ReportFolder(
            id=folder_id.text if folder_id is not None else "Unknown",
            name=name_elem.text if name_elem is not None else "Unknown",
            parent_folder_id=parent_folder_elem.text if parent_folder_elem is not None else None,
            sequence=int(sequence_elem.text) if sequence_elem is not None else 0
        )
    except Exception:
        return None

def _parse_report(report_elem, namespaces, folders=None) -> Optional[SearchReport]:
    """Parse individual report element using namespace handler"""
    try:
        ns = NamespaceHandler()
        report_id = ns.find(report_elem, 'id')
        name_elem = ns.find(report_elem, 'name')
        desc_elem = ns.find(report_elem, 'description')
        parent_elem = ns.find(report_elem, 'parent')
        search_date_elem = ns.find(report_elem, 'searchDate')
        sequence_elem = ns.find(report_elem, 'sequence')
        folder_elem = ns.find(report_elem, 'folder')
        population_type_elem = ns.find(report_elem, 'populationType')
        
        # Use ReportParser to determine report type and structure
        report_parser = ReportParser()
        report_structure = report_parser.parse_report_structure(report_elem)
        
        # Extract parent information
        parent_type = None
        parent_guid = None
        if parent_elem is not None:
            parent_type = parent_elem.get('parentType')
            # Look for SearchIdentifier using namespace handler
            search_id_elem = ns.find(parent_elem, 'SearchIdentifier')
            if search_id_elem is not None:
                parent_guid = search_id_elem.get('reportGuid')
        
        # Override parent_type with parsed value if available
        if report_structure.get('parent_type'):
            parent_type = report_structure['parent_type']
        
        # Get report dependencies
        dependencies = report_parser.get_report_dependencies(report_elem)
        
        # Extract folder information
        folder_id = folder_elem.text if folder_elem is not None else None
        
        # Build folder path
        folder_path = []
        if folder_id and folders:
            folder_map = {f.id: f for f in folders}
            current_folder = folder_map.get(folder_id)
            while current_folder:
                folder_path.insert(0, current_folder.name)
                parent_id = current_folder.parent_folder_id
                current_folder = folder_map.get(parent_id) if parent_id else None
        
        # Parse criteria groups (from population criteria)
        criteria_groups = []
        for group_elem in report_elem.findall('.//emis:criteriaGroup', namespaces):
            group = _parse_criteria_group(group_elem, namespaces)
            if group:
                criteria_groups.append(group)
        
        # For aggregate reports, also include built-in criteria as criteria groups
        if report_structure.get('aggregate_criteria'):
            agg_criteria = report_structure['aggregate_criteria']
            for criteria_group_data in agg_criteria.get('criteria_groups', []):
                # Convert the parsed aggregate criteria to CriteriaGroup format
                criteria_objects = []
                for criterion_data in criteria_group_data.get('criteria', []):
                    # Create SearchCriterion object with source tracking
                    search_criterion = SearchCriterion(
                        id=criterion_data.get('id', ''),
                        table=criterion_data.get('table', ''),
                        display_name=criterion_data.get('display_name', ''),
                        description=criterion_data.get('description', ''),
                        negation=criterion_data.get('negation', False),
                        column_filters=criterion_data.get('column_filters', []),
                        value_sets=_add_source_tracking_to_value_sets(criterion_data.get('value_sets', []), 'report', report_structure.get('report_type', 'unknown'), name_elem.text if name_elem is not None else 'Unknown Search'),
                        restrictions=criterion_data.get('restrictions', []),
                        linked_criteria=criterion_data.get('linked_criteria', [])
                        # Note: SearchCriterion doesn't have parameters field
                    )
                    criteria_objects.append(search_criterion)
                
                # Create CriteriaGroup object
                criteria_group = CriteriaGroup(
                    id=criteria_group_data.get('id', ''),
                    member_operator=criteria_group_data.get('member_operator', 'AND'),
                    action_if_true=criteria_group_data.get('action_if_true', 'SELECT'),
                    action_if_false=criteria_group_data.get('action_if_false', 'REJECT'),
                    criteria=criteria_objects,
                    population_criteria=[]  # Aggregate reports don't typically have population criteria
                )
                criteria_groups.append(criteria_group)
        
        return SearchReport(
            id=report_id.text if report_id is not None else "Unknown",
            name=name_elem.text if name_elem is not None else "Unknown",
            description=desc_elem.text if desc_elem is not None else "",
            parent_type=parent_type,
            parent_guid=parent_guid,
            folder_id=folder_id,
            search_date=search_date_elem.text if search_date_elem is not None else "BASELINE",
            criteria_groups=criteria_groups,
            sequence=int(sequence_elem.text) if sequence_elem is not None else 1,
            folder_path=folder_path,
            population_type=population_type_elem.text if population_type_elem is not None else None,
            # Enhanced report type classification
            report_type=report_structure['report_type'],
            is_list_report=report_structure['report_type'] == 'list',
            is_audit_report=report_structure['report_type'] == 'audit',
            is_aggregate_report=report_structure['report_type'] == 'aggregate',
            # Report-specific content structures
            column_groups=report_structure['column_groups'],
            custom_aggregate=report_structure['custom_aggregate'],
            aggregate_groups=report_structure['aggregate_groups'],
            statistical_groups=report_structure['statistical_groups'],
            logical_table=report_structure.get('logical_table'),
            aggregate_criteria=report_structure.get('aggregate_criteria'),
            # Add dependencies found by parser
            direct_dependencies=dependencies
        )
    except Exception:
        return None

def _parse_criteria_group(group_elem, namespaces) -> Optional[CriteriaGroup]:
    """Parse criteria group with AND/OR logic using namespace handler"""
    try:
        ns = NamespaceHandler()
        group_id = ns.find(group_elem, 'id')
        group_id_text = group_id.text if group_id is not None else "Unknown"
        definition_elem = ns.find(group_elem, 'definition')
        action_true_elem = ns.find(group_elem, 'actionIfTrue')
        action_false_elem = ns.find(group_elem, 'actionIfFalse')
        
        if definition_elem is None:
            return None
            
        member_op_elem = ns.find(definition_elem, 'memberOperator')
        member_operator = member_op_elem.text if member_op_elem is not None else "AND"
        
        # Parse individual criteria
        criteria = []
        for criterion_elem in definition_elem.findall('./emis:criteria/emis:criterion', namespaces):
            criterion = _parse_criterion(criterion_elem, namespaces)
            if criterion:
                criteria.append(criterion)
        
        # Parse population criteria (references to other reports)
        population_criteria = []
        
        # Check both namespaced and non-namespaced elements
        namespaced_pop_criteria = definition_elem.findall('.//emis:populationCriterion', namespaces)
        non_namespaced_pop_criteria = definition_elem.findall('.//populationCriterion')
        all_pop_criteria = non_namespaced_pop_criteria + [p for p in namespaced_pop_criteria if p not in non_namespaced_pop_criteria]
        
        for pop_criterion_elem in all_pop_criteria:
            report_guid = pop_criterion_elem.get('reportGuid')
            criterion_id = pop_criterion_elem.get('id', '')
            if report_guid:
                population_criteria.append(PopulationCriterion(
                    id=criterion_id,
                    report_guid=report_guid,
                    relationship_type="population"
                ))
        
        return CriteriaGroup(
            id=group_id.text if group_id is not None else "Unknown",
            member_operator=member_operator,
            criteria=criteria,
            population_criteria=population_criteria,
            action_if_true=action_true_elem.text if action_true_elem is not None else "SELECT",
            action_if_false=action_false_elem.text if action_false_elem is not None else "REJECT"
        )
    except Exception:
        return None

def _parse_criterion(criterion_elem, namespaces) -> Optional[SearchCriterion]:
    """Parse individual search criterion using modular parser"""
    parser = CriterionParser(namespaces)
    return parser.parse_criterion(criterion_elem)

def _parse_value_set(valueset_elem, namespaces) -> Dict:
    """Parse value set information using modular parser"""
    parser = ValueSetParser(namespaces)
    return parser.parse_value_set(valueset_elem) or {}

def _parse_column_filter(column_elem, namespaces) -> Dict:
    """Parse column filter conditions using modular parser"""
    parser = CriterionParser(namespaces)
    return parser.parse_column_filter(column_elem) or {}

# _parse_range_value function removed - now handled internally by CriterionParser

def _parse_restriction(restriction_elem, namespaces) -> SearchRestriction:
    """Parse restriction elements using modular parser"""
    parser = RestrictionParser(namespaces)
    return parser.parse_restriction(restriction_elem)

def _parse_linked_criterion(linked_elem, namespaces) -> SearchCriterion:
    """Parse linked criteria using modular parser"""
    parser = LinkedCriteriaParser(namespaces)
    return parser.parse_linked_criterion(linked_elem)

def _build_folder_relationships(folders: List[ReportFolder]) -> List[ReportFolder]:
    """Build parent-child relationships between folders and generate paths"""
    folder_map = {f.id: f for f in folders}
    
    # Build child relationships
    for folder in folders:
        if folder.parent_folder_id:
            parent = folder_map.get(folder.parent_folder_id)
            if parent:
                parent.child_folder_ids.append(folder.id)
    
    # Build full paths
    for folder in folders:
        path = []
        current = folder
        while current:
            path.insert(0, current.name)
            parent_id = current.parent_folder_id
            current = folder_map.get(parent_id) if parent_id else None
        folder.path = path
    
    return folders

def _build_report_dependencies(reports: List[SearchReport]) -> List[SearchReport]:
    """Build dependency relationships between reports"""
    report_map = {r.id: r for r in reports}
    
    for report in reports:
        # Add parent dependencies
        if report.parent_guid:
            report.direct_dependencies.append(report.parent_guid)
            parent = report_map.get(report.parent_guid)
            if parent:
                parent.dependents.append(report.id)
        
        # Add populationCriterion dependencies
        for group in report.criteria_groups:
            for pop_criterion in group.population_criteria:
                if pop_criterion.report_guid not in report.direct_dependencies:
                    report.direct_dependencies.append(pop_criterion.report_guid)
                    dependency = report_map.get(pop_criterion.report_guid)
                    if dependency:
                        dependency.dependents.append(report.id)
    
    return reports

def _build_folder_tree(folders: List[ReportFolder]) -> Dict[str, Any]:
    """Build hierarchical folder tree structure"""
    folder_map = {f.id: f for f in folders}
    folder_ids = {f.id for f in folders}
    
    # Find true root folders (no parent) and orphaned folders (parent not in our list)
    root_folders = []
    for folder in folders:
        if not folder.parent_folder_id or folder.parent_folder_id not in folder_ids:
            root_folders.append(folder)
    
    def build_tree_node(folder):
        children = []
        for child_id in folder.child_folder_ids:
            child = folder_map.get(child_id)
            if child:
                children.append(build_tree_node(child))
        
        return {
            'id': folder.id,
            'name': folder.name,
            'path': folder.path,
            'report_count': len(folder.report_ids),
            'children': children
        }
    
    tree = {
        'roots': [build_tree_node(folder) for folder in root_folders],
        'total_folders': len(folders),
        'orphaned_count': len([f for f in folders if f.parent_folder_id and f.parent_folder_id not in folder_ids])
    }
    
    return tree

def _map_reports_to_folders(reports: List[SearchReport], folders: List[ReportFolder]) -> List[ReportFolder]:
    """Map reports to their containing folders"""
    folder_map = {f.id: f for f in folders}
    
    for report in reports:
        if report.folder_id:
            folder = folder_map.get(report.folder_id)
            if folder:
                folder.report_ids.append(report.id)
    
    return folders

def _build_dependency_tree(reports: List[SearchReport]) -> Dict[str, Any]:
    """Build dependency tree showing report relationships including all report types"""
    report_map = {r.id: r for r in reports}
    
    # Find reports that should be displayed as roots:
    # 1. Reports with no dependencies (true roots)
    # 2. Reports with dependencies but not referenced by anyone (orphaned dependents)
    root_reports = []
    all_referenced_ids = set()
    
    # Collect all report IDs that are referenced by others
    for report in reports:
        all_referenced_ids.update(report.dependents)
    
    # Include as roots:
    # - Reports without dependencies (traditional roots)
    # - Reports that have dependencies but are never referenced by others (leaf nodes that depend on roots)
    for report in reports:
        if not report.direct_dependencies or report.id not in all_referenced_ids:
            # This is either a true root or a leaf that should be shown
            root_reports.append(report)
    
    def build_dependency_node(report, visited=None):
        if visited is None:
            visited = set()
        
        if report.id in visited:
            return {'id': report.id, 'name': report.name, 'circular': True}
        
        visited.add(report.id)
        
        dependents = []
        for dependent_id in report.dependents:
            dependent = report_map.get(dependent_id)
            if dependent:
                dependents.append(build_dependency_node(dependent, visited.copy()))
        
        return {
            'id': report.id,
            'name': report.name,
            'folder_path': report.folder_path,
            'dependencies': report.direct_dependencies,
            'dependents': dependents,
            'complexity': len(report.criteria_groups)
        }
    
    tree = {
        'roots': [build_dependency_node(report) for report in root_reports],
        'total_reports': len(reports),
        'max_depth': _calculate_max_dependency_depth(reports)
    }
    
    return tree

def _calculate_max_dependency_depth(reports: List[SearchReport]) -> int:
    """Calculate maximum dependency chain depth"""
    report_map = {r.id: r for r in reports}
    max_depth = 0
    
    def get_depth(report, visited=None):
        if visited is None:
            visited = set()
        
        if report.id in visited:
            return 0  # Circular reference
        
        visited.add(report.id)
        
        if not report.dependents:
            return 1
        
        max_dependent_depth = 0
        for dependent_id in report.dependents:
            dependent = report_map.get(dependent_id)
            if dependent:
                depth = get_depth(dependent, visited.copy())
                max_dependent_depth = max(max_dependent_depth, depth)
        
        return 1 + max_dependent_depth
    
    for report in reports:
        if not report.direct_dependencies:  # Root report
            depth = get_depth(report)
            max_depth = max(max_depth, depth)
    
    return max_depth

def _generate_rule_flow(reports: List[SearchReport], folders: List[ReportFolder] = None) -> List[Dict]:
    """Generate step-by-step execution flow with proper parent-child hierarchy"""
    # Filter out list reports - they are output templates, not search logic
    # They shouldn't appear in search flow but can appear in structure trees
    from util_modules.core import ReportClassifier
    search_reports = ReportClassifier.filter_searches_only(reports)
    
    # Create a mapping of report IDs to reports
    report_map = {report.id: report for report in search_reports}
    
    # Find parent and child reports
    parent_reports = []
    child_reports = []
    
    for report in search_reports:
        # A report is a base population (parent) only if:
        # 1. It has parent_type 'ACTIVE' (active patient list) - these are true base populations
        # 2. It's named "All currently registered patients" or similar base population patterns
        
        # Check if this is a true base population search
        is_base_population = (
            report.parent_type == 'ACTIVE' or
            'All currently registered patients' in report.name or
            'Active patients' in report.name
        )
        
        if is_base_population:
            parent_reports.append(report)
        else:
            # Everything else is a clinical search, even if it has parent relationships
            child_reports.append(report)
    
    # Sort reports: parents first (by sequence), then children (by sequence)
    sorted_parents = sorted(parent_reports, key=lambda x: x.sequence)
    sorted_children = sorted(child_reports, key=lambda x: x.sequence)
    
    flow_steps = []
    step_number = 1
    
    # Add parent reports first
    for report in sorted_parents:
        step = {
            'step': step_number,
            'report_name': report.name,
            'report_id': report.id,
            'parent_type': report.parent_type,
            'parent_guid': report.parent_guid,
            'action': 'base_population',
            'is_parent': True,
            'criteria_groups': len(report.criteria_groups),
            'description': report.description
        }
        flow_steps.append(step)
        step_number += 1
    
    # Add child reports
    for report in sorted_children:
        # Find if this child has a parent in our current reports
        parent_report = None
        if report.parent_guid:
            parent_report = report_map.get(report.parent_guid)
        
        step = {
            'step': step_number,
            'report_name': report.name,
            'report_id': report.id,
            'parent_type': report.parent_type,
            'parent_guid': report.parent_guid,
            'parent_name': parent_report.name if parent_report else 'Unknown Parent',
            'action': 'filter_population',
            'is_parent': False,
            'criteria_groups': len(report.criteria_groups),
            'description': report.description
        }
        flow_steps.append(step)
        step_number += 1
    
    return flow_steps

def _calculate_complexity_metrics(reports: List[SearchReport], folders: List[ReportFolder] = None) -> Dict[str, Any]:
    """Calculate complexity metrics for the search"""
    # Separate searches from reports for accurate counting
    from util_modules.core import ReportClassifier, FolderManager
    search_reports = ReportClassifier.filter_searches_only(reports)
    list_reports = ReportClassifier.filter_reports_only(reports)
    
    total_criteria = sum(len(group.criteria) for report in search_reports for group in report.criteria_groups)
    total_value_sets = sum(len(criterion.value_sets) for report in search_reports for group in report.criteria_groups for criterion in group.criteria)
    total_restrictions = sum(len(criterion.restrictions) for report in search_reports for group in report.criteria_groups for criterion in group.criteria)
    linked_criteria_count = sum(len(criterion.linked_criteria) for report in search_reports for group in report.criteria_groups for criterion in group.criteria if criterion.linked_criteria)
    
    # Parameter analysis using shared function
    from ..xml_parsers.criterion_parser import check_criterion_parameters
    
    parameter_names = set()
    global_parameters = set()
    local_parameters = set()
    searches_with_parameters = set()
    
    for report in search_reports:
        report_has_parameters = False
        for group in report.criteria_groups:
            for criterion in group.criteria:
                param_info = check_criterion_parameters(criterion)
                if param_info['has_parameters']:
                    report_has_parameters = True
                    for param_name in param_info['parameter_names']:
                        parameter_names.add(param_name)
                        
                        # Note: This logic assumes all parameters in the list have the same scope
                        # If mixed scopes exist in one criterion, both flags will be True
                        if param_info['has_global']:
                            global_parameters.add(param_name)
                        if param_info['has_local']:
                            local_parameters.add(param_name)
        
        if report_has_parameters:
            searches_with_parameters.add(report.id)
    
    # Enhanced complexity metrics
    population_criteria_count = sum(len(group.population_criteria) for report in search_reports for group in report.criteria_groups)
    total_dependencies = sum(len(report.direct_dependencies) for report in search_reports)
    
    # Calculate maximum folder depth if folders exist
    max_folder_depth = 1
    if folders:
        folder_map = {f.id: f for f in folders}
        for folder in folders:
            path = FolderManager.build_full_folder_path(folder, folder_map)
            max_folder_depth = max(max_folder_depth, len(path))
    
    has_negation = any(criterion.negation for report in reports for group in report.criteria_groups for criterion in group.criteria)
    has_latest_restrictions = any(
        any(restriction.type == 'latest_records' for restriction in criterion.restrictions)
        for report in reports for group in report.criteria_groups for criterion in group.criteria
    )
    has_branching_logic = any(
        group.action_if_false == 'NEXT' for report in reports for group in report.criteria_groups
    )
    has_folders = len(folders) > 0 if folders else False
    
    # Enhanced complexity scoring (only count searches for complexity, not reports)
    complexity_score = (
        len(search_reports) * 2 +
        total_criteria * 3 +
        total_value_sets +
        total_restrictions * 2 +
        linked_criteria_count * 5 +
        population_criteria_count * 4 +  # Report dependencies add complexity
        total_dependencies * 3 +
        (len(folders) * 2 if folders else 0) +  # Folder structure adds complexity
        (max_folder_depth * 3) +  # Deeper folder structures are more complex
        (10 if has_negation else 0) +
        (5 if has_latest_restrictions else 0) +
        (15 if has_branching_logic else 0) +  # NEXT actions are complex
        (10 if has_folders else 0) +
        len(parameter_names) * 8 +  # Parameters add significant complexity (runtime user input)
        len(searches_with_parameters) * 5  # Searches using parameters are inherently more complex
    )
    
    if complexity_score < 120:
        complexity_level = "Basic"
    elif complexity_score < 250:
        complexity_level = "Moderate"
    elif complexity_score < 450:
        complexity_level = "Complex"
    else:
        complexity_level = "Very Complex"
    
    return {
        'complexity_score': complexity_score,
        'complexity_level': complexity_level,
        'total_searches': len(search_reports),
        'total_reports': len(list_reports), 
        'total_folders': len(folders) if folders else 0,
        'max_folder_depth': max_folder_depth,
        'total_criteria': total_criteria,
        'total_value_sets': total_value_sets,
        'total_restrictions': total_restrictions,
        'linked_criteria_count': linked_criteria_count,
        'population_criteria_count': population_criteria_count,
        'total_dependencies': total_dependencies,
        'interlinked_searches': len([r for r in search_reports if r.direct_dependencies or r.dependents]),
        'has_negation': has_negation,
        'has_latest_restrictions': has_latest_restrictions,
        'has_branching_logic': has_branching_logic,
        'has_folder_structure': has_folders,
        'total_parameters': len(parameter_names),
        'global_parameters': len(global_parameters),
        'local_parameters': len(local_parameters),
        'searches_with_parameters': len(searches_with_parameters),
        'parameter_names': sorted(list(parameter_names)),
        'global_parameter_names': sorted(list(global_parameters)),
        'local_parameter_names': sorted(list(local_parameters))
    }


def _add_source_tracking_to_value_sets(value_sets: List[Dict], source_type: str, report_type: str, source_name: str = None) -> List[Dict]:
    """Add source tracking information to value sets for clinical code origin tracking"""
    tracked_value_sets = []
    
    for value_set in value_sets:
        tracked_value_set = value_set.copy()
        tracked_values = []
        
        for value in value_set.get('values', []):
            tracked_value = value.copy()
            tracked_value['source_type'] = source_type  # 'search' or 'report'
            tracked_value['report_type'] = report_type  # 'search', 'aggregate', 'list', 'audit'
            tracked_value['source_name'] = source_name or 'Unknown'  # Actual name of search/report
            tracked_values.append(tracked_value)
        
        tracked_value_set['values'] = tracked_values
        tracked_value_sets.append(tracked_value_set)
    
    return tracked_value_sets
