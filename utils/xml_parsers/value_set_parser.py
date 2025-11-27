"""
Value set parsing utilities for EMIS XML
Handles parsing of clinical code value sets and code systems
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional, Set, Tuple
from .base_parser import XMLParserBase, get_namespaces
from ..common.error_handling import ParseResult, create_xml_parsing_context, create_error_context


class ValueSetParser(XMLParserBase):
    """Parser for value set elements"""
    
    def semantic_deduplicate_value_sets(self, value_sets: List[Dict]) -> ParseResult:
        """
        Perform semantic deduplication of value sets with content comparison
        
        Goes beyond simple ID matching to compare:
        - Code values and code systems
        - Display names and descriptions  
        - Functional equivalence
        - Hierarchical relationships
        
        Returns detailed deduplication results with preserved semantic meaning
        """
        xml_context = create_xml_parsing_context(
            element_name="valueSets",
            parsing_stage="semantic_deduplication"
        )
        
        if not value_sets:
            return ParseResult.success_result({
                'deduplicated': [],
                'removed_duplicates': 0,
                'deduplication_summary': {}
            })
        
        errors = []
        warnings = []
        
        try:
            # Group value sets by semantic similarity
            semantic_groups = self._group_by_semantic_similarity(value_sets)
            
            # Process each group for deduplication
            deduplicated_sets = []
            deduplication_details = {}
            total_removed = 0
            
            for group_id, group_sets in semantic_groups.items():
                if len(group_sets) == 1:
                    # Single item - no deduplication needed
                    deduplicated_sets.extend(group_sets)
                    deduplication_details[group_id] = {
                        'action': 'kept_single',
                        'original_count': 1,
                        'final_count': 1
                    }
                else:
                    # Multiple items - apply semantic deduplication
                    dedup_result = self._deduplicate_semantic_group(group_sets)
                    
                    if dedup_result['success']:
                        deduplicated_sets.extend(dedup_result['merged_sets'])
                        removed_count = len(group_sets) - len(dedup_result['merged_sets'])
                        total_removed += removed_count
                        
                        deduplication_details[group_id] = {
                            'action': 'merged',
                            'original_count': len(group_sets),
                            'final_count': len(dedup_result['merged_sets']),
                            'removed_count': removed_count,
                            'merge_strategy': dedup_result['strategy']
                        }
                        
                        if dedup_result.get('warnings'):
                            warnings.extend(dedup_result['warnings'])
                    else:
                        # Fallback - keep all if merging failed
                        deduplicated_sets.extend(group_sets)
                        warnings.extend(dedup_result.get('warnings', []))
                        
                        deduplication_details[group_id] = {
                            'action': 'kept_all_due_to_error',
                            'original_count': len(group_sets),
                            'final_count': len(group_sets),
                            'error': dedup_result.get('error')
                        }
            
            result = {
                'deduplicated': deduplicated_sets,
                'removed_duplicates': total_removed,
                'deduplication_summary': {
                    'original_count': len(value_sets),
                    'final_count': len(deduplicated_sets),
                    'groups_processed': len(semantic_groups),
                    'details_by_group': deduplication_details
                }
            }
            
            if errors:
                return ParseResult.failure_result(errors, xml_context)
            elif warnings:
                return ParseResult.partial_result(result, warnings, xml_context)
            else:
                return ParseResult.success_result(result)
                
        except Exception as e:
            error_msg = f"Unexpected error during semantic deduplication: {str(e)}"
            return ParseResult.failure_result([error_msg], xml_context)
    
    def _group_by_semantic_similarity(self, value_sets: List[Dict]) -> Dict[str, List[Dict]]:
        """Group value sets by semantic similarity"""
        groups = {}
        
        for i, value_set in enumerate(value_sets):
            if value_set is None:
                continue
            
            # Generate semantic signature for grouping
            signature = self._generate_semantic_signature(value_set)
            
            if signature not in groups:
                groups[signature] = []
            
            groups[signature].append(value_set)
        
        return groups
    
    def _generate_semantic_signature(self, value_set: Dict) -> str:
        """Generate a semantic signature for value set grouping"""
        # Combine key semantic elements
        signature_parts = []
        
        # Code system (primary grouping factor)
        code_system = value_set.get('code_system', '').strip().lower()
        if code_system:
            signature_parts.append(f"cs:{code_system}")
        
        # Primary codes (first few values for similarity)
        values = value_set.get('values', [])
        primary_codes = []
        for value_item in values[:3]:  # Use first 3 codes for signature
            if value_item and 'value' in value_item:
                primary_codes.append(value_item['value'])
        
        if primary_codes:
            signature_parts.append(f"codes:{'|'.join(sorted(primary_codes))}")
        
        # Description similarity (normalized)
        description = value_set.get('description', '').strip().lower()
        if description:
            # Normalize description for grouping
            normalized = self._normalize_description(description)
            if normalized:
                signature_parts.append(f"desc:{normalized}")
        
        return "||".join(signature_parts) if signature_parts else f"empty_{id(value_set)}"
    
    def _normalize_description(self, description: str) -> str:
        """Normalize description for semantic comparison"""
        import re
        
        # Remove common prefixes/suffixes
        normalized = description.lower().strip()
        
        # Remove version numbers
        normalized = re.sub(r'v?\d+\.\d+', '', normalized)
        
        # Remove dates  
        normalized = re.sub(r'\d{4}-\d{2}-\d{2}', '', normalized)
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Remove common clinical terminology prefixes
        prefixes_to_remove = ['snomed', 'sct', 'icd', 'opcs', 'read', 'ctv3']
        for prefix in prefixes_to_remove:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
        
        return normalized
    
    def _deduplicate_semantic_group(self, group_sets: List[Dict]) -> Dict[str, Any]:
        """Deduplicate a group of semantically similar value sets"""
        if len(group_sets) <= 1:
            return {
                'success': True,
                'merged_sets': group_sets,
                'strategy': 'no_merge_needed'
            }
        
        try:
            # Strategy 1: Exact code match - merge if codes are identical
            exact_matches = self._group_by_exact_codes(group_sets)
            if len(exact_matches) < len(group_sets):
                merged = []
                for code_group in exact_matches.values():
                    merged.append(self._merge_identical_code_sets(code_group))
                
                return {
                    'success': True,
                    'merged_sets': merged,
                    'strategy': 'exact_code_merge'
                }
            
            # Strategy 2: Hierarchical relationship - keep parent, remove children
            hierarchical_result = self._resolve_hierarchical_duplicates(group_sets)
            if hierarchical_result['success']:
                return hierarchical_result
            
            # Strategy 3: Best quality - keep highest quality set
            best_quality_result = self._select_best_quality_set(group_sets)
            return best_quality_result
            
        except Exception as e:
            return {
                'success': False,
                'merged_sets': group_sets,  # Fallback to original
                'error': str(e)
            }
    
    def _group_by_exact_codes(self, value_sets: List[Dict]) -> Dict[str, List[Dict]]:
        """Group value sets that have identical code lists"""
        code_groups = {}
        
        for value_set in value_sets:
            # Generate code signature
            codes = []
            for value_item in value_set.get('values', []):
                if value_item and 'value' in value_item:
                    codes.append(value_item['value'])
            
            code_signature = '|'.join(sorted(codes))
            
            if code_signature not in code_groups:
                code_groups[code_signature] = []
            code_groups[code_signature].append(value_set)
        
        return code_groups
    
    def _merge_identical_code_sets(self, code_sets: List[Dict]) -> Dict:
        """Merge value sets with identical codes, preserving best information"""
        if len(code_sets) == 1:
            return code_sets[0]
        
        # Use the most complete set as base
        base_set = max(code_sets, key=lambda vs: self._calculate_completeness_score(vs))
        
        # Merge additional information from other sets
        merged = base_set.copy()
        merged['_merge_info'] = {
            'merged_from_count': len(code_sets),
            'merge_strategy': 'identical_codes'
        }
        
        # Enhance description if others have better ones
        for value_set in code_sets:
            if value_set != base_set:
                other_desc = value_set.get('description', '')
                if len(other_desc) > len(merged.get('description', '')):
                    merged['description'] = other_desc
        
        return merged
    
    def _resolve_hierarchical_duplicates(self, group_sets: List[Dict]) -> Dict[str, Any]:
        """Resolve duplicates based on hierarchical relationships"""
        # For now, implement basic parent-child detection
        # This could be enhanced with proper SNOMED hierarchy analysis
        
        parent_sets = []
        child_sets = []
        
        for value_set in group_sets:
            # Check if this appears to be a parent (has includeChildren=true)
            has_include_children = any(
                val.get('include_children', False) 
                for val in value_set.get('values', [])
            )
            
            if has_include_children:
                parent_sets.append(value_set)
            else:
                child_sets.append(value_set)
        
        if parent_sets and child_sets:
            # Keep parents, they subsume children
            return {
                'success': True,
                'merged_sets': parent_sets,
                'strategy': 'hierarchical_parent_kept',
                'warnings': [f"Removed {len(child_sets)} child sets in favour of parent sets"]
            }
        
        return {'success': False}
    
    def _select_best_quality_set(self, group_sets: List[Dict]) -> Dict[str, Any]:
        """Select the highest quality value set from a group"""
        best_set = max(group_sets, key=self._calculate_quality_score)
        
        return {
            'success': True,
            'merged_sets': [best_set],
            'strategy': 'best_quality_selected',
            'warnings': [f"Selected 1 best quality set from {len(group_sets)} similar sets"]
        }
    
    def _calculate_completeness_score(self, value_set: Dict) -> int:
        """Calculate completeness score for a value set"""
        score = 0
        
        # Points for having description
        if value_set.get('description'):
            score += 10
        
        # Points for number of values
        score += len(value_set.get('values', []))
        
        # Points for having code system
        if value_set.get('code_system'):
            score += 5
        
        # Points for having display names in values
        for value_item in value_set.get('values', []):
            if value_item.get('display_name'):
                score += 2
        
        return score
    
    def _calculate_quality_score(self, value_set: Dict) -> int:
        """Calculate quality score for value set selection"""
        score = self._calculate_completeness_score(value_set)
        
        # Bonus for standard code systems
        code_system = value_set.get('code_system', '').lower()
        if 'snomed' in code_system:
            score += 20
        elif 'icd' in code_system:
            score += 15
        elif 'read' in code_system or 'ctv3' in code_system:
            score += 10
        
        # Bonus for refsets
        if any(val.get('is_refset', False) for val in value_set.get('values', [])):
            score += 15
        
        return score
    
    def _is_medication_from_context(self, code_system, table_context='', column_context=''):
        """
        Determine if a code is a medication based on code system and table/column context.
        Uses the same logic as xml_utils.is_medication_code_system.
        """
        from .xml_utils import is_medication_code_system
        return is_medication_code_system(code_system, table_context, column_context)
    
    def parse_value_set(self, valueset_elem: ET.Element, is_linked_criteria: bool = False, is_restriction: bool = False) -> Optional[Dict]:
        """Parse value set information"""
        try:
            code_system = self.parse_child_text(valueset_elem, 'codeSystem')
            result = {
                'id': self.parse_child_text(valueset_elem, 'id'),
                'code_system': code_system,
                'description': self.parse_child_text(valueset_elem, 'description'),
                'values': [],
                'is_linked_criteria': is_linked_criteria,
                'is_restriction': is_restriction
            }
            
            # Parse individual values
            # Handle both namespaced and non-namespaced values elements
            namespaced_values = self.find_elements(valueset_elem, './/emis:values')
            non_namespaced_values = valueset_elem.findall('.//values')
            all_values_elems = non_namespaced_values + [v for v in namespaced_values if v not in non_namespaced_values]
            for values_elem in all_values_elems:
                value_data = self._parse_value_entry(values_elem, code_system)
                if value_data:
                    result['values'].append(value_data)
            
            # Parse allValues if present (alternative structure) - handle both namespaced and non-namespaced
            all_values_elem = self.find_element_both(valueset_elem, 'allValues')
            if all_values_elem is not None:
                result['all_values'] = self._parse_all_values(all_values_elem, code_system)
            
            # If no description at valueSet level, try to get displayName from first values element
            if not result['description'] and result['values']:
                for value_item in result['values']:
                    if value_item.get('display_name'):
                        result['description'] = value_item['display_name']
                        break
            
            # Clean up the description to extract just the meaningful name
            if result['description']:
                result['description'] = self._clean_refset_description(result['description'])
            
            return result if result['values'] or result.get('all_values') else None
            
        except Exception as e:
            # Use structured error handling as documented
            xml_context = create_xml_parsing_context(
                element_name="value_set",
                parsing_stage="value_set_parsing"
            )
            self.error_handler.log_exception(
                "value set parsing",
                e,
                create_error_context("value_set_parsing", user_data={"operation": "parse_value_set"})
            )
            return None
    
    def _parse_value_entry(self, values_elem: ET.Element, code_system: str = '') -> Optional[Dict]:
        """Parse individual value entry within a value set"""
        try:
            # Handle both namespaced and non-namespaced displayName elements
            display_name_elem = values_elem.find('displayName')
            if display_name_elem is None:
                display_name_elem = values_elem.find('emis:displayName', self.namespaces)
            display_name = self.get_text(display_name_elem) if display_name_elem is not None else ""
            
            return {
                'value': self.parse_child_text(values_elem, 'value'),
                'display_name': display_name,
                'include_children': self._parse_boolean_child(values_elem, 'includeChildren'),
                'is_refset': self._parse_boolean_child(values_elem, 'isRefset'),
                'is_medication': self._is_medication_from_context(code_system, '', ''),  # Basic medication detection based on code system
                'code_system': code_system,
                # Extended parsing for additional EMIS XML attributes
                'inactive': self._parse_boolean_child(values_elem, 'inactive'),
                'legacy_value': self.parse_child_text(values_elem, 'legacyValue'),
                'cluster_code': self.parse_child_text(values_elem, 'clusterCode')
            }
        except Exception as e:
            # Use structured error handling as documented
            xml_context = create_xml_parsing_context(
                element_name="value_entry",
                parsing_stage="value_entry_parsing"
            )
            self.error_handler.log_exception(
                "value entry parsing",
                e,
                create_error_context("value_entry_parsing", user_data={"operation": "parse_value_entry"})
            )
            return None
    
    def _parse_all_values(self, all_values_elem: ET.Element, parent_code_system: str = '') -> Dict:
        """Parse allValues structure (alternative to individual values)"""
        try:
            # allValues can have its own codeSystem or inherit from parent
            all_values_code_system = self.parse_child_text(all_values_elem, 'codeSystem') or parent_code_system
            result = {
                'code_system': all_values_code_system,
                'values': []
            }
            
            # Parse nested values within allValues - handle both namespaced and non-namespaced
            namespaced_values = self.find_elements(all_values_elem, './/emis:values')
            non_namespaced_values = all_values_elem.findall('.//values')
            all_nested_values = non_namespaced_values + [v for v in namespaced_values if v not in non_namespaced_values]
            for values_elem in all_nested_values:
                value_data = self._parse_value_entry(values_elem, all_values_code_system)
                if value_data:
                    result['values'].append(value_data)
            
            return result
        except Exception as e:
            # Use structured error handling as documented
            xml_context = create_xml_parsing_context(
                element_name="all_values",
                parsing_stage="all_values_parsing"
            )
            self.error_handler.log_exception(
                "all values parsing",
                e,
                create_error_context("all_values_parsing", user_data={"operation": "parse_all_values"})
            )
            return {}
    
    def _parse_boolean_child(self, parent: ET.Element, child_name: str) -> bool:
        """Parse boolean value from child element - handles both namespaced and non-namespaced"""
        child_elem = self.find_element_both(parent, child_name)
        if child_elem is not None:
            return self.get_text(child_elem).lower() == 'true'
        return False
    
    def _clean_refset_description(self, description: str) -> str:
        """Clean up refset descriptions to extract just the meaningful name"""
        if not description:
            return description
        
        import re
        
        # Handle pattern: "Refset: ETHNALL_COD[999022611000230100]" -> "ETHNALL_COD"
        match = re.match(r'Refset:\s*([^[\]]+)\[.*\]', description)
        if match:
            return match.group(1).strip()
        
        # Handle pattern: "Refset: ETHNALL_COD" (no brackets) -> "ETHNALL_COD" 
        match = re.match(r'Refset:\s*(.+)', description)
        if match:
            return match.group(1).strip()
        
        # If no pattern matches, return original (handles cases like "ETH2016WB_COD")
        return description


# Convenience function for backward compatibility
def parse_value_set(valueset_elem: ET.Element, namespaces: Optional[Dict[str, str]] = None, is_linked_criteria: bool = False, is_restriction: bool = False) -> Optional[Dict]:
    """Parse value set information"""
    parser = ValueSetParser(namespaces)
    return parser.parse_value_set(valueset_elem, is_linked_criteria, is_restriction)
