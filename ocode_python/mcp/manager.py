"""
MCP Server Manager for OCode.

Manages the lifecycle of MCP servers, including starting, stopping, and listing.
"""

import asyncio
import json
import os
import subprocess  # nosec
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

from ..utils.config import ConfigManager


@dataclass
class MCPServerInfo:
    """Information about an MCP server instance."""

    name: str
    command: str
    args: List[str]
    env: Dict[str, str]
    cwd: Optional[str]
    status: str  # "running", "stopped", "error"
    pid: Optional[int] = None
    port: Optional[int] = None
    error: Optional[str] = None


class MCPServerManager:
    """
    Manages MCP servers lifecycle.

    Servers are configured in the settings file under the "mcp_servers" key.
    Each server configuration includes:
    - command: The command to run the server
    - args: Arguments to pass to the command
    - env: Environment variables
    - cwd: Working directory
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """Initialize MCP server manager."""
        self.config_manager = config_manager or ConfigManager()
        self._processes: Dict[str, subprocess.Popen] = {}
        self._server_info: Dict[str, MCPServerInfo] = {}
        self._load_server_configs()

    def _load_server_configs(self) -> None:
        """Load server configurations from settings."""
        mcp_servers = self.config_manager.get("mcp_servers", {})

        for name, config in mcp_servers.items():
            if not isinstance(config, dict):
                continue

            server_info = MCPServerInfo(
                name=name,
                command=config.get("command", ""),
                args=config.get("args", []),
                env=config.get("env", {}),
                cwd=config.get("cwd"),
                status="stopped",
            )

            self._server_info[name] = server_info

    def list_servers(self) -> List[MCPServerInfo]:
        """List all configured MCP servers with their status."""
        # Update status for all servers
        for name, info in self._server_info.items():
            if name in self._processes:
                process = self._processes[name]
                if process.poll() is None:
                    info.status = "running"
                    info.pid = process.pid
                else:
                    info.status = "stopped"
                    info.pid = None
                    del self._processes[name]
            else:
                # Check if process is running from a previous session
                if info.pid:
                    if PSUTIL_AVAILABLE:
                        try:
                            ps_process = psutil.Process(info.pid)
                            if ps_process.is_running():
                                info.status = "running"
                            else:
                                info.status = "stopped"
                                info.pid = None
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            info.status = "stopped"
                            info.pid = None
                    else:
                        # Fallback: just mark as unknown status without psutil
                        info.status = "unknown"
                else:
                    info.status = "stopped"

        return list(self._server_info.values())

    async def start_server(self, name: str) -> MCPServerInfo:
        """Start an MCP server by name."""
        if name not in self._server_info:
            # Try to reload configs in case it was just added
            self._load_server_configs()

            if name not in self._server_info:
                raise ValueError(f"Server '{name}' not found in configuration")

        info = self._server_info[name]

        # Check if already running
        if name in self._processes and self._processes[name].poll() is None:
            info.status = "running"
            return info

        try:
            # Prepare environment
            env = dict(os.environ)
            env.update(info.env)

            # Start the process
            cmd = [info.command] + info.args

            process = subprocess.Popen(  # nosec
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=info.cwd,
                text=True,
            )

            # Wait a moment to see if it starts successfully
            await asyncio.sleep(0.5)

            if process.poll() is None:
                # Process is running
                self._processes[name] = process
                info.status = "running"
                info.pid = process.pid
                info.error = None

                # Save PID to config for persistence
                self._save_server_state(name, info)
            else:
                # Process failed to start
                stderr = process.stderr.read() if process.stderr else ""
                info.status = "error"
                info.error = f"Failed to start: {stderr}"

        except Exception as e:
            info.status = "error"
            info.error = str(e)

        return info

    async def stop_server(self, name: str) -> MCPServerInfo:
        """Stop an MCP server by name."""
        if name not in self._server_info:
            raise ValueError(f"Server '{name}' not found")

        info = self._server_info[name]

        # Try to stop the process
        if name in self._processes:
            process = self._processes[name]
            if process.poll() is None:
                try:
                    # Send terminate signal
                    process.terminate()

                    # Wait for graceful shutdown
                    try:
                        await asyncio.wait_for(
                            asyncio.create_subprocess_shell(f"wait {process.pid}"),
                            timeout=5.0,
                        )
                    except asyncio.TimeoutError:
                        # Force kill if needed
                        process.kill()

                    info.status = "stopped"
                    info.pid = None
                    del self._processes[name]

                except Exception as e:
                    info.status = "error"
                    info.error = f"Failed to stop: {str(e)}"
            else:
                # Process already stopped
                info.status = "stopped"
                info.pid = None
                if name in self._processes:
                    del self._processes[name]

        elif info.pid:
            # Try to stop by PID (from previous session)
            if PSUTIL_AVAILABLE:
                try:
                    process = psutil.Process(info.pid)
                    process.terminate()

                    # Wait for termination
                    try:
                        process.wait(timeout=5)
                    except psutil.TimeoutExpired:
                        process.kill()

                    info.status = "stopped"
                    info.pid = None

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    info.status = "stopped"
                    info.pid = None
            else:
                # Fallback: try OS kill command
                try:
                    import os
                    import signal

                    os.kill(info.pid, signal.SIGTERM)
                    info.status = "stopped"
                    info.pid = None
                except (OSError, ProcessLookupError):
                    info.status = "stopped"
                    info.pid = None

        else:
            info.status = "stopped"

        # Save state
        self._save_server_state(name, info)

        return info

    async def restart_server(self, name: str) -> MCPServerInfo:
        """Restart an MCP server."""
        await self.stop_server(name)
        await asyncio.sleep(0.5)  # Brief pause before restart
        return await self.start_server(name)

    def add_server(
        self,
        name: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> bool:
        """Add a new MCP server configuration."""
        # Create server config
        server_config = {
            "command": command,
            "args": args or [],
            "env": env or {},
            "cwd": cwd,
        }

        # Get current MCP servers config
        mcp_servers = self.config_manager.get("mcp_servers", {})
        mcp_servers[name] = server_config

        # Save to config
        success = self.config_manager.set("mcp_servers", mcp_servers)

        if success:
            # Reload configs
            self._load_server_configs()

        return success

    def remove_server(self, name: str) -> bool:
        """Remove an MCP server configuration."""
        # Stop server if running
        if name in self._server_info:
            asyncio.run(self.stop_server(name))

        # Get current MCP servers config
        mcp_servers = self.config_manager.get("mcp_servers", {})

        if name in mcp_servers:
            del mcp_servers[name]

            # Save to config
            success = self.config_manager.set("mcp_servers", mcp_servers)

            if success:
                # Remove from internal state
                if name in self._server_info:
                    del self._server_info[name]
                if name in self._processes:
                    del self._processes[name]

            return success

        return False

    def _save_server_state(self, name: str, info: MCPServerInfo) -> None:
        """Save server state to config for persistence."""
        # Get state file path
        state_file = Path.home() / ".ocode" / "mcp_state.json"

        # Load existing state
        state = {}
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    state = json.load(f)
            except Exception:  # nosec
                state = {}

        # Update state
        state[name] = {"pid": info.pid, "status": info.status, "port": info.port}

        # Save state
        try:
            state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception:  # nosec
            pass

    def _load_server_state(self) -> None:
        """Load server state from persistence."""
        state_file = Path.home() / ".ocode" / "mcp_state.json"

        if not state_file.exists():
            return

        try:
            with open(state_file, "r") as f:
                state = json.load(f)

            for name, server_state in state.items():
                if name in self._server_info:
                    self._server_info[name].pid = server_state.get("pid")
                    self._server_info[name].port = server_state.get("port")
        except Exception:  # nosec
            pass

    async def cleanup(self) -> None:
        """Stop all running servers."""
        for name in list(self._processes.keys()):
            await self.stop_server(name)


# Example server configurations that could be added:
EXAMPLE_MCP_SERVERS = {
    "filesystem": {
        "command": "npx",
        "args": [
            "-y",
            "@modelcontextprotocol/server-filesystem",
            tempfile.gettempdir(),
        ],
        "env": {},
        "cwd": None,
    },
    "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "<your-token>"},
        "cwd": None,
    },
    "postgres": {
        "command": "npx",
        "args": [
            "-y",
            "@modelcontextprotocol/server-postgres",
            "postgresql://localhost/mydb",
        ],
        "env": {},
        "cwd": None,
    },
}
