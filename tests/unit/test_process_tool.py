"""Unit tests for ProcessMonitorTool."""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

import pytest

from ocode_python.tools.process_tool import ProcessMonitorTool


@pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
class TestProcessMonitorTool:
    """Test ProcessMonitorTool functionality."""

    @pytest.fixture
    def tool(self):
        """Create ProcessMonitorTool instance."""
        return ProcessMonitorTool()

    @pytest.fixture
    def mock_process(self):
        """Create a mock process object."""
        process = Mock(spec=psutil.Process)
        process.pid = 1234
        process.name.return_value = "test_process"
        process.username.return_value = "test_user"
        process.cpu_percent.return_value = 25.5
        process.memory_percent.return_value = 10.2
        process.status.return_value = "running"
        process.create_time.return_value = 1609459200.0  # 2021-01-01 00:00:00
        process.exe.return_value = "/usr/bin/test_process"
        process.cmdline.return_value = ["/usr/bin/test_process", "--arg1", "value1"]
        process.ppid.return_value = 1
        process.num_threads.return_value = 4

        # Memory info
        mem_info = Mock()
        mem_info.rss = 104857600  # 100 MB
        mem_info.vms = 209715200  # 200 MB
        process.memory_info.return_value = mem_info

        # Open files
        open_file = Mock()
        open_file.path = "/tmp/test.txt"  # nosec B108
        process.open_files.return_value = [open_file]

        # Connections
        conn = Mock()
        conn.laddr = Mock(ip="127.0.0.1", port=8080)
        conn.raddr = Mock(ip="192.168.1.1", port=80)
        conn.status = "ESTABLISHED"
        process.connections.return_value = [conn]

        return process

    def test_tool_definition(self, tool):
        """Test tool definition."""
        assert tool.definition.name == "ps"
        assert tool.definition.category == "System Operations"
        assert len(tool.definition.parameters) == 7

    @pytest.mark.asyncio
    async def test_list_action(self, tool):
        """Test list action."""
        # Create additional mock processes
        process2 = Mock(spec=psutil.Process)
        process2.pid = 5678
        process2.name.return_value = "another_process"
        process2.username.return_value = "root"
        process2.cpu_percent.return_value = 50.0
        process2.memory_percent.return_value = 5.5
        process2.status.return_value = "sleeping"

        with patch("psutil.process_iter") as mock_iter:
            # Create process1 with info
            process1 = Mock()
            process1.info = {
                "pid": 1234,
                "name": "test_process",
                "cpu_percent": 25.5,
                "memory_percent": 10.2,
                "status": "running",
                "create_time": 1609459200.0,
                "username": "test_user",
            }
            process1.cpu_percent.return_value = (
                25.5  # Return float that supports round()
            )

            # Add info to process2
            process2.info = {
                "pid": 5678,
                "name": "another_process",
                "cpu_percent": 50.0,
                "memory_percent": 5.5,
                "status": "sleeping",
                "create_time": 1609459200.0,
                "username": "root",
            }
            process2.cpu_percent.return_value = (
                50.0  # Return float that supports round()
            )

            mock_iter.return_value = [process1, process2]

            result = await tool.execute(action="list", limit=10)

            assert result.success
            assert result.metadata["count"] == 2
            assert "test_process" in result.output
            assert "another_process" in result.output
            assert "1234" in result.output
            assert "5678" in result.output
            assert "CPU%" in result.output
            assert "MEM%" in result.output

    @pytest.mark.asyncio
    async def test_list_action_sorted(self, tool):
        """Test list action with sorting."""
        # Create process with higher CPU usage
        high_cpu_process = Mock(spec=psutil.Process)
        high_cpu_process.pid = 9999
        high_cpu_process.name.return_value = "cpu_intensive"
        high_cpu_process.username.return_value = "user"
        high_cpu_process.cpu_percent.return_value = 90.0
        high_cpu_process.memory_percent.return_value = 2.0
        high_cpu_process.status.return_value = "running"

        with patch("psutil.process_iter") as mock_iter:
            # Create low CPU process
            low_cpu = Mock()
            low_cpu.info = {
                "pid": 1234,
                "name": "test_process",
                "cpu_percent": 25.5,
                "memory_percent": 10.2,
                "status": "running",
                "create_time": 1609459200.0,
                "username": "test_user",
            }
            low_cpu.cpu_percent.return_value = (
                25.5  # Return float that supports round()
            )

            # Add info to high_cpu_process
            high_cpu_process.info = {
                "pid": 9999,
                "name": "cpu_intensive",
                "cpu_percent": 90.0,
                "memory_percent": 2.0,
                "status": "running",
                "create_time": 1609459200.0,
                "username": "user",
            }
            high_cpu_process.cpu_percent.return_value = (
                90.0  # Return float that supports round()
            )

            mock_iter.return_value = [low_cpu, high_cpu_process]

            result = await tool.execute(action="list", sort_by="cpu", limit=10)

            assert result.success
            # Should be sorted by CPU, high_cpu_process first
            lines = result.output.split("\n")
            cpu_intensive_index = next(
                i for i, line in enumerate(lines) if "cpu_intensive" in line
            )
            test_process_index = next(
                i for i, line in enumerate(lines) if "test_process" in line
            )
            assert cpu_intensive_index < test_process_index

    @pytest.mark.asyncio
    async def test_list_action_with_limit(self, tool):
        """Test list action with limit."""
        # Create many mock processes
        processes = []
        for i in range(20):
            process = Mock()
            process.info = {
                "pid": 1000 + i,
                "name": f"process_{i}",
                "cpu_percent": i * 2.0,
                "memory_percent": i * 0.5,
                "status": "running",
                "create_time": 1609459200.0,
                "username": "user",
            }
            process.cpu_percent.return_value = float(
                i * 2.0
            )  # Return float that supports round()
            processes.append(process)

        with patch("psutil.process_iter") as mock_iter:
            mock_iter.return_value = processes

            result = await tool.execute(action="list", limit=5)

            assert result.success
            # Should only show 5 processes
            assert result.metadata["count"] == 5

    @pytest.mark.asyncio
    async def test_find_action(self, tool):
        """Test find action."""
        # Create processes with different names
        python_process = Mock(spec=psutil.Process)
        python_process.pid = 2000
        python_process.name.return_value = "python3"
        python_process.exe.return_value = "/usr/bin/python3"
        python_process.cmdline.return_value = ["python3", "script.py"]

        chrome_process = Mock(spec=psutil.Process)
        chrome_process.pid = 3000
        chrome_process.name.return_value = "chrome"
        chrome_process.exe.return_value = (
            "/Applications/Chrome.app/Contents/MacOS/chrome"
        )
        chrome_process.cmdline.return_value = ["chrome", "--profile-directory=Default"]

        with patch("psutil.process_iter") as mock_iter:
            # Create test process with info
            test_proc = Mock()
            test_proc.info = {
                "pid": 1234,
                "name": "test_process",
                "cpu_percent": 25.5,
                "memory_percent": 10.2,
                "status": "running",
                "cmdline": ["test_process", "--arg"],
                "username": "test_user",
            }
            test_proc.cpu_percent.return_value = (
                25.5  # Return float that supports round()
            )

            # Add info to python and chrome processes
            python_process.info = {
                "pid": 2000,
                "name": "python3",
                "cpu_percent": 15.0,
                "memory_percent": 5.0,
                "status": "running",
                "cmdline": ["python3", "script.py"],
                "username": "user",
            }
            python_process.cpu_percent.return_value = (
                15.0  # Return float that supports round()
            )

            chrome_process.info = {
                "pid": 3000,
                "name": "chrome",
                "cpu_percent": 30.0,
                "memory_percent": 20.0,
                "status": "running",
                "cmdline": ["chrome", "--profile-directory=Default"],
                "username": "user",
            }
            chrome_process.cpu_percent.return_value = (
                30.0  # Return float that supports round()
            )

            mock_iter.return_value = [test_proc, python_process, chrome_process]

            result = await tool.execute(action="find", name="python")

            assert result.success
            # Check metadata instead of output text
            assert result.metadata["found"] == 1
            assert "python3" in result.output
            assert "2000" in result.output
            assert "chrome" not in result.output

    @pytest.mark.asyncio
    async def test_find_action_case_insensitive(self, tool):
        """Test find action with case-insensitive search."""
        process = Mock()
        process.info = {
            "pid": 1111,
            "name": "MyApp",
            "cpu_percent": 5.0,
            "memory_percent": 2.0,
            "status": "running",
            "cmdline": ["MyApp", "--daemon"],
            "username": "user",
        }
        process.cpu_percent.return_value = 5.0  # Return float that supports round()

        with patch("psutil.process_iter") as mock_iter:
            mock_iter.return_value = [process]

            result = await tool.execute(action="find", name="myapp")

            assert result.success
            # Check metadata instead of output text
            assert result.metadata["found"] == 1
            assert "MyApp" in result.output

    @pytest.mark.asyncio
    async def test_find_action_cmdline_search(self, tool):
        """Test find action searching in command line."""
        process = Mock()
        process.info = {
            "pid": 4444,
            "name": "java",
            "cpu_percent": 35.0,
            "memory_percent": 15.0,
            "status": "running",
            "cmdline": ["java", "-jar", "myapp.jar", "--port=8080"],
            "username": "user",
        }
        process.cpu_percent.return_value = 35.0  # Return float that supports round()

        with patch("psutil.process_iter") as mock_iter:
            mock_iter.return_value = [process]

            result = await tool.execute(action="find", name="myapp.jar")

            assert result.success
            # Check metadata instead of output text
            assert result.metadata["found"] == 1
            assert "java" in result.output
            assert "myapp.jar" in result.output

    @pytest.mark.asyncio
    async def test_info_action(self, tool):
        """Test info action."""
        with patch("psutil.Process") as mock_process_class:
            # Create a mock process for info action
            process = Mock()
            process.pid = 1234
            process.name.return_value = "test_process"
            process.username.return_value = "test_user"
            process.cpu_percent.return_value = (
                25.5  # Return float that supports round()
            )
            process.memory_percent.return_value = (
                10.2  # Return float that supports round()
            )
            process.status.return_value = "running"
            process.create_time.return_value = 1609459200.0
            process.exe.return_value = "/usr/bin/test_process"
            process.cmdline.return_value = ["/usr/bin/test_process", "--arg1", "value1"]
            process.ppid.return_value = 1
            process.num_threads.return_value = 4
            process.children.return_value = []  # Return empty list of children
            process.cwd.return_value = "/home/test"
            process.nice.return_value = 0

            # Memory info
            mem_info = Mock()
            mem_info.rss = 104857600  # 100 MB
            mem_info.vms = 209715200  # 200 MB
            process.memory_info.return_value = mem_info

            # Open files
            open_file = Mock()
            open_file.path = "/tmp/test.txt"  # nosec B108
            process.open_files.return_value = [open_file]

            # Connections
            conn = Mock()
            conn.laddr = Mock(ip="127.0.0.1", port=8080)
            conn.raddr = Mock(ip="192.168.1.1", port=80)
            conn.status = "ESTABLISHED"
            process.connections.return_value = [conn]

            # Support context manager protocol (oneshot)
            oneshot_mock = Mock()
            oneshot_mock.__enter__ = Mock(return_value=oneshot_mock)
            oneshot_mock.__exit__ = Mock(return_value=None)
            process.oneshot.return_value = oneshot_mock

            mock_process_class.return_value = process

            result = await tool.execute(action="info", pid=1234)

            assert result.success
            assert "Process Information for PID 1234" in result.output
            # Check formatted info table output
            assert "Name:" in result.output and "test_process" in result.output
            assert "Status:" in result.output and "running" in result.output
            assert "User:" in result.output and "test_user" in result.output
            assert "CPU %:" in result.output and "25.5%" in result.output
            assert "Memory %:" in result.output and "10.2%" in result.output
            assert "Memory RSS:" in result.output and "100" in result.output
            assert "Memory VMS:" in result.output and "200" in result.output
            assert "Threads:" in result.output and "4" in result.output
            assert "Parent PID:" in result.output and "1" in result.output
            assert (
                "Command:" in result.output
                and "/usr/bin/test_process --arg1 value1" in result.output
            )

    @pytest.mark.asyncio
    async def test_info_action_process_not_found(self, tool):
        """Test info action with non-existent process."""
        with patch("psutil.Process") as mock_process_class:
            mock_process_class.side_effect = psutil.NoSuchProcess(9999)

            result = await tool.execute(action="info", pid=9999)

            assert not result.success
            assert "No process found with PID 9999" in result.error

    @pytest.mark.asyncio
    async def test_info_action_access_denied(self, tool):
        """Test info action with access denied error."""
        with patch("psutil.Process") as mock_process_class:
            process = Mock()
            process.pid = 1
            process.name.side_effect = psutil.AccessDenied(1)
            # Support context manager protocol (oneshot)
            oneshot_mock = Mock()
            oneshot_mock.__enter__ = Mock(side_effect=psutil.AccessDenied(1))
            oneshot_mock.__exit__ = Mock(return_value=None)
            process.oneshot.return_value = oneshot_mock
            mock_process_class.return_value = process

            result = await tool.execute(action="info", pid=1)

            assert not result.success
            assert "Access denied to process 1" in result.error

    @pytest.mark.asyncio
    async def test_check_action_running(self, tool):
        """Test check action with running process."""
        # Create a mock process with info attribute
        mock_proc = Mock()
        mock_proc.info = {"pid": 1234, "name": "test_process"}

        with patch("psutil.process_iter") as mock_iter:
            mock_iter.return_value = [mock_proc]

            result = await tool.execute(action="check", name="test_process")

            assert result.success
            # Check action returns JSON format
            assert result.metadata["running"] is True
            assert result.metadata["count"] == 1

    @pytest.mark.asyncio
    async def test_check_action_not_running(self, tool):
        """Test check action with non-existent process."""
        with patch("psutil.process_iter") as mock_iter:
            mock_iter.return_value = []  # No processes

            result = await tool.execute(action="check", name="nonexistent")

            assert result.success
            # Check action returns JSON format
            assert result.metadata["running"] is False
            assert result.metadata["count"] == 0

    @pytest.mark.asyncio
    async def test_invalid_action(self, tool):
        """Test invalid action."""
        result = await tool.execute(action="invalid")

        assert not result.success
        assert (
            "Invalid action" in result.error
            and "list, find, info, check" in result.error
        )

    @pytest.mark.asyncio
    async def test_missing_pid_for_info(self, tool):
        """Test info action without PID."""
        result = await tool.execute(action="info")

        assert not result.success
        assert "PID parameter is required for 'info' action" in result.error

    @pytest.mark.asyncio
    async def test_missing_name_for_check(self, tool):
        """Test check action without name."""
        result = await tool.execute(action="check")

        assert not result.success
        assert "Name parameter is required for 'check' action" in result.error

    @pytest.mark.asyncio
    async def test_invalid_sort_by(self, tool):
        """Test list action with invalid sort_by."""
        with patch("psutil.process_iter") as mock_iter:
            mock_iter.return_value = []  # Empty list

            result = await tool.execute(action="list", sort_by="invalid")

            # The tool doesn't fail on invalid sort_by, it defaults to "cpu"
            assert result.success
            assert result.metadata["sort_by"] == "cpu"

    @pytest.mark.asyncio
    async def test_handle_process_gone(self, tool):
        """Test handling of process that disappears during iteration."""
        # Create mock processes with info attribute
        process1 = Mock()
        process1.info = {
            "pid": 1111,
            "name": "good_process",
            "cpu_percent": 10.0,
            "memory_percent": 5.0,
            "username": "user",
            "status": "running",
            "create_time": 1609459200.0,
        }
        process1.cpu_percent.return_value = 10.0

        process2 = Mock()
        process2.info = {"pid": 2222, "name": "bad_process"}
        # Simulate process disappearing during cpu_percent call
        process2.cpu_percent.side_effect = psutil.NoSuchProcess(2222)

        with patch("psutil.process_iter") as mock_iter:
            mock_iter.return_value = [process1, process2]

            result = await tool.execute(action="list")

            assert result.success
            # Should handle the error gracefully and still show process1
            assert "good_process" in result.output
            assert "1111" in result.output
            # process2 should be skipped
            assert "2222" not in result.output
