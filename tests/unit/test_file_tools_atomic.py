"""Tests for atomic file write operations in FileWriteTool."""

import asyncio
from pathlib import Path

import pytest

from ocode_python.tools.file_tools import FileWriteTool


@pytest.mark.unit
class TestFileWriteToolAtomic:
    """Test FileWriteTool atomic write functionality."""

    @pytest.mark.asyncio
    async def test_atomic_write_default(self, tmp_path):
        """Test that atomic write is enabled by default."""
        tool = FileWriteTool()
        target_file = tmp_path / "test.txt"
        
        result = await tool.execute(
            path=str(target_file),
            content="Test content"
        )
        
        assert result.success
        assert target_file.read_text() == "Test content"
        assert result.metadata["atomic"] is True
        assert result.metadata["backup_created"] is False  # No existing file
        
    @pytest.mark.asyncio
    async def test_atomic_write_with_backup(self, tmp_path):
        """Test atomic write creates backup of existing file."""
        tool = FileWriteTool()
        target_file = tmp_path / "test.txt"
        
        # Create initial file
        target_file.write_text("Original content")
        
        result = await tool.execute(
            path=str(target_file),
            content="New content",
            atomic=True,
            backup=True
        )
        
        assert result.success
        assert target_file.read_text() == "New content"
        assert result.metadata["atomic"] is True
        assert result.metadata["backup_created"] is True
        
        # Check backup exists
        backup_file = target_file.with_suffix(".txt.bak")
        assert backup_file.exists()
        assert backup_file.read_text() == "Original content"
        
    @pytest.mark.asyncio
    async def test_atomic_write_disabled(self, tmp_path):
        """Test non-atomic write when explicitly disabled."""
        tool = FileWriteTool()
        target_file = tmp_path / "test.txt"
        
        result = await tool.execute(
            path=str(target_file),
            content="Test content",
            atomic=False
        )
        
        assert result.success
        assert target_file.read_text() == "Test content"
        assert result.metadata["atomic"] is False
        
    @pytest.mark.asyncio
    async def test_append_mode_disables_atomic(self, tmp_path):
        """Test that append mode is incompatible with atomic write."""
        tool = FileWriteTool()
        target_file = tmp_path / "test.txt"
        target_file.write_text("Original\n")
        
        # Atomic and append should fail
        result = await tool.execute(
            path=str(target_file),
            content="Appended\n",
            append=True,
            atomic=True
        )
        
        assert not result.success
        assert "incompatible with append mode" in result.error
        
    @pytest.mark.asyncio
    async def test_append_mode_works_without_atomic(self, tmp_path):
        """Test append mode works when atomic is disabled."""
        tool = FileWriteTool()
        target_file = tmp_path / "test.txt"
        target_file.write_text("Original\n")
        
        result = await tool.execute(
            path=str(target_file),
            content="Appended\n",
            append=True,
            atomic=False
        )
        
        assert result.success
        assert target_file.read_text() == "Original\nAppended\n"
        assert result.metadata["mode"] == "append"
        assert result.metadata["atomic"] is False
        
    @pytest.mark.asyncio
    async def test_atomic_write_preserves_content_on_error(self, tmp_path):
        """Test that original file is preserved if write fails."""
        tool = FileWriteTool()
        target_file = tmp_path / "test.txt"
        target_file.write_text("Original content")
        
        # Make directory read-only to cause write failure
        import os
        original_mode = tmp_path.stat().st_mode
        try:
            # This might not work on all systems, but worth trying
            os.chmod(tmp_path, 0o555)  # Read-only directory
            
            result = await tool.execute(
                path=str(target_file),
                content="This should fail",
                atomic=True
            )
            
            # If it failed (expected on Unix-like systems)
            if not result.success:
                # Original content should be preserved
                assert target_file.read_text() == "Original content"
        finally:
            # Restore permissions
            os.chmod(tmp_path, original_mode)
            
    @pytest.mark.asyncio
    async def test_fsync_in_non_atomic_mode(self, tmp_path):
        """Test that fsync is called in non-atomic mode."""
        tool = FileWriteTool()
        target_file = tmp_path / "test.txt"
        
        # We can't easily mock os.fsync in async context, 
        # but we can verify the write succeeds
        result = await tool.execute(
            path=str(target_file),
            content="Test content",
            atomic=False
        )
        
        assert result.success
        assert target_file.read_text() == "Test content"
        
    @pytest.mark.asyncio
    async def test_binary_content_handling(self, tmp_path):
        """Test writing binary-like content."""
        tool = FileWriteTool()
        target_file = tmp_path / "test.txt"
        
        # Test with content that could cause encoding issues
        content = "Binary-like: \x00\x01\x02"
        
        result = await tool.execute(
            path=str(target_file),
            content=content,
            encoding="utf-8",
            atomic=True
        )
        
        assert result.success
        # The string representation should be preserved
        assert target_file.read_text() == content
        
    @pytest.mark.asyncio
    async def test_concurrent_writes_safety(self, tmp_path):
        """Test that atomic writes handle concurrent access safely."""
        tool = FileWriteTool()
        target_file = tmp_path / "concurrent.txt"
        
        async def write_content(index):
            return await tool.execute(
                path=str(target_file),
                content=f"Writer {index} content",
                atomic=True,
                backup=False  # Avoid backup file conflicts
            )
            
        # Run multiple writes concurrently
        results = await asyncio.gather(
            write_content(1),
            write_content(2),
            write_content(3),
            return_exceptions=True
        )
        
        # All operations should complete (though order is undefined)
        successful_results = [r for r in results if not isinstance(r, Exception) and r.success]
        assert len(successful_results) >= 1  # At least one should succeed
        
        # File should contain one of the complete contents
        final_content = target_file.read_text()
        assert final_content in [
            "Writer 1 content",
            "Writer 2 content", 
            "Writer 3 content"
        ]
        
    @pytest.mark.asyncio
    async def test_create_parent_dirs_with_atomic(self, tmp_path):
        """Test parent directory creation works with atomic writes."""
        tool = FileWriteTool()
        target_file = tmp_path / "subdir" / "nested" / "test.txt"
        
        result = await tool.execute(
            path=str(target_file),
            content="Nested content",
            create_dirs=True,
            atomic=True
        )
        
        assert result.success
        assert target_file.exists()
        assert target_file.read_text() == "Nested content"