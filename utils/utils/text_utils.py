"""
Text utility functions for EMIS XML Convertor
Provides common text formatting and pluralization helpers
"""

def pluralize_unit(value, unit):
    """
    Handle singular vs plural units correctly for medical/clinical contexts
    
    Args:
        value: The numeric value (can be string, int, or float)
        unit: The unit name (e.g., 'year', 'month', 'day', 'week')
    
    Returns:
        str: Correctly pluralized unit
        
    Examples:
        pluralize_unit(1, 'year') → 'year'
        pluralize_unit(18, 'years') → 'years'
        pluralize_unit('1', 'month') → 'month'
        pluralize_unit('-6', 'months') → 'months'
    """
    unit_lower = unit.lower()
    
    # Convert value to int for comparison, handle string values
    try:
        # Handle negative values by removing the minus sign
        numeric_value = int(float(str(value).replace('-', '')))
    except (ValueError, TypeError):
        numeric_value = 2  # Default to plural if can't parse
    
    if numeric_value == 1:
        # Singular forms
        if unit_lower in ['years', 'year']:
            return 'year'
        elif unit_lower in ['months', 'month']:
            return 'month'
        elif unit_lower in ['days', 'day']:
            return 'day'
        elif unit_lower in ['weeks', 'week']:
            return 'week'
        elif unit_lower in ['hours', 'hour']:
            return 'hour'
        elif unit_lower in ['minutes', 'minute']:
            return 'minute'
        elif unit_lower in ['records', 'record']:
            return 'record'
        elif unit_lower in ['codes', 'code']:
            return 'code'
        elif unit_lower in ['patients', 'patient']:
            return 'patient'
        else:
            # Generic: remove 's' if present
            return unit_lower.rstrip('s')
    else:
        # Plural forms
        if unit_lower in ['year', 'years']:
            return 'years'
        elif unit_lower in ['month', 'months']:
            return 'months'
        elif unit_lower in ['day', 'days']:
            return 'days'
        elif unit_lower in ['week', 'weeks']:
            return 'weeks'
        elif unit_lower in ['hour', 'hours']:
            return 'hours'
        elif unit_lower in ['minute', 'minutes']:
            return 'minutes'
        elif unit_lower in ['record', 'records']:
            return 'records'
        elif unit_lower in ['code', 'codes']:
            return 'codes'
        elif unit_lower in ['patient', 'patients']:
            return 'patients'
        else:
            # Generic: add 's' if not already present
            return unit_lower if unit_lower.endswith('s') else unit_lower + 's'


def format_operator_text(operator, is_numeric=False):
    """
    Convert operator codes to human-readable text
    
    Args:
        operator: The operator code (e.g., 'GTEQ', 'LT', 'EQ')
        is_numeric: True for numeric comparisons, False for date comparisons
        
    Returns:
        str: Human-readable operator text
        
    Examples:
        format_operator_text('GTEQ', is_numeric=True) → 'greater than or equal to'
        format_operator_text('GTEQ', is_numeric=False) → 'on or after'
    """
    if is_numeric:
        operator_map = {
            'GT': 'greater than',
            'GTEQ': 'greater than or equal to',
            'LT': 'less than',
            'LTEQ': 'less than or equal to',
            'EQ': 'equal to',
            'NEQ': 'not equal to'
        }
    else:
        # Date/time operators
        operator_map = {
            'GT': 'after',
            'GTEQ': 'on or after',
            'LT': 'before',
            'LTEQ': 'on or before',
            'EQ': 'on',
            'NEQ': 'not on'
        }
    
    return operator_map.get(operator.upper(), operator)


def format_clinical_description(column, action="include"):
    """
    Generate consistent descriptions for clinical data columns
    
    Args:
        column: The column name (e.g., 'READCODE', 'DRUGCODE', 'AGE')
        action: The action being performed ('include', 'exclude', 'filter')
        
    Returns:
        str: Formatted description
    """
    column_upper = column.upper()
    action_verb = action.lower()
    
    if column_upper in ['READCODE', 'SNOMEDCODE']:
        return f"{action_verb.title()} specified clinical codes"
    elif column_upper in ['DRUGCODE']:
        return f"{action_verb.title()} specified medication codes"
    elif column_upper in ['DISPLAYTERM', 'NAME']:
        return f"{action_verb.title()} medication names/descriptions"
    elif column_upper in ['AGE']:
        return f"Patient age {action_verb}ing"
    elif column_upper == 'AGE_AT_EVENT':
        return f"Patient age at event {action_verb}ing"
    elif column_upper == 'NUMERIC_VALUE':
        return f"Numeric value {action_verb}ing"
    elif column_upper in ['DATE', 'ISSUE_DATE', 'CONSULTATION_DATE']:
        return f"Date {action_verb}ing"
    elif column_upper == 'DOB':
        return f"Date of birth {action_verb}ing"
    elif column_upper in ['EPISODE']:
        return f"Episode type {action_verb}ing"
    else:
        return f"{column} {action_verb}ing"
