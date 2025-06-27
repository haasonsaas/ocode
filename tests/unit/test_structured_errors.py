"""
Tests for structured error classes.
"""

import asyncio
from datetime import datetime

from ocode_python.utils.structured_errors import (
    AuthenticationError,
    ConfigurationError,
    ErrorCategory,
    ErrorContext,
    ErrorSeverity,
    ExecutionError,
    FileSystemError,
    NetworkError,
    ParsingError,
    PermissionError,
    ResourceError,
    StructuredError,
    TimeoutError,
    ValidationError,
    create_error_from_exception,
    format_error_for_user,
)


class TestErrorEnums:
    """Test error enumeration classes."""

    def test_error_severity_values(self):
        """Test ErrorSeverity enum values."""
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.MEDIUM.value == "medium"
        assert ErrorSeverity.HIGH.value == "high"
        assert ErrorSeverity.CRITICAL.value == "critical"

    def test_error_category_values(self):
        """Test ErrorCategory enum values."""
        assert ErrorCategory.VALIDATION.value == "validation"
        assert ErrorCategory.PERMISSION.value == "permission"
        assert ErrorCategory.NETWORK.value == "network"
        assert ErrorCategory.FILE_SYSTEM.value == "file_system"
        assert ErrorCategory.PARSING.value == "parsing"
        assert ErrorCategory.TIMEOUT.value == "timeout"
        assert ErrorCategory.AUTHENTICATION.value == "authentication"
        assert ErrorCategory.CONFIGURATION.value == "configuration"
        assert ErrorCategory.RESOURCE.value == "resource"
        assert ErrorCategory.EXECUTION.value == "execution"
        assert ErrorCategory.UNKNOWN.value == "unknown"


class TestErrorContext:
    """Test ErrorContext class."""

    def test_basic_context_creation(self):
        """Test basic error context creation."""
        context = ErrorContext(operation="test_operation", component="test_component")

        assert context.operation == "test_operation"
        assert context.component == "test_component"
        assert context.details == {}
        assert context.user_data == {}
        assert isinstance(context.timestamp, datetime)

    def test_context_with_details(self):
        """Test error context with details and user data."""
        details = {"key": "value", "number": 42}
        user_data = {"user_input": "test"}

        context = ErrorContext(
            operation="test_operation",
            component="test_component",
            details=details,
            user_data=user_data,
        )

        assert context.details == details
        assert context.user_data == user_data

    def test_context_to_dict(self):
        """Test converting context to dictionary."""
        context = ErrorContext(
            operation="test_operation",
            component="test_component",
            details={"test": "data"},
            user_data={"input": "value"},
        )

        result = context.to_dict()

        assert result["operation"] == "test_operation"
        assert result["component"] == "test_component"
        assert result["details"] == {"test": "data"}
        assert result["user_data"] == {"input": "value"}
        assert "timestamp" in result


class TestStructuredError:
    """Test base StructuredError class."""

    def test_basic_error_creation(self):
        """Test basic structured error creation."""
        error = StructuredError("Test error message")

        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.category == ErrorCategory.UNKNOWN
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.context is None
        assert error.original_error is None
        assert error.suggestions == []
        assert error.error_code is None

    def test_error_with_all_parameters(self):
        """Test structured error with all parameters."""
        context = ErrorContext("test_op", "test_component")
        original = ValueError("original error")
        suggestions = ["Try this", "Try that"]

        error = StructuredError(
            message="Test error",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.HIGH,
            context=context,
            original_error=original,
            suggestions=suggestions,
            error_code="ERR001",
        )

        assert error.category == ErrorCategory.VALIDATION
        assert error.severity == ErrorSeverity.HIGH
        assert error.context is context
        assert error.original_error is original
        assert error.suggestions == suggestions
        assert error.error_code == "ERR001"

    def test_error_to_dict(self):
        """Test converting error to dictionary."""
        context = ErrorContext("test_op", "test_component")
        error = StructuredError(
            message="Test error",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.HIGH,
            context=context,
            suggestions=["Fix this"],
            error_code="ERR001",
        )

        result = error.to_dict()

        assert result["type"] == "StructuredError"
        assert result["message"] == "Test error"
        assert result["category"] == "validation"
        assert result["severity"] == "high"
        assert result["context"]["operation"] == "test_op"
        assert result["suggestions"] == ["Fix this"]
        assert result["error_code"] == "ERR001"

    def test_get_debug_info(self):
        """Test getting debug information."""
        context = ErrorContext(
            "test_operation", "test_component", details={"detail_key": "detail_value"}
        )
        error = StructuredError(
            message="Test error",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.HIGH,
            context=context,
            suggestions=["Try this", "Try that"],
            error_code="ERR001",
        )

        debug_info = error.get_debug_info()

        assert "Error: StructuredError" in debug_info
        assert "Message: Test error" in debug_info
        assert "Category: validation" in debug_info
        assert "Severity: high" in debug_info
        assert "Code: ERR001" in debug_info
        assert "Operation: test_operation" in debug_info
        assert "Component: test_component" in debug_info
        assert "detail_key: detail_value" in debug_info
        assert "• Try this" in debug_info
        assert "• Try that" in debug_info


class TestSpecificErrorClasses:
    """Test specific error class implementations."""

    def test_validation_error(self):
        """Test ValidationError class."""
        error = ValidationError(
            message="Invalid input",
            field_name="email",
            field_value="invalid-email",
            expected_type="email address",
        )

        assert error.category == ErrorCategory.VALIDATION
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.field_name == "email"
        assert error.field_value == "invalid-email"
        assert error.expected_type == "email address"

    def test_permission_error(self):
        """Test PermissionError class."""
        error = PermissionError(
            message="Access denied",
            resource_path="/protected/file.txt",
            required_permission="read",
        )

        assert error.category == ErrorCategory.PERMISSION
        assert error.severity == ErrorSeverity.HIGH
        assert error.resource_path == "/protected/file.txt"
        assert error.required_permission == "read"

    def test_network_error(self):
        """Test NetworkError class."""
        error = NetworkError(
            message="Connection failed",
            url="https://api.example.com",
            status_code=404,
            retry_count=3,
        )

        assert error.category == ErrorCategory.NETWORK
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.url == "https://api.example.com"
        assert error.status_code == 404
        assert error.retry_count == 3

    def test_file_system_error(self):
        """Test FileSystemError class."""
        error = FileSystemError(
            message="File not found",
            file_path="/path/to/file.txt",
            operation_type="read",
        )

        assert error.category == ErrorCategory.FILE_SYSTEM
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.file_path == "/path/to/file.txt"
        assert error.operation_type == "read"

    def test_parsing_error(self):
        """Test ParsingError class."""
        error = ParsingError(
            message="Invalid JSON", data_format="json", line_number=5, column_number=12
        )

        assert error.category == ErrorCategory.PARSING
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.data_format == "json"
        assert error.line_number == 5
        assert error.column_number == 12

    def test_timeout_error(self):
        """Test TimeoutError class."""
        error = TimeoutError(
            message="Operation timed out",
            timeout_duration=30.0,
            operation_name="api_call",
        )

        assert error.category == ErrorCategory.TIMEOUT
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.timeout_duration == 30.0
        assert error.operation_name == "api_call"

    def test_authentication_error(self):
        """Test AuthenticationError class."""
        error = AuthenticationError(
            message="Authentication failed",
            auth_method="bearer_token",
            provider="github",
        )

        assert error.category == ErrorCategory.AUTHENTICATION
        assert error.severity == ErrorSeverity.HIGH
        assert error.auth_method == "bearer_token"
        assert error.provider == "github"

    def test_configuration_error(self):
        """Test ConfigurationError class."""
        error = ConfigurationError(
            message="Missing configuration",
            config_key="api_key",
            config_file="config.yaml",
        )

        assert error.category == ErrorCategory.CONFIGURATION
        assert error.severity == ErrorSeverity.HIGH
        assert error.config_key == "api_key"
        assert error.config_file == "config.yaml"

    def test_resource_error(self):
        """Test ResourceError class."""
        error = ResourceError(
            message="Memory limit exceeded",
            resource_type="memory",
            current_usage=1024,
            limit=512,
        )

        assert error.category == ErrorCategory.RESOURCE
        assert error.severity == ErrorSeverity.HIGH
        assert error.resource_type == "memory"
        assert error.current_usage == 1024
        assert error.limit == 512

    def test_execution_error(self):
        """Test ExecutionError class."""
        error = ExecutionError(
            message="Command failed",
            command="ls /nonexistent",
            exit_code=2,
            stdout="",
            stderr="ls: /nonexistent: No such file or directory",
        )

        assert error.category == ErrorCategory.EXECUTION
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.command == "ls /nonexistent"
        assert error.exit_code == 2
        assert error.stdout == ""
        assert "No such file or directory" in error.stderr


class TestErrorCreationFromException:
    """Test creating structured errors from standard exceptions."""

    def test_file_not_found_error(self):
        """Test creating error from FileNotFoundError."""
        original = FileNotFoundError("No such file: test.txt")
        original.filename = "test.txt"

        error = create_error_from_exception(original, "read_file", "file_tool")

        assert isinstance(error, FileSystemError)
        assert error.file_path == "test.txt"
        assert error.operation_type == "read"
        assert error.original_error is original

    def test_permission_error(self):
        """Test creating error from PermissionError."""
        original = PermissionError("Permission denied")
        original.filename = "/protected/file.txt"

        error = create_error_from_exception(original, "write_file", "file_tool")

        assert isinstance(error, PermissionError)
        assert error.resource_path == "/protected/file.txt"
        assert error.original_error is original

    def test_connection_error(self):
        """Test creating error from ConnectionError."""
        original = ConnectionError("Network unreachable")

        error = create_error_from_exception(original, "http_request", "curl_tool")

        assert isinstance(error, NetworkError)
        assert error.original_error is original

    def test_value_error(self):
        """Test creating error from ValueError."""
        original = ValueError("Invalid input format")

        error = create_error_from_exception(original, "parse_input", "parser")

        assert isinstance(error, ValidationError)
        assert error.original_error is original

    def test_timeout_error(self):
        """Test creating error from TimeoutError."""
        original = TimeoutError("Operation timed out")

        error = create_error_from_exception(original, "long_operation", "worker")

        assert isinstance(error, TimeoutError)
        assert error.original_error is original

    def test_asyncio_timeout_error(self):
        """Test creating error from asyncio.TimeoutError."""
        original = asyncio.TimeoutError()

        error = create_error_from_exception(original, "async_operation", "async_worker")

        assert isinstance(error, TimeoutError)
        assert error.original_error is original

    def test_unknown_exception(self):
        """Test creating error from unknown exception type."""
        original = RuntimeError("Something went wrong")

        error = create_error_from_exception(
            original, "unknown_operation", "unknown_component"
        )

        assert isinstance(error, StructuredError)
        assert error.category == ErrorCategory.UNKNOWN
        assert error.original_error is original

    def test_error_with_additional_context(self):
        """Test creating error with additional context."""
        original = ValueError("Invalid input")
        additional_context = {"input_value": "test", "expected_format": "json"}

        error = create_error_from_exception(
            original, "validate_input", "validator", additional_context
        )

        assert error.context.details == additional_context


class TestErrorFormatting:
    """Test error formatting for user display."""

    def test_format_basic_error(self):
        """Test formatting basic error."""
        context = ErrorContext("test_operation", "test_component")
        error = StructuredError("Something went wrong", context=context)

        formatted = format_error_for_user(error)

        assert "❌ Something went wrong" in formatted
        assert "Operation: test_operation" in formatted

    def test_format_file_system_error(self):
        """Test formatting FileSystemError."""
        context = ErrorContext("read_file", "file_tool")
        error = FileSystemError(
            "File not found", file_path="/path/to/file.txt", context=context
        )

        formatted = format_error_for_user(error)

        assert "❌ File not found" in formatted
        assert "Operation: read_file" in formatted
        assert "File: /path/to/file.txt" in formatted

    def test_format_network_error(self):
        """Test formatting NetworkError."""
        context = ErrorContext("http_request", "curl_tool")
        error = NetworkError(
            "Request failed",
            url="https://api.example.com",
            status_code=404,
            context=context,
        )

        formatted = format_error_for_user(error)

        assert "❌ Request failed" in formatted
        assert "Operation: http_request" in formatted
        assert "URL: https://api.example.com" in formatted
        assert "Status Code: 404" in formatted

    def test_format_validation_error(self):
        """Test formatting ValidationError."""
        context = ErrorContext("validate_input", "validator")
        error = ValidationError(
            "Invalid email format", field_name="email", context=context
        )

        formatted = format_error_for_user(error)

        assert "❌ Invalid email format" in formatted
        assert "Operation: validate_input" in formatted
        assert "Field: email" in formatted

    def test_format_error_with_suggestions(self):
        """Test formatting error with suggestions."""
        context = ErrorContext("operation", "component")
        error = StructuredError(
            "Something failed",
            context=context,
            suggestions=[
                "Check your configuration",
                "Verify your permissions",
                "Try again later",
            ],
        )

        formatted = format_error_for_user(error)

        assert "Suggestions:" in formatted
        assert "• Check your configuration" in formatted
        assert "• Verify your permissions" in formatted
        assert "• Try again later" in formatted

    def test_format_error_without_context(self):
        """Test formatting error without context."""
        error = StructuredError("Simple error message")

        formatted = format_error_for_user(error)

        assert formatted == "❌ Simple error message"


class TestErrorInheritance:
    """Test error class inheritance and behavior."""

    def test_all_errors_inherit_from_structured_error(self):
        """Test that all specific errors inherit from StructuredError."""
        error_classes = [
            ValidationError,
            PermissionError,
            NetworkError,
            FileSystemError,
            ParsingError,
            TimeoutError,
            AuthenticationError,
            ConfigurationError,
            ResourceError,
            ExecutionError,
        ]

        for error_class in error_classes:
            error = error_class("Test message")
            assert isinstance(error, StructuredError)
            assert isinstance(error, Exception)

    def test_errors_have_correct_categories(self):
        """Test that errors have correct default categories."""
        category_mappings = {
            ValidationError: ErrorCategory.VALIDATION,
            PermissionError: ErrorCategory.PERMISSION,
            NetworkError: ErrorCategory.NETWORK,
            FileSystemError: ErrorCategory.FILE_SYSTEM,
            ParsingError: ErrorCategory.PARSING,
            TimeoutError: ErrorCategory.TIMEOUT,
            AuthenticationError: ErrorCategory.AUTHENTICATION,
            ConfigurationError: ErrorCategory.CONFIGURATION,
            ResourceError: ErrorCategory.RESOURCE,
            ExecutionError: ErrorCategory.EXECUTION,
        }

        for error_class, expected_category in category_mappings.items():
            error = error_class("Test message")
            assert error.category == expected_category


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_error_with_none_values(self):
        """Test error creation with None values."""
        error = StructuredError(
            message="Test", context=None, original_error=None, suggestions=None
        )

        assert error.context is None
        assert error.original_error is None
        assert error.suggestions == []

    def test_error_serialization_with_complex_data(self):
        """Test error serialization with complex context data."""
        context = ErrorContext(
            "test_op",
            "test_component",
            details={
                "nested": {"data": "value"},
                "list": [1, 2, 3],
                "none_value": None,
            },
        )
        error = StructuredError("Test", context=context)

        # Should not raise an exception
        result = error.to_dict()
        assert "context" in result
        assert result["context"]["details"]["nested"]["data"] == "value"
