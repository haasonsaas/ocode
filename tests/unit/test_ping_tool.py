"""Unit tests for PingTool."""

from unittest.mock import MagicMock, patch

import pytest

from ocode_python.tools.ping_tool import PingTool


class TestPingTool:
    """Test cases for PingTool."""

    @pytest.fixture
    def ping_tool(self):
        """Create a PingTool instance."""
        return PingTool()

    def test_tool_definition(self, ping_tool):
        """Test tool definition."""
        definition = ping_tool.definition
        assert definition.name == "ping"
        assert (
            definition.description == "Test network connectivity to a host using ping"
        )
        assert definition.category == "System Operations"
        assert len(definition.parameters) == 4

        # Check parameters
        param_names = [p.name for p in definition.parameters]
        assert "host" in param_names
        assert "count" in param_names
        assert "timeout" in param_names
        assert "interval" in param_names

    @pytest.mark.asyncio
    async def test_missing_host(self, ping_tool):
        """Test execution without host parameter."""
        result = await ping_tool.execute()
        assert not result.success
        assert "Host parameter is required" in result.error

    @pytest.mark.asyncio
    async def test_invalid_host_format(self, ping_tool):
        """Test with invalid host format."""
        # Test command injection attempts
        dangerous_hosts = [
            "google.com; rm -rf /",
            "localhost && echo hacked",
            "8.8.8.8 | cat /etc/passwd",
            "host$(whoami)",
            "host`id`",
            "host\necho test",
            'host"test"',
            "host'test'",
        ]

        for host in dangerous_hosts:
            result = await ping_tool.execute(host=host)
            assert not result.success
            assert "Invalid host format" in result.error

    @pytest.mark.asyncio
    async def test_valid_host_formats(self, ping_tool):
        """Test host validation with valid formats."""
        valid_hosts = [
            "localhost",
            "google.com",
            "8.8.8.8",
            "192.168.1.1",
            "test-server.example.com",
            "server_name",
            "::1",  # IPv6
            "[::1]",  # IPv6 with brackets
            "2001:db8::1",  # IPv6
        ]

        for host in valid_hosts:
            # Just test validation, not actual execution
            assert ping_tool._is_valid_host(host), f"Host {host} should be valid"

    @pytest.mark.asyncio
    async def test_parameter_validation(self, ping_tool):
        """Test parameter validation."""
        # Test invalid count
        result = await ping_tool.execute(host="localhost", count=0)
        assert not result.success
        assert "Count must be between 1 and 10" in result.error

        result = await ping_tool.execute(host="localhost", count=20)
        assert not result.success
        assert "Count must be between 1 and 10" in result.error

        # Test invalid timeout
        result = await ping_tool.execute(host="localhost", timeout=0)
        assert not result.success
        assert "Timeout must be between 1 and 30" in result.error

        result = await ping_tool.execute(host="localhost", timeout=60)
        assert not result.success
        assert "Timeout must be between 1 and 30" in result.error

        # Test invalid interval
        result = await ping_tool.execute(host="localhost", interval=0.1)
        assert not result.success
        assert "Interval must be between 0.2 and 10" in result.error

    @pytest.mark.asyncio
    async def test_successful_ping(self, ping_tool):
        """Test successful ping execution."""
        # Mock the subprocess execution
        mock_process = MagicMock()
        mock_process.returncode = 0

        async def mock_communicate():
            return (
                b"PING localhost (127.0.0.1): 56 data bytes\n"
                b"64 bytes from 127.0.0.1: icmp_seq=0 ttl=64 time=0.055 ms\n"
                b"\n--- localhost ping statistics ---\n"
                b"1 packets transmitted, 1 packets received, 0.0% packet loss\n"
                b"round-trip min/avg/max/stddev = 0.055/0.055/0.055/0.000 ms\n",
                b"",
            )

        mock_process.communicate = mock_communicate

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await ping_tool.execute(host="localhost", count=1)

            assert result.success
            assert "PING localhost" in result.output
            assert result.metadata is not None
            assert result.metadata["packets_transmitted"] == 1
            assert result.metadata["packets_received"] == 1
            assert result.metadata["packet_loss"] == 0.0

    @pytest.mark.asyncio
    async def test_failed_ping(self, ping_tool):
        """Test failed ping execution."""
        # Mock the subprocess execution with failure
        mock_process = MagicMock()
        mock_process.returncode = 1

        async def mock_communicate():
            return (
                b"PING unreachable.host (1.2.3.4): 56 data bytes\n"
                b"\n--- unreachable.host ping statistics ---\n"
                b"4 packets transmitted, 0 packets received, 100.0% packet loss\n",
                b"",
            )

        mock_process.communicate = mock_communicate

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await ping_tool.execute(host="unreachable.host", count=4)

            assert not result.success
            assert result.metadata is not None
            assert result.metadata["packets_transmitted"] == 4
            assert result.metadata["packets_received"] == 0
            assert result.metadata["packet_loss"] == 100.0

    def test_build_ping_command(self, ping_tool):
        """Test platform-specific command building."""
        # Test macOS command
        with patch("platform.system", return_value="Darwin"):
            cmd = ping_tool._build_ping_command("localhost", 4, 5, 1.0)
            assert cmd == ["ping", "-c", "4", "-W", "5000", "-i", "1.0", "localhost"]

        # Test Linux command
        with patch("platform.system", return_value="Linux"):
            cmd = ping_tool._build_ping_command("localhost", 4, 5, 1.0)
            assert cmd == ["ping", "-c", "4", "-W", "5", "-i", "1.0", "localhost"]

        # Test Windows command
        with patch("platform.system", return_value="Windows"):
            cmd = ping_tool._build_ping_command("localhost", 4, 5, 1.0)
            assert cmd == ["ping", "-n", "4", "-w", "5000", "localhost"]

    def test_parse_ping_output(self, ping_tool):
        """Test ping output parsing."""
        # Test typical Linux/macOS output
        output = """PING google.com (142.250.80.46): 56 data bytes
64 bytes from 142.250.80.46: icmp_seq=0 ttl=117 time=15.123 ms
64 bytes from 142.250.80.46: icmp_seq=1 ttl=117 time=14.456 ms
64 bytes from 142.250.80.46: icmp_seq=2 ttl=117 time=16.789 ms

--- google.com ping statistics ---
3 packets transmitted, 3 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 14.456/15.456/16.789/0.967 ms"""

        stats = ping_tool._parse_ping_output(output)
        assert stats["packets_transmitted"] == 3
        assert stats["packets_received"] == 3
        assert stats["packet_loss"] == 0.0
        assert stats["min_time"] == 14.456
        assert stats["avg_time"] == 15.456
        assert stats["max_time"] == 16.789
