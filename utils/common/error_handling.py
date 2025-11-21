"""
Standardized error handling for the EMIS XML Converter application
Provides consistent exception classes, logging, and user-friendly error messages
"""

import logging
import traceback
from typing import Optional, Dict, Any, Callable
from enum import Enum
from dataclasses import dataclass


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for better classification"""
    XML_PARSING = "xml_parsing"
    DATA_VALIDATION = "data_validation"
    FILE_OPERATION = "file_operation"
    BUSINESS_LOGIC = "business_logic"
    UI_RENDERING = "ui_rendering"
    EXPORT_OPERATION = "export_operation"
    SYSTEM = "system"


@dataclass
class ErrorContext:
    """Context information for errors"""
    operation: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    user_data: Optional[Dict[str, Any]] = None
    session_info: Optional[Dict[str, Any]] = None


class EMISConverterError(Exception):
    """Base exception class for EMIS Converter application"""
    
    def __init__(self, 
                 message: str,
                 category: ErrorCategory = ErrorCategory.SYSTEM,
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 context: Optional[ErrorContext] = None,
                 original_exception: Optional[Exception] = None):
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context
        self.original_exception = original_exception
        super().__init__(self.message)
    
    def get_user_friendly_message(self) -> str:
        """Get a user-friendly version of the error message"""
        friendly_messages = {
            ErrorCategory.XML_PARSING: "There was an issue processing the XML file. Please check the file format and try again.",
            ErrorCategory.DATA_VALIDATION: "The data contains invalid or unexpected values. Please review your input.",
            ErrorCategory.FILE_OPERATION: "There was a problem accessing or saving files. Please check permissions and try again.",
            ErrorCategory.BUSINESS_LOGIC: "A business rule validation failed. Please review your search criteria.",
            ErrorCategory.UI_RENDERING: "There was a display issue. Please refresh the page and try again.",
            ErrorCategory.EXPORT_OPERATION: "Export failed. Please check your selections and try again.",
            ErrorCategory.SYSTEM: "A system error occurred. Please try again or contact support."
        }
        return friendly_messages.get(self.category, self.message)
    
    def get_technical_details(self) -> Dict[str, Any]:
        """Get technical details for logging"""
        details = {
            'message': self.message,
            'category': self.category.value,
            'severity': self.severity.value
        }
        
        if self.context:
            details['context'] = {
                'operation': self.context.operation,
                'file_path': self.context.file_path,
                'line_number': self.context.line_number
            }
        
        if self.original_exception:
            details['original_exception'] = {
                'type': type(self.original_exception).__name__,
                'message': str(self.original_exception),
                'traceback': traceback.format_exc()
            }
        
        return details


class XMLParsingError(EMISConverterError):
    """Specific error for XML parsing issues"""
    
    def __init__(self, message: str, element_name: str = None, **kwargs):
        self.element_name = element_name
        super().__init__(
            message=message,
            category=ErrorCategory.XML_PARSING,
            **kwargs
        )


class DataValidationError(EMISConverterError):
    """Specific error for data validation issues"""
    
    def __init__(self, message: str, field_name: str = None, value: Any = None, **kwargs):
        self.field_name = field_name
        self.value = value
        super().__init__(
            message=message,
            category=ErrorCategory.DATA_VALIDATION,
            **kwargs
        )


class FileOperationError(EMISConverterError):
    """Specific error for file operation issues"""
    
    def __init__(self, message: str, file_path: str = None, operation: str = None, **kwargs):
        self.file_path = file_path
        self.operation = operation
        super().__init__(
            message=message,
            category=ErrorCategory.FILE_OPERATION,
            **kwargs
        )


class ExportError(EMISConverterError):
    """Specific error for export operation issues"""
    
    def __init__(self, message: str, export_type: str = None, **kwargs):
        self.export_type = export_type
        super().__init__(
            message=message,
            category=ErrorCategory.EXPORT_OPERATION,
            **kwargs
        )


class ErrorHandler:
    """Centralized error handling and logging"""
    
    def __init__(self, logger_name: str = "emis_converter"):
        self.logger = logging.getLogger(logger_name)
        self._setup_logger()
    
    def _setup_logger(self):
        """Setup logging configuration"""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def handle_error(self, error: EMISConverterError) -> None:
        """Handle an error with appropriate logging"""
        # Log technical details
        technical_details = error.get_technical_details()
        
        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(f"Critical error: {technical_details}")
        elif error.severity == ErrorSeverity.HIGH:
            self.logger.error(f"High severity error: {technical_details}")
        elif error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(f"Medium severity error: {technical_details}")
        else:
            self.logger.info(f"Low severity error: {technical_details}")
    
    def log_exception(self, 
                     operation: str,
                     exception: Exception,
                     context: Optional[ErrorContext] = None,
                     severity: ErrorSeverity = ErrorSeverity.MEDIUM) -> EMISConverterError:
        """Convert a generic exception to EMISConverterError and log it"""
        
        # Determine category based on exception type
        category = self._categorize_exception(exception)
        
        # Create EMISConverterError
        emis_error = EMISConverterError(
            message=f"Error in {operation}: {str(exception)}",
            category=category,
            severity=severity,
            context=context,
            original_exception=exception
        )
        
        # Handle the error
        self.handle_error(emis_error)
        
        return emis_error
    
    def _categorize_exception(self, exception: Exception) -> ErrorCategory:
        """Categorize a generic exception"""
        exception_type = type(exception).__name__
        
        category_map = {
            'ET.ParseError': ErrorCategory.XML_PARSING,
            'ParseError': ErrorCategory.XML_PARSING,
            'XMLSyntaxError': ErrorCategory.XML_PARSING,
            'FileNotFoundError': ErrorCategory.FILE_OPERATION,
            'PermissionError': ErrorCategory.FILE_OPERATION,
            'IOError': ErrorCategory.FILE_OPERATION,
            'ValueError': ErrorCategory.DATA_VALIDATION,
            'TypeError': ErrorCategory.DATA_VALIDATION,
            'KeyError': ErrorCategory.DATA_VALIDATION,
            'AttributeError': ErrorCategory.SYSTEM
        }
        
        return category_map.get(exception_type, ErrorCategory.SYSTEM)


def safe_execute(operation_name: str, 
                func: Callable,
                *args,
                context: Optional[ErrorContext] = None,
                error_handler: Optional[ErrorHandler] = None,
                default_return=None,
                **kwargs) -> Any:
    """
    Safely execute a function with standardized error handling
    
    Args:
        operation_name: Name of the operation for logging
        func: Function to execute
        *args: Arguments for the function
        context: Error context information
        error_handler: Error handler instance
        default_return: Value to return if function fails
        **kwargs: Keyword arguments for the function
        
    Returns:
        Function result or default_return if error occurs
    """
    if error_handler is None:
        error_handler = ErrorHandler()
    
    try:
        return func(*args, **kwargs)
    except EMISConverterError:
        # Re-raise our custom errors
        raise
    except Exception as e:
        # Convert generic exceptions
        emis_error = error_handler.log_exception(operation_name, e, context)
        
        # Return default or re-raise based on severity
        if emis_error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            raise emis_error
        else:
            return default_return


def create_error_context(operation: str, 
                        file_path: str = None,
                        line_number: int = None,
                        **kwargs) -> ErrorContext:
    """Helper function to create error context"""
    return ErrorContext(
        operation=operation,
        file_path=file_path,
        line_number=line_number,
        user_data=kwargs.get('user_data'),
        session_info=kwargs.get('session_info')
    )


# Convenience functions for common error patterns
def handle_xml_parsing_error(operation: str, exception: Exception, element_name: str = None) -> XMLParsingError:
    """Handle XML parsing errors with specific context"""
    return XMLParsingError(
        message=f"Failed to parse XML in {operation}: {str(exception)}",
        element_name=element_name,
        context=create_error_context(operation),
        original_exception=exception
    )


def handle_validation_error(field_name: str, value: Any, message: str = None) -> DataValidationError:
    """Handle data validation errors"""
    default_message = f"Invalid value for {field_name}: {value}"
    return DataValidationError(
        message=message or default_message,
        field_name=field_name,
        value=value
    )


def handle_file_operation_error(operation: str, file_path: str, exception: Exception) -> FileOperationError:
    """Handle file operation errors"""
    return FileOperationError(
        message=f"File operation '{operation}' failed: {str(exception)}",
        file_path=file_path,
        operation=operation,
        context=create_error_context(operation, file_path=file_path),
        original_exception=exception
    )


# Global error handler instance
_global_error_handler = ErrorHandler()


def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance"""
    return _global_error_handler
