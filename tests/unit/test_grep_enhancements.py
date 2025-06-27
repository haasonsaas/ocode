"""
Tests for enhanced grep tool features.
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ocode_python.tools.grep_tool import CodeGrepTool, GrepTool


class TestGrepEnhancements:
    """Test enhanced grep tool features."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory with test files."""
        temp_dir = tempfile.mkdtemp()

        # Create test files
        (Path(temp_dir) / "test1.py").write_text(
            """
def hello_world():
    # This is a comment with TODO
    print("Hello, TODO World!")
    return True

def calculate_sum(a, b):
    '''Calculate the sum of two numbers'''
    result = a + b  # TODO: Add validation
    return result
"""
        )

        (Path(temp_dir) / "test2.js").write_text(
            """
function greetUser(name) {
    // TODO: Add validation
    console.log(`Hello, ${name}!`);
    return `Welcome ${name}`;
}

/* TODO: Implement this function */
const calculateProduct = (x, y) => {
    return x * y;
};
"""
        )

        (Path(temp_dir) / "test.txt").write_text(
            """
Line 1
Line 2
Line 3 with MATCH
Line 4
Line 5
Line 6
Line 7 with MATCH
Line 8
Line 9
"""
        )

        # Create binary file
        (Path(temp_dir) / "binary.bin").write_bytes(b"\x00\x01\x02\x03\x04\x05")

        # Create nested directory
        nested = Path(temp_dir) / "nested"
        nested.mkdir()
        (nested / "nested.py").write_text("def nested(): return 'TODO'")

        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_ripgrep_integration(self, temp_dir):
        """Test ripgrep integration when available."""
        tool = GrepTool()

        # Check if ripgrep is available
        if tool.has_ripgrep:
            # Force use of ripgrep
            tool.use_ripgrep = True

            result = await tool.execute(pattern="TODO", path=temp_dir, recursive=True)

            assert result.success
            assert result.metadata["matches_found"] > 0
            assert "TODO" in result.output

    @pytest.mark.asyncio
    async def test_context_lines(self, temp_dir):
        """Test context lines support."""
        tool = GrepTool()
        # Force Python implementation to test our context logic
        tool.use_ripgrep = False

        result = await tool.execute(
            pattern="MATCH", path=str(Path(temp_dir) / "test.txt"), context_lines=2
        )

        assert result.success
        assert result.metadata["matches_found"] == 2

        # Check that context is included
        matches = result.metadata.get("matches", [])
        if matches:
            # First match should have before context
            first_match = matches[0]
            assert any(
                ctx["type"] == "before" for ctx in first_match.get("context", [])
            )
            assert any(ctx["type"] == "after" for ctx in first_match.get("context", []))

    @pytest.mark.asyncio
    async def test_brace_expansion(self, temp_dir):
        """Test file pattern with brace expansion."""
        tool = GrepTool()

        result = await tool.execute(
            pattern="TODO", path=temp_dir, file_pattern="*.{py,js}", recursive=True
        )

        assert result.success
        # Should find matches in both .py and .js files
        assert "test1.py" in result.output
        assert "test2.js" in result.output
        assert "test.txt" not in result.output

    @pytest.mark.asyncio
    async def test_binary_file_detection(self, temp_dir):
        """Test that binary files are skipped."""
        tool = GrepTool()
        # Force Python implementation
        tool.use_ripgrep = False

        result = await tool.execute(pattern=".*", path=temp_dir, recursive=True)

        assert result.success
        # Binary file should be skipped
        assert "binary.bin" not in result.output

    @pytest.mark.asyncio
    async def test_parallel_processing(self, temp_dir):
        """Test parallel file processing."""
        # Create many files
        for i in range(10):
            (Path(temp_dir) / f"file{i}.txt").write_text(f"File {i} with PATTERN")

        tool = GrepTool()
        # Force Python implementation with parallel processing
        tool.use_ripgrep = False
        tool.parallel_workers = 4

        result = await tool.execute(pattern="PATTERN", path=temp_dir, recursive=False)

        assert result.success
        assert result.metadata["matches_found"] == 10

    @pytest.mark.asyncio
    async def test_config_integration(self):
        """Test configuration support."""
        config = {"use_ripgrep": False, "parallel_grep_workers": 2}

        tool = GrepTool(config=config)

        assert tool.use_ripgrep is False
        assert tool.parallel_workers == 2

    @pytest.mark.asyncio
    async def test_code_grep_with_comments(self, temp_dir):
        """Test code grep excluding comments."""
        tool = CodeGrepTool()
        # Force Python implementation
        tool.use_ripgrep = False

        result = await tool.execute(
            pattern="TODO",
            path=temp_dir,
            file_pattern="*.py",
            exclude_comments=True,
            recursive=True,
        )

        assert result.success
        # Should find TODO in string but not in comments
        matches = result.metadata["matches_found"]
        assert matches > 0

        # Check that comment lines are excluded
        assert "# This is a comment with TODO" not in result.output
        assert "# TODO: Add validation" not in result.output

    @pytest.mark.asyncio
    async def test_max_matches_limit(self, temp_dir):
        """Test max matches limit."""
        # Create file with many matches
        content = "\n".join([f"Line {i} MATCH" for i in range(100)])
        (Path(temp_dir) / "many_matches.txt").write_text(content)

        tool = GrepTool()
        tool.use_ripgrep = False

        result = await tool.execute(
            pattern="MATCH",
            path=str(Path(temp_dir) / "many_matches.txt"),
            max_matches=10,
        )

        assert result.success
        assert result.metadata["matches_found"] == 10

    @pytest.mark.asyncio
    async def test_case_insensitive_search(self, temp_dir):
        """Test case insensitive search."""
        (Path(temp_dir) / "case_test.txt").write_text(
            """
TODO in caps
todo in lower
ToDo in mixed
"""
        )

        tool = GrepTool()

        result = await tool.execute(
            pattern="todo",
            path=str(Path(temp_dir) / "case_test.txt"),
            case_sensitive=False,
        )

        assert result.success
        assert result.metadata["matches_found"] == 3

    @pytest.mark.asyncio
    async def test_whole_word_matching(self, temp_dir):
        """Test whole word matching."""
        (Path(temp_dir) / "word_test.txt").write_text(
            """
test word
testing word
word test
wordtest
"""
        )

        tool = GrepTool()

        result = await tool.execute(
            pattern="test", path=str(Path(temp_dir) / "word_test.txt"), whole_word=True
        )

        assert result.success
        assert result.metadata["matches_found"] == 2  # Only "test word" and "word test"

    @pytest.mark.asyncio
    async def test_ripgrep_fallback(self, temp_dir):
        """Test fallback to Python implementation when ripgrep fails."""
        tool = GrepTool()

        # Mock ripgrep to fail
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = MagicMock()
            mock_proc.communicate.side_effect = Exception("ripgrep failed")
            mock_exec.return_value = mock_proc

            result = await tool.execute(pattern="TODO", path=temp_dir, recursive=True)

            # Should still succeed using Python implementation
            assert result.success
            assert result.metadata["matches_found"] > 0

    def test_parse_file_pattern(self):
        """Test file pattern parsing."""
        tool = GrepTool()

        # Test brace expansion
        patterns = tool._parse_file_pattern("*.{js,ts,jsx,tsx}")
        assert patterns == ["*.js", "*.ts", "*.jsx", "*.tsx"]

        # Test simple pattern
        patterns = tool._parse_file_pattern("*.py")
        assert patterns == ["*.py"]

        # Test complex pattern
        patterns = tool._parse_file_pattern("test.{py,js}")
        assert patterns == ["test.py", "test.js"]

    def test_is_binary_file(self, temp_dir):
        """Test binary file detection."""
        tool = GrepTool()

        # Test text file
        text_file = Path(temp_dir) / "text.txt"
        text_file.write_text("Hello world")
        assert not tool._is_binary_file(text_file)

        # Test binary file
        binary_file = Path(temp_dir) / "binary.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03")
        assert tool._is_binary_file(binary_file)

        # Test empty file
        empty_file = Path(temp_dir) / "empty.txt"
        empty_file.touch()
        assert not tool._is_binary_file(empty_file)
