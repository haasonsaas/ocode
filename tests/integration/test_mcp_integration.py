"""
Integration tests for MCP protocol.
"""

import json

import pytest

from ocode_python.mcp.protocol import (
    MCPProtocol,
    MCPServer,
)
from ocode_python.mcp.server import OCodeMCPServer


@pytest.mark.integration
@pytest.mark.mcp
class TestMCPProtocolIntegration:
    """Test MCP protocol integration."""

    @pytest.mark.asyncio
    async def test_initialize_handshake(self):
        """Test MCP initialization handshake."""
        protocol = MCPProtocol("test-server", "1.0.0")

        # Initialize request
        init_params = {
            "protocolVersion": "0.1.0",
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
            "capabilities": {},
        }

        result = await protocol._handle_initialize(init_params)

        assert result["protocolVersion"] == "0.1.0"
        assert "capabilities" in result
        assert "serverInfo" in result
        assert result["serverInfo"]["name"] == "test-server"

    @pytest.mark.asyncio
    async def test_full_message_flow(self):
        """Test complete message request/response flow."""
        server = MCPServer("test-server")

        # Create initialize request
        request = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "initialize",
            "params": {
                "protocolVersion": "0.1.0",
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }

        response_str = await server.handle_message(json.dumps(request))
        assert response_str is not None

        response = json.loads(response_str)
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "1"
        assert "result" in response

    @pytest.mark.asyncio
    async def test_tools_list_and_call(self):
        """Test tools listing and calling."""
        server = MCPServer("test-server")

        # Add a test tool
        from ocode_python.mcp.protocol import MCPTool

        test_tool = MCPTool(
            name="echo",
            description="Echo input text",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        )
        server.register_tool(test_tool)

        # List tools
        list_request = {
            "jsonrpc": "2.0",
            "id": "2",
            "method": "tools/list",
            "params": {},
        }

        response_str = await server.handle_message(json.dumps(list_request))
        response = json.loads(response_str)

        assert response["result"]["tools"]
        assert len(response["result"]["tools"]) == 1
        assert response["result"]["tools"][0]["name"] == "echo"

        # Call tool
        call_request = {
            "jsonrpc": "2.0",
            "id": "3",
            "method": "tools/call",
            "params": {"name": "echo", "arguments": {"text": "Hello, World!"}},
        }

        response_str = await server.handle_message(json.dumps(call_request))
        response = json.loads(response_str)

        assert "result" in response
        assert "content" in response["result"]

    @pytest.mark.asyncio
    async def test_resources_operations(self, tmp_path):
        """Test resource operations."""
        server = MCPServer("test-server")

        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content")

        # Add a test resource
        from ocode_python.mcp.protocol import MCPResource

        test_resource = MCPResource(
            uri=f"file://{test_file}",
            name="Test File",
            description="A test file",
            mime_type="text/plain",
        )
        server.register_resource(test_resource)

        # List resources
        list_request = {
            "jsonrpc": "2.0",
            "id": "4",
            "method": "resources/list",
            "params": {},
        }

        response_str = await server.handle_message(json.dumps(list_request))
        response = json.loads(response_str)

        assert "result" in response
        assert "resources" in response["result"]
        assert len(response["result"]["resources"]) == 1

        # Read resource
        read_request = {
            "jsonrpc": "2.0",
            "id": "5",
            "method": "resources/read",
            "params": {"uri": f"file://{test_file}"},
        }

        response_str = await server.handle_message(json.dumps(read_request))
        response = json.loads(response_str)

        assert "result" in response
        assert "contents" in response["result"]
        assert len(response["result"]["contents"]) == 1
        assert response["result"]["contents"][0]["text"] == "Test content"

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test MCP error handling."""
        server = MCPServer("test-server")

        # Invalid JSON
        response_str = await server.handle_message("invalid json")
        response = json.loads(response_str)

        assert "error" in response
        assert response["error"]["code"] == -32700  # Parse error

        # Unknown method
        unknown_request = {
            "jsonrpc": "2.0",
            "id": "6",
            "method": "unknown/method",
            "params": {},
        }

        response_str = await server.handle_message(json.dumps(unknown_request))
        response = json.loads(response_str)

        assert "error" in response
        assert response["error"]["code"] == -32601  # Method not found

    @pytest.mark.asyncio
    async def test_batch_requests(self):
        """Test batch request handling."""
        server = MCPServer("test-server")

        # Batch request
        batch_request = [
            {"jsonrpc": "2.0", "id": "1", "method": "resources/list", "params": {}},
            {"jsonrpc": "2.0", "id": "2", "method": "tools/list", "params": {}},
        ]

        response_str = await server.handle_message(json.dumps(batch_request))
        responses = json.loads(response_str)

        assert isinstance(responses, list)
        assert len(responses) == 2
        assert all("result" in resp for resp in responses)


@pytest.mark.integration
@pytest.mark.mcp
class TestOCodeMCPServerIntegration:
    """Test OCode MCP server integration."""

    @pytest.mark.asyncio
    async def test_ocode_server_initialization(self, mock_project_dir):
        """Test OCode MCP server initialization."""
        server = OCodeMCPServer(mock_project_dir)

        # Should have registered resources
        assert len(server.resources) > 0

        # Should have registered tools
        assert len(server.tools) > 0

        # Should have registered prompts
        assert len(server.prompts) > 0

        # Test initialization
        init_params = {
            "protocolVersion": "0.1.0",
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
        }

        result = await server._handle_initialize(init_params)

        assert "capabilities" in result
        assert "resources" in result["capabilities"]
        assert "tools" in result["capabilities"]
        assert "prompts" in result["capabilities"]

    @pytest.mark.asyncio
    async def test_ocode_project_resources(self, mock_project_dir):
        """Test OCode project resource access."""
        server = OCodeMCPServer(mock_project_dir)

        # List resources - should include project files
        resources_result = await server._handle_list_resources({})

        resources = resources_result["resources"]
        assert len(resources) > 0

        # Should have Python files
        python_resources = [r for r in resources if r["name"].endswith(".py")]
        assert len(python_resources) > 0

        # Should have special OCode resources
        ocode_resources = [r for r in resources if r["uri"].startswith("ocode://")]
        assert len(ocode_resources) > 0

    @pytest.mark.asyncio
    async def test_ocode_file_resource_reading(self, mock_project_dir):
        """Test reading actual project files through MCP."""
        server = OCodeMCPServer(mock_project_dir)

        # Read main.py file
        main_py_path = mock_project_dir / "main.py"
        file_uri = f"file://{main_py_path.absolute()}"

        result = await server._read_file_resource(file_uri)

        assert "contents" in result
        assert len(result["contents"]) == 1
        assert result["contents"][0]["uri"] == file_uri
        assert "def main" in result["contents"][0]["text"]

    @pytest.mark.asyncio
    async def test_ocode_special_resources(self, mock_project_dir):
        """Test OCode special resources."""
        server = OCodeMCPServer(mock_project_dir)

        # Test project structure resource
        structure_result = await server._read_ocode_resource(
            "ocode://project/structure"
        )

        assert "contents" in structure_result
        content = structure_result["contents"][0]
        assert content["mimeType"] == "application/json"

        # Parse and verify structure
        import json

        structure = json.loads(content["text"])
        assert "name" in structure
        assert "type" in structure

    @pytest.mark.asyncio
    async def test_ocode_tool_execution(self, mock_project_dir):
        """Test executing OCode tools through MCP."""
        server = OCodeMCPServer(mock_project_dir)

        # Execute file_read tool
        test_file = mock_project_dir / "main.py"

        result = await server._handle_call_tool(
            {"name": "file_read", "arguments": {"path": str(test_file)}}
        )

        assert "content" in result
        assert not result.get("isError", True)
        assert len(result["content"]) > 0
        assert "def main" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_ocode_prompt_generation(self, mock_project_dir):
        """Test OCode prompt generation."""
        server = OCodeMCPServer(mock_project_dir)

        # Get code review prompt
        result = await server._handle_get_prompt(
            {
                "name": "code_review",
                "arguments": {"file_path": "main.py", "focus": "performance"},
            }
        )

        assert "description" in result
        assert "messages" in result
        assert len(result["messages"]) > 0

        message = result["messages"][0]
        assert message["role"] == "user"
        assert "main.py" in message["content"]["text"]
        assert "performance" in message["content"]["text"]

    @pytest.mark.asyncio
    async def test_ocode_git_integration(self, mock_git_repo):
        """Test OCode git integration through MCP."""
        server = OCodeMCPServer(mock_git_repo)

        # Read git status resource
        git_result = await server._read_ocode_resource("ocode://git/status")

        assert "contents" in git_result
        content = git_result["contents"][0]

        import json

        git_info = json.loads(content["text"])

        assert "branch" in git_info
        assert "commit" in git_info

    @pytest.mark.asyncio
    async def test_error_handling_in_ocode_server(self, mock_project_dir):
        """Test error handling in OCode MCP server."""
        server = OCodeMCPServer(mock_project_dir)

        # Try to read non-existent file
        try:
            await server._read_file_resource("file:///nonexistent/file.txt")
            assert False, "Should have raised an error"
        except ValueError as e:
            assert "not found" in str(e).lower()

        # Try to call non-existent tool
        result = await server._handle_call_tool(
            {"name": "nonexistent_tool", "arguments": {}}
        )

        assert result.get("isError", False)
        assert "content" in result

    @pytest.mark.asyncio
    async def test_full_mcp_workflow(self, mock_project_dir):
        """Test complete MCP workflow."""
        server = OCodeMCPServer(mock_project_dir)

        # 1. Initialize
        init_result = await server._handle_initialize(
            {
                "protocolVersion": "0.1.0",
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            }
        )
        assert "capabilities" in init_result

        # 2. List resources
        resources_result = await server._handle_list_resources({})
        assert len(resources_result["resources"]) > 0

        # 3. List tools
        tools_result = await server._handle_list_tools({})
        assert len(tools_result["tools"]) > 0

        # 4. List prompts
        prompts_result = await server._handle_list_prompts({})
        assert len(prompts_result["prompts"]) > 0

        # 5. Read a resource
        file_uri = f"file://{mock_project_dir / 'main.py'}"
        read_result = await server._read_file_resource(file_uri)
        assert "contents" in read_result

        # 6. Execute a tool
        tool_result = await server._handle_call_tool(
            {"name": "file_list", "arguments": {"path": str(mock_project_dir)}}
        )
        assert not tool_result.get("isError", True)

        # 7. Get a prompt
        prompt_result = await server._handle_get_prompt(
            {"name": "explain_code", "arguments": {"file_path": "main.py"}}
        )
        assert "messages" in prompt_result
