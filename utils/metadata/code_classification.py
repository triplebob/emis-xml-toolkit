"""
Code classification utilities for the parsing pipeline.
"""


def get_medication_type_flag(code_system: str) -> str:
    """Determine medication type flag based on code system from XML."""
    code_system_upper = code_system.upper() if code_system else ""
    
    # Check for specific medication type flags in the code system
    if code_system_upper == 'SCT_CONST':
        return 'SCT_CONST (Constituent)'
    elif code_system_upper == 'SCT_DRGGRP':
        return 'SCT_DRGGRP (Drug Group)'
    elif code_system_upper == 'SCT_PREP':
        return 'SCT_PREP (Preparation)'
    elif code_system_upper == 'SCT_SUB':
        return 'SCT_SUB (Substance)'
    elif code_system_upper == 'SCT_FORM':
        return 'SCT_FORM (Dosage Form)'
    else:
        return ''


def _normalise_context(value) -> str:
    """Normalise table/column context into a single string."""
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item not in (None, ""))
    return str(value)


def is_medication_code_system(code_system: str, table_context: str = None, column_context: str = None) -> bool:
    """Check if the code system indicates this is a medication, considering XML context."""
    code_system_upper = code_system.upper() if code_system else ""
    table_context = _normalise_context(table_context)
    column_context = _normalise_context(column_context)
    
    # Exclude internal EMIS system codes - these are never medications
    if code_system_upper == 'EMISINTERNAL':
        return False
    
    # First check explicit medication code systems
    if code_system_upper in ['SCT_CONST', 'SCT_DRGGRP', 'SCT_PREP', 'SCT_APPNAME', 'SCT_SUB', 'SCT_FORM']:
        return True
    
    # Check table context for medication tables
    if table_context:
        table_upper = table_context.upper()
        if any(med_table in table_upper for med_table in [
            'MEDICATION_ISSUES', 'MEDICATION_COURSES', 'DRUG_', 'REPEAT_', 'ACUTE_'
        ]):
            return True
    
    # Check column context for medication columns
    if column_context:
        column_upper = column_context.upper()
        if any(med_col in column_upper for med_col in [
            'DRUGCODE', 'DRUG_', 'MEDICATION_', 'REPEAT_', 'ACUTE_', 'COMPOUND_'
        ]):
            return True
    
    # Default to false for standard SNOMED_CONCEPT
    return False


def is_clinical_code_system(code_system: str, table_context: str = None, column_context: str = None) -> bool:
    """Check if the code system indicates this is a clinical code, considering XML context."""
    code_system_upper = code_system.upper() if code_system else ""
    table_context = _normalise_context(table_context)
    column_context = _normalise_context(column_context)
    
    # Exclude internal EMIS system codes - these are never clinical codes
    if code_system_upper == 'EMISINTERNAL':
        return False
    
    # If it's a medication context, it's not clinical
    if (table_context and column_context and 
        table_context.upper() in ['MEDICATION_ISSUES', 'MEDICATION_COURSES'] and
        column_context.upper() in ['DRUGCODE', 'COMPOUND_DRUGCODE']):
        return False
    
    # If it's explicitly a medication code system, it's not clinical
    if is_medication_code_system(code_system, table_context, column_context):
        return False
    
    # Standard clinical code systems
    if code_system_upper in ['SNOMED_CONCEPT', 'READ_CODE', 'CTV3_CODE', 'ICD10_CODE']:
        return True
    
    # Check for clinical table contexts
    if table_context:
        table_upper = table_context.upper()
        if any(clinical_table in table_upper for clinical_table in [
            'OBSERVATION_', 'CONSULTATION_', 'PROBLEM_', 'DIAGNOSIS_', 'PROCEDURE_'
        ]):
            return True
    
    # Default: if it's not internal or medication, assume clinical
    return True


def is_pseudo_refset_from_xml_structure(valueset_element, namespaces: dict) -> bool:
    """
    Detect if a valueSet is a pseudo-refset based on XML structure.
    
    True refsets: <isRefset>true</isRefset></values></valueSet> (ends immediately)
    Pseudo refsets: <isRefset>true</isRefset></values><values><value> (continues with member codes)
    """
    try:
        # Find all values elements within this valueSet
        values_elements = valueset_element.findall('.//values', namespaces) + valueset_element.findall('.//emis:values', namespaces)
        
        if not values_elements:
            return False
        
        # Check each values element for refset marker
        refset_count = 0
        member_count = 0
        
        for values_elem in values_elements:
            # Check if this values element has isRefset=true
            is_refset_elem = values_elem.find('isRefset', namespaces) or values_elem.find('emis:isRefset', namespaces)
            if is_refset_elem is not None and is_refset_elem.text and is_refset_elem.text.lower() == 'true':
                refset_count += 1
            else:
                # This is a member code (has value but no isRefset=true)
                value_elem = values_elem.find('value', namespaces) or values_elem.find('emis:value', namespaces)
                if value_elem is not None and value_elem.text:
                    member_count += 1
        
        # Pseudo refset: has both refset definition AND member codes
        return refset_count > 0 and member_count > 0
        
    except Exception:
        return False
