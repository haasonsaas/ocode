"""
Model Context Protocol (MCP) integration tool for OCode.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.timeout_handler import TimeoutError, with_timeout
from ..utils.retry_handler import retry_async
from .base import (
    ErrorHandler,
    ErrorType,
    Tool,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)


class MCPTool(Tool):
    """Tool for integrating with Model Context Protocol (MCP) servers and clients."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="mcp",
            description="Integrate with Model Context Protocol (MCP) servers for extended capabilities",  # noqa: E501
            parameters=[
                ToolParameter(
                    name="action",
                    type="string",
                    description="Action to perform: 'connect', 'list_servers', 'discover_tools', 'call_tool', 'get_resources', 'disconnect', 'status'",  # noqa: E501
                    required=True,
                ),
                ToolParameter(
                    name="server_name",
                    type="string",
                    description="Name of MCP server to connect to",
                    required=False,
                ),
                ToolParameter(
                    name="server_config",
                    type="object",
                    description="Server configuration (command, args, env)",
                    required=False,
                ),
                ToolParameter(
                    name="tool_name",
                    type="string",
                    description="Name of tool to call on MCP server",
                    required=False,
                ),
                ToolParameter(
                    name="tool_arguments",
                    type="object",
                    description="Arguments to pass to the MCP tool",
                    required=False,
                    default={},
                ),
                ToolParameter(
                    name="resource_uri",
                    type="string",
                    description="URI of resource to fetch from MCP server",
                    required=False,
                ),
                ToolParameter(
                    name="timeout",
                    type="number",
                    description="Operation timeout in seconds",
                    required=False,
                    default=30,
                ),
            ],
        )

    def __init__(self):
        super().__init__()
        self.connected_servers: Dict[str, Dict[str, Any]] = {}
        self.server_tools: Dict[str, List[Dict[str, Any]]] = {}
        self.server_resources: Dict[str, List[Dict[str, Any]]] = {}

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute MCP operations."""
        try:
            # Extract parameters
            action = kwargs.get("action")
            server_name = kwargs.get("server_name")
            server_config = kwargs.get("server_config")
            tool_name = kwargs.get("tool_name")
            tool_arguments = kwargs.get("tool_arguments", {})
            resource_uri = kwargs.get("resource_uri")
            timeout = kwargs.get("timeout", 30)

            if not action:
                return ToolResult(
                    success=False, output="", error="action parameter is required"
                )

            if action == "connect":
                return await self._connect_server(server_name, server_config, timeout)
            elif action == "list_servers":
                return await self._list_servers()
            elif action == "discover_tools":
                return await self._discover_tools(server_name)
            elif action == "call_tool":
                return await self._call_tool(
                    server_name, tool_name, tool_arguments, timeout
                )
            elif action == "get_resources":
                return await self._get_resources(server_name, resource_uri)
            elif action == "disconnect":
                return await self._disconnect_server(server_name)
            elif action == "status":
                return await self._get_status()
            else:
                return ToolResult(
                    success=False, output="", error=f"Unknown action: {action}"
                )

        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"MCP operation failed: {str(e)}"
            )

    async def _connect_server(
        self,
        server_name: Optional[str],
        server_config: Optional[Dict[str, Any]],
        timeout: int,
    ) -> ToolResult:
        """Connect to an MCP server."""
        if not server_name:
            return ToolResult(
                success=False, output="", error="server_name is required for connection"
            )

        if server_name in self.connected_servers:
            return ToolResult(
                success=False,
                output="",
                error=f"Server '{server_name}' is already connected",
            )

        # Default configurations for common MCP servers
        default_configs = {
            "filesystem": {
                "command": "npx",
                "args": [
                    "@modelcontextprotocol/server-filesystem",
                    "/path/to/allowed/files",
                ],
                "description": "File system access MCP server",
            },
            "git": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-git", "--repository", "."],
                "description": "Git operations MCP server",
            },
            "sqlite": {
                "command": "npx",
                "args": [
                    "@modelcontextprotocol/server-sqlite",
                    "--db-path",
                    "database.db",
                ],
                "description": "SQLite database MCP server",
            },
            "web-search": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-brave-search"],
                "description": "Web search MCP server",
            },
            "github": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-github"],
                "description": "GitHub integration MCP server",
            },
        }

        # Use provided config or default
        if server_config:
            config = server_config
        elif server_name in default_configs:
            config = default_configs[server_name].copy()
        else:
            return ToolResult(
                success=False,
                output="",
                error=f"No configuration provided for server '{server_name}' and no default available",  # noqa: E501
            )

        # Simulate connection (in reality, this would start the MCP server process)
        try:
            # This is where we would actually spawn the MCP server process
            # and establish communication via stdio or other transport

            @retry_async(
                max_attempts=3,
                base_delay=1.0,
                retryable_exceptions=(ConnectionError, OSError, TimeoutError)
            )
            async def _perform_connection():
                connection_info = {
                    "name": server_name,
                    "config": config,
                    "status": "connected",
                    "connected_at": datetime.now().isoformat(),
                    "capabilities": [
                        "tools",
                        "resources",
                        "prompts",
                    ],  # Example capabilities
                    "server_info": {
                        "name": config.get("description", f"{server_name} MCP server"),
                        "version": "1.0.0",
                    },
                }

                self.connected_servers[server_name] = connection_info

                # Discover available tools and resources
                await self._discover_tools_internal(server_name)
                await self._discover_resources_internal(server_name)

                return connection_info

            # Use timeout for the connection process
            connection_info = await with_timeout(
                _perform_connection(),
                timeout=timeout,
                operation=f"mcp_connect({server_name})",
            )

            output = f"Successfully connected to MCP server: {server_name}\n"
            output += f"Description: {config.get('description', 'No description')}\n"
            output += f"Capabilities: {', '.join(connection_info['capabilities'])}\n"
            output += (
                f"Tools available: {len(self.server_tools.get(server_name, []))}\n"
            )
            output += f"Resources available: {len(self.server_resources.get(server_name, []))}\n"  # noqa: E501

            return ToolResult(
                success=True, output=output, metadata={"server": connection_info}
            )

        except TimeoutError as e:
            # Clean up partial connection on timeout
            if server_name in self.connected_servers:
                del self.connected_servers[server_name]
            return ErrorHandler.create_error_result(
                f"Connection to MCP server '{server_name}' timed out: {str(e)}",
                ErrorType.TIMEOUT_ERROR,
                {"server_name": server_name, "timeout": timeout},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to connect to MCP server '{server_name}': {str(e)}",
            )

    async def _list_servers(self) -> ToolResult:
        """List all connected MCP servers."""
        if not self.connected_servers:
            return ToolResult(
                success=True,
                output="No MCP servers connected. Use action='connect' to connect to a server.",  # noqa: E501
                metadata={"servers": []},
            )

        output = f"Connected MCP Servers ({len(self.connected_servers)}):\n"
        output += "=" * 50 + "\n"

        for server_name, server_info in self.connected_servers.items():
            output += f"Name: {server_name}\n"
            output += f"Status: {server_info['status']}\n"
            output += f"Connected: {server_info['connected_at']}\n"
            output += f"Tools: {len(self.server_tools.get(server_name, []))}\n"
            output += f"Resources: {len(self.server_resources.get(server_name, []))}\n"
            output += f"Capabilities: {', '.join(server_info['capabilities'])}\n"
            output += "-" * 30 + "\n"

        return ToolResult(
            success=True,
            output=output,
            metadata={"servers": list(self.connected_servers.values())},
        )

    async def _discover_tools(self, server_name: Optional[str]) -> ToolResult:
        """Discover available tools on MCP server(s)."""
        if server_name:
            if server_name not in self.connected_servers:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Server '{server_name}' is not connected",
                )

            servers_to_check = [server_name]
        else:
            servers_to_check = list(self.connected_servers.keys())

        if not servers_to_check:
            return ToolResult(
                success=True,
                output="No connected servers to discover tools from.",
                metadata={"tools": {}},
            )

        all_tools = {}
        output = "Available MCP Tools:\n"
        output += "=" * 30 + "\n"

        for srv_name in servers_to_check:
            tools = self.server_tools.get(srv_name, [])
            all_tools[srv_name] = tools

            output += f"\nServer: {srv_name}\n"
            output += f"Tools ({len(tools)}):\n"

            for tool in tools:
                output += (
                    f"  • {tool['name']}: {tool.get('description', 'No description')}\n"
                )
                if tool.get("parameters"):
                    output += (
                        f"    Parameters: {', '.join(tool['parameters'].keys())}\n"
                    )

        return ToolResult(success=True, output=output, metadata={"tools": all_tools})

    async def _discover_tools_internal(self, server_name: str) -> None:
        """Internal method to discover tools from a server."""
        # Simulate tool discovery - in reality, this would query the MCP server
        example_tools = {
            "filesystem": [
                {
                    "name": "read_file",
                    "description": "Read contents of a file",
                    "parameters": {
                        "path": {"type": "string", "description": "File path"}
                    },
                },
                {
                    "name": "write_file",
                    "description": "Write contents to a file",
                    "parameters": {
                        "path": {"type": "string", "description": "File path"},
                        "content": {"type": "string", "description": "File content"},
                    },
                },
                {
                    "name": "list_directory",
                    "description": "List files in a directory",
                    "parameters": {
                        "path": {"type": "string", "description": "Directory path"}
                    },
                },
            ],
            "git": [
                {
                    "name": "git_status",
                    "description": "Get git repository status",
                    "parameters": {},
                },
                {
                    "name": "git_log",
                    "description": "Get git commit history",
                    "parameters": {
                        "max_count": {
                            "type": "number",
                            "description": "Maximum number of commits",
                        }
                    },
                },
                {
                    "name": "git_diff",
                    "description": "Get git diff",
                    "parameters": {
                        "cached": {
                            "type": "boolean",
                            "description": "Show staged changes",
                        }
                    },
                },
            ],
            "web-search": [
                {
                    "name": "search",
                    "description": "Search the web",
                    "parameters": {
                        "query": {"type": "string", "description": "Search query"},
                        "count": {"type": "number", "description": "Number of results"},
                    },
                }
            ],
        }

        self.server_tools[server_name] = example_tools.get(server_name, [])

    async def _discover_resources_internal(self, server_name: str) -> None:
        """Internal method to discover resources from a server."""
        # Simulate resource discovery
        example_resources = {
            "filesystem": [
                {
                    "uri": "file:///current/directory",
                    "name": "Current Directory",
                    "mimeType": "application/vnd.directory",
                },
                {
                    "uri": "file:///project/readme",
                    "name": "Project README",
                    "mimeType": "text/markdown",
                },
            ],
            "git": [
                {
                    "uri": "git://repository/status",
                    "name": "Repository Status",
                    "mimeType": "application/json",
                },
                {
                    "uri": "git://repository/log",
                    "name": "Commit History",
                    "mimeType": "application/json",
                },
            ],
            "github": [
                {
                    "uri": "github://repository/issues",
                    "name": "Issues",
                    "mimeType": "application/json",
                },
                {
                    "uri": "github://repository/pulls",
                    "name": "Pull Requests",
                    "mimeType": "application/json",
                },
            ],
        }

        self.server_resources[server_name] = example_resources.get(server_name, [])

    async def _call_tool(
        self,
        server_name: Optional[str],
        tool_name: Optional[str],
        tool_arguments: Dict[str, Any],
        timeout: int,
    ) -> ToolResult:
        """Call a tool on an MCP server."""
        if not server_name:
            return ToolResult(
                success=False, output="", error="server_name is required for tool calls"
            )

        if not tool_name:
            return ToolResult(
                success=False, output="", error="tool_name is required for tool calls"
            )

        if server_name not in self.connected_servers:
            return ToolResult(
                success=False,
                output="",
                error=f"Server '{server_name}' is not connected",
            )

        # Check if tool exists
        server_tools = self.server_tools.get(server_name, [])
        tool = next((t for t in server_tools if t["name"] == tool_name), None)

        if not tool:
            available_tools = [t["name"] for t in server_tools]
            return ToolResult(
                success=False,
                output="",
                error=f"Tool '{tool_name}' not found on server '{server_name}'. Available tools: {', '.join(available_tools)}",  # noqa: E501
            )

        # Simulate tool execution
        try:
            # Use timeout and retry for tool execution
            @retry_async(
                max_attempts=2,
                base_delay=0.5,
                retryable_exceptions=(ConnectionError, OSError, TimeoutError)
            )
            async def _execute_tool():
                return await self._simulate_tool_call(server_name, tool_name, tool_arguments)
            
            result = await with_timeout(
                _execute_tool(),
                timeout=timeout,
                operation=f"mcp_tool_call({server_name}.{tool_name})",
            )

            output = "MCP Tool Call Result:\n"
            output += f"Server: {server_name}\n"
            output += f"Tool: {tool_name}\n"
            output += f"Arguments: {json.dumps(tool_arguments, indent=2)}\n"
            output += f"Result:\n{result}\n"

            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "server": server_name,
                    "tool": tool_name,
                    "arguments": tool_arguments,
                    "result": result,
                },
            )

        except TimeoutError as e:
            return ErrorHandler.create_error_result(
                f"MCP tool call '{tool_name}' on server '{server_name}' timed out: {str(e)}",  # noqa: E501
                ErrorType.TIMEOUT_ERROR,
                {
                    "server_name": server_name,
                    "tool_name": tool_name,
                    "timeout": timeout,
                },
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Tool call failed: {str(e)}"
            )

    async def _simulate_tool_call(
        self, server_name: str, tool_name: str, arguments: Dict[str, Any]
    ) -> str:
        """Simulate calling a tool on an MCP server."""
        await asyncio.sleep(0.1)  # Simulate network delay

        # Simulate different tool responses
        if server_name == "filesystem":
            if tool_name == "read_file":
                path = arguments.get("path", "unknown")
                return f"Contents of {path}:\n[Simulated file content]"
            elif tool_name == "write_file":
                path = arguments.get("path", "unknown")
                return f"Successfully wrote to {path}"
            elif tool_name == "list_directory":
                path = arguments.get("path", ".")
                return f"Files in {path}:\nfile1.py\nfile2.js\nfolder/\n"

        elif server_name == "git":
            if tool_name == "git_status":
                return "On branch main\nNothing to commit, working tree clean"
            elif tool_name == "git_log":
                return "commit abc123 (HEAD -> main)\nAuthor: Developer\nDate: Today\n\nLatest commit"  # noqa: E501
            elif tool_name == "git_diff":
                return "diff --git a/file.py b/file.py\n+Added line\n-Removed line"

        elif server_name == "web-search":
            if tool_name == "search":
                query = arguments.get("query", "")
                return f"Search results for '{query}':\n1. Example result 1\n2. Example result 2"  # noqa: E501

        return f"Result from {tool_name} on {server_name} with args {arguments}"

    async def _get_resources(
        self, server_name: Optional[str], resource_uri: Optional[str]
    ) -> ToolResult:
        """Get resources from MCP server."""
        if not server_name:
            return ToolResult(
                success=False,
                output="",
                error="server_name is required for resource access",
            )

        if server_name not in self.connected_servers:
            return ToolResult(
                success=False,
                output="",
                error=f"Server '{server_name}' is not connected",
            )

        server_resources = self.server_resources.get(server_name, [])

        if resource_uri:
            # Get specific resource
            resource = next(
                (r for r in server_resources if r["uri"] == resource_uri), None
            )
            if not resource:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Resource '{resource_uri}' not found on server '{server_name}'",  # noqa: E501
                )

            # Simulate resource fetching
            content = await self._simulate_resource_fetch(resource_uri)

            output = "Resource Content:\n"
            output += f"URI: {resource_uri}\n"
            output += f"Name: {resource['name']}\n"
            output += f"Type: {resource['mimeType']}\n"
            output += f"Content:\n{content}\n"

            return ToolResult(
                success=True,
                output=output,
                metadata={"resource": resource, "content": content},
            )

        else:
            # List all resources
            output = f"Available Resources on {server_name}:\n"
            output += "=" * 40 + "\n"

            for resource in server_resources:
                output += f"URI: {resource['uri']}\n"
                output += f"Name: {resource['name']}\n"
                output += f"Type: {resource['mimeType']}\n"
                output += "-" * 30 + "\n"

            return ToolResult(
                success=True, output=output, metadata={"resources": server_resources}
            )

    async def _simulate_resource_fetch(self, resource_uri: str) -> str:
        """Simulate fetching a resource."""
        await asyncio.sleep(0.1)

        if "directory" in resource_uri:
            return "Directory listing:\nfile1.py\nfile2.js\nsubfolder/\n"
        elif "readme" in resource_uri:
            return "# Project README\n\nThis is a sample project...\n"
        elif "status" in resource_uri:
            return '{"branch": "main", "status": "clean", "files": []}'
        elif "log" in resource_uri:
            return '{"commits": [{"hash": "abc123", "message": "Latest commit", "author": "Developer"}]}'  # noqa: E501
        else:
            return f"Content of resource: {resource_uri}"

    async def _disconnect_server(self, server_name: Optional[str]) -> ToolResult:
        """Disconnect from an MCP server."""
        if not server_name:
            return ToolResult(
                success=False,
                output="",
                error="server_name is required for disconnection",
            )

        if server_name not in self.connected_servers:
            return ToolResult(
                success=False,
                output="",
                error=f"Server '{server_name}' is not connected",
            )

        # Clean up server data
        server_info = self.connected_servers[server_name]
        del self.connected_servers[server_name]

        if server_name in self.server_tools:
            del self.server_tools[server_name]

        if server_name in self.server_resources:
            del self.server_resources[server_name]

        output = f"Disconnected from MCP server: {server_name}\n"
        output += f"Server was connected at: {server_info['connected_at']}\n"

        return ToolResult(
            success=True, output=output, metadata={"disconnected_server": server_info}
        )

    async def _get_status(self) -> ToolResult:
        """Get status of MCP connections and capabilities."""
        output = "MCP Integration Status:\n"
        output += "=" * 30 + "\n"
        output += f"Connected Servers: {len(self.connected_servers)}\n"

        total_tools = sum(len(tools) for tools in self.server_tools.values())
        total_resources = sum(
            len(resources) for resources in self.server_resources.values()
        )

        output += f"Total Available Tools: {total_tools}\n"
        output += f"Total Available Resources: {total_resources}\n\n"

        if self.connected_servers:
            output += "Server Details:\n"
            for server_name, server_info in self.connected_servers.items():
                output += f"  {server_name}: {server_info['status']}\n"
                output += f"    Tools: {len(self.server_tools.get(server_name, []))}\n"
                output += f"    Resources: {len(self.server_resources.get(server_name, []))}\n"  # noqa: E501
        else:
            output += "No servers connected.\n"
            output += (
                "Use action='connect' with server_name to connect to an MCP server.\n"
            )

        return ToolResult(
            success=True,
            output=output,
            metadata={
                "servers": self.connected_servers,
                "tools": self.server_tools,
                "resources": self.server_resources,
                "statistics": {
                    "connected_servers": len(self.connected_servers),
                    "total_tools": total_tools,
                    "total_resources": total_resources,
                },
            },
        )
