"""
Process monitoring and management tool.
"""

import json
import platform
from datetime import datetime
from typing import Any, Dict, List

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    # Fallback for environments where psutil is not available
    psutil = None
    PSUTIL_AVAILABLE = False

from ..utils.timeout_handler import TimeoutError, with_timeout
from .base import (
    ErrorHandler,
    ErrorType,
    Tool,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)


class ProcessMonitorTool(Tool):
    """Tool for monitoring system processes."""

    @property
    def definition(self) -> ToolDefinition:
        """Define the ps (process monitor) tool specification.

        Returns:
            ToolDefinition with parameters for monitoring system processes
            including list, find, info, and check actions.
        """
        return ToolDefinition(
            name="ps",
            description="Monitor and query system processes",
            category="System Operations",
            parameters=[
                ToolParameter(
                    name="action",
                    type="string",
                    description="Action: list, find, info, check",
                    required=True,
                ),
                ToolParameter(
                    name="name",
                    type="string",
                    description="Process name to search for (supports partial match)",
                    required=False,
                ),
                ToolParameter(
                    name="pid",
                    type="number",
                    description="Process ID for 'info' action",
                    required=False,
                ),
                ToolParameter(
                    name="sort_by",
                    type="string",
                    description="Sort by: cpu, memory, pid, name (default: cpu)",
                    required=False,
                    default="cpu",
                ),
                ToolParameter(
                    name="limit",
                    type="number",
                    description="Limit number of results (default: 20)",
                    required=False,
                    default=20,
                ),
                ToolParameter(
                    name="format",
                    type="string",
                    description="Output format: table, json (default: table)",
                    required=False,
                    default="table",
                ),
                ToolParameter(
                    name="timeout",
                    type="number",
                    description="Operation timeout in seconds (default: 10)",
                    required=False,
                    default=10,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute process monitoring operations."""
        if not PSUTIL_AVAILABLE:
            return ToolResult(
                success=False,
                output="",
                error="Process monitoring not available (psutil not installed)",
            )

        action = kwargs.get("action", "").lower()
        name = kwargs.get("name")
        pid = kwargs.get("pid")
        sort_by = kwargs.get("sort_by", "cpu").lower()
        limit = kwargs.get("limit", 20)
        output_format = kwargs.get("format", "table").lower()
        timeout = kwargs.get("timeout", 10)

        if not action:
            return ToolResult(
                success=False, output="", error="Action parameter is required"
            )

        valid_actions = ["list", "find", "info", "check"]
        if action not in valid_actions:
            return ToolResult(
                success=False,
                output="",
                error=f"Invalid action. Must be one of: {', '.join(valid_actions)}",
            )

        try:
            if action == "list":
                return await with_timeout(
                    self._action_list(sort_by, limit, output_format),
                    timeout=timeout,
                    operation="process_list",
                )
            elif action == "find":
                if not name:
                    return ToolResult(
                        success=False,
                        output="",
                        error="Name parameter is required for 'find' action",
                    )
                return await with_timeout(
                    self._action_find(name, output_format),
                    timeout=timeout,
                    operation=f"process_find({name})",
                )
            elif action == "info":
                if pid is None:
                    return ToolResult(
                        success=False,
                        output="",
                        error="PID parameter is required for 'info' action",
                    )
                return await with_timeout(
                    self._action_info(int(pid), output_format),
                    timeout=timeout,
                    operation=f"process_info({pid})",
                )
            elif action == "check":
                if not name:
                    return ToolResult(
                        success=False,
                        output="",
                        error="Name parameter is required for 'check' action",
                    )
                return await with_timeout(
                    self._action_check(name),
                    timeout=timeout,
                    operation=f"process_check({name})",
                )

            # This should never happen due to validation above, but included for completeness  # noqa: E501
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown action: {action}",
            )

        except TimeoutError as e:
            return ErrorHandler.create_error_result(
                f"Process operation timed out: {str(e)}",
                ErrorType.TIMEOUT_ERROR,
                {"action": action, "timeout": timeout},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error executing process operation: {str(e)}",
            )

    async def _action_list(
        self, sort_by: str, limit: int, output_format: str
    ) -> ToolResult:
        """List running processes."""
        processes = []

        # Validate sort_by
        valid_sort = ["cpu", "memory", "pid", "name"]
        if sort_by not in valid_sort:
            sort_by = "cpu"

        # Validate limit
        if limit < 1 or limit > 100:
            limit = 20

        # Get process list
        for proc in psutil.process_iter(
            [
                "pid",
                "name",
                "cpu_percent",
                "memory_percent",
                "status",
                "create_time",
                "username",
            ]
        ):
            try:
                info = proc.info
                # Get CPU percent (this might be 0 on first call)
                cpu_percent = proc.cpu_percent(interval=0.1)

                processes.append(
                    {
                        "pid": info["pid"],
                        "name": info["name"] or "Unknown",
                        "cpu": round(cpu_percent, 2),
                        "memory": round(info["memory_percent"] or 0, 2),
                        "status": info["status"],
                        "user": info["username"] or "Unknown",
                        "started": datetime.fromtimestamp(info["create_time"]).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Sort processes
        sort_key = {
            "cpu": lambda x: x["cpu"],
            "memory": lambda x: x["memory"],
            "pid": lambda x: x["pid"],
            "name": lambda x: x["name"].lower(),
        }
        processes.sort(
            key=sort_key.get(sort_by, sort_key["cpu"]),
            reverse=sort_by in ["cpu", "memory"],
        )

        # Limit results
        processes = processes[:limit]

        # Format output
        if output_format == "json":
            output = json.dumps(processes, indent=2)
        else:  # table
            output = self._format_table(processes)

        return ToolResult(
            success=True,
            output=output,
            metadata={
                "count": len(processes),
                "sort_by": sort_by,
                "total_processes": len(list(psutil.process_iter())),
            },
        )

    async def _action_find(self, name: str, output_format: str) -> ToolResult:
        """Find processes by name."""
        matching_processes = []
        name_lower = name.lower()

        for proc in psutil.process_iter(
            [
                "pid",
                "name",
                "cpu_percent",
                "memory_percent",
                "status",
                "cmdline",
                "username",
            ]
        ):
            try:
                info = proc.info
                proc_name = info["name"] or ""

                # Check if name matches in process name or cmdline
                cmdline = " ".join(info["cmdline"] or [])
                if name_lower in proc_name.lower() or name_lower in cmdline.lower():
                    cpu_percent = proc.cpu_percent(interval=0.1)

                    matching_processes.append(
                        {
                            "pid": info["pid"],
                            "name": proc_name,
                            "cpu": round(cpu_percent, 2),
                            "memory": round(info["memory_percent"] or 0, 2),
                            "status": info["status"],
                            "user": info["username"] or "Unknown",
                            "cmdline": cmdline,
                        }
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        if not matching_processes:
            return ToolResult(
                success=True,
                output=f"No processes found matching '{name}'",
                metadata={"search_term": name, "found": 0},
            )

        # Sort by CPU usage
        matching_processes.sort(key=lambda x: x["cpu"], reverse=True)

        # Format output
        if output_format == "json":
            output = json.dumps(matching_processes, indent=2)
        else:  # table
            output = self._format_find_table(matching_processes)

        return ToolResult(
            success=True,
            output=output,
            metadata={"search_term": name, "found": len(matching_processes)},
        )

    async def _action_info(self, pid: int, output_format: str) -> ToolResult:
        """Get detailed information about a specific process."""
        try:
            proc = psutil.Process(pid)

            # Gather detailed info
            with proc.oneshot():
                info = {
                    "pid": proc.pid,
                    "name": proc.name(),
                    "status": proc.status(),
                    "cpu_percent": round(proc.cpu_percent(interval=0.1), 2),
                    "memory_percent": round(proc.memory_percent(), 2),
                    "memory_info": {
                        "rss": proc.memory_info().rss,
                        "vms": proc.memory_info().vms,
                        "rss_mb": round(proc.memory_info().rss / 1024 / 1024, 2),
                        "vms_mb": round(proc.memory_info().vms / 1024 / 1024, 2),
                    },
                    "create_time": datetime.fromtimestamp(proc.create_time()).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "username": proc.username(),
                    "num_threads": proc.num_threads(),
                    "cmdline": " ".join(proc.cmdline()),
                    "exe": proc.exe() if hasattr(proc, "exe") else None,
                    "cwd": proc.cwd() if hasattr(proc, "cwd") else None,
                    "parent_pid": proc.ppid(),
                    "children": [child.pid for child in proc.children()],
                }

                # Add platform-specific info
                if platform.system() != "Windows":
                    info["nice"] = proc.nice()

            if output_format == "json":
                output = json.dumps(info, indent=2)
            else:  # table
                output = self._format_info_table(info)

            return ToolResult(success=True, output=output, metadata={"pid": pid})

        except psutil.NoSuchProcess:
            return ToolResult(
                success=False, output="", error=f"No process found with PID {pid}"
            )
        except psutil.AccessDenied:
            return ToolResult(
                success=False, output="", error=f"Access denied to process {pid}"
            )

    async def _action_check(self, name: str) -> ToolResult:
        """Check if a process is running."""
        name_lower = name.lower()
        running_pids = []

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if name_lower in proc.info["name"].lower():
                    running_pids.append(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        is_running = len(running_pids) > 0

        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "running": is_running,
                    "count": len(running_pids),
                    "pids": running_pids,
                },
                indent=2,
            ),
            metadata={
                "process_name": name,
                "running": is_running,
                "count": len(running_pids),
            },
        )

    def _format_table(self, processes: List[Dict[str, Any]]) -> str:
        """Format processes as a table."""
        if not processes:
            return "No processes to display"

        # Header
        lines = ["PID     CPU%   MEM%   STATUS       USER         NAME", "-" * 70]

        # Rows
        for proc in processes:
            lines.append(
                f"{proc['pid']:<7} {proc['cpu']:>5}  {proc['memory']:>5}  "
                f"{proc['status']:<11} {proc['user'][:12]:<12} {proc['name']}"
            )

        return "\n".join(lines)

    def _format_find_table(self, processes: List[Dict[str, Any]]) -> str:
        """Format found processes as a table."""
        if not processes:
            return "No processes found"

        # Header
        lines = ["PID     CPU%   MEM%   STATUS    NAME", "-" * 50]

        # Rows
        for proc in processes:
            lines.append(
                f"{proc['pid']:<7} {proc['cpu']:>5}  {proc['memory']:>5}  "
                f"{proc['status']:<9} {proc['name']}"
            )
            # Add command line on next line if present
            if proc["cmdline"]:
                lines.append(f"        CMD: {proc['cmdline'][:60]}...")

        return "\n".join(lines)

    def _format_info_table(self, info: Dict[str, Any]) -> str:
        """Format process info as a table."""
        lines = [
            f"Process Information for PID {info['pid']}",
            "=" * 50,
            f"Name:           {info['name']}",
            f"Status:         {info['status']}",
            f"User:           {info['username']}",
            f"CPU %:          {info['cpu_percent']}%",
            f"Memory %:       {info['memory_percent']}%",
            f"Memory RSS:     {info['memory_info']['rss_mb']} MB",
            f"Memory VMS:     {info['memory_info']['vms_mb']} MB",
            f"Threads:        {info['num_threads']}",
            f"Created:        {info['create_time']}",
            f"Parent PID:     {info['parent_pid']}",
        ]

        if info.get("nice") is not None:
            lines.append(f"Nice:           {info['nice']}")

        if info["cmdline"]:
            lines.append(f"Command:        {info['cmdline']}")

        if info["exe"]:
            lines.append(f"Executable:     {info['exe']}")

        if info["cwd"]:
            lines.append(f"Working Dir:    {info['cwd']}")

        if info["children"]:
            lines.append(f"Children PIDs:  {', '.join(map(str, info['children']))}")

        return "\n".join(lines)
