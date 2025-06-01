"""
Centralized path validation utility for all file operations.
Provides robust validation against path traversal attacks and other security issues.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Tuple, Union


class PathValidator:
    """Centralized path validation for security and reliability."""

    def __init__(self):
        """Initialize path validator with platform-specific settings."""
        self.platform = sys.platform
        self.separator = os.sep
        self.alt_separator = os.altsep or ""

        # Platform-specific forbidden path segments
        self.forbidden_segments = {
            "..",  # Parent directory traversal
            "...",  # Extended parent traversal
            "~",  # Home directory expansion (when at start)
        }

        # Platform-specific dangerous characters
        if self.platform.startswith("win"):
            # Note: colon is allowed in drive letters (C:), but dangerous elsewhere
            self.dangerous_chars = set('<>"|?*\x00')
            self.reserved_names = {
                "CON",
                "PRN",
                "AUX",
                "NUL",
                "COM1",
                "COM2",
                "COM3",
                "COM4",
                "COM5",
                "COM6",
                "COM7",
                "COM8",
                "COM9",
                "LPT1",
                "LPT2",
                "LPT3",
                "LPT4",
                "LPT5",
                "LPT6",
                "LPT7",
                "LPT8",
                "LPT9",
            }
        else:
            self.dangerous_chars = set("\x00")
            self.reserved_names = set()

    def validate_path(
        self,
        path: Union[str, Path],
        base_path: Optional[Union[str, Path]] = None,
        allow_symlinks: bool = False,
        check_exists: bool = False,
    ) -> Tuple[bool, str, Optional[Path]]:
        """
        Validate a path for security and correctness.

        Args:
            path: Path to validate
            base_path: Optional base path to ensure path stays within
            allow_symlinks: Whether to allow symbolic links
            check_exists: Whether to check if path exists

        Returns:
            Tuple of (is_valid, error_message, normalized_path)
        """
        try:
            # Convert to string for validation
            path_str = str(path)

            # Check for null bytes
            if "\x00" in path_str:
                return False, "Path contains null bytes", None

            # Check for dangerous characters
            for char in path_str:
                if char in self.dangerous_chars:
                    return (
                        False,
                        f"Path contains forbidden character: {repr(char)}",
                        None,
                    )

            # Special handling for colons on Windows
            if self.platform.startswith("win") and ":" in path_str:
                # Allow drive letters (C:, D:, etc.) but block alternate data streams
                import re

                # Check for valid Windows drive patterns
                drive_pattern = r"^[A-Za-z]:[/\\]"  # C:\ or C:/
                drive_only_pattern = r"^[A-Za-z]:$"  # C:

                # Count colons - should only be one for drive letter
                colon_count = path_str.count(":")

                if colon_count > 1:
                    return (
                        False,
                        "Invalid colon usage (alternate data streams not allowed)",
                        None,
                    )
                elif colon_count == 1:
                    # Must be a drive letter pattern
                    if not (
                        re.match(drive_pattern, path_str)
                        or re.match(drive_only_pattern, path_str)
                    ):
                        return (
                            False,
                            "Invalid colon usage (must be drive letter like C:)",
                            None,
                        )

            # Check for path traversal attempts
            if self._has_path_traversal(path_str):
                return False, "Path traversal detected", None

            # Normalize the path
            try:
                normalized = Path(path_str).resolve()
            except (RuntimeError, OSError) as e:
                # Handle path resolution errors (e.g., too many symlinks)
                return False, f"Path resolution failed: {str(e)}", None

            # Check for reserved names on Windows
            if self.platform.startswith("win"):
                name = normalized.name.upper().split(".")[0]
                if name in self.reserved_names:
                    return False, f"Path uses reserved name: {name}", None

            # Validate against base path if provided
            if base_path:
                try:
                    base_normalized = Path(base_path).resolve()
                    if not self._is_subpath(normalized, base_normalized):
                        return False, "Path escapes base directory", None
                except Exception as e:
                    return False, f"Base path validation failed: {str(e)}", None

            # Check for symbolic links if not allowed
            if not allow_symlinks and normalized.exists() and normalized.is_symlink():
                return False, "Symbolic links not allowed", None

            # Check existence if requested
            if check_exists and not normalized.exists():
                return False, "Path does not exist", None

            # Additional platform-specific validations
            if self.platform.startswith("win"):
                # Check for alternate data streams
                if ":" in str(normalized) and not normalized.is_absolute():
                    return False, "Alternate data streams not allowed", None

            return True, "Path is valid", normalized

        except Exception as e:
            return False, f"Validation error: {str(e)}", None

    def _has_path_traversal(self, path: str) -> bool:
        """Check if path contains traversal attempts."""
        # Split by both separators
        parts = (
            path.replace(self.alt_separator, self.separator).split(self.separator)
            if self.alt_separator
            else path.split(self.separator)
        )

        for part in parts:
            # Check for forbidden segments
            if part in self.forbidden_segments:
                return True

            # Check for encoded traversal attempts
            if "%2e%2e" in part.lower() or "%252e%252e" in part.lower():
                return True

            # Check for Unicode normalization attacks
            try:
                import unicodedata

                normalized = unicodedata.normalize("NFKC", part)
                if ".." in normalized and ".." not in part:
                    return True
            except Exception:
                # Intentionally ignore exceptions when checking symlinks
                # as they may not exist or be accessible
                pass  # nosec B110

        return False

    def _is_subpath(self, child: Path, parent: Path) -> bool:
        """Check if child is a subpath of parent."""
        try:
            # Resolve both paths to handle symlinks
            child_resolved = child.resolve()
            parent_resolved = parent.resolve()

            # Check if child is relative to parent
            child_resolved.relative_to(parent_resolved)
            return True
        except ValueError:
            return False

    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize a filename for safe file creation.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Remove path separators
        filename = filename.replace(self.separator, "_")
        if self.alt_separator:
            filename = filename.replace(self.alt_separator, "_")

        # Remove dangerous characters
        sanitized = "".join(
            c if c not in self.dangerous_chars else "_" for c in filename
        )

        # Handle reserved names on Windows
        if self.platform.startswith("win"):
            name_parts = sanitized.split(".")
            if name_parts[0].upper() in self.reserved_names:
                name_parts[0] = f"_{name_parts[0]}"
                sanitized = ".".join(name_parts)

        # Ensure filename is not empty
        if not sanitized or sanitized == ".":
            sanitized = "unnamed"

        # Limit length
        max_length = 255
        if len(sanitized) > max_length:
            # Preserve extension if possible
            parts = sanitized.rsplit(".", 1)
            if len(parts) == 2 and len(parts[1]) < 10:
                base_max = max_length - len(parts[1]) - 1
                sanitized = f"{parts[0][:base_max]}.{parts[1]}"
            else:
                sanitized = sanitized[:max_length]

        return sanitized

    def validate_relative_path(self, path: str) -> Tuple[bool, str]:
        """
        Validate that a path is relative and safe.

        Args:
            path: Path to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        path_obj = Path(path)

        # Check if path is absolute
        if path_obj.is_absolute():
            return False, "Path must be relative"

        # Check for traversal
        if self._has_path_traversal(path):
            return False, "Path traversal detected in relative path"

        # Normalize and check again
        try:
            # Use os.path.normpath for relative path normalization
            normalized = os.path.normpath(path)
            if normalized.startswith(".."):
                return False, "Normalized path escapes current directory"
        except Exception as e:
            return False, f"Path normalization failed: {str(e)}"

        return True, "Relative path is valid"

    def get_safe_path(
        self,
        user_input: str,
        base_path: Optional[Union[str, Path]] = None,
        must_exist: bool = False,
    ) -> Optional[Path]:
        """
        Get a safe, validated path from user input.

        Args:
            user_input: User-provided path
            base_path: Optional base directory to constrain to
            must_exist: Whether path must exist

        Returns:
            Validated Path object or None if invalid
        """
        is_valid, error_msg, normalized = self.validate_path(
            user_input, base_path=base_path, check_exists=must_exist
        )

        if is_valid and normalized:
            return normalized

        return None


# Global validator instance
_validator = PathValidator()


# Convenience functions
def validate_path(
    path: Union[str, Path],
    base_path: Optional[Union[str, Path]] = None,
    allow_symlinks: bool = False,
    check_exists: bool = False,
) -> Tuple[bool, str, Optional[Path]]:
    """Validate a path using the global validator."""
    return _validator.validate_path(path, base_path, allow_symlinks, check_exists)


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename using the global validator."""
    return _validator.sanitize_filename(filename)


def validate_relative_path(path: str) -> Tuple[bool, str]:
    """Validate a relative path using the global validator."""
    return _validator.validate_relative_path(path)


def get_safe_path(
    user_input: str,
    base_path: Optional[Union[str, Path]] = None,
    must_exist: bool = False,
) -> Optional[Path]:
    """Get a safe path from user input using the global validator."""
    return _validator.get_safe_path(user_input, base_path, must_exist)
