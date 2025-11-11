"""
Analysis Orchestrator - Coordinates the complete XML analysis flow
Handles initial classification and orchestrates specialized analyzers
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from .xml_element_classifier import XMLElementClassifier, ClassifiedElements
from .search_analyzer import SearchAnalyzer, SearchAnalysisResult
from .report_analyzer import ReportAnalyzer, ReportAnalysisResult
from .common_structures import CompleteAnalysisResult, ReportFolder


class AnalysisOrchestrator:
    """Orchestrates the complete XML analysis process"""
    
    def __init__(self):
        self.classifier = XMLElementClassifier()
        self.search_analyzer = SearchAnalyzer()
        self.report_analyzer = ReportAnalyzer()
    
    def analyze_complete_xml(self, xml_content: str) -> CompleteAnalysisResult:
        """
        Perform complete analysis of XML content
        
        Args:
            xml_content: Raw XML content
            
        Returns:
            CompleteAnalysisResult with combined search and report analysis
        """
        try:
            # Step 1: Classify all elements by type
            classified = self.classifier.classify_elements(xml_content)
            
            # Step 2: Analyze searches if any exist
            search_results = None
            if classified.search_elements:
                search_results = self.search_analyzer.analyze_searches(
                    classified.search_elements, 
                    classified.namespaces, 
                    classified.folders
                )
            
            # Step 3: Analyze reports if any exist  
            report_results = None
            if classified.audit_elements or classified.list_elements or classified.aggregate_elements:
                # Combine all report elements
                all_report_elements = (classified.audit_elements + 
                                     classified.list_elements + 
                                     classified.aggregate_elements)
                
                report_results = self.report_analyzer.analyze_reports(
                    all_report_elements,
                    classified.namespaces,
                    classified.folders
                )
            
            # Step 4: Combine results
            combined_results = self._combine_analysis_results(
                classified, search_results, report_results
            )
            
            return combined_results
            
        except Exception as e:
            raise Exception(f"Error in analysis orchestration: {str(e)}")
    
    def _combine_analysis_results(self, 
                                classified: ClassifiedElements,
                                search_results: Optional[SearchAnalysisResult],
                                report_results: Optional[ReportAnalysisResult]) -> CompleteAnalysisResult:
        """Combine results from different analyzers"""
        
        # Combine all reports (searches + reports) for UI compatibility
        all_reports = []
        if search_results:
            all_reports.extend(search_results.searches)
        if report_results:
            all_reports.extend(report_results.reports)
        
        # Generate combined dependency tree
        combined_dependencies = self._build_combined_dependency_tree(
            search_results, report_results
        )
        
        # Generate combined rule flow
        combined_rule_flow = self._build_combined_rule_flow(
            search_results, report_results
        )
        
        # Calculate overall complexity
        overall_complexity = self._calculate_overall_complexity(
            search_results, report_results
        )
        
        return CompleteAnalysisResult(
            # Document metadata
            document_id=classified.document_id,
            creation_time=classified.creation_time,
            
            # Folder structure (shared)
            folders=classified.folders,
            folder_tree=classified.folder_tree,
            
            # Search analysis results
            searches=search_results.searches if search_results else [],
            search_flow=search_results.search_flow if search_results else [],
            search_dependencies=search_results.search_dependencies if search_results else {},
            search_complexity=search_results.search_complexity if search_results else {},
            
            # Report analysis results  
            reports=all_reports,  # Combined for UI compatibility
            report_dependencies=report_results.report_dependencies if report_results else {},
            report_clinical_codes=report_results.clinical_codes if report_results else [],
            
            # Combined metrics
            overall_complexity=overall_complexity,
            dependency_tree=combined_dependencies,
            rule_flow=combined_rule_flow
        )
    
    def _build_combined_dependency_tree(self, 
                                      search_results: Optional[SearchAnalysisResult],
                                      report_results: Optional[ReportAnalysisResult]) -> Dict[str, Any]:
        """Build truly integrated dependency tree with searches as parents of reports when appropriate"""
        combined_tree = {
            'roots': [],
            'total_items': 0,
            'max_depth': 1
        }
        
        # Create maps for easier lookups
        search_map = {}
        report_map = {}
        
        if search_results and search_results.searches:
            search_map = {s.id: s for s in search_results.searches}
            combined_tree['total_items'] += len(search_results.searches)
        
        if report_results and report_results.reports:
            report_map = {r.id: r for r in report_results.reports}
            combined_tree['total_items'] += len(report_results.reports)
        
        # Build integrated tree where searches can be parents of reports
        all_entities = list(search_map.values()) + list(report_map.values())
        
        # Track which entities are children so we don't add them as roots
        child_entity_ids = set()
        
        for entity in all_entities:
            parent_guid = getattr(entity, 'parent_guid', None)
            if parent_guid and (parent_guid in search_map or parent_guid in report_map):
                child_entity_ids.add(entity.id)
        
        # Only add entities as roots if they're not children of other entities
        for entity in all_entities:
            if entity.id not in child_entity_ids:
                combined_tree['roots'].append(self._create_combined_node(entity, search_map, report_map, all_entities))
        
        # Calculate max depth
        combined_tree['max_depth'] = self._calculate_combined_max_depth(combined_tree['roots'])
        
        return combined_tree
    
    def _create_combined_node(self, entity, search_map: Dict, report_map: Dict, all_entities: List, visited: set = None) -> Dict[str, Any]:
        """Create a dependency node that can contain both searches and reports"""
        if visited is None:
            visited = set()
        
        if entity.id in visited:
            return {'id': entity.id, 'name': entity.name, 'circular': True}
        
        visited.add(entity.id)
        
        # Determine entity type and create base node
        if hasattr(entity, 'report_type'):
            # This is a report - clean up the type display
            clean_type = entity.report_type.strip('[]').title()
            node = {
                'id': entity.id,
                'name': entity.name,
                'type': clean_type,
                'children': []
            }
        else:
            # This is a search
            node = {
                'id': entity.id,
                'name': entity.name,
                'type': 'Search',
                'children': []
            }
        
        # Find children (entities that have this entity as parent)
        for child_entity in all_entities:
            child_parent_guid = getattr(child_entity, 'parent_guid', None)
            if child_parent_guid == entity.id and child_entity.id not in visited:
                child_node = self._create_combined_node(child_entity, search_map, report_map, all_entities, visited.copy())
                node['children'].append(child_node)
        
        return node
    
    def _calculate_combined_max_depth(self, roots: List[Dict]) -> int:
        """Calculate maximum depth of combined dependency tree"""
        if not roots:
            return 1
        
        def get_depth(node: Dict) -> int:
            children = node.get('children', [])
            if not children:
                return 1
            return 1 + max(get_depth(child) for child in children)
        
        return max(get_depth(root) for root in roots)
    
    def _update_report_dependencies_with_search_names(self, combined_tree: Dict, search_results: SearchAnalysisResult):
        """Update report dependency tree with proper search names from search analysis"""
        if not hasattr(search_results, 'searches') or not search_results.searches:
            return
        
        # Create GUID to name mapping from searches
        search_name_map = {}
        for search in search_results.searches:
            if hasattr(search, 'id') and hasattr(search, 'name'):
                search_name_map[search.id] = search.name
        
        # Update the report dependency tree with proper search names
        def update_children_names(node):
            if 'children' in node and node['children']:
                for child in node['children']:
                    if child.get('type') == 'Search' and child.get('id') in search_name_map:
                        child['name'] = search_name_map[child['id']]
                    update_children_names(child)
        
        # Apply to all roots
        for root in combined_tree.get('roots', []):
            update_children_names(root)
    
    def _build_combined_rule_flow(self,
                                search_results: Optional[SearchAnalysisResult],
                                report_results: Optional[ReportAnalysisResult]) -> List[Dict]:
        """Build combined execution flow from both analyzers"""
        combined_flow = []
        
        if search_results and search_results.search_flow:
            # Add search flow items with proper labeling
            for item in search_results.search_flow:
                flow_item = item.copy()
                flow_item['source_analyzer'] = 'search'
                combined_flow.append(flow_item)
        
        # Note: Report flow would be added here if ReportAnalyzer generates flow
        
        return combined_flow
    
    def _calculate_overall_complexity(self,
                                    search_results: Optional[SearchAnalysisResult],
                                    report_results: Optional[ReportAnalysisResult]) -> Dict[str, Any]:
        """Calculate overall complexity metrics"""
        complexity = {
            'classification': 'Basic',
            'complexity_level': 'Basic',  # For UI compatibility
            'complexity_score': 0,        # For UI compatibility
            'total_items': 0,
            'search_complexity': {},
            'report_complexity': {},
            'combined_metrics': {}
        }
        
        # Add search complexity
        if search_results and search_results.search_complexity:
            search_complexity = search_results.search_complexity
            complexity['search_complexity'] = search_complexity
            complexity['total_items'] += search_complexity.get('total_searches', 0)
            
            # Copy key metrics from search complexity for UI compatibility
            complexity.update({
                'total_searches': search_complexity.get('total_searches', 0),
                'total_criteria': search_complexity.get('total_criteria', 0),
                'total_value_sets': search_complexity.get('total_value_sets', 0),
                'total_restrictions': search_complexity.get('total_restrictions', 0),
                'linked_criteria_count': search_complexity.get('linked_criteria_count', 0),
                'population_criteria_count': search_complexity.get('population_criteria_count', 0),
                'total_dependencies': search_complexity.get('total_dependencies', 0),
                'total_folders': search_complexity.get('total_folders', 0),
                'total_parameters': search_complexity.get('total_parameters', 0),
                'searches_with_parameters': search_complexity.get('searches_with_parameters', 0),
                'global_parameters': search_complexity.get('global_parameters', 0),
                'local_parameters': search_complexity.get('local_parameters', 0),
                'interlinked_searches': search_complexity.get('interlinked_searches', 0),
                'max_folder_depth': search_complexity.get('max_folder_depth', 0),
                # Boolean flags
                'has_negation': search_complexity.get('has_negation', False),
                'has_latest_restrictions': search_complexity.get('has_latest_restrictions', False),
                'has_branching_logic': search_complexity.get('has_branching_logic', False),
                'has_folder_structure': search_complexity.get('has_folder_structure', False),
                # Parameter lists
                'parameter_names': search_complexity.get('parameter_names', []),
                'global_parameter_names': search_complexity.get('global_parameter_names', []),
                'local_parameter_names': search_complexity.get('local_parameter_names', [])
            })
        
        # Add report complexity (if available)
        if report_results and hasattr(report_results, 'report_complexity'):
            report_complexity = report_results.report_complexity
            complexity['report_complexity'] = report_complexity
            complexity['total_items'] += len(report_results.reports)
            
            # Add report-specific metrics for UI compatibility
            if report_complexity:
                complexity.update({
                    'total_reports': report_complexity.get('total_reports', len(report_results.reports)),
                    'list_reports': report_complexity.get('list_reports', 0),
                    'audit_reports': report_complexity.get('audit_reports', 0),
                    'aggregate_reports': report_complexity.get('aggregate_reports', 0),
                    'list_report_columns': report_complexity.get('list_report_columns', 0),
                    'audit_reports_with_aggregation': report_complexity.get('audit_reports_with_aggregation', 0),
                    'aggregate_report_groups': report_complexity.get('aggregate_report_groups', 0),
                    'aggregate_statistical_groups': report_complexity.get('aggregate_statistical_groups', 0)
                })
        
        # Use search complexity score if available, otherwise fallback to item count
        score = complexity['total_items']
        if search_results and search_results.search_complexity:
            # Use the detailed complexity score from search analyzer if available
            detailed_score = search_results.search_complexity.get('complexity_score', 0)
            if detailed_score > 0:
                score = detailed_score
        
        # Use search analyzer's complexity level if available, otherwise calculate from item count
        level = 'Basic'
        if search_results and search_results.search_complexity:
            level = search_results.search_complexity.get('complexity_level', 'Basic')
        else:
            # Fallback to simple item-based classification
            if complexity['total_items'] > 20:
                level = 'Complex'
            elif complexity['total_items'] > 10:
                level = 'Moderate'
        
        # Set both classification fields for compatibility
        complexity['classification'] = level
        complexity['complexity_level'] = level
        complexity['complexity_score'] = score
        
        return complexity
    
    def get_analysis_summary(self, results: CompleteAnalysisResult) -> Dict[str, Any]:
        """Get summary of complete analysis"""
        return {
            'document_info': {
                'document_id': results.document_id,
                'creation_time': results.creation_time,
                'total_folders': len(results.folders)
            },
            'element_counts': {
                'total_searches': len(results.searches),
                'total_reports': len([r for r in results.reports if hasattr(r, 'report_type')]),
                'total_items': len(results.reports)
            },
            'complexity': {
                'classification': results.overall_complexity.get('classification', 'Basic'),
                'total_items': results.overall_complexity.get('total_items', 0)
            },
            'structure': {
                'max_dependency_depth': results.dependency_tree.get('max_depth', 1),
                'has_folders': len(results.folders) > 0,
                'execution_flow_items': len(results.rule_flow)
            }
        }