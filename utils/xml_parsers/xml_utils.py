"""
XML utilities for The Unofficial EMIS XML Toolkit
Handles XML parsing, GUID extraction, and code system classification
"""

import xml.etree.ElementTree as ET
import re
from utils.xml_parsers.namespace_handler import NamespaceHandler

def _clean_refset_description(description):
    """Clean up refset descriptions to extract just the meaningful name"""
    if not description:
        return description
    
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

def parse_xml_for_emis_guids(xml_content, source_guid=None):
    """
    Parse XML content and extract EMIS GUIDs from value elements.
    
    Args:
        xml_content: The XML content to parse
        source_guid: Optional GUID of the source search/report (for tracking source in dual-mode)
    """
    try:
        root = ET.fromstring(xml_content)
        
        # Define namespaces
        # Initialize namespace handler
        ns = NamespaceHandler()
        emis_guids = []
        
        # Find all valueSet elements using namespace handler
        all_valuesets = ns.findall_with_path(root, './/valueSet')
        
        for valueset in all_valuesets:
            valueset_id = ns.find(valueset, 'id')
            valueset_description = ns.find(valueset, 'description')
            code_system = ns.find(valueset, 'codeSystem')
            
            # Get valueSet metadata
            vs_id = valueset_id.text if valueset_id is not None else "N/A"
            vs_desc = valueset_description.text if valueset_description is not None else "N/A"
            
            # Perform XML structure-based detection for refset types
            is_pseudo_refset_container = is_pseudo_refset_from_xml_structure(valueset, ns)
            
            # Analyze structure to understand this valueSet
            values_elements = ns.findall_with_path(valueset, './/values')
            has_refset_flag = False
            refset_values_element = None
            
            # Check if any values element has isRefset = true
            for values in values_elements:
                is_refset_elem = ns.find(values, 'isRefset')
                if is_refset_elem is not None and is_refset_elem.text and is_refset_elem.text.lower() == 'true':
                    has_refset_flag = True
                    refset_values_element = values
                    break
            
            
            
            # If no description at valueSet level, try to get displayName from first values element
            if vs_desc == "N/A":
                values_elem = ns.find_with_path(valueset, './/values')
                if values_elem is not None:
                    display_name_elem = ns.find(values_elem, 'displayName')
                    if display_name_elem is not None:
                        vs_desc = display_name_elem.text
            
            # Clean up the description to extract just the meaningful name
            if vs_desc and vs_desc != "N/A":
                original_desc = vs_desc
                vs_desc = _clean_refset_description(vs_desc)
            vs_system = code_system.text if code_system is not None else "N/A"
            
            # Look for context information (table and column) - first try within valueSet
            table_elem = ns.find_with_path(valueset, './/table')
            column_elem = ns.find_with_path(valueset, './/column')
            
            # If not found within valueSet, look in parent elements (for pseudo-refsets)
            if table_elem is None or column_elem is None:
                # Find the parent criterion that contains this valueSet
                parent_criterion = None
                # Find all criteria using namespace handler
                criteria = ns.findall_with_path(root, './/criterion')
                for criterion in criteria:
                    if valueset in criterion.iter():
                        parent_criterion = criterion
                        break
                
                if parent_criterion is not None:
                    if table_elem is None:
                        table_elem = ns.find(parent_criterion, 'table')
                    if column_elem is None:
                        column_elem = ns.find_with_path(parent_criterion, './/column')
            
            table_context = table_elem.text if table_elem is not None else None
            column_context = column_elem.text if column_elem is not None else None
            
            # Find all values elements within this valueSet using namespace handler
            values_elements = ns.findall_with_path(valueset, './/values')
            
            for values in values_elements:
                # Get metadata that applies to all values in this set - prioritize non-namespaced
                include_children_elem = ns.find(values, 'includeChildren')
                include_children = include_children_elem.text if include_children_elem is not None else "false"
                
                is_refset_elem = ns.find(values, 'isRefset')
                is_refset = is_refset_elem.text if is_refset_elem is not None else "false"
                
                # Check if this is a refset - if so, there's usually only one value
                is_refset_bool = is_refset.lower() == 'true'
                
                # Find all value elements using namespace handler
                value_elements = ns.findall(values, 'value')
                
                for value in value_elements:
                    emis_guid = value.text if value.text else "N/A"
                    
                    # For refsets, get displayName from values element or use valueSet description
                    if is_refset_bool:
                        # First try to get displayName from the values element (Pattern 1)
                        display_name_elem = ns.find(values, 'displayName')
                        if display_name_elem is not None:
                            xml_display_name = display_name_elem.text
                        else:
                            # Fall back to valueSet description (Pattern 2) 
                            xml_display_name = vs_desc
                    else:
                        # Get displayName - could be child of value or sibling
                        display_name_elem = ns.find(value, 'displayName')
                        if display_name_elem is None:
                            # Try finding displayName as sibling of value
                            display_name_elem = ns.find(values, 'displayName')
                        
                        xml_display_name = display_name_elem.text if display_name_elem is not None else "N/A"
                    
                    # Determine flags based on XML structure
                    is_pseudorefset_flag = False
                    is_pseudomember_flag = False
                    
                    if has_refset_flag:  # This valueSet contains a refset
                        if is_refset_bool:  # This specific code is the refset identifier
                            if is_pseudo_refset_container:
                                is_pseudorefset_flag = True  # Pseudo-refset identifier
                            # If not pseudo, it's a true refset (is_refset=True is sufficient)
                        else:  # This is a member code in the same valueSet as a refset
                            if is_pseudo_refset_container:
                                is_pseudomember_flag = True  # Member of pseudo-refset
                    
                    emis_guids.append({
                        'valueSet_guid': vs_id,
                        'valueSet_description': vs_desc,
                        'code_system': vs_system,
                        'emis_guid': emis_guid,
                        'xml_display_name': xml_display_name,
                        'include_children': include_children.lower() == 'true',
                        'is_refset': is_refset_bool,
                        'is_pseudorefset': is_pseudorefset_flag,
                        'is_pseudomember': is_pseudomember_flag,
                        'table_context': table_context,
                        'column_context': column_context,
                        'source_guid': source_guid  # Track which search/report this came from
                    })
        
        # Find all libraryItem elements (internal EMIS libraries) using namespace handler
        library_items = ns.findall_with_path(root, './/libraryItem')
        for library_item in library_items:
            library_guid = library_item.text if library_item.text else "N/A"
            
            # Find context information for the library item
            table_context = None
            column_context = None
            
            # Find the parent criterion that contains this libraryItem
            parent_criterion = None
            # Find all criteria using namespace handler
            criteria = ns.findall_with_path(root, './/criterion')
            for criterion in criteria:
                if library_item in criterion.iter():
                    parent_criterion = criterion
                    break
            
            if parent_criterion is not None:
                table_elem = ns.find(parent_criterion, 'table')
                table_context = table_elem.text if table_elem is not None else None
                
                # Find column context from the columnValue that contains this libraryItem
                column_value = None
                # Find all columnValue using namespace handler
                column_values = ns.findall_with_path(parent_criterion, './/columnValue')
                for cv in column_values:
                    if library_item in cv.iter():
                        column_value = cv
                        break
                
                if column_value is not None:
                    column_elem = ns.find(column_value, 'column')
                    column_context = column_elem.text if column_elem is not None else None
            
            # Classify library items based on context (similar to valueSet logic)
            code_system = "UNKNOWN"
            if column_context:
                if column_context.upper() in ['READCODE', 'SNOMEDCODE']:
                    code_system = "CLINICAL_CODES"
                elif column_context.upper() in ['DRUGCODE']:
                    code_system = "MEDICATION_CODES"
            
            emis_guids.append({
                'valueSet_guid': library_guid,  # Use library GUID as the valueSet identifier
                'valueSet_description': f"EMIS Library Item {library_guid}",
                'code_system': code_system,
                'emis_guid': library_guid,
                'xml_display_name': f"Library Item: {library_guid}",
                'include_children': False,  # Library items don't have children
                'is_refset': False,  # Library items are not refsets
                'is_library_item': True,  # Flag to identify library items
                'table_context': table_context,
                'column_context': column_context,
                'source_guid': source_guid  # Track which search/report this came from
            })
        
        return emis_guids
        
    except ET.ParseError as e:
        raise Exception(f"XML parsing error: {str(e)}")
    except Exception as e:
        raise Exception(f"Error processing XML: {str(e)}")

def is_pseudo_refset_from_xml_structure(valueset_element, ns):
    """
    Detect if a valueSet is a pseudo-refset based on XML structure.
    
    True refsets: <isRefset>true</isRefset></values></valueSet> (ends immediately)
    Pseudo refsets: <isRefset>true</isRefset></values><values><value> (continues with member codes)
    """
    try:
        # Find all values elements within this valueSet
        values_elements = ns.findall_with_path(valueset_element, './/values')
        
        # Check if any values element has isRefset = true
        refset_values_element = None
        for values in values_elements:
            is_refset_elem = ns.find(values, 'isRefset')
            if is_refset_elem is not None and is_refset_elem.text and is_refset_elem.text.lower() == 'true':
                refset_values_element = values
                break
        
        if refset_values_element is None:
            return False  # Not a refset at all
        
        # Count total values elements in this valueSet
        total_values_count = len(values_elements)
        
        # True refset: Only ONE values element (the one with isRefset=true)
        # Pseudo refset: MULTIPLE values elements (isRefset=true + member values)
        if total_values_count == 1:
            return False  # True refset - only the refset identifier itself
        else:
            return True   # Pseudo refset - has member codes after the refset identifier
            
    except Exception:
        return False  # Fallback to false if structure analysis fails


def is_pseudo_refset(identifier, valueset_description):
    """
    Legacy function kept for compatibility. 
    Proper detection should use is_pseudo_refset_from_xml_structure during XML parsing.
    """
    # This is kept for backward compatibility but should not be used for new code
    # The proper detection happens during XML structure analysis
    return False

def get_medication_type_flag(code_system):
    """Determine medication type flag based on code system from XML."""
    code_system_upper = code_system.upper() if code_system else ""
    
    # Check for specific medication type flags in the code system
    if code_system_upper == 'SCT_CONST':
        return 'SCT_CONST (Constituent)'
    elif code_system_upper == 'SCT_DRGGRP':
        return 'SCT_DRGGRP (Drug Group)'
    elif code_system_upper == 'SCT_PREP':
        return 'SCT_PREP (Preparation)'
    else:
        return 'Standard Medication'

def is_medication_code_system(code_system, table_context=None, column_context=None):
    """Check if the code system indicates this is a medication, considering XML context."""
    code_system_upper = code_system.upper() if code_system else ""
    
    # Exclude internal EMIS system codes - these are never medications
    if code_system_upper == 'EMISINTERNAL':
        return False
    
    # First check explicit medication code systems
    if code_system_upper in ['SCT_CONST', 'SCT_DRGGRP', 'SCT_PREP']:
        return True
    
    # Check for medication context even if codeSystem is SNOMED_CONCEPT
    # Must be both medication table AND drug column (not status, date, etc.)
    if (table_context and column_context and 
        table_context.upper() in ['MEDICATION_ISSUES', 'MEDICATION_COURSES'] and 
        column_context.upper() == 'DRUGCODE'):
        return True
        
    return False

def is_clinical_code_system(code_system, table_context=None, column_context=None):
    """Check if the code system indicates this is a clinical code, considering XML context."""
    code_system_upper = code_system.upper() if code_system else ""
    
    # Exclude internal EMIS system codes - these are never clinical codes
    if code_system_upper == 'EMISINTERNAL':
        return False
    
    # If it's a medication context, it's not clinical
    if (table_context and column_context and 
        table_context.upper() in ['MEDICATION_ISSUES', 'MEDICATION_COURSES'] and 
        column_context.upper() == 'DRUGCODE'):
        return False
    
    # Otherwise, SNOMED_CONCEPT is clinical
    return code_system_upper == 'SNOMED_CONCEPT'
