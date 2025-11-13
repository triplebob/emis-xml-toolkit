"""
Universal Field Mapping System for EMIS XML Clinical Codes

This module provides standardized field names and mapping functions to ensure
consistency across all parts of the application that handle clinical codes.
"""

from typing import Dict, Any, List, Optional


# Standard field names - these are the canonical field names used throughout the application
class StandardFields:
    """Standard field names for clinical codes"""
    
    # Core identification fields
    EMIS_GUID = "EMIS GUID"
    SNOMED_CODE = "SNOMED Code"
    SNOMED_DESCRIPTION = "SNOMED Description"
    CODE_SYSTEM = "Code System"
    
    # ValueSet fields
    VALUESET_GUID = "ValueSet GUID"
    VALUESET_DESCRIPTION = "ValueSet Description"
    
    # Hierarchy and relationships
    INCLUDE_CHILDREN = "Include Children"
    NUMBER_OF_CHILDREN = "Descendants"
    
    # Source tracking fields
    SOURCE_TYPE = "Source Type"
    SOURCE_NAME = "Source Name"
    SOURCE_CONTAINER = "Source Container"
    SOURCE_GUID = "Source GUID"
    
    # Status and metadata
    MAPPING_FOUND = "Mapping Found"
    HAS_QUALIFIER = "Has Qualifier"
    
    # Internal fields (lowercase for internal use)
    INTERNAL_SOURCE_TYPE = "source_type"
    INTERNAL_SOURCE_NAME = "source_name"
    INTERNAL_SOURCE_CONTAINER = "source_container"
    INTERNAL_SOURCE_GUID = "source_guid"
    INTERNAL_REPORT_TYPE = "report_type"


# Field mapping dictionaries - map various field name variants to standard names
FIELD_MAPPINGS = {
    # EMIS GUID variants
    StandardFields.EMIS_GUID: [
        "EMIS GUID", "emis_guid", "code_value", "EMIS_GUID", "emis guid"
    ],
    
    # SNOMED Code variants
    StandardFields.SNOMED_CODE: [
        "SNOMED Code", "snomed_code", "code_value", "SNOMED_CODE", "snomed code"
    ],
    
    # SNOMED Description variants
    StandardFields.SNOMED_DESCRIPTION: [
        "SNOMED Description", "snomed_description", "display_name", "SNOMED_DESCRIPTION", 
        "snomed description", "description", "name"
    ],
    
    # Code System variants
    StandardFields.CODE_SYSTEM: [
        "Code System", "code_system", "CODE_SYSTEM", "code system", "codeSystem"
    ],
    
    # ValueSet GUID variants
    StandardFields.VALUESET_GUID: [
        "ValueSet GUID", "VALUESET GUID", "valueset_guid", "value_set_id", 
        "valueSet_guid", "valueset_id", "VALUESET_GUID", "ValueSetGUID"
    ],
    
    # ValueSet Description variants
    StandardFields.VALUESET_DESCRIPTION: [
        "ValueSet Description", "VALUESET Description", "valueset_description", 
        "value_set_description", "valueSet_description", "valueset_desc", 
        "VALUESET_DESCRIPTION", "ValueSetDescription"
    ],
    
    # Include Children variants
    StandardFields.INCLUDE_CHILDREN: [
        "Include Children", "include_children", "INCLUDE_CHILDREN", "includeChildren",
        "include children", "Include_Children"
    ],
    
    # Number of Children variants
    StandardFields.NUMBER_OF_CHILDREN: [
        "Number of Children", "number_of_children", "NUMBER_OF_CHILDREN", 
        "numberOfChildren", "number children", "child_count", "descendants", "Descendants"
    ],
    
    # Source Type variants
    StandardFields.SOURCE_TYPE: [
        "Source Type", "source_type", "SOURCE_TYPE", "sourceType", "source type",
        "report_type", "Source_Type"
    ],
    
    # Source Name variants
    StandardFields.SOURCE_NAME: [
        "Source Name", "source_name", "SOURCE_NAME", "sourceName", "source name",
        "source_report_name", "report_name", "name", "Source_Name"
    ],
    
    # Source Container variants
    StandardFields.SOURCE_CONTAINER: [
        "Source Container", "source_container", "SOURCE_CONTAINER", "sourceContainer",
        "source container", "container", "column_group_name", "Source_Container"
    ],
    
    # Mapping Found variants
    StandardFields.MAPPING_FOUND: [
        "Mapping Found", "mapping_found", "MAPPING_FOUND", "mappingFound", 
        "mapping found", "found", "status"
    ],
    
    # Has Qualifier variants
    StandardFields.HAS_QUALIFIER: [
        "Has Qualifier", "has_qualifier", "HAS_QUALIFIER", "hasQualifier",
        "has qualifier", "HasQualifier", "qualifier"
    ]
}


def fix_code_system(raw_code_system: str, data: Dict[str, Any]) -> str:
    """
    Fix code system field - ensure it's not a table name.
    
    Args:
        raw_code_system: Raw code system value
        data: Complete code data for context
        
    Returns:
        Corrected code system string
    """
    if not raw_code_system:
        return 'SNOMED_CONCEPT'  # Default
    
    # Check if it's a table name (these are not code systems)
    table_names = ['EVENTS', 'MEDICATION_ISSUES', 'MEDICATION_COURSES', 'PATIENTS', 'GPES_JOURNALS']
    if raw_code_system.upper() in table_names:
        # For medications, try to determine the actual code system
        logical_table = data.get('logical_table', '').upper()
        if logical_table in ['MEDICATION_ISSUES', 'MEDICATION_COURSES']:
            # Default medication code system
            return 'SNOMED_CONCEPT'
        else:
            # Default clinical code system
            return 'SNOMED_CONCEPT'
    
    # If it's already a valid code system, return as-is
    valid_code_systems = ['SNOMED_CONCEPT', 'SCT_APPNAME', 'SCT_CONST', 'SCT_DRGGRP', 'SCT_PREP', 'LIBRARY_ITEM', 'EMISINTERNAL']
    if raw_code_system.upper() in valid_code_systems:
        return raw_code_system.upper()
    
    # Default fallback
    return 'SNOMED_CONCEPT'


def format_source_type(raw_source_type: str, data: Dict[str, Any]) -> str:
    """
    Format source type with proper icons and specific report type information.
    
    Args:
        raw_source_type: Raw source type value
        data: Complete code data for context
        
    Returns:
        Formatted source type string with icon and specific type
    """
    if not raw_source_type:
        return ''
    
    # Check if already formatted (has emoji)
    if '🔍' in raw_source_type or '📊' in raw_source_type:
        return raw_source_type
    
    source_type_lower = raw_source_type.lower()
    
    # Search types
    if source_type_lower == 'search':
        return '🔍 Search'
    
    # Report types - get specific report type from data
    if source_type_lower == 'report':
        # Check for specific report type in various fields
        report_type = (data.get('report_type') or 
                      data.get('source_report_type') or 
                      data.get('_original_fields', {}).get('report_type') or
                      data.get('_original_fields', {}).get('source_report_type'))
        
        if report_type:
            report_type_lower = str(report_type).lower()
            if 'list' in report_type_lower:
                return '📊 List Report'
            elif 'audit' in report_type_lower:
                return '📊 Audit Report'  
            elif 'aggregate' in report_type_lower:
                return '📊 Aggregate Report'
            else:
                # Capitalize the specific report type
                return f"📊 {report_type.title()} Report"
        else:
            return '📊 Report'
    
    # Default formatting - capitalize first letter
    return raw_source_type.title()


def get_field_value(data: Dict[str, Any], standard_field: str, default: Any = None) -> Any:
    """
    Get a field value using the standard field name, checking all possible variants.
    
    Args:
        data: Dictionary containing the data
        standard_field: Standard field name from StandardFields class
        default: Default value if field not found
        
    Returns:
        Field value or default if not found
    """
    if standard_field not in FIELD_MAPPINGS:
        # If not in mappings, try the field name directly
        return data.get(standard_field, default)
    
    # Check all possible field name variants
    for field_variant in FIELD_MAPPINGS[standard_field]:
        if field_variant in data:
            return data[field_variant]
    
    return default


def standardize_clinical_code(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a clinical code dictionary to use standard field names.
    
    Args:
        data: Clinical code dictionary with potentially non-standard field names
        
    Returns:
        Dictionary with standardized field names
    """
    standardized = {}
    
    # Map all standard fields
    standardized[StandardFields.EMIS_GUID] = get_field_value(data, StandardFields.EMIS_GUID, '')
    
    # Special handling for true refsets: EMIS GUID IS the SNOMED code
    is_refset = data.get('is_refset', False)
    if is_refset:
        # For true refsets, EMIS GUID = SNOMED Code
        emis_guid = standardized[StandardFields.EMIS_GUID]
        standardized[StandardFields.SNOMED_CODE] = emis_guid
        
        # Use the best available description for SNOMED Description
        display_name = data.get('display_name', '')
        valueset_desc = get_field_value(data, StandardFields.VALUESET_DESCRIPTION, '')
        
        if display_name and display_name.startswith('Refset: '):
            # Clean "Refset: ETHNALL_COD[999022611000230100]" -> "ETHNALL_COD"
            clean_desc = display_name.replace('Refset: ', '').split('[')[0]
            standardized[StandardFields.SNOMED_DESCRIPTION] = clean_desc
        elif valueset_desc and valueset_desc != 'No ValueSet Description Defined In The XML':
            # Use ValueSet Description as SNOMED Description for refsets
            standardized[StandardFields.SNOMED_DESCRIPTION] = valueset_desc
        elif display_name:
            standardized[StandardFields.SNOMED_DESCRIPTION] = display_name
    else:
        # Regular codes: preserve SNOMED Code from lookup if available
        standardized[StandardFields.SNOMED_CODE] = get_field_value(data, StandardFields.SNOMED_CODE, '')
        standardized[StandardFields.SNOMED_DESCRIPTION] = get_field_value(data, StandardFields.SNOMED_DESCRIPTION, '')
    # Fix code system - don't use table names as code systems
    raw_code_system = get_field_value(data, StandardFields.CODE_SYSTEM, '')
    standardized[StandardFields.CODE_SYSTEM] = fix_code_system(raw_code_system, data)
    standardized[StandardFields.VALUESET_GUID] = get_field_value(data, StandardFields.VALUESET_GUID, '')
    # Handle ValueSet description with fallback for truly blank cases
    valueset_desc = get_field_value(data, StandardFields.VALUESET_DESCRIPTION, '')
    valueset_guid = standardized[StandardFields.VALUESET_GUID]
    
    # Add placeholder text if description is empty or missing
    if not valueset_desc or not valueset_desc.strip():
        valueset_desc = 'No ValueSet Description Defined In The XML'
    
    standardized[StandardFields.VALUESET_DESCRIPTION] = valueset_desc
    
    # Handle boolean Include Children field
    include_children_raw = get_field_value(data, StandardFields.INCLUDE_CHILDREN, False)
    if isinstance(include_children_raw, bool):
        standardized[StandardFields.INCLUDE_CHILDREN] = 'Yes' if include_children_raw else 'No'
    elif str(include_children_raw).lower() in ['true', 'yes', '1']:
        standardized[StandardFields.INCLUDE_CHILDREN] = 'Yes'
    else:
        standardized[StandardFields.INCLUDE_CHILDREN] = 'No'
    
    # Number of Children should come from lookup table descendants, not XML
    # Prioritize Descendants field from lookup over existing Number of Children field
    if 'Descendants' in data:
        descendants_value = data['Descendants']
    elif StandardFields.NUMBER_OF_CHILDREN in data:
        descendants_value = data[StandardFields.NUMBER_OF_CHILDREN]
    else:
        descendants_value = get_field_value(data, StandardFields.NUMBER_OF_CHILDREN, '0')
    standardized[StandardFields.NUMBER_OF_CHILDREN] = str(descendants_value)
    
    # Has Qualifier should come from lookup table
    if 'Has Qualifier' in data:
        qualifier_value = data['Has Qualifier']
    elif StandardFields.HAS_QUALIFIER in data:
        qualifier_value = data[StandardFields.HAS_QUALIFIER]
    else:
        qualifier_value = get_field_value(data, StandardFields.HAS_QUALIFIER, '0')
    
    # Convert 0/1 to False/True for display
    if str(qualifier_value) == '1':
        standardized[StandardFields.HAS_QUALIFIER] = 'True'
    else:
        standardized[StandardFields.HAS_QUALIFIER] = 'False'
    
    
    # Format source type with proper icons and capitalization
    raw_source_type = get_field_value(data, StandardFields.SOURCE_TYPE, '')
    standardized[StandardFields.SOURCE_TYPE] = format_source_type(raw_source_type, data)
    standardized[StandardFields.SOURCE_NAME] = get_field_value(data, StandardFields.SOURCE_NAME, '')
    standardized[StandardFields.SOURCE_CONTAINER] = get_field_value(data, StandardFields.SOURCE_CONTAINER, '')
    
    # Set mapping status: refsets are always "Found" since EMIS GUID = SNOMED Code
    if is_refset:
        standardized[StandardFields.MAPPING_FOUND] = 'Found'
    else:
        standardized[StandardFields.MAPPING_FOUND] = get_field_value(data, StandardFields.MAPPING_FOUND, 'Found')
    
    # Preserve internal fields for processing
    standardized[StandardFields.INTERNAL_SOURCE_TYPE] = get_field_value(data, StandardFields.INTERNAL_SOURCE_TYPE, 
                                                                       standardized[StandardFields.SOURCE_TYPE].lower())
    standardized[StandardFields.INTERNAL_SOURCE_NAME] = get_field_value(data, StandardFields.INTERNAL_SOURCE_NAME,
                                                                       standardized[StandardFields.SOURCE_NAME])
    standardized[StandardFields.INTERNAL_SOURCE_CONTAINER] = get_field_value(data, StandardFields.INTERNAL_SOURCE_CONTAINER,
                                                                            standardized[StandardFields.SOURCE_CONTAINER])
    standardized[StandardFields.INTERNAL_SOURCE_GUID] = get_field_value(data, StandardFields.INTERNAL_SOURCE_GUID, '')
    standardized[StandardFields.INTERNAL_REPORT_TYPE] = get_field_value(data, StandardFields.INTERNAL_REPORT_TYPE, 
                                                                       standardized[StandardFields.SOURCE_TYPE].lower())
    
    # Preserve important fields that aren't in standard mappings
    if 'is_refset' in data:
        standardized['is_refset'] = data['is_refset']
    if 'is_pseudo' in data:
        standardized['is_pseudo'] = data['is_pseudo']
    if 'is_medication' in data:
        standardized['is_medication'] = data['is_medication']
    if 'is_pseudorefset' in data:
        standardized['is_pseudorefset'] = data['is_pseudorefset']
    if 'is_pseudomember' in data:
        standardized['is_pseudomember'] = data['is_pseudomember']
    
    # Preserve original data for debugging (including lookup results)
    debug_data = data.copy()
    
    # Add standardized values to debug data for complete visibility
    debug_data['standardized_emis_guid'] = standardized[StandardFields.EMIS_GUID]
    debug_data['standardized_snomed_code'] = standardized[StandardFields.SNOMED_CODE]
    debug_data['standardized_descendants'] = standardized[StandardFields.NUMBER_OF_CHILDREN]
    debug_data['standardized_has_qualifier'] = standardized[StandardFields.HAS_QUALIFIER]
    debug_data['standardized_mapping_found'] = standardized[StandardFields.MAPPING_FOUND]
    
    # Add raw EMIS GUID extraction for debugging
    raw_emis_guid = get_field_value(data, StandardFields.EMIS_GUID, 'NOT_FOUND')
    debug_data['raw_emis_guid_lookup'] = raw_emis_guid
    debug_data['emis_equals_snomed'] = 'YES' if standardized[StandardFields.EMIS_GUID] == standardized[StandardFields.SNOMED_CODE] else 'NO'
    
    # Also preserve raw lookup fields if they exist
    if 'Descendants' in data:
        debug_data['lookup_descendants'] = data['Descendants']
    if 'Has Qualifier' in data:
        debug_data['lookup_has_qualifier'] = data['Has Qualifier']
    if 'Code Type' in data:
        debug_data['lookup_code_type'] = data['Code Type']
    if 'Is Parent' in data:
        debug_data['lookup_is_parent'] = data['Is Parent']
    
    standardized['_original_fields'] = debug_data
    
    return standardized


def standardize_clinical_codes_list(codes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Standardize a list of clinical codes.
    
    Args:
        codes: List of clinical code dictionaries
        
    Returns:
        List of standardized clinical code dictionaries
    """
    return [standardize_clinical_code(code) for code in codes]


def get_display_columns() -> List[str]:
    """
    Get the standard display column order for clinical codes.
    
    Returns:
        List of column names in display order
    """
    return [
        StandardFields.VALUESET_DESCRIPTION,
        StandardFields.EMIS_GUID,
        StandardFields.SNOMED_CODE,
        StandardFields.SNOMED_DESCRIPTION,
        StandardFields.MAPPING_FOUND,
        StandardFields.INCLUDE_CHILDREN,
        StandardFields.NUMBER_OF_CHILDREN,
        StandardFields.HAS_QUALIFIER,
        StandardFields.CODE_SYSTEM,
        StandardFields.SOURCE_TYPE,
        StandardFields.SOURCE_NAME,
        StandardFields.SOURCE_CONTAINER,
    ]


def get_source_columns() -> List[str]:
    """
    Get the source tracking columns that should be hidden in unique mode.
    
    Returns:
        List of source column names
    """
    return [
        StandardFields.SOURCE_TYPE,
        StandardFields.SOURCE_NAME,
        StandardFields.SOURCE_CONTAINER,
    ]


def get_hidden_columns(include_debug: bool = False) -> List[str]:
    """
    Get columns that should be hidden from UI display.
    
    Args:
        include_debug: If True, includes debug columns like _original_fields
    
    Returns:
        List of column names to hide
    """
    hidden = [
        StandardFields.VALUESET_GUID,  # Hidden but used for processing
        StandardFields.INTERNAL_SOURCE_TYPE,
        StandardFields.INTERNAL_SOURCE_NAME,
        StandardFields.INTERNAL_SOURCE_CONTAINER,
        StandardFields.INTERNAL_SOURCE_GUID,
        StandardFields.INTERNAL_REPORT_TYPE,
        'is_refset',  # Internal categorization flag, not needed in UI
        'is_pseudo',  # Internal categorization flag, not needed in UI
    ]
    
    # Conditionally include debug information
    if not include_debug:
        hidden.append('_original_fields')  # Debug information
    
    return hidden
