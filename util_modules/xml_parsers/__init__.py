"""
XML Parsing utilities for EMIS XML Convertor
Modularized parsing functions for different XML elements
"""

from .criterion_parser import parse_criterion, parse_column_filter, CriterionParser
from .restriction_parser import parse_restriction, RestrictionParser
from .value_set_parser import parse_value_set, ValueSetParser
from .linked_criteria_parser import parse_linked_criterion, LinkedCriteriaParser
from .base_parser import XMLParserBase, get_namespaces
from .xml_utils import (
    parse_xml_for_emis_guids, 
    is_pseudo_refset, 
    is_pseudo_refset_from_xml_structure,
    get_medication_type_flag, 
    is_medication_code_system, 
    is_clinical_code_system
)

__all__ = [
    'parse_criterion',
    'parse_column_filter', 
    'parse_restriction',
    'parse_value_set',
    'parse_linked_criterion',
    'CriterionParser',
    'RestrictionParser',
    'ValueSetParser', 
    'LinkedCriteriaParser',
    'XMLParserBase',
    'get_namespaces',
    'parse_xml_for_emis_guids',
    'is_pseudo_refset',
    'is_pseudo_refset_from_xml_structure',
    'get_medication_type_flag',
    'is_medication_code_system',
    'is_clinical_code_system'
]
