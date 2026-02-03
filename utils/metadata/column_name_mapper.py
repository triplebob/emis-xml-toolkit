"""
Column name display mappings for EMIS XML.
Maps technical column names to user-friendly display names.
Based on documented EMIS XML patterns.
"""

# Comprehensive mapping of EMIS column names to display names
# Based on documented EMIS XML patterns and compatibility code translations
COLUMN_DISPLAY_NAMES = {
    # Date columns
    "DOB": "Date of Birth",
    "ISSUE_DATE": "Date of Issue",
    "RECORDED_DATE": "Date Recorded",
    "START_DATE": "Start Date",
    "END_DATE": "End Date",
    "LASTISSUE_DATE": "Last Issue Date",
    "REGISTRATION_DATE": "Registration Date",
    "DEDUCTION_DATE": "Deduction Date",
    "DEATH_DATE": "Date of Death",
    "CONSULTATION_DATE": "Consultation Date",
    "EVENT_DATE": "Event Date",
    "AUTHORISED_DATE": "Authorised Date",
    "PRESCRIPTION_DATE": "Prescription Date",
    "COMMENCE_DATE": "Commencement Date",
    "DATE": "Date",

    # Patient demographics
    "PATIENT": "Patient",
    "PATIENT_NAME": "Patient Name",
    "AGE": "Age",
    "AGE_AT_EVENT": "Age at Event",
    "SEX": "Sex",
    "GENDER": "Gender",
    "NHS_NUMBER": "NHS Number",
    "PATIENT_ID": "Patient ID",

    # Medication columns
    "DRUG_CODE": "Drug Code",
    "DRUGCODE": "Medication Code",
    "MEDICATION_NAME": "Medication Name",
    "DISPLAYTERM": "Drug Display Name",
    "AUTHORIZING_USER": "Authorising User",
    "COURSE_ID": "Course ID",
    "QUANTITY_UNIT": "Quantity Unit",
    "NAME": "Name",

    # Clinical data
    "CODE": "Clinical Code",
    "TERM": "Clinical Term",
    "RUBRIC": "Rubric",
    "PROBLEM": "Problem",
    "CONSULTATION_HEADING": "Consultation Heading",
    "READCODE": "SNOMED Code",
    "SNOMEDCODE": "SNOMED Code",
    "CONCEPT_ID": "SNOMED Concept",
    "CODE_DESCRIPTION": "Code Description",
    "ASSOCIATEDTEXT": "Associated Text",

    # Numeric values
    "NUMERIC_VALUE": "Numeric Value",
    "VALUE": "Value",
    "RESULT": "Result",
    "UNITS": "Units",

    # User and practice
    "AUTHOR": "Author",
    "USER": "User",
    "CURRENTLY_CONTRACTED": "Currently Contracted",
    "PRACTICE_CODE": "Practice Code",

    # Other common columns
    "ACTIVE": "Active",
    "STATUS": "Status",
    "TYPE": "Type",
    "IS_PRIVATE": "Privately Prescribed",

    # LSOA (Lower Layer Super Output Area)
    "LONDON_LSOA": "Lower Layer Area",
    "LSOA": "Lower Layer Area",
    "IMD": "Index of Multiple Deprivation",
}


def get_column_display_name(column_name: str) -> str:
    """
    Get the user-friendly display name for a column.

    Args:
        column_name: The technical column name (e.g., "ISSUE_DATE", "DOB")

    Returns:
        The display name (e.g., "Date of Issue", "Date of Birth")
        Falls back to title-cased version if not in mapping.

    Examples:
        >>> get_column_display_name("ISSUE_DATE")
        "Date of Issue"
        >>> get_column_display_name("DOB")
        "Date of Birth"
        >>> get_column_display_name("CUSTOM_FIELD")
        "Custom Field"
    """
    if not column_name:
        return ""

    # Check exact match first (case-insensitive)
    upper_name = column_name.upper().strip()
    if upper_name in COLUMN_DISPLAY_NAMES:
        return COLUMN_DISPLAY_NAMES[upper_name]

    # Fallback: split on underscores and title case
    words = column_name.replace("_", " ").split()
    cleaned = " ".join(word.capitalize() for word in words if word)

    return cleaned if cleaned else column_name
