import streamlit as st
from .code_classification import get_medication_type_flag, is_medication_code_system, is_clinical_code_system
from ..caching.lookup_manager import create_lookup_dictionaries
from ..system.session_state import (
    get_cached_snomed_mappings, update_snomed_cache, clear_expired_snomed_cache,
    SessionStateKeys
)

@st.cache_data(ttl=3600, max_entries=1, show_spinner=False)  # Cache translation for active file only
def translate_emis_to_snomed(emis_guids, lookup_df, emis_guid_col, snomed_code_col, deduplication_mode='unique_codes'):
    """
    Translate EMIS GUIDs to SNOMED codes using lookup DataFrame with persistent session cache.
    
    Args:
        emis_guids: List of EMIS GUID dictionaries from XML parsing
        lookup_df: DataFrame with EMIS GUID to SNOMED code mappings
        emis_guid_col: Column name for EMIS GUIDs in lookup_df
        snomed_code_col: Column name for SNOMED codes in lookup_df
        deduplication_mode: 'unique_codes' (dedupe by SNOMED code) or 'unique_per_entity' (dedupe by entity+code)
    
    Returns:
        Dict with categorized results based on deduplication mode
    """
    # Clean up any expired SNOMED cache first
    clear_expired_snomed_cache()
    
    # Get cached EMIS GUID → SNOMED mappings (persists across XML uploads)
    cached_mappings = get_cached_snomed_mappings()
    
    # Create lookup dictionaries for faster lookups, enhanced with cached mappings
    guid_to_snomed_dict, snomed_to_info_dict = create_lookup_dictionaries(lookup_df, emis_guid_col, snomed_code_col)
    
    # Enhance lookup with cached mappings (cached mappings take precedence for performance)
    guid_to_snomed_dict.update(cached_mappings)
    
    # Track additional mappings discovered in this translation for cache update
    new_mappings = {}
    
    # First pass: identify pseudo-refset containers and group codes by valueSet
    valueset_groups = {}  # Group codes by valueSet GUID
    pseudo_refset_valuesets = set()  # Track which valueSets are pseudo-refsets
    
    def _get_emis_guid(entry):
        base = entry.get('emis_guid') or entry.get('EMIS GUID')
        if base:
            return base
        return None

    def _get_valueset_guid(entry):
        base = entry.get('valueSet_guid') or entry.get('ValueSet GUID') or entry.get('valueset_guid')
        if base:
            return base
        return None

    for guid_info in emis_guids:
        valueset_guid = _get_valueset_guid(guid_info) or "N/A"
        emis_guid = _get_emis_guid(guid_info)
        
        # Group all codes by their valueSet
        if valueset_guid not in valueset_groups:
            valueset_groups[valueset_guid] = {
                'info': guid_info,  # Store valueSet info
                'codes': []
            }
        valueset_groups[valueset_guid]['codes'].append(guid_info)
        
        # Check if this code indicates a pseudo-refset container or member using XML structure-based flags
        if guid_info.get('is_pseudorefset', False):
            pseudo_refset_valuesets.add(valueset_guid)
    
    # Separate results by type
    clinical_codes = []  # Standalone clinical codes
    medications = []     # Standalone medications
    clinical_pseudo_members = []  # Clinical codes that are part of pseudo-refsets
    medication_pseudo_members = []  # Medications that are part of pseudo-refsets
    refsets = []
    pseudo_refsets = []  # Containers for pseudo-refsets
    pseudo_refset_members = {}  # Members of each pseudo-refset (for detailed view)
    
    # Track which refset SNOMED codes we've already added to avoid duplicates
    added_refset_snomed_codes = set()
    
    # Track unique codes to avoid duplicates in all categories
    # Deduplication key depends on mode: emis_guid (unique_codes) or (source_guid, emis_guid) (unique_per_entity)
    if deduplication_mode == 'unique_codes':
        # Deduplicate by SNOMED code only - one instance per code across entire XML
        unique_clinical_codes = {}  # key: emis_guid, value: code_info
        unique_medications = {}     # key: emis_guid, value: code_info
        unique_clinical_pseudo = {} # key: emis_guid, value: code_info
        unique_medication_pseudo = {} # key: emis_guid, value: code_info
    else:  # unique_per_entity
        # Deduplicate by (source_guid, emis_guid) - one instance per code per search/report
        unique_clinical_codes = {}  # key: (source_guid, emis_guid), value: code_info
        unique_medications = {}     # key: (source_guid, emis_guid), value: code_info
        unique_clinical_pseudo = {} # key: (source_guid, emis_guid), value: code_info
        unique_medication_pseudo = {} # key: (source_guid, emis_guid), value: code_info
    
    def get_deduplication_key(guid_info):
        """Get the appropriate deduplication key based on mode"""
        if deduplication_mode == 'unique_codes':
            return _get_emis_guid(guid_info)  # Dedupe by SNOMED code only
        else:  # unique_per_entity
            source_guid = guid_info.get('source_guid', 'unknown_source')
            return (source_guid, _get_emis_guid(guid_info))  # Dedupe by (source, code)
    
    def should_replace_entry(existing_entry, new_entry):
        """Determine if incoming entry has better details than existing entry (for unique_codes mode only)"""
        if deduplication_mode != 'unique_codes':
            return False  # Don't replace in per_entity mode
        
        # Priority factors (higher score = better entry):
        # 1. Has ValueSet Description (not N/A or empty)
        # 2. Has XML Display Name (not N/A or empty) 
        # 3. Has Table/Column Context
        
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
            
            # SNOMED Description (XML display name) - medium priority
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
        
        existing_score = calculate_completeness_score(existing_entry)
        new_score = calculate_completeness_score(new_entry)
        
        return new_score > existing_score
    
    # Create pseudo-refset containers first
    for valueset_guid in pseudo_refset_valuesets:
        valueset_info = valueset_groups[valueset_guid]['info']
        member_codes = valueset_groups[valueset_guid]['codes']
        
        # Count unique member codes (avoid counting duplicates)
        unique_member_codes = set()
        for code_info in member_codes:
            guid_val = _get_emis_guid(code_info)
            if guid_val:
                unique_member_codes.add(guid_val)
        
        # Inherit source information from the first member code (they should all be from the same source)
        source_info = {}
        if member_codes:
            first_member = member_codes[0]
            source_info = {
                'source_guid': first_member.get('source_guid', ''),
                'source_name': first_member.get('source_name', ''),
                'source_container': first_member.get('source_container', ''),
                'source_type': first_member.get('source_type', ''),
                'report_type': first_member.get('report_type', '')
            }
        
        # Create pseudo-refset entry preserving original XML data
        pseudo_refset_entry = valueset_info.copy()  # Start with all original XML data
        pseudo_refset_entry.update({
            'ValueSet GUID': valueset_guid,
            'ValueSet Description': valueset_info.get('valueSet_description', ''),
            'Code System': valueset_info.get('code_system', ''),
            'Type': 'Pseudo-Refset',
            'Usage': '⚠️ Can only be used by listing member codes, not by SNOMED code reference',
            'Status': 'Not in EMIS database - requires member code listing',
            'Member Count': len(unique_member_codes)
        })
        
        # Add source information to the pseudo-refset container
        pseudo_refset_entry.update(source_info)
        pseudo_refsets.append(pseudo_refset_entry)
        
        # Initialise member dict for this pseudo-refset (for deduplication)
        pseudo_refset_members[valueset_guid] = {}
    
    # Process all individual codes
    for guid_info in emis_guids:
        emis_guid = _get_emis_guid(guid_info)
        is_refset = bool(
            guid_info.get('is_refset')
            or guid_info.get('Is Refset')
        )
        is_pseudo_refset = bool(
            guid_info.get('is_pseudorefset')
            or guid_info.get('is_pseudo_refset')
            or guid_info.get('Is Pseudo Refset')
        )
        valueset_guid = _get_valueset_guid(guid_info)
        if not emis_guid:
            # Skip entries without a resolvable EMIS GUID
            continue
        
        # For true refsets, the emis_guid IS the SNOMED code
        if is_refset:
            snomed_code = emis_guid
            
            # Only add this refset if we haven't already added this specific SNOMED code
            if snomed_code not in added_refset_snomed_codes:
                # Try to get additional info from lookup table
                if snomed_code in snomed_to_info_dict:
                    source_info = snomed_to_info_dict[snomed_code]
                    refset_source_type = source_info['source_type']
                else:
                    refset_source_type = 'Refset'
                
                # Create refset entry preserving original XML data
                refset_entry = guid_info.copy()  # Start with all original XML data
                refset_entry.update({
                    'ValueSet GUID': valueset_guid,
                    'ValueSet Description': guid_info.get('valueSet_description', ''), 
                    'Code System': guid_info.get('code_system', ''),
                    'SNOMED Code': snomed_code,
                    'SNOMED Description': guid_info.get('valueSet_description', ''),
                    'Mapping Found': 'Found',  # True refsets are always "mapped" since EMIS GUID IS the SNOMED code
                    'Type': 'True Refset',
                    'Source Type': refset_source_type,
                    # Add source information from the GUID info
                    'source_guid': guid_info.get('source_guid', ''),
                    'source_name': guid_info.get('source_name', ''),
                    'source_container': guid_info.get('source_container', ''),
                    'source_type': guid_info.get('source_type', ''),
                    'report_type': guid_info.get('report_type', '')
                })
                
                refsets.append(refset_entry)
                
                # Mark this SNOMED code as already added
                added_refset_snomed_codes.add(snomed_code)
            continue
        
        # For regular codes, check if they belong to a pseudo-refset
        if valueset_guid in pseudo_refset_valuesets or is_pseudo_refset:
            # This code is a member of a pseudo-refset
            if emis_guid in guid_to_snomed_dict:
                mapping = guid_to_snomed_dict[emis_guid]
                snomed_code = mapping['snomed_code']
                source_type = mapping['source_type']
                has_qualifier = mapping.get('has_qualifier', 'Unknown')
                is_parent = mapping.get('is_parent', 'Unknown')
                descendants = mapping.get('descendants', '0')
                code_type = mapping.get('code_type', 'Unknown')
                mapping_found = True
            else:
                snomed_code = 'Not Found'
                source_type = 'Unknown'
                has_qualifier = 'Unknown'
                is_parent = 'Unknown'
                descendants = '0'
                code_type = 'Unknown'
                mapping_found = False
            
            # Always use XML display name for description (whether found or not)
            description = guid_info.get('xml_display_name') or guid_info.get('SNOMED Description') or ""
            if description == "N/A" or not description:
                description = "No display name in XML"
            
            # Create the base member record preserving original XML data
            member_record = guid_info.copy()  # Start with all original XML data
            member_record.update({
                'ValueSet GUID': valueset_guid,
                'ValueSet Description': guid_info.get('valueSet_description', ''),
                'EMIS GUID': emis_guid,
                'SNOMED Code': snomed_code,
                'SNOMED Description': description,
                'Mapping Found': 'Found' if mapping_found else 'Not Found'
            })
            
            # Add to pseudo-refset members (for detailed view) - deduplicate by emis_guid
            detailed_member = member_record.copy()
            detailed_member['Include Children'] = 'Yes' if guid_info.get('include_children', False) else 'No'
            pseudo_refset_members[valueset_guid][emis_guid] = detailed_member
            
            # Also add to appropriate category list for display in main tabs
            code_system = guid_info.get('code_system', '')
            table_context = guid_info.get('table_context')
            column_context = guid_info.get('column_context')
            
            # Use XML codeSystem and context as primary indicator of type
            dedupe_key = get_deduplication_key(guid_info)
            if is_medication_code_system(code_system, table_context, column_context):
                member_record['Medication Type'] = get_medication_type_flag(code_system)
                # Add source info for both modes (will be hidden in UI for unique_codes mode)
                member_record['Source GUID'] = guid_info.get('source_guid', 'Unknown')
                member_record['source_guid'] = guid_info.get('source_guid', '')
                member_record['source_name'] = guid_info.get('source_name', '')
                member_record['source_container'] = guid_info.get('source_container', '')
                member_record['source_type'] = guid_info.get('source_type', '')
                member_record['report_type'] = guid_info.get('report_type', '')
                # Add to unique medications pseudo dict
                if dedupe_key in unique_medication_pseudo:
                    # Replace existing entry if incoming one has better details
                    if should_replace_entry(unique_medication_pseudo[dedupe_key], member_record):
                        unique_medication_pseudo[dedupe_key] = member_record
                else:
                    unique_medication_pseudo[dedupe_key] = member_record
            elif is_clinical_code_system(code_system, table_context, column_context):
                member_record['Include Children'] = 'Yes' if guid_info.get('include_children', False) else 'No'
                member_record['Has Qualifier'] = has_qualifier
                member_record['Is Parent'] = is_parent
                member_record['Descendants'] = descendants
                member_record['Code Type'] = code_type
                # Add source info for both modes (will be hidden in UI for unique_codes mode)
                member_record['Source GUID'] = guid_info.get('source_guid', 'Unknown')
                member_record['source_guid'] = guid_info.get('source_guid', '')
                member_record['source_name'] = guid_info.get('source_name', '')
                member_record['source_container'] = guid_info.get('source_container', '')
                member_record['source_type'] = guid_info.get('source_type', '')
                member_record['report_type'] = guid_info.get('report_type', '')
                # Add to unique clinical pseudo dict
                if dedupe_key in unique_clinical_pseudo:
                    # Replace existing entry if incoming one has better details
                    if should_replace_entry(unique_clinical_pseudo[dedupe_key], member_record):
                        unique_clinical_pseudo[dedupe_key] = member_record
                else:
                    unique_clinical_pseudo[dedupe_key] = member_record
            else:
                # Skip EMIS internal codes entirely - they're not medical codes
                if code_system.upper() == 'EMISINTERNAL':
                    continue  # Skip this pseudo-refset member entirely
                
                # Fall back to lookup table source type for unknown code systems
                if source_type in ['Medication', 'Constituent', 'DM+D']:
                    member_record['Medication Type'] = 'Standard Medication'
                    # Add source info for both modes (will be hidden in UI for unique_codes mode)
                    member_record['Source GUID'] = guid_info.get('source_guid', 'Unknown')
                    if dedupe_key in unique_medication_pseudo:
                        # Replace existing entry if incoming one has better details
                        if should_replace_entry(unique_medication_pseudo[dedupe_key], member_record):
                            unique_medication_pseudo[dedupe_key] = member_record
                    else:
                        unique_medication_pseudo[dedupe_key] = member_record
                else:
                    member_record['Include Children'] = 'Yes' if guid_info.get('include_children', False) else 'No'
                    member_record['Has Qualifier'] = has_qualifier
                    member_record['Is Parent'] = is_parent
                    member_record['Descendants'] = descendants
                    member_record['Code Type'] = code_type
                    # Add source info for both modes (will be hidden in UI for unique_codes mode)
                    member_record['Source GUID'] = guid_info.get('source_guid', 'Unknown')
                    if dedupe_key in unique_clinical_pseudo:
                        # Replace existing entry if incoming one has better details
                        if should_replace_entry(unique_clinical_pseudo[dedupe_key], member_record):
                            unique_clinical_pseudo[dedupe_key] = member_record
                    else:
                        unique_clinical_pseudo[dedupe_key] = member_record
            
            continue  # Don't add to standalone codes
        
        # For standalone codes (not in pseudo-refsets)
        else:
            code_system = (guid_info.get('code_system', '') or '').strip()
            is_emis_internal = code_system.upper() == 'EMISINTERNAL'

            # Default unmapped; only set mapped if lookup/cache contains entry and not EMISINTERNAL
            snomed_code = 'Not Found'
            source_type = 'Unknown'
            has_qualifier = 'Unknown'
            is_parent = 'Unknown'
            descendants = '0'
            code_type = 'Unknown'
            mapping_found = False

            if not is_emis_internal and emis_guid in guid_to_snomed_dict:
                mapping = guid_to_snomed_dict[emis_guid]
                snomed_code = mapping['snomed_code']
                source_type = mapping['source_type']
                has_qualifier = mapping.get('has_qualifier', 'Unknown')
                is_parent = mapping.get('is_parent', 'Unknown')
                descendants = mapping.get('descendants', '0')
                code_type = mapping.get('code_type', 'Unknown')
                mapping_found = True
            
            # Always use XML display name for description (whether found or not)
            description = guid_info.get('xml_display_name', '')
            if description == "N/A" or not description:
                description = "No display name in XML"
            
            # Start with all original XML data to preserve pseudo-refset flags and other metadata
            result = guid_info.copy()
            result.update({
                'ValueSet GUID': valueset_guid,
                'ValueSet Description': guid_info.get('valueSet_description', ''),
                'Code System': guid_info.get('code_system', ''),
                'EMIS GUID': emis_guid,
                'SNOMED Code': snomed_code,
                'SNOMED Description': description,
                'Mapping Found': 'Found' if mapping_found else 'Not Found',
                'Table Context': guid_info.get('table_context', 'N/A'),
                'Column Context': guid_info.get('column_context', 'N/A')
            })
            
            # Classify as clinical or medication based on XML codeSystem and context
            table_context = guid_info.get('table_context')
            column_context = guid_info.get('column_context')
            
            # Use XML codeSystem and context as primary indicator of type
            dedupe_key = get_deduplication_key(guid_info)
            if is_medication_code_system(code_system, table_context, column_context):
                result['Medication Type'] = get_medication_type_flag(code_system)
                # Add source info for both modes (will be hidden in UI for unique_codes mode)
                result['Source GUID'] = guid_info.get('source_guid', 'Unknown')
                # Always prioritize medication context - remove from clinical if it exists there
                if dedupe_key in unique_clinical_codes:
                    del unique_clinical_codes[dedupe_key]
                # Check if we already have this medication
                if dedupe_key in unique_medications:
                    # Replace existing entry if incoming one has better details
                    if should_replace_entry(unique_medications[dedupe_key], result):
                        unique_medications[dedupe_key] = result
                else:
                    # First time seeing this medication, add it
                    unique_medications[dedupe_key] = result
            elif is_clinical_code_system(code_system, table_context, column_context):
                result['Include Children'] = 'Yes' if guid_info.get('include_children', False) else 'No'
                result['Has Qualifier'] = has_qualifier
                result['Is Parent'] = is_parent
                result['Descendants'] = descendants
                result['Code Type'] = code_type
                # Add source info for both modes (will be hidden in UI for unique_codes mode)
                result['Source GUID'] = guid_info.get('source_guid', 'Unknown')
                # Only add to clinical if it's not already in medications (medication context takes priority)
                if dedupe_key not in unique_medications:
                    # Check if we already have this clinical code
                    if dedupe_key in unique_clinical_codes:
                        # Replace existing entry if incoming one has better details
                        if should_replace_entry(unique_clinical_codes[dedupe_key], result):
                            unique_clinical_codes[dedupe_key] = result
                    else:
                        # First time seeing this code, add it
                        unique_clinical_codes[dedupe_key] = result
            else:
                # Skip EMIS internal codes entirely - they're not medical codes
                if code_system.upper() == 'EMISINTERNAL':
                    continue  # Skip this code entirely
                
                # Fall back to lookup table source type for unknown code systems
                if source_type in ['Medication', 'Constituent', 'DM+D']:
                    result['Medication Type'] = 'Standard Medication'
                    # Add source info for both modes (will be hidden in UI for unique_codes mode)
                    result['Source GUID'] = guid_info.get('source_guid', 'Unknown')
                    # Remove from clinical if it exists there
                    if dedupe_key in unique_clinical_codes:
                        del unique_clinical_codes[dedupe_key]
                    # Check if we already have this medication
                    if dedupe_key in unique_medications:
                        # Replace existing entry if incoming one has better details
                        if should_replace_entry(unique_medications[dedupe_key], result):
                            unique_medications[dedupe_key] = result
                    else:
                        # First time seeing this medication, add it
                        unique_medications[dedupe_key] = result
                else:
                    result['Include Children'] = 'Yes' if guid_info.get('include_children', False) else 'No'
                    result['Has Qualifier'] = has_qualifier
                    result['Is Parent'] = is_parent
                    result['Descendants'] = descendants
                    result['Code Type'] = code_type
                    # Add source info for both modes (will be hidden in UI for unique_codes mode)
                    result['Source GUID'] = guid_info.get('source_guid', 'Unknown')
                    # Only add to clinical if it's not already in medications
                    if dedupe_key not in unique_medications:
                        # Check if we already have this clinical code
                        if dedupe_key in unique_clinical_codes:
                            # Replace existing entry if incoming one has better details
                            if should_replace_entry(unique_clinical_codes[dedupe_key], result):
                                unique_clinical_codes[dedupe_key] = result
                        else:
                            # First time seeing this code, add it
                            unique_clinical_codes[dedupe_key] = result
    
    # Convert dictionaries back to lists (now deduplicated)
    clinical_codes = list(unique_clinical_codes.values())
    medications = list(unique_medications.values())
    clinical_pseudo_members = list(unique_clinical_pseudo.values())
    medication_pseudo_members = list(unique_medication_pseudo.values())
    
    # Convert pseudo_refset_members dictionaries to lists
    deduplicated_pseudo_refset_members = {}
    for valueset_guid, members_dict in pseudo_refset_members.items():
        deduplicated_pseudo_refset_members[valueset_guid] = list(members_dict.values())
    
    # Update persistent SNOMED cache with all successful mappings for future XML files
    all_results = (clinical_codes + medications + clinical_pseudo_members +
                   medication_pseudo_members + refsets + pseudo_refsets)

    for result in all_results:
        emis_guid = result.get('EMIS GUID')
        snomed_code = result.get('SNOMED Code')
        mapping_found = result.get('Mapping Found') == 'Found'
        code_system = (result.get('Code System', '') or result.get('code_system', '') or '').strip().upper()

        if emis_guid and snomed_code and mapping_found and emis_guid not in cached_mappings and code_system != 'EMISINTERNAL':
            # Store complete mapping info for cache, not just SNOMED code
            new_mappings[emis_guid] = {
                'snomed_code': snomed_code,
                'source_type': result.get('Source Type', 'Unknown'),
                'has_qualifier': result.get('Has Qualifier', 'Unknown'),
                'is_parent': result.get('Is Parent', 'Unknown'),
                'descendants': result.get('Descendants', '0')
            }
    
    # Update the persistent cache with additional mappings (60-minute TTL)
    if new_mappings:
        update_snomed_cache(new_mappings)
    
    return {
        'clinical': clinical_codes,
        'medications': medications,
        'clinical_pseudo_members': clinical_pseudo_members,
        'medication_pseudo_members': medication_pseudo_members,
        'refsets': refsets,
        'pseudo_refsets': pseudo_refsets,
        'pseudo_refset_members': deduplicated_pseudo_refset_members
    }
