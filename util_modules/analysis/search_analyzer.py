"""
Search Analyzer - Focused on EMIS Search Analysis
Handles population logic, criteria groups, and search-specific operations.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from ..xml_parsers.criterion_parser import SearchCriterion, CriterionParser
from ..xml_parsers.namespace_handler import NamespaceHandler
from .common_structures import CriteriaGroup, PopulationCriterion, ReportFolder


@dataclass
class SearchReport:
    """Individual search report focused on population logic"""
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
    direct_dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    folder_path: List[str] = field(default_factory=list)
    population_type: Optional[str] = None
    # Metadata fields
    creation_time: Optional[str] = None
    author: Optional[str] = None


@dataclass 
class SearchAnalysisResult:
    """Results from search-only analysis"""
    searches: List[SearchReport]
    search_flow: List[Dict]
    search_dependencies: Dict[str, Any]
    search_complexity: Dict[str, Any]


class SearchAnalyzer:
    """Analyzes EMIS search population logic and criteria"""
    
    def __init__(self):
        self.criterion_parser = CriterionParser()
        self.ns = NamespaceHandler()
    
    def analyze_searches(self, search_elements: List[ET.Element], namespaces: Dict, folders: List[ReportFolder] = None) -> SearchAnalysisResult:
        """
        Analyze pre-filtered search elements
        
        Args:
            search_elements: Pre-filtered search report elements
            namespaces: XML namespaces
            folders: Parsed folder structure
            
        Returns:
            SearchAnalysisResult containing search-only analysis
        """
        try:
            # Parse search elements
            searches = self._parse_search_elements(search_elements, namespaces, folders)
            
            # Build search relationships
            searches = self._build_search_dependencies(searches)
            
            # Generate search flow
            search_flow = self._generate_search_flow(searches)
            
            # Calculate search complexity
            search_complexity = self._calculate_search_complexity(searches)
            
            # Build search dependency tree
            search_dependencies = self._build_search_dependency_tree(searches)
            
            return SearchAnalysisResult(
                searches=searches,
                search_flow=search_flow,
                search_dependencies=search_dependencies,
                search_complexity=search_complexity
            )
            
        except Exception as e:
            raise Exception(f"Error analyzing searches: {str(e)}")
    
    def _parse_search_elements(self, search_elements: List[ET.Element], namespaces: Dict, folders: List[ReportFolder] = None) -> List[SearchReport]:
        """Parse pre-filtered search elements"""
        searches = []
        
        for search_elem in search_elements:
            search = self._parse_search_report(search_elem, namespaces, folders)
            if search:
                searches.append(search)
        
        return searches
    
    def _parse_search_report(self, report_elem: ET.Element, namespaces: Dict, folders: List[ReportFolder] = None) -> Optional[SearchReport]:
        """Parse individual search report"""
        try:
            # Extract basic elements using namespace handler
            report_id = self.ns.find(report_elem, 'id')
            name_elem = self.ns.find(report_elem, 'name')
            desc_elem = self.ns.find(report_elem, 'description')
            parent_elem = self.ns.find(report_elem, 'parent')
            search_date_elem = self.ns.find(report_elem, 'searchDate')
            sequence_elem = self.ns.find(report_elem, 'sequence')
            folder_elem = self.ns.find(report_elem, 'folder')
            population_type_elem = self.ns.find(report_elem, 'populationType')
            
            # Extract metadata elements using namespace handler
            creation_time_elem = self.ns.find(report_elem, 'creationTime')
            author_elem = self.ns.find(report_elem, 'author')
            
            # Extract parent information
            parent_type = None
            parent_guid = None
            if parent_elem is not None:
                parent_type = parent_elem.get('parentType')
                # Look for SearchIdentifier using namespace handler
                search_id_elem = self.ns.find(parent_elem, 'SearchIdentifier')
                if search_id_elem is not None:
                    parent_guid = search_id_elem.get('reportGuid')
            
            # Get dependencies (extract directly from parent element)
            dependencies = []
            if parent_guid:
                dependencies.append(parent_guid)
            
            # Build folder path
            folder_id = folder_elem.text if folder_elem is not None else None
            folder_path = self._build_folder_path(folder_id, folders)
            
            # Parse criteria groups (population criteria only)
            criteria_groups = self._parse_search_criteria_groups(report_elem, namespaces)
            
            # Extract author information
            author_name = None
            if author_elem is not None:
                # Check for authorName first (preferred format) using namespace handler
                author_name_elem = self.ns.find(author_elem, 'authorName')
                if author_name_elem is not None:
                    author_name = author_name_elem.text
                else:
                    # Fall back to userInRole GUID if authorName not available
                    user_role_elem = self.ns.find(author_elem, 'userInRole')
                    if user_role_elem is not None:
                        author_name = f"User Role: {user_role_elem.text}"  # Show as role rather than raw GUID
            
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
                direct_dependencies=dependencies,
                creation_time=creation_time_elem.text if creation_time_elem is not None else None,
                author=author_name
            )
            
        except Exception:
            return None
    
    def _parse_search_criteria_groups(self, report_elem: ET.Element, namespaces: Dict) -> List[CriteriaGroup]:
        """Parse criteria groups for search population logic"""
        criteria_groups = []
        
        for group_elem in report_elem.findall('.//emis:criteriaGroup', namespaces):
            group = self._parse_criteria_group(group_elem, namespaces)
            if group:
                criteria_groups.append(group)
        
        return criteria_groups
    
    def _parse_criteria_group(self, group_elem: ET.Element, namespaces: Dict) -> Optional[CriteriaGroup]:
        """Parse individual criteria group"""
        try:
            group_id = self.ns.find(group_elem, 'id')
            definition_elem = self.ns.find(group_elem, 'definition')
            action_true_elem = self.ns.find(group_elem, 'actionIfTrue')
            action_false_elem = self.ns.find(group_elem, 'actionIfFalse')
            
            if definition_elem is None:
                return None
                
            member_op_elem = self.ns.find(definition_elem, 'memberOperator')
            member_operator = member_op_elem.text if member_op_elem is not None else "AND"
            
            # Parse individual criteria
            criteria = []
            
            # Handle both direct criterion elements and criterion elements wrapped in criteria elements
            # Pattern 1: Direct criterion elements under definition
            for criterion_elem in definition_elem.findall('.//emis:criterion', namespaces):
                criterion = self.criterion_parser.parse_criterion(criterion_elem)
                if criterion:
                    criteria.append(criterion)
            
            # Pattern 2: Criterion elements wrapped in criteria elements (patient demographics pattern)
            # Look for <criteria><criterion> patterns
            criteria_elements = self.ns.findall_with_path(definition_elem, 'criteria')
            for criteria_elem in criteria_elements:
                criterion_elems = self.ns.findall_with_path(criteria_elem, 'criterion')
                for criterion_elem in criterion_elems:
                    criterion = self.criterion_parser.parse_criterion(criterion_elem)
                    if criterion:
                        criteria.append(criterion)
            
            # Process patient demographics criteria grouping if detected
            criteria = self._group_patient_demographics_criteria(criteria, member_operator)
            
            # Parse population criteria (references to other searches)
            population_criteria = []
            pop_criteria_elements = self.ns.findall_with_path(definition_elem, './/populationCriterion')
            
            for pop_elem in pop_criteria_elements:
                pop_criterion = self._parse_population_criterion(pop_elem, namespaces)
                if pop_criterion:
                    population_criteria.append(pop_criterion)
            
            return CriteriaGroup(
                id=group_id.text if group_id is not None else "",
                member_operator=member_operator,
                action_if_true=action_true_elem.text if action_true_elem is not None else "SELECT",
                action_if_false=action_false_elem.text if action_false_elem is not None else "REJECT",
                criteria=criteria,
                population_criteria=population_criteria
            )
            
        except Exception:
            return None
    
    def _parse_population_criterion(self, pop_elem: ET.Element, namespaces: Dict) -> Optional[PopulationCriterion]:
        """Parse population criterion (reference to another search)"""
        try:
            pop_id = self.ns.find(pop_elem, 'id')
            report_guid = pop_elem.get('reportGuid', '')
            
            return PopulationCriterion(
                id=self.ns.get_text(pop_id),
                report_guid=report_guid
            )
        except Exception:
            return None
    
    def _build_folder_path(self, folder_id: str, folders: List[ReportFolder] = None) -> List[str]:
        """Build full folder path for a search"""
        if not folder_id or not folders:
            return []
            
        folder_map = {f.id: f for f in folders}
        folder_path = []
        current_folder = folder_map.get(folder_id)
        
        while current_folder:
            folder_path.insert(0, current_folder.name)
            parent_id = current_folder.parent_folder_id
            current_folder = folder_map.get(parent_id) if parent_id else None
        
        return folder_path
    
    def _build_search_dependencies(self, searches: List[SearchReport]) -> List[SearchReport]:
        """Build dependency relationships between searches"""
        search_map = {s.id: s for s in searches}
        
        for search in searches:
            # Add parent dependencies
            if search.parent_guid:
                search.direct_dependencies.append(search.parent_guid)
                parent = search_map.get(search.parent_guid)
                if parent:
                    parent.dependents.append(search.id)
            
            # Add population criterion dependencies
            for group in search.criteria_groups:
                for pop_criterion in group.population_criteria:
                    if pop_criterion.report_guid not in search.direct_dependencies:
                        search.direct_dependencies.append(pop_criterion.report_guid)
                        dependency = search_map.get(pop_criterion.report_guid)
                        if dependency:
                            dependency.dependents.append(search.id)
        
        return searches
    
    def _generate_search_flow(self, searches: List[SearchReport]) -> List[Dict]:
        """Generate step-by-step search execution flow"""
        # Find parent searches (those that don't depend on other searches)
        parent_searches = [s for s in searches if not s.direct_dependencies]
        
        # Find child searches and sort by dependencies
        child_searches = [s for s in searches if s.direct_dependencies]
        child_searches.sort(key=lambda s: len(s.direct_dependencies))
        
        flow = []
        search_map = {search.id: search for search in searches}
        
        # Add parent searches first
        for search in parent_searches:
            flow.append({
                'report_id': search.id,
                'report_name': search.name,
                'report_type': 'Search',
                'action': 'Base population',
                'dependencies': []
            })
        
        # Add child searches in dependency order
        for search in child_searches:
            dependencies = []
            if search.parent_guid:
                parent_search = search_map.get(search.parent_guid)
                if parent_search:
                    dependencies.append({
                        'id': parent_search.id,
                        'name': parent_search.name,
                        'type': 'parent'
                    })
            
            flow.append({
                'report_id': search.id,
                'report_name': search.name,
                'report_type': 'Search',
                'action': 'Filter population',
                'dependencies': dependencies
            })
        
        return flow
    
    def _calculate_search_complexity(self, searches: List[SearchReport]) -> Dict[str, Any]:
        """Calculate complexity metrics for searches"""
        if not searches:
            return {}
        
        total_criteria = sum(len(group.criteria) for search in searches for group in search.criteria_groups)
        total_value_sets = sum(
            len(criterion.value_sets) 
            for search in searches 
            for group in search.criteria_groups 
            for criterion in group.criteria
        )
        total_restrictions = sum(
            len(criterion.restrictions) 
            for search in searches 
            for group in search.criteria_groups 
            for criterion in group.criteria
        )
        population_criteria_count = sum(
            len(group.population_criteria) 
            for search in searches 
            for group in search.criteria_groups
        )
        total_dependencies = sum(len(search.direct_dependencies) for search in searches)
        
        has_negation = any(
            criterion.negation 
            for search in searches 
            for group in search.criteria_groups 
            for criterion in group.criteria
        )
        has_latest_restrictions = any(
            any(restriction.type == 'latest_records' for restriction in criterion.restrictions)
            for search in searches 
            for group in search.criteria_groups 
            for criterion in group.criteria
        )
        has_branching_logic = any(
            group.action_if_false == 'NEXT' 
            for search in searches 
            for group in search.criteria_groups
        )
        
        return {
            'total_searches': len(searches),
            'total_criteria': total_criteria,
            'total_value_sets': total_value_sets,
            'total_restrictions': total_restrictions,
            'population_criteria_count': population_criteria_count,
            'total_dependencies': total_dependencies,
            'has_negation': has_negation,
            'has_latest_restrictions': has_latest_restrictions,
            'has_branching_logic': has_branching_logic,
            'average_criteria_per_search': total_criteria / len(searches) if searches else 0,
            'searches_with_dependencies': len([s for s in searches if s.direct_dependencies])
        }
    
    def _build_search_dependency_tree(self, searches: List[SearchReport]) -> Dict[str, Any]:
        """Build dependency tree for searches"""
        def build_dependency_node(search: SearchReport, visited: set = None) -> Dict[str, Any]:
            if visited is None:
                visited = set()
            
            if search.id in visited:
                return {'id': search.id, 'name': search.name, 'circular': True}
            
            visited.add(search.id)
            search_map = {s.id: s for s in searches}
            
            children = []
            for dep_id in search.dependents:
                dependent = search_map.get(dep_id)
                if dependent:
                    children.append(build_dependency_node(dependent, visited.copy()))
            
            return {
                'id': search.id,
                'name': search.name,
                'type': 'Search',
                'children': children
            }
        
        # Find root searches (no dependencies)
        root_searches = [s for s in searches if not s.direct_dependencies]
        
        return {
            'roots': [build_dependency_node(search) for search in root_searches],
            'total_searches': len(searches),
            'max_depth': self._calculate_max_search_depth(searches)
        }
    
    def _calculate_max_search_depth(self, searches: List[SearchReport]) -> int:
        """Calculate maximum dependency depth for searches"""
        search_map = {s.id: s for s in searches}
        max_depth = 1
        
        def get_depth(search: SearchReport, visited: set = None) -> int:
            if visited is None:
                visited = set()
            
            if search.id in visited:
                return 0  # Circular reference
            
            visited.add(search.id)
            
            if not search.dependents:
                return 1
            
            max_dependent_depth = 0
            for dep_id in search.dependents:
                dependent = search_map.get(dep_id)
                if dependent:
                    depth = get_depth(dependent, visited.copy())
                    max_dependent_depth = max(max_dependent_depth, depth)
            
            return 1 + max_dependent_depth
        
        for search in searches:
            if not search.direct_dependencies:  # Root search
                depth = get_depth(search)
                max_depth = max(max_depth, depth)
        
        return max_depth
    
    def _group_patient_demographics_criteria(self, criteria: List[SearchCriterion], member_operator: str) -> List[SearchCriterion]:
        """
        Group patient demographics criteria that share the same criterion ID but have different demographic values.
        
        This handles the LSOA pattern where multiple criteria have the same ID but different area codes.
        """
        if not criteria:
            return criteria
        
        # Group criteria by ID and check for patient demographics patterns
        id_groups = {}
        non_demographics = []
        
        for criterion in criteria:
            # Check if this criterion has patient demographics column filters
            has_demographics = False
            demographics_values = []
            
            for column_filter in criterion.column_filters:
                if column_filter.get('column_type') == 'patient_demographics':
                    has_demographics = True
                    # Extract the demographics value from the range
                    range_data = column_filter.get('range', {})
                    from_data = range_data.get('from', {})
                    value = from_data.get('value')
                    if value:
                        demographics_values.append(value)
            
            if has_demographics and demographics_values:
                # This is a patient demographics criterion - group by ID
                if criterion.id not in id_groups:
                    id_groups[criterion.id] = {
                        'base_criterion': criterion,
                        'demographics_values': demographics_values.copy(),
                        'all_criteria': [criterion]
                    }
                else:
                    # Add demographics values to existing group
                    id_groups[criterion.id]['demographics_values'].extend(demographics_values)
                    id_groups[criterion.id]['all_criteria'].append(criterion)
            else:
                # Non-demographics criterion - keep as-is
                non_demographics.append(criterion)
        
        # Build result list
        result = non_demographics.copy()
        
        for group_id, group_data in id_groups.items():
            base_criterion = group_data['base_criterion']
            all_values = group_data['demographics_values']
            
            if len(all_values) > 1:
                # Multiple demographics values - create enhanced criterion with grouped values
                enhanced_criterion = SearchCriterion(
                    id=base_criterion.id,
                    table=base_criterion.table,
                    display_name=base_criterion.display_name,
                    description=base_criterion.description,
                    negation=base_criterion.negation,
                    value_sets=base_criterion.value_sets,
                    column_filters=base_criterion.column_filters.copy(),
                    restrictions=base_criterion.restrictions,
                    exception_code=base_criterion.exception_code,
                    linked_criteria=base_criterion.linked_criteria
                )
                
                # Add metadata about demographics grouping
                if enhanced_criterion.column_filters:
                    for column_filter in enhanced_criterion.column_filters:
                        if column_filter.get('column_type') == 'patient_demographics':
                            column_filter['grouped_demographics_values'] = all_values
                            column_filter['demographics_count'] = len(all_values)
                            column_filter['demographics_operator'] = member_operator
                
                result.append(enhanced_criterion)
            else:
                # Single demographics value - keep original
                result.append(base_criterion)
        
        return result
