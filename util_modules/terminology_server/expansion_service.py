"""
SNOMED Code Expansion Service

This module provides high-level services for expanding SNOMED codes
when includechildren=True is detected in the XML analysis.

It integrates with the existing clinical codes pipeline and provides
UI components for on-demand expansion.
"""

import pandas as pd
import streamlit as st
from typing import Dict, List, Set, Optional, Tuple
from datetime import datetime
import json
from dataclasses import asdict

from .nhs_terminology_client import get_terminology_client, ExpansionResult, ExpandedConcept
from ..utils.caching.lookup_cache import get_cached_emis_lookup


class ExpansionService:
    """Service for managing SNOMED code expansion operations"""
    
    def __init__(self):
        self.client = get_terminology_client()
        self.cache_key_prefix = "snomed_expansion_"
    
    def _get_cache_key(self, snomed_code: str, include_inactive: bool = False) -> str:
        """Generate cache key for expansion results"""
        return f"{self.cache_key_prefix}{snomed_code}_inactive_{include_inactive}"
    
    def _cache_expansion_result(self, result: ExpansionResult, include_inactive: bool = False):
        """Cache expansion result in session state"""
        cache_key = self._get_cache_key(result.source_code, include_inactive)
        
        # Convert result to dict with proper datetime handling
        result_dict = asdict(result)
        if isinstance(result_dict['expansion_timestamp'], datetime):
            result_dict['expansion_timestamp'] = result_dict['expansion_timestamp'].isoformat()
        
        st.session_state[cache_key] = {
            'result': result_dict,
            'cached_at': datetime.now().isoformat()
        }
    
    def _get_cached_expansion(self, snomed_code: str, include_inactive: bool = False) -> Optional[ExpansionResult]:
        """Get cached expansion result if available"""
        cache_key = self._get_cache_key(snomed_code, include_inactive)
        cached_data = st.session_state.get(cache_key)
        
        if cached_data:
            # Check if cache is still fresh (24 hours)
            cached_at = datetime.fromisoformat(cached_data['cached_at'])
            if (datetime.now() - cached_at).total_seconds() < 86400:  # 24 hours
                result_dict = cached_data['result']
                # Convert children back to ExpandedConcept objects
                children = [ExpandedConcept(**child) for child in result_dict['children']]
                
                # Handle datetime parsing safely
                expansion_timestamp = result_dict['expansion_timestamp']
                if isinstance(expansion_timestamp, str):
                    expansion_timestamp = datetime.fromisoformat(expansion_timestamp)
                elif not isinstance(expansion_timestamp, datetime):
                    expansion_timestamp = datetime.now()
                
                return ExpansionResult(
                    source_code=result_dict['source_code'],
                    source_display=result_dict['source_display'],
                    children=children,
                    total_count=result_dict['total_count'],
                    expansion_timestamp=expansion_timestamp,
                    error=result_dict.get('error')
                )
        
        return None
    
    def expand_snomed_code(self, snomed_code: str, include_inactive: bool = False, use_cache: bool = True) -> ExpansionResult:
        """
        Expand a SNOMED code to get all child concepts
        
        Args:
            snomed_code: The SNOMED CT code to expand
            include_inactive: Whether to include inactive concepts
            use_cache: Whether to use cached results if available
            
        Returns:
            ExpansionResult with child concepts
        """
        if use_cache:
            cached_result = self._get_cached_expansion(snomed_code, include_inactive)
            if cached_result:
                return cached_result
        
        # Perform expansion
        result = self.client.expand_concept(snomed_code, include_inactive)
        
        # Cache the result
        if use_cache:
            self._cache_expansion_result(result, include_inactive)
        
        return result
    
    def find_codes_with_include_children(self, clinical_data: List[Dict], filter_zero_descendants: bool = True) -> List[Dict]:
        """
        Find clinical codes that have includechildren=True flag
        
        Args:
            clinical_data: List of clinical code dictionaries
            filter_zero_descendants: Whether to filter out codes known to have 0 descendants
            
        Returns:
            List of codes that need expansion
        """
        expandable_codes = []
        filtered_out_count = 0
        
        for code_entry in clinical_data:
            # Check various possible fields where includechildren might be stored
            include_children = False
            
            # Check common field names
            for field in ['include_children', 'includechildren', 'Include Children', 'descendants']:
                if field in code_entry:
                    value = code_entry[field]
                    if isinstance(value, bool):
                        include_children = value
                    elif isinstance(value, str):
                        include_children = value.lower() in ['true', '1', 'yes']
                    break
            
            # Also check if "Descendants" column shows any child count
            descendants = code_entry.get('Descendants', '')
            if descendants and str(descendants).strip() and str(descendants) != '0':
                include_children = True
            
            if include_children:
                # Pre-filter: Check if we already know this code has 0 descendants
                if filter_zero_descendants:
                    descendants_value = code_entry.get('Descendants', '')
                    
                    # If we have descendants info and it's explicitly 0, skip this code
                    if str(descendants_value).strip() == '0':
                        filtered_out_count += 1
                        continue
                
                expandable_codes.append(code_entry)
        
        # Note: UI now handles the display of filtering information
        
        return expandable_codes
    
    def enhance_clinical_codes_with_expansion(self, clinical_data: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Enhance clinical codes data with expansion information
        
        Args:
            clinical_data: Original clinical codes data
            
        Returns:
            Tuple of (enhanced_original_data, expanded_child_codes)
        """
        enhanced_data = clinical_data.copy()
        expanded_child_codes = []
        
        expandable_codes = self.find_codes_with_include_children(clinical_data)
        
        if not expandable_codes:
            return enhanced_data, expanded_child_codes
        
        # Show expansion summary
        st.info(f"Found {len(expandable_codes)} codes with includechildren=True that can be expanded")
        
        for code_entry in expandable_codes:
            snomed_code = code_entry.get('SNOMED Code', '').strip()
            if not snomed_code:
                continue
            
            # Perform expansion
            result = self.expand_snomed_code(snomed_code)
            
            if result.error:
                # Handle errors gracefully - don't show warning bars, just track the failure
                continue
            
            # Add expansion info to original code
            code_entry['Expansion Status'] = f"✅ {len(result.children)} child codes"
            code_entry['Child Count'] = len(result.children)
            
            # Create entries for child codes
            for child in result.children:
                child_entry = {
                    'EMIS GUID': f"CHILD_{child.code}",  # Mark as child
                    'SNOMED Code': child.code,
                    'SNOMED Description': child.display,
                    'Parent SNOMED Code': snomed_code,
                    'Parent Description': result.source_display,
                    'Mapping Found': 'Child Code',
                    'Source Type': code_entry.get('Source Type', 'Unknown'),
                    'Source Name': code_entry.get('Source Name', 'Unknown'),
                    'Source Container': code_entry.get('Source Container', 'Unknown'),
                    'Is Child Code': True,
                    'Inactive': child.inactive
                }
                expanded_child_codes.append(child_entry)
        
        return enhanced_data, expanded_child_codes
    
    def create_expansion_summary_dataframe(self, expansions: Dict[str, ExpansionResult], original_codes: List[Dict] = None) -> pd.DataFrame:
        """
        Create a summary DataFrame of expansion results
        
        Args:
            expansions: Dictionary of code -> ExpansionResult
            original_codes: Original clinical data to get descriptions from
            
        Returns:
            DataFrame with expansion summary
        """
        summary_data = []
        
        # Get cached EMIS lookup for child count information
        lookup_df = st.session_state.get('lookup_df')
        snomed_code_col = st.session_state.get('snomed_code_col', 'SNOMED Code')
        emis_guid_col = st.session_state.get('emis_guid_col', 'EMIS GUID') 
        version_info = st.session_state.get('lookup_version_info', {})
        
        lookup_records = {}
        if lookup_df is not None:
            cached_data = get_cached_emis_lookup(lookup_df, snomed_code_col, emis_guid_col, version_info)
            if cached_data is not None:
                lookup_records = cached_data.get('lookup_records', {})
        
        # Create lookup for original descriptions
        original_descriptions = {}
        if original_codes:
            for code_entry in original_codes:
                snomed_code = code_entry.get('SNOMED Code', '').strip()
                if snomed_code:
                    original_descriptions[snomed_code] = code_entry.get('SNOMED Description', snomed_code)
        
        for code, result in expansions.items():
            # Determine status and get appropriate description
            if result.error:
                # Check if it's a "not found" error vs actual error
                if ('does not exist' in result.error.lower() or 
                    'not found' in result.error.lower() or 
                    'resource-not-found' in result.error.lower()):
                    status = 'Unmatched'
                    # Use original description for unmatched codes
                    description = original_descriptions.get(code, result.source_display)
                else:
                    status = 'Error'
                    description = original_descriptions.get(code, result.source_display)
            else:
                # No error - check if we got children
                if len(result.children) > 0:
                    status = 'Matched'
                    # Use the description from terminology server if we got children
                    description = result.source_display if result.source_display != code else original_descriptions.get(code, result.source_display)
                else:
                    # No error but no children - this might be a valid concept with no descendants
                    # Check if we got a proper source_display (means concept exists)
                    if result.source_display and result.source_display != code and result.source_display != 'Unknown':
                        status = 'Matched'  # Valid concept, just no children
                        description = result.source_display
                    else:
                        status = 'Unmatched'
                        description = original_descriptions.get(code, result.source_display)
            
            # Create user-friendly result status messages
            if result.error:
                # Handle different types of API errors
                if 'does not exist' in result.error.lower() or 'not found' in result.error.lower() or '422' in str(result.error):
                    result_status = "Unmatched - No concept found on terminology server for that ID"
                elif 'connection' in result.error.lower() or 'network' in result.error.lower():
                    result_status = "Error - Failed to connect to terminology server"
                else:
                    result_status = f"Error - {result.error}"
            elif status == 'Matched' and len(result.children) > 0:
                result_status = f"Matched - Found {len(result.children)} children"
            elif status == 'Matched' and len(result.children) == 0:
                result_status = "Matched - Valid concept but has no children"
            elif status == 'Unmatched':
                result_status = "Unmatched - No concept found on terminology server for that ID"
            else:
                result_status = f"Unknown - Please report this: children={len(result.children)}, error={result.error}"
            
            # Get EMIS child count from lookup records
            emis_child_count = 'N/A'
            if lookup_records and code in lookup_records:
                descendants = lookup_records[code].get('descendants', '')
                if descendants and str(descendants).isdigit():
                    emis_child_count = str(descendants)  # Keep as string for consistency
                elif descendants:
                    emis_child_count = str(descendants)  # Convert to string for consistency
            
            summary_data.append({
                'SNOMED Code': code,
                'Description': description,
                'EMIS Child Count': emis_child_count,
                'Term Server Child Count': len(result.children),
                'Result Status': result_status,
                'Expanded At': result.expansion_timestamp.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return pd.DataFrame(summary_data)
    


# Singleton instance
_expansion_service = None

def get_expansion_service() -> ExpansionService:
    """Get or create the expansion service singleton"""
    global _expansion_service
    if _expansion_service is None:
        _expansion_service = ExpansionService()
    return _expansion_service
