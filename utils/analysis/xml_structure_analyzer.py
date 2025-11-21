"""
XML Structure Analyzer - Main Orchestrator
Combines search and report analysis to provide complete EMIS XML analysis.
Maintains compatibility with existing interfaces while using specialized analyzers.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from .search_analyzer import SearchAnalyzer, SearchReport
from .report_analyzer import ReportAnalyzer, Report
from .common_structures import CompleteAnalysisResult, ReportFolder
from ..core import ReportClassifier, FolderManager
from ..xml_parsers.namespace_handler import NamespaceHandler


# Legacy compatibility - expose the old SearchReport structure
@dataclass  
class LegacySearchReport:
    """Legacy SearchReport structure for backward compatibility"""
    id: str
    name: str
    description: str
    parent_type: Optional[str]
    parent_guid: Optional[str]
    folder_id: Optional[str]
    search_date: str
    criteria_groups: List[Any]
    sequence: int = 1
    
    # Enhanced relationship tracking
    direct_dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    folder_path: List[str] = field(default_factory=list)
    population_type: Optional[str] = None
    
    # Metadata fields
    creation_time: Optional[str] = None
    author: Optional[str] = None
    
    # Report type classification (enhanced for 4 report types)
    report_type: Optional[str] = None  # 'search', 'list', 'audit', 'aggregate'
    is_list_report: bool = False
    is_audit_report: bool = False
    is_aggregate_report: bool = False
    
    # Report-specific content structures (for compatibility)
    column_groups: List[Dict] = field(default_factory=list)
    custom_aggregate: Optional[Dict] = None
    aggregate_groups: List[Dict] = field(default_factory=list)
    statistical_groups: List[Dict] = field(default_factory=list)
    logical_table: Optional[str] = None
    aggregate_criteria: Optional[Dict] = None


@dataclass
class SearchRuleAnalysis:
    """Legacy analysis result structure for backward compatibility"""
    document_id: str
    creation_time: str
    reports: List[LegacySearchReport]  # Combined searches + reports for compatibility
    folders: List[ReportFolder]
    rule_flow: List[Dict]
    dependency_tree: Dict[str, Any]
    folder_tree: Dict[str, Any]
    complexity_metrics: Dict[str, Any]


def _parse_folder(folder_elem, namespaces) -> Optional[ReportFolder]:
    """Parse folder element"""
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


def _build_folder_relationships(folders: List[ReportFolder]) -> List[ReportFolder]:
    """Build parent-child relationships between folders"""
    # Already handled in individual folder creation
    return folders


def _map_reports_to_folders(all_reports: List[Union[SearchReport, Report]], folders: List[ReportFolder]) -> List[ReportFolder]:
    """Map reports to their containing folders"""
    folder_map = {f.id: f for f in folders}
    
    for report in all_reports:
        if report.folder_id:
            folder = folder_map.get(report.folder_id)
            if folder:
                folder.report_ids.append(report.id)
    
    return folders


def _build_folder_tree(folders: List[ReportFolder]) -> Dict[str, Any]:
    """Build hierarchical folder tree structure"""
    if not folders:
        return {}
    
    folder_map = {f.id: f for f in folders}
    folder_ids = {f.id for f in folders}
    
    # Find true root folders (no parent) and orphaned folders (parent not in our list)
    root_folders = []
    for folder in folders:
        if not folder.parent_folder_id or folder.parent_folder_id not in folder_ids:
            root_folders.append(folder)
    
    def build_tree_node(folder):
        # Find children of this folder
        children = []
        for other_folder in folders:
            if other_folder.parent_folder_id == folder.id:
                children.append(build_tree_node(other_folder))
        
        return {
            'id': folder.id,
            'name': folder.name,
            'report_count': len(folder.report_ids),
            'children': children
        }
    
    tree = {
        'roots': [build_tree_node(folder) for folder in root_folders],
        'total_folders': len(folders),
        'orphaned_count': len([f for f in folders if f.parent_folder_id and f.parent_folder_id not in folder_ids])
    }
    
    return tree


def analyze_search_rules(xml_content: str) -> SearchRuleAnalysis:
    """
    Main entry point for XML analysis - maintains backward compatibility
    
    Args:
        xml_content: Raw EMIS XML content
        
    Returns:
        SearchRuleAnalysis: Complete analysis results in legacy format
    """
    try:
        root = ET.fromstring(xml_content)
        namespaces = {'emis': 'http://www.e-mis.com/emisopen'}
        
        # Extract document metadata using namespace handler
        ns = NamespaceHandler()
        doc_id_elem = ns.find(root, 'id')
        doc_id = doc_id_elem.text if doc_id_elem is not None else "Unknown"
        creation_time_elem = ns.find(root, 'creationTime')
        creation_time = creation_time_elem.text if creation_time_elem is not None else "Unknown"
        
        # Parse folders first using namespace handler
        folders = []
        folder_elements = ns.findall_with_path(root, './/reportFolder')
        
        for folder_elem in folder_elements:
            folder = _parse_folder(folder_elem, namespaces)
            if folder:
                folders.append(folder)
        
        # Build folder relationships
        folders = _build_folder_relationships(folders)
        
        # Use new orchestrator for complete analysis
        from .analysis_orchestrator import AnalysisOrchestrator
        orchestrator = AnalysisOrchestrator()
        
        # Get complete analysis results using orchestrator
        orchestrated_results = orchestrator.analyze_complete_xml(xml_content)
        
        # Use orchestrated results directly (already combines searches + reports)
        all_reports = orchestrated_results.reports
        
        # Map reports to folders
        folders = _map_reports_to_folders(orchestrated_results.reports, orchestrated_results.folders)
        
        # Generate folder tree structure  
        folder_tree = _build_folder_tree(folders)
        
        # Create legacy analysis object
        analysis = SearchRuleAnalysis(
            document_id=orchestrated_results.document_id,
            creation_time=orchestrated_results.creation_time,
            reports=all_reports,
            folders=folders,
            rule_flow=orchestrated_results.rule_flow,
            dependency_tree=orchestrated_results.dependency_tree,
            folder_tree=folder_tree,
            complexity_metrics=orchestrated_results.overall_complexity
        )
        
        # Store orchestrated results for access to separate search/report analysis
        analysis.orchestrated_results = orchestrated_results
        
        # Create compatible search_results and report_results for session state
        from .search_analyzer import SearchAnalysisResult
        from .report_analyzer import ReportAnalysisResult
        
        analysis.search_results = SearchAnalysisResult(
            searches=orchestrated_results.searches,
            search_flow=orchestrated_results.search_flow,
            search_dependencies=orchestrated_results.search_dependencies,
            search_complexity=orchestrated_results.search_complexity
        )
        
        # Extract report results  
        actual_reports = [r for r in orchestrated_results.reports if hasattr(r, 'report_type')]
        if actual_reports:
            # Group by report type
            report_breakdown = {}
            for report in actual_reports:
                report_type = report.report_type
                if report_type not in report_breakdown:
                    report_breakdown[report_type] = []
                report_breakdown[report_type].append(report)
            
            analysis.report_results = ReportAnalysisResult(
                reports=actual_reports,
                report_breakdown=report_breakdown,
                report_dependencies=orchestrated_results.report_dependencies,
                clinical_codes=orchestrated_results.report_clinical_codes if hasattr(orchestrated_results, 'report_clinical_codes') else [],
                report_complexity={}
            )
        else:
            analysis.report_results = ReportAnalysisResult(
                reports=[], report_breakdown={}, report_dependencies={}, clinical_codes=[], report_complexity={}
            )
        
        return analysis
        
    except Exception as e:
        raise Exception(f"Error analyzing XML structure: {str(e)}")


def _combine_to_legacy_format_new(orchestrated_results) -> List[LegacySearchReport]:
    """Convert orchestrated results to legacy SearchReport format"""
    legacy_reports = []
    
    # Convert all reports to legacy format
    for report in orchestrated_results.reports:
        # Determine report type for legacy compatibility
        if hasattr(report, 'report_type'):
            report_type = f"[{report.report_type.title()} Report]"
        else:
            report_type = "[Search]"
        
        # Create legacy report
        legacy_report = LegacySearchReport(
            id=report.id,
            name=report.name,
            description=report.description,
            parent_type=report.parent_type,
            parent_guid=report.parent_guid,
            folder_id=report.folder_id,
            search_date=report.search_date,
            criteria_groups=report.criteria_groups,
            sequence=getattr(report, 'sequence', 1),
            direct_dependencies=report.direct_dependencies,
            dependents=getattr(report, 'dependents', []),
            folder_path=report.folder_path,
            population_type=report.population_type,
            report_type=report_type,
            creation_time=getattr(report, 'creation_time', None),
            author=getattr(report, 'author', None)
        )
        legacy_reports.append(legacy_report)
    
    return legacy_reports


def _combine_to_legacy_format(search_results, report_results) -> List[LegacySearchReport]:
    """Convert new format results to legacy SearchReport format"""
    legacy_reports = []
    
    # Convert searches
    for search in search_results.searches:
        legacy_reports.append(LegacySearchReport(
            id=search.id,
            name=search.name,
            description=search.description,
            parent_type=search.parent_type,
            parent_guid=search.parent_guid,
            folder_id=search.folder_id,
            search_date=search.search_date,
            criteria_groups=search.criteria_groups,
            sequence=search.sequence,
            direct_dependencies=search.direct_dependencies,
            dependents=search.dependents,
            folder_path=search.folder_path,
            population_type=search.population_type,
            creation_time=search.creation_time,
            author=search.author,
            report_type='search',
            is_list_report=False,
            is_audit_report=False,
            is_aggregate_report=False
        ))
    
    # Convert reports
    for report in report_results.reports:
        legacy_reports.append(LegacySearchReport(
            id=report.id,
            name=report.name,
            description=report.description,
            parent_type=report.parent_type,
            parent_guid=report.parent_guid,
            folder_id=report.folder_id,
            search_date=report.search_date,
            criteria_groups=report.criteria_groups,
            sequence=report.sequence,
            direct_dependencies=report.direct_dependencies,
            dependents=report.dependents,
            folder_path=report.folder_path,
            population_type=report.population_type,
            report_type=report.report_type,
            is_list_report=report.is_list_report,
            is_audit_report=report.is_audit_report,
            is_aggregate_report=report.is_aggregate_report,
            column_groups=report.column_groups,
            custom_aggregate=report.custom_aggregate,
            aggregate_groups=report.aggregate_groups,
            statistical_groups=report.statistical_groups,
            logical_table=report.logical_table,
            aggregate_criteria=report.aggregate_criteria
        ))
    
    return legacy_reports


def _build_complete_dependency_tree(all_entities: List) -> Dict[str, Any]:
    """Build complete dependency tree with cross-analyzer parent-child relationships"""
    def build_dependency_node(entity, visited: set = None) -> Dict[str, Any]:
        if visited is None:
            visited = set()
        
        if entity.id in visited:
            # Determine entity type for recursion prevention
            if hasattr(entity, 'report_type'):
                entity_type = f'{entity.report_type.title()} Report'
            else:
                entity_type = 'Search'
            
            return {
                'id': entity.id,
                'name': entity.name,
                'type': entity_type,
                'children': []  # Prevent infinite recursion
            }
        
        visited.add(entity.id)
        entity_map = {e.id: e for e in all_entities}
        
        # Find all entities that depend on this one (children)
        children = []
        for other_entity in all_entities:
            if entity.id in other_entity.direct_dependencies:
                children.append(build_dependency_node(other_entity, visited.copy()))
        
        # Determine entity type based on class and attributes
        if hasattr(entity, 'report_type'):
            # This is a Report from report_analyzer
            entity_type = f'{entity.report_type.title()} Report'
        else:
            # This is a SearchReport from search_analyzer
            entity_type = 'Search'
        
        return {
            'id': entity.id,
            'name': entity.name,
            'type': entity_type,
            'children': children
        }
    
    # Find root entities (no dependencies)
    root_entities = [e for e in all_entities if not e.direct_dependencies]
    
    # Calculate max depth
    def calculate_depth(entity, visited=None):
        if visited is None:
            visited = set()
        if entity.id in visited:
            return 0
        visited.add(entity.id)
        
        if not any(entity.id in other.direct_dependencies for other in all_entities):
            return 1
        
        max_child_depth = 0
        for other_entity in all_entities:
            if entity.id in other_entity.direct_dependencies:
                max_child_depth = max(max_child_depth, calculate_depth(other_entity, visited.copy()))
        
        return 1 + max_child_depth
    
    max_depth = max([calculate_depth(entity) for entity in root_entities]) if root_entities else 1
    
    return {
        'roots': [build_dependency_node(entity) for entity in root_entities],
        'total_reports': len(all_entities),
        'max_depth': max_depth
    }


def _generate_combined_rule_flow(search_results, report_results, folders: List[ReportFolder]) -> List[Dict]:
    """Generate combined rule flow from searches and reports"""
    # Include all report types - List Reports can be complex multi-column search engines
    from ..core import ReportClassifier
    
    # Combine all entities for flow analysis
    all_entities = search_results.searches + report_results.reports
    
    # Create a mapping of report IDs to entities
    entity_map = {entity.id: entity for entity in all_entities}
    
    # Find parent and child entities
    parent_entities = []
    child_entities = []
    
    for entity in all_entities:
        # An entity is a base population (parent) only if it's a true base population
        # Use the same logic as search_rule_analyzer.py for consistency
        is_base_population = (
            hasattr(entity, 'parent_type') and entity.parent_type == 'ACTIVE' or
            'All currently registered patients' in getattr(entity, 'name', '') or
            'Active patients' in getattr(entity, 'name', '')
        )
        
        if is_base_population:
            parent_entities.append(entity)
        else:
            # Everything else is a clinical search/report, even if it has no dependencies
            child_entities.append(entity)
    
    # Sort child entities by dependency complexity
    child_entities.sort(key=lambda e: len(e.direct_dependencies))
    
    # Generate flow steps
    flow = []
    
    # Add parent entities first
    for entity in parent_entities:
        entity_type = 'Search' if hasattr(entity, 'population_type') and not hasattr(entity, 'report_type') else f'{entity.report_type.title()} Report'
        flow.append({
            'report_id': entity.id,
            'report_name': entity.name,
            'report_type': entity_type,
            'action': 'Base population' if entity_type == 'Search' else 'Base report',
            'dependencies': [],
            'is_parent': True,
            'description': getattr(entity, 'description', '')
        })
    
    # Add child entities in dependency order
    for entity in child_entities:
        # Find all dependencies for this entity
        dependencies = []
        for dep_id in entity.direct_dependencies:
            parent_entity = entity_map.get(dep_id)
            if parent_entity:
                parent_type = 'Search' if hasattr(parent_entity, 'population_type') and not hasattr(parent_entity, 'report_type') else f'{parent_entity.report_type.title()} Report'
                dependencies.append({
                    'id': parent_entity.id,
                    'name': parent_entity.name,
                    'type': 'parent'
                })
        
        entity_type = 'Search' if hasattr(entity, 'population_type') and not hasattr(entity, 'report_type') else f'{entity.report_type.title()} Report'
        action = 'Filter population' if entity_type == 'Search' else f'Process {entity.report_type}'
        
        flow.append({
            'report_id': entity.id,
            'report_name': entity.name,
            'report_type': entity_type,
            'action': action,
            'dependencies': dependencies,
            'is_parent': False,
            'description': getattr(entity, 'description', '')
        })
    
    return flow


def _calculate_combined_complexity_metrics(search_results, report_results, folders: List[ReportFolder]) -> Dict[str, Any]:
    """Calculate combined complexity metrics"""
    # Start with search complexity
    search_complexity = search_results.search_complexity
    report_complexity = report_results.report_complexity
    
    # Calculate linked criteria count from search results (based on analysis_progress.md patterns)
    linked_criteria_count = 0
    total_parameters = 0
    
    # Count linked criteria from searches (cross-table relationships, date calculations)
    for search in search_results.searches:
        for criteria_group in search.criteria_groups:
            if hasattr(criteria_group, 'criteria'):
                for criterion in criteria_group.criteria:
                    # Count linked criteria based on EMIS patterns (cross-table relationships)
                    if hasattr(criterion, 'table') and criterion.table in ['MEDICATION_ISSUES', 'PATIENTS']:
                        linked_criteria_count += 1
                    # Count parameters (dynamicdate, user input)
                    if hasattr(criterion, 'filter_attributes'):
                        for attr in criterion.filter_attributes:
                            if hasattr(attr, 'parameter') or 'parameter' in str(attr):
                                total_parameters += 1
    
    # Combine metrics
    combined_metrics = {
        # Search metrics (both new names and legacy names for compatibility)
        'total_searches': search_complexity.get('total_searches', 0),
        'total_criteria': search_complexity.get('total_criteria', 0),  # Legacy name
        'search_criteria': search_complexity.get('total_criteria', 0),  # New name
        'total_value_sets': search_complexity.get('total_value_sets', 0),  # Legacy name
        'search_value_sets': search_complexity.get('total_value_sets', 0),  # New name
        'total_restrictions': search_complexity.get('total_restrictions', 0),  # Legacy name
        'search_restrictions': search_complexity.get('total_restrictions', 0),  # New name
        'total_dependencies': search_complexity.get('total_dependencies', 0),  # Legacy name
        'search_dependencies': search_complexity.get('total_dependencies', 0),  # New name
        'total_parameters': total_parameters,  # Calculated from searches
        
        # Additional search metrics expected by visualizer
        'linked_criteria_count': linked_criteria_count,  # Calculated from cross-table relationships
        'population_criteria_count': search_complexity.get('population_criteria_count', 0),
        
        # Report metrics  
        'total_reports': report_complexity.get('total_reports', 0),
        'list_reports': report_complexity.get('list_reports', 0),
        'audit_reports': report_complexity.get('audit_reports', 0),
        'aggregate_reports': report_complexity.get('aggregate_reports', 0),
        
        # Combined totals
        'total_entities': search_complexity.get('total_searches', 0) + report_complexity.get('total_reports', 0),
        'total_folders': len(folders),
        
        # Quality indicators
        'has_negation': search_complexity.get('has_negation', False),
        'has_latest_restrictions': search_complexity.get('has_latest_restrictions', False),
        'has_branching_logic': search_complexity.get('has_branching_logic', False),
        'has_folders': len(folders) > 0,
        
        # Averages
        'average_criteria_per_search': search_complexity.get('average_criteria_per_search', 0),
        'entities_with_dependencies': search_complexity.get('searches_with_dependencies', 0) + len([r for r in report_results.reports if r.direct_dependencies])
    }
    
    # Add report-specific metrics if available
    if 'list_report_columns' in report_complexity:
        combined_metrics['list_report_columns'] = report_complexity['list_report_columns']
    if 'aggregate_report_groups' in report_complexity:
        combined_metrics['aggregate_report_groups'] = report_complexity['aggregate_report_groups']
    if 'audit_reports_with_aggregation' in report_complexity:
        combined_metrics['audit_reports_with_aggregation'] = report_complexity['audit_reports_with_aggregation']
    
    # Calculate folder depth if folders exist
    max_folder_depth = 1
    if folders:
        folder_map = {f.id: f for f in folders}
        for folder in folders:
            depth = 1
            current = folder
            while current.parent_folder_id:
                current = folder_map.get(current.parent_folder_id)
                if current:
                    depth += 1
                else:
                    break
            max_folder_depth = max(max_folder_depth, depth)
    
    combined_metrics['max_folder_depth'] = max_folder_depth
    
    # Calculate complexity score (based on original search_rule_analyzer logic)
    # Only count searches for complexity scoring, not reports (reports are output templates)
    total_searches = combined_metrics['total_searches']
    search_criteria = combined_metrics['search_criteria']
    search_value_sets = combined_metrics['search_value_sets']
    search_restrictions = combined_metrics['search_restrictions']
    search_dependencies = combined_metrics['search_dependencies']
    has_negation = combined_metrics['has_negation']
    has_latest_restrictions = combined_metrics['has_latest_restrictions']
    has_branching_logic = combined_metrics['has_branching_logic']
    has_folders = combined_metrics['has_folders']
    
    # Enhanced complexity scoring (focused on search complexity)
    complexity_score = (
        total_searches * 2 +
        search_criteria * 3 +
        search_value_sets +
        search_restrictions * 2 +
        search_dependencies * 4 +  # Dependencies add complexity
        (5 if has_negation else 0) +
        (8 if has_latest_restrictions else 0) +
        (15 if has_branching_logic else 0) +
        (10 if has_folders else 0)
        # Note: Parameters and linked criteria would need search-level analysis to calculate
    )
    
    # Determine complexity level
    if complexity_score < 120:
        complexity_level = "Basic"
    elif complexity_score < 250:
        complexity_level = "Moderate"
    elif complexity_score < 450:
        complexity_level = "Complex"
    else:
        complexity_level = "Very Complex"
    
    # Add complexity scoring to metrics
    combined_metrics['complexity_score'] = complexity_score
    combined_metrics['complexity_level'] = complexity_level
    
    return combined_metrics
