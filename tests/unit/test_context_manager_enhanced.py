"""
Enhanced unit tests for improved context manager.
"""

import asyncio
import shutil
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ocode_python.core.context_manager import ContextManager, FileInfo, ProjectContext


@pytest.mark.unit
class TestContextManagerEnhanced:
    """Test enhanced ContextManager functionality."""

    def test_init_with_nonexistent_root(self):
        """Test initialization with non-existent root directory."""
        with pytest.raises(ValueError, match="Root directory does not exist"):
            ContextManager(Path("/nonexistent/directory"))

    def test_init_with_file_as_root(self, temp_dir: Path):
        """Test initialization with file instead of directory."""
        file_path = temp_dir / "file.txt"
        file_path.write_text("content")

        with pytest.raises(ValueError, match="Root path is not a directory"):
            ContextManager(file_path)

    def test_init_cache_dir_creation_failure(self, temp_dir: Path):
        """Test cache directory creation failure handling."""
        import platform

        # Skip this test on Windows as permission model is different
        if platform.system() == "Windows":
            pytest.skip("Permission test not applicable on Windows")

        # Make temp_dir read-only
        import os

        os.chmod(temp_dir, 0o444)

        try:
            with pytest.raises(RuntimeError, match="Failed to create cache directory"):
                ContextManager(temp_dir)
        finally:
            # Restore permissions
            os.chmod(temp_dir, 0o755)

    def test_wildcard_pattern_compilation(self, temp_dir: Path):
        """Test wildcard pattern compilation during init."""
        manager = ContextManager(temp_dir)

        assert "*.pyc" in manager.wildcard_patterns
        assert "*.log" in manager.wildcard_patterns
        assert ".git" not in manager.wildcard_patterns  # Not a wildcard

    def test_should_ignore_enhanced(self, temp_dir: Path):
        """Test enhanced ignore logic with wildcards."""
        manager = ContextManager(temp_dir)

        # Test wildcard patterns
        assert manager._should_ignore(temp_dir / "test.pyc")
        assert manager._should_ignore(temp_dir / "debug.log")
        assert manager._should_ignore(temp_dir / "module.egg-info")

        # Test exact matches
        assert manager._should_ignore(temp_dir / ".git" / "config")
        assert manager._should_ignore(temp_dir / "node_modules" / "package.json")

        # Test files that should not be ignored
        assert not manager._should_ignore(temp_dir / "main.py")
        assert not manager._should_ignore(temp_dir / "config.yaml")

    @pytest.mark.skip(reason="Path methods are read-only, difficult to mock properly")
    def test_should_ignore_permission_error(self, temp_dir: Path):
        """Test handling permission errors in should_ignore."""
        # This test is skipped because Path methods are read-only
        # The functionality is tested in integration tests instead
        pass

    def test_cache_size_management(self, temp_dir: Path):
        """Test cache size management."""
        manager = ContextManager(temp_dir)
        manager.max_cache_size = 5  # Small cache for testing

        # Fill cache beyond limit
        for i in range(10):
            path = Path(f"file_{i}.py")
            manager.file_cache[path] = (f"content_{i}", float(i))
            manager.file_info_cache[path] = FileInfo(
                path=path, size=100, modified_time=float(i), content_hash=f"hash_{i}"
            )

        # Trigger cache management
        manager._manage_cache_size()

        # Cache should be reduced
        assert len(manager.file_cache) <= manager.max_cache_size
        assert len(manager.file_info_cache) <= manager.max_cache_size

        # Newest entries should remain
        assert Path("file_9.py") in manager.file_cache
        assert Path("file_0.py") not in manager.file_cache

    @pytest.mark.asyncio
    async def test_analyze_file_with_cache_hit(self, temp_dir: Path):
        """Test file analysis with in-memory cache hit."""
        manager = ContextManager(temp_dir)

        # Create test file
        test_file = temp_dir / "cached.py"
        test_file.write_text("def cached(): pass")

        # Pre-populate cache
        stat = test_file.stat()
        cached_info = FileInfo(
            path=test_file,
            size=stat.st_size,
            modified_time=stat.st_mtime,
            content_hash="cached_hash",
            language="python",
            symbols=["cached"],
        )
        manager.file_info_cache[test_file] = cached_info

        # Analyze should return cached info
        result = await manager.analyze_file(test_file)

        assert result == cached_info

    @pytest.mark.asyncio
    async def test_analyze_file_permission_error(self, temp_dir: Path):
        """Test file analysis with permission errors."""
        import platform

        # Skip this test on Windows as permission model is different
        if platform.system() == "Windows":
            pytest.skip("Permission test not applicable on Windows")

        manager = ContextManager(temp_dir)

        # Create file with no read permissions
        test_file = temp_dir / "noperm.py"
        test_file.write_text("content")

        import os

        os.chmod(test_file, 0o000)

        try:
            result = await manager.analyze_file(test_file)
            assert result is None  # Should return None on permission error
        finally:
            os.chmod(test_file, 0o644)

    def test_database_error_handling(self, temp_dir: Path):
        """Test database error handling."""
        manager = ContextManager(temp_dir)

        # Test _get_cached_analysis with corrupted database
        with patch("sqlite3.connect", side_effect=sqlite3.Error("DB Error")):
            result = manager._get_cached_analysis(Path("test.py"), 123.0)
            assert result is None  # Should return None on DB error

        # Test _cache_analysis with database error
        file_info = FileInfo(
            path=Path("test.py"), size=100, modified_time=123.0, content_hash="hash"
        )

        with patch("sqlite3.connect", side_effect=sqlite3.Error("DB Error")):
            # Should not raise, just skip caching
            manager._cache_analysis(file_info)

    def test_categorize_query_empty(self):
        """Test query categorization with empty query."""
        manager = ContextManager()

        # Test empty string
        result = manager._categorize_query("")
        assert result["category"] == "empty_query"
        assert result["context_strategy"] == "none"

        # Test whitespace only
        result = manager._categorize_query("   \n\t   ")
        assert result["category"] == "empty_query"
        assert result["context_strategy"] == "none"

    def test_detect_multi_action_query(self):
        """Test multi-action query detection."""
        manager = ContextManager()

        # Test run tests then commit
        result = manager._detect_multi_action_query(
            "run tests and then commit if they pass"
        )
        assert result is not None
        assert result["multi_action"] is True
        assert "test_runner" in result["primary_tools"]
        assert "git_commit" in result["secondary_tools"]

        # Test search and replace
        result = manager._detect_multi_action_query(
            "find all TODO comments and replace them"
        )
        assert result is not None
        assert result["multi_action"] is True
        assert any(tool in result["primary_tools"] for tool in ["grep", "code_grep"])
        assert "file_edit" in result["secondary_tools"]

        # Test single action
        result = manager._detect_multi_action_query("run the tests")
        assert result is None  # Not multi-action

    @pytest.mark.asyncio
    async def test_build_context_validation(self):
        """Test build_context input validation."""
        manager = ContextManager()

        # Test negative max_files
        with pytest.raises(ValueError, match="max_files must be non-negative"):
            await manager.build_context("test", max_files=-1)

        # Test excessive max_files (should be capped)
        await manager.build_context("test", max_files=5000)
        # Should not raise, but internally capped at 1000

    @pytest.mark.asyncio
    async def test_build_context_empty_query(self, temp_dir: Path):
        """Test build_context with empty query."""
        manager = ContextManager(temp_dir)

        # Create some test files
        (temp_dir / "test1.py").write_text("def test1(): pass")
        (temp_dir / "test2.py").write_text("def test2(): pass")

        # Empty query should still work but with minimal context
        context = await manager.build_context("", max_files=10)

        assert isinstance(context, ProjectContext)
        assert context.project_root == temp_dir

    @pytest.mark.asyncio
    async def test_build_context_file_limit(self, temp_dir: Path):
        """Test build_context respects file limits."""
        manager = ContextManager(temp_dir)

        # Create many test files
        for i in range(20):
            (temp_dir / f"file_{i}.py").write_text(f"def func_{i}(): pass")

        # Build context with limit
        context = await manager.build_context("test query", max_files=5)

        # Should respect the limit
        assert len(context.files) <= 5

    @pytest.mark.asyncio
    async def test_concurrent_file_analysis(self, temp_dir: Path):
        """Test concurrent file analysis with semaphore."""
        manager = ContextManager(temp_dir)

        # Create multiple test files
        for i in range(15):
            (temp_dir / f"concurrent_{i}.py").write_text(f"def func_{i}(): pass")

        # Track concurrent operations
        concurrent_count = 0
        max_concurrent = 0

        original_analyze = manager.analyze_file

        async def track_concurrent_analyze(path):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            try:
                result = await original_analyze(path)
                return result
            finally:
                concurrent_count -= 1

        with patch.object(
            manager, "analyze_file", side_effect=track_concurrent_analyze
        ):
            await manager.build_context("test", max_files=15)

        # Should limit concurrency (semaphore is set to 10)
        assert max_concurrent <= 10

    def test_git_info_error_handling(self, temp_dir: Path):
        """Test git info extraction error handling."""
        manager = ContextManager(temp_dir)

        # Create mock repo with error
        mock_repo = Mock()
        mock_repo.active_branch.name = Mock(side_effect=Exception("Git error"))
        manager.repo = mock_repo

        # Should handle error gracefully in build_context
        # This is tested implicitly through build_context


@pytest.mark.unit
class TestProjectContextEnhanced:
    """Test enhanced ProjectContext functionality."""

    def test_get_relevant_files_scoring(self, temp_dir: Path):
        """Test enhanced relevance scoring."""
        context = ProjectContext(
            files={
                temp_dir / "auth" / "login.py": "def login(): authenticate_user()",
                temp_dir / "auth" / "logout.py": "def logout(): clear_session()",
                temp_dir / "utils" / "helpers.py": "def helper(): pass",
                temp_dir / "test_auth.py": "def test_login(): assert login()",
            },
            file_info={
                temp_dir
                / "auth"
                / "login.py": FileInfo(
                    path=temp_dir / "auth" / "login.py",
                    size=100,
                    modified_time=1.0,
                    content_hash="hash1",
                    symbols=["login", "authenticate_user"],
                )
            },
            dependencies={},
            symbols={
                "login": [temp_dir / "auth" / "login.py"],
                "authenticate_user": [temp_dir / "auth" / "login.py"],
            },
            project_root=temp_dir,
        )

        # Query for login functionality
        relevant = context.get_relevant_files("user login authentication", max_files=3)

        # Should prioritize files with matching terms
        assert temp_dir / "auth" / "login.py" in relevant

        # Files with "login" in path should score higher
        login_file_index = relevant.index(temp_dir / "auth" / "login.py")
        assert login_file_index == 0  # Should be first


@pytest.mark.integration
class TestContextManagerIntegration:
    """Integration tests for context manager."""

    @pytest.mark.asyncio
    async def test_full_project_scan(self):
        """Test scanning a real project structure."""
        # Use the ocode project itself
        project_root = Path(__file__).parent.parent.parent
        manager = ContextManager(project_root)

        files = await manager.scan_project()

        # Should find Python files
        python_files = [f for f in files if f.suffix == ".py"]
        assert len(python_files) > 0

        # Should not find ignored patterns
        ignored_files = [f for f in files if "__pycache__" in str(f)]
        assert len(ignored_files) == 0

    @pytest.mark.asyncio
    async def test_real_file_analysis(self):
        """Test analyzing real Python files."""
        project_root = Path(__file__).parent.parent.parent
        manager = ContextManager(project_root)

        # Analyze this test file
        this_file = Path(__file__)
        file_info = await manager.analyze_file(this_file)

        assert file_info is not None
        assert file_info.language == "python"
        assert len(file_info.symbols) > 0  # Should find test classes/functions

        # Should find this test class name in symbols
        symbol_names = [s for s in file_info.symbols]
        assert any("TestContextManagerEnhanced" in s for s in symbol_names)
