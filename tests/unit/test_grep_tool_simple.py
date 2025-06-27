"""Simple unit tests for grep tool."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ocode_python.tools.grep_tool import GrepTool


class TestGrepTool:
    """Test GrepTool functionality."""

    @pytest.fixture
    def grep_tool(self):
        """Create GrepTool instance."""
        return GrepTool()

    @pytest.fixture
    def temp_files(self):
        """Create temporary files for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test files
            (tmpdir_path / "test.py").write_text(
                """
def hello_world():
    print("Hello, World!")

class TestClass:
    def method(self):
        return True
"""
            )

            (tmpdir_path / "test.js").write_text(
                """
function helloWorld() {
    console.log("Hello, World!");
}

class TestClass {
    method() {
        return true;
    }
}
"""
            )

            (tmpdir_path / "README.md").write_text(
                """
# Test Project

This is a test project with Hello World examples.
"""
            )

            yield tmpdir_path

    def test_grep_tool_definition(self, grep_tool):
        """Test grep tool definition."""
        definition = grep_tool.definition

        assert definition.name == "grep"
        assert "search" in definition.description.lower()

        param_names = [p.name for p in definition.parameters]
        assert "pattern" in param_names
        assert "path" in param_names

    @pytest.mark.asyncio
    async def test_basic_grep_search(self, grep_tool, temp_files):
        """Test basic grep search functionality."""
        # Mock the subprocess call
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = f"{temp_files}/test.py:2:def hello_world():\n{temp_files}/test.js:1:function helloWorld() {{"  # noqa: E501
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = await grep_tool.execute(pattern="hello", path=str(temp_files))

            assert result.success
            assert "test.py" in result.output
            assert "test.js" in result.output
            assert "hello_world" in result.output or "helloWorld" in result.output

    @pytest.mark.asyncio
    async def test_grep_with_include_filter(self, grep_tool, temp_files):
        """Test grep with file include filter."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = f"{temp_files}/test.py:2:def hello_world():"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = await grep_tool.execute(
                pattern="hello", path=str(temp_files), file_pattern="*.py"
            )

            assert result.success
            assert "test.py" in result.output
            # Should not include .js files due to filter

    @pytest.mark.asyncio
    async def test_grep_no_matches(self, grep_tool, temp_files):
        """Test grep with no matches."""
        mock_result = Mock()
        mock_result.returncode = 1  # grep returns 1 when no matches
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = await grep_tool.execute(
                pattern="nonexistent", path=str(temp_files)
            )

            assert result.success  # Should still be successful even with no matches
            assert result.output == "" or "No matches found" in result.output

    @pytest.mark.asyncio
    async def test_grep_error_handling(self, grep_tool):
        """Test grep error handling."""
        mock_result = Mock()
        mock_result.returncode = 2  # Error code
        mock_result.stdout = ""
        mock_result.stderr = "grep: /nonexistent: No such file or directory"

        with patch("subprocess.run", return_value=mock_result):
            result = await grep_tool.execute(pattern="test", path="/nonexistent/path")

            assert not result.success
            assert (
                "error" in (result.error or "").lower()
                or "does not exist" in (result.error or "").lower()
            )

    @pytest.mark.asyncio
    async def test_grep_tool_basic_functionality(self, grep_tool, temp_files):
        """Test that grep tool can handle real searches."""
        # This is more of an integration test
        result = await grep_tool.execute(pattern="Hello", path=str(temp_files))

        # Should succeed with actual files
        assert result.success
        assert "Hello" in result.output

    def test_grep_tool_name(self, grep_tool):
        """Test grep tool name property."""
        assert grep_tool.name == "grep"

    @pytest.mark.asyncio
    async def test_grep_with_special_characters(self, grep_tool, temp_files):
        """Test grep with special regex characters."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = f'{temp_files}/test.py:3:    print("Hello, World!")'
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = await grep_tool.execute(pattern='"Hello.*"', path=str(temp_files))

            assert result.success
            assert "Hello" in result.output
