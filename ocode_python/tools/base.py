"""
Base classes and infrastructure for the OCode tool system.

This module provides the foundational abstractions and utilities for building
and managing AI-callable tools in OCode. It defines the contract that all tools
must follow, provides error handling utilities, and implements the tool registry
system for dynamic tool discovery and execution.

Key Components:
- Tool definition framework for AI function calling
- Standardized error handling and validation
- Tool registry for discovery and execution
- Parameter validation and type checking
- Consistent result formatting

The tool system is designed to be extensible, allowing new tools to be easily
added while maintaining consistency in behavior and error handling across
all tools.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


@dataclass
class ToolParameter:
    """Definition of a single parameter for a tool.

    Represents a parameter that can be passed to a tool, including
    its type information, description, and validation rules. This
    information is used by the AI to understand how to call tools
    and by the tool system for parameter validation.

    Attributes:
        name: Parameter name as it appears in function calls
        type: JSON Schema type ("string", "number", "boolean", "array", "object")
        description: Human-readable description of the parameter's purpose
        required: Whether this parameter must be provided
        default: Default value if parameter is not provided (None if no default)
    """

    name: str
    type: str  # "string", "number", "boolean", "array", "object"
    description: str
    required: bool = True
    default: Optional[Any] = None


class ResourceLock(Enum):
    """Resource locks that tools can acquire to prevent conflicts.

    Tools declare which resources they need exclusive access to,
    allowing the orchestrator to run tools safely in parallel.
    """

    FILESYSTEM_WRITE = "filesystem_write"
    GIT = "git"
    MEMORY = "memory"
    SHELL = "shell"
    NETWORK = "network"


@dataclass
class ToolDefinition:
    """Complete definition of a tool for AI function calling.

    Contains all metadata needed for the AI to understand and call a tool,
    including its purpose, parameters, and categorization. This definition
    is converted to various formats (like Ollama's function calling format)
    for different AI systems.

    Attributes:
        name: Unique identifier for the tool (used in function calls)
        description: Clear explanation of what the tool does and when to use it
        parameters: List of ToolParameter objects defining expected inputs
        category: Functional category for tool organization and discovery
        resource_locks: List of resources this tool needs exclusive access to
    """

    name: str
    description: str
    parameters: List[ToolParameter]
    category: str = "General"  # Default category for backward compatibility
    resource_locks: List[ResourceLock] = field(default_factory=list)

    def to_ollama_format(self) -> Dict[str, Any]:
        """Convert to Ollama function calling format.

        Transforms the tool definition into the format expected by
        Ollama's function calling API.

        Returns:
            Dictionary with type="function" and nested function definition.
        """
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }

            if param.default is not None:
                properties[param.name]["default"] = param.default

            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


@dataclass
class ToolResult:
    """Standardized result from tool execution.

    Provides a consistent format for tool results that includes success status,
    output content, error information, and additional metadata. This standard
    format enables consistent error handling and result processing across
    the entire system.

    Attributes:
        success: Whether the tool execution completed successfully
        output: The primary output content (empty string if failed)
        error: Error message if execution failed (None if successful)
        metadata: Additional structured data about the execution
        recovery_context: Information about error recovery attempts
    """

    success: bool
    output: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    recovery_context: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        """String representation of the tool result.

        Returns:
            Output string if successful, error message if not.
        """
        if self.success:
            return self.output
        else:
            return f"Error: {self.error}"


class ErrorType(Enum):
    """Standard error types for consistent error handling."""

    VALIDATION_ERROR = "validation_error"
    PERMISSION_ERROR = "permission_error"
    FILE_NOT_FOUND = "file_not_found"
    TIMEOUT_ERROR = "timeout_error"
    RESOURCE_ERROR = "resource_error"
    NETWORK_ERROR = "network_error"
    SECURITY_ERROR = "security_error"
    INTERNAL_ERROR = "internal_error"


class ToolError(Exception):
    """Base exception for tool-specific errors."""

    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.INTERNAL_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize tool error with type and details.

        Args:
            message: Error message.
            error_type: Type of error from ErrorType enum.
            details: Additional error details.
        """
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}


class ErrorHandler:
    """Centralized error handling utilities for tools."""

    @staticmethod
    def handle_exception(e: Exception, context: str = "") -> ToolResult:
        """Convert any exception to a standardized ToolResult.

        Provides consistent error handling and categorization for
        different exception types.

        Args:
            e: The exception to handle.
            context: Additional context about where the error occurred.

        Returns:
            ToolResult with error details and appropriate metadata.
        """
        if isinstance(e, ToolError):
            error_msg = str(e)
            metadata = {
                "error_type": e.error_type.value,
                "context": context,
                **e.details,
            }
        elif isinstance(e, FileNotFoundError):
            error_msg = f"File not found: {str(e)}"
            metadata = {
                "error_type": ErrorType.FILE_NOT_FOUND.value,
                "context": context,
            }
        elif isinstance(e, PermissionError):
            error_msg = f"Permission denied: {str(e)}"
            metadata = {
                "error_type": ErrorType.PERMISSION_ERROR.value,
                "context": context,
            }
        elif isinstance(e, TimeoutError):
            error_msg = f"Operation timed out: {str(e)}"
            metadata = {"error_type": ErrorType.TIMEOUT_ERROR.value, "context": context}
        elif isinstance(e, (OSError, IOError)):
            error_msg = f"I/O error: {str(e)}"
            metadata = {
                "error_type": ErrorType.RESOURCE_ERROR.value,
                "context": context,
            }
        else:
            error_msg = f"Unexpected error: {str(e)}"
            metadata = {
                "error_type": ErrorType.INTERNAL_ERROR.value,
                "context": context,
                "exception_type": type(e).__name__,
            }

        # Log error with stack trace for debugging
        logging.error(f"Tool error in {context}: {error_msg}", exc_info=True)

        return ToolResult(success=False, output="", error=error_msg, metadata=metadata)

    @staticmethod
    def validate_required_params(
        kwargs: Dict[str, Any], required_params: List[str]
    ) -> Optional[ToolResult]:
        """Validate that required parameters are present.

        Args:
            kwargs: Dictionary of provided parameters.
            required_params: List of parameter names that must be present.

        Returns:
            ToolResult with error if validation fails, None if valid.
        """
        missing_params = [
            param
            for param in required_params
            if param not in kwargs or kwargs[param] is None
        ]

        if missing_params:
            return ToolResult(
                success=False,
                output="",
                error=f"Missing required parameters: {', '.join(missing_params)}",
                metadata={
                    "error_type": ErrorType.VALIDATION_ERROR.value,
                    "missing_params": missing_params,
                },
            )
        return None

    @staticmethod
    def validate_string_param(
        value: Any,
        param_name: str,
        min_length: int = 0,
        max_length: int = 10000,
        pattern: Optional[str] = None,
    ) -> Optional[ToolResult]:
        """Validate string parameter with length and pattern constraints.

        Args:
            value: Value to validate.
            param_name: Name of the parameter (for error messages).
            min_length: Minimum string length.
            max_length: Maximum string length.
            pattern: Optional regex pattern to match.

        Returns:
            ToolResult with error if validation fails, None if valid.
        """
        if not isinstance(value, str):
            return ErrorHandler.create_error_result(
                f"Parameter '{param_name}' must be a string, got {type(value).__name__}",  # noqa: E501
                ErrorType.VALIDATION_ERROR,
                {"param_name": param_name, "actual_type": type(value).__name__},
            )

        if len(value) < min_length:
            return ErrorHandler.create_error_result(
                f"Parameter '{param_name}' must be at least {min_length} characters, got {len(value)}",  # noqa: E501
                ErrorType.VALIDATION_ERROR,
                {
                    "param_name": param_name,
                    "actual_length": len(value),
                    "min_length": min_length,
                },
            )

        if len(value) > max_length:
            return ErrorHandler.create_error_result(
                f"Parameter '{param_name}' must be at most {max_length} characters, got {len(value)}",  # noqa: E501
                ErrorType.VALIDATION_ERROR,
                {
                    "param_name": param_name,
                    "actual_length": len(value),
                    "max_length": max_length,
                },
            )

        if pattern:
            import re

            if not re.match(pattern, value):
                return ErrorHandler.create_error_result(
                    f"Parameter '{param_name}' does not match required pattern",
                    ErrorType.VALIDATION_ERROR,
                    {"param_name": param_name, "pattern": pattern},
                )

        return None

    @staticmethod
    def create_success_result(
        output: str, metadata: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """Create a standardized success result.

        Args:
            output: The output string from the tool.
            metadata: Optional metadata dictionary.

        Returns:
            ToolResult with success=True.
        """
        return ToolResult(success=True, output=output, metadata=metadata or {})

    @staticmethod
    def create_error_result(
        error_msg: str,
        error_type: ErrorType = ErrorType.INTERNAL_ERROR,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        """Create a standardized error result.

        Args:
            error_msg: The error message.
            error_type: Type of error from ErrorType enum.
            metadata: Optional error metadata.

        Returns:
            ToolResult with success=False and error details.
        """
        result_metadata = {"error_type": error_type.value}
        if metadata:
            result_metadata.update(metadata)

        return ToolResult(
            success=False, output="", error=error_msg, metadata=result_metadata
        )


class Tool(ABC):
    """
    Abstract base class for all OCode tools.

    Defines the contract that all tools must implement to be usable by the AI.
    Tools are specialized functions that can be called by AI models to perform
    specific tasks like file operations, git commands, shell execution, etc.

    Architecture:
    - Each tool has a unique name and detailed definition for AI understanding
    - Tools implement async execution for non-blocking operations
    - Parameter validation ensures type safety and proper error handling
    - Standardized error handling provides consistent user feedback

    Tool Lifecycle:
    1. Definition: Tool declares its name, description, and parameters
    2. Registration: Tool is registered with the ToolRegistry
    3. Discovery: AI discovers tool via registry and definition
    4. Validation: Parameters are validated before execution
    5. Execution: Tool performs its async operation
    6. Result: Tool returns standardized ToolResult

    Key Requirements for Implementations:
    - Must provide a ToolDefinition via the definition property
    - Must implement async execute() method
    - Should use ErrorHandler utilities for consistent error handling
    - Should follow parameter validation patterns
    - Should provide meaningful error messages and metadata
    """

    def __init__(self):
        """Initialize tool with name from definition.

        Extracts the tool name from the definition for convenient access.
        Subclasses should call super().__init__() to ensure proper initialization.
        """
        self.name = self.definition.name

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Get tool definition for LLM function calling.

        This property must be implemented by all tool subclasses to provide
        metadata about the tool including its name, description, parameters,
        and category. The definition is used by the LLM to understand what
        tools are available and how to call them.

        Returns:
            ToolDefinition object containing:
            - name: Unique identifier for the tool
            - description: Clear explanation of what the tool does
            - parameters: List of ToolParameter objects defining inputs
            - category: Functional category for tool organization

        Example:
            >>> def definition(self) -> ToolDefinition:
            ...     return ToolDefinition(
            ...         name="file_read",
            ...         description="Read the contents of a file",
            ...         category="File Operations",
            ...         parameters=[
            ...             ToolParameter(
            ...                 name="path",
            ...                 type="string",
            ...                 description="Path to the file to read",
            ...                 required=True
            ...             )
            ...         ]
            ...     )
        """
        pass

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool's main functionality asynchronously.

        This is the core method that performs the tool's actual work.
        Implementations should:
        1. Validate parameters thoroughly
        2. Perform the tool's operation asynchronously when possible
        3. Handle errors gracefully with appropriate categorization
        4. Return standardized ToolResult with meaningful output
        5. Include relevant metadata for debugging and monitoring

        Args:
            **kwargs: Parameters as defined in the tool's definition.
                     Parameter names and types should match the ToolDefinition.

        Returns:
            ToolResult indicating success/failure with appropriate output,
            error messages, and metadata.

        Raises:
            Should not raise exceptions - instead catch them and return
            appropriate ToolResult with error information.
        """
        pass

    def validate_parameters(self, kwargs: Dict[str, Any]) -> bool:
        """Validate parameters against tool definition.

        Checks that required parameters are present and have correct types.
        Special handling for 'value' parameter in memory tools.

        Args:
            kwargs: Dictionary of provided parameters.

        Returns:
            True if parameters are valid, False otherwise.
        """
        definition = self.definition

        # Check required parameters
        for param in definition.parameters:
            if param.required and param.name not in kwargs:
                return False

        # Check parameter types (basic validation)
        for param_name, value in kwargs.items():
            param_def = next(
                (p for p in definition.parameters if p.name == param_name), None
            )
            if param_def:
                # Special case: for memory tools, "value" parameter can be any type
                if (
                    param_name == "value"
                    and param_def.description
                    and "JSON-serializable" in param_def.description
                ):
                    continue  # Allow any JSON-serializable type
                elif param_def.type == "string" and not isinstance(value, str):
                    return False
                elif param_def.type == "number" and not isinstance(value, (int, float)):
                    return False
                elif param_def.type == "boolean" and not isinstance(value, bool):
                    return False
                elif param_def.type == "array" and not isinstance(value, list):
                    return False
                elif param_def.type == "object" and not isinstance(value, dict):
                    return False

        return True


class ToolRegistry:
    """
    Central registry for tool discovery, management, and execution.

    The ToolRegistry serves as the central hub for all tool operations in OCode.
    It manages tool instances, provides discovery mechanisms for the AI, handles
    tool execution with proper validation, and maintains the catalog of available
    capabilities.

    Key Responsibilities:
    - Tool registration and storage
    - Tool discovery and metadata access
    - Parameter validation and execution coordination
    - Error handling and result standardization
    - Core tool initialization and management

    Architecture:
    - Singleton pattern: One registry per application instance
    - Name-based tool lookup for efficient access
    - Async execution support for non-blocking operations
    - Automatic core tool registration
    - Extensible design for custom tool addition

    Usage Patterns:
    1. Initialize registry
    2. Register core tools (automatically)
    3. Register any custom tools
    4. Provide tool definitions to AI
    5. Execute tools based on AI function calls
    """

    def __init__(self):
        self.tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        """Register a tool.

        Args:
            tool: Tool instance to register.
        """
        self.tools[tool.name] = tool

    def register_core_tools(self):
        """Register all built-in OCode tools.

        Imports and registers the complete set of core tools that provide
        the standard OCode functionality. This includes tools for file
        operations, version control, shell execution, data processing,
        analysis, and more.

        Tool Categories Registered:
        - File Operations: read, write, edit, list, copy, move, remove
        - Version Control: git status, commit, diff, branch operations
        - Shell and Execution: bash commands, script execution
        - Text Processing: grep, find, head, tail, sort, uniq
        - Data Tools: JSON/YAML processing, data analysis
        - Development: code analysis, testing, documentation
        - System: process monitoring, environment management
        - AI Assistance: thinking, architecture analysis, agent management
        - Specialized: notebook handling, memory management, annotations

        This method is typically called once during application initialization
        to make all standard tools available for AI use.

        Side Effects:
            Imports all tool modules and instantiates tool classes.
            Registers approximately 30+ core tools in the registry.
        """
        from .agent_tool import AgentTool
        from .architect_tool import ArchitectTool
        from .bash_tool import BashTool, ScriptTool
        from .curl_tool import CurlTool
        from .data_tools import JsonYamlTool
        from .diff_tool import DiffTool
        from .env_tool import EnvironmentTool
        from .file_edit_tool import FileEditTool
        from .file_ops_tool import CopyTool, MoveTool, RemoveTool
        from .file_tools import FileListTool, FileReadTool, FileWriteTool
        from .find_tool import FindTool
        from .git_advanced_tools import (
            GitAddTool,
            GitCloneTool,
            GitPullTool,
            GitPushTool,
            GitResetTool,
            GitStashTool,
            GitStatusJSONTool,
        )
        from .git_tools import GitCommitTool, GitDiffTool, GitStatusTool
        from .glob_tool import AdvancedGlobTool, GlobTool
        from .grep_tool import CodeGrepTool, GrepTool

        # Basic Unix tools
        from .head_tail_tool import HeadTool, TailTool
        from .ls_tool import LsTool
        from .mcp_tool import MCPTool
        from .memory_tools import MemoryReadTool, MemoryWriteTool
        from .notebook_tools import NotebookEditTool, NotebookReadTool
        from .ping_tool import PingTool
        from .process_tool import ProcessMonitorTool

        try:
            from .search_tool import SearchTool

            search_tool_available = True
        except ImportError:
            search_tool_available = False
        from .session_tool import SessionTool
        from .shell_tools import ShellCommandTool
        from .sticker_tool import StickerRequestTool
        from .test_tools import ExecutionTool
        from .text_tools import SortTool, UniqTool
        from .think_tool import ThinkTool
        from .wc_tool import WcTool
        from .which_tool import WhichTool

        core_tools = [
            # Original tools
            FileReadTool(),
            FileWriteTool(),
            FileListTool(),
            GitStatusTool(),
            GitCommitTool(),
            GitDiffTool(),
            # Advanced Git tools
            GitAddTool(),
            GitPullTool(),
            GitPushTool(),
            GitCloneTool(),
            GitResetTool(),
            GitStashTool(),
            GitStatusJSONTool(),
            ShellCommandTool(),
            ExecutionTool(),
            # New enhanced tools
            GlobTool(),
            AdvancedGlobTool(),
            GrepTool(),
            CodeGrepTool(),
            LsTool(),
            FileEditTool(),
            BashTool(),
            ScriptTool(),
            NotebookReadTool(),
            NotebookEditTool(),
            MemoryReadTool(),
            MemoryWriteTool(),
            ThinkTool(),
            ArchitectTool(),
            AgentTool(),
            MCPTool(),
            StickerRequestTool(),
            # Basic Unix tools
            HeadTool(),
            TailTool(),
            DiffTool(),
            WcTool(),
            FindTool(),
            CopyTool(),
            MoveTool(),
            RemoveTool(),
            SortTool(),
            UniqTool(),
            CurlTool(),
            WhichTool(),
            PingTool(),
            # Data processing and system tools
            JsonYamlTool(),
            ProcessMonitorTool(),
            EnvironmentTool(),
            SessionTool(),
        ]

        # Add SearchTool if available
        if search_tool_available:
            core_tools.append(SearchTool())

        for tool in core_tools:
            self.register(tool)

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get tool by name.

        Args:
            name: Name of the tool to retrieve.

        Returns:
            Tool instance if found, None otherwise.
        """
        return self.tools.get(name)

    def get_all_tools(self) -> List[Tool]:
        """Get all registered tools.

        Returns:
            List of all registered Tool instances.
        """
        return list(self.tools.values())

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get all tool definitions in Ollama format.

        Returns:
            List of tool definitions formatted for Ollama's function calling API.
        """
        return [tool.definition.to_ollama_format() for tool in self.tools.values()]

    async def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a tool by name with parameter validation.

        This is the main entry point for tool execution, providing a safe
        and standardized way to run tools with proper error handling and
        validation. It coordinates the entire execution pipeline from
        tool lookup through result generation.

        Execution Pipeline:
        1. Tool lookup: Find tool instance by name
        2. Parameter validation: Check parameters against tool definition
        3. Async execution: Run the tool's execute() method
        4. Error handling: Catch and convert any exceptions to ToolResult
        5. Result standardization: Ensure consistent ToolResult format

        Args:
            tool_name: Exact name of the tool to execute as registered
                      in the registry.
            **kwargs: All parameters to pass to the tool's execute() method.
                     Parameter names and types should match the tool's definition.

        Returns:
            ToolResult indicating the outcome of the execution:
            - Success: Contains tool output and optional metadata
            - Failure: Contains error message, error type, and context

        Error Conditions:
        - Tool not found: Returns error if tool_name doesn't exist
        - Invalid parameters: Returns error if validation fails
        - Execution failure: Returns error if tool execution raises exception

        Note:
            This method never raises exceptions - all errors are captured
            and returned as ToolResult objects for consistent handling.
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(
                success=False, output="", error=f"Tool '{tool_name}' not found"
            )

        if not tool.validate_parameters(kwargs):
            return ToolResult(
                success=False,
                output="",
                error=f"Invalid parameters for tool '{tool_name}'",
            )

        try:
            return await tool.execute(**kwargs)
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Tool execution failed: {str(e)}"
            )
