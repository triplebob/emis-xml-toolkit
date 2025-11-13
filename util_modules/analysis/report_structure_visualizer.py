"""
Report Structure Visualizer - Folder and Dependency Functions
Contains functions for visualizing folder hierarchies and dependency relationships
"""

import streamlit as st
import pandas as pd
import io
import re
import json
from datetime import datetime
from ..core import ReportClassifier, SearchManager


def _natural_sort_key(text):
    """
    Natural sort key that handles numbers and letters properly
    Numbers come first (1, 2, 3...) then letters (A, B, C...)
    """
    # Extract the leading number or letter from the name
    match = re.match(r'^(\d+)', text)
    if match:
        # If starts with number, sort by number first
        return (0, int(match.group(1)), text)
    else:
        # If starts with letter, sort after all numbers
        return (1, 0, text.lower())


def render_folder_structure(folder_tree, folders, reports):
    """Render hierarchical folder structure with reports"""
    if not folders:
        st.info("No folder structure found in this XML")
        return
    
    st.markdown("**📁 Directory structure with search reports:**")
    
    # Create cache key for this specific folder structure
    import hashlib
    cache_key = hashlib.md5(str(folder_tree).encode()).hexdigest()
    
    # Create folder and report maps for quick lookup (not cached since objects aren't serializable)
    folder_map = {f.id: f for f in folders}
    report_map = {r.id: r for r in reports}
    
    # Export options at the top - collapsed by default
    with st.expander("📥 Export Folder Structure", expanded=False):
        st.markdown("**Export Options:**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Folder structure TXT export as fragment
            @st.fragment
            def folder_txt_export_fragment():
                # TXT export using cached tree text
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                xml_filename = st.session_state.get('xml_filename', 'unknown')
                clean_xml_name = xml_filename.replace('.xml', '').replace(' ', '_')
                
                # Generate summary statistics to match JSON export
                from ..export_handlers.json_export_generator import JSONExportGenerator
                from ..ui.tabs.tab_helpers import ensure_analysis_cached
                
                analysis = ensure_analysis_cached(None)
                json_generator = JSONExportGenerator(analysis)
                summary_stats = json_generator._calculate_folder_summary(folder_tree, folder_map, report_map)
                
                # Ensure tree text is initialized before using it
                if f'tree_text_{cache_key}' not in st.session_state:
                    st.session_state[f'tree_text_{cache_key}'] = generate_folder_tree_ascii(folder_tree, folder_map, report_map)
                
                # Build TXT content with summary
                txt_content = f"Folder Structure - Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                txt_content += "=" * 80 + "\n\n"
                txt_content += st.session_state[f'tree_text_{cache_key}']
                txt_content += "\n\n" + "=" * 80 + "\n"
                txt_content += "SUMMARY STATISTICS\n"
                txt_content += "=" * 80 + "\n"
                txt_content += f"Total Folders: {summary_stats.get('folders', 0)}\n"
                txt_content += f"Total Searches: {summary_stats.get('searches', 0)}\n"
                txt_content += f"Total List Reports: {summary_stats.get('list_reports', 0)}\n"
                txt_content += f"Total Audit Reports: {summary_stats.get('audit_reports', 0)}\n"
                txt_content += f"Total Aggregate Reports: {summary_stats.get('aggregate_reports', 0)}\n"
                
                from util_modules.export_handlers.ui_export_manager import UIExportManager
                export_manager = UIExportManager()
                export_manager.render_text_download_button(
                    content=txt_content,
                    filename=f"{clean_xml_name}_folder_structure_{timestamp}.txt",
                    key="tree_download_txt"
                )
            
            folder_txt_export_fragment()
        
        with col2:
            # Folder structure JSON export as fragment
            @st.fragment
            def folder_json_export_fragment():
                # JSON export using cached folder structure - generate JSON representation lazily
                if f'tree_json_{cache_key}' not in st.session_state:
                    # Use the proper JSON export generator
                    from ..export_handlers.json_export_generator import JSONExportGenerator
                    from ..ui.tabs.tab_helpers import ensure_analysis_cached
                    
                    # Get XML filename from session state
                    xml_filename = st.session_state.get('xml_filename', 'unknown')
                    
                    # Get analysis object for the JSON generator
                    analysis = ensure_analysis_cached(None)  # Use cached analysis
                    json_generator = JSONExportGenerator(analysis)
                    
                    filename, json_content = json_generator.generate_folder_structure_json(
                        folder_tree, folder_map, report_map, xml_filename
                    )
                    st.session_state[f'tree_json_{cache_key}'] = (filename, json_content)
                
                # Get cached JSON data
                filename, json_content = st.session_state[f'tree_json_{cache_key}']
                
                from util_modules.export_handlers.ui_export_manager import UIExportManager
                export_manager = UIExportManager()
                export_manager.render_json_download_button(
                    content=json_content,
                    filename=filename,
                    key="tree_download_json"
                )
            
            folder_json_export_fragment()
    
    # Tree View - cache the tree generation in session state
    if f'tree_text_{cache_key}' not in st.session_state:
        st.session_state[f'tree_text_{cache_key}'] = generate_folder_tree_ascii(folder_tree, folder_map, report_map)
    st.code(st.session_state[f'tree_text_{cache_key}'], language="")


# Deprecated - JSON exports now handled by JSONExportGenerator
def _convert_folder_structure_to_json_DEPRECATED(folder_tree, folder_map, report_map):
    """Convert folder structure to hierarchical JSON format matching the ASCII tree structure"""
    
    if not folder_map or not report_map:
        return {
            "error": "Missing data",
            "total_folders": len(folder_map) if folder_map else 0,
            "total_reports": len(report_map) if report_map else 0
        }
    
    try:
        def convert_folder_node(folder_node):
            """Recursively convert a folder node to JSON with all its children and reports"""
            try:
                folder_id = folder_node['id']
                folder = folder_map.get(folder_id)
            except Exception as e:
                raise Exception(f"Error accessing folder_node structure: {e}. Type: {type(folder_node)}, Content: {str(folder_node)[:200]}")
            
            # Build folder JSON structure
            folder_json = {
                "id": folder_id,
                "name": folder_node['name'],
                "type": "folder",
                "children": [],
                "reports": []
            }
            
            # Add reports in this folder with proper classification
            if folder and folder.report_ids:
                reports = [report_map.get(report_id) for report_id in folder.report_ids if report_map.get(report_id)]
                
                # Group reports by type like the ASCII tree does
                search_reports = []
                output_reports = []  # List, Audit, and Aggregate reports
                
                for report in reports:
                    report_type = ReportClassifier.classify_report_type(report)
                    
                    report_json = {
                        "id": report.id,
                        "name": getattr(report, 'name', 'Unknown'),
                        "type": report_type,
                        "type_clean": report_type.strip('[]')
                    }
                    
                    # Add metadata
                    for attr in ['parent_guid', 'description']:
                        if hasattr(report, attr):
                            report_json[attr] = getattr(report, attr)
                    
                    if report_type == "[Search]":
                        search_reports.append(report_json)
                    else:
                        output_reports.append(report_json)
                
                # Create parent-child relationships like the ASCII tree
                parent_to_reports = {}
                for output_report in output_reports:
                    parent_guid = output_report.get('parent_guid')
                    if parent_guid:
                        if parent_guid not in parent_to_reports:
                            parent_to_reports[parent_guid] = []
                        parent_to_reports[parent_guid].append(output_report)
                
                # Add search reports with their children
                for search_report in search_reports:
                    search_guid = search_report['id']
                    child_reports = parent_to_reports.get(search_guid, [])
                    
                    if child_reports:
                        search_report['child_reports'] = child_reports
                    
                    folder_json['reports'].append(search_report)
                
                # Add orphaned output reports (no parent found)
                for output_report in output_reports:
                    parent_guid = output_report.get('parent_guid')
                    if not parent_guid or parent_guid not in [s['id'] for s in search_reports]:
                        folder_json['reports'].append(output_report)
            
            # Recursively add child folders
            for child_folder in folder_node['children']:
                child_json = convert_folder_node(child_folder)
                folder_json['children'].append(child_json)
            
            return folder_json
        
        # Convert the root folder tree - same structure as ASCII tree
        if folder_tree and folder_tree.get('roots'):
            # Multiple root folders
            root_structure = {
                "type": "root",
                "children": []
            }
            
            for root_folder in folder_tree['roots']:
                root_structure['children'].append(convert_folder_node(root_folder))
        else:
            # No folder tree or invalid structure
            root_structure = {"error": "No folder tree found or invalid structure"}
        
        # Calculate summary statistics
        def count_items(node):
            """Recursively count folders and reports by type"""
            counts = {
                'folders': 0,
                'searches': 0,
                'list_reports': 0,
                'audit_reports': 0,
                'aggregate_reports': 0
            }
            
            if node.get('type') == 'folder':
                counts['folders'] += 1
                
                # Count reports in this folder
                for report in node.get('reports', []):
                    report_type = report.get('type_clean', '').lower().replace(' ', '_')
                    if report_type == 'search':
                        counts['searches'] += 1
                        # Count child reports
                        for child in report.get('child_reports', []):
                            child_type = child.get('type_clean', '').lower().replace(' ', '_')
                            if child_type in counts:
                                counts[child_type] += 1
                    elif report_type in counts:
                        counts[report_type] += 1
                
                # Recursively count children
                for child in node.get('children', []):
                    child_counts = count_items(child)
                    for key in counts:
                        counts[key] += child_counts[key]
            elif node.get('type') == 'root':
                # Handle root node
                for child in node.get('children', []):
                    child_counts = count_items(child)
                    for key in counts:
                        counts[key] += child_counts[key]
            
            return counts
        
        summary_counts = count_items(root_structure) if root_structure.get('type') != 'error' else {}
        
        return {
            "folder_structure": root_structure,
            "summary": summary_counts
        }
        
    except Exception as e:
        # Comprehensive debugging
        return {
            "error": f"JSON conversion failed: {str(e)}",
            "debug_info": {
                "folder_map_keys": list(folder_map.keys())[:5],
                "report_map_keys": list(report_map.keys())[:5],
                "sample_folder": {
                    "type": str(type(next(iter(folder_map.values())))) if folder_map else "none",
                    "attributes": list(vars(next(iter(folder_map.values()))).keys()) if folder_map and hasattr(next(iter(folder_map.values())), '__dict__') else "no __dict__"
                },
                "sample_report": {
                    "type": str(type(next(iter(report_map.values())))) if report_map else "none", 
                    "attributes": list(vars(next(iter(report_map.values()))).keys()) if report_map and hasattr(next(iter(report_map.values())), '__dict__') else "no __dict__"
                }
            }
        }




def generate_folder_tree_ascii(folder_tree, folder_map, report_map):
    """Generate ASCII tree visualization of folder structure"""
    lines = []
    
    def build_tree_lines(folder_node, prefix="", is_last=True):
        # Folder line with SQL-style schema format
        connector = "+-- " if is_last else "|-- "
        folder_icon = "[+]" if folder_node['children'] or folder_node['report_count'] > 0 else "[-]"
        folder_line = f"{prefix}{connector}{folder_icon}.[{folder_node['name']}]"
        
        # Get detailed counts for all 4 report types in this folder
        if folder_node['report_count'] > 0:
            folder = folder_map.get(folder_node['id'])
            if folder and folder.report_ids:
                reports = [report_map.get(report_id) for report_id in folder.report_ids if report_map.get(report_id)]
                type_counts = ReportClassifier.get_report_type_counts(reports)
                
                count_parts = []
                if type_counts['[Search]'] > 0:
                    count_parts.append(f"{type_counts['[Search]']} searches")
                if type_counts['[List Report]'] > 0:
                    count_parts.append(f"{type_counts['[List Report]']} list")
                if type_counts['[Audit Report]'] > 0:
                    count_parts.append(f"{type_counts['[Audit Report]']} audit")
                if type_counts['[Aggregate Report]'] > 0:
                    count_parts.append(f"{type_counts['[Aggregate Report]']} aggregate")
                
                if count_parts:
                    folder_line += f" ({', '.join(count_parts)})"
        
        lines.append(folder_line)
        
        # Extension for child items
        extension = "    " if is_last else "|   "
        new_prefix = prefix + extension
        
        # Add ALL reports in this folder with hierarchical nesting
        folder = folder_map.get(folder_node['id'])
        if folder and folder.report_ids:
            # Group reports by type (enhanced for 4 report types)
            reports = [report_map.get(report_id) for report_id in folder.report_ids if report_map.get(report_id)]
            
            search_reports = []
            output_reports = []  # List, Audit, and Aggregate reports
            
            for report in reports:
                report_type = ReportClassifier.classify_report_type(report)
                if report_type == "[Search]":
                    search_reports.append(report)
                else:
                    # All other types (List, Audit, Aggregate) are considered output reports
                    output_reports.append(report)
            
            # Create a mapping of parent searches to their output reports
            parent_to_reports = {}
            for output_report in output_reports:
                parent_guid = output_report.parent_guid
                if parent_guid:
                    if parent_guid not in parent_to_reports:
                        parent_to_reports[parent_guid] = []
                    parent_to_reports[parent_guid].append(output_report)
            
            # Render search reports and their nested output reports
            all_items = []
            
            # Add all search reports first, with their nested reports (sorted alphabetically)
            for search in sorted(search_reports, key=lambda x: _natural_sort_key(x.name)):
                all_items.append(('search', search))
                # Add any output reports that belong to this search (sorted by sequence)
                child_reports = parent_to_reports.get(search.id, [])
                for child_report in sorted(child_reports, key=lambda x: _natural_sort_key(x.name)):
                    all_items.append(('nested_report', child_report))
            
            # Add any orphaned output reports (reports without parent in same folder, sorted by sequence)
            for output_report in sorted(output_reports, key=lambda x: _natural_sort_key(x.name)):
                parent_guid = output_report.parent_guid
                parent_in_folder = any(s.id == parent_guid for s in search_reports)
                if not parent_in_folder:
                    all_items.append(('orphan_report', output_report))
            
            # Render all items
            for i, (item_type, report) in enumerate(all_items):
                is_last_item = (i == len(all_items) - 1 and 
                              len(folder_node['children']) == 0)
                
                # Determine connector and indentation based on type
                if item_type == 'nested_report':
                    # Extra indentation for nested reports under their parent search
                    item_connector = "    +-- " if is_last_item else "    |-- "
                else:
                    # Normal indentation for searches and orphan reports
                    item_connector = "+-- " if is_last_item else "|-- "
                
                # Clean the name and add classification with SQL-style schema format
                clean_name = SearchManager.clean_search_name(report.name)
                classification = ReportClassifier.classify_report_type(report)
                
                # Remove brackets from classification for schema format
                clean_classification = classification.strip('[]')
                
                report_line = f"{new_prefix}{item_connector}* [{clean_classification}].[{clean_name}]"
                lines.append(report_line)
        
        # Add child folders
        children = folder_node['children']
        for i, child in enumerate(children):
            is_last_child = (i == len(children) - 1)
            build_tree_lines(child, new_prefix, is_last_child)
    
    # Build tree for all roots
    roots = folder_tree['roots']
    for i, root in enumerate(roots):
        is_last_root = (i == len(roots) - 1)
        build_tree_lines(root, "", is_last_root)
        
        # Add spacing between multiple roots
        if not is_last_root:
            lines.append("")
    
    return "\n".join(lines)


def render_folder_list_view(folder_tree, folder_map, report_map):
    """Render detailed list view of folders"""
    def render_folder_node(folder_node, level=0):
        """Recursively render folder hierarchy"""
        indent = "  " * level
        folder_icon = "📁" if folder_node['children'] else "📂"
        
        with st.container():
            # Folder header with SQL-style schema format and accurate counts (matching Tree view)
            folder = folder_map.get(folder_node['id'])
            if folder and folder.report_ids:
                reports = [report_map.get(report_id) for report_id in folder.report_ids if report_map.get(report_id)]
                type_counts = ReportClassifier.get_report_type_counts(reports)
                
                count_parts = []
                if type_counts['[Search]'] > 0:
                    count_parts.append(f"{type_counts['[Search]']} searches")
                if type_counts['[List Report]'] > 0:
                    count_parts.append(f"{type_counts['[List Report]']} list")
                if type_counts['[Audit Report]'] > 0:
                    count_parts.append(f"{type_counts['[Audit Report]']} audit")
                if type_counts['[Aggregate Report]'] > 0:
                    count_parts.append(f"{type_counts['[Aggregate Report]']} aggregate")
                    
                count_text = f"({', '.join(count_parts)})" if count_parts else ""
            else:
                count_text = ""
                
            st.markdown(f"{indent}{folder_icon} **[{folder_node['name']}]** {count_text}")
            
            # Show ALL reports in this folder
            folder = folder_map.get(folder_node['id'])
            if folder and folder.report_ids:
                # Group reports by parent-child relationships for better organization
                reports = [report_map.get(report_id) for report_id in folder.report_ids if report_map.get(report_id)]
                
                search_reports = []
                output_reports = []
                
                for report in reports:
                    classification = ReportClassifier.classify_report_type(report)
                    if classification in ["[List Report]", "[Audit Report]", "[Aggregate Report]"]:
                        output_reports.append(report)
                    elif classification == "[Search]":
                        search_reports.append(report)
                    # Note: This logic properly handles all report types
                
                # Create a mapping of parent searches to their output reports
                parent_to_reports = {}
                for output_report in output_reports:
                    parent_guid = output_report.parent_guid
                    if parent_guid:
                        if parent_guid not in parent_to_reports:
                            parent_to_reports[parent_guid] = []
                        parent_to_reports[parent_guid].append(output_report)
                
                
                # Render search reports and their nested output reports (sorted by sequence)
                for search in sorted(search_reports, key=lambda x: _natural_sort_key(x.name)):
                    # Display search with search emoji and classification
                    dependency_count = len(search.direct_dependencies)
                    dependent_count = len(search.dependents)
                    dependency_info = ""
                    if dependency_count > 0 or dependent_count > 0:
                        dependency_info = f" (↗️{dependency_count} deps, ↙️{dependent_count} dependents)"
                    
                    clean_name = SearchManager.clean_search_name(search.name)
                    st.caption(f"{indent}  🔍 **[Search].[{clean_name}]**{dependency_info}")
                    
                    # Display any output reports nested under this search (sorted by sequence)
                    child_reports = parent_to_reports.get(search.id, [])
                    for child_report in sorted(child_reports, key=lambda x: _natural_sort_key(x.name)):
                        child_dep_count = len(child_report.direct_dependencies)
                        child_dependent_count = len(child_report.dependents)
                        child_dependency_info = ""
                        if child_dep_count > 0 or child_dependent_count > 0:
                            child_dependency_info = f" (↗️{child_dep_count} deps, ↙️{child_dependent_count} dependents)"
                        
                        child_clean_name = SearchManager.clean_search_name(child_report.name)
                        st.caption(f"{indent}      📊 **[Report].[{child_clean_name}]**{child_dependency_info}")
                
                # Display any orphaned output reports (without parent in same folder, sorted by sequence)
                for output_report in sorted(output_reports, key=lambda x: _natural_sort_key(x.name)):
                    parent_guid = output_report.parent_guid
                    parent_in_folder = any(s.id == parent_guid for s in search_reports)
                    if not parent_in_folder:
                        dependency_count = len(output_report.direct_dependencies)
                        dependent_count = len(output_report.dependents)
                        dependency_info = ""
                        if dependency_count > 0 or dependent_count > 0:
                            dependency_info = f" (↗️{dependency_count} deps, ↙️{dependent_count} dependents)"
                        
                        clean_name = SearchManager.clean_search_name(output_report.name)
                        st.caption(f"{indent}  📊 **[Report].[{clean_name}]**{dependency_info}")
            
            # Render child folders
            for child in folder_node['children']:
                render_folder_node(child, level + 1)
    
    # Render all root folders
    for root_folder in folder_tree['roots']:
        render_folder_node(root_folder)


def render_dependency_tree(dependency_tree, reports):
    """Render report dependency relationships with caching and lazy exports"""
    if not dependency_tree or not dependency_tree['roots']:
        st.info("No dependency relationships found")
        return
    
    # Header with options
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("**🔗 Report dependency relationships:**")
    with col2:
        show_circular = st.checkbox("Show circular refs", help="Highlight circular dependencies")
    
    report_map = {r.id: r for r in reports}
    
    # Generate cache key for dependency tree
    cache_key = f"dep_tree_{len(reports)}_{show_circular}"
    
    # Generate and cache dependency tree text
    if f'dep_tree_text_{cache_key}' not in st.session_state:
        st.session_state[f'dep_tree_text_{cache_key}'] = generate_dependency_tree_ascii(dependency_tree, report_map, show_circular)
    
    # Export options at the top - collapsed by default
    with st.expander("📥 Export Dependencies", expanded=False):
        st.markdown("**Export Options:**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Dependency TXT export as fragment
            @st.fragment
            def dependency_txt_export_fragment():
                # TXT export using cached tree text
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                xml_filename = st.session_state.get('uploaded_filename', 'dependency_tree')
                clean_xml_name = xml_filename.replace('.xml', '').replace(' ', '_')
                
                # Generate summary statistics to match JSON export
                from util_modules.export_handlers.json_export_generator import JSONExportGenerator
                from util_modules.ui.tabs.tab_helpers import ensure_analysis_cached
                
                analysis = ensure_analysis_cached(None)
                json_generator = JSONExportGenerator(analysis)
                summary_stats = json_generator._calculate_dependency_summary(dependency_tree, report_map, show_circular)
                
                # Ensure dependency tree text is initialized before using it
                if f'dep_tree_text_{cache_key}' not in st.session_state:
                    st.session_state[f'dep_tree_text_{cache_key}'] = generate_dependency_tree_ascii(dependency_tree, report_map, show_circular)
                
                # Build TXT content with summary
                dep_txt_content = f"Dependency Tree - Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                dep_txt_content += f"Show Circular Dependencies: {show_circular}\n"
                dep_txt_content += "=" * 80 + "\n\n"
                dep_txt_content += st.session_state[f'dep_tree_text_{cache_key}']
                dep_txt_content += "\n\n" + "=" * 80 + "\n"
                dep_txt_content += "SUMMARY STATISTICS\n"
                dep_txt_content += "=" * 80 + "\n"
                dep_txt_content += f"Total Nodes: {summary_stats.get('total_nodes', 0)}\n"
                dep_txt_content += f"Total Searches: {summary_stats.get('searches', 0)}\n"
                dep_txt_content += f"Total List Reports: {summary_stats.get('list_reports', 0)}\n"
                dep_txt_content += f"Total Audit Reports: {summary_stats.get('audit_reports', 0)}\n"
                dep_txt_content += f"Total Aggregate Reports: {summary_stats.get('aggregate_reports', 0)}\n"
                dep_txt_content += f"Circular Dependencies: {summary_stats.get('circular_dependencies', 0)}\n"
                
                from util_modules.export_handlers.ui_export_manager import UIExportManager
                export_manager = UIExportManager()
                export_manager.render_text_download_button(
                    content=dep_txt_content,
                    filename=f"{clean_xml_name}_dependency_tree_{timestamp}.txt",
                    key="dep_tree_download_txt"
                )
            
            dependency_txt_export_fragment()
        
        with col2:
            # Dependency JSON export as fragment
            @st.fragment
            def dependency_json_export_fragment():
                # JSON export using cached dependency structure - generate JSON representation lazily
                dep_cache_key = f'dep_tree_json_{cache_key}'
                if dep_cache_key not in st.session_state:
                    # Use the proper JSON export generator
                    from util_modules.export_handlers.json_export_generator import JSONExportGenerator
                    from util_modules.ui.tabs.tab_helpers import ensure_analysis_cached
                    
                    # Get XML filename from session state
                    xml_filename = st.session_state.get('xml_filename', 'unknown')
                    
                    # Get analysis object for the JSON generator
                    analysis = ensure_analysis_cached(None)  # Use cached analysis
                    json_generator = JSONExportGenerator(analysis)
                    
                    filename, json_content = json_generator.generate_dependency_tree_json(
                        dependency_tree, report_map, show_circular, xml_filename
                    )
                    st.session_state[dep_cache_key] = (filename, json_content)
                
                # Get cached JSON data
                filename, json_content = st.session_state[dep_cache_key]
                
                from util_modules.export_handlers.ui_export_manager import UIExportManager
                export_manager = UIExportManager()
                export_manager.render_json_download_button(
                    content=json_content,
                    filename=filename,
                    key="dep_tree_download_json"
                )
            
            dependency_json_export_fragment()
    
    # Tree View (collapsible)
    with st.expander("🌳 Dependency Tree", expanded=True):
        st.code(st.session_state[f'dep_tree_text_{cache_key}'], language="")


def generate_dependency_tree_ascii(dependency_tree, report_map, show_circular=True):
    """Generate ASCII tree visualization of dependency structure"""
    lines = []
    
    def build_dependency_lines(dep_node, prefix="", is_last=True, visited=None):
        if visited is None:
            visited = set()
        
        # Check for circular dependency
        is_circular = dep_node.get('circular', False)
        if is_circular and not show_circular:
            return
        
        if dep_node['id'] in visited:
            # Show circular reference
            connector = "+-- " if is_last else "|-- "
            formatted_name = _format_dependency_name_with_context(dep_node, report_map)
            lines.append(f"{prefix}{connector}(!) > {formatted_name} (circular)")
            return
        
        visited.add(dep_node['id'])
        
        # Dependency line
        connector = "+-- " if is_last else "|-- "
        
        # Choose icon based on type
        if is_circular:
            icon = "(!)"
        elif len(visited) == 1:  # Root level
            icon = "[R]"
        else:
            icon = "[D]"
        
        # Get formatted name with folder context (now includes hierarchical breadcrumb)
        formatted_name = _format_dependency_name_with_context(dep_node, report_map)
        
        # Build hierarchical line: tree_connector + dependency_type > folder_path > classification > name
        dep_line = f"{prefix}{connector}{icon} > {formatted_name}"
        
        # Add dependency count info (optional - remove if too cluttered)
        deps = dep_node.get('dependencies', [])
        if deps and len(deps) > 0:
            dep_line += f" [needs {len(deps)}]"
        
        # Folder path is now included in the formatted name above, no need for duplicate @path
        
        lines.append(dep_line)
        
        # Extension for child items
        extension = "    " if is_last else "|   "
        new_prefix = prefix + extension
        
        # Add dependent reports (children in the dependency tree)
        children = dep_node.get('children', [])
        for i, child in enumerate(children):
            is_last_child = (i == len(children) - 1)
            build_dependency_lines(child, new_prefix, is_last_child, visited.copy())
    
    # Add improved summary header
    composition = _analyze_dependency_composition(dependency_tree, report_map)
    
    summary_parts = []
    if composition['root_searches'] > 0:
        summary_parts.append(f"{composition['root_searches']} root searches")
    if composition['branch_searches'] > 0:
        summary_parts.append(f"{composition['branch_searches']} branch searches")
    if composition['root_reports'] > 0:
        summary_parts.append(f"{composition['root_reports']} root reports")
    
    summary = ", ".join(summary_parts) if summary_parts else "0 root items"
    
    lines.append(f"🔗 {summary}, spanning {composition['folder_count']} folders, max depth: {composition['max_depth']}")
    lines.append("")
    
    # Build tree for all roots
    roots = dependency_tree['roots']
    for i, root in enumerate(roots):
        is_last_root = (i == len(roots) - 1)
        build_dependency_lines(root, "", is_last_root)
        
        # Add spacing between multiple roots
        if not is_last_root and len(roots) > 1:
            lines.append("")
    
    return "\n".join(lines)


def render_dependency_list_view(dependency_tree, report_map, show_circular):
    """Render the original detailed list view for dependencies"""
    
    def render_dependency_node(dep_node, level=0, visited=None):
        """Recursively render dependency tree"""
        if visited is None:
            visited = set()
        
        indent = "  " * level
        
        # Check for circular dependency
        is_circular = dep_node.get('circular', False)
        if is_circular and not show_circular:
            return
        
        # Node icon based on complexity and circular status
        if is_circular:
            icon = "🔄"
            style = "background-color: #5a4d2d; color: #f5f3e8;"
        elif level == 0:
            icon = "🔵"
            style = ""
        else:
            icon = "⚡"
            style = ""
        
        # Get formatted name with folder context
        formatted_name = _format_dependency_name_with_context(dep_node, report_map)
        
        # Extract classification for emoji
        classification = ReportClassifier.classify_report_type(report_map.get(dep_node['id'])) if report_map.get(dep_node['id']) else "[Search]"
        class_icon = "🔍" if classification == "[Search]" else "📊"
        
        with st.container():
            if style:
                st.markdown(
                    f'<div style="{style} padding: 5px; border-radius: 3px;">'
                    f'{indent}{icon} {class_icon} **{formatted_name}**</div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(f"{indent}{icon} {class_icon} **{formatted_name}**")
            
            # Show detailed information about the node
            node_type = dep_node.get('type', '')
            if node_type and 'Report' in node_type and level == 0:
                # For root reports, show detailed metadata
                report = report_map.get(dep_node['id'])
                if report:
                    col1, col2 = st.columns(2)
                    with col1:
                        if hasattr(report, 'author') and report.author:
                            st.caption(f"👤 Author: {report.author}")
                        if hasattr(report, 'creation_time') and report.creation_time:
                            st.caption(f"📅 Created: {report.creation_time}")
                    with col2:
                        if hasattr(report, 'report_type'):
                            report_type = report.report_type.strip('[]').title()
                            # Clean up the display text
                            st.caption(f"📋 Type: {report_type}")
                        if hasattr(report, 'population_references') and report.population_references:
                            st.caption(f"🧑‍🤝‍🧑 References: {len(report.population_references)} populations")
            
            # Show children (member searches for audit reports)
            children = dep_node.get('children', [])
            if children:
                st.caption(f"{indent}  📂 **Member Searches ({len(children)}):**")
                for i, child in enumerate(children):
                    child_icon = "🔍" if child.get('type') == 'Search' else "📊"
                    is_last_child = (i == len(children) - 1)
                    connector = "└─" if is_last_child else "├─"
                    st.caption(f"{indent}    {connector} {child_icon} {child.get('name', 'Unknown')}")
            
            # Show legacy dependency info if available
            deps = dep_node.get('dependencies', [])
            if deps and not children:  # Only show if we don't already have children
                dep_names = []
                for dep_id in deps[:3]:  # Show first 3 dependencies
                    dep_report = report_map.get(dep_id)
                    if dep_report:
                        dep_names.append(dep_report.name)
                
                dep_text = ", ".join(dep_names)
                if len(deps) > 3:
                    dep_text += f" and {len(deps) - 3} more"
                
                st.caption(f"{indent}  ↗️ Depends on: {dep_text}")
            
            # Render dependent reports (legacy)
            if not is_circular:
                for dependent in dep_node.get('dependents', []):
                    if dependent['id'] not in visited:
                        visited.add(dependent['id'])
                        render_dependency_node(dependent, level + 1, visited.copy())
    
    # Show improved summary stats
    composition = _analyze_dependency_composition(dependency_tree, report_map)
    
    summary_parts = []
    if composition['root_searches'] > 0:
        summary_parts.append(f"{composition['root_searches']} root searches")
    if composition['branch_searches'] > 0:
        summary_parts.append(f"{composition['branch_searches']} branch searches")
    if composition['root_reports'] > 0:
        summary_parts.append(f"{composition['root_reports']} root reports")
    
    summary = ", ".join(summary_parts) if summary_parts else "0 root items"
    
    st.info(f"🔗 {summary}, spanning {composition['folder_count']} folders, max dependency depth: {composition['max_depth']}")
    
    # Additional composition details
    if composition['total_items'] > len(dependency_tree['roots']):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Searches", composition['searches'])
        with col2:
            st.metric("Total Reports", composition['reports'])
        with col3:
            st.metric("Folders Involved", composition['folder_count'])
    
    # Render root dependencies
    for root_dep in dependency_tree['roots']:
        render_dependency_node(root_dep)


# REMOVED: Legacy export handler - no longer used since TXT/JSON exports are handled directly
    


# REMOVED: Legacy CSV export function - no longer needed since we use TXT/JSON exports
def _generate_folder_csv_data_REMOVED(folder_tree, folder_map, report_map):
    """Generate CSV data for folder structure"""
    csv_data = []
    
    def process_folder_node(folder_node, level=0, parent_path=""):
        folder = folder_map.get(folder_node['id'])
        current_path = f"{parent_path}/{folder_node['name']}" if parent_path else folder_node['name']
        
        if folder and folder.report_ids:
            # Group reports by parent-child relationships
            reports = [report_map.get(report_id) for report_id in folder.report_ids if report_map.get(report_id)]
            
            search_reports = []
            output_reports = []
            
            for report in reports:
                if ReportClassifier.classify_report_type(report) == "[Report]":
                    output_reports.append(report)
                else:
                    search_reports.append(report)
            
            # Create a mapping of parent searches to their output reports
            parent_to_reports = {}
            for output_report in output_reports:
                parent_guid = output_report.parent_guid
                if parent_guid:
                    if parent_guid not in parent_to_reports:
                        parent_to_reports[parent_guid] = []
                    parent_to_reports[parent_guid].append(output_report)
            
            # Add search reports and their nested output reports (sorted by sequence)
            for search in sorted(search_reports, key=lambda x: _natural_sort_key(x.name)):
                clean_name = SearchManager.clean_search_name(search.name)
                csv_data.append({
                    'Folder_Path': current_path,
                    'Item_Type': 'Search',
                    'Item_Name': clean_name,
                    'Schema_Format': f"[Search].[{clean_name}]",
                    'Report_ID': search.id,
                    'Parent_Report_ID': search.parent_guid if search.parent_guid else '',
                    'Dependencies_Count': len(search.direct_dependencies),
                    'Dependents_Count': len(search.dependents),
                    'Folder_Level': level,
                    'Is_Nested': False
                })
                
                # Add any output reports that belong to this search (sorted by sequence)
                child_reports = parent_to_reports.get(search.id, [])
                for child_report in sorted(child_reports, key=lambda x: _natural_sort_key(x.name)):
                    child_clean_name = SearchManager.clean_search_name(child_report.name)
                    csv_data.append({
                        'Folder_Path': current_path,
                        'Item_Type': 'Report',
                        'Item_Name': child_clean_name,
                        'Schema_Format': f"[Report].[{child_clean_name}]",
                        'Report_ID': child_report.id,
                        'Parent_Report_ID': child_report.parent_guid if child_report.parent_guid else '',
                        'Dependencies_Count': len(child_report.direct_dependencies),
                        'Dependents_Count': len(child_report.dependents),
                        'Folder_Level': level,
                        'Is_Nested': True
                    })
            
            # Add any orphaned output reports (sorted by sequence)
            for output_report in sorted(output_reports, key=lambda x: _natural_sort_key(x.name)):
                parent_guid = output_report.parent_guid
                parent_in_folder = any(s.id == parent_guid for s in search_reports)
                if not parent_in_folder:
                    clean_name = SearchManager.clean_search_name(output_report.name)
                    csv_data.append({
                        'Folder_Path': current_path,
                        'Item_Type': 'Report',
                        'Item_Name': clean_name,
                        'Schema_Format': f"[Report].[{clean_name}]",
                        'Report_ID': output_report.id,
                        'Parent_Report_ID': output_report.parent_guid if output_report.parent_guid else '',
                        'Dependencies_Count': len(output_report.direct_dependencies),
                        'Dependents_Count': len(output_report.dependents),
                        'Folder_Level': level,
                        'Is_Nested': False
                    })
        
        # Process child folders
        for child in folder_node['children']:
            process_folder_node(child, level + 1, current_path)
    
    # Process all root folders
    for root in folder_tree['roots']:
        process_folder_node(root)
    
    return csv_data


def _generate_complete_dependency_analysis(dependency_tree, report_map, show_circular, tree_text):
    """Generate complete dependency analysis combining tree and detailed views"""
    output_lines = []
    
    # Header
    output_lines.append("=" * 80)
    output_lines.append("DEPENDENCY ANALYSIS REPORT")
    output_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    output_lines.append("=" * 80)
    output_lines.append("")
    
    # Tree view section
    output_lines.append("🌳 DEPENDENCY TREE")
    output_lines.append("-" * 40)
    output_lines.append(tree_text)
    output_lines.append("")
    
    # Detailed view section
    output_lines.append("📋 DETAILED DEPENDENCY VIEW")
    output_lines.append("-" * 40)
    
    def format_detailed_node(dep_node, level=0, visited=None):
        if visited is None:
            visited = set()
        
        # Check for circular dependency
        is_circular = dep_node.get('circular', False)
        if is_circular and not show_circular:
            return
        
        indent = "  " * level
        
        # Node header
        node_type = dep_node.get('type', '')
        node_icon = "📊" if 'Report' in node_type else "🔍"
        formatted_name = _format_dependency_name_with_context(dep_node, report_map)
        
        output_lines.append(f"{indent}{node_icon} {formatted_name}")
        
        # Show detailed information for root reports
        if node_type and 'Report' in node_type and level == 0:
            report = report_map.get(dep_node['id'])
            if report:
                if hasattr(report, 'author') and report.author:
                    output_lines.append(f"{indent}  👤 Author: {report.author}")
                if hasattr(report, 'creation_time') and report.creation_time:
                    output_lines.append(f"{indent}  📅 Created: {report.creation_time}")
                if hasattr(report, 'report_type'):
                    report_type = report.report_type.strip('[]').title()
                    # Clean up the display text
                    output_lines.append(f"{indent}  📋 Type: {report_type}")
                if hasattr(report, 'population_references') and report.population_references:
                    output_lines.append(f"{indent}  🧑‍🤝‍🧑 References: {len(report.population_references)} populations")
        
        # Show children (member searches)
        children = dep_node.get('children', [])
        if children:
            output_lines.append(f"{indent}  📂 Member Searches ({len(children)}):")
            for i, child in enumerate(children):
                child_icon = "🔍" if child.get('type') == 'Search' else "📊"
                is_last_child = (i == len(children) - 1)
                connector = "└─" if is_last_child else "├─"
                output_lines.append(f"{indent}    {connector} {child_icon} {child.get('name', 'Unknown')}")
        
        output_lines.append("")
        
        # Process children recursively for legacy structure
        if not is_circular:
            for dependent in dep_node.get('dependents', []):
                if dependent['id'] not in visited:
                    visited.add(dependent['id'])
                    format_detailed_node(dependent, level + 1, visited.copy())
    
    # Process all roots in detailed view
    for root in dependency_tree.get('roots', []):
        format_detailed_node(root)
    
    # Summary statistics
    composition = _analyze_dependency_composition(dependency_tree, report_map)
    output_lines.append("📊 SUMMARY STATISTICS")
    output_lines.append("-" * 40)
    output_lines.append(f"Total Items: {composition['total_items']}")
    output_lines.append(f"Root Reports: {composition['root_reports']}")
    output_lines.append(f"Root Searches: {composition['root_searches']}")
    output_lines.append(f"Total Searches: {composition['searches']}")
    output_lines.append(f"Total Reports: {composition['reports']}")
    output_lines.append(f"Max Dependency Depth: {composition['max_depth']}")
    output_lines.append(f"Folders: {composition['folder_count']}")
    
    return "\n".join(output_lines)




# REMOVED: Legacy export handler - no longer used since TXT/JSON exports are handled directly
    


def _analyze_dependency_composition(dependency_tree, report_map):
    """Analyze the composition of the dependency tree for better summary"""
    composition = {
        'total_items': 0,
        'searches': 0,
        'reports': 0,
        'root_searches': 0,
        'root_reports': 0,
        'branch_searches': 0,
        'folders': set(),
        'max_depth': dependency_tree.get('max_depth', 0)
    }
    
    def analyze_node(node, level=0):
        composition['total_items'] += 1
        
        # Use node type if available, otherwise fall back to report map classification
        node_type = node.get('type', '')
        if node_type and 'Report' in node_type:
            # This is a report (Audit Report, List Report, etc.)
            composition['reports'] += 1
            if level == 0:
                composition['root_reports'] += 1
        elif node_type == 'Search' or not node_type:
            # This is a search or unknown type - check report map as fallback
            report = report_map.get(node['id'])
            classification = ReportClassifier.classify_report_type(report) if report else "[Search]"
            
            if classification == "[Search]":
                composition['searches'] += 1
                if level == 0:
                    composition['root_searches'] += 1
                else:
                    composition['branch_searches'] += 1
            else:
                composition['reports'] += 1
                if level == 0:
                    composition['root_reports'] += 1
        else:
            # Unknown type, treat as search for backward compatibility
            composition['searches'] += 1
            if level == 0:
                composition['root_searches'] += 1
            else:
                composition['branch_searches'] += 1
        
        # Track folders
        if node.get('folder_path'):
            folder_path = " > ".join(node['folder_path'])
            composition['folders'].add(folder_path)
        
        # Analyze dependents recursively (not dependencies - those are just IDs)
        for dep in node.get('dependents', []):
            analyze_node(dep, level + 1)
    
    # Analyze all root nodes
    for root in dependency_tree.get('roots', []):
        analyze_node(root)
    
    composition['folder_count'] = len(composition['folders'])
    return composition


def _format_dependency_name_with_context(node, report_map):
    """Format dependency name with folder context"""
    clean_name = SearchManager.clean_search_name(node['name'])
    
    # Use node type if available, otherwise fall back to report map classification
    node_type = node.get('type', '')
    if node_type and 'Report' in node_type:
        # Format: "Audit Report" -> "[Audit Report]"
        classification = f"[{node_type}]"
    elif node_type == 'Search':
        classification = "[Search]"
    else:
        # Fall back to report map classification
        report = report_map.get(node['id'])
        classification = ReportClassifier.classify_report_type(report) if report else "[Search]"
    
    # Add folder context if available
    if node.get('folder_path') and len(node['folder_path']) > 0:
        # Create hierarchical breadcrumb with individual brackets for each folder
        folder_parts = [f"[{folder.strip()}]" for folder in node['folder_path']]
        folder_breadcrumb = " > ".join(folder_parts)
        
        # Remove brackets from classification for schema format
        clean_classification = classification.strip('[]')
        
        return f"{folder_breadcrumb} > [{clean_classification}].[{clean_name}]"
    else:
        # Remove brackets from classification for schema format
        clean_classification = classification.strip('[]')
        return f"[{clean_classification}].[{clean_name}]"


# REMOVED: Legacy CSV export function - no longer needed since we use TXT/JSON exports  
def _generate_dependency_csv_data_REMOVED(dependency_tree, report_map, show_circular):
    """Generate CSV data for dependency structure"""
    csv_data = []
    
    def process_dependency_node(dep_node, level=0, parent_id=None, visited=None):
        if visited is None:
            visited = set()
        
        # Check for circular dependency
        is_circular = dep_node.get('circular', False)
        if is_circular and not show_circular:
            return
        
        if dep_node['id'] in visited:
            # Circular reference - add it but mark as circular
            report = report_map.get(dep_node['id'])
            clean_name = SearchManager.clean_search_name(dep_node['name'])
            classification = ReportClassifier.classify_report_type(report) if report else "Search"
            
            clean_classification = classification.replace('[', '').replace(']', '')
            csv_data.append({
                'Report_ID': dep_node['id'],
                'Report_Name': clean_name,
                'Report_Type': clean_classification,
                'Schema_Format': f"[{clean_classification}].[{clean_name}]",
                'Parent_Report_ID': parent_id if parent_id else '',
                'Dependency_Level': level,
                'Is_Circular': True,
                'Folder_Path': " > ".join([f"[{folder}]" for folder in dep_node.get('folder_path', [])]),
                'Direct_Dependencies': 0,  # Circular, so we don't count again
                'Total_Dependents': 0
            })
            return
        
        visited.add(dep_node['id'])
        
        # Add this node to CSV
        report = report_map.get(dep_node['id'])
        clean_name = SearchManager.clean_search_name(dep_node['name'])
        classification = ReportClassifier.classify_report_type(report) if report else "Search"
        
        clean_classification = classification.replace('[', '').replace(']', '')
        csv_data.append({
            'Report_ID': dep_node['id'],
            'Report_Name': clean_name,
            'Report_Type': clean_classification,
            'Schema_Format': f"[{clean_classification}].[{clean_name}]",
            'Parent_Report_ID': parent_id if parent_id else '',
            'Dependency_Level': level,
            'Is_Circular': is_circular,
            'Folder_Path': " > ".join([f"[{folder}]" for folder in dep_node.get('folder_path', [])]),
            'Direct_Dependencies': len(dep_node.get('children', []) or dep_node.get('dependencies', [])),
            'Total_Dependents': len(report.dependents) if report else 0
        })
        
        # Process child dependencies (check both 'children' and 'dependencies' for compatibility)
        children = dep_node.get('children', []) or dep_node.get('dependencies', [])
        for child_dep in children:
            process_dependency_node(child_dep, level + 1, dep_node['id'], visited.copy())
    
    # Process all root dependencies
    for root_dep in dependency_tree['roots']:
        process_dependency_node(root_dep)
    
    return csv_data


# Deprecated - JSON exports now handled by JSONExportGenerator
def _convert_dependency_tree_to_json_DEPRECATED(dependency_tree, report_map, show_circular, xml_filename):
    """Convert dependency tree to hierarchical JSON format matching the ASCII tree structure"""
    
    if not dependency_tree or not dependency_tree.get('roots'):
        return {
            "error": "No dependency tree found",
            "total_reports": len(report_map) if report_map else 0
        }
    
    try:
        def convert_dependency_node(dep_node):
            """Recursively convert a dependency node to JSON with all its children"""
            report = report_map.get(dep_node['id'])
            report_type = ReportClassifier.classify_report_type(report) if report else "[Search]"
            
            # Build dependency JSON structure
            dep_json = {
                "id": dep_node['id'],
                "name": dep_node['name'],
                "type": report_type,
                "type_clean": report_type.strip('[]'),
                "is_circular": dep_node.get('circular', False),
                "dependencies": []
            }
            
            # Add metadata if available
            if report:
                for attr in ['parent_guid', 'description']:
                    if hasattr(report, attr):
                        dep_json[attr] = getattr(report, attr)
            
            # Add folder path if available
            if dep_node.get('folder_path'):
                dep_json['folder_path'] = dep_node['folder_path']
            
            # Only include circular dependencies if show_circular is True
            children = dep_node.get('children', []) or dep_node.get('dependencies', [])
            for child_dep in children:
                if not child_dep.get('circular', False) or show_circular:
                    child_json = convert_dependency_node(child_dep)
                    dep_json['dependencies'].append(child_json)
            
            return dep_json
        
        # Convert all root dependencies
        root_dependencies = []
        for root_dep in dependency_tree['roots']:
            root_json = convert_dependency_node(root_dep)
            root_dependencies.append(root_json)
        
        # Calculate summary statistics
        def count_dependency_items(node):
            """Recursively count dependencies by type"""
            counts = {
                'total_nodes': 0,
                'searches': 0,
                'list_reports': 0,
                'audit_reports': 0,
                'aggregate_reports': 0,
                'circular_dependencies': 0
            }
            
            counts['total_nodes'] += 1
            
            # Count by type
            report_type = node.get('type_clean', '').lower().replace(' ', '_')
            if report_type in counts:
                counts[report_type] += 1
            
            # Count circular dependencies
            if node.get('is_circular', False):
                counts['circular_dependencies'] += 1
            
            # Recursively count children
            for child in node.get('dependencies', []):
                child_counts = count_dependency_items(child)
                for key in counts:
                    counts[key] += child_counts[key]
            
            return counts
        
        # Calculate total counts across all roots
        total_counts = {
            'total_nodes': 0,
            'searches': 0,
            'list_reports': 0,
            'audit_reports': 0,
            'aggregate_reports': 0,
            'circular_dependencies': 0
        }
        
        for root in root_dependencies:
            root_counts = count_dependency_items(root)
            for key in total_counts:
                total_counts[key] += root_counts[key]
        
        return {
            "generated": datetime.now().isoformat(),
            "xml_filename": xml_filename,
            "show_circular_dependencies": show_circular,
            "dependency_tree": {
                "type": "dependency_root",
                "roots": root_dependencies
            },
            "summary": total_counts
        }
        
    except Exception as e:
        return {
            "error": f"JSON conversion failed: {str(e)}",
            "debug_info": {
                "dependency_tree_keys": list(dependency_tree.keys()) if dependency_tree else [],
                "report_map_size": len(report_map) if report_map else 0,
                "show_circular": show_circular
            }
        }
