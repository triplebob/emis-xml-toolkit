"""
Standardized error handling for the EMIS XML Converter application.
Includes user-facing helpers for Streamlit UI.
"""

import logging
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from enum import Enum
from dataclasses import dataclass


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for better classification."""
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
    """Context information for errors."""
    operation: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    user_data: Optional[Dict[str, Any]] = None
    session_info: Optional[Dict[str, Any]] = None


@dataclass
class XMLParsingContext:
    """Specialised context for XML parsing errors."""
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
    """Result object for parsing operations that can succeed or fail."""
    success: bool
    data: Optional[Any] = None
    errors: Optional[list] = None
    warnings: Optional[list] = None
    context: Optional[XMLParsingContext] = None

    @classmethod
    def success_result(cls, data: Any) -> "ParseResult":
        return cls(success=True, data=data)

    @classmethod
    def failure_result(cls, errors: list, context: Optional[XMLParsingContext] = None) -> "ParseResult":
        return cls(success=False, errors=errors or [], context=context)

    @classmethod
    def partial_result(cls, data: Any, warnings: list, context: Optional[XMLParsingContext] = None) -> "ParseResult":
        return cls(success=True, data=data, warnings=warnings or [], context=context)

    def add_error(self, error: str):
        if self.errors is None:
            self.errors = []
        self.errors.append(error)
        self.success = False

    def add_warning(self, warning: str):
        if self.warnings is None:
            self.warnings = []
        self.warnings.append(warning)


class EMISConverterError(Exception):
    """Base exception class for EMIS Converter application."""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[ErrorContext] = None,
        original_exception: Optional[Exception] = None,
    ):
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context
        self.original_exception = original_exception
        super().__init__(self.message)

    def get_user_friendly_message(self) -> str:
        friendly_messages = {
            ErrorCategory.XML_PARSING: "There was an issue processing the XML file. Please check the file format and try again.",
            ErrorCategory.DATA_VALIDATION: "The data contains invalid or unexpected values. Please review your input.",
            ErrorCategory.FILE_OPERATION: "There was a problem accessing or saving files. Please check permissions and try again.",
            ErrorCategory.BUSINESS_LOGIC: "A business rule validation failed. Please review your search criteria.",
            ErrorCategory.UI_RENDERING: "There was a display issue. Please refresh the page and try again.",
            ErrorCategory.EXPORT_OPERATION: "Export failed. Please check your selections and try again.",
            ErrorCategory.TERMINOLOGY_SERVER: "NHS Terminology Server connection issue. Please check your credentials and connection.",
            ErrorCategory.SYSTEM: "A system error occurred. Please try again or contact support.",
        }
        return friendly_messages.get(self.category, self.message)

    def get_technical_details(self) -> Dict[str, Any]:
        details = {
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
        }

        if self.context:
            details["context"] = {
                "operation": self.context.operation,
                "file_path": self.context.file_path,
                "line_number": self.context.line_number,
            }

        if self.original_exception:
            details["original_exception"] = {
                "type": type(self.original_exception).__name__,
                "message": str(self.original_exception),
                "traceback": traceback.format_exc(),
            }

        return details


class XMLParsingError(EMISConverterError):
    """Specific error for XML parsing issues."""

    def __init__(self, message: str, element_name: str = None, xml_context: Optional[XMLParsingContext] = None, **kwargs):
        self.element_name = element_name
        self.xml_context = xml_context
        super().__init__(message=message, category=ErrorCategory.XML_PARSING, **kwargs)

    def get_technical_details(self) -> Dict[str, Any]:
        details = super().get_technical_details()

        if self.xml_context:
            details["xml_parsing_context"] = {
                "element_name": self.xml_context.element_name,
                "element_path": self.xml_context.element_path,
                "parent_element": self.xml_context.parent_element,
                "attribute_name": self.xml_context.attribute_name,
                "expected_format": self.xml_context.expected_format,
                "actual_value": self.xml_context.actual_value,
                "parsing_stage": self.xml_context.parsing_stage,
                "validation_rules": self.xml_context.validation_rules,
                "namespace_info": self.xml_context.namespace_info,
                "recovery_attempted": self.xml_context.recovery_attempted,
                "recovery_strategies": self.xml_context.recovery_strategies,
            }

        return details


class DataValidationError(EMISConverterError):
    """Specific error for data validation issues."""

    def __init__(self, message: str, field_name: str = None, value: Any = None, **kwargs):
        self.field_name = field_name
        self.value = value
        super().__init__(message=message, category=ErrorCategory.DATA_VALIDATION, **kwargs)


class FileOperationError(EMISConverterError):
    """Specific error for file operation issues."""

    def __init__(self, message: str, file_path: str = None, operation: str = None, **kwargs):
        self.file_path = file_path
        self.operation = operation
        super().__init__(message=message, category=ErrorCategory.FILE_OPERATION, **kwargs)


class ExportError(EMISConverterError):
    """Specific error for export operation issues."""

    def __init__(self, message: str, export_type: str = None, **kwargs):
        self.export_type = export_type
        super().__init__(message=message, category=ErrorCategory.EXPORT_OPERATION, **kwargs)


class TerminologyServerError(EMISConverterError):
    """Specific error for NHS Terminology Server operations."""

    def __init__(
        self,
        message: str,
        error_type: str = None,
        api_response: Optional[Dict] = None,
        user_guidance: Optional[str] = None,
        **kwargs,
    ):
        self.error_type = error_type
        self.api_response = api_response
        self.user_guidance = user_guidance
        super().__init__(message=message, category=ErrorCategory.TERMINOLOGY_SERVER, **kwargs)

    def get_user_friendly_message(self) -> str:
        if self.user_guidance:
            return self.user_guidance

        friendly_messages = {
            "authentication_failed": "Authentication with NHS Terminology Server failed. Please check your credentials.",
            "code_not_found": "The SNOMED code was not found in the NHS Terminology Server.",
            "invalid_code_format": "The SNOMED code format is invalid. Please check the code and try again.",
            "server_error": "The NHS Terminology Server is experiencing issues. Please try again later.",
            "rate_limit_exceeded": "Too many requests sent to the server. Please wait a moment and try again.",
            "connection_error": "Unable to connect to NHS Terminology Server. Please check your internet connection.",
            "timeout_error": "Request to NHS Terminology Server timed out. Please try again.",
            "insufficient_permissions": "Your account does not have permission to access this resource.",
            "malformed_response": "Received unexpected response from NHS Terminology Server. Please try again.",
            "expansion_limit_exceeded": "The concept has too many child codes to expand. Consider using filters.",
            "partial_failure": "Some child codes could not be retrieved. The partial results are shown below.",
            "batch_timeout": "The batch operation took too long and was stopped. Partial results may be available.",
        }

        return friendly_messages.get(
            self.error_type,
            "An error occurred while communicating with NHS Terminology Server. Please try again.",
        )

    def get_technical_details(self) -> Dict[str, Any]:
        details = super().get_technical_details()
        details.update(
            {
                "error_type": self.error_type,
                "api_response": self.api_response,
                "user_guidance": self.user_guidance,
            }
        )
        return details


class ErrorHandler:
    """Centralised error handling and logging."""

    def __init__(self, logger_name: str = "emis_converter"):
        self.logger = logging.getLogger(logger_name)
        self._setup_logger()
        self._error_count = 0
        self._warning_count = 0
        self._session_errors = []

    def _setup_logger(self):
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def handle_error(self, error: EMISConverterError) -> None:
        technical_details = error.get_technical_details()
        self._error_count += 1
        self._session_errors.append(
            {"timestamp": datetime.now().isoformat(), "error": error, "details": technical_details}
        )

        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(f"Critical error: {technical_details}")
        elif error.severity == ErrorSeverity.HIGH:
            self.logger.error(f"High severity error: {technical_details}")
        elif error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(f"Medium severity error: {technical_details}")
        else:
            self.logger.info(f"Low severity error: {technical_details}")

    def log_exception(
        self,
        operation: str,
        exception: Exception,
        context: Optional[ErrorContext] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    ) -> EMISConverterError:
        category = self._categorize_exception(exception)
        emis_error = EMISConverterError(
            message=f"Error in {operation}: {str(exception)}",
            category=category,
            severity=severity,
            context=context,
            original_exception=exception,
        )
        self.handle_error(emis_error)
        return emis_error

    def _categorize_exception(self, exception: Exception) -> ErrorCategory:
        exception_type = type(exception).__name__
        exception_module = type(exception).__module__

        if exception_type == "ParseError":
            if "xml.etree" in exception_module or "lxml" in exception_module:
                return ErrorCategory.XML_PARSING

        category_map = {
            "XMLSyntaxError": ErrorCategory.XML_PARSING,
            "FileNotFoundError": ErrorCategory.FILE_OPERATION,
            "PermissionError": ErrorCategory.FILE_OPERATION,
            "IsADirectoryError": ErrorCategory.FILE_OPERATION,
            "IOError": ErrorCategory.FILE_OPERATION,
            "OSError": ErrorCategory.FILE_OPERATION,
            "UnicodeDecodeError": ErrorCategory.FILE_OPERATION,
            "UnicodeEncodeError": ErrorCategory.FILE_OPERATION,
            "ValueError": ErrorCategory.DATA_VALIDATION,
            "TypeError": ErrorCategory.DATA_VALIDATION,
            "KeyError": ErrorCategory.DATA_VALIDATION,
            "AttributeError": ErrorCategory.SYSTEM,
            "ImportError": ErrorCategory.SYSTEM,
            "ModuleNotFoundError": ErrorCategory.SYSTEM,
            "MemoryError": ErrorCategory.SYSTEM,
        }

        return category_map.get(exception_type, ErrorCategory.SYSTEM)


def safe_execute(
    operation_name: str,
    func: Callable,
    *args,
    context: Optional[ErrorContext] = None,
    error_handler: Optional[ErrorHandler] = None,
    default_return=None,
    **kwargs,
) -> Any:
    """Safely execute a function with standardized error handling."""
    if error_handler is None:
        error_handler = ErrorHandler()

    try:
        return func(*args, **kwargs)
    except EMISConverterError as emis_error:
        error_handler.handle_error(emis_error)
        raise
    except Exception as e:
        emis_error = error_handler.log_exception(operation_name, e, context)
        if emis_error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            raise emis_error
        return default_return


def create_error_context(
    operation: str,
    file_path: str = None,
    line_number: int = None,
    **kwargs,
) -> ErrorContext:
    """Helper function to create error context."""
    return ErrorContext(
        operation=operation,
        file_path=file_path,
        line_number=line_number,
        user_data=kwargs.get("user_data"),
        session_info=kwargs.get("session_info"),
    )


def handle_xml_parsing_error(operation: str, exception: Exception, element_name: str = None) -> XMLParsingError:
    """Handle XML parsing errors with specific context."""
    return XMLParsingError(
        message=f"Failed to parse XML in {operation}: {str(exception)}",
        element_name=element_name,
        context=create_error_context(operation),
        original_exception=exception,
    )


def handle_file_operation_error(operation: str, file_path: str, exception: Exception) -> FileOperationError:
    """Handle file operation errors."""
    return FileOperationError(
        message=f"File operation '{operation}' failed: {str(exception)}",
        file_path=file_path,
        operation=operation,
        context=create_error_context(operation, file_path=file_path),
        original_exception=exception,
    )


# UI helpers (Streamlit)

def display_error_to_user(error: EMISConverterError, show_technical_details: bool = False) -> None:
    import streamlit as st
    from ..system.session_state import SessionStateKeys
    from ..ui.theme import info_box, warning_box, error_box

    user_message = error.get_user_friendly_message()

    if error.severity == ErrorSeverity.CRITICAL:
        st.markdown(error_box(f"🚨 **Critical Error:** {user_message}"), unsafe_allow_html=True)
    elif error.severity == ErrorSeverity.HIGH:
        st.markdown(error_box(f"❌ **Error:** {user_message}"), unsafe_allow_html=True)
    elif error.severity == ErrorSeverity.MEDIUM:
        st.markdown(warning_box(f"⚠️ **Warning:** {user_message}"), unsafe_allow_html=True)
    else:
        st.markdown(info_box(f"ℹ️ **Notice:** {user_message}"), unsafe_allow_html=True)

    if show_technical_details and st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        with st.expander("🔧 Technical Details", expanded=False):
            st.json(error.get_technical_details())


def display_generic_error(message: str, error_type: str = "error", icon: str = "❌") -> None:
    import streamlit as st
    from ..ui.theme import info_box, warning_box, error_box

    full_message = f"{icon} {message}"

    if error_type == "error":
        st.markdown(error_box(full_message), unsafe_allow_html=True)
    elif error_type == "warning":
        st.markdown(warning_box(full_message), unsafe_allow_html=True)
    elif error_type == "info":
        st.markdown(info_box(full_message), unsafe_allow_html=True)
    else:
        st.markdown(error_box(full_message), unsafe_allow_html=True)


def streamlit_safe_execute(
    operation_name: str,
    func: Callable,
    *args,
    show_error_to_user: bool = True,
    show_technical_details: bool = None,
    default_return=None,
    error_message_override: str = None,
    **kwargs,
) -> Any:
    import streamlit as st
    from ..system.session_state import SessionStateKeys

    error_handler = ErrorHandler()

    try:
        return func(*args, **kwargs)
    except EMISConverterError as e:
        error_handler.handle_error(e)
        if show_error_to_user:
            if error_message_override:
                display_generic_error(error_message_override)
            else:
                if show_technical_details is None:
                    show_technical_details = st.session_state.get(SessionStateKeys.DEBUG_MODE, False)
                display_error_to_user(e, show_technical_details)
        return default_return
    except Exception as e:
        context = create_error_context(operation_name)
        emis_error = error_handler.log_exception(operation_name, e, context)
        if show_error_to_user:
            if error_message_override:
                display_generic_error(error_message_override)
            else:
                if show_technical_details is None:
                    show_technical_details = st.session_state.get(SessionStateKeys.DEBUG_MODE, False)
                display_error_to_user(emis_error, show_technical_details)
        return default_return
