"""
Unit tests for context manager.
"""

from pathlib import Path

import pytest

from ocode_python.core.context_manager import ContextManager, FileInfo, ProjectContext


@pytest.mark.unit
class TestContextManager:
    """Test ContextManager functionality."""

    def test_init_with_default_root(self):
        """Test initialization with default root."""
        with ContextManager() as manager:
            assert manager.root == Path.cwd()

    def test_init_with_custom_root(self, temp_dir: Path):
        """Test initialization with custom root."""
        with ContextManager(temp_dir) as manager:
            assert manager.root == temp_dir

    def test_should_ignore_file(self, temp_dir: Path):
        """Test file ignore logic."""
        with ContextManager(temp_dir) as manager:
            # Should ignore
            assert manager._should_ignore(temp_dir / ".git" / "config")
            assert manager._should_ignore(temp_dir / "__pycache__" / "file.pyc")
            assert manager._should_ignore(temp_dir / "file.pyc")
            assert manager._should_ignore(temp_dir / ".DS_Store")

            # Should not ignore
            assert not manager._should_ignore(temp_dir / "main.py")
            assert not manager._should_ignore(temp_dir / "src" / "utils.py")

    def test_should_ignore_large_file(self, temp_dir: Path):
        """Test ignoring large files."""
        with ContextManager(temp_dir) as manager:
            # Create large file
            large_file = temp_dir / "large.txt"
            with open(large_file, "w") as f:
                # Write > 1MB of data
                f.write("x" * (1024 * 1024 + 1))

            assert manager._should_ignore(large_file)

    def test_get_content_hash(self):
        """Test content hashing."""
        with ContextManager() as manager:
            content1 = "Hello, world!"
            content2 = "Hello, world!"
            content3 = "Different content"

            hash1 = manager._get_content_hash(content1)
            hash2 = manager._get_content_hash(content2)
            hash3 = manager._get_content_hash(content3)

            assert hash1 == hash2
            assert hash1 != hash3

    def test_detect_language(self):
        """Test language detection."""
        with ContextManager() as manager:
            test_cases = [
                (Path("script.py"), "python"),
                (Path("app.js"), "typescript"),  # TypeScript analyzer handles .js files
                (Path("app.ts"), "typescript"),
                (Path("README.md"), "markdown"),
                (Path("config.yaml"), "yaml"),
                (Path("main.tf"), "terraform"),
                (Path("unknown.xyz"), None),
                (Path("main.go"), None),  # No Go analyzer yet
                (Path("style.css"), None),  # No CSS analyzer yet
            ]

            for file_path, expected in test_cases:
                assert manager._detect_language(file_path) == expected

    def test_extract_symbols_python(self):
        """Test Python symbol extraction."""
        with ContextManager() as manager:
            content = """
def hello():
    pass

class MyClass:
    def method(self):
        pass
"""

            symbols = manager._extract_symbols(content, "python")
            assert len(symbols) >= 2  # Should find function and class

    def test_extract_imports_python(self):
        """Test Python import extraction."""
        with ContextManager() as manager:
            content = """
import os
from pathlib import Path
import json as js
"""

            imports = manager._extract_imports(content, "python")
            assert len(imports) >= 3

    @pytest.mark.asyncio
    async def test_analyze_file_success(self, mock_project_dir: Path):
        """Test successful file analysis."""
        with ContextManager(mock_project_dir) as manager:
            file_path = mock_project_dir / "main.py"
            file_info = await manager.analyze_file(file_path)

            assert file_info is not None
            assert file_info.path == file_path
            assert file_info.language == "python"
            assert file_info.size > 0
            assert len(file_info.symbols) > 0

    @pytest.mark.asyncio
    async def test_analyze_file_nonexistent(self, temp_dir: Path):
        """Test analyzing non-existent file."""
        with ContextManager(temp_dir) as manager:
            file_path = temp_dir / "nonexistent.py"
            file_info = await manager.analyze_file(file_path)

            assert file_info is None

    @pytest.mark.asyncio
    async def test_analyze_file_ignored(self, temp_dir: Path):
        """Test analyzing ignored file."""
        with ContextManager(temp_dir) as manager:
            # Create ignored file
            ignored_file = temp_dir / ".git" / "config"
            ignored_file.parent.mkdir()
            ignored_file.write_text("ignored content")

            file_info = await manager.analyze_file(ignored_file)
            assert file_info is None

    @pytest.mark.asyncio
    async def test_scan_project(self, mock_project_dir: Path):
        """Test project scanning."""
        with ContextManager(mock_project_dir) as manager:
            files = await manager.scan_project()

            # Should find Python files but not ignore patterns
            python_files = [f for f in files if f.suffix == ".py"]
            assert len(python_files) >= 3  # main.py, utils.py, test_utils.py

            # Should not find ignored files
            git_files = [f for f in files if ".git" in str(f)]
            assert len(git_files) == 0

    @pytest.mark.asyncio
    async def test_build_context(self, mock_project_dir: Path):
        """Test building project context."""
        with ContextManager(mock_project_dir) as manager:
            context = await manager.build_context("test query", max_files=10)

            assert isinstance(context, ProjectContext)
            assert context.project_root == mock_project_dir
            assert len(context.files) > 0
            assert len(context.file_info) > 0

            # Check if we have some symbols
            assert len(context.symbols) > 0

    @pytest.mark.asyncio
    async def test_build_context_with_git(self, mock_git_repo: Path):
        """Test building context with git information."""
        with ContextManager(mock_git_repo) as manager:
            context = await manager.build_context("test query")

            assert context.git_info is not None
            assert "branch" in context.git_info
            assert "commit" in context.git_info

    def test_get_relevant_files(self, mock_project_dir: Path):
        """Test relevant file selection."""
        # Create a simple context
        context = ProjectContext(
            files={
                mock_project_dir / "main.py": "def main(): pass",
                mock_project_dir / "utils.py": "def utility(): pass",
                mock_project_dir / "test_main.py": "def test_main(): pass",
            },
            file_info={},
            dependencies={},
            symbols={
                "main": [mock_project_dir / "main.py"],
                "utility": [mock_project_dir / "utils.py"],
                "test_main": [mock_project_dir / "test_main.py"],
            },
            project_root=mock_project_dir,
        )

        # Query for main-related files
        relevant = context.get_relevant_files("main function", max_files=2)

        assert len(relevant) <= 2
        # Should prefer files with "main" in the name or content
        assert any("main" in str(f) for f in relevant)

    @pytest.mark.asyncio
    async def test_cache_analysis(self, temp_dir: Path):
        """Test caching of file analysis."""
        with ContextManager(temp_dir) as manager:
            # Create test file
            test_file = temp_dir / "test.py"
            test_file.write_text("def test(): pass")

            # First analysis
            file_info1 = await manager.analyze_file(test_file)

            # Second analysis should use cache (same mtime)
            file_info2 = await manager.analyze_file(test_file)

            assert file_info1 is not None
            assert file_info2 is not None
            assert file_info1.content_hash == file_info2.content_hash


@pytest.mark.unit
class TestFileInfo:
    """Test FileInfo data class."""

    def test_file_info_creation(self, temp_dir: Path):
        """Test FileInfo creation."""
        file_path = temp_dir / "test.py"

        file_info = FileInfo(
            path=file_path,
            size=100,
            modified_time=1234567890.0,
            content_hash="abc123",
            language="python",
            symbols=["test_function"],
            imports=["os", "sys"],
        )

        assert file_info.path == file_path
        assert file_info.size == 100
        assert file_info.language == "python"
        assert len(file_info.symbols) == 1
        assert len(file_info.imports) == 2


@pytest.mark.unit
class TestProjectContext:
    """Test ProjectContext data class."""

    def test_project_context_creation(self, temp_dir: Path):
        """Test ProjectContext creation."""
        context = ProjectContext(
            files={temp_dir / "test.py": "content"},
            file_info={},
            dependencies={},
            symbols={"test": [temp_dir / "test.py"]},
            project_root=temp_dir,
        )

        assert len(context.files) == 1
        assert context.project_root == temp_dir
        assert "test" in context.symbols

    def test_get_relevant_files_empty(self, temp_dir: Path):
        """Test relevant files with empty context."""
        context = ProjectContext(
            files={}, file_info={}, dependencies={}, symbols={}, project_root=temp_dir
        )

        relevant = context.get_relevant_files("test query")
        assert len(relevant) == 0
