"""
Authoritative flag registry with constraints and value domains.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Callable


Validator = Callable[[Any], bool]


@dataclass(frozen=True)
class FlagDefinition:
    name: str
    description: str
    required: bool = False
    domain: Optional[list] = None
    validator: Optional[Validator] = None

    def validate(self, value: Any) -> bool:
        if value is None:
            return not self.required
        if self.domain is not None:
            return value in self.domain
        if self.validator:
            return self.validator(value)
        return True


def _is_bool(v: Any) -> bool:
    return isinstance(v, bool)


def _is_int(v: Any) -> bool:
    return isinstance(v, int)


def _non_empty_str(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _list_str(v: Any) -> bool:
    return isinstance(v, list) and all(isinstance(i, str) for i in v)


def _list_obj(v: Any) -> bool:
    return isinstance(v, list) and all(isinstance(i, dict) for i in v)


FLAG_DEFINITIONS: Dict[str, FlagDefinition] = {
    # Identity
    "element_type": FlagDefinition("element_type", "Element classification", required=True),
    "element_id": FlagDefinition("element_id", "Element identifier", required=True, validator=_non_empty_str),
    "element_guid": FlagDefinition("element_guid", "GUID", validator=_non_empty_str),
    # Hierarchy
    "parent_search_guid": FlagDefinition("parent_search_guid", "Parent search GUID", validator=_non_empty_str),
    "criteria_group_id": FlagDefinition("criteria_group_id", "Criteria group ID", validator=_non_empty_str),
    "criterion_id": FlagDefinition("criterion_id", "Criterion ID", validator=_non_empty_str),
    "linked_criterion_parent_id": FlagDefinition("linked_criterion_parent_id", "Linked criterion parent ID", validator=_non_empty_str),
    "column_group_id": FlagDefinition("column_group_id", "Column group ID", validator=_non_empty_str),
    "logical_table_name": FlagDefinition("logical_table_name", "Logical table name", domain=["PATIENTS", "EVENTS", "MEDICATION_ISSUES", "MEDICATION_COURSES", "GPES_JOURNALS"]),
    "population_reference_guid": FlagDefinition("population_reference_guid", "Population reference GUIDs", validator=_list_str),
    "folder_id": FlagDefinition("folder_id", "Folder identifier", validator=_non_empty_str),
    "folder_path": FlagDefinition("folder_path", "Folder path", validator=_list_str),
    # Location
    "xpath_location": FlagDefinition("xpath_location", "XPath location", validator=_non_empty_str),
    "xml_tag_name": FlagDefinition("xml_tag_name", "XML tag", validator=_non_empty_str),
    # Code systems
    "code_system": FlagDefinition("code_system", "Code system"),
    "valueSet_guid": FlagDefinition("valueSet_guid", "ValueSet identifier"),
    "valueSet_description": FlagDefinition("valueSet_description", "ValueSet description"),
    "is_clinical_code": FlagDefinition("is_clinical_code", "Clinical code flag", validator=_is_bool),
    "is_medication_code": FlagDefinition("is_medication_code", "Medication code flag", validator=_is_bool),
    "is_library_item": FlagDefinition("is_library_item", "Library item", validator=_is_bool),
    "code_value": FlagDefinition("code_value", "Code value", validator=_non_empty_str),
    "display_name": FlagDefinition("display_name", "Display name", validator=_non_empty_str),
    "include_children": FlagDefinition("include_children", "Include children", validator=_is_bool),
    "is_refset": FlagDefinition("is_refset", "Refset flag", validator=_is_bool),
    "is_emisinternal": FlagDefinition("is_emisinternal", "EMIS Internal flag", validator=_is_bool),
    "is_pseudo_refset": FlagDefinition("is_pseudo_refset", "Pseudo-refset", validator=_is_bool),
    "is_pseudo_member": FlagDefinition("is_pseudo_member", "Pseudo member", validator=_is_bool),
    "inactive": FlagDefinition("inactive", "Inactive flag", validator=_is_bool),
    "legacy_value": FlagDefinition("legacy_value", "Mapped code value", validator=_non_empty_str),
    "cluster_code": FlagDefinition("cluster_code", "Cluster code identifier", validator=_non_empty_str),
    "exception_code": FlagDefinition("exception_code", "Exception code", validator=_non_empty_str),
    # Relationships
    "relationship_type": FlagDefinition("relationship_type", "Linked relationship type"),
    "parent_column": FlagDefinition("parent_column", "Parent column", validator=_non_empty_str),
    "child_column": FlagDefinition("child_column", "Child column", validator=_non_empty_str),
    "range_from_operator": FlagDefinition("range_from_operator", "Range from operator"),
    "range_from_value": FlagDefinition("range_from_value", "Range from value"),
    "range_from_unit": FlagDefinition("range_from_unit", "Range from unit"),
    "range_from_relation": FlagDefinition("range_from_relation", "Range from relation"),
    "range_to_operator": FlagDefinition("range_to_operator", "Range to operator"),
    "range_to_value": FlagDefinition("range_to_value", "Range to value"),
    "range_to_unit": FlagDefinition("range_to_unit", "Range to unit"),
    "range_to_relation": FlagDefinition("range_to_relation", "Range to relation"),
    # Context
    "negation": FlagDefinition("negation", "Negation flag", validator=_is_bool),
    "member_operator": FlagDefinition("member_operator", "Member operator"),
    "action_if_true": FlagDefinition("action_if_true", "Action if true"),
    "action_if_false": FlagDefinition("action_if_false", "Action if false"),
    # Filters
    "column_name": FlagDefinition("column_name", "Column names", validator=_list_str),
    "column_display_name": FlagDefinition("column_display_name", "Column display name", validator=_non_empty_str),
    "in_not_in": FlagDefinition("in_not_in", "In/Not In"),
    "demographics_type": FlagDefinition("demographics_type", "Demographics type"),
    "demographics_confidence": FlagDefinition("demographics_confidence", "Demographics confidence"),
    "is_patient_demographics": FlagDefinition("is_patient_demographics", "Patient demographics flag", validator=_is_bool),
    "has_parameter": FlagDefinition("has_parameter", "Parameter present", validator=_is_bool),
    "parameter_names": FlagDefinition("parameter_names", "Parameter names", validator=_list_str),
    "has_global_parameters": FlagDefinition("has_global_parameters", "Global parameters present", validator=_is_bool),
    "has_local_parameters": FlagDefinition("has_local_parameters", "Local parameters present", validator=_is_bool),
    "has_emisinternal_filters": FlagDefinition("has_emisinternal_filters", "EMISINTERNAL filters present", validator=_is_bool),
    "emisinternal_values": FlagDefinition("emisinternal_values", "EMISINTERNAL values", validator=_list_str),
    "emisinternal_entries": FlagDefinition("emisinternal_entries", "EMISINTERNAL entries", validator=_list_obj),
    "emisinternal_all_values": FlagDefinition("emisinternal_all_values", "EMISINTERNAL all-values flag", validator=_is_bool),
    "medication_type_flag": FlagDefinition("medication_type_flag", "Medication type flag", validator=_non_empty_str),
    "column_filters": FlagDefinition("column_filters", "Column filters metadata", validator=_list_obj),
    "has_explicit_valueset_description": FlagDefinition("has_explicit_valueset_description", "ValueSet has explicit description", validator=_is_bool),
    "use_guid_as_valueset_description": FlagDefinition("use_guid_as_valueset_description", "ValueSet description uses GUID", validator=_is_bool),
    "has_individual_code_display_names": FlagDefinition("has_individual_code_display_names", "ValueSet has per-code display names", validator=_is_bool),
    "linked_criteria": FlagDefinition("linked_criteria", "Linked criteria metadata", validator=_list_obj),

    # Temporal
    "has_temporal_filter": FlagDefinition("has_temporal_filter", "Temporal filter present", validator=_is_bool),
    "temporal_variable_value": FlagDefinition("temporal_variable_value", "Temporal variable value"),
    "temporal_unit": FlagDefinition("temporal_unit", "Temporal unit"),
    "temporal_relation": FlagDefinition("temporal_relation", "Temporal relation"),
    "relative_to": FlagDefinition("relative_to", "Temporal baseline reference", validator=_non_empty_str),
    # Restrictions
    "has_restriction": FlagDefinition("has_restriction", "Restriction present", validator=_is_bool),
    "restriction_type": FlagDefinition("restriction_type", "Restriction type"),
    "record_count": FlagDefinition("record_count", "Record count", validator=_is_int),
    "ordering_direction": FlagDefinition("ordering_direction", "Ordering direction"),
    "ordering_column": FlagDefinition("ordering_column", "Ordering column"),
    "has_test_conditions": FlagDefinition("has_test_conditions", "Test conditions present", validator=_is_bool),
    "test_condition_column": FlagDefinition("test_condition_column", "Test condition column"),
    "test_condition_operator": FlagDefinition("test_condition_operator", "Test condition operator"),
    # Rendering/export
    "source_file_name": FlagDefinition("source_file_name", "Source file name"),
    "source_guid": FlagDefinition("source_guid", "Source GUID"),
    "source_type": FlagDefinition("source_type", "Source type"),
    "container_type": FlagDefinition("container_type", "Container type"),
    "search_date": FlagDefinition("search_date", "Search date reference", validator=_non_empty_str),
    "report_creation_time": FlagDefinition("report_creation_time", "Report creation time", validator=_non_empty_str),
    "report_author_name": FlagDefinition("report_author_name", "Report author name", validator=_non_empty_str),
    "report_author_user_id": FlagDefinition("report_author_user_id", "Report author user ID", validator=_non_empty_str),
    "include_in_export": FlagDefinition("include_in_export", "Include in export", validator=_is_bool),
    "export_category": FlagDefinition("export_category", "Export category"),
    # Enterprise/QOF
    "enterprise_reporting_level": FlagDefinition("enterprise_reporting_level", "Enterprise level"),
    "organisation_associations": FlagDefinition("organisation_associations", "Org associations", validator=_list_obj),
    "version_independent_guid": FlagDefinition("version_independent_guid", "Version independent GUID"),
    "qmas_indicator": FlagDefinition("qmas_indicator", "QOF indicator"),
    "contract_information_needed": FlagDefinition("contract_information_needed", "Contract info needed", validator=_is_bool),
    "contract_target": FlagDefinition("contract_target", "Contract target", validator=_is_int),
}


def validate_flags(flags: Dict[str, Any]) -> Dict[str, Any]:
    """Validate flags against registry; returns cleaned subset."""
    cleaned = {}
    for key, value in flags.items():
        definition = FLAG_DEFINITIONS.get(key)
        if not definition:
            continue
        if definition.validate(value):
            cleaned[key] = value
    return cleaned
