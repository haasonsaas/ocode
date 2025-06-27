"""
Structured error classes for better error context and debugging.

This module provides a hierarchy of structured error classes that standardize
error handling across all tools and provide rich context for debugging.
"""

import builtins
import traceback
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""

    VALIDATION = "validation"
    PERMISSION = "permission"
    NETWORK = "network"
    FILE_SYSTEM = "file_system"
    PARSING = "parsing"
    TIMEOUT = "timeout"
    AUTHENTICATION = "authentication"
    CONFIGURATION = "configuration"
    RESOURCE = "resource"
    EXECUTION = "execution"
    UNKNOWN = "unknown"


class ErrorContext:
    """Container for error context information."""

    def __init__(
        self,
        operation: str,
        component: str,
        details: Optional[Dict[str, Any]] = None,
        user_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize error context.

        Args:
            operation: Name of the operation that failed
            component: Component or tool where the error occurred
            details: Technical details about the error
            user_data: User-provided data that may have caused the error
        """
        self.operation = operation
        self.component = component
        self.details = details or {}
        self.user_data = user_data or {}
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "operation": self.operation,
            "component": self.component,
            "details": self.details,
            "user_data": self.user_data,
            "timestamp": self.timestamp.isoformat(),
        }


class StructuredError(Exception):
    """
    Base structured error class with rich context information.

    All OCode errors should inherit from this class to provide
    consistent error handling and debugging information.
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[ErrorContext] = None,
        original_error: Optional[Exception] = None,
        suggestions: Optional[List[str]] = None,
        error_code: Optional[str] = None,
    ):
        """
        Initialize structured error.

        Args:
            message: Human-readable error message
            category: Error category for classification
            severity: Error severity level
            context: Error context information
            original_error: Original exception that caused this error
            suggestions: List of suggested remediation steps
            error_code: Unique error code for this error type
        """
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context
        self.original_error = original_error
        self.suggestions = suggestions or []
        self.error_code = error_code
        self.traceback_info = traceback.format_exc() if original_error else None

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization."""
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "context": self.context.to_dict() if self.context else None,
            "original_error": str(self.original_error) if self.original_error else None,
            "suggestions": self.suggestions,
            "error_code": self.error_code,
            "traceback": self.traceback_info,
        }

    def get_debug_info(self) -> str:
        """Get formatted debug information."""
        lines = [
            f"Error: {self.__class__.__name__}",
            f"Message: {self.message}",
            f"Category: {self.category.value}",
            f"Severity: {self.severity.value}",
        ]

        if self.error_code:
            lines.append(f"Code: {self.error_code}")

        if self.context:
            lines.append(f"Operation: {self.context.operation}")
            lines.append(f"Component: {self.context.component}")
            lines.append(f"Timestamp: {self.context.timestamp}")

            if self.context.details:
                lines.append("Details:")
                for key, value in self.context.details.items():
                    lines.append(f"  {key}: {value}")

        if self.original_error:
            lines.append(f"Original Error: {self.original_error}")

        if self.suggestions:
            lines.append("Suggestions:")
            for suggestion in self.suggestions:
                lines.append(f"  • {suggestion}")

        return "\n".join(lines)


class ValidationError(StructuredError):
    """Error for input validation failures."""

    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        field_value: Optional[Any] = None,
        expected_type: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        **kwargs,
    ):
        super().__init__(
            message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            context=context,
            **kwargs,
        )
        self.field_name = field_name
        self.field_value = field_value
        self.expected_type = expected_type


class PermissionError(StructuredError):
    """Error for permission-related failures."""

    def __init__(
        self,
        message: str,
        resource_path: Optional[str] = None,
        required_permission: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        **kwargs,
    ):
        super().__init__(
            message,
            category=ErrorCategory.PERMISSION,
            severity=ErrorSeverity.HIGH,
            context=context,
            **kwargs,
        )
        self.resource_path = resource_path
        self.required_permission = required_permission


class NetworkError(StructuredError):
    """Error for network-related failures."""

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        status_code: Optional[int] = None,
        retry_count: Optional[int] = None,
        context: Optional[ErrorContext] = None,
        **kwargs,
    ):
        super().__init__(
            message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.MEDIUM,
            context=context,
            **kwargs,
        )
        self.url = url
        self.status_code = status_code
        self.retry_count = retry_count


class FileSystemError(StructuredError):
    """Error for file system-related failures."""

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        operation_type: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        **kwargs,
    ):
        super().__init__(
            message,
            category=ErrorCategory.FILE_SYSTEM,
            severity=ErrorSeverity.MEDIUM,
            context=context,
            **kwargs,
        )
        self.file_path = file_path
        self.operation_type = operation_type


class ParsingError(StructuredError):
    """Error for data parsing failures."""

    def __init__(
        self,
        message: str,
        data_format: Optional[str] = None,
        line_number: Optional[int] = None,
        column_number: Optional[int] = None,
        context: Optional[ErrorContext] = None,
        **kwargs,
    ):
        super().__init__(
            message,
            category=ErrorCategory.PARSING,
            severity=ErrorSeverity.MEDIUM,
            context=context,
            **kwargs,
        )
        self.data_format = data_format
        self.line_number = line_number
        self.column_number = column_number


class TimeoutError(StructuredError):
    """Error for timeout-related failures."""

    def __init__(
        self,
        message: str,
        timeout_duration: Optional[float] = None,
        operation_name: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        **kwargs,
    ):
        super().__init__(
            message,
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.MEDIUM,
            context=context,
            **kwargs,
        )
        self.timeout_duration = timeout_duration
        self.operation_name = operation_name


class AuthenticationError(StructuredError):
    """Error for authentication failures."""

    def __init__(
        self,
        message: str,
        auth_method: Optional[str] = None,
        provider: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        **kwargs,
    ):
        super().__init__(
            message,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            context=context,
            **kwargs,
        )
        self.auth_method = auth_method
        self.provider = provider


class ConfigurationError(StructuredError):
    """Error for configuration-related failures."""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_file: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        **kwargs,
    ):
        super().__init__(
            message,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.HIGH,
            context=context,
            **kwargs,
        )
        self.config_key = config_key
        self.config_file = config_file


class ResourceError(StructuredError):
    """Error for resource-related failures (memory, disk, etc.)."""

    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        current_usage: Optional[Union[int, float]] = None,
        limit: Optional[Union[int, float]] = None,
        context: Optional[ErrorContext] = None,
        **kwargs,
    ):
        super().__init__(
            message,
            category=ErrorCategory.RESOURCE,
            severity=ErrorSeverity.HIGH,
            context=context,
            **kwargs,
        )
        self.resource_type = resource_type
        self.current_usage = current_usage
        self.limit = limit


class ExecutionError(StructuredError):
    """Error for command/tool execution failures."""

    def __init__(
        self,
        message: str,
        command: Optional[str] = None,
        exit_code: Optional[int] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        **kwargs,
    ):
        super().__init__(
            message,
            category=ErrorCategory.EXECUTION,
            severity=ErrorSeverity.MEDIUM,
            context=context,
            **kwargs,
        )
        self.command = command
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


def create_error_from_exception(
    exc: Exception,
    operation: str,
    component: str,
    additional_context: Optional[Dict[str, Any]] = None,
) -> StructuredError:
    """
    Create a structured error from a standard Python exception.

    Args:
        exc: Original exception
        operation: Name of the operation that failed
        component: Component where the error occurred
        additional_context: Additional context information

    Returns:
        Appropriate StructuredError subclass
    """
    # If it's already a StructuredError, just return it
    if isinstance(exc, StructuredError):
        return exc

    context = ErrorContext(
        operation=operation, component=component, details=additional_context or {}
    )

    # Map common exceptions to structured errors
    if isinstance(exc, FileNotFoundError):
        return FileSystemError(
            f"File not found: {exc}",
            file_path=str(exc.filename) if exc.filename else None,
            operation_type="read",
            context=context,
            original_error=exc,
        )

    elif isinstance(exc, builtins.PermissionError):
        # Return custom PermissionError as tests expect resource_path attribute
        filename = getattr(exc, "filename", None)
        return PermissionError(
            f"Permission denied: {exc}",
            resource_path=str(filename) if filename is not None else None,
            context=context,
            original_error=exc,
        )

    elif isinstance(exc, FileExistsError):
        return FileSystemError(
            f"File exists: {exc}",
            file_path=str(exc.filename) if exc.filename else None,
            operation_type="create",
            context=context,
            original_error=exc,
        )

    elif isinstance(exc, ConnectionError):
        return NetworkError(
            f"Network connection failed: {exc}", context=context, original_error=exc
        )

    elif isinstance(exc, ValueError):
        return ValidationError(
            f"Invalid value: {exc}", context=context, original_error=exc
        )

    elif isinstance(exc, (builtins.TimeoutError, asyncio.TimeoutError)):
        return TimeoutError(
            f"Operation timed out: {exc}",
            context=context,
            original_error=exc,
        )

    else:
        # Default to generic StructuredError
        return StructuredError(
            f"Unexpected error: {exc}",
            category=ErrorCategory.UNKNOWN,
            context=context,
            original_error=exc,
        )


def format_error_for_user(error: StructuredError) -> str:
    """
    Format a structured error for user-friendly display.

    Args:
        error: Structured error to format

    Returns:
        User-friendly error message
    """
    lines = [f"❌ {error.message}"]

    if error.context:
        lines.append(f"Operation: {error.context.operation}")

        # Add relevant details based on error type
        if isinstance(error, FileSystemError) and error.file_path:
            lines.append(f"File: {error.file_path}")
        elif isinstance(error, NetworkError) and error.url:
            lines.append(f"URL: {error.url}")
            if error.status_code:
                lines.append(f"Status Code: {error.status_code}")
        elif isinstance(error, ValidationError) and error.field_name:
            lines.append(f"Field: {error.field_name}")

    if error.suggestions:
        lines.append("\nSuggestions:")
        for suggestion in error.suggestions:
            lines.append(f"  • {suggestion}")

    return "\n".join(lines)


# Convenience imports for backward compatibility
try:
    import asyncio
except ImportError:
    pass
