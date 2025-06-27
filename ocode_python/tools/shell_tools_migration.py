"""
Migration utilities for transitioning to enhanced shell tools.

This module provides compatibility layers and migration helpers
to smoothly transition from the original ShellCommandTool to
the enhanced version with process management.
"""

import warnings
from typing import Any, Optional

from .base import ToolResult
from .shell_tools import ShellCommandTool
from .shell_tools_enhanced import EnhancedShellCommandTool


class MigrationShellCommandTool(EnhancedShellCommandTool):
    """
    Drop-in replacement for ShellCommandTool with compatibility layer.

    This class provides the same interface as ShellCommandTool but uses
    the enhanced implementation under the hood. It includes compatibility
    shims for any interface differences.
    """

    def __init__(self, use_legacy: bool = False):
        """
        Initialize migration tool.

        Args:
            use_legacy: If True, fall back to legacy implementation
                       for specific commands or conditions
        """
        super().__init__()
        self.use_legacy = use_legacy
        self._legacy_tool = ShellCommandTool() if use_legacy else None

    @property
    def definition(self):
        """Use the same definition name as original for compatibility."""
        definition = super().definition
        # Override name to match original
        definition.name = "shell_command"
        return definition

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute command with compatibility handling.

        Provides compatibility layer for legacy callers while using
        enhanced implementation where possible.
        """
        # Check if we should use legacy implementation
        if self._should_use_legacy(kwargs):
            warnings.warn(
                "Using legacy ShellCommandTool implementation. "
                "Consider updating to use enhanced features.",
                DeprecationWarning,
                stacklevel=2,
            )
            if self._legacy_tool:
                return await self._legacy_tool.execute(**kwargs)

        # Map legacy parameters to new ones if needed
        kwargs = self._map_legacy_params(kwargs)

        # Execute with enhanced implementation
        result = await super().execute(**kwargs)

        # Map result format if needed for compatibility
        return self._map_result_format(result, kwargs)

    def _should_use_legacy(self, kwargs: dict) -> bool:
        """
        Determine if legacy implementation should be used.

        Returns True for edge cases that might not work correctly
        with the enhanced implementation.
        """
        if not self.use_legacy:
            return False

        command = kwargs.get("command", "")

        # List of patterns that might need legacy behavior
        legacy_patterns: list[str] = [
            # Add specific commands that need legacy behavior
            # Example: "special_legacy_command",
        ]

        for pattern in legacy_patterns:
            if pattern in command:
                return True

        return False

    def _map_legacy_params(self, kwargs: dict) -> dict:
        """Map legacy parameter names/values to new ones."""
        mapped = kwargs.copy()

        # The enhanced tool has additional parameters that legacy doesn't
        # Set reasonable defaults for them if not provided
        if "max_output_size" not in mapped:
            mapped["max_output_size"] = 10  # 10MB default

        if "kill_timeout" not in mapped:
            mapped["kill_timeout"] = 5.0

        # Handle any parameter name changes
        # (Currently none, but this is where they would go)

        return mapped

    def _map_result_format(self, result: ToolResult, kwargs: dict) -> ToolResult:
        """
        Map enhanced result format to legacy format if needed.

        Ensures backward compatibility for code expecting specific
        result formats.
        """
        # The enhanced tool includes stderr in metadata
        # Legacy tool might have included it differently

        # Currently the formats are compatible, but this method
        # provides a place to handle any differences

        return result


class ShellToolsMigrationHelper:
    """Helper class for migrating shell tools usage."""

    @staticmethod
    def analyze_usage(code: str) -> dict:
        """
        Analyze code for ShellCommandTool usage patterns.

        Args:
            code: Source code to analyze

        Returns:
            Dictionary with migration suggestions
        """
        suggestions = {
            "uses_shell_command_tool": False,
            "uses_timeout": False,
            "uses_working_dir": False,
            "uses_capture_output": False,
            "migration_complexity": "low",
            "suggestions": [],
        }

        if "ShellCommandTool" in code:
            suggestions["uses_shell_command_tool"] = True

        if "timeout=" in code or '"timeout"' in code:
            suggestions["uses_timeout"] = True

        if "working_dir=" in code or '"working_dir"' in code:
            suggestions["uses_working_dir"] = True

        if "capture_output=" in code or '"capture_output"' in code:
            suggestions["uses_capture_output"] = True

        # Add migration suggestions
        if suggestions["uses_shell_command_tool"]:
            suggestions["suggestions"].append(
                "Replace 'from ocode_python.tools.shell_tools import ShellCommandTool' "
                "with 'from ocode_python.tools.shell_tools_enhanced import EnhancedShellCommandTool'"
            )

            suggestions["suggestions"].append(
                "Consider using new features: max_output_size, cpu_limit, memory_limit"
            )

        # Assess complexity
        feature_count = sum(
            [
                suggestions["uses_timeout"],
                suggestions["uses_working_dir"],
                suggestions["uses_capture_output"],
            ]
        )

        if feature_count == 0:
            suggestions["migration_complexity"] = "low"
        elif feature_count <= 2:
            suggestions["migration_complexity"] = "medium"
        else:
            suggestions["migration_complexity"] = "high"

        return suggestions

    @staticmethod
    def generate_migration_code(original_code: str) -> str:
        """
        Generate migrated code from original.

        Args:
            original_code: Original code using ShellCommandTool

        Returns:
            Migrated code using EnhancedShellCommandTool
        """
        migrated = original_code

        # Replace imports
        migrated = migrated.replace(
            "from ocode_python.tools.shell_tools import ShellCommandTool",
            "from ocode_python.tools.shell_tools_enhanced import EnhancedShellCommandTool",
        )

        migrated = migrated.replace(
            "from .shell_tools import ShellCommandTool",
            "from .shell_tools_enhanced import EnhancedShellCommandTool",
        )

        # Replace class instantiation
        migrated = migrated.replace("ShellCommandTool()", "EnhancedShellCommandTool()")

        # Add migration comment
        if "EnhancedShellCommandTool" in migrated and "# Migrated from" not in migrated:
            lines = migrated.split("\n")
            for i, line in enumerate(lines):
                if "EnhancedShellCommandTool" in line and "import" in line:
                    lines.insert(
                        i + 1,
                        "# Migrated from ShellCommandTool - consider using new features",
                    )
                    break
            migrated = "\n".join(lines)

        return migrated


def create_compatibility_shell_tool() -> MigrationShellCommandTool:
    """
    Create a shell command tool with maximum compatibility.

    Returns:
        MigrationShellCommandTool configured for compatibility
    """
    return MigrationShellCommandTool(use_legacy=True)
