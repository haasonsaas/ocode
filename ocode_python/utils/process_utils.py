"""
Utilities for robust process management and resource cleanup.

This module provides shared utilities for managing subprocess execution,
including proper cleanup, resource limits, and signal handling.
"""

import asyncio
import os
import platform
import signal
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import resource
    RESOURCE_AVAILABLE = True
except ImportError:
    # Windows doesn't have resource module
    resource = None
    RESOURCE_AVAILABLE = False


class ProcessLimits:
    """Resource limits for process execution."""
    
    def __init__(
        self,
        cpu_time: Optional[int] = None,
        memory_mb: Optional[int] = None,
        file_size_mb: Optional[int] = None,
        processes: Optional[int] = None,
    ):
        """Initialize process limits.
        
        Args:
            cpu_time: Maximum CPU time in seconds
            memory_mb: Maximum memory usage in MB
            file_size_mb: Maximum file size in MB
            processes: Maximum number of child processes
        """
        self.cpu_time = cpu_time
        self.memory_mb = memory_mb
        self.file_size_mb = file_size_mb
        self.processes = processes
        
    def apply_to_preexec(self):
        """Apply resource limits in subprocess preexec_fn (Unix only)."""
        if not RESOURCE_AVAILABLE or platform.system() == "Windows":
            return
            
        def set_limits():
            if self.cpu_time is not None:
                resource.setrlimit(resource.RLIMIT_CPU, (self.cpu_time, self.cpu_time))
                
            if self.memory_mb is not None:
                mem_bytes = self.memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
                
            if self.file_size_mb is not None:
                file_bytes = self.file_size_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_FSIZE, (file_bytes, file_bytes))
                
            if self.processes is not None:
                resource.setrlimit(resource.RLIMIT_NPROC, (self.processes, self.processes))
                
        return set_limits


class ProcessReaper:
    """Manages zombie process cleanup."""
    
    def __init__(self):
        self._original_handler = None
        self._setup_done = False
        
    def setup(self):
        """Set up signal handler for child process reaping (Unix only)."""
        if platform.system() == "Windows" or self._setup_done:
            return
            
        def sigchld_handler(signum, frame):
            # Reap all available zombie children
            while True:
                try:
                    pid, _ = os.waitpid(-1, os.WNOHANG)
                    if pid == 0:
                        break
                except ChildProcessError:
                    break
                except Exception:
                    break
                    
        try:
            self._original_handler = signal.signal(signal.SIGCHLD, sigchld_handler)
            self._setup_done = True
        except (ValueError, OSError):
            # Signal handling not available in this context
            pass
            
    def cleanup(self):
        """Restore original signal handler."""
        if self._setup_done and self._original_handler is not None:
            try:
                signal.signal(signal.SIGCHLD, self._original_handler)
            except (ValueError, OSError):
                pass
            self._setup_done = False


@asynccontextmanager
async def managed_subprocess(
    cmd: Union[str, List[str]],
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    stdin: Optional[int] = None,
    stdout: Optional[int] = None,
    stderr: Optional[int] = None,
    shell: bool = False,
    limits: Optional[ProcessLimits] = None,
    timeout: Optional[float] = None,
    kill_timeout: float = 5.0,
):
    """Context manager for subprocess with guaranteed cleanup.
    
    Args:
        cmd: Command to execute (string for shell=True, list otherwise)
        cwd: Working directory
        env: Environment variables
        stdin: stdin setting for subprocess
        stdout: stdout setting for subprocess
        stderr: stderr setting for subprocess
        shell: Whether to use shell execution
        limits: Resource limits to apply
        timeout: Overall timeout for the process
        kill_timeout: Timeout for kill after terminate
        
    Yields:
        The subprocess instance
        
    Ensures:
        - Process is terminated on exit
        - Process group is killed on Unix
        - Resources are cleaned up
    """
    process = None
    start_time = time.time()
    
    try:
        # Prepare kwargs
        kwargs: Dict[str, Any] = {}
        
        if cwd:
            kwargs['cwd'] = cwd
        if env:
            kwargs['env'] = env
        if stdin is not None:
            kwargs['stdin'] = stdin
        if stdout is not None:
            kwargs['stdout'] = stdout
        if stderr is not None:
            kwargs['stderr'] = stderr
            
        # Set up process group on Unix for better cleanup
        if platform.system() != "Windows":
            kwargs['start_new_session'] = True
            
            # Apply resource limits if provided
            if limits and RESOURCE_AVAILABLE:
                kwargs['preexec_fn'] = limits.apply_to_preexec()
        
        # Create subprocess
        if shell:
            process = await asyncio.create_subprocess_shell(cmd, **kwargs)
        else:
            process = await asyncio.create_subprocess_exec(*cmd, **kwargs)
            
        # Yield the process
        yield process
        
    finally:
        if process and process.returncode is None:
            # Process is still running, need to clean up
            await terminate_process_tree(process, kill_timeout)


async def terminate_process_tree(
    process: asyncio.subprocess.Process,
    kill_timeout: float = 5.0
):
    """Terminate a process and all its children.
    
    Args:
        process: The process to terminate
        kill_timeout: Timeout before escalating to SIGKILL
    """
    if process.returncode is not None:
        return  # Already terminated
        
    try:
        # Try graceful termination first
        process.terminate()
        
        try:
            await asyncio.wait_for(process.wait(), timeout=kill_timeout)
            return
        except asyncio.TimeoutError:
            pass
            
        # Escalate to SIGKILL
        try:
            if platform.system() == "Windows":
                # Windows-specific forceful termination
                if process.pid:
                    import subprocess
                    # Kill process tree on Windows
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                        capture_output=True,
                        check=False
                    )
            else:
                # Unix: kill the process group
                if hasattr(os, 'killpg') and process.pid:
                    try:
                        # Kill the entire process group
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    except (OSError, ProcessLookupError):
                        # Process might be dead already
                        pass
                        
            # Last resort: direct kill
            process.kill()
            
            # Wait a bit for it to die
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                # Process is really stuck
                pass
                
        except Exception:
            # Best effort - process might be dead
            pass
            
    except (ProcessLookupError, OSError):
        # Process already dead
        pass


async def run_with_timeout(
    coro,
    timeout: Optional[float],
    cleanup_func=None
) -> Tuple[bool, Any, Optional[str]]:
    """Run a coroutine with timeout and cleanup.
    
    Args:
        coro: Coroutine to run
        timeout: Timeout in seconds (None for no timeout)
        cleanup_func: Optional async cleanup function to call on timeout
        
    Returns:
        Tuple of (success, result, error_message)
    """
    if timeout is None or timeout <= 0:
        try:
            result = await coro
            return True, result, None
        except Exception as e:
            return False, None, str(e)
            
    try:
        result = await asyncio.wait_for(coro, timeout=timeout)
        return True, result, None
    except asyncio.TimeoutError:
        if cleanup_func:
            try:
                await cleanup_func()
            except Exception:
                pass
        return False, None, f"Operation timed out after {timeout} seconds"
    except Exception as e:
        return False, None, str(e)


def safe_decode(data: bytes, encoding: str = 'utf-8', errors: str = 'replace') -> str:
    """Safely decode bytes to string with fallback handling.
    
    Args:
        data: Bytes to decode
        encoding: Primary encoding to try
        errors: Error handling strategy
        
    Returns:
        Decoded string
    """
    if not data:
        return ""
        
    # Try primary encoding
    try:
        return data.decode(encoding, errors='strict')
    except UnicodeDecodeError:
        pass
        
    # Try with error replacement
    try:
        return data.decode(encoding, errors=errors)
    except Exception:
        pass
        
    # Try common fallback encodings
    for fallback_encoding in ['utf-8', 'latin-1', 'cp1252', 'ascii']:
        if fallback_encoding != encoding:
            try:
                return data.decode(fallback_encoding, errors=errors)
            except Exception:
                continue
                
    # Last resort: return representation
    return repr(data)


class ProcessOutputBuffer:
    """Thread-safe buffer for collecting process output."""
    
    def __init__(self, max_size: int = 10 * 1024 * 1024):  # 10MB default
        """Initialize output buffer.
        
        Args:
            max_size: Maximum buffer size in bytes
        """
        self.max_size = max_size
        self._buffer = bytearray()
        self._lock = asyncio.Lock()
        self._truncated = False
        
    async def append(self, data: bytes):
        """Append data to buffer with size limit."""
        async with self._lock:
            if len(self._buffer) + len(data) > self.max_size:
                # Truncate to fit
                remaining = self.max_size - len(self._buffer)
                if remaining > 0:
                    self._buffer.extend(data[:remaining])
                self._truncated = True
            else:
                self._buffer.extend(data)
                
    async def get_contents(self) -> Tuple[bytes, bool]:
        """Get buffer contents and truncation status."""
        async with self._lock:
            return bytes(self._buffer), self._truncated
            
    def get_size(self) -> int:
        """Get current buffer size."""
        return len(self._buffer)