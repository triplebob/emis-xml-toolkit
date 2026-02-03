"""
Processing statistics for ClinXML.
Builds audit metrics for the analytics tab.
"""

from datetime import datetime


def create_processing_stats(
    xml_filename,
    xml_content=None,
    emis_guids=None,
    translated_codes=None,
    processing_time=None,
    file_size_bytes=None,
):
    """Create comprehensive processing and audit statistics."""
    processing_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Basic XML and file stats
    if file_size_bytes is None and xml_content is not None:
        file_size_bytes = len(xml_content.encode('utf-8'))
    if file_size_bytes is None:
        file_size_bytes = 0
    xml_stats = {
        'filename': xml_filename,
        'file_size_bytes': file_size_bytes,
        'processing_timestamp': processing_timestamp,
        'processing_time_seconds': processing_time
    }
    
    def _get_guid(entry):
        return entry.get('emis_guid') or entry.get('EMIS GUID')

    def _get_valueset(entry):
        return entry.get('valueSet_guid') or entry.get('ValueSet GUID')

    def _get_display(entry):
        return entry.get('xml_display_name') or entry.get('SNOMED Description')

    emis_guids = emis_guids or []
    translated_codes = translated_codes or {}

    # XML structure analysis - handle empty GUID lists for geographical XMLs
    if emis_guids:
        valueset_count = len(set(v for v in (_get_valueset(g) for g in emis_guids) if v))
        unique_guids_count = len(set(g for g in (_get_guid(g) for g in emis_guids) if g))
        total_guid_occurrences = len(emis_guids)
    else:
        valueset_count = 0
        unique_guids_count = 0
        total_guid_occurrences = 0
    
    xml_structure_stats = {
        'total_valuesets': valueset_count,
        'unique_emis_guids': unique_guids_count,
        'total_guid_occurrences': total_guid_occurrences,
        'duplicate_guid_ratio': round((total_guid_occurrences - unique_guids_count) / total_guid_occurrences * 100, 2) if total_guid_occurrences > 0 else 0
    }
    
    # Code system breakdown - handle empty GUID lists
    code_systems = {}
    if emis_guids:
        for guid in emis_guids:
            system = guid.get('code_system', 'Unknown')
            code_systems[system] = code_systems.get(system, 0) + 1
    
    # Translation accuracy stats - handle empty results for geographical XMLs
    clinical_found = sum(1 for code in translated_codes.get('clinical', []) if code.get('Mapping Found') == 'Found')
    clinical_total = len(translated_codes.get('clinical', []))
    
    medication_found = sum(1 for code in translated_codes.get('medications', []) if code.get('Mapping Found') == 'Found')
    medication_total = len(translated_codes.get('medications', []))
    
    pseudo_clinical_found = sum(1 for code in translated_codes.get('clinical_pseudo_members', []) if code.get('Mapping Found') == 'Found')
    pseudo_clinical_total = len(translated_codes.get('clinical_pseudo_members', []))
    
    pseudo_medication_found = sum(1 for code in translated_codes.get('medication_pseudo_members', []) if code.get('Mapping Found') == 'Found')
    pseudo_medication_total = len(translated_codes.get('medication_pseudo_members', []))
    
    translation_stats = {
        'clinical_codes': {
            'found': clinical_found,
            'total': clinical_total,
            'success_rate': round(clinical_found / clinical_total * 100, 2) if clinical_total > 0 else 0
        },
        'medications': {
            'found': medication_found,
            'total': medication_total,
            'success_rate': round(medication_found / medication_total * 100, 2) if medication_total > 0 else 0
        },
        'pseudo_refset_clinical': {
            'found': pseudo_clinical_found,
            'total': pseudo_clinical_total,
            'success_rate': round(pseudo_clinical_found / pseudo_clinical_total * 100, 2) if pseudo_clinical_total > 0 else 0
        },
        'pseudo_refset_medications': {
            'found': pseudo_medication_found,
            'total': pseudo_medication_total,
            'success_rate': round(pseudo_medication_found / pseudo_medication_total * 100, 2) if pseudo_medication_total > 0 else 0
        },
        'overall': {
            'found': clinical_found + medication_found + pseudo_clinical_found + pseudo_medication_found,
            'total': clinical_total + medication_total + pseudo_clinical_total + pseudo_medication_total,
            'success_rate': round((clinical_found + medication_found + pseudo_clinical_found + pseudo_medication_found) / 
                                  (clinical_total + medication_total + pseudo_clinical_total + pseudo_medication_total) * 100, 2) 
                           if (clinical_total + medication_total + pseudo_clinical_total + pseudo_medication_total) > 0 else 0
        }
    }
    
    # Category distribution - handle empty translated_codes for geographical XMLs
    category_distribution = {
        'clinical_codes': len(translated_codes.get('clinical', [])),
        'medications': len(translated_codes.get('medications', [])),
        'refsets': len(translated_codes.get('refsets', [])),
        'pseudo_refsets': len(translated_codes.get('pseudo_refsets', [])),
        'pseudo_refset_clinical_members': len(translated_codes.get('clinical_pseudo_members', [])),
        'pseudo_refset_medication_members': len(translated_codes.get('medication_pseudo_members', []))
    }
    
    # Validation flags and quality metrics
    quality_metrics = {
        'has_include_children_flags': sum(1 for guid in emis_guids if guid.get('include_children')),
        'has_table_context': sum(1 for guid in emis_guids if guid.get('table_context')),
        'has_column_context': sum(1 for guid in emis_guids if guid.get('column_context')),
        'has_display_names': sum(
            1
            for guid in emis_guids
            if (_get_display(guid) or '') not in ['N/A', 'No display name in XML', '']
        ),
        'emisinternal_codes_excluded': sum(1 for guid in emis_guids if str(guid.get('code_system', '')).upper() == 'EMISINTERNAL')
    }
    
    return {
        'xml_stats': xml_stats,
        'xml_structure': xml_structure_stats,
        'code_systems': code_systems,
        'translation_accuracy': translation_stats,
        'category_distribution': category_distribution,
        'quality_metrics': quality_metrics
    }
