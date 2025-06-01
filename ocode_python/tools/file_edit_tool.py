"""
File editing tool for in-place modifications, replacements, and transformations.
"""

import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import Tool, ToolDefinition, ToolParameter, ToolResult


class FileEditTool(Tool):
    """Tool for in-place file editing operations."""

    @property
    def definition(self) -> ToolDefinition:
        """Define the file_edit tool specification.

        Returns:
            ToolDefinition with parameters for in-place file editing including
            replace, insert, delete, append, and prepend operations.
        """
        return ToolDefinition(
            name="file_edit",
            description="Edit files in-place with find/replace, line operations, and transformations",  # noqa: E501
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to the file to edit",
                    required=True,
                ),
                ToolParameter(
                    name="operation",
                    type="string",
                    description="Edit operation: 'replace', 'insert', 'delete', 'append', 'prepend'",  # noqa: E501
                    required=True,
                ),
                ToolParameter(
                    name="content",
                    type="string",
                    description="Content to insert/append/prepend (for insert/append/prepend operations)",  # noqa: E501
                    required=False,
                ),
                ToolParameter(
                    name="search_pattern",
                    type="string",
                    description="Pattern to search for (for replace/delete operations)",
                    required=False,
                ),
                ToolParameter(
                    name="replacement",
                    type="string",
                    description="Replacement text (for replace operation)",
                    required=False,
                ),
                ToolParameter(
                    name="line_number",
                    type="number",
                    description="Specific line number to operate on (1-based, for insert/delete)",  # noqa: E501
                    required=False,
                ),
                ToolParameter(
                    name="line_range",
                    type="object",
                    description='Line range {"start": 1, "end": 10} (for delete operation)',  # noqa: E501
                    required=False,
                ),
                ToolParameter(
                    name="regex",
                    type="boolean",
                    description="Treat search_pattern as regex",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="case_sensitive",
                    type="boolean",
                    description="Case-sensitive search",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="whole_word",
                    type="boolean",
                    description="Match whole words only",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="max_replacements",
                    type="number",
                    description="Maximum number of replacements (0 = unlimited)",
                    required=False,
                    default=0,
                ),
                ToolParameter(
                    name="backup",
                    type="boolean",
                    description="Create backup file before editing",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="dry_run",
                    type="boolean",
                    description="Show what would be changed without making changes",
                    required=False,
                    default=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute file editing operation."""
        try:
            # Extract parameters
            path = kwargs.get("path")
            operation = kwargs.get("operation")
            content = kwargs.get("content")
            search_pattern = kwargs.get("search_pattern")
            replacement = kwargs.get("replacement")
            line_number = kwargs.get("line_number")
            line_range = kwargs.get("line_range")
            regex = kwargs.get("regex", False)
            case_sensitive = kwargs.get("case_sensitive", True)
            whole_word = kwargs.get("whole_word", False)
            max_replacements = kwargs.get("max_replacements", 0)
            backup = kwargs.get("backup", True)
            dry_run = kwargs.get("dry_run", False)

            if not path:
                return ToolResult(
                    success=False, output="", error="path parameter is required"
                )

            if not operation:
                return ToolResult(
                    success=False, output="", error="operation parameter is required"
                )

            file_path = Path(path).resolve()

            if not file_path.exists():
                return ToolResult(
                    success=False, output="", error=f"File does not exist: {path}"
                )

            if not file_path.is_file():
                return ToolResult(
                    success=False, output="", error=f"Path is not a file: {path}"
                )

            # Read current file content
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    original_content = f.read()
                    original_lines = original_content.splitlines(keepends=True)
            except UnicodeDecodeError:
                return ToolResult(
                    success=False, output="", error=f"Cannot read file as UTF-8: {path}"
                )

            # Perform the editing operation
            if operation == "replace":
                result = await self._replace_operation(
                    original_content,
                    search_pattern,
                    replacement,
                    regex,
                    case_sensitive,
                    whole_word,
                    max_replacements,
                )
            elif operation == "insert":
                result = await self._insert_operation(
                    original_lines, content, line_number
                )
            elif operation == "delete":
                result = await self._delete_operation(
                    original_lines,
                    search_pattern,
                    line_number,
                    line_range,
                    regex,
                    case_sensitive,
                    whole_word,
                )
            elif operation == "append":
                result = await self._append_operation(original_content, content)
            elif operation == "prepend":
                result = await self._prepend_operation(original_content, content)
            else:
                return ToolResult(
                    success=False, output="", error=f"Unknown operation: {operation}"
                )

            if not result["success"]:
                return ToolResult(success=False, output="", error=result["error"])

            new_content = result["content"]
            changes = result["changes"]

            # Format output
            output_lines = [f"File edit operation: {operation}"]

            if dry_run:
                output_lines.append("DRY RUN - No changes made")

            output_lines.append(f"File: {file_path}")
            output_lines.extend(changes)

            if dry_run:
                # Show preview of changes
                if new_content != original_content:
                    output_lines.append("\\nPreview of changes:")
                    output_lines.append(
                        self._create_diff_preview(original_content, new_content)
                    )
                else:
                    output_lines.append("\\nNo changes would be made.")
            else:
                # Actually write the file
                if new_content != original_content:
                    # Create backup if requested
                    if backup:
                        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
                        shutil.copy2(file_path, backup_path)
                        output_lines.append(f"Backup created: {backup_path}")

                    # Write new content
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_content)

                    output_lines.append("File updated successfully")
                else:
                    output_lines.append("No changes made - content unchanged")

            return ToolResult(
                success=True,
                output="\\n".join(output_lines),
                metadata={
                    "operation": operation,
                    "file_path": str(file_path),
                    "changes_made": len(changes) > 0,
                    "dry_run": dry_run,
                    "backup_created": backup
                    and not dry_run
                    and new_content != original_content,
                    "original_size": len(original_content),
                    "new_size": len(new_content),
                },
            )

        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"File edit operation failed: {str(e)}"
            )

    async def _replace_operation(
        self,
        content: str,
        search_pattern: Optional[str],
        replacement: Optional[str],
        regex: bool,
        case_sensitive: bool,
        whole_word: bool,
        max_replacements: int,
    ) -> Dict[str, Any]:
        """Perform find and replace operation."""
        if not search_pattern:
            return {
                "success": False,
                "error": "search_pattern is required for replace operation",
            }

        if replacement is None:
            replacement = ""

        try:
            # Prepare pattern
            if regex:
                pattern = search_pattern
            else:
                pattern = re.escape(search_pattern)

            if whole_word:
                pattern = rf"\b{pattern}\b"

            # Compile regex
            flags = 0 if case_sensitive else re.IGNORECASE
            compiled_pattern = re.compile(pattern, flags)

            # Find matches
            matches = list(compiled_pattern.finditer(content))

            if not matches:
                return {
                    "success": True,
                    "content": content,
                    "changes": ["No matches found for pattern"],
                }

            # Apply replacements
            if max_replacements > 0:
                matches = matches[:max_replacements]

            # Replace in reverse order to maintain positions
            new_content = content
            for match in reversed(matches):
                new_content = (
                    new_content[: match.start()]
                    + replacement
                    + new_content[match.end() :]
                )

            changes = [
                f"Replaced {len(matches)} occurrence(s) of '{search_pattern}' with '{replacement}'"  # noqa: E501
            ]

            return {"success": True, "content": new_content, "changes": changes}

        except re.error as e:
            return {"success": False, "error": f"Invalid regex pattern: {str(e)}"}

    async def _insert_operation(
        self, lines: List[str], content: Optional[str], line_number: Optional[int]
    ) -> Dict[str, Any]:
        """Insert content at specified line."""
        if content is None:
            return {
                "success": False,
                "error": "content is required for insert operation",
            }

        if line_number is None:
            return {
                "success": False,
                "error": "line_number is required for insert operation",
            }

        if line_number < 1 or line_number > len(lines) + 1:
            return {"success": False, "error": f"Invalid line number: {line_number}"}

        # Insert content (line_number is 1-based)
        insert_index = line_number - 1
        new_lines = lines[:insert_index] + [content + "\\n"] + lines[insert_index:]

        changes = [f"Inserted content at line {line_number}"]

        return {"success": True, "content": "".join(new_lines), "changes": changes}

    async def _delete_operation(
        self,
        lines: List[str],
        search_pattern: Optional[str],
        line_number: Optional[int],
        line_range: Optional[Dict[str, int]],
        regex: bool,
        case_sensitive: bool,
        whole_word: bool,
    ) -> Dict[str, Any]:
        """Delete lines based on pattern or line numbers."""
        if line_number is not None:
            # Delete specific line
            if line_number < 1 or line_number > len(lines):
                return {
                    "success": False,
                    "error": f"Invalid line number: {line_number}",
                }

            deleted_line = lines[line_number - 1].rstrip("\\n\\r")
            new_lines = lines[: line_number - 1] + lines[line_number:]
            changes = [f"Deleted line {line_number}: {deleted_line}"]

        elif line_range is not None:
            # Delete line range
            start = line_range.get("start", 1)
            end = line_range.get("end", start)

            if start < 1 or end > len(lines) or start > end:
                return {"success": False, "error": f"Invalid line range: {start}-{end}"}

            new_lines = lines[: start - 1] + lines[end:]
            changes = [f"Deleted lines {start}-{end} ({end - start + 1} lines)"]

        elif search_pattern is not None:
            # Delete lines matching pattern
            try:
                if regex:
                    pattern = search_pattern
                else:
                    pattern = re.escape(search_pattern)

                if whole_word:
                    pattern = rf"\b{pattern}\b"

                flags = 0 if case_sensitive else re.IGNORECASE
                compiled_pattern = re.compile(pattern, flags)

                new_lines = []
                deleted_count = 0

                for i, line in enumerate(lines):
                    if compiled_pattern.search(line):
                        deleted_count += 1
                    else:
                        new_lines.append(line)

                changes = [
                    f"Deleted {deleted_count} line(s) matching pattern '{search_pattern}'"  # noqa: E501
                ]

            except re.error as e:
                return {"success": False, "error": f"Invalid regex pattern: {str(e)}"}
        else:
            return {
                "success": False,
                "error": "line_number, line_range, or search_pattern is required for delete operation",  # noqa: E501
            }

        return {"success": True, "content": "".join(new_lines), "changes": changes}

    async def _append_operation(
        self, content: str, new_content: Optional[str]
    ) -> Dict[str, Any]:
        """Append content to end of file."""
        if new_content is None:
            return {
                "success": False,
                "error": "content is required for append operation",
            }

        # Ensure file ends with newline before appending
        if content and not content.endswith("\\n"):
            content += "\\n"

        new_full_content = content + new_content
        if not new_content.endswith("\\n"):
            new_full_content += "\\n"

        changes = ["Appended content to end of file"]

        return {"success": True, "content": new_full_content, "changes": changes}

    async def _prepend_operation(
        self, content: str, new_content: Optional[str]
    ) -> Dict[str, Any]:
        """Prepend content to beginning of file."""
        if new_content is None:
            return {
                "success": False,
                "error": "content is required for prepend operation",
            }

        # Ensure prepended content ends with newline
        if not new_content.endswith("\\n"):
            new_content += "\\n"

        new_full_content = new_content + content
        changes = ["Prepended content to beginning of file"]

        return {"success": True, "content": new_full_content, "changes": changes}

    def _create_diff_preview(self, original: str, new: str) -> str:
        """Create a simple diff preview."""
        original_lines = original.splitlines()
        new_lines = new.splitlines()

        # Simple diff - show first few changes
        diff_lines = []
        max_lines = 10

        for i, (old_line, new_line) in enumerate(zip(original_lines, new_lines)):
            if old_line != new_line:
                diff_lines.append(f"  {i+1:3d}- {old_line}")
                diff_lines.append(f"  {i+1:3d}+ {new_line}")
                max_lines -= 2
                if max_lines <= 0:
                    diff_lines.append("  ... (truncated)")
                    break

        # Handle length differences
        if len(new_lines) > len(original_lines):
            for i in range(
                len(original_lines),
                min(len(new_lines), len(original_lines) + max_lines),
            ):
                diff_lines.append(f"  {i+1:3d}+ {new_lines[i]}")
        elif len(original_lines) > len(new_lines):
            for i in range(
                len(new_lines), min(len(original_lines), len(new_lines) + max_lines)
            ):
                diff_lines.append(f"  {i+1:3d}- {original_lines[i]}")

        return "\\n".join(diff_lines) if diff_lines else "No preview available"
