"""
Common utilities for EMIS XML Convertor
Provides shared functionality across the application
"""

from .export_utils import (
    create_excel_workbook,
    add_worksheet_with_data,
    generate_export_filename,
    validate_export_data,
    save_workbook_to_bytes
)

from .dataframe_utils import (
    create_standard_dataframe,
    format_dataframe_columns,
    validate_dataframe_data,
    apply_standard_formatting
)

from .error_handling import (
    EMISConverterError, XMLParsingError, DataValidationError, FileOperationError, ExportError,
    ErrorSeverity, ErrorCategory, ErrorContext, ErrorHandler,
    safe_execute, create_error_context, get_error_handler,
    handle_xml_parsing_error, handle_validation_error, handle_file_operation_error
)

from .ui_error_handling import (
    display_error_to_user, display_generic_error, streamlit_safe_execute,
    create_error_recovery_section, with_error_boundary, check_session_state_errors,
    show_xml_parse_error, show_file_error, show_validation_error, show_export_error
)

__all__ = [
    # Export utilities
    'create_excel_workbook',
    'add_worksheet_with_data', 
    'generate_export_filename',
    'validate_export_data',
    'save_workbook_to_bytes',
    
    # DataFrame utilities
    'create_standard_dataframe',
    'format_dataframe_columns',
    'validate_dataframe_data',
    'apply_standard_formatting',
    
    # Error handling - Core classes
    'EMISConverterError', 'XMLParsingError', 'DataValidationError', 
    'FileOperationError', 'ExportError',
    'ErrorSeverity', 'ErrorCategory', 'ErrorContext', 'ErrorHandler',
    
    # Error handling - Utility functions
    'safe_execute', 'create_error_context', 'get_error_handler',
    'handle_xml_parsing_error', 'handle_validation_error', 'handle_file_operation_error',
    
    # UI Error handling
    'display_error_to_user', 'display_generic_error', 'streamlit_safe_execute',
    'create_error_recovery_section', 'with_error_boundary', 'check_session_state_errors',
    'show_xml_parse_error', 'show_file_error', 'show_validation_error', 'show_export_error'
]
