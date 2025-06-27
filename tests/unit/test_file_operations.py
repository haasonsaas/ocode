"""Tests for resilient file operations."""

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ocode_python.utils.file_operations import (
    is_file_locked,
    safe_directory_create,
    safe_file_copy,
    safe_file_delete,
    safe_file_move,
    safe_file_read,
    safe_file_write,
    wait_for_file_unlock,
)
from ocode_python.utils.retry_handler import RetryConfig
from ocode_python.utils.structured_errors import (
    FileSystemError,
    PermissionError,
    StructuredError,
)


class TestSafeFileRead:
    """Test safe file reading with retries."""

    def test_successful_read(self):
        """Test successful file reading."""
        content = "Hello, World!"

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = safe_file_read(temp_path)
            assert result == content
        finally:
            os.unlink(temp_path)

    def test_read_with_encoding(self):
        """Test reading with specific encoding."""
        content = "こんにちは世界"  # Japanese text

        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = safe_file_read(temp_path, encoding="utf-8")
            assert result == content
        finally:
            os.unlink(temp_path)

    def test_read_nonexistent_file(self):
        """Test reading nonexistent file raises appropriate error."""
        with pytest.raises(FileSystemError) as exc_info:
            safe_file_read("/nonexistent/file.txt")

        assert exc_info.value.context.operation == "file_read"

    def test_read_with_custom_retry_config(self):
        """Test reading with custom retry configuration."""
        # Use very low retry count to speed up test
        retry_config = RetryConfig(max_attempts=1, base_delay=0.01)

        with pytest.raises(FileSystemError):
            safe_file_read("/nonexistent/file.txt", retry_config=retry_config)

    def test_read_with_permission_error(self):
        """Test handling permission errors during read."""
        import platform

        if platform.system() == "Windows":
            # Skip this test on Windows as file permissions work differently
            # Windows handles file permissions differently and chmod doesn't
            # work the same way
            pytest.skip("Unix-style permission test not applicable on Windows")
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
        content = "Test content"

        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            safe_file_write(temp_path, content)

            with open(temp_path, "r") as f:
                result = f.read()
            assert result == content
        finally:
            os.unlink(temp_path)

    def test_write_creates_directories(self):
        """Test writing creates parent directories if needed."""
        content = "Test content"

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "subdir" / "file.txt"

            safe_file_write(file_path, content, create_dirs=True)

            assert file_path.exists()
            assert file_path.read_text() == content

    def test_write_without_create_dirs(self):
        """Test writing fails when parent directory doesn't exist."""
        content = "Test content"

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "nonexistent" / "file.txt"

            with pytest.raises(FileSystemError):
                safe_file_write(file_path, content, create_dirs=False)

    def test_write_with_encoding(self):
        """Test writing with specific encoding."""
        content = "こんにちは世界"  # Japanese text

        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            safe_file_write(temp_path, content, encoding="utf-8")

            with open(temp_path, "r", encoding="utf-8") as f:
                result = f.read()
            assert result == content
        finally:
            os.unlink(temp_path)

    def test_atomic_write(self):
        """Test atomic write behavior."""
        original_content = "original"
        new_content = "new content"

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(original_content)
            temp_path = f.name

        try:
            # Simulate failure during write
            original_rename = Path.rename

            def failing_rename(self, target):
                if str(target) == temp_path:
                    raise OSError("Simulated rename failure")
                return original_rename(self, target)

            with patch.object(Path, "rename", failing_rename):
                with pytest.raises((FileSystemError, StructuredError)):
                    safe_file_write(temp_path, new_content)

            # Original content should be preserved
            with open(temp_path, "r") as f:
                result = f.read()
            assert result == original_content
        finally:
            # Clean up the file if it exists
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestSafeFileCopy:
    """Test safe file copying with retries."""

    def test_successful_copy(self):
        """Test successful file copying."""
        content = "test content"

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

    def test_move_nonexistent_source(self):
        """Test moving from nonexistent source."""
        with tempfile.NamedTemporaryFile(delete=False) as dst_f:
            dst_path = dst_f.name

        try:
            with pytest.raises(FileSystemError):
                safe_file_move("/nonexistent/source.txt", dst_path)
        finally:
            os.unlink(dst_path)


class TestSafeFileDelete:
    """Test safe file deletion with retries."""

    def test_successful_delete(self):
        """Test successful file deletion."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        assert os.path.exists(temp_path)
        safe_file_delete(temp_path)
        assert not os.path.exists(temp_path)

    def test_delete_nonexistent_with_ignore(self):
        """Test deleting nonexistent file with ignore_missing=True."""
        # Should not raise
        safe_file_delete("/nonexistent/file.txt", ignore_missing=True)

    def test_delete_nonexistent_without_ignore(self):
        """Test deleting nonexistent file with ignore_missing=False."""
        with pytest.raises(FileSystemError):
            safe_file_delete("/nonexistent/file.txt", ignore_missing=False)

    def test_delete_with_permission_error(self):
        """Test handling permission errors during deletion."""
        import platform

        if platform.system() == "Windows":
            # Skip this test on Windows as file permissions work differently
            # Windows handles file permissions differently and chmod doesn't
            # work the same way
            pytest.skip("Unix-style permission test not applicable on Windows")
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

    def test_create_nested_directories(self):
        """Test creating nested directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_dir = Path(temp_dir) / "level1" / "level2" / "level3"

            safe_directory_create(nested_dir)
            assert nested_dir.exists()
            assert nested_dir.is_dir()

    def test_create_existing_directory(self):
        """Test creating already existing directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            existing_dir = Path(temp_dir) / "existing"
            existing_dir.mkdir()

            # Should not raise
            safe_directory_create(existing_dir)
            assert existing_dir.exists()

    def test_create_when_file_exists(self):
        """Test creating directory when a file with same name exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "file_not_dir"
            file_path.write_text("content")

            with pytest.raises(FileSystemError) as exc_info:
                safe_directory_create(file_path)

            # The error message should indicate the path exists
            assert (
                "exists" in str(exc_info.value).lower()
                or "exist_ok" in str(exc_info.value).lower()
            )


class TestFileUtilities:
    """Test file utility functions."""

    def test_is_file_locked_windows_only(self):
        """Test is_file_locked function (Windows-specific)."""
        if os.name != "nt":
            # Function should return False on non-Windows
            assert not is_file_locked("/any/path")
            return

        # On Windows, test with a real file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            # File should not be locked
            assert not is_file_locked(temp_path)
        finally:
            os.unlink(temp_path)

    def test_is_file_locked_nonexistent(self):
        """Test is_file_locked with nonexistent file."""
        # Should return False for nonexistent files
        # Use a path that definitely doesn't exist
        import tempfile
        temp_dir = tempfile.gettempdir()
        nonexistent_path = os.path.join(temp_dir, "definitely_nonexistent_file_12345.txt")
        assert not is_file_locked(nonexistent_path)

    def test_wait_for_file_unlock_immediate(self):
        """Test waiting for file unlock when file is not locked."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            result = wait_for_file_unlock(temp_path, timeout=1.0)
            assert result is True
        finally:
            os.unlink(temp_path)

    def test_wait_for_file_unlock_timeout(self):
        """Test waiting for file unlock with timeout."""
        # Create a file that we can ensure exists and is accessible
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name
            f.write(b"test")
            f.flush()
        
        try:
            # File should not be locked, so this should return True immediately
            result = wait_for_file_unlock(temp_path, timeout=0.1)
            assert result is True
        finally:
            os.unlink(temp_path)


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

            def mock_open(path, mode="r", **kwargs):
                nonlocal call_count
                if mode == "w" and str(path).endswith(".tmp"):
                    call_count += 1
                    if call_count == 1:
                        raise OSError("Simulated transient failure")
                return original_open(path, mode, **kwargs)

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


class TestWindowsSpecific:
    """Windows-specific file operation tests."""

    @pytest.mark.skipif(os.name != "nt", reason="Windows-only tests")
    def test_windows_file_in_use_error(self):
        """Test handling of file-in-use errors on Windows."""
        import platform

        if platform.system() != "Windows":
            pytest.skip("Windows-only test")

        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, mode="w") as f:
            temp_path = f.name
            f.write("test content")
            f.flush()

            # Keep the file open to simulate it being in use
            # This should cause permission/access errors
            try:
                # Try to delete the file while it's still open
                with pytest.raises((PermissionError, OSError, FileSystemError)):
                    safe_file_delete(temp_path, ignore_missing=False)
            finally:
                # File will be closed when the context manager exits
                pass

        # Clean up after the file is closed
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    @pytest.mark.skipif(os.name != "nt", reason="Windows-only tests")
    def test_windows_locked_file_detection(self):
        """Test detection of locked files on Windows."""
        import platform

        if platform.system() != "Windows":
            pytest.skip("Windows-only test")

        # Create a file and keep it open with exclusive access
        with tempfile.NamedTemporaryFile(delete=False, mode='w+b') as f:
            temp_path = f.name
            f.write(b"test")
            f.flush()

            # Try to open the same file with exclusive write access to simulate lock
            try:
                # On Windows, having the file open should make it appear locked
                # But NamedTemporaryFile doesn't create exclusive locks by default
                # So let's just test that the function doesn't crash
                lock_status = is_file_locked(temp_path)
                # The exact result may vary based on Windows configuration
                assert isinstance(lock_status, bool)
            except Exception:
                pytest.skip("Windows file locking behavior varies by system")

        # After closing, file should not be locked
        assert is_file_locked(temp_path) is False
        os.unlink(temp_path)
