"""
Common Data Structures for Analysis
Shared between search and report analyzers to ensure consistency.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from ..xml_parsers.criterion_parser import SearchCriterion


@dataclass
class PopulationCriterion:
    """Reference to another report for population criteria"""
    id: str
    report_guid: str


@dataclass
class CriteriaGroup:
    """Group of criteria with AND/OR logic"""
    id: str
    member_operator: str  # AND/OR
    criteria: List[SearchCriterion]
    population_criteria: List[PopulationCriterion]
    action_if_true: str  # SELECT/REJECT/NEXT
    action_if_false: str  # SELECT/REJECT/NEXT


@dataclass
class ReportFolder:
    """Report folder structure"""
    id: str
    name: str
    parent_folder_id: Optional[str] = None
    sequence: int = 0
    report_ids: List[str] = field(default_factory=list)


@dataclass
class CompleteAnalysisResult:
    """Combined results from search and report analysis"""
    # Document metadata
    document_id: str
    creation_time: str
    
    # Folder structure (shared)
    folders: List[ReportFolder]
    folder_tree: Dict[str, Any]
    
    # Search analysis results
    searches: List[Any]  # Will be SearchReport from search_analyzer
    search_flow: List[Dict]
    search_dependencies: Dict[str, Any]
    search_complexity: Dict[str, Any]
    
    # Report analysis results  
    reports: List[Any]  # Will be Report from report_analyzer
    report_dependencies: Dict[str, Any]
    
    # Combined metrics
    overall_complexity: Dict[str, Any]
    dependency_tree: Dict[str, Any]  # Combined search + report dependencies
    rule_flow: List[Dict]  # Combined execution flow
    
    # Clinical codes (with default value, must come after non-default fields)
    report_clinical_codes: List[Dict] = field(default_factory=list)  # Clinical codes from reports
