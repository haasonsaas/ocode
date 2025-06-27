"""Tests for atomic file operations."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from ocode_python.utils.atomic_operations import (
    AtomicFileWriter,
    atomic_write,
    safe_file_update,
)


@pytest.mark.unit
class TestAtomicFileWriter:
    """Test AtomicFileWriter functionality."""

    def test_successful_write(self, tmp_path):
        """Test successful atomic write operation."""
        target_file = tmp_path / "test.txt"
        content = "Hello, World!"

        with AtomicFileWriter(target_file) as f:
            f.write(content)

        assert target_file.exists()
        assert target_file.read_text() == content

    def test_exception_during_write(self, tmp_path):
        """Test cleanup when exception occurs during write."""
        target_file = tmp_path / "test.txt"

        # Write initial content
        target_file.write_text("Original content")

        try:
            with AtomicFileWriter(target_file) as f:
                f.write("Partial content")
                raise RuntimeError("Simulated error")
        except RuntimeError:
            pass

        # Original file should be unchanged
        assert target_file.read_text() == "Original content"

        # No temp files should remain
        temp_files = list(tmp_path.glob(".*tmp"))
        assert len(temp_files) == 0

    def test_backup_creation(self, tmp_path):
        """Test backup file creation."""
        target_file = tmp_path / "test.txt"
        original_content = "Original content"
        new_content = "New content"

        # Write initial content
        target_file.write_text(original_content)

        with AtomicFileWriter(target_file, backup=True) as f:
            f.write(new_content)

        assert target_file.read_text() == new_content

        # Check backup exists
        backup_file = target_file.with_suffix(".txt.bak")
        assert backup_file.exists()
        assert backup_file.read_text() == original_content

    def test_permission_preservation(self, tmp_path):
        """Test that file permissions are preserved."""
        if os.name == "nt":
            pytest.skip("Permission test not applicable on Windows")

        target_file = tmp_path / "test.txt"
        target_file.write_text("Original")

        # Set specific permissions
        os.chmod(target_file, 0o644)
        original_mode = target_file.stat().st_mode

        with AtomicFileWriter(target_file) as f:
            f.write("Updated content")

        # Permissions should be preserved
        assert target_file.stat().st_mode == original_mode

    def test_binary_mode(self, tmp_path):
        """Test binary file writing."""
        target_file = tmp_path / "test.bin"
        content = b"\x00\x01\x02\x03"

        with AtomicFileWriter(target_file, mode="wb", encoding=None) as f:
            f.write(content)

        assert target_file.read_bytes() == content

    def test_abort_method(self, tmp_path):
        """Test abort method cleans up properly."""
        target_file = tmp_path / "test.txt"

        writer = AtomicFileWriter(target_file)
        f = writer.__enter__()
        f.write("Some content")

        # Abort the operation
        writer.abort()

        # Target file should not exist
        assert not target_file.exists()

        # No temp files should remain
        temp_files = list(tmp_path.glob(".*tmp"))
        assert len(temp_files) == 0

    def test_sync_to_disk(self, tmp_path):
        """Test sync to disk option."""
        target_file = tmp_path / "test.txt"

        with patch("os.fsync") as mock_fsync:
            with AtomicFileWriter(target_file, sync=True) as f:
                f.write("Content")

            # fsync should have been called
            mock_fsync.assert_called_once()

    def test_windows_atomic_replace(self, tmp_path):
        """Test atomic replacement on Windows."""
        if os.name != "nt":
            pytest.skip("Windows-specific test")

        target_file = tmp_path / "test.txt"
        target_file.write_text("Original")

        with AtomicFileWriter(target_file) as f:
            f.write("New content")

        assert target_file.read_text() == "New content"


@pytest.mark.unit
class TestAtomicWrite:
    """Test atomic_write helper function."""

    def test_string_write(self, tmp_path):
        """Test writing string content."""
        target_file = tmp_path / "test.txt"

        success, error = atomic_write(target_file, "Hello, World!")

        assert success is True
        assert error is None
        assert target_file.read_text() == "Hello, World!"

    def test_bytes_write(self, tmp_path):
        """Test writing bytes content."""
        target_file = tmp_path / "test.bin"
        content = b"Binary content"

        success, error = atomic_write(target_file, content)

        assert success is True
        assert error is None
        assert target_file.read_bytes() == content

    def test_write_with_error(self, tmp_path):
        """Test error handling in atomic_write."""
        # Try to write to a directory (should fail)
        target_dir = tmp_path / "dir"
        target_dir.mkdir()

        success, error = atomic_write(target_dir, "Content")

        assert success is False
        assert error is not None
        # Windows and Unix have different error messages for directory write
        error_lower = error.lower()
        assert (
            "is a directory" in error 
            or "directory" in error_lower 
            or "permission denied" in error_lower
            or "access is denied" in error_lower
        )

    def test_encoding_parameter(self, tmp_path):
        """Test custom encoding."""
        target_file = tmp_path / "test.txt"
        content = "Café ☕"

        success, error = atomic_write(target_file, content, encoding="utf-8")

        assert success is True
        assert target_file.read_text(encoding="utf-8") == content


@pytest.mark.unit
class TestSafeFileUpdate:
    """Test safe_file_update function."""

    def test_update_existing_file(self, tmp_path):
        """Test updating an existing file."""
        target_file = tmp_path / "test.txt"
        target_file.write_text("line1\nline2\n")

        def add_line(content):
            return content + "line3\n"

        success, error = safe_file_update(target_file, add_line)

        assert success is True
        assert error is None
        assert target_file.read_text() == "line1\nline2\nline3\n"

    def test_update_nonexistent_file(self, tmp_path):
        """Test updating a file that doesn't exist."""
        target_file = tmp_path / "new.txt"

        def create_content(content):
            assert content == ""
            return "New file content"

        success, error = safe_file_update(target_file, create_content)

        assert success is True
        assert error is None
        assert target_file.read_text() == "New file content"

    def test_update_with_exception(self, tmp_path):
        """Test error handling when update function raises."""
        target_file = tmp_path / "test.txt"
        target_file.write_text("Original")

        def failing_update(content):
            raise ValueError("Update failed")

        success, error = safe_file_update(target_file, failing_update)

        assert success is False
        assert "Update failed" in error
        # Original file should be unchanged
        assert target_file.read_text() == "Original"

    def test_backup_on_update(self, tmp_path):
        """Test backup creation during update."""
        target_file = tmp_path / "test.txt"
        target_file.write_text("Original")

        def update(content):
            return "Updated"

        success, error = safe_file_update(target_file, update, backup=True)

        assert success is True
        assert target_file.read_text() == "Updated"

        # Check backup
        backup_file = target_file.with_suffix(".txt.bak")
        assert backup_file.exists()
        assert backup_file.read_text() == "Original"
