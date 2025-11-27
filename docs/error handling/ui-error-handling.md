# UI Error Handling - Technical Guide

## Overview

The UI error handling system (`utils/common/ui_error_handling.py`) provides Streamlit-specific error display, user interaction, and recovery mechanisms. This system bridges the gap between the backend error handling infrastructure and user-facing error presentation, ensuring consistent, accessible, and actionable error displays throughout the ClinXML application.

## Core Components

### Error Display Functions

#### Primary Display Function
```python
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
        st.markdown(error_box(f"🚨 **Critical Error:** {user_message}"), unsafe_allow_html=True)
    elif error.severity == ErrorSeverity.HIGH:
        st.markdown(error_box(f"❌ **Error:** {user_message}"), unsafe_allow_html=True)
    elif error.severity == ErrorSeverity.MEDIUM:
        st.markdown(warning_box(f"⚠️ **Warning:** {user_message}"), unsafe_allow_html=True)
    else:
        st.markdown(info_box(f"ℹ️ **Notice:** {user_message}"), unsafe_allow_html=True)
    
    # Show technical details if requested and debug mode enabled
    if show_technical_details and st.session_state.get(SessionStateKeys.DEBUG_MODE, False):
        with st.expander("🔧 Technical Details", expanded=False):
            technical_details = error.get_technical_details()
            st.json(technical_details)
```

#### Generic Error Display
```python
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
        st.markdown(error_box(full_message), unsafe_allow_html=True)
    elif error_type == "warning":
        st.markdown(warning_box(full_message), unsafe_allow_html=True)
    elif error_type == "info":
        st.markdown(info_box(full_message), unsafe_allow_html=True)
```

### Safe Execution in Streamlit Context

#### Streamlit-Specific Safe Execute
```python
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
        show_error_to_user: Whether to display error to user
        show_technical_details: Whether to show technical details (None = auto-detect debug mode)
        default_return: Value to return on error
        error_message_override: Custom error message to show user
        
    Returns:
        Function result or default_return on error
    """
    error_handler = ErrorHandler()
    
    try:
        return func(*args, **kwargs)
    except EMISConverterError as e:
        # Handle structured errors
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
        # Convert and handle generic exceptions
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
```

## User Experience Features

### Error Recovery Suggestions

#### Recovery Section Creation
```python
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
```

#### Category-Specific Recovery Actions
```python
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
```

### User Feedback and Reporting

#### Error Feedback Form
```python
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
            value=f"Error Category: {error.category.value}\\n"
                  f"Severity: {error.severity.value}\\n"
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
            # Error reporting implementation would go here
            st.markdown(success_box("Thank you for your feedback! We'll investigate this issue."), unsafe_allow_html=True)
```

## Session State Integration

### Error State Management

#### Storing Errors for Later Display
```python
def store_error_for_display(error: EMISConverterError):
    """Store an error in session state for later display"""
    if 'pending_errors' not in st.session_state:
        st.session_state[SessionStateKeys.PENDING_ERRORS] = []
    
    st.session_state[SessionStateKeys.PENDING_ERRORS].append(error)

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
```

## Error Boundaries and Decorators

### Error Boundary Decorator
```python
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
```

## Convenience Functions for Common Scenarios

### Specialised Error Display Functions
```python
def show_xml_parse_error(operation: str, details: str = None):
    """Show a standardised XML parsing error"""
    message = f"Failed to parse XML during {operation}"
    if details:
        message += f": {details}"
    display_generic_error(message, "error", "📄")

def show_file_error(operation: str, filename: str = None):
    """Show a standardised file operation error"""
    message = f"File operation failed during {operation}"
    if filename:
        message += f" for file: {filename}"
    display_generic_error(message, "error", "📁")

def show_validation_error(field: str, issue: str = None):
    """Show a standardised validation error"""
    message = f"Validation failed for {field}"
    if issue:
        message += f": {issue}"
    display_generic_error(message, "warning", "⚠️")

def show_export_error(export_type: str, details: str = None):
    """Show a standardised export error"""
    message = f"Export failed for {export_type}"
    if details:
        message += f": {details}"
    display_generic_error(message, "error", "📤")
```

## Theme Integration

### Consistent Visual Styling

The UI error handling system integrates with the theme system to ensure consistent visual presentation:

```python
from ..ui.theme import info_box, success_box, warning_box, error_box

# Severity-based styling mapping
def get_theme_function(severity: ErrorSeverity):
    """Get appropriate theme function based on error severity"""
    theme_map = {
        ErrorSeverity.CRITICAL: error_box,    # Red, urgent styling
        ErrorSeverity.HIGH: error_box,        # Red, error styling
        ErrorSeverity.MEDIUM: warning_box,    # Orange, warning styling  
        ErrorSeverity.LOW: info_box          # Blue, informational styling
    }
    return theme_map.get(severity, error_box)
```

### Custom Error Styling
```python
def display_critical_system_error(message: str):
    """Display critical system errors with enhanced styling"""
    st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #ff4444, #cc0000);
            color: white;
            padding: 20px;
            border-radius: 10px;
            border-left: 5px solid #990000;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin: 10px 0;
        ">
            <h3 style="margin:0; color: white;">🚨 Critical System Error</h3>
            <p style="margin: 10px 0 0 0; color: white;">{message}</p>
        </div>
    """, unsafe_allow_html=True)
```

## Implementation Patterns

### Basic UI Error Handling
```python
from utils.common.ui_error_handling import display_error_to_user, streamlit_safe_execute
from utils.common.error_handling import handle_xml_parsing_error

def render_xml_processing_tab():
    """Example tab rendering with error handling"""
    
    # Safe execution with automatic error display
    def process_xml():
        # XML processing logic that might fail
        if not validate_xml_structure():
            raise ValueError("XML structure validation failed")
        return process_xml_content()
    
    result = streamlit_safe_execute(
        "xml_processing",
        process_xml,
        show_error_to_user=True,
        show_technical_details=True,  # Show details in debug mode
        default_return=None
    )
    
    if result:
        st.success("XML processing completed successfully")
        display_results(result)
```

### Error Boundary Implementation
```python
@with_error_boundary(
    "tab_rendering", 
    show_recovery=True,
    show_feedback=True
)
def render_complex_tab():
    """Tab rendering with comprehensive error boundary"""
    
    # Complex rendering logic that might fail
    data = load_complex_data()
    processed_data = transform_data(data)
    render_data_visualization(processed_data)
```

### Manual Error Display with Recovery
```python
def handle_file_upload_error(e: Exception, filename: str):
    """Handle file upload errors with recovery suggestions"""
    
    # Convert to structured error
    file_error = handle_file_operation_error("file upload", filename, e)
    
    # Display with custom recovery actions
    display_error_to_user(file_error)
    create_error_recovery_section(file_error, recovery_actions=[
        f"Check that {filename} is not corrupted",
        "Try uploading a different file to test",
        "Ensure the file is a valid XML format",
        "Contact support if this file previously worked"
    ])
```

### Session State Error Management
```python
def handle_background_processing_error(error: EMISConverterError):
    """Handle errors from background processing"""
    
    # Store error for display on next UI update
    store_error_for_display(error)
    
    # Trigger UI refresh to show error
    st.rerun()

def check_for_pending_errors():
    """Check for errors at start of page rendering"""
    # Call this at the beginning of main page rendering
    check_session_state_errors()
```

## Integration with Base Components

### Tab Error Handling
```python
class BaseTab:
    def _handle_error(self, error: Exception, context: str = "processing") -> None:
        """Standardised error handling for tabs using structured UI error handling"""
        
        # Create error context with tab information
        error_context = create_error_context(
            operation=f"tab_{context}",
            user_data={"tab_type": self.__class__.__name__}
        )
        
        # Convert to structured error
        error_handler = ErrorHandler(f"tab_{self.__class__.__name__}")
        structured_error = error_handler.log_exception(
            f"tab {context}",
            error,
            error_context,
            ErrorSeverity.MEDIUM
        )
        
        # Display with UI error handling
        display_error_to_user(structured_error, show_technical_details=True)
        
        # Add tab-specific recovery suggestions
        create_error_recovery_section(
            structured_error,
            recovery_actions=[
                "Refresh the page to reload the tab",
                "Check that all required data is properly loaded",
                "Try switching to a different tab and back",
                "Clear browser cache if the issue persists"
            ]
        )
```

## Testing UI Error Handling

### Unit Tests for Error Display
```python
import streamlit as st
import pytest
from unittest.mock import patch, MagicMock
from utils.common.ui_error_handling import display_error_to_user, display_generic_error
from utils.common.error_handling import EMISConverterError, ErrorCategory, ErrorSeverity

def test_display_error_severity_styling():
    """Test that different severities use appropriate styling"""
    
    # Mock Streamlit markdown function
    with patch('streamlit.markdown') as mock_markdown:
        # Critical error should use error_box
        critical_error = EMISConverterError(
            "Critical test error", 
            severity=ErrorSeverity.CRITICAL
        )
        display_error_to_user(critical_error)
        
        # Check that error_box styling was used with critical formatting
        call_args = mock_markdown.call_args[0][0]
        assert "🚨" in call_args
        assert "Critical Error" in call_args

def test_display_generic_error_types():
    """Test generic error display with different types"""
    
    with patch('streamlit.markdown') as mock_markdown:
        # Test error type
        display_generic_error("Test error message", error_type="error", icon="❌")
        assert mock_markdown.called
        
        # Test warning type  
        display_generic_error("Test warning message", error_type="warning", icon="⚠️")
        assert mock_markdown.call_count == 2

def test_error_boundary_decorator():
    """Test error boundary decorator functionality"""
    
    @with_error_boundary("test_operation", show_recovery=True)
    def failing_function():
        raise ValueError("Test error")
    
    with patch('utils.common.ui_error_handling.display_error_to_user') as mock_display:
        with patch('utils.common.ui_error_handling.create_error_recovery_section') as mock_recovery:
            failing_function()
            
            # Verify error was displayed and recovery section was shown
            assert mock_display.called
            assert mock_recovery.called
```

### Integration Tests
```python
def test_tab_error_handling_integration():
    """Test error handling integration in tab components"""
    
    from utils.ui.tabs.base_tab import BaseTab
    
    class TestTab(BaseTab):
        def render(self):
            # Simulate tab rendering that might fail
            raise Exception("Test tab rendering error")
    
    tab = TestTab()
    
    with patch('utils.common.ui_error_handling.display_error_to_user') as mock_display:
        tab._handle_error(Exception("Test error"), "test_context")
        
        # Verify structured error handling was used
        assert mock_display.called
        # Verify error was properly categorised
        error_arg = mock_display.call_args[0][0]
        assert hasattr(error_arg, 'category')
        assert hasattr(error_arg, 'severity')
```

## Best Practices

### Error Display Guidelines
1. **Use Appropriate Severity**: Match visual styling to error impact
2. **Provide Clear Messages**: Use user-friendly language, avoid technical jargon
3. **Include Recovery Actions**: Always suggest next steps for users
4. **Respect Debug Mode**: Only show technical details when appropriate
5. **Maintain Consistency**: Use standardised display functions across components

### User Experience Considerations
1. **Progressive Disclosure**: Start with simple message, provide details on request
2. **Actionable Guidance**: Focus on what users can do to resolve issues
3. **Visual Hierarchy**: Use icons and styling to communicate severity
4. **Context Preservation**: Maintain user's place in the application workflow
5. **Feedback Opportunities**: Provide ways for users to report persistent issues

### Performance Guidelines
1. **Lazy Error Details**: Only generate expensive diagnostic information when needed
2. **Session State Management**: Clean up stored errors appropriately
3. **Efficient Recovery Suggestions**: Cache common recovery action lists
4. **Theme Integration**: Use consistent theming without performance overhead

This UI error handling system provides a comprehensive, user-friendly interface layer that makes the backend error handling infrastructure accessible and actionable for end users while maintaining the technical depth needed for debugging and system maintenance.