"""
File manipulation tools with centralized path validation.
"""

import asyncio
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils import path_validator
from ..utils.atomic_operations import AtomicFileWriter
from ..utils.timeout_handler import TimeoutError, async_timeout
from .base import ToolError  # noqa: F401
from .base import (
    ErrorHandler,
    ErrorType,
    ResourceLock,
    Tool,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)


class FileReadTool(Tool):
    """Tool for reading file contents with enhanced security."""

    @property
    def definition(self) -> ToolDefinition:
        """Define the file_read tool specification.

        Returns:
            ToolDefinition with parameters for reading files including
            path, encoding, offset, and limit options.
        """
        return ToolDefinition(
            name="file_read",
            description="Read the contents of a file",
            category="File Operations",
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to the file to read",
                    required=True,
                ),
                ToolParameter(
                    name="encoding",
                    type="string",
                    description="File encoding (default: utf-8)",
                    required=False,
                    default="utf-8",
                ),
                ToolParameter(
                    name="offset",
                    type="number",
                    description="Start reading from this byte offset",
                    required=False,
                    default=0,
                ),
                ToolParameter(
                    name="limit",
                    type="number",
                    description="Maximum number of bytes to read",
                    required=False,
                    default=-1,
                ),
            ],
        )

    def _try_common_extensions(self, base_path: Path) -> Optional[Path]:
        """Try common file extensions if the base path doesn't exist."""
        if base_path.exists():
            return base_path

        # Common extensions to try
        common_extensions = [
            ".md",
            ".txt",
            ".rst",
            ".markdown",
            ".py",
            ".js",
            ".ts",
            ".json",
            ".yaml",
            ".yml",
        ]

        for ext in common_extensions:
            path_with_ext = base_path.with_suffix(ext)
            if path_with_ext.exists():
                return path_with_ext

        return None

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Read file contents with enhanced security validation and streaming support."""  # noqa: E501
        try:
            # Validate required parameters
            validation_error = ErrorHandler.validate_required_params(kwargs, ["path"])
            if validation_error:
                return validation_error

            path = kwargs.get("path")
            encoding = kwargs.get("encoding", "utf-8")
            offset = kwargs.get("offset", 0)
            limit = kwargs.get("limit", -1)

            # Calculate appropriate timeout based on file size
            timeout = kwargs.get("timeout", 30.0)  # Default 30 second timeout

            # Validate path security using centralized validator
            if path is None:
                return ErrorHandler.create_error_result(
                    "Path parameter is required",
                    ErrorType.VALIDATION_ERROR,
                    {"path": path},
                )
            is_valid, error_msg, validated_path = path_validator.validate_path(
                path, check_exists=False  # We'll check with extensions
            )
            if not is_valid:
                return ErrorHandler.create_error_result(
                    f"Path validation failed: {error_msg}",
                    ErrorType.SECURITY_ERROR,
                    {"path": path},
                )

            # Try to find the file with common extensions if it doesn't exist
            if validated_path is None:
                return ErrorHandler.create_error_result(
                    "Path validation returned None",
                    ErrorType.VALIDATION_ERROR,
                    {"path": path},
                )
            resolved_path = self._try_common_extensions(validated_path)
            if not resolved_path:
                return ErrorHandler.create_error_result(
                    f"File does not exist: {path}",
                    ErrorType.FILE_NOT_FOUND,
                    {
                        "path": path,
                        "attempted_extensions": [
                            ".md",
                            ".txt",
                            ".rst",
                            ".markdown",
                            ".py",
                            ".js",
                            ".ts",
                            ".json",
                            ".yaml",
                            ".yml",
                        ],
                    },
                )

            if not resolved_path.is_file():
                return ErrorHandler.create_error_result(
                    f"Path is not a file: {resolved_path}",
                    ErrorType.VALIDATION_ERROR,
                    {
                        "path": str(resolved_path),
                        "path_type": "directory" if resolved_path.is_dir() else "other",
                    },
                )

            # Check file size before reading
            file_size = resolved_path.stat().st_size
            max_file_size = 50 * 1024 * 1024  # 50MB limit

            # Adjust timeout based on file size (roughly 1MB per second)
            if file_size > 1024 * 1024:  # 1MB
                timeout = max(timeout, file_size / (1024 * 1024))  # Seconds per MB

            # For streaming support with offset/limit
            if offset > 0 or limit > 0:
                # Validate offset
                if offset >= file_size:
                    return ErrorHandler.create_error_result(
                        f"Offset {offset} exceeds file size {file_size}",
                        ErrorType.VALIDATION_ERROR,
                        {"offset": offset, "file_size": file_size},
                    )

                # Read with offset and limit - wrapped with timeout
                try:
                    async with async_timeout(
                        timeout, f"file_read({resolved_path.name})"
                    ):
                        # Use asyncio to make I/O non-blocking
                        loop = asyncio.get_event_loop()

                        def _read_chunk():
                            with open(resolved_path, "rb") as f:
                                f.seek(offset)
                                if limit > 0:
                                    return f.read(limit)
                                else:
                                    return f.read()

                        content_bytes = await loop.run_in_executor(None, _read_chunk)

                    # Try to decode with specified encoding
                    try:
                        content = content_bytes.decode(encoding)
                    except UnicodeDecodeError:
                        # Fallback to replace errors
                        content = content_bytes.decode(encoding, errors="replace")
                except TimeoutError as e:
                    return ErrorHandler.create_error_result(
                        f"File read operation timed out: {e}",
                        ErrorType.TIMEOUT_ERROR,
                        {
                            "path": str(resolved_path),
                            "timeout": timeout,
                            "file_size": file_size,
                        },
                    )

                return ErrorHandler.create_success_result(
                    content,
                    {
                        "file_size": file_size,
                        "encoding": encoding,
                        "resolved_path": str(resolved_path),
                        "bytes_read": len(content_bytes),
                        "offset": offset,
                    },
                )

            # Standard full file read
            if file_size > max_file_size:
                return ErrorHandler.create_error_result(
                    f"File too large: {file_size} bytes (max: {max_file_size}). Use offset/limit for large files.",  # noqa: E501
                    ErrorType.RESOURCE_ERROR,
                    {"file_size": file_size, "max_size": max_file_size},
                )

            # Try multiple encodings if the specified one fails
            encodings_to_try = [encoding]
            if encoding != "utf-8":
                encodings_to_try.append("utf-8")
            encodings_to_try.extend(["utf-8-sig", "latin-1", "cp1252"])

            content = None
            used_encoding = None

            try:
                async with async_timeout(timeout, f"file_read({resolved_path.name})"):
                    loop = asyncio.get_event_loop()

                    def _read_with_encoding():
                        for enc in encodings_to_try:
                            try:
                                with open(resolved_path, "r", encoding=enc) as f:
                                    return f.read(), enc
                            except UnicodeDecodeError:
                                continue

                        # Last resort: binary read with lossy conversion
                        with open(resolved_path, "rb") as f:
                            return (
                                f.read().decode("utf-8", errors="replace"),
                                "utf-8 (with replacements)",
                            )

                    content, used_encoding = await loop.run_in_executor(
                        None, _read_with_encoding
                    )

            except TimeoutError as e:
                return ErrorHandler.create_error_result(
                    f"File read operation timed out: {e}",
                    ErrorType.TIMEOUT_ERROR,
                    {
                        "path": str(resolved_path),
                        "timeout": timeout,
                        "file_size": file_size,
                    },
                )

            return ErrorHandler.create_success_result(
                content,
                {
                    "file_size": file_size,
                    "encoding": used_encoding,
                    "resolved_path": str(resolved_path),
                    "original_encoding_requested": encoding,
                },
            )

        except Exception as e:
            return ErrorHandler.handle_exception(
                e, f"FileReadTool.execute(path={kwargs.get('path')})"
            )


class FileWriteTool(Tool):
    """Tool for writing file contents with enhanced security."""

    @property
    def definition(self) -> ToolDefinition:
        """Define the file_write tool specification.

        Returns:
            ToolDefinition with parameters for writing files including
            path, content, encoding, and create_directories options.
        """
        return ToolDefinition(
            name="file_write",
            description="Write content to a file",
            category="File Operations",
            resource_locks=[ResourceLock.FILESYSTEM_WRITE],
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to the file to write",
                    required=True,
                ),
                ToolParameter(
                    name="content",
                    type="string",
                    description="Content to write to the file",
                    required=True,
                ),
                ToolParameter(
                    name="encoding",
                    type="string",
                    description="File encoding (default: utf-8)",
                    required=False,
                    default="utf-8",
                ),
                ToolParameter(
                    name="create_dirs",
                    type="boolean",
                    description="Create parent directories if they don't exist",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="append",
                    type="boolean",
                    description="Append to file instead of overwriting",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="atomic",
                    type="boolean",
                    description="Use atomic write operation (safer but incompatible with append)",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="backup",
                    type="boolean",
                    description="Create backup of existing file when using atomic write",
                    required=False,
                    default=True,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Write content to file with enhanced validation and safety."""
        try:
            # Validate required parameters
            validation_error = ErrorHandler.validate_required_params(
                kwargs, ["path", "content"]
            )
            if validation_error:
                return validation_error

            path = kwargs.get("path")
            content = kwargs.get("content")
            encoding = kwargs.get("encoding", "utf-8")
            create_dirs = kwargs.get("create_dirs", True)
            append = kwargs.get("append", False)
            atomic = kwargs.get("atomic", True)
            backup = kwargs.get("backup", True)

            # Validate path security
            if path is None:
                return ErrorHandler.create_error_result(
                    "Path parameter is required",
                    ErrorType.VALIDATION_ERROR,
                    {"path": path},
                )
            is_valid, error_msg, validated_path = path_validator.validate_path(path)
            if not is_valid:
                return ErrorHandler.create_error_result(
                    f"Path validation failed: {error_msg}",
                    ErrorType.SECURITY_ERROR,
                    {"path": path},
                )

            # Ensure parent directory exists if requested
            if validated_path is None:
                return ErrorHandler.create_error_result(
                    "Path validation returned None",
                    ErrorType.VALIDATION_ERROR,
                    {"path": path},
                )
            if create_dirs:
                validated_path.parent.mkdir(parents=True, exist_ok=True)
            elif not validated_path.parent.exists():
                return ErrorHandler.create_error_result(
                    f"Parent directory does not exist: {validated_path.parent}",
                    ErrorType.FILE_NOT_FOUND,
                    {"parent_dir": str(validated_path.parent)},
                )

            # Check if we're overwriting an existing file
            file_exists = validated_path.exists()
            original_size = validated_path.stat().st_size if file_exists else 0

            # Validate atomic mode constraints
            if atomic and append:
                return ErrorHandler.create_error_result(
                    "Atomic write mode is incompatible with append mode",
                    ErrorType.VALIDATION_ERROR,
                    {"atomic": atomic, "append": append},
                )

            # Write the file
            if content is None:
                content = ""

            bytes_written = len(str(content).encode(encoding))

            # Use atomic write for safety when not appending
            if atomic and not append:
                try:
                    with AtomicFileWriter(
                        validated_path,
                        mode="w",
                        encoding=encoding,
                        backup=backup and file_exists,
                        sync=True,
                    ) as f:
                        f.write(str(content))
                except Exception as e:
                    return ErrorHandler.create_error_result(
                        f"Atomic write failed: {str(e)}",
                        ErrorType.RESOURCE_ERROR,
                        {
                            "path": str(validated_path),
                            "error": str(e),
                            "atomic": True,
                        },
                    )
            else:
                # Traditional write for append mode or when atomic is disabled
                mode = "a" if append else "w"
                try:
                    with open(validated_path, mode, encoding=encoding) as f:
                        f.write(str(content))
                        # Ensure data is written to disk
                        f.flush()
                        if hasattr(f, "fileno"):
                            try:
                                os.fsync(f.fileno())
                            except (OSError, ValueError):
                                pass  # Best effort
                except Exception as e:
                    return ErrorHandler.create_error_result(
                        f"File write failed: {str(e)}",
                        ErrorType.RESOURCE_ERROR,
                        {
                            "path": str(validated_path),
                            "error": str(e),
                            "mode": mode,
                        },
                    )

            # Verify write succeeded
            new_size = validated_path.stat().st_size

            return ErrorHandler.create_success_result(
                f"Successfully wrote {len(content)} characters to {validated_path}",
                {
                    "bytes_written": bytes_written,
                    "file_existed": file_exists,
                    "original_size": original_size,
                    "new_size": new_size,
                    "mode": "append" if append else "overwrite",
                    "encoding": encoding,
                    "atomic": atomic and not append,
                    "backup_created": backup and file_exists and atomic and not append,
                },
            )

        except Exception as e:
            return ErrorHandler.handle_exception(
                e, f"FileWriteTool.execute(path={kwargs.get('path')})"
            )


class FileListTool(Tool):
    """Tool for listing directory contents with enhanced filtering."""

    @property
    def definition(self) -> ToolDefinition:
        """Define the file_list (ls) tool specification.

        Returns:
            ToolDefinition with parameters for listing directory contents
            including path, recursive, pattern, and show_hidden options.
        """
        return ToolDefinition(
            name="file_list",
            description="List files and directories in a path",
            category="File Operations",
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to list (default: current directory)",
                    required=False,
                    default=".",
                ),
                ToolParameter(
                    name="recursive",
                    type="boolean",
                    description="List files recursively",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="include_hidden",
                    type="boolean",
                    description="Include hidden files (starting with .)",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="extensions",
                    type="array",
                    description="Filter by file extensions (e.g., ['.py', '.js'])",
                    required=False,
                ),
                ToolParameter(
                    name="pattern",
                    type="string",
                    description="Glob pattern to filter files (e.g., '*.py', 'test_*')",
                    required=False,
                ),
                ToolParameter(
                    name="max_depth",
                    type="number",
                    description="Maximum directory depth for recursive listing",
                    required=False,
                    default=-1,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """List directory contents with enhanced filtering options."""
        try:
            path = kwargs.get("path", ".")
            recursive = kwargs.get("recursive", False)
            include_hidden = kwargs.get("include_hidden", False)
            extensions = kwargs.get("extensions")
            pattern = kwargs.get("pattern")
            max_depth = kwargs.get("max_depth", -1)

            # Validate path
            is_valid, error_msg, validated_path = path_validator.validate_path(
                path, check_exists=True
            )
            if not is_valid or validated_path is None:
                return ErrorHandler.create_error_result(
                    f"Path validation failed: {error_msg}",
                    ErrorType.SECURITY_ERROR,
                    {"path": path},
                )

            if not validated_path.is_dir():
                return ErrorHandler.create_error_result(
                    f"Path is not a directory: {validated_path}",
                    ErrorType.VALIDATION_ERROR,
                    {"path": str(validated_path)},
                )

            files = []
            dirs = []

            # Helper to check depth
            def is_within_depth(item_path: Path, base_path: Path, max_d: int) -> bool:
                if max_d < 0:
                    return True
                try:
                    rel_path = item_path.relative_to(base_path)
                    depth = len(rel_path.parts) - 1
                    return depth <= max_d
                except ValueError:
                    return False

            if pattern:
                # Use glob pattern
                if recursive:
                    glob_pattern = f"**/{pattern}"
                else:
                    glob_pattern = pattern

                for item in validated_path.glob(glob_pattern):
                    if not include_hidden and any(
                        part.startswith(".") for part in item.parts
                    ):
                        continue
                    if max_depth >= 0 and not is_within_depth(
                        item, validated_path, max_depth
                    ):
                        continue

                    if item.is_file():
                        if not extensions or item.suffix in extensions:
                            files.append(str(item.relative_to(validated_path)))
                    elif item.is_dir():
                        dirs.append(str(item.relative_to(validated_path)))
            else:
                # Standard listing
                if recursive:
                    for item in validated_path.rglob("*"):
                        if not include_hidden and any(
                            part.startswith(".") for part in item.parts
                        ):
                            continue
                        if max_depth >= 0 and not is_within_depth(
                            item, validated_path, max_depth
                        ):
                            continue

                        if item.is_file():
                            if not extensions or item.suffix in extensions:
                                files.append(str(item.relative_to(validated_path)))
                        elif item.is_dir():
                            dirs.append(str(item.relative_to(validated_path)))
                else:
                    for item in validated_path.iterdir():
                        if not include_hidden and item.name.startswith("."):
                            continue

                        if item.is_file():
                            if not extensions or item.suffix in extensions:
                                files.append(item.name)
                        elif item.is_dir():
                            dirs.append(item.name + "/")

            # Sort results
            files.sort()
            dirs.sort()

            # Format output
            result_lines = []
            if dirs:
                result_lines.append("Directories:")
                result_lines.extend(f"  {d}" for d in dirs)

            if files:
                if dirs:
                    result_lines.append("")
                result_lines.append("Files:")
                result_lines.extend(f"  {f}" for f in files)

            if not dirs and not files:
                result_lines.append("(empty directory)")

            return ErrorHandler.create_success_result(
                "\n".join(result_lines),
                {
                    "file_count": len(files),
                    "dir_count": len(dirs),
                    "total_items": len(files) + len(dirs),
                    "path": str(validated_path),
                },
            )

        except Exception as e:
            return ErrorHandler.handle_exception(
                e, f"FileListTool.execute(path={kwargs.get('path')})"
            )


class FileSearchTool(Tool):
    """Tool for searching file contents with enhanced pattern matching."""

    @property
    def definition(self) -> ToolDefinition:
        """Define the file_search (find) tool specification.

        Returns:
            ToolDefinition with parameters for searching files by name
            or content including path, pattern, name_only, and recursive options.
        """
        return ToolDefinition(
            name="file_search",
            description="Search for text patterns in files",
            category="File Operations",
            parameters=[
                ToolParameter(
                    name="pattern",
                    type="string",
                    description="Text pattern to search for (supports regex)",
                    required=True,
                ),
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to search in (default: current directory)",
                    required=False,
                    default=".",
                ),
                ToolParameter(
                    name="extensions",
                    type="array",
                    description="File extensions to search in",
                    required=False,
                ),
                ToolParameter(
                    name="case_sensitive",
                    type="boolean",
                    description="Case sensitive search",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="max_results",
                    type="number",
                    description="Maximum number of results to return",
                    required=False,
                    default=50,
                ),
                ToolParameter(
                    name="context_lines",
                    type="number",
                    description="Number of context lines to show around matches",
                    required=False,
                    default=0,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Search for pattern in files with context support."""
        try:
            pattern = kwargs.get("pattern")
            if not pattern:
                return ErrorHandler.create_error_result(
                    "Pattern is required for searching",
                    ErrorType.VALIDATION_ERROR,
                )
            path = kwargs.get("path", ".")
            extensions = kwargs.get("extensions")
            case_sensitive = kwargs.get("case_sensitive", False)
            max_results = kwargs.get("max_results", 50)
            context_lines = kwargs.get("context_lines", 0)

            # Validate path
            is_valid, error_msg, validated_path = path_validator.validate_path(
                path, check_exists=True
            )
            if not is_valid or validated_path is None:
                return ErrorHandler.create_error_result(
                    f"Path validation failed: {error_msg}",
                    ErrorType.SECURITY_ERROR,
                    {"path": path},
                )

            # Compile regex pattern
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                regex = re.compile(pattern, flags)
            except re.error as e:
                return ErrorHandler.create_error_result(
                    f"Invalid regex pattern: {str(e)}",
                    ErrorType.VALIDATION_ERROR,
                    {"pattern": pattern},
                )

            results: List[Dict[str, Any]] = []
            files_searched = 0
            files_with_matches = 0

            # Determine files to search
            if validated_path.is_file():
                files_to_search = [validated_path]
            else:
                files_to_search = []
                for file_path in validated_path.rglob("*"):
                    if file_path.is_file():
                        if extensions and file_path.suffix not in extensions:
                            continue
                        # Skip binary files
                        if file_path.suffix in [
                            ".exe",
                            ".dll",
                            ".so",
                            ".dylib",
                            ".bin",
                            ".jpg",
                            ".png",
                            ".gif",
                            ".pdf",
                        ]:
                            continue
                        files_to_search.append(file_path)

            # Search files
            for file_path in files_to_search:
                if len(results) >= max_results:
                    break

                try:
                    # Check file size to avoid huge files
                    if file_path.stat().st_size > 10 * 1024 * 1024:  # 10MB
                        continue

                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()

                    files_searched += 1
                    file_has_match = False

                    # Search lines
                    for line_num, line in enumerate(lines):
                        if len(results) >= max_results:
                            break

                        if regex.search(line):
                            file_has_match = True

                            # Get context lines
                            context_before = []
                            context_after = []

                            if context_lines > 0:
                                start = max(0, line_num - context_lines)
                                end = min(len(lines), line_num + context_lines + 1)

                                for i in range(start, line_num):
                                    context_before.append((i + 1, lines[i].rstrip()))

                                for i in range(line_num + 1, end):
                                    context_after.append((i + 1, lines[i].rstrip()))

                            results.append(
                                {
                                    "file": str(
                                        file_path.relative_to(validated_path)
                                        if validated_path.is_dir()
                                        else file_path
                                    ),
                                    "line": line_num + 1,
                                    "text": line.rstrip(),
                                    "context_before": context_before,
                                    "context_after": context_after,
                                }
                            )

                    if file_has_match:
                        files_with_matches += 1

                except (UnicodeDecodeError, PermissionError, OSError):
                    # Skip files that can't be read
                    continue

            # Format results
            if not results:
                output = f"No matches found for pattern '{pattern}'"
            else:
                output_lines = [
                    f"Found {len(results)} matches in {files_with_matches} files:"
                ]

                for result in results:
                    output_lines.append(f"\n{result['file']}:{result['line']}:")

                    # Show context before
                    for line_num, text in result["context_before"]:
                        output_lines.append(f"  {line_num}: {text}")

                    # Show matching line (highlighted)
                    output_lines.append(f"> {result['line']}: {result['text']}")

                    # Show context after
                    for line_num, text in result["context_after"]:
                        output_lines.append(f"  {line_num}: {text}")

                output = "\n".join(output_lines)

            return ErrorHandler.create_success_result(
                output,
                {
                    "matches": len(results),
                    "files_searched": files_searched,
                    "files_with_matches": files_with_matches,
                    "pattern": pattern,
                },
            )

        except Exception as e:
            return ErrorHandler.handle_exception(
                e, f"FileSearchTool.execute(pattern={kwargs.get('pattern')})"
            )
