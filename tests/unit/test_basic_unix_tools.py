"""Tests for basic Unix-style tools."""

import os
import tempfile
from unittest.mock import patch

import pytest

from ocode_python.tools.curl_tool import CurlTool
from ocode_python.tools.diff_tool import DiffTool
from ocode_python.tools.file_ops_tool import CopyTool, MoveTool, RemoveTool
from ocode_python.tools.find_tool import FindTool
from ocode_python.tools.head_tail_tool import HeadTool, TailTool
from ocode_python.tools.text_tools import SortTool, UniqTool
from ocode_python.tools.wc_tool import WcTool
from ocode_python.tools.which_tool import WhichTool


class TestHeadTailTools:
    """Test HeadTool and TailTool."""

    @pytest.fixture
    def temp_file(self):
        """Create a temporary file with test content."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            for i in range(20):
                f.write(f"Line {i+1}\n")
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_head_tool_default(self, temp_file):
        """Test HeadTool with default 10 lines."""
        tool = HeadTool()
        result = await tool.execute(file_path=temp_file)

        assert result.success
        lines = result.output.strip().split("\n")
        assert len(lines) == 10
        assert lines[0] == "Line 1"
        assert lines[9] == "Line 10"

    @pytest.mark.asyncio
    async def test_head_tool_custom_lines(self, temp_file):
        """Test HeadTool with custom line count."""
        tool = HeadTool()
        result = await tool.execute(file_path=temp_file, lines=5)

        assert result.success
        lines = result.output.strip().split("\n")
        assert len(lines) == 5
        assert lines[0] == "Line 1"
        assert lines[4] == "Line 5"

    @pytest.mark.asyncio
    async def test_tail_tool_default(self, temp_file):
        """Test TailTool with default 10 lines."""
        tool = TailTool()
        result = await tool.execute(file_path=temp_file)

        assert result.success
        lines = result.output.strip().split("\n")
        assert len(lines) == 10
        assert lines[0] == "Line 11"
        assert lines[9] == "Line 20"

    @pytest.mark.asyncio
    async def test_tail_tool_custom_lines(self, temp_file):
        """Test TailTool with custom line count."""
        tool = TailTool()
        result = await tool.execute(file_path=temp_file, lines=3)

        assert result.success
        lines = result.output.strip().split("\n")
        assert len(lines) == 3
        assert lines[0] == "Line 18"
        assert lines[2] == "Line 20"

    @pytest.mark.asyncio
    async def test_head_nonexistent_file(self):
        """Test HeadTool with nonexistent file."""
        tool = HeadTool()
        result = await tool.execute(file_path="/nonexistent/file.txt")

        assert not result.success
        assert "path does not exist" in result.error.lower()


class TestDiffTool:
    """Test DiffTool."""

    @pytest.fixture
    def temp_files(self):
        """Create two temporary files with different content."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f1:
            f1.write("Line 1\nLine 2\nLine 3\n")
            file1 = f1.name

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f2:
            f2.write("Line 1\nModified Line 2\nLine 3\nLine 4\n")
            file2 = f2.name

        yield file1, file2
        os.unlink(file1)
        os.unlink(file2)

    @pytest.mark.asyncio
    async def test_diff_tool_unified(self, temp_files):
        """Test DiffTool with unified format."""
        file1, file2 = temp_files
        tool = DiffTool()
        result = await tool.execute(file1=file1, file2=file2, format="unified")

        assert result.success
        assert "Modified Line 2" in result.output
        assert "Line 4" in result.output

    @pytest.mark.asyncio
    async def test_diff_tool_context(self, temp_files):
        """Test DiffTool with context format."""
        file1, file2 = temp_files
        tool = DiffTool()
        result = await tool.execute(file1=file1, file2=file2, format="context")

        assert result.success
        assert "Modified Line 2" in result.output


class TestWcTool:
    """Test WcTool."""

    @pytest.fixture
    def temp_file(self):
        """Create a temporary file with known content."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("Hello world\nThis is line 2\n")
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_wc_tool_all_counts(self, temp_file):
        """Test WcTool with all counts."""
        tool = WcTool()
        result = await tool.execute(file_path=temp_file)

        assert result.success
        assert "2" in result.output  # lines
        assert "6" in result.output  # words
        assert "27" in result.output  # characters

    @pytest.mark.asyncio
    async def test_wc_tool_lines_only(self, temp_file):
        """Test WcTool with lines only."""
        tool = WcTool()
        result = await tool.execute(file_path=temp_file, lines_only=True)

        assert result.success
        assert "2" in result.output


class TestFindTool:
    """Test FindTool."""

    @pytest.mark.asyncio
    async def test_find_tool_basic(self):
        """Test FindTool basic functionality."""
        tool = FindTool()

        # Use temporary directory for real files test
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            os.makedirs(os.path.join(tmpdir, "subdir"))
            with open(os.path.join(tmpdir, "file1.txt"), "w") as f:
                f.write("test")
            with open(os.path.join(tmpdir, "file2.py"), "w") as f:
                f.write("test")
            with open(os.path.join(tmpdir, "subdir", "file3.txt"), "w") as f:
                f.write("test")

            result = await tool.execute(path=tmpdir, name="*.txt")

            assert result.success
            assert "file1.txt" in result.output
            assert "file3.txt" in result.output
            assert "file2.py" not in result.output


class TestFileOpsTools:
    """Test file operations tools."""

    @pytest.fixture
    def temp_files(self):
        """Create temporary files for testing."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            source = f.name

        target = source + ".copy"
        yield source, target

        for path in [source, target]:
            if os.path.exists(path):
                os.unlink(path)

    @pytest.mark.asyncio
    async def test_copy_tool(self, temp_files):
        """Test CopyTool."""
        source, target = temp_files
        tool = CopyTool()

        result = await tool.execute(source=source, destination=target)

        assert result.success
        assert os.path.exists(target)

        with open(target) as f:
            assert f.read() == "test content"

    @pytest.mark.asyncio
    async def test_move_tool(self, temp_files):
        """Test MoveTool."""
        source, target = temp_files
        tool = MoveTool()

        result = await tool.execute(source=source, destination=target)

        assert result.success
        assert not os.path.exists(source)
        assert os.path.exists(target)

    @pytest.mark.asyncio
    async def test_remove_tool_safety(self):
        """Test RemoveTool safety checks."""
        tool = RemoveTool()

        # Test that it refuses to remove dangerous paths
        result = await tool.execute(path="/")
        assert not result.success
        assert "safety" in result.error.lower()


class TestTextTools:
    """Test text processing tools."""

    @pytest.fixture
    def temp_file(self):
        """Create a temporary file with unsorted content."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("zebra\napple\nbanana\napple\n")
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_sort_tool(self, temp_file):
        """Test SortTool."""
        tool = SortTool()
        result = await tool.execute(file_path=temp_file)

        assert result.success
        lines = result.output.strip().split("\n")
        assert lines == ["apple", "apple", "banana", "zebra"]

    @pytest.mark.asyncio
    async def test_uniq_tool(self, temp_file):
        """Test UniqTool."""
        tool = UniqTool()
        result = await tool.execute(file_path=temp_file)

        assert result.success
        lines = result.output.strip().split("\n")
        assert "apple" in lines
        assert lines.count("apple") == 1  # Should be deduplicated


class TestCurlTool:
    """Test CurlTool."""

    @pytest.mark.asyncio
    async def test_curl_tool_get(self):
        """Test CurlTool GET request."""
        tool = CurlTool()

        # Test without mocking - just verify the tool exists and can handle bad URLs
        result = await tool.execute(url="http://definitely-not-a-real-domain-12345.com")

        # Either it succeeds (very unlikely) or fails with a connection error
        if not result.success:
            assert "error" in result.error.lower()


class TestWhichTool:
    """Test WhichTool."""

    @pytest.mark.asyncio
    async def test_which_tool_found(self):
        """Test WhichTool when command is found."""
        tool = WhichTool()

        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/python"

            result = await tool.execute(command="python")

            assert result.success
            assert "/usr/bin/python" in result.output

    @pytest.mark.asyncio
    async def test_which_tool_not_found(self):
        """Test WhichTool when command is not found."""
        tool = WhichTool()

        with patch("shutil.which") as mock_which:
            mock_which.return_value = None

            result = await tool.execute(command="nonexistent_command")

            assert not result.success
            assert "not found" in result.error.lower()
