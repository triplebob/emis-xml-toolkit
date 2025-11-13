"""
Search Management Module
Handles search-specific operations like sorting, filtering, and name cleaning
"""

import re
from typing import List, Dict, Any, Optional


class SearchManager:
    """Handles search-specific operations and utilities"""
    
    @staticmethod
    def sort_searches_numerically(search_reports: List) -> List:
        """
        Sort searches numerically by extracting numbers from names
        
        Args:
            search_reports: List of SearchReport objects to sort
            
        Returns:
            List: Sorted list of search reports
        """
        def extract_sort_key(search):
            # First sort by sequence number
            sequence_key = search.sequence if hasattr(search, 'sequence') else 999
            
            # Then extract numbers from the name for secondary sorting
            name = search.name
            numbers = re.findall(r'\d+', name)
            numeric_key = int(numbers[0]) if numbers else 999
            
            return (sequence_key, numeric_key, name.lower())
        
        return sorted(search_reports, key=extract_sort_key)
    
    @staticmethod
    def clean_search_name(name: str) -> str:
        """
        Clean search name by removing dependency artifacts
        
        Args:
            name: Raw search name
            
        Returns:
            str: Cleaned search name
        """
        # Remove dependency indicators like [^1 v2], [^0 v1], etc.
        cleaned = re.sub(r'\s*\[\^\d+\s+v\d+\]$', '', name)
        return cleaned.strip()
    
    @staticmethod
    def extract_search_numbers(name: str) -> List[int]:
        """
        Extract numeric values from search name
        
        Args:
            name: Search name to extract numbers from
            
        Returns:
            List[int]: List of numbers found in the name
        """
        return [int(num) for num in re.findall(r'\d+', name)]
    
    @staticmethod
    def get_primary_search_number(name: str) -> Optional[int]:
        """
        Get the primary search number (usually the first number in the name)
        
        Args:
            name: Search name
            
        Returns:
            Optional[int]: Primary search number or None if no numbers found
        """
        numbers = SearchManager.extract_search_numbers(name)
        return numbers[0] if numbers else None
    
    @staticmethod
    def group_searches_by_sequence(search_reports: List) -> Dict[int, List]:
        """
        Group searches by their sequence number
        
        Args:
            search_reports: List of SearchReport objects
            
        Returns:
            Dict[int, List]: Dictionary mapping sequence numbers to lists of searches
        """
        grouped = {}
        for search in search_reports:
            sequence = search.sequence if hasattr(search, 'sequence') else 999
            if sequence not in grouped:
                grouped[sequence] = []
            grouped[sequence].append(search)
        
        return grouped
    
    @staticmethod
    def find_search_by_id(search_reports: List, search_id: str):
        """
        Find a search by its ID
        
        Args:
            search_reports: List of SearchReport objects
            search_id: ID to search for
            
        Returns:
            SearchReport or None: Found search or None if not found
        """
        return next((s for s in search_reports if s.id == search_id), None)
    
    @staticmethod
    def find_searches_by_name_pattern(search_reports: List, pattern: str) -> List:
        """
        Find searches matching a name pattern
        
        Args:
            search_reports: List of SearchReport objects
            pattern: Regex pattern to match against names
            
        Returns:
            List: Matching searches
        """
        compiled_pattern = re.compile(pattern, re.IGNORECASE)
        return [s for s in search_reports if compiled_pattern.search(s.name)]
    
    @staticmethod
    def get_search_statistics(search_reports: List) -> Dict[str, Any]:
        """
        Get statistics about a list of searches
        
        Args:
            search_reports: List of SearchReport objects
            
        Returns:
            Dict: Statistics including counts, sequences, etc.
        """
        if not search_reports:
            return {
                'total_searches': 0,
                'sequences': [],
                'has_criteria': 0,
                'has_linked_criteria': 0
            }
        
        has_criteria = sum(1 for s in search_reports if s.criteria_groups)
        has_linked = sum(1 for s in search_reports 
                        if s.criteria_groups and any(
                            any(c.linked_criteria for c in g.criteria) 
                            for g in s.criteria_groups))
        
        sequences = sorted(set(s.sequence for s in search_reports 
                             if hasattr(s, 'sequence')))
        
        return {
            'total_searches': len(search_reports),
            'sequences': sequences,
            'has_criteria': has_criteria,
            'has_linked_criteria': has_linked,
            'sequence_range': f"{min(sequences)}-{max(sequences)}" if sequences else "N/A"
        }


# Convenience functions for backward compatibility
def sort_searches_numerically(search_reports: List) -> List:
    """Convenience function for sorting searches"""
    return SearchManager.sort_searches_numerically(search_reports)

def clean_report_name(name: str) -> str:
    """Convenience function for cleaning search names"""
    return SearchManager.clean_search_name(name)
