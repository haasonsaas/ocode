"""
Safe parsing utilities for JSON and YAML with size validation and streaming support.

This module provides safe parsing functions that prevent memory exhaustion from
extremely large files while maintaining compatibility with existing code.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Union

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

logger = logging.getLogger(__name__)


class FileSizeError(Exception):
    """Raised when a file exceeds the maximum allowed size for parsing."""

    def __init__(self, message: str, file_size: int, max_size: int):
        super().__init__(message)
        self.file_size = file_size
        self.max_size = max_size


class ParseError(Exception):
    """Raised when parsing fails due to invalid content or other errors."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


# Default size limits (in bytes)
DEFAULT_JSON_MAX_SIZE = 50 * 1024 * 1024  # 50MB
DEFAULT_YAML_MAX_SIZE = 10 * 1024 * 1024  # 10MB (YAML is typically slower to parse)
STREAMING_CHUNK_SIZE = 8192  # 8KB chunks for streaming


def get_file_size(file_path: Union[str, Path]) -> int:
    """Get the size of a file in bytes."""
    try:
        return os.path.getsize(file_path)
    except OSError as e:
        raise ParseError(f"Unable to get file size for {file_path}: {e}")


def validate_file_size(
    file_path: Union[str, Path], max_size: int, format_name: str = "file"
) -> None:
    """
    Validate that a file is not larger than the maximum allowed size.

    Args:
        file_path: Path to the file to validate
        max_size: Maximum allowed size in bytes
        format_name: Name of the format for error messages

    Raises:
        FileSizeError: If the file exceeds the maximum size
        ParseError: If unable to check file size
    """
    file_size = get_file_size(file_path)

    if file_size > max_size:
        raise FileSizeError(
            f"{format_name} file {file_path} is {file_size:,} bytes, "
            f"which exceeds the maximum allowed size of {max_size:,} bytes",
            file_size=file_size,
            max_size=max_size,
        )

    logger.debug(f"File size validation passed: {file_path} ({file_size:,} bytes)")


def safe_json_load(
    file_path: Union[str, Path],
    max_size: int = DEFAULT_JSON_MAX_SIZE,
    encoding: str = "utf-8",
) -> Any:
    """
    Safely load JSON from a file with size validation.

    Args:
        file_path: Path to the JSON file
        max_size: Maximum allowed file size in bytes
        encoding: File encoding

    Returns:
        Parsed JSON object

    Raises:
        FileSizeError: If file exceeds maximum size
        ParseError: If JSON parsing fails
    """
    file_path = Path(file_path)

    # Validate file size before loading
    validate_file_size(file_path, max_size, "JSON")

    try:
        with open(file_path, "r", encoding=encoding) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON in {file_path}: {e}", original_error=e)
    except OSError as e:
        raise ParseError(f"Unable to read JSON file {file_path}: {e}", original_error=e)


def safe_json_loads(json_string: str, max_size: int = DEFAULT_JSON_MAX_SIZE) -> Any:
    """
    Safely parse JSON from a string with size validation.

    Args:
        json_string: JSON string to parse
        max_size: Maximum allowed string size in bytes

    Returns:
        Parsed JSON object

    Raises:
        FileSizeError: If string exceeds maximum size
        ParseError: If JSON parsing fails
    """
    string_size = len(json_string.encode("utf-8"))

    if string_size > max_size:
        raise FileSizeError(
            f"JSON string is {string_size:,} bytes, "
            f"which exceeds the maximum allowed size of {max_size:,} bytes",
            file_size=string_size,
            max_size=max_size,
        )

    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON string: {e}", original_error=e)


def safe_yaml_load(
    file_path: Union[str, Path],
    max_size: int = DEFAULT_YAML_MAX_SIZE,
    encoding: str = "utf-8",
) -> Any:
    """
    Safely load YAML from a file with size validation.

    Args:
        file_path: Path to the YAML file
        max_size: Maximum allowed file size in bytes
        encoding: File encoding

    Returns:
        Parsed YAML object

    Raises:
        FileSizeError: If file exceeds maximum size
        ParseError: If YAML parsing fails or PyYAML not available
    """
    if not YAML_AVAILABLE:
        raise ParseError("PyYAML is not installed. Install it with: pip install PyYAML")

    file_path = Path(file_path)

    # Validate file size before loading
    validate_file_size(file_path, max_size, "YAML")

    try:
        with open(file_path, "r", encoding=encoding) as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ParseError(f"Invalid YAML in {file_path}: {e}", original_error=e)
    except OSError as e:
        raise ParseError(f"Unable to read YAML file {file_path}: {e}", original_error=e)


def safe_yaml_loads(yaml_string: str, max_size: int = DEFAULT_YAML_MAX_SIZE) -> Any:
    """
    Safely parse YAML from a string with size validation.

    Args:
        yaml_string: YAML string to parse
        max_size: Maximum allowed string size in bytes

    Returns:
        Parsed YAML object

    Raises:
        FileSizeError: If string exceeds maximum size
        ParseError: If YAML parsing fails or PyYAML not available
    """
    if not YAML_AVAILABLE:
        raise ParseError("PyYAML is not installed. Install it with: pip install PyYAML")

    string_size = len(yaml_string.encode("utf-8"))

    if string_size > max_size:
        raise FileSizeError(
            f"YAML string is {string_size:,} bytes, "
            f"which exceeds the maximum allowed size of {max_size:,} bytes",
            file_size=string_size,
            max_size=max_size,
        )

    try:
        return yaml.safe_load(yaml_string)
    except yaml.YAMLError as e:
        raise ParseError(f"Invalid YAML string: {e}", original_error=e)


def stream_json_objects(
    file_path: Union[str, Path], encoding: str = "utf-8"
) -> Iterator[Dict[str, Any]]:
    """
    Stream JSON objects from a file containing multiple JSON objects.

    This function assumes each line in the file is a separate JSON object
    (JSON Lines format). For true streaming of large single JSON objects,
    consider using a specialized streaming JSON parser.

    Args:
        file_path: Path to the JSON file
        encoding: File encoding

    Yields:
        Individual JSON objects

    Raises:
        ParseError: If file reading or JSON parsing fails
    """
    file_path = Path(file_path)

    try:
        with open(file_path, "r", encoding=encoding) as f:
            line_number = 0
            for line in f:
                line_number += 1
                line = line.strip()

                if not line:  # Skip empty lines
                    continue

                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Skipping invalid JSON on line {line_number} "
                        f"in {file_path}: {e}"
                    )
                    continue

    except OSError as e:
        raise ParseError(f"Unable to read JSON file {file_path}: {e}", original_error=e)


def stream_yaml_documents(
    file_path: Union[str, Path], encoding: str = "utf-8"
) -> Iterator[Any]:
    """
    Stream YAML documents from a file containing multiple YAML documents.

    Args:
        file_path: Path to the YAML file
        encoding: File encoding

    Yields:
        Individual YAML documents

    Raises:
        ParseError: If file reading, YAML parsing fails, or PyYAML not available
    """
    if not YAML_AVAILABLE:
        raise ParseError("PyYAML is not installed. Install it with: pip install PyYAML")

    file_path = Path(file_path)

    try:
        with open(file_path, "r", encoding=encoding) as f:
            try:
                for document in yaml.safe_load_all(f):
                    if document is not None:  # Skip empty documents
                        yield document
            except yaml.YAMLError as e:
                raise ParseError(f"Invalid YAML in {file_path}: {e}", original_error=e)

    except OSError as e:
        raise ParseError(f"Unable to read YAML file {file_path}: {e}", original_error=e)


def safe_json_dump(
    obj: Any,
    file_path: Union[str, Path],
    encoding: str = "utf-8",
    indent: Optional[int] = 2,
    **kwargs,
) -> None:
    """
    Safely dump JSON to a file.

    Args:
        obj: Object to serialize to JSON
        file_path: Path to write the JSON file
        encoding: File encoding
        indent: JSON indentation
        **kwargs: Additional arguments for json.dump

    Raises:
        ParseError: If JSON serialization or file writing fails
    """
    file_path = Path(file_path)

    try:
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding=encoding) as f:
            json.dump(obj, f, indent=indent, **kwargs)

    except (TypeError, ValueError) as e:
        raise ParseError(f"Unable to serialize object to JSON: {e}", original_error=e)
    except OSError as e:
        raise ParseError(
            f"Unable to write JSON file {file_path}: {e}", original_error=e
        )


def safe_yaml_dump(
    obj: Any, file_path: Union[str, Path], encoding: str = "utf-8", **kwargs
) -> None:
    """
    Safely dump YAML to a file.

    Args:
        obj: Object to serialize to YAML
        file_path: Path to write the YAML file
        encoding: File encoding
        **kwargs: Additional arguments for yaml.dump

    Raises:
        ParseError: If YAML serialization, file writing fails, or PyYAML not available
    """
    if not YAML_AVAILABLE:
        raise ParseError("PyYAML is not installed. Install it with: pip install PyYAML")

    file_path = Path(file_path)

    try:
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Set default YAML dump options for better output
        dump_kwargs = {
            "default_flow_style": False,
            "sort_keys": False,
            "allow_unicode": True,
            **kwargs,
        }

        with open(file_path, "w", encoding=encoding) as f:
            yaml.dump(obj, f, **dump_kwargs)

    except yaml.YAMLError as e:
        raise ParseError(f"Unable to serialize object to YAML: {e}", original_error=e)
    except OSError as e:
        raise ParseError(
            f"Unable to write YAML file {file_path}: {e}", original_error=e
        )


# Convenience functions for backward compatibility and ease of use
def load_json(file_path: Union[str, Path], **kwargs) -> Any:
    """Load JSON file safely (convenience function)."""
    return safe_json_load(file_path, **kwargs)


def load_yaml(file_path: Union[str, Path], **kwargs) -> Any:
    """Load YAML file safely (convenience function)."""
    return safe_yaml_load(file_path, **kwargs)


def parse_json(json_string: str, **kwargs) -> Any:
    """Parse JSON string safely (convenience function)."""
    return safe_json_loads(json_string, **kwargs)


def parse_yaml(yaml_string: str, **kwargs) -> Any:
    """Parse YAML string safely (convenience function)."""
    return safe_yaml_loads(yaml_string, **kwargs)
