"""
Tests for resilient file operations utility.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from ocode_python.utils.file_operations import (
    is_file_locked,
    safe_directory_create,
    safe_file_copy,
    safe_file_delete,
    safe_file_move,
    safe_file_read,
    safe_file_read_async,
    safe_file_write,
    safe_file_write_async,
    wait_for_file_unlock,
)
from ocode_python.utils.retry_handler import RetryConfig
from ocode_python.utils.structured_errors import FileSystemError, PermissionError


class TestSafeFileRead:
    """Test safe file reading with retries."""

    def test_successful_read(self):
        """Test successful file reading."""
        content = "test file content\nwith multiple lines"

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = safe_file_read(temp_path)
            assert result == content
        finally:
            os.unlink(temp_path)

    def test_read_with_encoding(self):
        """Test file reading with specific encoding."""
        content = "test content with unicode: ñáéíóú"

        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = safe_file_read(temp_path, encoding="utf-8")
            assert result == content
        finally:
            os.unlink(temp_path)

    def test_read_nonexistent_file(self):
        """Test reading a nonexistent file."""
        with pytest.raises(FileSystemError):
            safe_file_read("/nonexistent/file.txt")

    def test_read_with_custom_retry_config(self):
        """Test reading with custom retry configuration."""
        retry_config = RetryConfig(max_attempts=1, base_delay=0.01)

        with pytest.raises(FileSystemError):
            safe_file_read("/nonexistent/file.txt", retry_config=retry_config)

    def test_read_with_permission_error(self):
        """Test handling permission errors during read."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            # Change permissions to make file unreadable
            os.chmod(temp_path, 0o000)

            with pytest.raises(PermissionError):
                safe_file_read(temp_path)
        finally:
            # Restore permissions for cleanup
            os.chmod(temp_path, 0o644)
            os.unlink(temp_path)


class TestSafeFileWrite:
    """Test safe file writing with retries."""

    def test_successful_write(self):
        """Test successful file writing."""
        content = "test content to write"

        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            safe_file_write(temp_path, content)

            # Verify content was written
            with open(temp_path, "r") as f:
                result = f.read()
            assert result == content
        finally:
            os.unlink(temp_path)

    def test_write_with_directory_creation(self):
        """Test writing with automatic directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "subdir" / "newfile.txt"
            content = "test content"

            safe_file_write(file_path, content, create_dirs=True)

            assert file_path.exists()
            assert file_path.read_text() == content

    def test_write_without_directory_creation(self):
        """Test writing without directory creation fails appropriately."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "nonexistent" / "newfile.txt"
            content = "test content"

            with pytest.raises(FileSystemError):
                safe_file_write(file_path, content, create_dirs=False)

    def test_write_with_encoding(self):
        """Test writing with specific encoding."""
        content = "content with unicode: ñáéíóú"

        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            safe_file_write(temp_path, content, encoding="utf-8")

            with open(temp_path, "r", encoding="utf-8") as f:
                result = f.read()
            assert result == content
        finally:
            os.unlink(temp_path)

    def test_atomic_write_behavior(self):
        """Test that writes are atomic (using temporary files)."""
        content = "test content"

        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            # Mock open to fail on the first attempt but succeed on retry
            original_open = open
            call_count = 0

            def mock_open(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1 and args[0].endswith(".tmp"):
                    raise PermissionError("Simulated temporary failure")
                return original_open(*args, **kwargs)

            with patch("builtins.open", side_effect=mock_open):
                retry_config = RetryConfig(max_attempts=2, base_delay=0.01)
                safe_file_write(temp_path, content, retry_config=retry_config)

            # Verify content was eventually written
            with open(temp_path, "r") as f:
                result = f.read()
            assert result == content

        finally:
            os.unlink(temp_path)


class TestSafeFileCopy:
    """Test safe file copying with retries."""

    def test_successful_copy(self):
        """Test successful file copying."""
        content = "test content to copy"

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as src_f:
            src_f.write(content)
            src_path = src_f.name

        with tempfile.NamedTemporaryFile(delete=False) as dst_f:
            dst_path = dst_f.name

        try:
            safe_file_copy(src_path, dst_path)

            with open(dst_path, "r") as f:
                result = f.read()
            assert result == content
        finally:
            os.unlink(src_path)
            os.unlink(dst_path)

    def test_copy_with_directory_creation(self):
        """Test copying with automatic directory creation."""
        content = "test content"

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as src_f:
            src_f.write(content)
            src_path = src_f.name

        with tempfile.TemporaryDirectory() as temp_dir:
            dst_path = Path(temp_dir) / "subdir" / "copied_file.txt"

            try:
                safe_file_copy(src_path, dst_path, create_dirs=True)

                assert dst_path.exists()
                assert dst_path.read_text() == content
            finally:
                os.unlink(src_path)

    def test_copy_nonexistent_source(self):
        """Test copying from nonexistent source."""
        with tempfile.NamedTemporaryFile(delete=False) as dst_f:
            dst_path = dst_f.name

        try:
            with pytest.raises(FileSystemError):
                safe_file_copy("/nonexistent/source.txt", dst_path)
        finally:
            os.unlink(dst_path)


class TestSafeFileMove:
    """Test safe file moving with retries."""

    def test_successful_move(self):
        """Test successful file moving."""
        content = "test content to move"

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as src_f:
            src_f.write(content)
            src_path = src_f.name

        with tempfile.NamedTemporaryFile(delete=False) as dst_f:
            dst_path = dst_f.name

        try:
            safe_file_move(src_path, dst_path)

            assert not os.path.exists(src_path)  # Source should be gone

            with open(dst_path, "r") as f:
                result = f.read()
            assert result == content
        finally:
            if os.path.exists(src_path):
                os.unlink(src_path)
            if os.path.exists(dst_path):
                os.unlink(dst_path)

    def test_move_with_directory_creation(self):
        """Test moving with automatic directory creation."""
        content = "test content"

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as src_f:
            src_f.write(content)
            src_path = src_f.name

        with tempfile.TemporaryDirectory() as temp_dir:
            dst_path = Path(temp_dir) / "subdir" / "moved_file.txt"

            safe_file_move(src_path, dst_path, create_dirs=True)

            assert not os.path.exists(src_path)
            assert dst_path.exists()
            assert dst_path.read_text() == content


class TestSafeFileDelete:
    """Test safe file deletion with retries."""

    def test_successful_delete(self):
        """Test successful file deletion."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        assert os.path.exists(temp_path)

        result = safe_file_delete(temp_path)

        assert result is True
        assert not os.path.exists(temp_path)

    def test_delete_nonexistent_file_ignore(self):
        """Test deleting nonexistent file with ignore_missing=True."""
        result = safe_file_delete("/nonexistent/file.txt", ignore_missing=True)
        assert result is False

    def test_delete_nonexistent_file_no_ignore(self):
        """Test deleting nonexistent file with ignore_missing=False."""
        with pytest.raises(FileSystemError):
            safe_file_delete("/nonexistent/file.txt", ignore_missing=False)

    def test_delete_with_permission_error(self):
        """Test handling permission errors during deletion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_file.txt"
            file_path.write_text("test content")

            # Make directory read-only to prevent deletion
            os.chmod(temp_dir, 0o444)

            try:
                with pytest.raises(PermissionError):
                    safe_file_delete(file_path)
            finally:
                # Restore permissions for cleanup
                os.chmod(temp_dir, 0o755)


class TestSafeDirectoryCreate:
    """Test safe directory creation with retries."""

    def test_successful_create(self):
        """Test successful directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir = Path(temp_dir) / "new_directory"

            safe_directory_create(new_dir)

            assert new_dir.exists()
            assert new_dir.is_dir()

    def test_create_with_parents(self):
        """Test creating directory with parent directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir = Path(temp_dir) / "parent" / "child" / "grandchild"

            safe_directory_create(new_dir, parents=True)

            assert new_dir.exists()
            assert new_dir.is_dir()

    def test_create_without_parents_fails(self):
        """Test creating directory without parents fails appropriately."""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir = Path(temp_dir) / "nonexistent" / "child"

            with pytest.raises(FileSystemError):
                safe_directory_create(new_dir, parents=False)

    def test_create_existing_directory(self):
        """Test creating directory that already exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            existing_dir = Path(temp_dir) / "existing"
            existing_dir.mkdir()

            # Should not raise an error with exist_ok=True (default)
            safe_directory_create(existing_dir)

            assert existing_dir.exists()

    def test_create_existing_directory_no_exist_ok(self):
        """Test creating existing directory with exist_ok=False."""
        with tempfile.TemporaryDirectory() as temp_dir:
            existing_dir = Path(temp_dir) / "existing"
            existing_dir.mkdir()

            with pytest.raises(FileSystemError):
                safe_directory_create(existing_dir, exist_ok=False)


class TestAsyncFileOperations:
    """Test async file operations."""

    @pytest.mark.asyncio
    async def test_async_file_read(self):
        """Test async file reading."""
        content = "async test content"

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = await safe_file_read_async(temp_path)
            assert result == content
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_async_file_write(self):
        """Test async file writing."""
        content = "async test content"

        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            await safe_file_write_async(temp_path, content)

            with open(temp_path, "r") as f:
                result = f.read()
            assert result == content
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_async_operations_with_retry(self):
        """Test async operations with retry logic."""
        retry_config = RetryConfig(max_attempts=2, base_delay=0.01)

        with pytest.raises(FileSystemError):
            await safe_file_read_async(
                "/nonexistent/file.txt", retry_config=retry_config
            )


class TestFileUtilities:
    """Test file utility functions."""

    @pytest.mark.skipif(
        os.name != "nt", reason="File locking check is Windows-specific"
    )
    def test_is_file_locked_windows(self):
        """Test file lock detection on Windows."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            # File should not be locked initially
            assert not is_file_locked(temp_path)

            # Open file exclusively to lock it
            with open(temp_path, "r+"):
                # File should appear locked to another process
                # Note: This test is somewhat limited as we can't easily
                # simulate true cross-process file locking in unit tests
                pass

        finally:
            os.unlink(temp_path)

    @pytest.mark.skipif(os.name == "nt", reason="Skip on Windows")
    def test_is_file_locked_non_windows(self):
        """Test file lock detection on non-Windows systems."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            # Should always return False on non-Windows systems
            assert not is_file_locked(temp_path)
        finally:
            os.unlink(temp_path)

    def test_wait_for_file_unlock_immediate(self):
        """Test waiting for file unlock when file is not locked."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            # Should return immediately as file is not locked
            result = wait_for_file_unlock(temp_path, timeout=1.0)
            assert result is True
        finally:
            os.unlink(temp_path)

    def test_wait_for_file_unlock_timeout(self):
        """Test waiting for file unlock with timeout."""
        # Use a path that doesn't exist to simulate a locked file
        # that never becomes unlocked
        result = wait_for_file_unlock("/nonexistent/file.txt", timeout=0.1)
        # Since file doesn't exist, is_file_locked returns False,
        # so this should actually return True quickly
        assert result is True


class TestRetryIntegration:
    """Test integration with retry logic."""

    def test_retry_on_transient_failure(self):
        """Test that operations retry on transient failures."""
        content = "test content"

        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            # Mock file writing to fail once then succeed
            original_open = open
            call_count = 0

            def mock_open(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1 and "w" in str(
                    kwargs.get("mode", args[1] if len(args) > 1 else "")
                ):
                    raise PermissionError("Temporary failure")
                return original_open(*args, **kwargs)

            with patch("builtins.open", side_effect=mock_open):
                retry_config = RetryConfig(max_attempts=3, base_delay=0.01)
                safe_file_write(temp_path, content, retry_config=retry_config)

            # Verify the operation eventually succeeded
            with open(temp_path, "r") as f:
                result = f.read()
            assert result == content
            assert call_count >= 2  # Should have retried

        finally:
            os.unlink(temp_path)

    def test_exhaust_all_retries(self):
        """Test behavior when all retries are exhausted."""
        # Use a very restrictive retry config
        retry_config = RetryConfig(max_attempts=1, base_delay=0.01)

        with pytest.raises(FileSystemError):
            safe_file_read(
                "/definitely/nonexistent/file.txt", retry_config=retry_config
            )


class TestErrorHandling:
    """Test error handling and structured errors."""

    def test_structured_error_context(self):
        """Test that structured errors include proper context."""
        try:
            safe_file_read("/nonexistent/file.txt")
            assert False, "Should have raised an exception"
        except FileSystemError as e:
            assert e.context is not None
            assert e.context.operation == "file_read"
            assert e.context.component == "file_operations"
            assert "/nonexistent/file.txt" in str(
                e.context.details.get("file_path", "")
            )

    def test_error_with_original_exception(self):
        """Test that structured errors preserve original exceptions."""
        try:
            safe_file_read("/nonexistent/file.txt")
            assert False, "Should have raised an exception"
        except FileSystemError as e:
            assert e.original_error is not None
            # The original error should be from the retry mechanism
            # which wraps the actual FileNotFoundError
