"""
Audit and validation module for The Unofficial EMIS XML Toolkit
Tracks provenance, validation stats, and processing metrics
"""

from datetime import datetime


def create_processing_stats(xml_filename, xml_content, emis_guids, translated_codes, processing_time=None):
    """Create comprehensive processing and audit statistics."""
    processing_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Basic XML and file stats
    xml_stats = {
        'filename': xml_filename,
        'file_size_bytes': len(xml_content.encode('utf-8')),
        'processing_timestamp': processing_timestamp,
        'processing_time_seconds': processing_time
    }
    
    # XML structure analysis - handle empty GUID lists for geographical XMLs
    if emis_guids:
        valueset_count = len(set(guid['valueSet_guid'] for guid in emis_guids if 'valueSet_guid' in guid))
        unique_guids_count = len(set(guid['emis_guid'] for guid in emis_guids if 'emis_guid' in guid))
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
        'has_include_children_flags': sum(1 for guid in emis_guids if guid['include_children']),
        'has_table_context': sum(1 for guid in emis_guids if guid.get('table_context')),
        'has_column_context': sum(1 for guid in emis_guids if guid.get('column_context')),
        'has_display_names': sum(1 for guid in emis_guids if guid['xml_display_name'] != 'N/A' and guid['xml_display_name'] != 'No display name in XML'),
        'emisinternal_codes_excluded': sum(1 for guid in emis_guids if guid['code_system'].upper() == 'EMISINTERNAL')
    }
    
    return {
        'xml_stats': xml_stats,
        'xml_structure': xml_structure_stats,
        'code_systems': code_systems,
        'translation_accuracy': translation_stats,
        'category_distribution': category_distribution,
        'quality_metrics': quality_metrics
    }


def create_validation_report(audit_stats):
    """Create a human-readable validation report from audit statistics."""
    report_lines = []
    
    report_lines.append("PROCESSING VALIDATION REPORT")
    report_lines.append("=" * 50)
    report_lines.append(f"File: {audit_stats['xml_stats']['filename']}")
    report_lines.append(f"Processed: {audit_stats['xml_stats']['processing_timestamp']}")
    report_lines.append(f"File Size: {audit_stats['xml_stats']['file_size_bytes']:,} bytes")
    if audit_stats['xml_stats']['processing_time_seconds']:
        report_lines.append(f"Processing Time: {audit_stats['xml_stats']['processing_time_seconds']:.2f} seconds")
    report_lines.append("")
    
    report_lines.append("XML STRUCTURE ANALYSIS")
    report_lines.append("-" * 25)
    structure = audit_stats['xml_structure']
    report_lines.append(f"Total ValueSets: {structure['total_valuesets']}")
    report_lines.append(f"Unique EMIS GUIDs: {structure['unique_emis_guids']}")
    report_lines.append(f"Total GUID References: {structure['total_guid_occurrences']}")
    report_lines.append(f"Duplication Rate: {structure['duplicate_guid_ratio']}%")
    
    # Add enhanced structure metrics (need to import streamlit for session state access)
    try:
        import streamlit as st
        
        # Add search/report/folder counts
        search_results = st.session_state.get('search_results')
        search_count = len(search_results.searches) if search_results and hasattr(search_results, 'searches') else 0
        report_lines.append(f"Clinical Searches Found: {search_count}")
        
        report_results = st.session_state.get('report_results')
        if report_results and hasattr(report_results, 'report_breakdown'):
            total_reports = sum(len(reports) for reports in report_results.report_breakdown.values())
            report_lines.append(f"Reports Found: {total_reports}")
            
            # Add breakdown by report type
            breakdown_parts = []
            for report_type, reports in report_results.report_breakdown.items():
                if reports:
                    count = len(reports)
                    breakdown_parts.append(f"{count} {report_type}")
            if breakdown_parts:
                report_lines.append(f"  Report Types: {', '.join(breakdown_parts)}")
        else:
            report_lines.append(f"Reports Found: 0")
        
        analysis = st.session_state.get('search_analysis')
        folder_count = len(analysis.folders) if analysis and hasattr(analysis, 'folders') else 0
        report_lines.append(f"Folders Found: {folder_count}")
        
    except (ImportError, AttributeError):
        # Fallback if streamlit not available or session state missing
        pass
    
    report_lines.append("")
    
    report_lines.append("TRANSLATION ACCURACY")
    report_lines.append("-" * 20)
    trans = audit_stats['translation_accuracy']
    
    # Add enhanced translation breakdown
    try:
        import streamlit as st
        report_results = st.session_state.get('report_results')
        report_clinical_count = 0
        if report_results and hasattr(report_results, 'clinical_codes'):
            report_clinical_count = len(report_results.clinical_codes)
        
        search_found = trans['clinical_codes']['found']
        search_total = trans['clinical_codes']['total']
        total_clinical = search_total + report_clinical_count
        total_found = search_found + report_clinical_count
        
        # Show breakdown
        report_lines.append(f"Search Clinical Codes: {search_found}/{search_total} ({trans['clinical_codes']['success_rate']}%)")
        if report_clinical_count > 0:
            report_lines.append(f"Report Clinical Codes: {report_clinical_count}/{report_clinical_count} (100.0%)")
            report_lines.append(f"Combined Clinical Codes: {total_found}/{total_clinical} ({(total_found/total_clinical*100):.1f}%)")
        else:
            report_lines.append(f"Report Clinical Codes: 0/0 (0%)")
            
    except (ImportError, AttributeError):
        # Fallback to original format
        report_lines.append(f"Clinical Codes: {trans['clinical_codes']['found']}/{trans['clinical_codes']['total']} ({trans['clinical_codes']['success_rate']}%)")
    
    report_lines.append(f"Medications: {trans['medications']['found']}/{trans['medications']['total']} ({trans['medications']['success_rate']}%)")
    report_lines.append(f"Pseudo-Refset Clinical: {trans['pseudo_refset_clinical']['found']}/{trans['pseudo_refset_clinical']['total']} ({trans['pseudo_refset_clinical']['success_rate']}%)")
    report_lines.append(f"Pseudo-Refset Medications: {trans['pseudo_refset_medications']['found']}/{trans['pseudo_refset_medications']['total']} ({trans['pseudo_refset_medications']['success_rate']}%)")
    report_lines.append(f"OVERALL: {trans['overall']['found']}/{trans['overall']['total']} ({trans['overall']['success_rate']}%)")
    report_lines.append("")
    
    report_lines.append("CODE SYSTEM BREAKDOWN")
    report_lines.append("-" * 20)
    for system, count in sorted(audit_stats['code_systems'].items(), key=lambda x: x[1], reverse=True):
        report_lines.append(f"{system}: {count}")
    report_lines.append("")
    
    report_lines.append("CATEGORY DISTRIBUTION")
    report_lines.append("-" * 20)
    dist = audit_stats['category_distribution']
    
    # Add enhanced category distribution with combined totals
    try:
        import streamlit as st
        report_results = st.session_state.get('report_results')
        report_clinical_count = 0
        if report_results and hasattr(report_results, 'clinical_codes'):
            report_clinical_count = len(report_results.clinical_codes)
        
        search_clinical = dist['clinical_codes']
        total_clinical = search_clinical + report_clinical_count
        
        # Show breakdown
        report_lines.append(f"Search Clinical Codes: {search_clinical}")
        if report_clinical_count > 0:
            report_lines.append(f"Report Clinical Codes: {report_clinical_count}")
            report_lines.append(f"Total Clinical Codes: {total_clinical}")
        else:
            report_lines.append(f"Report Clinical Codes: 0")
            report_lines.append(f"Total Clinical Codes: {search_clinical}")
            
    except (ImportError, AttributeError):
        # Fallback to original format
        report_lines.append(f"Clinical Codes: {dist['clinical_codes']}")
    
    report_lines.append(f"Medications: {dist['medications']}")
    report_lines.append(f"True Refsets: {dist['refsets']}")
    report_lines.append(f"Pseudo-Refsets: {dist['pseudo_refsets']}")
    report_lines.append(f"Pseudo-Refset Clinical Members: {dist['pseudo_refset_clinical_members']}")
    report_lines.append(f"Pseudo-Refset Medication Members: {dist['pseudo_refset_medication_members']}")
    report_lines.append("")
    
    report_lines.append("QUALITY INDICATORS")
    report_lines.append("-" * 18)
    quality = audit_stats['quality_metrics']
    report_lines.append(f"Include Children Flags: {quality['has_include_children_flags']}")
    report_lines.append(f"Table Context Available: {quality['has_table_context']}")
    report_lines.append(f"Column Context Available: {quality['has_column_context']}")
    report_lines.append(f"Display Names Present: {quality['has_display_names']}")
    report_lines.append(f"EMISINTERNAL Codes (Excluded): {quality['emisinternal_codes_excluded']}")
    
    return "\n".join(report_lines)


def get_processing_provenance(xml_filename, lookup_version_info):
    """Create provenance information for processing audit trail."""
    return {
        'source_file': xml_filename,
        'processing_timestamp': datetime.now().isoformat(),
        'lookup_table_version': lookup_version_info.get('emis_version', 'Unknown'),
        'snomed_version': lookup_version_info.get('snomed_version', 'Unknown'),
        'extract_date': lookup_version_info.get('extract_date', 'Unknown'),
        'processor_version': '1.0.0'  # TODO: Could be made configurable or read from version file
    }
