"""
Comprehensive tests for the new enhanced tools.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ocode_python.tools.agent_tool import AgentTool
from ocode_python.tools.architect_tool import ArchitectTool
from ocode_python.tools.base import ToolResult
from ocode_python.tools.bash_tool import BashTool, ScriptTool
from ocode_python.tools.file_edit_tool import FileEditTool

# Import the tools
from ocode_python.tools.glob_tool import AdvancedGlobTool, GlobTool
from ocode_python.tools.grep_tool import CodeGrepTool, GrepTool
from ocode_python.tools.ls_tool import LsTool
from ocode_python.tools.mcp_tool import MCPTool
from ocode_python.tools.memory_tools import MemoryReadTool, MemoryWriteTool
from ocode_python.tools.notebook_tools import NotebookEditTool, NotebookReadTool
from ocode_python.tools.sticker_tool import StickerRequestTool
from ocode_python.tools.think_tool import ThinkTool


class TestGlobTool:
    """Test the GlobTool for file pattern matching."""

    @pytest.mark.asyncio
    async def test_glob_tool_basic(self):
        tool = GlobTool()

        # Test with simple pattern
        result = await tool.execute(pattern="*.py", path=".", recursive=True)
        assert result.success
        assert "Found" in result.output and "matches" in result.output

    @pytest.mark.asyncio
    async def test_glob_tool_no_matches(self):
        tool = GlobTool()

        # Test with pattern that shouldn't match anything
        result = await tool.execute(pattern="*.nonexistent", path=".")
        assert result.success
        assert "No files found" in result.output

    @pytest.mark.asyncio
    async def test_advanced_glob_tool(self):
        tool = AdvancedGlobTool()

        # Test with size filter
        result = await tool.execute(
            pattern="*.py", path=".", min_size=100, max_size=10000
        )
        assert result.success


class TestGrepTool:
    """Test the GrepTool for text searching."""

    @pytest.mark.asyncio
    async def test_grep_tool_basic(self):
        tool = GrepTool()

        # Test searching for common pattern
        result = await tool.execute(pattern="import", path=".", file_pattern="*.py")
        assert result.success

    @pytest.mark.asyncio
    async def test_grep_tool_no_matches(self):
        tool = GrepTool()

        # Test with pattern that shouldn't match
        result = await tool.execute(pattern="xyznonexistentpatternxyz", path=".")
        assert result.success
        # Either no matches or only matches in this test file
        assert "matches" in result.output

    @pytest.mark.asyncio
    async def test_code_grep_tool(self):
        tool = CodeGrepTool()

        # Test searching for function definitions
        result = await tool.execute(pattern="def ", path=".", language="python")
        assert result.success


class TestLsTool:
    """Test the LsTool for directory listing."""

    @pytest.mark.asyncio
    async def test_ls_tool_basic(self):
        tool = LsTool()

        # Test listing current directory
        result = await tool.execute(path=".")
        assert result.success
        # Check for typical ls output elements
        assert result.output  # Should have some output
        assert "KB" in result.output or "B" in result.output  # Size indicators

    @pytest.mark.asyncio
    async def test_ls_tool_long_format(self):
        tool = LsTool()

        # Test with long format
        result = await tool.execute(path=".", long_format=True)
        assert result.success
        assert "Size" in result.output or "Modified" in result.output

    @pytest.mark.asyncio
    async def test_ls_tool_invalid_path(self):
        tool = LsTool()

        # Test with invalid path
        result = await tool.execute(path="/nonexistent/path")
        assert not result.success
        assert "does not exist" in result.error


class TestFileEditTool:
    """Test the FileEditTool for file editing."""

    @pytest.mark.asyncio
    async def test_file_edit_tool_append(self):
        tool = FileEditTool()

        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Initial content\n")
            temp_path = f.name

        try:
            # Test appending content
            result = await tool.execute(
                path=temp_path, operation="append", content="Appended content"
            )
            assert result.success
            assert "success" in result.output.lower() or result.success

            # Verify content was appended
            with open(temp_path, "r") as f:
                content = f.read()
                assert "Initial content" in content
                assert "Appended content" in content
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_file_edit_tool_replace(self):
        tool = FileEditTool()

        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Hello world\n")
            temp_path = f.name

        try:
            # Test replacing content
            result = await tool.execute(
                path=temp_path,
                operation="replace",
                search_pattern="world",
                replacement="universe",
            )
            assert result.success

            # Verify content was replaced
            with open(temp_path, "r") as f:
                content = f.read()
                assert "Hello universe" in content
        finally:
            Path(temp_path).unlink()


class TestBashTool:
    """Test the BashTool for shell commands."""

    @pytest.mark.asyncio
    async def test_bash_tool_simple_command(self):
        tool = BashTool()

        # Test simple echo command
        result = await tool.execute(command="echo 'Hello World'")
        assert result.success
        assert "Hello World" in result.output

    @pytest.mark.asyncio
    async def test_bash_tool_invalid_command(self):
        tool = BashTool()

        # Test invalid command
        result = await tool.execute(command="nonexistentcommand12345")
        assert not result.success
        # Handle both Unix and Windows error messages
        error_text = (result.error + " " + result.output).lower()
        assert (
            "not found" in error_text
            or "command not found" in error_text
            or "not recognized" in error_text
        )

    @pytest.mark.asyncio
    async def test_script_tool(self):
        tool = ScriptTool()

        # Test multi-line script
        script = """
        echo "Line 1"
        echo "Line 2"
        """
        result = await tool.execute(script=script)
        assert result.success
        assert "Line 1" in result.output
        assert "Line 2" in result.output


class TestNotebookTools:
    """Test the notebook reading and editing tools."""

    @pytest.mark.asyncio
    async def test_notebook_read_tool_invalid_path(self):
        tool = NotebookReadTool()

        # Test with non-existent file
        result = await tool.execute(path="/nonexistent/notebook.ipynb")
        assert not result.success
        assert "path does not exist" in result.error.lower()

    @pytest.mark.asyncio
    async def test_notebook_read_tool_not_notebook(self):
        tool = NotebookReadTool()

        # Test with non-notebook file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Not a notebook")
            temp_path = f.name

        try:
            result = await tool.execute(path=temp_path)
            assert not result.success
            assert "not a Jupyter notebook" in result.error
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_notebook_edit_tool_invalid_path(self):
        tool = NotebookEditTool()

        # Test with non-existent file
        result = await tool.execute(
            path="/nonexistent/notebook.ipynb",
            operation="add_cell",
            source="print('test')",
        )
        assert not result.success
        assert "path does not exist" in result.error.lower()


class TestMemoryTools:
    """Test the memory management tools."""

    @pytest.mark.asyncio
    async def test_memory_write_tool(self):
        tool = MemoryWriteTool()

        # Test setting memory
        result = await tool.execute(
            memory_type="context", operation="set", key="test_key", value="test_value"
        )
        assert result.success
        assert "Set key 'test_key'" in result.output

    @pytest.mark.asyncio
    async def test_memory_read_tool(self):
        tool = MemoryReadTool()

        # Test reading memory
        result = await tool.execute(memory_type="context")
        assert result.success

    @pytest.mark.asyncio
    async def test_memory_invalid_type(self):
        tool = MemoryWriteTool()

        # Test with invalid memory type
        result = await tool.execute(
            memory_type="invalid", operation="set", key="test", value="test"
        )
        assert not result.success
        assert "Unknown memory type" in result.error


class TestThinkTool:
    """Test the structured thinking tool."""

    @pytest.mark.asyncio
    async def test_think_tool_analyze(self):
        tool = ThinkTool()

        # Test analysis thinking
        result = await tool.execute(
            thinking_type="analyze", topic="Code optimization strategies"
        )
        assert result.success
        assert "Analysis of" in result.output

    @pytest.mark.asyncio
    async def test_think_tool_compare(self):
        tool = ThinkTool()

        # Test comparison thinking
        result = await tool.execute(
            thinking_type="compare",
            topic="Programming languages",
            options=["Python", "JavaScript", "Go"],
        )
        assert result.success
        assert "Comparison for" in result.output

    @pytest.mark.asyncio
    async def test_think_tool_missing_params(self):
        tool = ThinkTool()

        # Test with missing required parameters
        result = await tool.execute(thinking_type="analyze")
        assert not result.success
        assert "required parameters" in result.error


class TestArchitectTool:
    """Test the architecture analysis tool."""

    @pytest.mark.asyncio
    async def test_architect_tool_overview(self):
        tool = ArchitectTool()

        # Test overview analysis
        result = await tool.execute(analysis_type="overview", path=".")
        assert result.success
        assert (
            "Project Overview" in result.output or "overview" in result.output.lower()
        )

    @pytest.mark.asyncio
    async def test_architect_tool_invalid_path(self):
        tool = ArchitectTool()

        # Test with invalid path
        result = await tool.execute(analysis_type="overview", path="/nonexistent/path")
        assert not result.success
        assert "does not exist" in result.error

    @pytest.mark.asyncio
    async def test_architect_tool_missing_analysis_type(self):
        tool = ArchitectTool()

        # Test without analysis type
        result = await tool.execute(path=".")
        assert not result.success
        assert "required" in result.error


class TestAgentTool:
    """Test the agent management tool."""

    @pytest.mark.asyncio
    async def test_agent_tool_create(self):
        tool = AgentTool()

        # Test creating an agent
        result = await tool.execute(action="create", agent_type="coder")
        assert result.success
        assert "Created" in result.output
        assert "agent_id" in result.metadata

    @pytest.mark.asyncio
    async def test_agent_tool_list_empty(self):
        tool = AgentTool()

        # Test listing when no agents exist
        result = await tool.execute(action="list")
        assert result.success
        assert "No agents created" in result.output

    @pytest.mark.asyncio
    async def test_agent_tool_invalid_agent_type(self):
        tool = AgentTool()

        # Test with invalid agent type
        result = await tool.execute(action="create", agent_type="invalid_type")
        assert not result.success
        assert "Unknown agent type" in result.error


class TestMCPTool:
    """Test the MCP integration tool."""

    @pytest.mark.asyncio
    async def test_mcp_tool_status(self):
        tool = MCPTool()

        # Test getting status
        result = await tool.execute(action="status")
        assert result.success
        assert "MCP Integration Status" in result.output

    @pytest.mark.asyncio
    async def test_mcp_tool_list_servers_empty(self):
        tool = MCPTool()

        # Test listing servers when none connected
        result = await tool.execute(action="list_servers")
        assert result.success
        assert "No MCP servers connected" in result.output

    @pytest.mark.asyncio
    async def test_mcp_tool_connect_missing_name(self):
        tool = MCPTool()

        # Test connecting without server name
        result = await tool.execute(action="connect")
        assert not result.success
        assert "server_name is required" in result.error


class TestStickerTool:
    """Test the code annotation tool."""

    @pytest.mark.asyncio
    async def test_sticker_tool_add(self):
        tool = StickerRequestTool()

        # Test adding a sticker
        result = await tool.execute(
            action="add", content="Test annotation", file_path="test.py", line_number=10
        )
        assert result.success
        assert "Added" in result.output
        assert "sticker_id" in result.metadata

    @pytest.mark.asyncio
    async def test_sticker_tool_list_empty(self):
        tool = StickerRequestTool()

        # Test listing when no stickers exist
        result = await tool.execute(action="list")
        assert result.success

    @pytest.mark.asyncio
    async def test_sticker_tool_add_missing_content(self):
        tool = StickerRequestTool()

        # Test adding without content
        result = await tool.execute(action="add")
        assert not result.success
        assert "content is required" in result.error

    @pytest.mark.asyncio
    async def test_sticker_tool_invalid_action(self):
        tool = StickerRequestTool()

        # Test with invalid action
        result = await tool.execute(action="invalid_action")
        assert not result.success
        assert "Unknown action" in result.error


class TestToolDefinitions:
    """Test that all tools have proper definitions."""

    def test_all_tools_have_definitions(self):
        """Test that all tools have valid definitions."""
        tools = [
            GlobTool(),
            AdvancedGlobTool(),
            GrepTool(),
            CodeGrepTool(),
            LsTool(),
            FileEditTool(),
            BashTool(),
            ScriptTool(),
            NotebookReadTool(),
            NotebookEditTool(),
            MemoryReadTool(),
            MemoryWriteTool(),
            ThinkTool(),
            ArchitectTool(),
            AgentTool(),
            MCPTool(),
            StickerRequestTool(),
        ]

        for tool in tools:
            definition = tool.definition
            assert definition.name
            assert definition.description
            assert isinstance(definition.parameters, list)

            # Test Ollama format conversion
            ollama_format = definition.to_ollama_format()
            assert "type" in ollama_format
            assert "function" in ollama_format
            assert "name" in ollama_format["function"]
            assert "description" in ollama_format["function"]
            assert "parameters" in ollama_format["function"]


class TestToolRegistry:
    """Test tool registry functionality."""

    def test_tool_registry_registration(self):
        """Test that tools can be registered and retrieved."""
        from ocode_python.tools.base import ToolRegistry

        registry = ToolRegistry()
        tool = GlobTool()

        # Test registration
        registry.register(tool)
        assert tool.name in registry.tools

        # Test retrieval
        retrieved_tool = registry.get_tool(tool.name)
        assert retrieved_tool is tool

        # Test get all tools
        all_tools = registry.get_all_tools()
        assert tool in all_tools

        # Test tool definitions
        definitions = registry.get_tool_definitions()
        assert len(definitions) > 0

    @pytest.mark.asyncio
    async def test_tool_registry_execution(self):
        """Test tool execution through registry."""
        from ocode_python.tools.base import ToolRegistry

        registry = ToolRegistry()
        tool = GlobTool()
        registry.register(tool)

        # Test execution
        result = await registry.execute_tool(tool.name, pattern="*.py", path=".")
        assert isinstance(result, ToolResult)

        # Test non-existent tool
        result = await registry.execute_tool("nonexistent", param="value")
        assert not result.success
        assert "not found" in result.error

    def test_core_tools_registration(self):
        """Test that core tools can be registered."""
        from ocode_python.tools.base import ToolRegistry

        registry = ToolRegistry()

        # This should not raise an exception
        registry.register_core_tools()

        # Verify some tools were registered
        tools = registry.get_all_tools()
        assert len(tools) > 10  # We should have many tools registered

        # Check for some specific tools
        tool_names = [tool.name for tool in tools]
        assert "glob" in tool_names
        assert "grep" in tool_names
        assert "ls" in tool_names


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
