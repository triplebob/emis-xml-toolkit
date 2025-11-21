"""
UI-specific error handling for Streamlit applications
Provides user-friendly error display and recovery mechanisms
"""

import streamlit as st
from typing import Optional, Callable, Any
from ..core.session_state import SessionStateKeys
from .error_handling import (
    EMISConverterError, ErrorSeverity, ErrorCategory,
    ErrorHandler, safe_execute, create_error_context
)


def display_error_to_user(error: EMISConverterError, 
                         show_technical_details: bool = False) -> None:
    """
    Display error to user in Streamlit with appropriate styling
    
    Args:
        error: The EMISConverterError to display
        show_technical_details: Whether to show technical details in expandable section
    """
    user_message = error.get_user_friendly_message()
    
    # Choose appropriate Streamlit display method based on severity
    if error.severity == ErrorSeverity.CRITICAL:
        st.error(f"🚨 **Critical Error:** {user_message}")
    elif error.severity == ErrorSeverity.HIGH:
        st.error(f"❌ **Error:** {user_message}")
    elif error.severity == ErrorSeverity.MEDIUM:
        st.warning(f"⚠️ **Warning:** {user_message}")
    else:
        st.info(f"ℹ️ **Notice:** {user_message}")
    
    # Show technical details if requested
    if show_technical_details and st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        with st.expander("🔧 Technical Details", expanded=False):
            technical_details = error.get_technical_details()
            st.json(technical_details)


def display_generic_error(message: str, 
                         error_type: str = "error",
                         icon: str = "❌") -> None:
    """
    Display a generic error message with consistent styling
    
    Args:
        message: Error message to display
        error_type: Type of error display ('error', 'warning', 'info')
        icon: Icon to display with the message
    """
    full_message = f"{icon} {message}"
    
    if error_type == "error":
        st.error(full_message)
    elif error_type == "warning":
        st.warning(full_message)
    elif error_type == "info":
        st.info(full_message)
    else:
        st.error(full_message)


def streamlit_safe_execute(operation_name: str,
                          func: Callable,
                          *args,
                          show_error_to_user: bool = True,
                          show_technical_details: bool = None,
                          default_return=None,
                          error_message_override: str = None,
                          **kwargs) -> Any:
    """
    Execute a function safely in Streamlit context with user-friendly error display
    
    Args:
        operation_name: Name of operation for logging
        func: Function to execute
        *args: Function arguments
        show_error_to_user: Whether to display error to user
        show_technical_details: Whether to show technical details (None = auto-detect debug mode)
        default_return: Value to return on error
        error_message_override: Custom error message to show user
        **kwargs: Function keyword arguments
        
    Returns:
        Function result or default_return on error
    """
    error_handler = ErrorHandler()
    
    try:
        return func(*args, **kwargs)
    except EMISConverterError as e:
        # Handle our custom errors
        error_handler.handle_error(e)
        
        if show_error_to_user:
            if error_message_override:
                display_generic_error(error_message_override)
            else:
                # Auto-detect debug mode if not specified
                if show_technical_details is None:
                    show_technical_details = st.session_state.get(SessionStateKeys.DEBUG_MODE, False)
                
                display_error_to_user(e, show_technical_details)
        
        return default_return
    except Exception as e:
        # Convert generic exceptions
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


def create_error_recovery_section(error: EMISConverterError,
                                 recovery_actions: list = None) -> None:
    """
    Create a section with error recovery suggestions
    
    Args:
        error: The error that occurred
        recovery_actions: List of suggested recovery actions
    """
    if not recovery_actions:
        recovery_actions = _get_default_recovery_actions(error.category)
    
    if recovery_actions:
        st.markdown("### 🔄 Suggested Actions:")
        for i, action in enumerate(recovery_actions, 1):
            st.markdown(f"{i}. {action}")


def _get_default_recovery_actions(category: ErrorCategory) -> list:
    """Get default recovery actions for different error categories"""
    recovery_map = {
        ErrorCategory.XML_PARSING: [
            "Check that the uploaded file is a valid XML file",
            "Ensure the XML file is not corrupted",
            "Try uploading a different XML file",
            "Contact support if the issue persists"
        ],
        ErrorCategory.DATA_VALIDATION: [
            "Review your input data for invalid values",
            "Check that all required fields are filled",
            "Ensure data formats match expected patterns",
            "Try with a smaller dataset to isolate the issue"
        ],
        ErrorCategory.FILE_OPERATION: [
            "Check file permissions and access rights",
            "Ensure sufficient disk space is available",
            "Try saving to a different location",
            "Close any programs that might be using the file"
        ],
        ErrorCategory.EXPORT_OPERATION: [
            "Check your export settings and selections",
            "Ensure you have write permissions to the target location",
            "Try a different export format",
            "Reduce the amount of data being exported"
        ],
        ErrorCategory.UI_RENDERING: [
            "Refresh the page and try again",
            "Clear your browser cache",
            "Try using a different browser",
            "Check your internet connection"
        ],
        ErrorCategory.BUSINESS_LOGIC: [
            "Review your search criteria and parameters",
            "Check for conflicting rules or constraints",
            "Ensure all required dependencies are met",
            "Consult the documentation for proper usage"
        ],
        ErrorCategory.SYSTEM: [
            "Try refreshing the page",
            "Wait a moment and try again",
            "Check your internet connection",
            "Contact support if the issue persists"
        ]
    }
    
    return recovery_map.get(category, [
        "Try the operation again",
        "Contact support if the issue persists"
    ])


def create_error_feedback_form(error: EMISConverterError) -> None:
    """
    Create a feedback form for users to report errors
    
    Args:
        error: The error that occurred
    """
    with st.expander("📝 Report This Issue", expanded=False):
        st.markdown("Help us improve by reporting this issue:")
        
        # Error details (read-only)
        st.text_area(
            "Error Details (automatically filled)",
            value=f"Error Category: {error.category.value}\n"
                  f"Severity: {error.severity.value}\n"
                  f"Message: {error.message}",
            height=100,
            disabled=True
        )
        
        # User input
        user_description = st.text_area(
            "What were you trying to do when this error occurred?",
            placeholder="Please describe the steps you took..."
        )
        
        user_email = st.text_input(
            "Email (optional, for follow-up)",
            placeholder="your.email@example.com"
        )
        
        if st.button("Submit Error Report"):
            # Here you would implement actual error reporting
            # For now, just show a success message
            st.success("Thank you for your feedback! We'll investigate this issue.")


def with_error_boundary(operation_name: str,
                       error_message: str = None,
                       show_recovery: bool = True,
                       show_feedback: bool = False):
    """
    Decorator for wrapping Streamlit functions with error boundaries
    
    Args:
        operation_name: Name of the operation
        error_message: Custom error message to display
        show_recovery: Whether to show recovery suggestions
        show_feedback: Whether to show feedback form
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except EMISConverterError as e:
                display_error_to_user(e)
                
                if show_recovery:
                    create_error_recovery_section(e)
                
                if show_feedback:
                    create_error_feedback_form(e)
                    
            except Exception as e:
                error_handler = ErrorHandler()
                context = create_error_context(operation_name)
                emis_error = error_handler.log_exception(operation_name, e, context)
                
                if error_message:
                    display_generic_error(error_message)
                else:
                    display_error_to_user(emis_error)
                
                if show_recovery:
                    create_error_recovery_section(emis_error)
                
                if show_feedback:
                    create_error_feedback_form(emis_error)
        
        return wrapper
    return decorator


def check_session_state_errors():
    """Check for any errors stored in session state and display them"""
    if 'pending_errors' in st.session_state:
        errors = st.session_state[SessionStateKeys.PENDING_ERRORS]
        for error in errors:
            if isinstance(error, EMISConverterError):
                display_error_to_user(error)
            else:
                display_generic_error(str(error))
        
        # Clear the errors after displaying
        del st.session_state[SessionStateKeys.PENDING_ERRORS]


def store_error_for_display(error: EMISConverterError):
    """Store an error in session state for later display"""
    if 'pending_errors' not in st.session_state:
        st.session_state[SessionStateKeys.PENDING_ERRORS] = []
    
    st.session_state[SessionStateKeys.PENDING_ERRORS].append(error)


# Common error display functions for frequent use cases
def show_xml_parse_error(operation: str, details: str = None):
    """Show a standardized XML parsing error"""
    message = f"Failed to parse XML during {operation}"
    if details:
        message += f": {details}"
    display_generic_error(message, "error", "📄")


def show_file_error(operation: str, filename: str = None):
    """Show a standardized file operation error"""
    message = f"File operation failed during {operation}"
    if filename:
        message += f" for file: {filename}"
    display_generic_error(message, "error", "📁")


def show_validation_error(field: str, issue: str = None):
    """Show a standardized validation error"""
    message = f"Validation failed for {field}"
    if issue:
        message += f": {issue}"
    display_generic_error(message, "warning", "⚠️")


def show_export_error(export_type: str, details: str = None):
    """Show a standardized export error"""
    message = f"Export failed for {export_type}"
    if details:
        message += f": {details}"
    display_generic_error(message, "error", "📤")
