"""
Basic tests for the new enhanced tools without pytest dependency.
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ocode_python.tools.agent_tool import AgentTool  # noqa: E402
from ocode_python.tools.base import ToolRegistry  # noqa: E402
from ocode_python.tools.bash_tool import BashTool  # noqa: E402
from ocode_python.tools.file_edit_tool import FileEditTool  # noqa: E402

# Import the tools
from ocode_python.tools.glob_tool import GlobTool  # noqa: E402
from ocode_python.tools.grep_tool import GrepTool  # noqa: E402
from ocode_python.tools.ls_tool import LsTool  # noqa: E402
from ocode_python.tools.sticker_tool import StickerRequestTool  # noqa: E402
from ocode_python.tools.think_tool import ThinkTool  # noqa: E402


class SimpleTestRunner:
    """Simple test runner without pytest."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def run_test(self, test_func, test_name):
        """Run a single test function."""
        try:
            if asyncio.iscoroutinefunction(test_func):
                asyncio.run(test_func())
            else:
                test_func()
            print(f"✅ {test_name}")
            self.passed += 1
        except Exception as e:
            print(f"❌ {test_name}: {str(e)}")
            self.failed += 1
            self.errors.append(f"{test_name}: {str(e)}")

    def run_all_tests(self):
        """Run all tests."""
        print("Running basic tool tests...\n")

        # Test GlobTool
        self.run_test(self.test_glob_tool_basic, "GlobTool basic functionality")

        # Test GrepTool
        self.run_test(self.test_grep_tool_basic, "GrepTool basic functionality")

        # Test LsTool
        self.run_test(self.test_ls_tool_basic, "LsTool basic functionality")

        # Test FileEditTool
        self.run_test(
            self.test_file_edit_tool_basic, "FileEditTool basic functionality"
        )

        # Test BashTool
        self.run_test(self.test_bash_tool_basic, "BashTool basic functionality")

        # Test ThinkTool
        self.run_test(self.test_think_tool_basic, "ThinkTool basic functionality")

        # Test AgentTool
        self.run_test(self.test_agent_tool_basic, "AgentTool basic functionality")

        # Test StickerTool
        self.run_test(self.test_sticker_tool_basic, "StickerTool basic functionality")

        # Test Tool Registry
        self.run_test(self.test_tool_registry, "Tool Registry functionality")

        # Test Tool Definitions
        self.run_test(self.test_tool_definitions, "Tool Definitions")

        # Print summary
        print("\nTest Results:")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")

        if self.errors:
            print("\nErrors:")
            for error in self.errors:
                print(f"  - {error}")

        return self.failed == 0

    async def test_glob_tool_basic(self):
        """Test GlobTool basic functionality."""
        tool = GlobTool()
        result = await tool.execute(pattern="*.py", path=".")
        assert result.success, "GlobTool should succeed with *.py pattern"
        assert "files found" in result.output, "Output should mention files found"

    async def test_grep_tool_basic(self):
        """Test GrepTool basic functionality."""
        tool = GrepTool()
        result = await tool.execute(pattern="import", path=".", file_pattern="*.py")
        assert result.success, "GrepTool should succeed with import search"

    async def test_ls_tool_basic(self):
        """Test LsTool basic functionality."""
        tool = LsTool()
        result = await tool.execute(path=".")
        assert result.success, "LsTool should succeed with current directory"
        assert (
            "Directory listing" in result.output or len(result.output) > 0
        ), "Should produce output"

    async def test_file_edit_tool_basic(self):
        """Test FileEditTool basic functionality."""
        tool = FileEditTool()

        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Hello world\n")
            temp_path = f.name

        try:
            # Test appending content
            result = await tool.execute(
                path=temp_path, operation="append", content="Test line"
            )
            assert result.success, "FileEditTool append should succeed"

            # Verify content
            with open(temp_path, "r") as f:
                content = f.read()
                assert (
                    "Hello world" in content and "Test line" in content
                ), "Content should be appended"
        finally:
            Path(temp_path).unlink()

    async def test_bash_tool_basic(self):
        """Test BashTool basic functionality."""
        tool = BashTool()
        result = await tool.execute(command="echo 'Hello Test'")
        assert result.success, "BashTool should succeed with echo command"
        assert "Hello Test" in result.output, "Output should contain echoed text"

    async def test_think_tool_basic(self):
        """Test ThinkTool basic functionality."""
        tool = ThinkTool()
        result = await tool.execute(thinking_type="analyze", topic="Test topic")
        assert result.success, "ThinkTool should succeed with analyze type"
        assert (
            "Analysis" in result.output or "analysis" in result.output.lower()
        ), "Should produce analysis output"

    async def test_agent_tool_basic(self):
        """Test AgentTool basic functionality."""
        tool = AgentTool()
        result = await tool.execute(action="list")
        assert result.success, "AgentTool list should succeed"
        assert "agents" in result.output.lower(), "Should mention agents"

    async def test_sticker_tool_basic(self):
        """Test StickerTool basic functionality."""
        tool = StickerRequestTool()
        result = await tool.execute(action="list")
        assert result.success, "StickerTool list should succeed"

    def test_tool_registry(self):
        """Test Tool Registry functionality."""
        registry = ToolRegistry()
        tool = GlobTool()

        # Test registration
        registry.register(tool)
        assert tool.name in registry.tools, "Tool should be registered"

        # Test retrieval
        retrieved_tool = registry.get_tool(tool.name)
        assert retrieved_tool is tool, "Should retrieve the same tool"

        # Test get all tools
        all_tools = registry.get_all_tools()
        assert tool in all_tools, "Tool should be in all tools list"

    def test_tool_definitions(self):
        """Test that all tools have proper definitions."""
        tools = [
            GlobTool(),
            GrepTool(),
            LsTool(),
            FileEditTool(),
            BashTool(),
            ThinkTool(),
            AgentTool(),
            StickerRequestTool(),
        ]

        for tool in tools:
            definition = tool.definition
            assert definition.name, f"{tool.__class__.__name__} should have a name"
            assert (
                definition.description
            ), f"{tool.__class__.__name__} should have a description"
            assert isinstance(
                definition.parameters, list
            ), f"{tool.__class__.__name__} should have parameters list"

            # Test Ollama format conversion
            ollama_format = definition.to_ollama_format()
            assert "type" in ollama_format, "Should have type in Ollama format"
            assert "function" in ollama_format, "Should have function in Ollama format"


def main():
    """Run all tests."""
    runner = SimpleTestRunner()
    success = runner.run_all_tests()

    if success:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n💥 Some tests failed!")
        return 1


if __name__ == "__main__":
    exit(main())
