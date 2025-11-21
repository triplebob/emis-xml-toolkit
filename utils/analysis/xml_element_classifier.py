"""
XML Element Classifier - Initial parsing and element type identification
Handles upfront classification of XML elements before passing to specialized analyzers
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from .common_structures import ReportFolder
from ..xml_parsers.namespace_handler import NamespaceHandler


@dataclass
class ClassifiedElements:
    """Container for classified XML elements"""
    # Document metadata
    document_id: str
    creation_time: str
    
    # Folder structure (shared across all analyzers)
    folders: List[ReportFolder]
    folder_tree: Dict[str, Any]
    
    # Classified elements by type
    search_elements: List[ET.Element] = field(default_factory=list)
    audit_elements: List[ET.Element] = field(default_factory=list)
    list_elements: List[ET.Element] = field(default_factory=list)
    aggregate_elements: List[ET.Element] = field(default_factory=list)
    
    # XML parsing context (for analyzers to use)
    namespaces: Dict[str, str] = field(default_factory=dict)
    root_element: Optional[ET.Element] = None


class XMLElementClassifier:
    """Classifies XML elements by type and extracts shared metadata"""
    
    def __init__(self):
        self.ns = NamespaceHandler()
    
    def classify_elements(self, xml_content: str) -> ClassifiedElements:
        """
        Parse XML and classify elements by type
        
        Args:
            xml_content: Raw XML content
            
        Returns:
            ClassifiedElements containing sorted elements and shared metadata
        """
        try:
            root = ET.fromstring(xml_content)
            namespaces = {'emis': 'http://www.e-mis.com/emisopen'}
            
            # Extract document metadata
            document_id, creation_time = self._extract_document_metadata(root, namespaces)
            
            # Extract folder structure (shared)
            folders, folder_tree = self._extract_folder_structure(root, namespaces)
            
            # Classify all report elements
            search_elements, audit_elements, list_elements, aggregate_elements = self._classify_report_elements(root, namespaces)
            
            return ClassifiedElements(
                document_id=document_id,
                creation_time=creation_time,
                folders=folders,
                folder_tree=folder_tree,
                search_elements=search_elements,
                audit_elements=audit_elements,
                list_elements=list_elements,
                aggregate_elements=aggregate_elements,
                namespaces=namespaces,
                root_element=root
            )
            
        except Exception as e:
            raise Exception(f"Error classifying XML elements: {str(e)}")
    
    def _extract_document_metadata(self, root: ET.Element, namespaces: Dict) -> Tuple[str, str]:
        """Extract document-level metadata using namespace handler"""
        # Extract document ID
        doc_id_elem = self.ns.find(root, 'id')
        document_id = doc_id_elem.text if doc_id_elem is not None else "unknown"
        
        # Extract creation time
        creation_time_elem = self.ns.find(root, 'creationTime')
        creation_time = creation_time_elem.text if creation_time_elem is not None else ""
        
        return document_id, creation_time
    
    def _extract_folder_structure(self, root: ET.Element, namespaces: Dict) -> Tuple[List[ReportFolder], Dict[str, Any]]:
        """Extract shared folder structure"""
        folders = []
        
        # Find folder elements using namespace handler
        folder_elements = self.ns.findall_with_path(root, './/reportFolder')
        if not folder_elements:
            folder_elements = self.ns.findall_with_path(root, './/folder')
        
        for folder_elem in folder_elements:
            # Use namespace handler for consistent element finding
            folder_id_elem = self.ns.find(folder_elem, 'id')
            folder_name_elem = self.ns.find(folder_elem, 'name')
            folder_parent_elem = self.ns.find(folder_elem, 'parentFolder')
            
            if folder_id_elem is not None and folder_name_elem is not None:
                folder = ReportFolder(
                    id=folder_id_elem.text,
                    name=folder_name_elem.text,
                    parent_folder_id=folder_parent_elem.text if folder_parent_elem is not None else None
                )
                folders.append(folder)
        
        # Build folder tree structure
        folder_tree = self._build_folder_tree(folders)
        
        return folders, folder_tree
    
    def _build_folder_tree(self, folders: List[ReportFolder]) -> Dict[str, Any]:
        """Build hierarchical folder tree structure"""
        if not folders:
            return {}
        
        # Create folder lookup
        folder_map = {folder.id: folder for folder in folders}
        
        # Find root folders (no parent)
        root_folders = [folder for folder in folders if not folder.parent_folder_id]
        
        def build_tree_node(folder: ReportFolder) -> Dict[str, Any]:
            children = [f for f in folders if f.parent_folder_id == folder.id]
            return {
                'id': folder.id,
                'name': folder.name,
                'type': 'folder',
                'children': [build_tree_node(child) for child in children]
            }
        
        return {
            'roots': [build_tree_node(folder) for folder in root_folders],
            'total_folders': len(folders)
        }
    
    def _classify_report_elements(self, root: ET.Element, namespaces: Dict) -> Tuple[List[ET.Element], List[ET.Element], List[ET.Element], List[ET.Element]]:
        """Classify all report elements by type"""
        search_elements = []
        audit_elements = []
        list_elements = []
        aggregate_elements = []
        
        # Find all report elements using namespace handler
        report_elements = self.ns.findall_with_path(root, './/report')
        
        for report_elem in report_elements:
            report_type = self._determine_report_type(report_elem, namespaces)
            
            if report_type == 'search':
                search_elements.append(report_elem)
            elif report_type == 'audit':
                audit_elements.append(report_elem)
            elif report_type == 'list':
                list_elements.append(report_elem)
            elif report_type == 'aggregate':
                aggregate_elements.append(report_elem)
        
        return search_elements, audit_elements, list_elements, aggregate_elements
    
    def _determine_report_type(self, report_elem: ET.Element, namespaces: Dict) -> str:
        """Determine the type of a report element"""
        # ONLY check for explicit content structure indicators
        # parentType just indicates parent relationship, not element type
        
        # Check for explicit report type indicators using namespace handler
        if self.ns.find(report_elem, 'auditReport') is not None:
            return 'audit'
        elif self.ns.find(report_elem, 'aggregateReport') is not None:
            return 'aggregate'
        elif self.ns.find(report_elem, 'listReport') is not None:
            # Has listReport structure - this is definitely a list report
            return 'list'
        elif self.ns.find(report_elem, 'population') is not None:
            # Has population criteria - this is a search
            return 'search'
        else:
            # No specific structure indicators - default to search
            return 'search'
    
    def get_classification_summary(self, classified: ClassifiedElements) -> Dict[str, Any]:
        """Get summary of classification results"""
        return {
            'document_id': classified.document_id,
            'creation_time': classified.creation_time,
            'total_folders': len(classified.folders),
            'element_counts': {
                'searches': len(classified.search_elements),
                'audit_reports': len(classified.audit_elements),
                'list_reports': len(classified.list_elements),
                'aggregate_reports': len(classified.aggregate_elements)
            },
            'total_elements': (len(classified.search_elements) + len(classified.audit_elements) + 
                             len(classified.list_elements) + len(classified.aggregate_elements))
        }
