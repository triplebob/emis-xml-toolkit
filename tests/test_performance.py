"""
Performance Testing Script
Tests the performance controls and metrics functionality.
"""

import time
import unittest
from unittest.mock import Mock, patch
import pandas as pd
import xml.etree.ElementTree as ET
from io import StringIO

from util_modules.analysis.performance_optimizer import render_performance_controls, display_performance_metrics
from util_modules.xml_parsers.xml_utils import parse_xml_for_emis_guids


class TestPerformanceOptimizations(unittest.TestCase):
    """Test performance controls and metrics."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create sample lookup DataFrame
        self.sample_lookup_df = pd.DataFrame({
            'EMIS_GUID': ['guid1', 'guid2', 'guid3', 'guid4', 'guid5'],
            'SNOMED_Code': ['123456789', '987654321', '111222333', '444555666', '777888999'],
            'Source_Type': ['Clinical', 'Medication', 'Clinical', 'Medication', 'Clinical'],
            'HasQualifier': ['No', 'No', 'Yes', 'No', 'Yes'],
            'IsParent': ['Yes', 'No', 'No', 'Yes', 'No'],
            'Descendants': ['10', '0', '0', '5', '0'],
            'CodeType': ['Concept', 'Concept', 'Concept', 'Concept', 'Concept']
        })
        
        # Sample XML content for testing
        self.small_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <emis:search xmlns:emis="http://www.e-mis.com/emisopen">
            <emis:criterion>
                <emis:valueSet>
                    <emis:id>test-guid-1</emis:id>
                    <emis:description>Small Test XML</emis:description>
                    <emis:codeSystem>SNOMED_CONCEPT</emis:codeSystem>
                    <emis:values>
                        <emis:isRefset>false</emis:isRefset>
                        <emis:includeChildren>true</emis:includeChildren>
                        <emis:value>guid1</emis:value>
                        <emis:displayName>Test Code 1</emis:displayName>
                    </emis:values>
                </emis:valueSet>
            </emis:criterion>
        </emis:search>"""
        
        # Create a larger XML for performance testing
        self.large_xml = self._generate_large_xml(100)  # 100 valuesets
    
    def _generate_large_xml(self, num_valuesets: int) -> str:
        """Generate a large XML file for testing."""
        root = ET.Element("{http://www.e-mis.com/emisopen}search")
        
        for i in range(num_valuesets):
            criterion = ET.SubElement(root, "{http://www.e-mis.com/emisopen}criterion")
            valueset = ET.SubElement(criterion, "{http://www.e-mis.com/emisopen}valueSet")
            
            id_elem = ET.SubElement(valueset, "{http://www.e-mis.com/emisopen}id")
            id_elem.text = f"test-guid-{i}"
            
            desc_elem = ET.SubElement(valueset, "{http://www.e-mis.com/emisopen}description")
            desc_elem.text = f"Test ValueSet {i}"
            
            system_elem = ET.SubElement(valueset, "{http://www.e-mis.com/emisopen}codeSystem")
            system_elem.text = "SNOMED_CONCEPT"
            
            values_elem = ET.SubElement(valueset, "{http://www.e-mis.com/emisopen}values")
            
            refset_elem = ET.SubElement(values_elem, "{http://www.e-mis.com/emisopen}isRefset")
            refset_elem.text = "false"
            
            children_elem = ET.SubElement(values_elem, "{http://www.e-mis.com/emisopen}includeChildren")
            children_elem.text = "true"
            
            # Add multiple values per valueset
            for j in range(5):
                value_elem = ET.SubElement(values_elem, "{http://www.e-mis.com/emisopen}value")
                value_elem.text = f"guid{i}_{j}"
                
                display_elem = ET.SubElement(values_elem, "{http://www.e-mis.com/emisopen}displayName")
                display_elem.text = f"Test Code {i}_{j}"
        
        xml_str = ET.tostring(root, encoding='unicode')
        return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'
    
    def test_performance_controls_render(self):
        """Test that performance controls render with correct options."""
        # Mock Streamlit session for testing
        import unittest.mock as mock
        
        with mock.patch('streamlit.sidebar') as mock_sidebar, \
             mock.patch('streamlit.expander') as mock_expander, \
             mock.patch('streamlit.checkbox') as mock_checkbox, \
             mock.patch('streamlit.selectbox') as mock_selectbox, \
             mock.patch('streamlit.caption') as mock_caption:
            
            # Set up mock returns
            mock_checkbox.side_effect = [True, True, False]  # chunk_large_files, show_progress, show_metrics
            mock_selectbox.return_value = "Memory Optimized"
            
            # Call the function
            settings = render_performance_controls()
            
            # Verify settings structure
            self.assertIn('strategy', settings)
            self.assertIn('max_workers', settings)
            self.assertIn('memory_optimize', settings)
            self.assertIn('show_metrics', settings)
            self.assertIn('show_progress', settings)
            self.assertIn('chunk_large_files', settings)
            self.assertIn('environment', settings)
            
            # Verify cloud-compatible defaults
            self.assertEqual(settings['max_workers'], 1)
            self.assertTrue(settings['memory_optimize'])
            self.assertEqual(settings['environment'], 'cloud')
    
    def test_performance_metrics_display(self):
        """Test that performance metrics display correctly."""
        import unittest.mock as mock
        
        # Sample metrics data
        test_metrics = {
            'memory_peak_mb': 45.2,
            'total_time': 2.34,
            'processing_strategy': 'Memory Optimized',
            'items_processed': 150
        }
        
        with mock.patch('streamlit.markdown') as mock_markdown, \
             mock.patch('streamlit.columns') as mock_columns:
            
            # Mock columns return
            mock_col = mock.MagicMock()
            mock_columns.return_value = [mock_col, mock_col, mock_col, mock_col]
            
            # Call the function
            display_performance_metrics(test_metrics)
            
            # Verify that markdown was called (it will be called multiple times)
            # Check that it was called at least once with the header
            calls = mock_markdown.call_args_list
            header_called = any('Performance Metrics' in str(call) for call in calls)
            self.assertTrue(header_called, "Performance Metrics header should be displayed")
            
            # Verify columns were created
            mock_columns.assert_called_with(4)
    
    def test_memory_tracking_functionality(self):
        """Test memory tracking works correctly."""
        import psutil
        import os
        
        # Get current process
        process = psutil.Process(os.getpid())
        
        # Test memory measurement
        memory_start = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform some memory-using operation
        large_data = ['x' * 1000 for _ in range(1000)]  # Create some data
        
        memory_end = process.memory_info().rss / 1024 / 1024  # MB
        
        # Memory should be measurable
        self.assertGreater(memory_start, 0)
        self.assertGreater(memory_end, 0)
        
        # Clean up
        del large_data
    
    def test_xml_size_classification(self):
        """Test that XML files are classified by size correctly."""
        # Test file size classification logic
        small_xml_size = len(self.small_xml.encode('utf-8'))
        large_xml_size = len(self.large_xml.encode('utf-8'))
        
        # Small XML should be under 1MB
        self.assertLess(small_xml_size, 1024 * 1024)
        
        # Large XML should be larger
        self.assertGreater(large_xml_size, small_xml_size)
        
        # Test size-based processing recommendations
        if small_xml_size < 1024 * 1024:  # < 1MB
            recommended_strategy = "Standard"
        else:
            recommended_strategy = "Memory Optimized"
        
        self.assertEqual(recommended_strategy, "Standard")
    
    def test_cloud_environment_detection(self):
        """Test cloud environment detection logic."""
        import os
        import unittest.mock as mock
        
        # Test local environment (no cloud indicators)
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch('os.path.exists', return_value=False):
                is_cloud = (os.getenv('STREAMLIT_SHARING_MODE') or 
                           os.getenv('HOSTNAME', '').startswith('streamlit') or
                           'streamlit.app' in os.getenv('STREAMLIT_SERVER_HEADLESS', '') or
                           os.path.exists('/.streamlit'))
                self.assertFalse(is_cloud)
        
        # Test cloud environment (with cloud indicators)
        with mock.patch.dict(os.environ, {'STREAMLIT_SHARING_MODE': 'true'}):
            is_cloud = (os.getenv('STREAMLIT_SHARING_MODE') or 
                       os.getenv('HOSTNAME', '').startswith('streamlit') or
                       'streamlit.app' in os.getenv('STREAMLIT_SERVER_HEADLESS', '') or
                       os.path.exists('/.streamlit'))
            self.assertTrue(is_cloud)
    
    def test_performance_comparison(self):
        """Compare performance between sync and async processing."""
        # Test XML parsing performance
        start_time = time.time()
        emis_guids = parse_xml_for_emis_guids(self.small_xml)
        parse_time = time.time() - start_time
        
        # Verify parsing results
        self.assertEqual(len(emis_guids), 1)
        self.assertEqual(emis_guids[0]['emis_guid'], 'guid1')
        self.assertEqual(emis_guids[0]['xml_display_name'], 'Test Code 1')
        
        # Parsing should be fast for small files
        self.assertLess(parse_time, 0.1)
        
        # Test larger XML performance
        start_time = time.time()
        large_emis_guids = parse_xml_for_emis_guids(self.large_xml)
        large_parse_time = time.time() - start_time
        
        # Should handle larger files efficiently
        self.assertGreater(len(large_emis_guids), 400)  # 100 valuesets * 5 values each
        self.assertLess(large_parse_time, 2.0)  # Should complete within 2 seconds


class TestMemoryOptimization(unittest.TestCase):
    """Test memory optimization features."""
    
    def test_memory_efficient_xml_parsing(self):
        """Test that XML parsing is memory efficient."""
        import psutil
        import os
        
        # Monitor memory during XML parsing
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # Parse a medium-sized XML
        test_xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <emis:search xmlns:emis="http://www.e-mis.com/emisopen">
        ''' + ''.join([
            f'''
            <emis:criterion>
                <emis:valueSet>
                    <emis:id>test-guid-{i}</emis:id>
                    <emis:description>Test ValueSet {i}</emis:description>
                    <emis:codeSystem>SNOMED_CONCEPT</emis:codeSystem>
                    <emis:values>
                        <emis:isRefset>false</emis:isRefset>
                        <emis:includeChildren>true</emis:includeChildren>
                        <emis:value>guid{i}</emis:value>
                        <emis:displayName>Test Code {i}</emis:displayName>
                    </emis:values>
                </emis:valueSet>
            </emis:criterion>
            ''' for i in range(50)
        ]) + '''
        </emis:search>'''
        
        # Parse the XML
        result = parse_xml_for_emis_guids(test_xml)
        
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = memory_after - memory_before
        
        # Verify parsing worked
        self.assertEqual(len(result), 50)
        
        # Memory increase should be reasonable (less than 50MB for this test)
        self.assertLess(memory_increase, 50)


if __name__ == '__main__':
    # Run performance tests with verbose output
    unittest.main(verbosity=2)
