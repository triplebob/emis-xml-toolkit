"""
Report Classification Module
Handles identification and classification of searches vs reports in EMIS XML data
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass


class ReportClassifier:
    """Handles classification of EMIS search reports and all report types"""
    
    @staticmethod
    def classify_report_type(report) -> str:
        """
        Classify report into one of 4 EMIS report types
        
        Args:
            report: SearchReport object to classify
            
        Returns:
            str: "[Search]", "[List Report]", "[Audit Report]", or "[Aggregate Report]"
        """
        if not report:
            return "[Search]"
        
        # Check for specific report type indicators
        report_type = ReportClassifier._detect_specific_report_type(report)
        if report_type:
            return report_type
        
        # Fallback to legacy classification for Search vs generic Report
        if ReportClassifier._has_search_population(report):
            return "[Search]"
        
        # Default to Search if has meaningful criteria, otherwise List Report
        if ReportClassifier.has_meaningful_criteria(report):
            return "[Search]"
        else:
            return "[List Report]"
    
    @staticmethod
    def _detect_specific_report_type(report) -> Optional[str]:
        """
        Detect specific EMIS report type based on XML structure indicators
        
        Returns:
            str or None: Specific report type if detected, None if unclear
        """
        # Check for explicit report type attributes
        if hasattr(report, 'report_type'):
            type_map = {
                'search': '[Search]',
                'list': '[List Report]', 
                'audit': '[Audit Report]',
                'aggregate': '[Aggregate Report]'
            }
            return type_map.get(report.report_type.lower())
        
        # Check for list report indicators
        if (hasattr(report, 'is_list_report') and report.is_list_report) or \
           (hasattr(report, 'column_groups') and report.column_groups):
            return "[List Report]"
        
        # Check for audit report indicators  
        if (hasattr(report, 'is_audit_report') and report.is_audit_report) or \
           (hasattr(report, 'custom_aggregate') and report.custom_aggregate):
            return "[Audit Report]"
        
        # Check for aggregate report indicators
        if (hasattr(report, 'is_aggregate_report') and report.is_aggregate_report) or \
           (hasattr(report, 'aggregate_groups') and report.aggregate_groups) or \
           (hasattr(report, 'statistical_groups') and report.statistical_groups):
            return "[Aggregate Report]"
        
        return None
    
    @staticmethod 
    def _has_search_population(report) -> bool:
        """Check if report has population-based search criteria"""
        if not report or not report.criteria_groups:
            return False
            
        # Check if has meaningful criteria groups (not just empty shells)
        for group in report.criteria_groups:
            if group.criteria:
                for criterion in group.criteria:
                    if (criterion.value_sets or criterion.column_filters or 
                        criterion.restrictions or criterion.linked_criteria):
                        return True
        return False
    
    @staticmethod
    def is_actual_search(report) -> bool:
        """
        Determine if a report represents an actual search (not a list report)
        
        Args:
            report: SearchReport object to check
            
        Returns:
            bool: True if it's an actual search, False if it's a report
        """
        if not report:
            return False
            
        # Explicit list report check
        if hasattr(report, 'is_list_report') and report.is_list_report:
            return False
            
        # Classification check
        classification = ReportClassifier.classify_report_type(report)
        return classification == "[Search]"
    
    @staticmethod
    def has_meaningful_criteria(report) -> bool:
        """
        Check if a report has meaningful search criteria
        
        Args:
            report: SearchReport object to check
            
        Returns:
            bool: True if it has meaningful criteria
        """
        if not report or not report.criteria_groups:
            return False
            
        for group in report.criteria_groups:
            if not group.criteria:
                continue
                
            for criterion in group.criteria:
                if (criterion.value_sets or criterion.column_filters or 
                    criterion.restrictions or criterion.linked_criteria):
                    return True
        
        return False
    
    @staticmethod
    def filter_searches_only(reports: List) -> List:
        """
        Filter a list of reports to only include actual searches, with smart deduplication
        
        Args:
            reports: List of SearchReport objects
            
        Returns:
            List: Filtered list containing only searches, with duplicates resolved
        """
        # First filter to only searches
        search_candidates = [r for r in reports if ReportClassifier.is_actual_search(r)]
        
        # Group by name to handle duplicates
        name_groups = {}
        for report in search_candidates:
            clean_name = report.name
            if clean_name not in name_groups:
                name_groups[clean_name] = []
            name_groups[clean_name].append(report)
        
        # For each name group, select the best candidate
        final_searches = []
        for clean_name, candidates in name_groups.items():
            if len(candidates) == 1:
                final_searches.append(candidates[0])
            else:
                # Multiple candidates with same name - apply smart selection
                best_candidate = ReportClassifier._select_best_search_candidate(candidates)
                final_searches.append(best_candidate)
        
        return final_searches
    
    @staticmethod
    def _select_best_search_candidate(candidates: List):
        """
        Select the best search candidate from items with the same name
        
        Priority:
        1. Prefer items that are NOT list reports
        2. Prefer items that have meaningful criteria
        3. Prefer items without parent_guid (standalone searches)
        4. Prefer items with more criteria
        """
        best_candidate = candidates[0]
        
        for candidate in candidates[1:]:
            # Check if candidate is better than current best
            if ReportClassifier._is_better_search_candidate(candidate, best_candidate):
                best_candidate = candidate
        
        return best_candidate
    
    @staticmethod
    def _is_better_search_candidate(candidate, current_best) -> bool:
        """Determine if candidate is a better search than current_best"""
        
        # 1. Strongly prefer non-list-reports over list reports
        candidate_is_list = hasattr(candidate, 'is_list_report') and candidate.is_list_report
        best_is_list = hasattr(current_best, 'is_list_report') and current_best.is_list_report
        
        if not candidate_is_list and best_is_list:
            return True
        elif candidate_is_list and not best_is_list:
            return False
        
        # 2. Prefer items with meaningful criteria
        candidate_has_meaningful = ReportClassifier.has_meaningful_criteria(candidate)
        best_has_meaningful = ReportClassifier.has_meaningful_criteria(current_best)
        
        if candidate_has_meaningful and not best_has_meaningful:
            return True
        elif not candidate_has_meaningful and best_has_meaningful:
            return False
        
        # 3. Prefer standalone searches (no parent) over child searches
        candidate_has_parent = hasattr(candidate, 'parent_guid') and candidate.parent_guid
        best_has_parent = hasattr(current_best, 'parent_guid') and current_best.parent_guid
        
        if not candidate_has_parent and best_has_parent:
            return True
        elif candidate_has_parent and not best_has_parent:
            return False
        
        # 4. If all else equal, prefer the one with more criteria
        candidate_criteria_count = len([c for g in candidate.criteria_groups for c in g.criteria]) if candidate.criteria_groups else 0
        best_criteria_count = len([c for g in current_best.criteria_groups for c in g.criteria]) if current_best.criteria_groups else 0
        
        return candidate_criteria_count > best_criteria_count
    
    @staticmethod
    def filter_reports_only(reports: List) -> List:
        """
        Filter a list of reports to only include list reports
        
        Args:
            reports: List of SearchReport objects
            
        Returns:
            List: Filtered list containing only reports
        """
        return [r for r in reports if not ReportClassifier.is_actual_search(r)]
    
    @staticmethod
    def separate_searches_and_reports(reports: List) -> tuple:
        """
        Separate a list of reports into searches and list reports
        
        Args:
            reports: List of SearchReport objects
            
        Returns:
            tuple: (searches, list_reports)
        """
        searches = []
        list_reports = []
        
        for report in reports:
            if ReportClassifier.is_actual_search(report):
                searches.append(report)
            else:
                list_reports.append(report)
        
        return searches, list_reports

    @staticmethod
    def get_report_type_counts(reports: List) -> Dict[str, int]:
        """
        Get counts of each report type
        
        Args:
            reports: List of SearchReport objects
            
        Returns:
            Dict: Report type counts with detailed breakdown
        """
        counts = {
            '[Search]': 0,
            '[List Report]': 0, 
            '[Audit Report]': 0,
            '[Aggregate Report]': 0,
            'Total Reports': 0
        }
        
        for report in reports:
            report_type = ReportClassifier.classify_report_type(report)
            if report_type in counts:
                counts[report_type] += 1
            counts['Total Reports'] += 1
        
        return counts
    
    @staticmethod
    def filter_by_report_type(reports: List, report_type: str) -> List:
        """
        Filter reports to only include specific report type
        
        Args:
            reports: List of SearchReport objects
            report_type: Target report type (e.g., "[Search]", "[List Report]")
            
        Returns:
            List: Filtered reports of specified type
        """
        return [r for r in reports if ReportClassifier.classify_report_type(r) == report_type]
    
    @staticmethod
    def group_by_report_type(reports: List) -> Dict[str, List]:
        """
        Group reports by their type
        
        Args:
            reports: List of SearchReport objects
            
        Returns:
            Dict: Reports grouped by type
        """
        groups = {
            '[Search]': [],
            '[List Report]': [],
            '[Audit Report]': [],
            '[Aggregate Report]': []
        }
        
        for report in reports:
            report_type = ReportClassifier.classify_report_type(report)
            if report_type in groups:
                groups[report_type].append(report)
        
        return groups


# Convenience functions for backward compatibility
def classify_report_type(report) -> str:
    """Convenience function for report classification"""
    return ReportClassifier.classify_report_type(report)

def is_actual_search(report) -> bool:
    """Convenience function for search identification"""
    return ReportClassifier.is_actual_search(report)
