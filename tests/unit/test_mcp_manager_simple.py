"""Simple unit tests for MCP manager."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ocode_python.mcp.manager import MCPServerInfo, MCPServerManager
from ocode_python.utils.config import ConfigManager


class TestMCPServerInfo:
    """Test MCPServerInfo dataclass."""

    def test_server_info_creation(self):
        """Test creating MCPServerInfo instance."""
        info = MCPServerInfo(
            name="test-server",
            command="python",
            args=["-m", "test"],
            env={"TEST": "value"},
            cwd="/tmp",  # nosec B108
            status="stopped",
        )

        assert info.name == "test-server"
        assert info.command == "python"
        assert info.args == ["-m", "test"]
        assert info.env == {"TEST": "value"}
        assert info.cwd == "/tmp"  # nosec B108
        assert info.status == "stopped"
        assert info.pid is None
        assert info.port is None
        assert info.error is None

    def test_server_info_with_runtime_data(self):
        """Test MCPServerInfo with runtime data."""
        info = MCPServerInfo(
            name="running-server",
            command="node",
            args=["server.js"],
            env={},
            cwd=None,
            status="running",
            pid=1234,
            port=8080,
        )

        assert info.name == "running-server"
        assert info.status == "running"
        assert info.pid == 1234
        assert info.port == 8080


class TestMCPServerManager:
    """Test MCPServerManager functionality."""

    @pytest.fixture
    def temp_config(self):
        """Create temporary config for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            yield config_dir

    @pytest.fixture
    def mock_config_manager(self, temp_config):
        """Create mock config manager."""
        config_manager = Mock(spec=ConfigManager)
        config_manager.get.return_value = {}
        return config_manager

    @pytest.fixture
    def manager(self, mock_config_manager):
        """Create MCPServerManager with mock config."""
        return MCPServerManager(config_manager=mock_config_manager)

    def test_manager_initialization(self, manager, mock_config_manager):
        """Test MCPServerManager initialization."""
        assert manager.config_manager == mock_config_manager
        assert isinstance(manager._processes, dict)
        assert isinstance(manager._server_info, dict)

    def test_load_server_configs_empty(self, manager, mock_config_manager):
        """Test loading empty server configs."""
        mock_config_manager.get.return_value = {}
        manager._load_server_configs()
        assert len(manager._server_info) == 0

    def test_load_server_configs_with_servers(self, manager, mock_config_manager):
        """Test loading server configs with servers."""
        servers_config = {
            "test-server": {
                "command": "python",
                "args": ["-m", "server"],
                "env": {"PORT": "8080"},
                "cwd": "/app",
            },
            "another-server": {"command": "node", "args": ["index.js"]},
        }

        mock_config_manager.get.return_value = servers_config
        manager._load_server_configs()

        assert len(manager._server_info) == 2
        assert "test-server" in manager._server_info
        assert "another-server" in manager._server_info

        test_server = manager._server_info["test-server"]
        assert test_server.name == "test-server"
        assert test_server.command == "python"
        assert test_server.args == ["-m", "server"]
        assert test_server.env == {"PORT": "8080"}
        assert test_server.cwd == "/app"
        assert test_server.status == "stopped"

    def test_list_servers_empty(self, manager):
        """Test listing servers when none configured."""
        servers = manager.list_servers()
        assert servers == []

    def test_list_servers_with_configs(self, manager, mock_config_manager):
        """Test listing servers with configurations."""
        servers_config = {
            "server1": {"command": "python", "args": []},
            "server2": {"command": "node", "args": []},
        }

        mock_config_manager.get.return_value = servers_config
        manager._load_server_configs()

        servers = manager.list_servers()
        assert len(servers) == 2
        assert all(server.status == "stopped" for server in servers)

    @pytest.mark.asyncio
    async def test_start_server_not_found(self, manager):
        """Test starting non-existent server."""
        with pytest.raises(ValueError, match="Server 'unknown' not found"):
            await manager.start_server("unknown")

    @pytest.mark.asyncio
    async def test_start_server_config_available(self, manager, mock_config_manager):
        """Test starting server with available config."""
        servers_config = {
            "test-server": {
                "command": "echo",
                "args": ["hello"],
                "env": {},
                "cwd": None,
            }
        }

        mock_config_manager.get.return_value = servers_config
        manager._load_server_configs()

        # Mock subprocess to simulate successful start
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process is running
        mock_process.pid = 1234

        with patch("subprocess.Popen", return_value=mock_process):
            with patch("asyncio.sleep"):  # Speed up test
                info = await manager.start_server("test-server")

                assert info.name == "test-server"
                assert info.status == "running"
                assert info.pid == 1234
                assert "test-server" in manager._processes

    @pytest.mark.asyncio
    async def test_stop_server_not_found(self, manager):
        """Test stopping non-existent server."""
        with pytest.raises(ValueError, match="Server 'unknown' not found"):
            await manager.stop_server("unknown")

    @pytest.mark.asyncio
    async def test_stop_server_not_running(self, manager, mock_config_manager):
        """Test stopping server that's not running."""
        servers_config = {"test-server": {"command": "echo", "args": []}}

        mock_config_manager.get.return_value = servers_config
        manager._load_server_configs()

        # The actual implementation doesn't raise an error, it just ensures the server is stopped  # noqa: E501
        info = await manager.stop_server("test-server")
        assert info.name == "test-server"
        assert info.status == "stopped"

    def test_manager_with_real_config_manager(self):
        """Test manager with real ConfigManager."""
        # This tests the integration without mocking
        real_config = ConfigManager()
        manager = MCPServerManager(config_manager=real_config)

        assert manager.config_manager == real_config
        assert isinstance(manager._processes, dict)
        assert isinstance(manager._server_info, dict)

        # Should work without errors even with empty config
        servers = manager.list_servers()
        assert isinstance(servers, list)
