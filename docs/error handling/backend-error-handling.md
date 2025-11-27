# Backend Error Handling - Technical Guide

## Overview

The backend error handling system (`utils/common/error_handling.py`) provides the core infrastructure for error creation, categorisation, logging, and tracking throughout the ClinXML application. This system is designed for reliability, comprehensive diagnostics, and enterprise-level error management.

## Core Components

### Exception Hierarchy

#### Base Exception Class
```python
class EMISConverterError(Exception):
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
```

#### Specialised Exception Classes
```python
# XML parsing errors with comprehensive context
class XMLParsingError(EMISConverterError):
    def __init__(self, message: str, element_name: str = None, 
                 xml_context: Optional[XMLParsingContext] = None):
        # Automatically categorised as ErrorCategory.XML_PARSING

# Data validation errors with field context
class DataValidationError(EMISConverterError):
    def __init__(self, message: str, field_name: str = None, value: Any = None):
        # Automatically categorised as ErrorCategory.DATA_VALIDATION

# File operation errors with file context
class FileOperationError(EMISConverterError):
    def __init__(self, message: str, file_path: str = None, operation: str = None):
        # Automatically categorised as ErrorCategory.FILE_OPERATION

# NHS Terminology Server errors with API context
class TerminologyServerError(EMISConverterError):
    def __init__(self, message: str, error_type: str = None, 
                 api_response: Optional[Dict] = None):
        # Automatically categorised as ErrorCategory.TERMINOLOGY_SERVER
```

### Error Categories and Severity Levels

#### Error Categories
```python
class ErrorCategory(Enum):
    XML_PARSING = "xml_parsing"           # XML structure and parsing issues
    DATA_VALIDATION = "data_validation"   # Invalid data values or formats
    FILE_OPERATION = "file_operation"     # File access and I/O issues
    BUSINESS_LOGIC = "business_logic"     # Application logic failures
    UI_RENDERING = "ui_rendering"         # User interface display issues
    EXPORT_OPERATION = "export_operation" # Data export and saving issues
    TERMINOLOGY_SERVER = "terminology_server" # NHS Term Server issues
    SYSTEM = "system"                     # General system and infrastructure
```

#### Severity Levels
```python
class ErrorSeverity(Enum):
    LOW = "low"           # Minor issues, processing can continue
    MEDIUM = "medium"     # Significant issues, may affect quality
    HIGH = "high"         # Major issues, likely to prevent completion
    CRITICAL = "critical" # System-level issues, immediate attention required
```

### Error Context Objects

#### Generic Error Context
```python
@dataclass
class ErrorContext:
    operation: str                              # What operation was being performed
    file_path: Optional[str] = None            # File being processed
    line_number: Optional[int] = None          # Line number (if applicable)
    user_data: Optional[Dict[str, Any]] = None # Additional user context
    session_info: Optional[Dict[str, Any]] = None # Session-level information
```

#### XML Parsing Context
```python
@dataclass
class XMLParsingContext:
    element_name: Optional[str] = None          # XML element being parsed
    element_path: Optional[str] = None          # XPath location
    parent_element: Optional[str] = None        # Parent element context
    attribute_name: Optional[str] = None        # Attribute being extracted
    expected_format: Optional[str] = None       # Expected data format
    actual_value: Optional[str] = None          # Actual value found
    parsing_stage: Optional[str] = None         # Stage of parsing process
    validation_rules: Optional[list] = None     # Applied validation rules
    namespace_info: Optional[Dict[str, str]] = None # Namespace context
    recovery_attempted: bool = False            # Whether recovery was tried
    recovery_strategies: Optional[list] = None  # Available recovery options
```

### ParseResult Pattern

#### Structured Parsing Results
```python
@dataclass
class ParseResult:
    success: bool                               # Operation success status
    data: Optional[Any] = None                  # Parsed data (if successful)
    errors: Optional[list] = None               # Error messages
    warnings: Optional[list] = None             # Warning messages
    context: Optional[XMLParsingContext] = None # Parsing context
    
    @classmethod
    def success_result(cls, data: Any) -> 'ParseResult':
        return cls(success=True, data=data)
    
    @classmethod
    def failure_result(cls, errors: list, context: Optional[XMLParsingContext] = None) -> 'ParseResult':
        return cls(success=False, errors=errors or [], context=context)
    
    @classmethod
    def partial_result(cls, data: Any, warnings: list, context: Optional[XMLParsingContext] = None) -> 'ParseResult':
        return cls(success=True, data=data, warnings=warnings or [], context=context)
```

## Error Handler

### Core Error Handler Class
```python
class ErrorHandler:
    def __init__(self, logger_name: str = "emis_converter"):
        self.logger = logging.getLogger(logger_name)
        self._error_count = 0
        self._warning_count = 0
        self._session_errors = []
    
    def handle_error(self, error: EMISConverterError) -> None:
        # Log technical details with appropriate severity
        # Track error metrics for session summary
        # Store error for audit purposes
    
    def log_parsing_diagnostic(self, operation: str, element_name: str = None, 
                              context: XMLParsingContext = None, 
                              message: str = None, level: str = "info") -> None:
        # Log detailed diagnostic information for XML parsing operations
    
    def log_parsing_progress(self, operation: str, total_elements: int, 
                            processed_elements: int, errors: int = 0, warnings: int = 0):
        # Log progress for large document processing operations
    
    def log_exception(self, operation: str, exception: Exception,
                     context: Optional[ErrorContext] = None,
                     severity: ErrorSeverity = ErrorSeverity.MEDIUM) -> EMISConverterError:
        # Convert generic exceptions to structured EMISConverterError
        # Automatic categorisation based on exception type
        # Return structured error for further handling
```

### Safe Execution Pattern
```python
def safe_execute(operation_name: str, 
                func: Callable,
                *args,
                context: Optional[ErrorContext] = None,
                error_handler: Optional[ErrorHandler] = None,
                default_return=None,
                **kwargs) -> Any:
    """
    Safely execute a function with standardised error handling
    
    Returns function result or default_return if error occurs
    Converts generic exceptions to structured EMISConverterError
    """
    if error_handler is None:
        error_handler = ErrorHandler()
    
    try:
        return func(*args, **kwargs)
    except EMISConverterError:
        raise  # Re-raise structured errors
    except Exception as e:
        emis_error = error_handler.log_exception(operation_name, e, context)
        if emis_error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            raise emis_error
        else:
            return default_return
```

## Batch Processing and Enterprise Features

### Batch Processing Reports
```python
@dataclass
class BatchParsingReport:
    operation_name: str                  # Operation identifier
    total_items: int = 0                # Total items to process
    successful_items: int = 0           # Successfully processed count
    failed_items: int = 0               # Failed items count
    warnings_count: int = 0             # Warning count
    errors: list = None                 # Detailed error list
    warnings: list = None               # Detailed warning list
    processing_time: Optional[float] = None  # Execution time
    
    @property
    def success_rate(self) -> float:
        if self.total_items == 0:
            return 0.0
        return (self.successful_items / self.total_items) * 100
```

### Batch Error Aggregator
```python
class BatchErrorAggregator:
    def start_batch(self, operation_name: str, total_items: int = 0) -> BatchParsingReport:
        # Start tracking a new batch operation
    
    def finish_batch(self) -> BatchParsingReport:
        # Complete batch and calculate final metrics
    
    def add_item_result(self, result: ParseResult, context: XMLParsingContext = None):
        # Add individual item result to batch tracking
    
    def get_error_patterns(self) -> Dict[str, int]:
        # Analyse error patterns across all batches
    
    def get_aggregated_report(self) -> Dict[str, Any]:
        # Get comprehensive report across all batch operations
```

## Helper Functions and Utilities

### Error Creation Helpers
```python
def create_error_context(operation: str, 
                        file_path: str = None,
                        line_number: int = None,
                        **kwargs) -> ErrorContext:
    # Helper to create error context objects

def create_xml_parsing_context(element_name: str = None,
                              element_path: str = None,
                              parent_element: str = None,
                              **kwargs) -> XMLParsingContext:
    # Helper to create XML parsing context objects

def handle_xml_parsing_error(operation: str, exception: Exception, element_name: str = None) -> XMLParsingError:
    # Create XMLParsingError with proper context

def handle_file_operation_error(operation: str, file_path: str, exception: Exception) -> FileOperationError:
    # Create FileOperationError with file context

def handle_terminology_server_error(operation: str, 
                                   error_type: str,
                                   api_response: Optional[Dict] = None,
                                   user_guidance: Optional[str] = None) -> TerminologyServerError:
    # Create TerminologyServerError with API context and user guidance
```

### Safe XML Parsing
```python
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
```

## Implementation Patterns

### Basic Error Creation and Handling
```python
from utils.common.error_handling import (
    ErrorHandler, create_error_context, ErrorSeverity
)

# Initialize error handler
error_handler = ErrorHandler("my_module")

# Create error context
context = create_error_context(
    operation="file_processing",
    file_path="/path/to/file.xml",
    user_data={"file_size": 1024000}
)

# Handle exceptions with structured error creation
try:
    process_file(filename)
except Exception as e:
    structured_error = error_handler.log_exception(
        "file processing",
        e,
        context,
        ErrorSeverity.HIGH
    )
    # Error is logged and categorised automatically
    raise structured_error  # Re-raise for upstream handling
```

### XML Parsing with ParseResult
```python
from utils.common.error_handling import (
    ParseResult, create_xml_parsing_context, safe_xml_parse
)

def parse_criterion(criterion_elem) -> ParseResult:
    xml_context = create_xml_parsing_context(
        element_name="criterion",
        element_path="//criteria/criterion",
        parsing_stage="criterion_parsing"
    )
    
    def _parse_criterion_internal():
        # Actual parsing logic
        criterion_id = criterion_elem.get('id')
        if not criterion_id:
            raise ValueError("Missing required 'id' attribute")
        
        return {
            'id': criterion_id,
            'display_name': criterion_elem.text or 'Unknown'
        }
    
    # Use safe parsing wrapper
    return safe_xml_parse(
        "criterion_parsing",
        _parse_criterion_internal,
        xml_context
    )
```

### Batch Processing Integration
```python
from utils.common.error_handling import get_batch_aggregator

# Get global batch aggregator
batch_aggregator = get_batch_aggregator()

# Start batch operation
batch_report = batch_aggregator.start_batch("xml_processing", total_items=len(criteria))

# Process items with error tracking
for criterion_elem in criteria:
    result = parse_criterion(criterion_elem)
    batch_aggregator.add_item_result(result)
    
    if result.success:
        processed_criteria.append(result.data)
    else:
        # Errors are automatically tracked in batch report
        for error in result.errors:
            print(f"Criterion parsing failed: {error}")

# Complete batch with comprehensive reporting
final_report = batch_aggregator.finish_batch()
print(f"Processing completed: {final_report.success_rate:.1f}% success rate")
```

## Error Categorisation Logic

### Automatic Exception Categorisation
```python
def _categorize_exception(self, exception: Exception) -> ErrorCategory:
    """Automatically categorise exceptions based on type"""
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
```

### User-Friendly Message Generation
```python
def get_user_friendly_message(self) -> str:
    """Convert technical errors to user-friendly messages"""
    friendly_messages = {
        ErrorCategory.XML_PARSING: "There was an issue processing the XML file. Please check the file format and try again.",
        ErrorCategory.DATA_VALIDATION: "The data contains invalid or unexpected values. Please review your input.",
        ErrorCategory.FILE_OPERATION: "There was a problem accessing or saving files. Please check permissions and try again.",
        ErrorCategory.BUSINESS_LOGIC: "A business rule validation failed. Please review your search criteria.",
        ErrorCategory.TERMINOLOGY_SERVER: "NHS Terminology Server connection issue. Please check your credentials and connection.",
        ErrorCategory.SYSTEM: "A system error occurred. Please try again or contact support."
    }
    return friendly_messages.get(self.category, self.message)
```

## Performance Considerations

### Efficient Error Collection
- **Structured Objects**: Avoid expensive string formatting until needed
- **Lazy Evaluation**: Only generate detailed context when errors occur  
- **Batch Processing**: Collect errors efficiently across large documents
- **Memory Management**: Clear error collections appropriately

### Error Pattern Caching
```python
# Cache validation results for repeated patterns
_validation_cache = {}

def validate_format(value: str, format_type: str) -> bool:
    cache_key = f"{format_type}:{value}"
    if cache_key in _validation_cache:
        return _validation_cache[cache_key]
    
    result = _perform_validation(value, format_type)
    _validation_cache[cache_key] = result
    return result
```

## Testing and Validation

### Unit Test Patterns
```python
import pytest
from utils.common.error_handling import (
    EMISConverterError, ErrorCategory, ErrorSeverity, 
    create_error_context, ParseResult
)

def test_error_context_creation():
    context = create_error_context(
        operation="test_operation",
        file_path="/test/file.xml",
        user_data={"test": "data"}
    )
    assert context.operation == "test_operation"
    assert context.file_path == "/test/file.xml"
    assert context.user_data["test"] == "data"

def test_parse_result_patterns():
    # Test success result
    success = ParseResult.success_result({"data": "test"})
    assert success.success is True
    assert success.data == {"data": "test"}
    
    # Test failure result
    failure = ParseResult.failure_result(["error message"])
    assert failure.success is False
    assert failure.errors == ["error message"]

def test_error_categorisation():
    error = EMISConverterError(
        "Test error",
        category=ErrorCategory.XML_PARSING,
        severity=ErrorSeverity.HIGH
    )
    assert error.category == ErrorCategory.XML_PARSING
    assert error.severity == ErrorSeverity.HIGH
```

## Best Practices

### Error Creation
1. **Use Specific Exception Classes**: XMLParsingError, FileOperationError, etc.
2. **Provide Rich Context**: Include operation, file paths, and relevant data
3. **Set Appropriate Severity**: Match severity to actual impact
4. **Include Original Exception**: Preserve original exception for debugging

### Error Handling
1. **Use ParseResult Pattern**: For operations that may fail gracefully
2. **Leverage Safe Execute**: For operations that should continue on error
3. **Create Structured Context**: Always provide operation and context information
4. **Log at Appropriate Level**: Match logging level to error severity

### Performance
1. **Lazy Context Generation**: Only create expensive context when needed
2. **Batch Error Collection**: Use BatchErrorAggregator for large operations  
3. **Clear Memory Appropriately**: Clean up error collections when done
4. **Cache Validation Results**: Avoid repeated expensive validation

This backend error handling system provides the foundation for reliable, transparent, and maintainable error management throughout the ClinXML application.