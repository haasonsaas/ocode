"""
Resilient file operations with retry logic for handling transient failures.

This module provides file operation utilities that can handle temporary
file locks, permission issues, and other transient file system problems.
"""

import asyncio
import os
import shutil
import time
from pathlib import Path
from typing import Optional, Union

from .retry_handler import FILE_RETRY, RetryConfig, with_retry, with_retry_async
from .structured_errors import FileSystemError, create_error_from_exception


def safe_file_read(
    file_path: Union[str, Path],
    encoding: str = "utf-8",
    retry_config: Optional[RetryConfig] = None,
) -> str:
    """
    Safely read a file with retry logic for transient failures.

    Args:
        file_path: Path to the file to read
        encoding: File encoding
        retry_config: Custom retry configuration (defaults to FILE_RETRY)

    Returns:
        File contents as string

    Raises:
        FileSystemError: If file reading fails after retries
    """
    retry_config = retry_config or FILE_RETRY

    def _read_operation():
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()
        except Exception as e:
            raise create_error_from_exception(
                e,
                "file_read",
                "file_operations",
                {"file_path": str(file_path), "encoding": encoding},
            )

    try:
        result = with_retry(_read_operation, retry_config)
        return str(result)
    except Exception as e:
        if hasattr(e, "last_exception"):
            # This is a RetryError, get the underlying exception
            original = e.last_exception
        else:
            original = e

        # If it's already a FileSystemError, just re-raise it
        if isinstance(original, FileSystemError):
            raise original

        raise create_error_from_exception(
            original,
            "file_read",
            "file_operations",
            {
                "file_path": str(file_path),
                "encoding": encoding,
                "retry_attempts": retry_config.max_attempts,
            },
        )


def safe_file_write(
    file_path: Union[str, Path],
    content: str,
    encoding: str = "utf-8",
    create_dirs: bool = True,
    retry_config: Optional[RetryConfig] = None,
) -> None:
    """
    Safely write to a file with retry logic for transient failures.

    Args:
        file_path: Path to the file to write
        content: Content to write
        encoding: File encoding
        create_dirs: Whether to create parent directories if they don't exist
        retry_config: Custom retry configuration (defaults to FILE_RETRY)

    Raises:
        FileSystemError: If file writing fails after retries
    """
    retry_config = retry_config or FILE_RETRY
    file_path = Path(file_path)

    def _write_operation():
        try:
            if create_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)

            # Use a temporary file for atomic writes
            temp_path = file_path.with_suffix(file_path.suffix + ".tmp")

            try:
                with open(temp_path, "w", encoding=encoding) as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())  # Ensure data is written to disk

                # Atomic move to final location
                if os.name == "nt":  # Windows
                    if file_path.exists():
                        file_path.unlink()
                    temp_path.rename(file_path)
                else:  # Unix-like systems
                    temp_path.rename(file_path)

            except Exception:
                # Clean up temp file on failure
                if temp_path.exists():
                    temp_path.unlink()
                raise

        except Exception as e:
            raise create_error_from_exception(
                e,
                "file_write",
                "file_operations",
                {
                    "file_path": str(file_path),
                    "encoding": encoding,
                    "content_length": len(content),
                },
            )

    try:
        with_retry(_write_operation, retry_config)
    except Exception as e:
        if hasattr(e, "last_exception"):
            original = e.last_exception
        else:
            original = e

        # If it's already a StructuredError, just re-raise it
        if isinstance(original, FileSystemError):
            raise original

        raise create_error_from_exception(
            original,
            "file_write",
            "file_operations",
            {
                "file_path": str(file_path),
                "encoding": encoding,
                "content_length": len(content),
                "retry_attempts": retry_config.max_attempts,
            },
        )


def safe_file_copy(
    src_path: Union[str, Path],
    dst_path: Union[str, Path],
    create_dirs: bool = True,
    retry_config: Optional[RetryConfig] = None,
) -> None:
    """
    Safely copy a file with retry logic for transient failures.

    Args:
        src_path: Source file path
        dst_path: Destination file path
        create_dirs: Whether to create parent directories if they don't exist
        retry_config: Custom retry configuration (defaults to FILE_RETRY)

    Raises:
        FileSystemError: If file copying fails after retries
    """
    retry_config = retry_config or FILE_RETRY
    src_path = Path(src_path)
    dst_path = Path(dst_path)

    def _copy_operation():
        try:
            if create_dirs:
                dst_path.parent.mkdir(parents=True, exist_ok=True)

            shutil.copy2(src_path, dst_path)

        except Exception as e:
            raise create_error_from_exception(
                e,
                "file_copy",
                "file_operations",
                {"src_path": str(src_path), "dst_path": str(dst_path)},
            )

    try:
        with_retry(_copy_operation, retry_config)
    except Exception as e:
        if hasattr(e, "last_exception"):
            original = e.last_exception
        else:
            original = e

        # If it's already a StructuredError, just re-raise it
        if isinstance(original, FileSystemError):
            raise original

        raise create_error_from_exception(
            original,
            "file_copy",
            "file_operations",
            {
                "src_path": str(src_path),
                "dst_path": str(dst_path),
                "retry_attempts": retry_config.max_attempts,
            },
        )


def safe_file_move(
    src_path: Union[str, Path],
    dst_path: Union[str, Path],
    create_dirs: bool = True,
    retry_config: Optional[RetryConfig] = None,
) -> None:
    """
    Safely move a file with retry logic for transient failures.

    Args:
        src_path: Source file path
        dst_path: Destination file path
        create_dirs: Whether to create parent directories if they don't exist
        retry_config: Custom retry configuration (defaults to FILE_RETRY)

    Raises:
        FileSystemError: If file moving fails after retries
    """
    retry_config = retry_config or FILE_RETRY
    src_path = Path(src_path)
    dst_path = Path(dst_path)

    def _move_operation():
        try:
            if create_dirs:
                dst_path.parent.mkdir(parents=True, exist_ok=True)

            shutil.move(str(src_path), str(dst_path))

        except Exception as e:
            raise create_error_from_exception(
                e,
                "file_move",
                "file_operations",
                {"src_path": str(src_path), "dst_path": str(dst_path)},
            )

    try:
        with_retry(_move_operation, retry_config)
    except Exception as e:
        if hasattr(e, "last_exception"):
            original = e.last_exception
        else:
            original = e

        # If it's already a StructuredError, just re-raise it
        if isinstance(original, FileSystemError):
            raise original

        raise create_error_from_exception(
            original,
            "file_move",
            "file_operations",
            {
                "src_path": str(src_path),
                "dst_path": str(dst_path),
                "retry_attempts": retry_config.max_attempts,
            },
        )


def safe_file_delete(
    file_path: Union[str, Path],
    ignore_missing: bool = True,
    retry_config: Optional[RetryConfig] = None,
) -> bool:
    """
    Safely delete a file with retry logic for transient failures.

    Args:
        file_path: Path to the file to delete
        ignore_missing: Whether to ignore if file doesn't exist
        retry_config: Custom retry configuration (defaults to FILE_RETRY)

    Returns:
        True if file was deleted, False if it didn't exist and ignore_missing=True

    Raises:
        FileSystemError: If file deletion fails after retries
    """
    retry_config = retry_config or FILE_RETRY
    file_path = Path(file_path)

    def _delete_operation():
        try:
            if not file_path.exists():
                if ignore_missing:
                    return False
                else:
                    raise FileNotFoundError(f"File not found: {file_path}")

            file_path.unlink()
            return True

        except Exception as e:
            raise create_error_from_exception(
                e,
                "file_delete",
                "file_operations",
                {"file_path": str(file_path), "ignore_missing": ignore_missing},
            )

    try:
        result = with_retry(_delete_operation, retry_config)
        return bool(result)
    except Exception as e:
        if hasattr(e, "last_exception"):
            original = e.last_exception
        else:
            original = e

        # If it's already a StructuredError, just re-raise it
        if isinstance(original, FileSystemError):
            raise original

        raise create_error_from_exception(
            original,
            "file_delete",
            "file_operations",
            {
                "file_path": str(file_path),
                "ignore_missing": ignore_missing,
                "retry_attempts": retry_config.max_attempts,
            },
        )


def safe_directory_create(
    dir_path: Union[str, Path],
    parents: bool = True,
    exist_ok: bool = True,
    retry_config: Optional[RetryConfig] = None,
) -> None:
    """
    Safely create a directory with retry logic for transient failures.

    Args:
        dir_path: Path to the directory to create
        parents: Whether to create parent directories
        exist_ok: Whether to ignore if directory already exists
        retry_config: Custom retry configuration (defaults to FILE_RETRY)

    Raises:
        FileSystemError: If directory creation fails after retries
    """
    retry_config = retry_config or FILE_RETRY
    dir_path = Path(dir_path)

    def _mkdir_operation():
        try:
            dir_path.mkdir(parents=parents, exist_ok=exist_ok)

        except Exception as e:
            raise create_error_from_exception(
                e,
                "directory_create",
                "file_operations",
                {"dir_path": str(dir_path), "parents": parents, "exist_ok": exist_ok},
            )

    try:
        with_retry(_mkdir_operation, retry_config)
    except Exception as e:
        if hasattr(e, "last_exception"):
            original = e.last_exception
        else:
            original = e

        # If it's already a StructuredError, just re-raise it
        if isinstance(original, FileSystemError):
            raise original

        raise create_error_from_exception(
            original,
            "directory_create",
            "file_operations",
            {
                "dir_path": str(dir_path),
                "parents": parents,
                "exist_ok": exist_ok,
                "retry_attempts": retry_config.max_attempts,
            },
        )


# Async versions for async file operations
async def safe_file_read_async(
    file_path: Union[str, Path],
    encoding: str = "utf-8",
    retry_config: Optional[RetryConfig] = None,
) -> str:
    """
    Async version of safe_file_read.

    Args:
        file_path: Path to the file to read
        encoding: File encoding
        retry_config: Custom retry configuration (defaults to FILE_RETRY)

    Returns:
        File contents as string

    Raises:
        FileSystemError: If file reading fails after retries
    """
    retry_config = retry_config or FILE_RETRY

    async def _read_operation():
        # Run blocking I/O in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: safe_file_read(file_path, encoding, RetryConfig(max_attempts=1)),
        )

    try:
        result = await with_retry_async(_read_operation, retry_config)
        return str(result)
    except Exception as e:
        if hasattr(e, "last_exception"):
            original = e.last_exception
        else:
            original = e

        # If it's already a StructuredError, just re-raise it
        if isinstance(original, FileSystemError):
            raise original

        raise create_error_from_exception(
            original,
            "file_read_async",
            "file_operations",
            {
                "file_path": str(file_path),
                "encoding": encoding,
                "retry_attempts": retry_config.max_attempts,
            },
        )


async def safe_file_write_async(
    file_path: Union[str, Path],
    content: str,
    encoding: str = "utf-8",
    create_dirs: bool = True,
    retry_config: Optional[RetryConfig] = None,
) -> None:
    """
    Async version of safe_file_write.

    Args:
        file_path: Path to the file to write
        content: Content to write
        encoding: File encoding
        create_dirs: Whether to create parent directories if they don't exist
        retry_config: Custom retry configuration (defaults to FILE_RETRY)

    Raises:
        FileSystemError: If file writing fails after retries
    """
    retry_config = retry_config or FILE_RETRY

    async def _write_operation():
        # Run blocking I/O in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: safe_file_write(
                file_path, content, encoding, create_dirs, RetryConfig(max_attempts=1)
            ),
        )

    try:
        await with_retry_async(_write_operation, retry_config)
    except Exception as e:
        if hasattr(e, "last_exception"):
            original = e.last_exception
        else:
            original = e

        # If it's already a StructuredError, just re-raise it
        if isinstance(original, FileSystemError):
            raise original

        raise create_error_from_exception(
            original,
            "file_write_async",
            "file_operations",
            {
                "file_path": str(file_path),
                "encoding": encoding,
                "content_length": len(content),
                "retry_attempts": retry_config.max_attempts,
            },
        )


def is_file_locked(file_path: Union[str, Path]) -> bool:
    """
    Check if a file is locked (Windows-specific utility).

    Args:
        file_path: Path to check

    Returns:
        True if file appears to be locked, False otherwise
    """
    if os.name != "nt":
        return False  # Not applicable on non-Windows systems

    # Check if file exists first
    if not os.path.exists(file_path):
        return False  # File doesn't exist, so it can't be locked

    try:
        # Try to open file in exclusive mode
        with open(file_path, "r+"):
            pass
        return False
    except (PermissionError, OSError):
        return True
    except FileNotFoundError:
        # File doesn't exist, so it can't be locked
        return False


def wait_for_file_unlock(
    file_path: Union[str, Path], timeout: float = 30.0, check_interval: float = 0.1
) -> bool:
    """
    Wait for a file to become unlocked.

    Args:
        file_path: Path to the file
        timeout: Maximum time to wait in seconds
        check_interval: How often to check in seconds

    Returns:
        True if file became unlocked, False if timeout was reached
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        if not is_file_locked(file_path):
            return True
        time.sleep(check_interval)

    return False
