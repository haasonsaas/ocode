"""
Unit tests for security and permission management.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ocode_python.utils.security import (
    OperationType,
    PermissionLevel,
    PermissionManager,
    PermissionRule,
    SecureShellExecutor,
)


@pytest.mark.unit
@pytest.mark.security
class TestPermissionManager:
    """Test PermissionManager functionality."""

    def test_init_default(self):
        """Test default initialization."""
        manager = PermissionManager()

        assert len(manager.rules) > 0
        assert len(manager.blocked_paths) > 0  # Default blocked paths are loaded

    def test_load_default_rules(self):
        """Test loading of default security rules."""
        manager = PermissionManager()

        # Should have rules for blocking dangerous operations
        write_rules = [
            r for r in manager.rules if r.operation == OperationType.FILE_WRITE
        ]
        assert len(write_rules) > 0

        exec_rules = [
            r for r in manager.rules if r.operation == OperationType.SHELL_EXEC
        ]
        assert len(exec_rules) > 0

    def test_add_rule(self):
        """Test adding custom rules."""
        manager = PermissionManager()
        initial_count = len(manager.rules)

        rule = PermissionRule(
            operation=OperationType.FILE_READ,
            pattern="/secret/*",
            permission=PermissionLevel.DENIED,
            description="Block secret files",
        )

        manager.add_rule(rule)

        assert len(manager.rules) == initial_count + 1
        assert rule in manager.rules

    def test_check_permission_file_read(self):
        """Test file read permission checking."""
        manager = PermissionManager()

        # Normal file should be readable
        permission = manager.check_permission(
            OperationType.FILE_READ, "/home/user/document.txt"
        )
        assert permission != PermissionLevel.DENIED

        # System file should have restrictions
        permission = manager.check_permission(OperationType.FILE_WRITE, "/etc/passwd")
        assert permission == PermissionLevel.DENIED

    def test_check_permission_shell_exec(self):
        """Test shell execution permission checking."""
        manager = PermissionManager()

        # Safe command should be allowed
        permission = manager.check_permission(OperationType.SHELL_EXEC, "ls -la")
        assert permission != PermissionLevel.DENIED

        # Dangerous command should be blocked
        permission = manager.check_permission(OperationType.SHELL_EXEC, "rm -rf /")
        assert permission == PermissionLevel.DENIED

        permission = manager.check_permission(OperationType.SHELL_EXEC, "sudo rm file")
        assert permission == PermissionLevel.DENIED

    def test_can_read_file(self, temp_dir: Path):
        """Test file read capability checking."""
        manager = PermissionManager()

        # Allow reading normal files
        test_file = temp_dir / "test.txt"
        assert manager.can_read_file(str(test_file))

        # Block reading system files
        assert not manager.can_write_file("/etc/passwd")

    def test_can_write_file(self, temp_dir: Path):
        """Test file write capability checking."""
        manager = PermissionManager()

        # Allow writing to user directories
        test_file = temp_dir / "output.txt"
        assert manager.can_write_file(str(test_file))

        # Block writing to system directories
        assert not manager.can_write_file("/etc/malicious.conf")
        assert not manager.can_write_file("/bin/malware")

    def test_can_execute_command(self):
        """Test command execution capability checking."""
        manager = PermissionManager()

        # Allow safe commands
        assert manager.can_execute_command("echo hello")
        assert manager.can_execute_command("python script.py")
        assert manager.can_execute_command("ls -la")

        # Block dangerous commands
        assert not manager.can_execute_command("rm -rf /")
        assert not manager.can_execute_command("sudo passwd")
        assert not manager.can_execute_command("dd if=/dev/zero of=/dev/sda")

    def test_sanitize_command(self):
        """Test command sanitization."""
        manager = PermissionManager()

        # Safe commands should pass through
        assert manager.sanitize_command("echo hello") == "echo hello"
        assert manager.sanitize_command("python script.py") is not None

        # Dangerous commands should be blocked
        assert manager.sanitize_command("rm -rf /") is None
        assert manager.sanitize_command("echo hello; rm file") is None
        assert manager.sanitize_command("echo hello > /etc/passwd") is None
        assert manager.sanitize_command("sudo ls") is None

    def test_get_safe_environment(self):
        """Test safe environment variable filtering."""
        manager = PermissionManager()

        with patch.dict(
            os.environ,
            {
                "PATH": "/usr/bin",
                "HOME": "/home/user",
                "SECRET_KEY": "supersecret",
                "PYTHONPATH": "/usr/lib/python",
                "MALICIOUS_VAR": "evil_value",
            },
        ):
            safe_env = manager.get_safe_environment()

            # Should include safe variables
            assert "PATH" in safe_env
            assert "HOME" in safe_env
            assert "PYTHONPATH" in safe_env

            # Should exclude unsafe variables
            assert "SECRET_KEY" not in safe_env
            assert "MALICIOUS_VAR" not in safe_env

    def test_validate_file_operation_read(self, temp_dir: Path):
        """Test file operation validation for reading."""
        manager = PermissionManager()

        # Create test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        # Should allow reading existing file
        allowed, reason = manager.validate_file_operation("read", str(test_file))
        assert allowed

        # Should block reading non-existent file
        allowed, reason = manager.validate_file_operation(
            "read", str(temp_dir / "nonexistent.txt")
        )
        assert not allowed
        assert "does not exist" in reason

    def test_validate_file_operation_write(self, temp_dir: Path):
        """Test file operation validation for writing."""
        manager = PermissionManager()

        # Should allow writing to valid location
        test_file = temp_dir / "output.txt"
        allowed, reason = manager.validate_file_operation("write", str(test_file))
        assert allowed

        # Should block writing to system directories
        allowed, reason = manager.validate_file_operation(
            "write", "/etc/malicious.conf"
        )
        assert not allowed

    def test_custom_validator(self):
        """Test custom validator functionality."""
        manager = PermissionManager()

        # Add custom validator that blocks files containing "secret"
        def block_secret_files(target: str) -> bool:
            return "secret" not in target.lower()

        manager.add_validator(OperationType.FILE_READ, block_secret_files)

        # Normal file should be allowed
        permission = manager.check_permission(
            OperationType.FILE_READ, "/home/user/normal.txt"
        )
        assert permission != PermissionLevel.DENIED

        # File with "secret" should be blocked
        permission = manager.check_permission(
            OperationType.FILE_READ, "/home/user/secret_file.txt"
        )
        assert permission == PermissionLevel.DENIED

    def test_create_sandbox_config(self, temp_dir: Path):
        """Test sandbox configuration creation."""
        manager = PermissionManager()

        config = manager.create_sandbox_config([str(temp_dir)])

        assert str(temp_dir) in config["allowed_paths"]
        assert len(config["blocked_paths"]) > 0
        assert "environment" in config
        assert config["network_access"] is False
        assert config["max_execution_time"] > 0

    def test_export_policy(self, temp_dir: Path):
        """Test policy export functionality."""
        manager = PermissionManager()

        export_file = temp_dir / "policy.json"
        manager.export_policy(export_file)

        assert export_file.exists()

        # Verify exported content
        import json

        with open(export_file) as f:
            policy = json.load(f)

        assert "rules" in policy
        assert "blocked_paths" in policy
        assert "allowed_paths" in policy
        assert len(policy["rules"]) > 0


@pytest.mark.unit
@pytest.mark.security
class TestSecureShellExecutor:
    """Test SecureShellExecutor functionality."""

    def test_init(self):
        """Test executor initialization."""
        manager = PermissionManager()
        executor = SecureShellExecutor(manager)

        assert executor.permission_manager is manager

    @pytest.mark.asyncio
    async def test_execute_safe_command(self):
        """Test executing safe command."""
        manager = PermissionManager()
        executor = SecureShellExecutor(manager)

        success, stdout, stderr = await executor.execute("echo hello")

        assert success
        assert "hello" in stdout
        assert stderr == ""

    @pytest.mark.asyncio
    async def test_execute_blocked_command(self):
        """Test executing blocked command."""
        manager = PermissionManager()
        executor = SecureShellExecutor(manager)

        success, stdout, stderr = await executor.execute("rm -rf /")

        assert not success
        assert stdout == ""
        assert "blocked" in stderr.lower()

    @pytest.mark.asyncio
    async def test_execute_with_working_dir(self, temp_dir: Path):
        """Test executing command with working directory."""
        import platform

        manager = PermissionManager()
        executor = SecureShellExecutor(manager)

        # Use platform-appropriate command to get current directory
        if platform.system() == "Windows":
            cmd = "cd"
        else:
            cmd = "pwd"

        success, stdout, stderr = await executor.execute(cmd, working_dir=str(temp_dir))

        assert success
        # Flexible path matching for cross-platform compatibility
        temp_str = str(temp_dir)
        temp_unix = temp_str.replace("\\", "/")
        temp_unix_c = temp_unix.replace("C:/", "/c/")

        # Check if any of the path formats are in the output
        # Normalize both the expected path and output for comparison
        stdout_normalized = stdout.replace("\\", "/").lower()
        temp_normalized = temp_str.replace("\\", "/").lower()

        path_found = any(
            [
                temp_str in stdout,
                temp_unix in stdout,
                temp_unix_c in stdout,
                # Normalized comparison
                temp_normalized in stdout_normalized,
                # Check for the actual directory structure patterns
                temp_dir.name.lower() in stdout.lower(),
                # Windows might use /c/ format in Git Bash
                "/c/" in stdout.lower() and "temp" in stdout.lower(),
            ]
        )

        assert (
            path_found
        ), f"Expected path not found in output. Temp dir: {temp_str}, Output: {stdout}"

    @pytest.mark.asyncio
    async def test_execute_with_invalid_working_dir(self):
        """Test executing command with invalid working directory."""
        manager = PermissionManager()
        executor = SecureShellExecutor(manager)

        success, stdout, stderr = await executor.execute(
            "echo hello", working_dir="/nonexistent/directory"
        )

        assert not success
        assert "access denied" in stderr.lower()

    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        """Test command execution timeout."""
        import platform

        manager = PermissionManager()
        executor = SecureShellExecutor(manager)

        # Use platform-appropriate sleep command
        if platform.system() == "Windows":
            # Windows timeout command (in seconds)
            cmd = "timeout /t 10 /nobreak"
        else:
            # Unix sleep command
            cmd = "sleep 10"

        success, stdout, stderr = await executor.execute(cmd, timeout=1)

        assert not success
        assert "timed out" in stderr.lower()


@pytest.mark.unit
@pytest.mark.security
class TestPermissionRule:
    """Test PermissionRule functionality."""

    def test_rule_creation(self):
        """Test rule creation."""
        rule = PermissionRule(
            operation=OperationType.FILE_WRITE,
            pattern="/tmp/*",  # nosec B108
            permission=PermissionLevel.RESTRICTED,
            description="Allow restricted writes to /tmp",  # nosec B108
        )

        assert rule.operation == OperationType.FILE_WRITE
        assert rule.pattern == "/tmp/*"  # nosec B108
        assert rule.permission == PermissionLevel.RESTRICTED

    def test_rule_matches(self):
        """Test rule pattern matching."""
        rule = PermissionRule(
            operation=OperationType.FILE_READ,
            pattern="/home/user/*",
            permission=PermissionLevel.FULL,
            description="Allow user files",
        )

        # Should match
        assert rule.matches("/home/user/document.txt")
        assert rule.matches("/home/user/subfolder/file.py")

        # Should not match
        assert not rule.matches("/home/other/document.txt")
        assert not rule.matches("/etc/passwd")

    def test_rule_glob_patterns(self):
        """Test various glob patterns."""
        # Wildcard pattern
        rule1 = PermissionRule(
            operation=OperationType.FILE_READ,
            pattern="*.py",
            permission=PermissionLevel.FULL,
            description="Python files",
        )

        assert rule1.matches("script.py")
        assert rule1.matches("main.py")
        assert not rule1.matches("readme.txt")

        # Directory pattern
        rule2 = PermissionRule(
            operation=OperationType.FILE_WRITE,
            pattern="/etc/*",
            permission=PermissionLevel.DENIED,
            description="Block /etc writes",
        )

        assert rule2.matches("/etc/passwd")
        assert rule2.matches("/etc/hosts")
        assert not rule2.matches("/home/user/file.txt")


@pytest.mark.unit
@pytest.mark.security
class TestPermissionLevels:
    """Test permission level enumeration."""

    def test_permission_levels(self):
        """Test permission level values."""
        assert PermissionLevel.DENIED.value == "denied"
        assert PermissionLevel.READ_ONLY.value == "read_only"
        assert PermissionLevel.RESTRICTED.value == "restricted"
        assert PermissionLevel.FULL.value == "full"

    def test_operation_types(self):
        """Test operation type values."""
        assert OperationType.FILE_READ.value == "file_read"
        assert OperationType.FILE_WRITE.value == "file_write"
        assert OperationType.SHELL_EXEC.value == "shell_exec"
        assert OperationType.GIT_OPERATION.value == "git_operation"
