"""
Clinical Code Export Handler
Handles export of clinical codes, refsets, and value sets
"""

import pandas as pd
import io
from datetime import datetime
from typing import List, Dict, Any, Optional
from ..core import ReportClassifier, SearchManager
from ..common.export_utils import sanitize_dataframe_for_excel


class ClinicalCodeExportHandler:
    """Handles export of clinical codes and value sets"""
    
    def __init__(self):
        pass
    
    def export_all_codes_as_csv(self, search_reports, include_search_context=True, include_source_tracking=True, include_report_codes=True, deduplication_mode='unique_codes'):
        """
        Export all clinical codes from multiple searches as CSV
        
        Args:
            search_reports: List of SearchReport objects
            include_search_context: Whether to include search/rule context
            include_source_tracking: Whether to include source tracking columns
            include_report_codes: Whether to include codes from reports (aggregate, audit, etc.)
            
        Returns:
            tuple: (filename, csv_content)
        """
        all_codes = []
        
        for search in search_reports:
            for rule_num, group in enumerate(search.criteria_groups, 1):
                # Check if this is a report criteria group and if we should include it
                is_report_criteria = group.id == 'aggregate_filters'
                if not include_report_codes and is_report_criteria:
                    continue  # Skip report criteria if configured to exclude them
                
                # Process only main criteria (not linked ones) to avoid duplication
                main_criteria = [c for c in group.criteria if not self._is_linked_criterion(c, group.criteria)]
                
                for crit_num, criterion in enumerate(main_criteria, 1):
                    # Extract codes from main criterion
                    codes = self._extract_codes_from_criterion(
                        criterion, search, rule_num, crit_num, include_search_context, include_source_tracking, is_report_criteria, "MAIN CRITERION"
                    )
                    all_codes.extend(codes)
                    
                    # Extract codes from linked criteria
                    for linked_num, linked_crit in enumerate(criterion.linked_criteria, 1):
                        linked_codes = self._extract_codes_from_criterion(
                            linked_crit, search, rule_num, f"{crit_num}.{linked_num}", include_search_context, include_source_tracking, is_report_criteria, f"LINKED TO CRITERION {crit_num}"
                        )
                        all_codes.extend(linked_codes)
        
        # Apply deduplication logic only in unique codes mode
        if deduplication_mode == 'unique_codes':
            all_codes = self._deduplicate_codes(all_codes)
        
        df = pd.DataFrame(all_codes)
        csv_content = df.to_csv(index=False)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"All_Clinical_Codes_{timestamp}.csv"
        
        return filename, csv_content
    
    def _deduplicate_codes(self, all_codes):
        """
        Deduplicate codes by EMIS GUID, prioritizing entries with actual ValueSet GUID over N/A
        
        Args:
            all_codes: List of code dictionaries
            
        Returns:
            List of deduplicated codes
        """
        if not all_codes:
            return all_codes
        
        # Group codes by EMIS GUID
        emis_guid_groups = {}
        for code in all_codes:
            emis_guid = code.get('EMIS GUID', 'unknown')
            if emis_guid not in emis_guid_groups:
                emis_guid_groups[emis_guid] = []
            emis_guid_groups[emis_guid].append(code)
        
        # For each group, select the best entry
        deduplicated_codes = []
        for emis_guid, codes_group in emis_guid_groups.items():
            if len(codes_group) == 1:
                # Only one entry, keep it
                deduplicated_codes.append(codes_group[0])
            else:
                # Multiple entries, select the best one
                best_code = self._select_best_code_entry(codes_group)
                deduplicated_codes.append(best_code)
        
        return deduplicated_codes
    
    def _select_best_code_entry(self, codes_group):
        """
        Select the best code entry from a group of duplicates
        
        Priority:
        1. Has actual ValueSet GUID (not N/A)
        2. Has ValueSet Description (not N/A)
        3. Has SNOMED Description (not N/A)
        4. Has Table/Column Context
        """
        def calculate_completeness_score(entry):
            score = 0
            
            # ValueSet GUID - HIGHEST priority (actual GUID vs N/A)
            vs_guid = entry.get('ValueSet GUID', 'N/A')
            if vs_guid and vs_guid != 'N/A' and vs_guid.strip():
                score += 20  # Highest priority for actual ValueSet GUID
            
            # ValueSet Description - high priority
            vs_desc = entry.get('ValueSet Description', 'N/A')
            if vs_desc and vs_desc != 'N/A' and vs_desc.strip():
                score += 10
            
            # SNOMED Description - medium priority
            snomed_desc = entry.get('SNOMED Description', 'N/A')
            if snomed_desc and snomed_desc != 'N/A' and snomed_desc != 'No display name in XML' and snomed_desc.strip():
                score += 5
            
            # Table Context - lower priority
            table_ctx = entry.get('Table Context', 'N/A')
            if table_ctx and table_ctx != 'N/A' and table_ctx.strip():
                score += 2
            
            # Column Context - lowest priority  
            col_ctx = entry.get('Column Context', 'N/A')
            if col_ctx and col_ctx != 'N/A' and col_ctx.strip():
                score += 1
            
            return score
        
        # Find the entry with the highest completeness score
        best_entry = codes_group[0]
        best_score = calculate_completeness_score(best_entry)
        
        for entry in codes_group[1:]:
            entry_score = calculate_completeness_score(entry)
            if entry_score > best_score:
                best_entry = entry
                best_score = entry_score
        
        return best_entry
    
    def _extract_codes_from_criterion(self, criterion, search, rule_num, crit_num, include_context, include_source_tracking=False, is_report_criteria=False, criterion_type="MAIN CRITERION"):
        """Extract clinical codes from a criterion"""
        codes = []
        
        if not criterion.value_sets:
            return codes
        
        for vs in criterion.value_sets:
            if not vs.get('values'):
                continue
                
            for value in vs['values']:
                code_data = {
                    'Code Value': value.get('value', ''),
                    'Display Name': value.get('display_name', ''),
                    'Code System': vs.get('code_system', ''),
                    'Include Children': value.get('include_children', False),
                    'Is Refset': value.get('is_refset', False),
                    'Value Set ID': vs.get('id', ''),
                    'Value Set Description': vs.get('description', '')
                }
                
                if include_context:
                    code_data.update({
                        'Search Name': search.name,
                        'Search ID': search.id,
                        'Creation Time': search.creation_time or 'N/A',
                        'Author': search.author or 'N/A',
                        'Rule Number': rule_num,
                        'Criterion Number': crit_num,
                        'Criterion Type': criterion_type,
                        'Criterion Description': criterion.description or '',
                        'Criterion Table': criterion.table
                    })
                
                # Add source tracking information if enabled
                if include_source_tracking:
                    if is_report_criteria:
                        # Get report type for more specific labeling
                        report_type = getattr(search, 'report_type', 'report')
                        report_type_display = {
                            'aggregate': 'Aggregate Report',
                            'list': 'List Report', 
                            'audit': 'Audit Report'
                        }.get(report_type, f'{report_type.title()} Report')
                        
                        code_data.update({
                            'Source': report_type_display,
                            'Source Type': 'Report',
                            'Report Type': report_type.title()
                        })
                    else:
                        code_data.update({
                            'Source': "Search",
                            'Source Type': 'Search',
                            'Report Type': 'Search'
                        })
                
                codes.append(code_data)
        
        return codes
    
    def get_code_statistics(self, search_reports):
        """
        Get statistics about clinical codes across all searches
        
        Args:
            search_reports: List of SearchReport objects
            
        Returns:
            dict: Statistics about the codes
        """
        stats = {
            'total_value_sets': 0,
            'total_codes': 0,
            'unique_codes': set(),
            'refset_codes': 0,
            'hierarchical_codes': 0,
            'code_systems': set(),
            'searches_with_codes': 0
        }
        
        for search in search_reports:
            has_codes = False
            
            for group in search.criteria_groups:
                for criterion in group.criteria:
                    if not criterion.value_sets:
                        continue
                        
                    has_codes = True
                    stats['total_value_sets'] += len(criterion.value_sets)
                    
                    for vs in criterion.value_sets:
                        if vs.get('code_system'):
                            stats['code_systems'].add(vs['code_system'])
                            
                        for value in vs.get('values', []):
                            stats['total_codes'] += 1
                            
                            if value.get('value'):
                                stats['unique_codes'].add(value['value'])
                            
                            if value.get('is_refset'):
                                stats['refset_codes'] += 1
                                
                            if value.get('include_children'):
                                stats['hierarchical_codes'] += 1
            
            if has_codes:
                stats['searches_with_codes'] += 1
        
        # Convert sets to counts for final stats
        stats['unique_codes_count'] = len(stats['unique_codes'])
        stats['code_systems_count'] = len(stats['code_systems'])
        
        # Clean up sets from return value
        del stats['unique_codes']
        stats['code_systems'] = list(stats['code_systems'])
        
        return stats
    
    def _is_linked_criterion(self, criterion, all_criteria):
        """Check if this criterion is a linked criterion (appears in another criterion's linked_criteria)"""
        if not hasattr(criterion, 'id') or not criterion.id:
            return False
            
        # Check if this criterion's ID appears in any other criterion's linked_criteria
        for other_criterion in all_criteria:
            if hasattr(other_criterion, 'linked_criteria'):
                for linked_crit in other_criterion.linked_criteria:
                    if hasattr(linked_crit, 'id') and linked_crit.id == criterion.id:
                        return True
        return False
