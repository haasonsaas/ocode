"""
Unit tests for tools.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ocode_python.tools.base import (
    ToolDefinition,
    ToolParameter,
    ToolRegistry,
    ToolResult,
)
from ocode_python.tools.file_tools import FileListTool, FileReadTool, FileWriteTool
from ocode_python.tools.git_tools import GitCommitTool, GitStatusTool
from ocode_python.tools.shell_tools import ShellCommandTool
from ocode_python.tools.test_tools import ExecutionTool


@pytest.mark.unit
class TestToolRegistry:
    """Test ToolRegistry functionality."""

    def test_registry_init(self):
        """Test registry initialization."""
        registry = ToolRegistry()
        assert len(registry.tools) == 0

    def test_register_tool(self):
        """Test tool registration."""
        registry = ToolRegistry()
        tool = FileReadTool()

        registry.register(tool)

        assert tool.name in registry.tools
        assert registry.get_tool(tool.name) is tool

    def test_register_core_tools(self):
        """Test core tools registration."""
        registry = ToolRegistry()
        registry.register_core_tools()

        assert len(registry.tools) > 0
        assert "file_read" in registry.tools
        assert "git_status" in registry.tools
        assert "shell_command" in registry.tools

    def test_get_tool_definitions(self):
        """Test getting tool definitions."""
        registry = ToolRegistry()
        registry.register(FileReadTool())

        definitions = registry.get_tool_definitions()

        assert len(definitions) == 1
        assert definitions[0]["type"] == "function"
        assert "file_read" in definitions[0]["function"]["name"]

    @pytest.mark.asyncio
    async def test_execute_tool_success(self, temp_dir: Path):
        """Test successful tool execution."""
        registry = ToolRegistry()
        registry.register(FileReadTool())

        # Create test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, world!")

        result = await registry.execute_tool("file_read", path=str(test_file))

        assert result.success
        assert "Hello, world!" in result.output

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self):
        """Test executing non-existent tool."""
        registry = ToolRegistry()

        result = await registry.execute_tool("nonexistent_tool")

        assert not result.success
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_tool_invalid_params(self):
        """Test executing tool with invalid parameters."""
        registry = ToolRegistry()
        registry.register(FileReadTool())

        result = await registry.execute_tool("file_read")  # Missing required path

        assert not result.success
        assert "Invalid parameters" in result.error

    @pytest.mark.asyncio
    async def test_all_tools_registration_and_execution(self, temp_dir: Path):
        """Test that all tools can be registered and executed with basic parameters."""
        registry = ToolRegistry()
        registry.register_core_tools()

        # Create test files for file operations
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test content")

        test_dir = temp_dir / "test_dir"
        test_dir.mkdir()

        # Test each tool with minimal valid parameters
        for tool in registry.get_all_tools():
            tool_name = tool.definition.name
            print(f"Testing tool: {tool_name}")

            # Skip tools that require specific setup or are not suitable for basic testing  # noqa: E501
            if tool_name in [
                "git_status",
                "git_commit",
                "git_diff",
                "test_runner",
                "mcp",
            ]:
                continue

            try:
                # Prepare minimal valid parameters based on tool type
                params = {}

                if tool_name == "file_read":
                    params = {"path": str(test_file)}
                elif tool_name == "file_write":
                    params = {"path": str(test_file), "content": "Test content"}
                elif tool_name == "file_list":
                    params = {"path": str(temp_dir)}
                elif tool_name == "shell_command":
                    params = {"command": "echo test"}
                elif tool_name == "glob":
                    params = {"pattern": "*.txt", "path": str(temp_dir)}
                elif tool_name == "grep":
                    params = {"pattern": "test", "path": str(temp_dir)}
                elif tool_name == "ls":
                    params = {"path": str(temp_dir)}
                elif tool_name == "file_edit":
                    params = {
                        "path": str(test_file),
                        "operation": "append",
                        "content": "test",
                    }
                elif tool_name == "bash":
                    params = {"script": "echo test"}
                elif tool_name == "memory_read":
                    params = {"memory_type": "persistent"}
                elif tool_name == "memory_write":
                    params = {
                        "memory_type": "persistent",
                        "key": "test",
                        "value": "test",
                    }
                elif tool_name == "think":
                    params = {"thinking_type": "analyze", "topic": "test"}
                elif tool_name == "architect":
                    params = {"path": str(temp_dir)}
                elif tool_name == "agent":
                    params = {"action": "list"}
                elif tool_name == "sticker":
                    params = {"action": "list"}

                # Execute tool
                result = await registry.execute_tool(tool_name, **params)

                # Basic validation
                assert isinstance(
                    result, ToolResult
                ), f"Tool {tool_name} did not return ToolResult"
                assert hasattr(
                    result, "success"
                ), f"Tool {tool_name} result missing success attribute"
                assert hasattr(
                    result, "output"
                ), f"Tool {tool_name} result missing output attribute"

                # Log result for debugging
                print(f"  Result: {'Success' if result.success else 'Failed'}")
                if not result.success:
                    print(f"  Error: {result.error}")

            except Exception as e:
                pytest.fail(f"Tool {tool_name} failed with error: {str(e)}")

    @pytest.mark.asyncio
    async def test_tool_name_mapping(self):
        """Test that tool names are mapped correctly."""
        from ocode_python.core.engine import OCodeEngine

        engine = OCodeEngine()
        registry = ToolRegistry()
        registry.register_core_tools()

        # Test various tool name formats
        test_cases = [
            ("file_read", "file_read"),
            ("file_write", "file_write"),
            ("shell_command", "shell_command"),
            ("memory_read", "memory_read"),
            ("memory_write", "memory_write"),
            ("git_status", "git_status"),
            ("test_runner", "test_runner"),
            ("glob", "glob"),
            ("grep", "grep"),
            ("ls", "ls"),
            ("file_edit", "file_edit"),
            ("bash", "bash"),
            ("think", "think"),
            ("architect", "architect"),
            ("agent", "agent"),
            ("sticker", "sticker"),
        ]

        for input_name, expected_name in test_cases:
            mapped_name = engine._map_tool_name(input_name)
            assert (
                mapped_name == expected_name
            ), f"Tool name mapping failed: {input_name} -> {mapped_name} (expected {expected_name})"  # noqa: E501

            # Verify the mapped name exists in the registry
            tool = registry.get_tool(mapped_name)
            assert (
                tool is not None
            ), f"Mapped tool name {mapped_name} not found in registry"
            assert (
                tool.name == expected_name
            ), f"Tool name mismatch: {tool.name} != {expected_name}"


@pytest.mark.unit
class TestFileTools:
    """Test file manipulation tools."""

    @pytest.mark.asyncio
    async def test_file_read_success(self, temp_dir: Path):
        """Test successful file reading."""
        tool = FileReadTool()

        test_file = temp_dir / "test.txt"
        content = "Hello, world!\nThis is a test file."
        test_file.write_text(content)

        result = await tool.execute(path=str(test_file))

        assert result.success
        assert result.output == content
        assert result.metadata["file_size"] > 0

    @pytest.mark.asyncio
    async def test_file_read_not_found(self, temp_dir: Path):
        """Test reading non-existent file."""
        tool = FileReadTool()

        result = await tool.execute(path=str(temp_dir / "nonexistent.txt"))

        assert not result.success
        assert "does not exist" in result.error

    @pytest.mark.asyncio
    async def test_file_write_success(self, temp_dir: Path):
        """Test successful file writing."""
        tool = FileWriteTool()

        test_file = temp_dir / "output.txt"
        content = "This is test content."

        result = await tool.execute(path=str(test_file), content=content)

        assert result.success
        assert test_file.exists()
        assert test_file.read_text() == content

    @pytest.mark.asyncio
    async def test_file_write_create_dirs(self, temp_dir: Path):
        """Test file writing with directory creation."""
        tool = FileWriteTool()

        test_file = temp_dir / "subdir" / "output.txt"
        content = "Test content"

        result = await tool.execute(
            path=str(test_file), content=content, create_dirs=True
        )

        assert result.success
        assert test_file.exists()
        assert test_file.read_text() == content

    @pytest.mark.asyncio
    async def test_file_list_success(self, mock_project_dir: Path):
        """Test successful directory listing."""
        tool = FileListTool()

        result = await tool.execute(path=str(mock_project_dir))

        assert result.success
        assert "main.py" in result.output
        assert "utils.py" in result.output
        assert result.metadata["file_count"] > 0

    @pytest.mark.asyncio
    async def test_file_list_recursive(self, mock_project_dir: Path):
        """Test recursive directory listing."""
        tool = FileListTool()

        result = await tool.execute(path=str(mock_project_dir), recursive=True)

        assert result.success
        # Handle both Windows and Unix path separators - be more flexible
        result_output = result.output.replace("\\", "/")  # Normalize to forward slashes
        assert "mypackage/module.py" in result_output

    @pytest.mark.asyncio
    async def test_file_list_filter_extensions(self, mock_project_dir: Path):
        """Test directory listing with extension filter."""
        tool = FileListTool()

        result = await tool.execute(path=str(mock_project_dir), extensions=[".py"])

        assert result.success
        # Should only show Python files
        assert ".toml" not in result.output or "pyproject.toml" not in result.output


@pytest.mark.unit
class TestGitTools:
    """Test Git integration tools."""

    @pytest.mark.asyncio
    async def test_git_status_success(self, mock_git_repo: Path):
        """Test successful git status."""
        tool = GitStatusTool()

        result = await tool.execute(path=str(mock_git_repo))

        assert result.success
        assert "Branch:" in result.output
        assert "Commit:" in result.output

    @pytest.mark.asyncio
    async def test_git_status_not_repo(self, temp_dir: Path):
        """Test git status on non-repo directory."""
        tool = GitStatusTool()

        result = await tool.execute(path=str(temp_dir))

        assert not result.success
        assert "Not a git repository" in result.error

    @pytest.mark.asyncio
    async def test_git_commit_success(self, mock_git_repo: Path):
        """Test successful git commit."""
        tool = GitCommitTool()

        # Create a new file to commit
        new_file = mock_git_repo / "new_file.txt"
        new_file.write_text("New content")

        result = await tool.execute(path=str(mock_git_repo), message="Add new file")

        assert result.success
        assert "Created commit" in result.output

    @pytest.mark.asyncio
    async def test_git_commit_no_changes(self, mock_git_repo: Path):
        """Test git commit with no changes."""
        tool = GitCommitTool()

        result = await tool.execute(path=str(mock_git_repo), message="No changes")

        assert not result.success
        assert "No changes to commit" in result.error


@pytest.mark.unit
class TestShellTools:
    """Test shell command tools."""

    def test_command_validation(self):
        """Test command validation."""
        tool = ShellCommandTool()

        # Safe commands
        allowed, error = tool._is_command_allowed("ls -la")
        assert allowed

        allowed, error = tool._is_command_allowed("python script.py")
        assert allowed

        # Dangerous commands
        allowed, error = tool._is_command_allowed("rm -rf /")
        assert not allowed
        assert "blocked" in error.lower()

        allowed, error = tool._is_command_allowed("sudo apt install")
        assert not allowed

        # Dangerous patterns
        allowed, error = tool._is_command_allowed("echo hello > /etc/passwd")
        assert not allowed
        assert "dangerous pattern" in error

    @pytest.mark.asyncio
    async def test_shell_command_success(self):
        """Test successful shell command execution."""
        tool = ShellCommandTool()

        result = await tool.execute(command="echo 'Hello, world!'")

        assert result.success
        assert "Hello, world!" in result.output

    @pytest.mark.asyncio
    async def test_shell_command_blocked(self):
        """Test blocked shell command."""
        tool = ShellCommandTool()

        result = await tool.execute(command="rm -rf /")

        assert not result.success
        assert "blocked" in result.error.lower()

    @pytest.mark.asyncio
    async def test_shell_command_timeout(self):
        """Test shell command timeout."""
        import platform

        tool = ShellCommandTool()

        # Use platform-appropriate long-running command
        if platform.system() == "Windows":
            # Windows: Use ping to localhost as a delay mechanism (no redirection)
            command = "ping -n 11 127.0.0.1"
        else:
            # Unix sleep command
            command = 'python -c "import time; time.sleep(10)"'

        result = await tool.execute(command=command, timeout=1)

        assert not result.success
        assert "timed out" in result.error.lower()


@pytest.mark.unit
class TestTestTools:
    """Test testing framework tools."""

    def test_framework_detection(self, mock_project_dir: Path):
        """Test test framework detection."""
        tool = ExecutionTool()

        framework = tool._detect_test_framework(str(mock_project_dir))

        # Should detect pytest due to test files
        assert framework in ["pytest", "unittest"]

    @pytest.mark.asyncio
    async def test_pytest_execution(self, mock_project_dir: Path):
        """Test pytest execution."""
        tool = ExecutionTool()

        with patch("asyncio.create_subprocess_shell") as mock_subprocess:
            # Mock successful test run
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (
                b"test_utils.py::test_add PASSED\n2 passed in 0.1s",
                b"",
            )
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            result = await tool._run_pytest(str(mock_project_dir), None, False, 300)

            assert result.success
            assert "PASSED" in result.output


@pytest.mark.unit
class TestToolDefinitions:
    """Test tool definition structures."""

    def test_tool_parameter_creation(self):
        """Test ToolParameter creation."""
        param = ToolParameter(
            name="test_param",
            type="string",
            description="Test parameter",
            required=True,
            default="default_value",
        )

        assert param.name == "test_param"
        assert param.type == "string"
        assert param.required
        assert param.default == "default_value"

    def test_tool_definition_creation(self):
        """Test ToolDefinition creation."""
        params = [
            ToolParameter("param1", "string", "First parameter", True),
            ToolParameter("param2", "number", "Second parameter", False, 42),
        ]

        definition = ToolDefinition(
            name="test_tool", description="Test tool", parameters=params
        )

        assert definition.name == "test_tool"
        assert len(definition.parameters) == 2

    def test_tool_definition_ollama_format(self):
        """Test conversion to Ollama format."""
        params = [
            ToolParameter("text", "string", "Input text", True),
            ToolParameter("count", "number", "Count", False, 1),
        ]

        definition = ToolDefinition(
            name="echo_tool", description="Echo text multiple times", parameters=params
        )

        ollama_format = definition.to_ollama_format()

        assert ollama_format["type"] == "function"
        assert ollama_format["function"]["name"] == "echo_tool"
        assert "text" in ollama_format["function"]["parameters"]["properties"]
        assert "count" in ollama_format["function"]["parameters"]["properties"]
        assert "text" in ollama_format["function"]["parameters"]["required"]
        assert "count" not in ollama_format["function"]["parameters"]["required"]

    def test_tool_result_creation(self):
        """Test ToolResult creation."""
        # Success result
        result = ToolResult(
            success=True, output="Operation completed", metadata={"duration": 1.5}
        )

        assert result.success
        assert result.output == "Operation completed"
        assert result.metadata["duration"] == 1.5
        assert str(result) == "Operation completed"

        # Error result
        error_result = ToolResult(success=False, output="", error="Operation failed")

        assert not error_result.success
        assert str(error_result) == "Error: Operation failed"
