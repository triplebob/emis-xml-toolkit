"""
Folder Management Module
Handles folder hierarchy operations and structure building
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from .report_classifier import ReportClassifier
from .search_manager import SearchManager


class FolderManager:
    """Handles folder hierarchy operations and navigation structures"""
    
    @staticmethod
    def build_folder_hierarchy_for_dropdown(folder_map: Dict, reports: List, debug_mode: bool = False) -> Dict:
        """
        Build folder hierarchy structure for dropdown navigation
        
        Args:
            folder_map: Dictionary mapping folder IDs to folder objects
            reports: List of SearchReport objects
            debug_mode: Whether to show debug information
            
        Returns:
            Dict: Processed hierarchy data for dropdown display
        """
        hierarchy = {}
        
        # First, identify common root folders to potentially remove
        all_paths = []
        folder_data = {}
        
        # Create folder path mapping
        for folder in folder_map.values():
            # Build full path for this folder
            path_parts = []
            current_folder = folder
            
            while current_folder:
                path_parts.insert(0, current_folder.name)
                parent_id = current_folder.parent_folder_id
                current_folder = folder_map.get(parent_id) if parent_id else None
            
            # Find reports in this folder
            folder_reports = [r for r in reports if getattr(r, 'folder_id', None) == folder.id]
            
            # Assume reports are already filtered by caller, no additional filtering needed
            search_reports = folder_reports
            
            
            if search_reports:  # Only include folders that have searches
                full_path = " > ".join(path_parts)
                all_paths.append(path_parts)
                folder_data[full_path] = {
                    'folder_id': folder.id,
                    'folder': folder,
                    'path_parts': path_parts,
                    'searches': SearchManager.sort_searches_numerically(search_reports)
                }
        
        # Remove common root if all paths start with the same root
        if len(all_paths) > 1:
            # Find common prefix
            min_length = min(len(path) for path in all_paths)
            common_prefix_length = 0
            
            for i in range(min_length):
                if all(path[i] == all_paths[0][i] for path in all_paths):
                    common_prefix_length = i + 1
                else:
                    break
            
            # Only remove common prefix if it's significant (more than 1 level)
            if common_prefix_length > 1:
                new_folder_data = {}
                for full_path, data in folder_data.items():
                    path_parts = data['path_parts']
                    if len(path_parts) > common_prefix_length:
                        new_path_parts = path_parts[common_prefix_length:]
                        new_full_path = " > ".join(new_path_parts)
                        data['path_parts'] = new_path_parts
                        new_folder_data[new_full_path] = data
                    else:
                        # Keep the original if it would become empty
                        new_folder_data[full_path] = data
                folder_data = new_folder_data
        
        return folder_data
    
    @staticmethod
    def build_full_folder_path(folder, folder_map: Dict) -> List[str]:
        """
        Build the full path for a folder from root to current
        
        Args:
            folder: Folder object
            folder_map: Dictionary mapping folder IDs to folder objects
            
        Returns:
            List[str]: List of folder names from root to current
        """
        path_parts = []
        current_folder = folder
        
        while current_folder:
            path_parts.insert(0, current_folder.name)
            parent_id = current_folder.parent_folder_id if hasattr(current_folder, 'parent_folder_id') else None
            current_folder = folder_map.get(parent_id) if parent_id else None
        
        return path_parts
    
    @staticmethod
    def generate_sql_schema_format(folder_path: List[str], item_type: str, item_name: str) -> str:
        """
        Generate SQL-style schema format for display
        
        Args:
            folder_path: List of folder names
            item_type: Type of item (Search, Report, etc.)
            item_name: Name of the item
            
        Returns:
            str: SQL-style formatted string
        """
        clean_name = SearchManager.clean_search_name(item_name)
        
        if folder_path:
            folder_breadcrumb = " > ".join(f"[{folder}]" for folder in folder_path)
            return f"{folder_breadcrumb} > [{item_type}].[{clean_name}]"
        else:
            return f"[{item_type}].[{clean_name}]"
    
    @staticmethod
    def find_common_root(folder_paths: List[List[str]]) -> Tuple[List[str], int]:
        """
        Find common root path among multiple folder paths
        
        Args:
            folder_paths: List of folder path lists
            
        Returns:
            Tuple[List[str], int]: (common_root_path, common_prefix_length)
        """
        if not folder_paths or len(folder_paths) < 2:
            return [], 0
        
        min_length = min(len(path) for path in folder_paths)
        common_prefix_length = 0
        common_root = []
        
        for i in range(min_length):
            if all(path[i] == folder_paths[0][i] for path in folder_paths):
                common_prefix_length = i + 1
                common_root.append(folder_paths[0][i])
            else:
                break
        
        return common_root, common_prefix_length
    
    @staticmethod
    def group_reports_by_folder(reports: List, folder_map: Dict) -> Dict[str, List]:
        """
        Group reports by their folder IDs
        
        Args:
            reports: List of SearchReport objects
            folder_map: Dictionary mapping folder IDs to folder objects
            
        Returns:
            Dict[str, List]: Dictionary mapping folder IDs to lists of reports
        """
        grouped = {}
        
        for report in reports:
            folder_id = getattr(report, 'folder_id', None)
            if folder_id:
                if folder_id not in grouped:
                    grouped[folder_id] = []
                grouped[folder_id].append(report)
        
        return grouped
    
    @staticmethod
    def get_folder_statistics(folder_map: Dict, reports: List) -> Dict[str, Any]:
        """
        Get statistics about folders and their contents
        
        Args:
            folder_map: Dictionary mapping folder IDs to folder objects
            reports: List of SearchReport objects
            
        Returns:
            Dict: Statistics about folders
        """
        folder_groups = FolderManager.group_reports_by_folder(reports, folder_map)
        searches, list_reports = ReportClassifier.separate_searches_and_reports(reports)
        
        # PERFORMANCE FIX: Pre-classify all reports once to avoid O(n²) explosion
        # Build lookup sets for faster folder analysis
        search_ids = {report.id for report in searches}
        report_ids = {report.id for report in list_reports}
        
        folders_with_searches = 0
        folders_with_reports = 0
        
        for folder_id, folder_reports in folder_groups.items():
            # OPTIMIZED: Use O(1) set lookups instead of expensive ReportClassifier calls
            folder_has_searches = any(report.id in search_ids for report in folder_reports)
            folder_has_reports = any(report.id in report_ids for report in folder_reports)
            
            if folder_has_searches:
                folders_with_searches += 1
            if folder_has_reports:
                folders_with_reports += 1
        
        return {
            'total_folders': len(folder_map),
            'folders_with_content': len(folder_groups),
            'folders_with_searches': folders_with_searches,
            'folders_with_reports': folders_with_reports,
            'total_searches': len(searches),
            'total_reports': len(list_reports)
        }
