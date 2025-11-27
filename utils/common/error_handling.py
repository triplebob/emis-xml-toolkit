"""
Standardized error handling for the EMIS XML Converter application
Provides consistent exception classes, logging, and user-friendly error messages
"""

import logging
import traceback
from datetime import datetime
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
    TERMINOLOGY_SERVER = "terminology_server"
    SYSTEM = "system"


@dataclass
class ErrorContext:
    """Context information for errors"""
    operation: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    user_data: Optional[Dict[str, Any]] = None
    session_info: Optional[Dict[str, Any]] = None


@dataclass
class XMLParsingContext:
    """Specialised context for XML parsing errors"""
    element_name: Optional[str] = None
    element_path: Optional[str] = None
    parent_element: Optional[str] = None
    attribute_name: Optional[str] = None
    expected_format: Optional[str] = None
    actual_value: Optional[str] = None
    parsing_stage: Optional[str] = None
    validation_rules: Optional[list] = None
    namespace_info: Optional[Dict[str, str]] = None
    recovery_attempted: bool = False
    recovery_strategies: Optional[list] = None


@dataclass 
class ParseResult:
    """Result object for parsing operations that can succeed or fail"""
    success: bool
    data: Optional[Any] = None
    errors: Optional[list] = None
    warnings: Optional[list] = None
    context: Optional[XMLParsingContext] = None
    
    @classmethod
    def success_result(cls, data: Any) -> 'ParseResult':
        """Create a successful parse result"""
        return cls(success=True, data=data)
    
    @classmethod
    def failure_result(cls, errors: list, context: Optional[XMLParsingContext] = None) -> 'ParseResult':
        """Create a failed parse result"""
        return cls(success=False, errors=errors or [], context=context)
    
    @classmethod
    def partial_result(cls, data: Any, warnings: list, context: Optional[XMLParsingContext] = None) -> 'ParseResult':
        """Create a partial success result with warnings"""
        return cls(success=True, data=data, warnings=warnings or [], context=context)
    
    def add_error(self, error: str):
        """Add an error to the result"""
        if self.errors is None:
            self.errors = []
        self.errors.append(error)
        self.success = False
    
    def add_warning(self, warning: str):
        """Add a warning to the result"""
        if self.warnings is None:
            self.warnings = []
        self.warnings.append(warning)


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
            ErrorCategory.TERMINOLOGY_SERVER: "NHS Terminology Server connection issue. Please check your credentials and connection.",
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
    
    def __init__(self, message: str, element_name: str = None, 
                 xml_context: Optional[XMLParsingContext] = None, **kwargs):
        self.element_name = element_name
        self.xml_context = xml_context
        super().__init__(
            message=message,
            category=ErrorCategory.XML_PARSING,
            **kwargs
        )
    
    def get_technical_details(self) -> Dict[str, Any]:
        """Get technical details including XML-specific context"""
        details = super().get_technical_details()
        
        if self.xml_context:
            details['xml_parsing_context'] = {
                'element_name': self.xml_context.element_name,
                'element_path': self.xml_context.element_path,
                'parent_element': self.xml_context.parent_element,
                'attribute_name': self.xml_context.attribute_name,
                'expected_format': self.xml_context.expected_format,
                'actual_value': self.xml_context.actual_value,
                'parsing_stage': self.xml_context.parsing_stage,
                'validation_rules': self.xml_context.validation_rules,
                'namespace_info': self.xml_context.namespace_info,
                'recovery_attempted': self.xml_context.recovery_attempted,
                'recovery_strategies': self.xml_context.recovery_strategies
            }
        
        return details


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


class TerminologyServerError(EMISConverterError):
    """Specific error for NHS Terminology Server operations"""
    
    def __init__(self, message: str, error_type: str = None, 
                 api_response: Optional[Dict] = None, 
                 user_guidance: Optional[str] = None, **kwargs):
        self.error_type = error_type
        self.api_response = api_response
        self.user_guidance = user_guidance
        super().__init__(
            message=message,
            category=ErrorCategory.TERMINOLOGY_SERVER,
            **kwargs
        )
    
    def get_user_friendly_message(self) -> str:
        """Get user-friendly message with specific guidance for terminology server errors"""
        if self.user_guidance:
            return self.user_guidance
        
        # Map error types to user-friendly messages
        friendly_messages = {
            'authentication_failed': 'Authentication with NHS Terminology Server failed. Please check your credentials.',
            'code_not_found': 'The SNOMED code was not found in the NHS Terminology Server.',
            'invalid_code_format': 'The SNOMED code format is invalid. Please check the code and try again.',
            'server_error': 'The NHS Terminology Server is experiencing issues. Please try again later.',
            'rate_limit_exceeded': 'Too many requests sent to the server. Please wait a moment and try again.',
            'connection_error': 'Unable to connect to NHS Terminology Server. Please check your internet connection.',
            'timeout_error': 'Request to NHS Terminology Server timed out. Please try again.',
            'insufficient_permissions': 'Your account does not have permission to access this resource.',
            'malformed_response': 'Received unexpected response from NHS Terminology Server. Please try again.',
            'expansion_limit_exceeded': 'The concept has too many child codes to expand. Consider using filters.',
            'partial_failure': 'Some child codes could not be retrieved. The partial results are shown below.',
            'batch_timeout': 'The batch operation took too long and was stopped. Partial results may be available.',
        }
        
        return friendly_messages.get(self.error_type, 
                                   'An error occurred while communicating with NHS Terminology Server. Please try again.')
    
    def get_technical_details(self) -> Dict[str, Any]:
        """Enhanced technical details for terminology server errors"""
        details = super().get_technical_details()
        details.update({
            'error_type': self.error_type,
            'api_response': self.api_response,
            'user_guidance': self.user_guidance
        })
        return details


class ErrorHandler:
    """Centralised error handling and logging"""
    
    def __init__(self, logger_name: str = "emis_converter"):
        self.logger = logging.getLogger(logger_name)
        self._setup_logger()
        self._error_count = 0
        self._warning_count = 0
        self._session_errors = []
    
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
        
        # Track error metrics
        self._error_count += 1
        
        # Store error for session summary
        self._session_errors.append({
            'timestamp': datetime.now().isoformat(),
            'error': error,
            'details': technical_details
        })
        
        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(f"Critical error: {technical_details}")
        elif error.severity == ErrorSeverity.HIGH:
            self.logger.error(f"High severity error: {technical_details}")
        elif error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(f"Medium severity error: {technical_details}")
        else:
            self.logger.info(f"Low severity error: {technical_details}")
    
    def log_parsing_diagnostic(self, operation: str, element_name: str = None, 
                              context: XMLParsingContext = None, 
                              message: str = None, level: str = "info") -> None:
        """Log detailed diagnostic information for XML parsing"""
        diagnostic_info = {
            'operation': operation,
            'element_name': element_name,
            'timestamp': datetime.now().isoformat()
        }
        
        if context:
            diagnostic_info.update({
                'element_path': context.element_path,
                'parent_element': context.parent_element,
                'attribute_name': context.attribute_name,
                'expected_format': context.expected_format,
                'actual_value': context.actual_value,
                'parsing_stage': context.parsing_stage,
                'validation_rules': context.validation_rules,
                'namespace_info': context.namespace_info,
                'recovery_attempted': context.recovery_attempted,
                'recovery_strategies': context.recovery_strategies
            })
        
        log_message = f"XML Parsing Diagnostic - {operation}"
        if message:
            log_message += f": {message}"
        log_message += f" | Details: {diagnostic_info}"
        
        if level == "error":
            self.logger.error(log_message)
        elif level == "warning":
            self.logger.warning(log_message)
            self._warning_count += 1
        elif level == "debug":
            self.logger.debug(log_message)
        else:
            self.logger.info(log_message)
    
    def log_parsing_progress(self, operation: str, total_elements: int, 
                            processed_elements: int, errors: int = 0, warnings: int = 0):
        """Log parsing progress for large documents"""
        progress_pct = (processed_elements / total_elements * 100) if total_elements > 0 else 0
        
        self.logger.info(
            f"Parsing Progress - {operation}: {processed_elements}/{total_elements} "
            f"({progress_pct:.1f}%) | Errors: {errors} | Warnings: {warnings}"
        )
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of errors and warnings for the current session"""
        return {
            'total_errors': self._error_count,
            'total_warnings': self._warning_count,
            'error_details': self._session_errors,
            'session_start': 'N/A',  # Could be enhanced to track session start
            'last_error': self._session_errors[-1] if self._session_errors else None
        }
    
    def clear_session_data(self):
        """Clear session error tracking data"""
        self._error_count = 0
        self._warning_count = 0
        self._session_errors.clear()
    
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
        """Categorize a generic exception based on type and module"""
        exception_type = type(exception).__name__
        exception_module = type(exception).__module__
        
        # Check for specific exception types and their modules
        if exception_type == 'ParseError':
            # Could be xml.etree.ElementTree.ParseError or lxml.etree.XMLSyntaxError
            if 'xml.etree' in exception_module or 'lxml' in exception_module:
                return ErrorCategory.XML_PARSING
        
        # Map by exception type name
        category_map = {
            'XMLSyntaxError': ErrorCategory.XML_PARSING,
            'FileNotFoundError': ErrorCategory.FILE_OPERATION,
            'PermissionError': ErrorCategory.FILE_OPERATION,
            'IsADirectoryError': ErrorCategory.FILE_OPERATION,
            'IOError': ErrorCategory.FILE_OPERATION,
            'OSError': ErrorCategory.FILE_OPERATION,
            'UnicodeDecodeError': ErrorCategory.FILE_OPERATION,
            'UnicodeEncodeError': ErrorCategory.FILE_OPERATION,
            'ValueError': ErrorCategory.DATA_VALIDATION,
            'TypeError': ErrorCategory.DATA_VALIDATION,
            'KeyError': ErrorCategory.DATA_VALIDATION,
            'AttributeError': ErrorCategory.SYSTEM,
            'ImportError': ErrorCategory.SYSTEM,
            'ModuleNotFoundError': ErrorCategory.SYSTEM,
            'MemoryError': ErrorCategory.SYSTEM
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
    except EMISConverterError as emis_error:
        # Log our custom errors before re-raising for tracking
        error_handler.handle_error(emis_error)
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


def create_xml_parsing_context(element_name: str = None,
                              element_path: str = None,
                              parent_element: str = None,
                              **kwargs) -> XMLParsingContext:
    """Helper function to create XML parsing context"""
    return XMLParsingContext(
        element_name=element_name,
        element_path=element_path,
        parent_element=parent_element,
        **kwargs
    )


def handle_xml_parsing_error_with_context(operation: str, 
                                         exception: Exception,
                                         xml_context: XMLParsingContext) -> XMLParsingError:
    """Handle XML parsing errors with comprehensive context"""
    return XMLParsingError(
        message=f"XML parsing failed in {operation}: {str(exception)}",
        element_name=xml_context.element_name,
        xml_context=xml_context,
        context=create_error_context(operation),
        original_exception=exception
    )


def safe_xml_parse(operation_name: str,
                  parse_func: Callable,
                  xml_context: XMLParsingContext = None,
                  *args, **kwargs) -> ParseResult:
    """
    Safely execute XML parsing with structured error handling
    
    Returns ParseResult instead of throwing exceptions
    """
    try:
        result = parse_func(*args, **kwargs)
        return ParseResult.success_result(result)
    except XMLParsingError as e:
        return ParseResult.failure_result([str(e)], xml_context)
    except Exception as e:
        error_msg = f"Unexpected error in {operation_name}: {str(e)}"
        return ParseResult.failure_result([error_msg], xml_context)


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


def handle_terminology_server_error(operation: str, 
                                   error_type: str,
                                   api_response: Optional[Dict] = None,
                                   user_guidance: Optional[str] = None) -> TerminologyServerError:
    """Handle NHS Terminology Server errors with user guidance"""
    
    # Default user guidance messages for common scenarios
    default_guidance = {
        'authentication_failed': 'Please check your NHS Terminology Server credentials in the application settings.',
        'code_not_found': 'The SNOMED code was not found. Please verify the code is correct.',
        'invalid_code_format': 'The SNOMED code format is invalid. Please check the format and try again.',
        'server_error': 'NHS Terminology Server is experiencing issues. Please try again later.',
        'rate_limit_exceeded': 'Too many requests. Please wait a moment and try again.',
        'connection_error': 'Cannot connect to NHS Terminology Server. Please check your internet connection.',
        'timeout_error': 'Request timed out. Please try again.',
        'insufficient_permissions': 'Your account does not have the required permissions.',
        'expansion_limit_exceeded': 'Too many child codes to expand. Consider using filters to narrow the results.'
    }
    
    guidance = user_guidance or default_guidance.get(error_type, 
        'An issue occurred with NHS Terminology Server. Please try again.')
    
    return TerminologyServerError(
        message=f"NHS Terminology Server error in {operation}: {error_type}",
        error_type=error_type,
        api_response=api_response,
        user_guidance=guidance,
        context=create_error_context(operation)
    )


def create_user_friendly_error_message(error_type: str, context: Optional[str] = None) -> str:
    """Create user-friendly error messages for common scenarios"""
    
    messages = {
        'invalid_snomed_code': {
            'message': 'Invalid SNOMED Code Format',
            'description': 'The SNOMED code you entered is not in the correct format.',
            'actions': ['Check that the code contains only numbers', 'Verify the code length is appropriate', 'Try copying the code directly from your source']
        },
        'code_not_found': {
            'message': 'SNOMED Code Not Found',
            'description': 'This SNOMED code was not found in the NHS Terminology Server.',
            'actions': ['Double-check the code is typed correctly', 'Verify this is an active SNOMED CT code', 'Try searching for the concept description instead']
        },
        'connection_failed': {
            'message': 'Connection Problem',
            'description': 'Cannot connect to NHS Terminology Server.',
            'actions': ['Check your internet connection', 'Verify NHS Terminology Server is accessible', 'Try again in a few moments']
        },
        'authentication_failed': {
            'message': 'Authentication Required',
            'description': 'Your NHS Terminology Server credentials need to be configured.',
            'actions': ['Check your client ID and secret are correct', 'Ensure your account has appropriate permissions', 'Contact your administrator if problems persist']
        },
        'rate_limited': {
            'message': 'Too Many Requests',
            'description': 'You are sending requests too quickly to the NHS Terminology Server.',
            'actions': ['Wait a few moments before trying again', 'Consider processing fewer codes at once', 'The system will automatically slow down requests']
        },
        'server_overloaded': {
            'message': 'Server Temporarily Unavailable',
            'description': 'NHS Terminology Server is experiencing high load.',
            'actions': ['Try again in a few minutes', 'Consider processing during off-peak hours', 'Reduce the number of concurrent requests']
        },
        'expansion_too_large': {
            'message': 'Too Many Results',
            'description': 'This concept has too many child codes to display all at once.',
            'actions': ['Use filters to narrow the results', 'Consider expanding more specific child concepts', 'Export results for offline analysis']
        }
    }
    
    error_info = messages.get(error_type, {
        'message': 'An Error Occurred',
        'description': 'An unexpected error has occurred.',
        'actions': ['Try the operation again', 'Check your input is valid', 'Contact support if the problem persists']
    })
    
    formatted_message = f"{error_info['message']}: {error_info['description']}"
    
    if context:
        formatted_message += f" Context: {context}"
    
    if error_info.get('actions'):
        formatted_message += "\n\nWhat you can do:\n"
        for i, action in enumerate(error_info['actions'], 1):
            formatted_message += f"{i}. {action}\n"
    
    return formatted_message


@dataclass
class BatchParsingReport:
    """Report for batch parsing operations"""
    operation_name: str
    total_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    warnings_count: int = 0
    errors: list = None
    warnings: list = None
    processing_time: Optional[float] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_items == 0:
            return 0.0
        return (self.successful_items / self.total_items) * 100
    
    def add_error(self, error: str, context: XMLParsingContext = None):
        """Add an error to the batch report"""
        error_entry = {'message': error}
        if context:
            error_entry['context'] = context
        self.errors.append(error_entry)
        self.failed_items += 1
    
    def add_warning(self, warning: str, context: XMLParsingContext = None):
        """Add a warning to the batch report"""
        warning_entry = {'message': warning}
        if context:
            warning_entry['context'] = context
        self.warnings.append(warning_entry)
        self.warnings_count += 1
    
    def add_success(self):
        """Mark an item as successfully processed"""
        self.successful_items += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the batch processing results"""
        return {
            'operation': self.operation_name,
            'total_items': self.total_items,
            'successful_items': self.successful_items,
            'failed_items': self.failed_items,
            'success_rate': f"{self.success_rate:.1f}%",
            'warnings_count': self.warnings_count,
            'processing_time': f"{self.processing_time:.2f}s" if self.processing_time else "N/A",
            'errors_summary': len(self.errors),
            'warnings_summary': len(self.warnings)
        }


class BatchErrorAggregator:
    """Aggregates and analyses errors from batch processing operations"""
    
    def __init__(self, error_handler: ErrorHandler = None):
        self.error_handler = error_handler or ErrorHandler()
        self.batch_reports = []
        self.current_batch = None
    
    def start_batch(self, operation_name: str, total_items: int = 0) -> BatchParsingReport:
        """Start a new batch processing operation"""
        import time
        
        self.current_batch = BatchParsingReport(
            operation_name=operation_name,
            total_items=total_items
        )
        self.current_batch._start_time = time.time()
        
        self.error_handler.logger.info(
            f"Starting batch operation '{operation_name}' with {total_items} items"
        )
        
        return self.current_batch
    
    def finish_batch(self) -> BatchParsingReport:
        """Finish the current batch and calculate final metrics"""
        if not self.current_batch:
            raise ValueError("No active batch to finish")
        
        import time
        self.current_batch.processing_time = time.time() - getattr(self.current_batch, '_start_time', time.time())
        
        # Log batch summary
        summary = self.current_batch.get_summary()
        self.error_handler.logger.info(f"Batch operation completed: {summary}")
        
        # Store completed batch
        self.batch_reports.append(self.current_batch)
        completed_batch = self.current_batch
        self.current_batch = None
        
        return completed_batch
    
    def add_item_result(self, result: ParseResult, context: XMLParsingContext = None):
        """Add the result of processing a single item to the current batch"""
        if not self.current_batch:
            raise ValueError("No active batch - call start_batch first")
        
        if result.success:
            self.current_batch.add_success()
        else:
            for error in (result.errors or []):
                self.current_batch.add_error(error, context or result.context)
        
        for warning in (result.warnings or []):
            self.current_batch.add_warning(warning, context or result.context)
    
    def get_error_patterns(self) -> Dict[str, int]:
        """Analyse error patterns across all batch operations"""
        error_patterns = {}
        
        for batch in self.batch_reports:
            for error in batch.errors:
                error_msg = error['message']
                # Simple pattern matching - could be enhanced
                for pattern_key in ['XPath query failed', 'Element is None', 'Required attribute']:
                    if pattern_key in error_msg:
                        error_patterns[pattern_key] = error_patterns.get(pattern_key, 0) + 1
                        break
                else:
                    error_patterns['Other'] = error_patterns.get('Other', 0) + 1
        
        return error_patterns
    
    def get_aggregated_report(self) -> Dict[str, Any]:
        """Get an aggregated report of all batch operations"""
        total_operations = len(self.batch_reports)
        total_items = sum(batch.total_items for batch in self.batch_reports)
        total_successful = sum(batch.successful_items for batch in self.batch_reports)
        total_failed = sum(batch.failed_items for batch in self.batch_reports)
        total_warnings = sum(batch.warnings_count for batch in self.batch_reports)
        
        return {
            'summary': {
                'total_operations': total_operations,
                'total_items_processed': total_items,
                'total_successful': total_successful,
                'total_failed': total_failed,
                'total_warnings': total_warnings,
                'overall_success_rate': f"{(total_successful / total_items * 100) if total_items > 0 else 0:.1f}%"
            },
            'error_patterns': self.get_error_patterns(),
            'operations': [batch.get_summary() for batch in self.batch_reports]
        }


# Global error handler instance
_global_error_handler = ErrorHandler()
_global_batch_aggregator = BatchErrorAggregator(_global_error_handler)


def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance"""
    return _global_error_handler


def get_batch_aggregator() -> BatchErrorAggregator:
    """Get the global batch error aggregator instance"""
    return _global_batch_aggregator
