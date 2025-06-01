"""
Enhanced Bash/Shell command execution tool with improved process management.
"""

import asyncio
import io
import os
import platform
import shlex
import shutil
import signal
import subprocess  # nosec B404
import tempfile
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Dict, List, Optional

import pexpect

from ..utils import command_sanitizer, path_validator
from .base import Tool, ToolDefinition, ToolParameter, ToolResult


class ProcessManager:
    """Manages process lifecycle with proper cleanup and resource management."""

    def __init__(self):
        self.active_processes = set()
        self._cleanup_lock = asyncio.Lock()

    async def register_process(self, process):
        """Register a process for tracking."""
        async with self._cleanup_lock:
            self.active_processes.add(process)

    async def unregister_process(self, process):
        """Unregister a process from tracking."""
        async with self._cleanup_lock:
            self.active_processes.discard(process)

    async def cleanup_all(self):
        """Cleanup all active processes."""
        async with self._cleanup_lock:
            for process in list(self.active_processes):
                await self._terminate_process(process)
            self.active_processes.clear()

    async def _terminate_process(self, process):
        """Terminate a single process with escalation."""
        if process.returncode is not None:
            return  # Already terminated

        try:
            # Try graceful termination first
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                # Escalate to SIGKILL
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    # Process is really stuck, try OS-level kill
                    if platform.system() == "Windows" and process.pid:
                        # Windows-specific process termination
                        with suppress(OSError, subprocess.SubprocessError):
                            subprocess.run(  # nosec B603 B607
                                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                                check=False,
                                capture_output=True,
                            )
                    elif hasattr(os, "killpg") and process.pid:
                        # Unix-specific process group kill
                        with suppress(OSError, ProcessLookupError):
                            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            # Process already dead
            pass


# Global process manager instance
_process_manager = ProcessManager()


class BashTool(Tool):
    """Enhanced Bash/Shell command execution tool with robust process management."""

    def __init__(self):
        super().__init__()
        self.process_manager = _process_manager

    @property
    def definition(self) -> ToolDefinition:
        """Define the bash tool specification.

        Returns:
            ToolDefinition with parameters for executing shell commands including
            command, working directory, environment variables, timeout, and
            interactive mode options.
        """
        return ToolDefinition(
            name="bash",
            description="Execute shell commands with advanced features and safety controls",  # noqa: E501
            category="System Operations",  # noqa: E501
            parameters=[
                ToolParameter(
                    name="command",
                    type="string",
                    description="Shell command to execute",
                    required=True,
                ),
                ToolParameter(
                    name="working_dir",
                    type="string",
                    description="Working directory for command execution",
                    required=False,
                    default=".",
                ),
                ToolParameter(
                    name="timeout",
                    type="number",
                    description="Command timeout in seconds (0 = no timeout)",
                    required=False,
                    default=30,
                ),
                ToolParameter(
                    name="capture_output",
                    type="boolean",
                    description="Capture stdout and stderr",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="shell",
                    type="string",
                    description="Shell to use (bash, sh, zsh, fish)",
                    required=False,
                    default="bash",
                ),
                ToolParameter(
                    name="env_vars",
                    type="object",
                    description="Additional environment variables",
                    required=False,
                    default={},
                ),
                ToolParameter(
                    name="input_data",
                    type="string",
                    description="Input data to pipe to the command",
                    required=False,
                ),
                ToolParameter(
                    name="interactive",
                    type="boolean",
                    description="Run in interactive mode (for commands requiring input)",  # noqa: E501
                    required=False,  # noqa: E501
                    default=False,
                ),
                ToolParameter(
                    name="safe_mode",
                    type="boolean",
                    description="Enable safety checks (prevent dangerous commands)",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="show_command",
                    type="boolean",
                    description="Show the command being executed",
                    required=False,
                    default=True,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute shell command with enhanced features."""
        # Extract parameters
        command = kwargs.get("command")
        if not command:
            return ToolResult(
                success=False,
                output="",
                error="Command parameter is required",
            )
        working_dir = kwargs.get("working_dir", ".")
        timeout = kwargs.get("timeout", 30)
        capture_output = kwargs.get("capture_output", True)
        shell = kwargs.get("shell", "bash")
        env_vars = kwargs.get("env_vars", {})
        input_data = kwargs.get("input_data")
        interactive = kwargs.get("interactive", False)
        safe_mode = kwargs.get("safe_mode", True)
        show_command = kwargs.get("show_command", True)

        try:
            # Validate working directory using centralized validator
            is_valid, error_msg, work_dir = path_validator.validate_path(
                working_dir, check_exists=True
            )
            if not is_valid:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Working directory validation failed: {error_msg}",
                )

            if work_dir and not work_dir.is_dir():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Working directory is not a directory: {working_dir}",
                )

            # Safety checks using enhanced sanitizer
            if safe_mode:
                sanitize_result = command_sanitizer.sanitize_command(
                    str(command), strict_mode=True
                )
                is_safe: bool = sanitize_result[0]
                sanitized_cmd: str = sanitize_result[1]
                sanitize_error: Optional[str] = sanitize_result[2]
                if not is_safe:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Command blocked for safety: {sanitize_error}",
                    )
                # Use the sanitized command
                if sanitized_cmd:
                    command = sanitized_cmd

            # Prepare environment with enhanced sanitization
            env = os.environ.copy()
            if env_vars:
                # Use the enhanced sanitizer for environment variables
                safe_env_vars = command_sanitizer.sanitize_environment(env_vars)
                env.update(safe_env_vars)

            # Prepare shell command
            shell_cmd = self._prepare_shell_command(str(command), shell)

            output_lines = []
            if show_command:
                output_lines.append(f"$ {command}")
                output_lines.append("")

            # Execute command
            if interactive:
                result = await self._execute_interactive(
                    shell_cmd, work_dir or Path("."), env, timeout, input_data
                )
            else:
                result = await self._execute_standard(
                    shell_cmd,
                    work_dir or Path("."),
                    env,
                    timeout,
                    capture_output,
                    input_data,
                )

            # Format output
            if result["success"]:
                if result["stdout"]:
                    output_lines.append(result["stdout"])

                if result["stderr"] and capture_output:
                    output_lines.append("STDERR:")
                    output_lines.append(result["stderr"])

                output = "\n".join(output_lines).rstrip()

                return ToolResult(
                    success=True,
                    output=output,
                    metadata={
                        "command": command,
                        "working_dir": str(work_dir),
                        "return_code": result["return_code"],
                        "execution_time": result.get("execution_time", 0),
                        "shell": shell,
                    },
                )
            else:
                error_msg = result["stderr"] or "Command execution failed"
                stdout = result.get("stdout", "")

                # Combine stdout and error for better context
                if stdout:
                    output_lines.append(stdout)

                return ToolResult(
                    success=False,
                    output="\n".join(output_lines).rstrip() if output_lines else "",
                    error=error_msg,
                    metadata={
                        "command": command,
                        "return_code": result["return_code"],
                        "execution_time": result.get("execution_time", 0),
                    },
                )

        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Command execution failed: {str(e)}"
            )

    def _prepare_shell_command(self, command: str, shell: str) -> List[str]:
        """Prepare shell command for execution with proper sanitization."""
        # Windows-specific handling
        if platform.system() == "Windows":
            # On Windows, use cmd.exe or PowerShell
            if shell in ["powershell", "pwsh"]:
                # Use PowerShell if requested and available
                powershell_path = shutil.which("pwsh") or shutil.which("powershell")
                if powershell_path:
                    return [powershell_path, "-Command", command]

            # Default to cmd.exe on Windows
            cmd_path = shutil.which("cmd") or "cmd.exe"
            # Don't add extra quotes - let the subprocess module handle it
            return [cmd_path, "/c", command]

        # Unix-like systems
        shell_map = {
            "bash": "bash",
            "sh": "sh",
            "zsh": "zsh",
            "fish": "fish",
        }

        # Validate shell parameter
        if shell not in shell_map:
            shell = "bash"  # Default to bash

        shell_name = shell_map[shell]

        # Use shutil.which to find the shell executable
        shell_path = shutil.which(shell_name)

        if not shell_path:
            # Fallback shells in order of preference
            fallback_shells = ["bash", "sh", "zsh", "fish"]
            for fallback in fallback_shells:
                shell_path = shutil.which(fallback)
                if shell_path:
                    break
            else:
                # Last resort: use 'sh' command
                shell_path = "sh"

        # Use exec form to prevent shell injection
        return [shell_path, "-c", command]

    @asynccontextmanager
    async def _managed_process(
        self,
        shell_cmd: List[str],
        work_dir: Path,
        env: Dict[str, str],
        capture_output: bool,
        input_data: Optional[str],
    ):
        """Enhanced context manager for proper process cleanup."""
        process = None
        try:
            # Create process with proper settings
            kwargs: Dict[str, Any] = {
                "cwd": str(work_dir),
                "env": env,
            }

            # Set up process group for better cleanup on Unix
            if platform.system() != "Windows" and hasattr(os, "setsid"):
                kwargs["start_new_session"] = True  # More portable than preexec_fn

            if capture_output:
                kwargs["stdout"] = asyncio.subprocess.PIPE
                kwargs["stderr"] = asyncio.subprocess.PIPE
                kwargs["stdin"] = asyncio.subprocess.PIPE if input_data else None

            process = await asyncio.create_subprocess_exec(*shell_cmd, **kwargs)

            # Register process for tracking
            await self.process_manager.register_process(process)

            yield process

        finally:
            if process:
                # Unregister process
                await self.process_manager.unregister_process(process)

                # Ensure proper cleanup
                if process.returncode is None:
                    try:
                        # Try graceful termination
                        process.terminate()
                        try:
                            await asyncio.wait_for(process.wait(), timeout=5.0)
                        except asyncio.TimeoutError:
                            # Force kill
                            process.kill()
                            try:
                                await asyncio.wait_for(process.wait(), timeout=2.0)
                            except asyncio.TimeoutError:
                                # Try OS-level process group kill
                                if hasattr(os, "killpg") and process.pid:
                                    try:
                                        os.killpg(
                                            os.getpgid(process.pid), signal.SIGKILL
                                        )
                                    except (OSError, ProcessLookupError):
                                        pass
                    except (ProcessLookupError, OSError):
                        # Process already terminated
                        pass

                # Ensure stdin is closed (stdout/stderr are read-only)
                if process.stdin and not process.stdin.is_closing():
                    process.stdin.close()

    async def _execute_standard(
        self,
        shell_cmd: List[str],
        work_dir: Path,
        env: Dict[str, str],
        timeout: int,
        capture_output: bool,
        input_data: Optional[str],
    ) -> Dict[str, Any]:
        """Execute command in standard mode with enhanced error handling."""
        start_time = time.time()

        try:
            async with self._managed_process(
                shell_cmd, work_dir, env, capture_output, input_data
            ) as process:
                if capture_output:
                    try:
                        # Prepare input
                        input_bytes = None
                        if input_data:
                            input_bytes = input_data.encode("utf-8", errors="replace")

                        # Execute with timeout
                        if timeout > 0:
                            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                                process.communicate(input=input_bytes), timeout=timeout
                            )
                        else:
                            stdout_bytes, stderr_bytes = await process.communicate(
                                input=input_bytes
                            )

                        # Decode output
                        stdout = (
                            stdout_bytes.decode("utf-8", errors="replace")
                            if stdout_bytes
                            else ""
                        )
                        stderr = (
                            stderr_bytes.decode("utf-8", errors="replace")
                            if stderr_bytes
                            else ""
                        )

                        return_code = process.returncode

                    except asyncio.TimeoutError:
                        # Process timed out
                        return {
                            "success": False,
                            "stdout": "",
                            "stderr": f"Command timed out after {timeout} seconds",
                            "return_code": -15,  # SIGTERM
                            "execution_time": time.time() - start_time,
                        }
                else:
                    # No output capture
                    try:
                        if timeout > 0:
                            return_code = await asyncio.wait_for(
                                process.wait(), timeout=timeout
                            )
                        else:
                            return_code = await process.wait()

                        stdout, stderr = "", ""

                    except asyncio.TimeoutError:
                        return {
                            "success": False,
                            "stdout": "",
                            "stderr": f"Command timed out after {timeout} seconds",
                            "return_code": -15,
                            "execution_time": time.time() - start_time,
                        }

            execution_time = time.time() - start_time

            return {
                "success": return_code == 0,
                "stdout": stdout.rstrip() if stdout else "",
                "stderr": stderr.rstrip() if stderr else "",
                "return_code": return_code,
                "execution_time": execution_time,
            }

        except FileNotFoundError as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Command not found: {e}",
                "return_code": 127,
                "execution_time": time.time() - start_time,
            }
        except PermissionError as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Permission denied: {e}",
                "return_code": 126,
                "execution_time": time.time() - start_time,
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "return_code": -1,
                "execution_time": time.time() - start_time,
            }

    def _expect_eof_safe(self, child):
        """Safely expect EOF from pexpect child process."""
        try:
            child.expect(pexpect.EOF)
        except pexpect.TIMEOUT:
            # Expected for timeout scenarios
            pass
        except pexpect.exceptions.ExceptionPexpect:
            # Handle other pexpect exceptions
            pass
        except Exception:  # nosec
            # Catch any other exceptions
            pass

    async def _execute_interactive(
        self,
        shell_cmd: List[str],
        work_dir: Path,
        env: Dict[str, str],
        timeout: int,
        input_data: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute command in interactive mode using pexpect with improved handling."""
        output_buffer = io.StringIO()
        child = None
        start_time = time.time()

        try:
            # Convert shell command to string
            cmd_str = " ".join(shlex.quote(arg) for arg in shell_cmd)

            # Create pexpect spawn with conservative settings
            child = pexpect.spawn(
                cmd_str,
                cwd=str(work_dir),
                env=env,
                encoding="utf-8",
                timeout=min(timeout, 30) if timeout > 0 else 30,
                maxread=8192,  # Limit read size
            )

            # Set up output capture
            child.logfile_read = output_buffer

            # Send input data if provided
            if input_data:
                input_lines = input_data.splitlines()
                for i, line in enumerate(input_lines):
                    try:
                        # Send line with timeout
                        await asyncio.wait_for(
                            asyncio.get_event_loop().run_in_executor(
                                None, child.sendline, line
                            ),
                            timeout=5.0,
                        )

                        # Small delay between lines
                        if i < len(input_lines) - 1:
                            await asyncio.sleep(0.1)

                    except asyncio.TimeoutError:
                        break

            # Wait for completion
            try:
                remaining_timeout = (
                    max(1, timeout - (time.time() - start_time)) if timeout > 0 else 30
                )

                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, self._expect_eof_safe, child
                    ),
                    timeout=remaining_timeout,
                )
            except asyncio.TimeoutError:
                pass

            # Get output and status
            final_output = output_buffer.getvalue()

            # Close child process
            child.close(force=True)
            return_code = child.exitstatus if child.exitstatus is not None else -1

            return {
                "success": return_code == 0,
                "stdout": final_output,
                "stderr": "",  # pexpect combines stdout/stderr
                "return_code": return_code,
                "execution_time": time.time() - start_time,
            }

        except pexpect.TIMEOUT:
            if child:
                child.terminate(force=True)
            return {
                "success": False,
                "stdout": output_buffer.getvalue(),
                "stderr": f"Interactive command timed out after {timeout} seconds",
                "return_code": -1,
                "execution_time": time.time() - start_time,
            }
        except Exception as e:
            if child:
                try:
                    child.terminate(force=True)
                except Exception:  # nosec
                    pass
            return {
                "success": False,
                "stdout": output_buffer.getvalue(),
                "stderr": str(e),
                "return_code": -1,
                "execution_time": time.time() - start_time,
            }
        finally:
            # Ensure cleanup
            if child and child.isalive():
                try:
                    child.terminate(force=True)
                except Exception:  # nosec
                    pass
            output_buffer.close()


class ScriptTool(Tool):
    """Tool for creating and executing shell scripts."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="script",
            description="Create and execute shell scripts with multiple commands",
            category="System Operations",
            parameters=[
                ToolParameter(
                    name="script_content",
                    type="string",
                    description="Script content (multiple commands separated by newlines)",  # noqa: E501
                    required=True,  # noqa: E501
                ),
                ToolParameter(
                    name="script_type",
                    type="string",
                    description="Script type: 'bash', 'sh', 'python', 'node'",
                    required=False,
                    default="bash",
                ),
                ToolParameter(
                    name="working_dir",
                    type="string",
                    description="Working directory for script execution",
                    required=False,
                    default=".",
                ),
                ToolParameter(
                    name="timeout",
                    type="number",
                    description="Script timeout in seconds",
                    required=False,
                    default=60,
                ),
                ToolParameter(
                    name="save_script",
                    type="boolean",
                    description="Save script to temporary file for inspection",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="env_vars",
                    type="object",
                    description="Environment variables for script",
                    required=False,
                    default={},
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a shell script with proper validation."""
        try:
            # Extract parameters (support both 'script_content' and 'script' for compatibility) # noqa: E501
            script_content = kwargs.get("script_content") or kwargs.get(
                "script"
            )  # noqa: E501
            script_type = kwargs.get("script_type", "bash")
            working_dir = kwargs.get("working_dir", ".")
            timeout = kwargs.get("timeout", 60)
            save_script = kwargs.get("save_script", False)
            env_vars = kwargs.get("env_vars", {})

            if not script_content:
                return ToolResult(
                    success=False, output="", error="No script content provided"
                )

            # Validate working directory
            is_valid, error_msg, work_dir = path_validator.validate_path(
                working_dir, check_exists=True
            )
            if not is_valid:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Working directory validation failed: {error_msg}",
                )

            # Create temporary script file
            script_extensions = {
                "bash": ".sh",
                "sh": ".sh",
                "python": ".py",
                "node": ".js",
                "javascript": ".js",
            }

            extension = script_extensions.get(script_type, ".sh")

            # Create temporary script file (Windows-compatible approach)
            fd, script_path = tempfile.mkstemp(
                suffix=extension,
                dir=tempfile.gettempdir(),
            )

            try:
                # Write and close the file before execution (Windows compatibility)
                with os.fdopen(fd, "w", encoding="utf-8") as script_file:
                    # Add shebang if needed (Unix only)
                    if platform.system() != "Windows":
                        if script_type == "bash":
                            script_file.write("#!/bin/bash\nset -e\n\n")
                        elif script_type == "python":
                            script_file.write("#!/usr/bin/env python3\n\n")
                        elif script_type in ["node", "javascript"]:
                            script_file.write("#!/usr/bin/env node\n\n")

                    script_file.write(script_content)

                # Make script executable (Unix only)
                if platform.system() != "Windows":
                    os.chmod(script_path, 0o700)  # User read/write/execute only

                # Prepare execution command
                if script_type == "bash":
                    if platform.system() == "Windows":
                        # On Windows, check if bash is available
                        bash_path = shutil.which("bash") or shutil.which("git-bash")
                        if not bash_path:
                            return ToolResult(
                                success=False,
                                output="",
                                error=(
                                    "Bash is not available on this Windows system. "
                                    "Please install Git for Windows (Git Bash), "
                                    "Windows Subsystem for Linux (WSL), or use "
                                    "script_type='python' for cross-platform scripts."
                                ),
                            )
                        cmd = [bash_path, script_path]
                    else:
                        cmd = [shutil.which("bash") or "bash", script_path]
                elif script_type == "python":
                    python_cmd = (
                        shutil.which("python3") or shutil.which("python") or "python"
                    )
                    cmd = [python_cmd, script_path]
                elif script_type in ["node", "javascript"]:
                    node_cmd = shutil.which("node") or "node"
                    cmd = [node_cmd, script_path]
                else:
                    if platform.system() == "Windows":
                        cmd = [shutil.which("cmd") or "cmd.exe", "/c", script_path]
                    else:
                        cmd = [shutil.which("sh") or "sh", script_path]

                # Execute script directly without going through shell wrapper
                # This avoids quoting issues with paths containing spaces
                result = await self._execute_script_direct(
                    cmd, work_dir or Path("."), timeout, env_vars
                )

                # Add script info to metadata
                if result.metadata:
                    result.metadata.update(
                        {
                            "script_type": script_type,
                            "script_path": (
                                script_path if save_script else "temporary"
                            ),
                            "script_size": len(script_content),
                        }
                    )

                if save_script:
                    result.output = f"Script saved to: {script_path}\n\n" + (
                        result.output or ""
                    )

                return result

            finally:
                # Clean up temporary file if not saving
                if not save_script:
                    try:
                        os.unlink(script_path)
                    except (OSError, FileNotFoundError):
                        pass  # File already deleted or inaccessible

        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Script execution failed: {str(e)}"
            )

    async def _execute_script_direct(
        self, cmd: List[str], work_dir: Path, timeout: int, env_vars: dict
    ) -> ToolResult:
        """Execute script directly using subprocess without shell wrapper."""
        import time

        start_time = time.time()

        try:
            # Prepare environment
            env = os.environ.copy()
            if env_vars:
                env.update(env_vars)

            # Execute directly using subprocess
            process = None
            try:
                # Set up process group for better cleanup on Unix
                start_new_session = platform.system() != "Windows" and hasattr(
                    os, "setsid"
                )

                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(work_dir),
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    start_new_session=start_new_session,
                )

                try:
                    if timeout > 0:
                        stdout_bytes, stderr_bytes = await asyncio.wait_for(
                            process.communicate(), timeout=timeout
                        )
                    else:
                        stdout_bytes, stderr_bytes = await process.communicate()

                    # Decode output
                    stdout = (
                        stdout_bytes.decode("utf-8", errors="replace")
                        if stdout_bytes
                        else ""
                    )
                    stderr = (
                        stderr_bytes.decode("utf-8", errors="replace")
                        if stderr_bytes
                        else ""
                    )

                    return_code = process.returncode
                    execution_time = time.time() - start_time

                    output_lines = [f"$ {' '.join(cmd)}", ""]
                    if stdout:
                        output_lines.append(stdout.rstrip())

                    return ToolResult(
                        success=return_code == 0,
                        output="\n".join(output_lines).rstrip(),
                        error=stderr.rstrip() if stderr else None,
                        metadata={
                            "command": " ".join(cmd),
                            "working_dir": str(work_dir),
                            "return_code": return_code,
                            "execution_time": execution_time,
                        },
                    )

                except asyncio.TimeoutError:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Script timed out after {timeout} seconds",
                        metadata={
                            "command": " ".join(cmd),
                            "return_code": -15,
                            "execution_time": time.time() - start_time,
                        },
                    )

            finally:
                # Clean up process
                if process and process.returncode is None:
                    try:
                        process.terminate()
                        await asyncio.wait_for(process.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        try:
                            process.kill()
                            await asyncio.wait_for(process.wait(), timeout=2.0)
                        except asyncio.TimeoutError:
                            pass
                    except Exception:  # nosec B110
                        pass

        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Script execution failed: {str(e)}",
                metadata={
                    "command": " ".join(cmd),
                    "return_code": -1,
                    "execution_time": time.time() - start_time,
                },
            )
