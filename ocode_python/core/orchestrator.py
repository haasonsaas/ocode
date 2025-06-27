"""
Advanced orchestration system with command queues, side-effect tracking, and retry.

This module implements sophisticated orchestration patterns including:
- Priority-based command queuing
- Side effect isolation and tracking
- Smart retry mechanisms with backoff
- Concurrent tool execution coordination
- Transaction-like rollback capabilities
"""

import asyncio
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from ..tools.base import ResourceLock, ToolRegistry, ToolResult

if TYPE_CHECKING:
    from .error_recovery import ErrorRecoveryModule

# Constants for retry and timing behavior
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_CONCURRENT = 5
WORKER_SLEEP_INTERVAL = 0.1
TASK_POLLING_INTERVAL = 0.1
ERROR_RECOVERY_DELAY = 1.0


class Priority(Enum):
    """Command execution priority levels."""

    HIGH = "high"
    NORMAL = "normal"
    BACKGROUND = "background"


class SideEffectType(Enum):
    """Types of side effects that tools can produce."""

    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    PROCESS_START = "process_start"
    NETWORK_REQUEST = "network_request"
    MEMORY_WRITE = "memory_write"
    GIT_OPERATION = "git_operation"


@dataclass
class SideEffect:
    """Represents a side effect from tool execution."""

    effect_type: SideEffectType
    target: str  # File path, process name, URL, etc.
    operation: str  # Specific operation performed
    timestamp: float
    tool_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    rollback_info: Optional[Dict[str, Any]] = None


@dataclass
class CommandTask:
    """Represents a command task in the queue."""

    task_id: str
    tool_name: str
    arguments: Dict[str, Any]
    priority: Priority
    dependencies: Set[str] = field(default_factory=set)
    side_effects: List[SideEffect] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[ToolResult] = None
    retry_count: int = 0
    max_retries: int = DEFAULT_MAX_RETRIES


class TransientError(Exception):
    """Exception for temporary errors that should be retried."""

    pass


class CommandQueue:
    """Priority-based command queue with dependency tracking."""

    def __init__(self):
        self.high_priority: Optional[asyncio.Queue[str]] = None
        self.normal_priority: Optional[asyncio.Queue[str]] = None
        self.background: Optional[asyncio.Queue[str]] = None
        self.tasks: Dict[str, CommandTask] = {}
        self.completed_tasks: Dict[str, CommandTask] = {}
        self._lock: Optional[asyncio.Lock] = None
        self._init_thread_lock = threading.Lock()

    async def _ensure_initialized(self) -> None:
        """Ensure queues are initialized using thread-safe pattern."""
        # Fast path: check if already initialized
        if (
            self.high_priority is not None
            and self.normal_priority is not None
            and self.background is not None
            and self._lock is not None
        ):
            return

        # Use thread lock for thread-safe lazy initialization
        with self._init_thread_lock:
            # Double-check pattern: check again after acquiring lock
            if self.high_priority is None:
                self.high_priority = asyncio.Queue()
            if self.normal_priority is None:
                self.normal_priority = asyncio.Queue()
            if self.background is None:
                self.background = asyncio.Queue()
            if self._lock is None:
                self._lock = asyncio.Lock()

    async def enqueue(self, task: CommandTask) -> None:
        """Add a task to the appropriate priority queue."""
        await self._ensure_initialized()
        async with self._lock:  # type: ignore[union-attr]
            self.tasks[task.task_id] = task

            if task.priority == Priority.HIGH:
                await self.high_priority.put(task.task_id)  # type: ignore[union-attr]
            elif task.priority == Priority.NORMAL:
                await self.normal_priority.put(task.task_id)  # type: ignore[union-attr]
            else:
                await self.background.put(task.task_id)  # type: ignore[union-attr]

    async def dequeue(self) -> Optional[CommandTask]:
        """Get the next task to execute, respecting priority and dependencies."""
        await self._ensure_initialized()
        async with self._lock:  # type: ignore[union-attr]
            # Always prefer high > normal > background
            for queue in [self.high_priority, self.normal_priority, self.background]:
                if queue and not queue.empty():
                    try:
                        task_id = queue.get_nowait()
                        task = self.tasks.get(task_id)

                        if task and self._are_dependencies_satisfied(task):
                            task.started_at = time.time()
                            return task
                        elif task:
                            # Dependencies not satisfied, re-queue
                            await queue.put(task_id)
                    except asyncio.QueueEmpty:
                        continue

        return None

    def _are_dependencies_satisfied(self, task: CommandTask) -> bool:
        """Check if all task dependencies are completed."""
        return all(dep_id in self.completed_tasks for dep_id in task.dependencies)

    async def mark_completed(self, task_id: str, result: ToolResult) -> None:
        """Mark a task as completed."""
        await self._ensure_initialized()
        async with self._lock:  # type: ignore[union-attr]
            if task_id in self.tasks:
                task = self.tasks.pop(task_id)
                task.completed_at = time.time()
                task.result = result
                self.completed_tasks[task_id] = task


class SideEffectBroker:
    """Tracks and manages side effects from tool execution."""

    def __init__(self):
        self.effects: List[SideEffect] = []
        self.file_backups: Dict[str, bytes] = {}  # For rollback
        self._lock: Optional[asyncio.Lock] = None
        self._init_thread_lock = threading.Lock()

    async def _ensure_initialized(self) -> None:
        """Ensure lock is initialized using thread-safe pattern."""
        # Fast path: check if already initialized
        if self._lock is not None:
            return

        # Use thread lock for thread-safe lazy initialization
        with self._init_thread_lock:
            # Double-check pattern: check again after acquiring lock
            if self._lock is None:
                self._lock = asyncio.Lock()

    async def record_effect(self, effect: SideEffect) -> None:
        """Record a side effect."""
        await self._ensure_initialized()
        async with self._lock:  # type: ignore[union-attr]
            self.effects.append(effect)

            # Create backup for file operations
            if effect.effect_type == SideEffectType.FILE_WRITE:
                await self._backup_file(effect.target)

    async def _backup_file(self, file_path: str) -> None:
        """Create a backup of a file before modification."""
        try:
            path = Path(file_path)
            if path.exists():
                self.file_backups[file_path] = path.read_bytes()
        except Exception as e:
            logging.warning(f"Failed to backup file {file_path}: {e}")

    async def rollback_effects(self, task_id: str) -> None:
        """Rollback side effects for a specific task."""
        await self._ensure_initialized()
        async with self._lock:  # type: ignore[union-attr]
            task_effects = [
                e for e in self.effects if e.metadata.get("task_id") == task_id
            ]

            for effect in reversed(task_effects):  # Rollback in reverse order
                try:
                    await self._rollback_single_effect(effect)
                except Exception as e:
                    logging.error(f"Failed to rollback effect {effect}: {e}")

    async def _rollback_single_effect(self, effect: SideEffect) -> None:
        """Rollback a single side effect."""
        if effect.effect_type == SideEffectType.FILE_WRITE:
            # Restore from backup
            if effect.target in self.file_backups:
                Path(effect.target).write_bytes(self.file_backups[effect.target])
        elif effect.effect_type == SideEffectType.FILE_DELETE:
            # Can't easily rollback deletions without backups
            logging.warning(f"Cannot rollback file deletion: {effect.target}")
        # Add more rollback logic for other effect types


class RetryManager:
    """Manages retry logic with exponential backoff and intelligent error recovery."""

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        error_recovery_module: Optional["ErrorRecoveryModule"] = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.error_recovery_module = error_recovery_module

    async def execute_with_retry(  # noqa: C901
        self,
        task: CommandTask,
        executor_func,
        side_effect_broker: SideEffectBroker,
        tool_registry: Optional[ToolRegistry] = None,
        original_goal: Optional[str] = None,
        execution_context: Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        """Execute a task with retry logic and intelligent error recovery."""
        last_error = None
        last_result = None

        for attempt in range(self.max_retries + 1):
            try:
                result = await executor_func(task)
                last_result = result

                if result and result.success:
                    return result  # type: ignore[no-any-return]
                elif result and self._is_retryable_error(result.error):
                    last_error = result.error
                    if attempt < self.max_retries:
                        delay = self.base_delay * (2**attempt)
                        await asyncio.sleep(delay)
                        task.retry_count += 1
                        continue

                # Traditional retries failed, try intelligent recovery
                if (
                    self.error_recovery_module
                    and tool_registry
                    and original_goal
                    and result
                    and not result.success
                ):

                    logging.info(
                        f"Attempting intelligent error recovery for {task.tool_name}"
                    )

                    # Prepare execution context
                    context = execution_context or {}
                    context.update(
                        {
                            "retry_count": task.retry_count,
                            "working_dir": getattr(task, "working_dir", None),
                            "attempt_number": attempt,
                        }
                    )

                    # Attempt recovery
                    recovery_result = await self.error_recovery_module.attempt_recovery(
                        original_goal=original_goal,
                        failed_command=task,
                        tool_result=result,
                        execution_context=context,
                        tool_registry=tool_registry,
                    )

                    if recovery_result and recovery_result.success:
                        logging.info(f"Error recovery successful for {task.tool_name}")
                        return recovery_result
                    else:
                        logging.warning(f"Error recovery failed for {task.tool_name}")

                return result or ToolResult(success=False, output="", error="No result")

            except TransientError as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    # Rollback any side effects from this attempt
                    await side_effect_broker.rollback_effects(task.task_id)

                    delay = self.base_delay * (2**attempt)
                    await asyncio.sleep(delay)
                    task.retry_count += 1
                    continue

            except Exception as e:
                # Non-retryable error
                return ToolResult(
                    success=False, output="", error=f"Non-retryable error: {str(e)}"
                )

        # All retries and recovery attempts failed
        final_error = f"Max retries exceeded. Last error: {last_error}"
        if last_result:
            # Include the last tool result error for more context
            final_error = (
                f"Max retries exceeded. Last error: {last_result.error or last_error}"
            )

        return ToolResult(
            success=False,
            output="",
            error=final_error,
        )

    def _is_retryable_error(self, error: Optional[str]) -> bool:
        """Determine if an error is retryable."""
        if not error:
            return False

        retryable_patterns = [
            "timeout",
            "connection",
            "network",
            "temporary",
            "resource unavailable",
            "try again",
        ]

        error_lower = error.lower()
        return any(pattern in error_lower for pattern in retryable_patterns)


class ConcurrentToolExecutor:
    """Manages concurrent execution of independent tools."""

    def __init__(self, max_concurrent: int = DEFAULT_MAX_CONCURRENT):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_tasks: Set[str] = set()

    async def execute_parallel_tools(
        self,
        tasks: List[CommandTask],
        tool_registry: ToolRegistry,
        side_effect_broker: SideEffectBroker,
    ) -> List[ToolResult]:
        """Execute independent tools in parallel."""
        # Identify truly independent tasks (no shared resources)
        independent_groups = self._group_independent_tasks(tasks, tool_registry)

        results = []
        for group in independent_groups:
            if len(group) == 1:
                # Single task, execute normally
                result = await self._execute_single_task(
                    group[0], tool_registry, side_effect_broker
                )
                results.append(result)
            else:
                # Multiple independent tasks, execute in parallel
                parallel_results = await self._execute_parallel_group(
                    group, tool_registry, side_effect_broker
                )
                results.extend(parallel_results)

        return results

    def _group_independent_tasks(
        self, tasks: List[CommandTask], tool_registry: ToolRegistry
    ) -> List[List[CommandTask]]:
        """Group tasks that can be executed independently."""
        # Simple implementation: group by resource conflicts
        groups: List[List[CommandTask]] = []
        used_resources: Set[str] = set()

        for task in tasks:
            task_resources = self._get_task_resources(task, tool_registry)

            if task_resources.isdisjoint(used_resources):
                # Can be executed with existing group
                if groups:
                    groups[-1].append(task)
                else:
                    groups.append([task])
                used_resources.update(task_resources)
            else:
                # Needs new group
                groups.append([task])
                used_resources = task_resources

        return groups

    def _get_task_resources(
        self, task: CommandTask, tool_registry: ToolRegistry
    ) -> Set[str]:
        """Get the resources that a task will access from tool definition."""
        resources = set()

        # Get tool definition from registry
        tool = tool_registry.get_tool(task.tool_name)
        if tool and hasattr(tool, "definition"):
            tool_def = tool.definition

            # Get resource locks from tool definition
            for lock in tool_def.resource_locks:
                resources.add(lock.value)
        else:
            # Fallback to basic heuristics if tool not found
            # Check for file operations
            for arg_name, arg_value in task.arguments.items():
                if "path" in arg_name.lower() or "file" in arg_name.lower():
                    if isinstance(arg_value, str):
                        # Any file operation on the same file should conflict
                        # Use the file path as the resource identifier
                        resources.add(f"file:{arg_value}")
                        break

            # Basic tool name heuristics as fallback
            if "git" in task.tool_name.lower():
                resources.add(ResourceLock.GIT.value)
            elif "memory" in task.tool_name.lower():
                resources.add(ResourceLock.MEMORY.value)
            elif "shell" in task.tool_name.lower() or "bash" in task.tool_name.lower():
                resources.add(ResourceLock.SHELL.value)
            elif "curl" in task.tool_name.lower() or "search" in task.tool_name.lower():
                resources.add(ResourceLock.NETWORK.value)

        return resources

    async def _execute_parallel_group(
        self,
        tasks: List[CommandTask],
        tool_registry: ToolRegistry,
        side_effect_broker: SideEffectBroker,
    ) -> List[ToolResult]:
        """Execute a group of tasks in parallel."""

        async def execute_task_with_semaphore(task):
            async with self.semaphore:
                return await self._execute_single_task(
                    task, tool_registry, side_effect_broker
                )

        results = await asyncio.gather(
            *[execute_task_with_semaphore(task) for task in tasks],
            return_exceptions=True,
        )

        # Convert exceptions to error results
        processed_results: List[ToolResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    ToolResult(
                        success=False,
                        output="",
                        error=f"Parallel execution error: {str(result)}",
                    )
                )
            elif isinstance(result, ToolResult):
                processed_results.append(result)
            else:
                processed_results.append(
                    ToolResult(success=False, output="", error="Unknown result type")
                )

        return processed_results

    async def _execute_single_task(
        self,
        task: CommandTask,
        tool_registry: ToolRegistry,
        side_effect_broker: SideEffectBroker,
    ) -> ToolResult:
        """Execute a single task with side effect tracking."""
        try:
            # Record pre-execution state for potential future use
            # pre_effects = len(side_effect_broker.effects)

            # Execute the tool
            result = await tool_registry.execute_tool(task.tool_name, **task.arguments)

            # Record side effects (simplified - in reality would be tool-specific)
            if task.tool_name.startswith("file_"):
                effect_type = (
                    SideEffectType.FILE_WRITE
                    if "write" in task.tool_name
                    else SideEffectType.FILE_READ
                )
                effect = SideEffect(
                    effect_type=effect_type,
                    target=task.arguments.get("path", "unknown"),
                    operation=task.tool_name,
                    timestamp=time.time(),
                    tool_name=task.tool_name,
                    metadata={"task_id": task.task_id},
                )
                await side_effect_broker.record_effect(effect)

            return result

        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Task execution failed: {str(e)}"
            )


class AdvancedOrchestrator:
    """Advanced orchestrator with all improvements integrated."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        error_recovery_module: Optional["ErrorRecoveryModule"] = None,
    ):
        self.tool_registry = tool_registry
        self.command_queue = CommandQueue()
        self.side_effect_broker = SideEffectBroker()
        self.retry_manager = RetryManager(error_recovery_module=error_recovery_module)
        self.concurrent_executor = ConcurrentToolExecutor(max_concurrent)
        self.running = False
        self._worker_task: Optional[asyncio.Task] = None
        self.current_goal: Optional[str] = None  # Track current high-level goal

    def set_current_goal(self, goal: str) -> None:
        """Set the current high-level goal for error recovery context."""
        self.current_goal = goal

    async def start(self) -> None:
        """Start the orchestrator worker."""
        if not self.running:
            self.running = True
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        """Stop the orchestrator worker."""
        self.running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def submit_task(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        priority: Priority = Priority.NORMAL,
        dependencies: Optional[Set[str]] = None,
    ) -> str:
        """Submit a task for execution."""
        task = CommandTask(
            task_id=str(uuid.uuid4()),
            tool_name=tool_name,
            arguments=arguments,
            priority=priority,
            dependencies=dependencies or set(),
        )

        await self.command_queue.enqueue(task)
        return task.task_id

    async def get_task_result(
        self, task_id: str, timeout: float = 30.0
    ) -> Optional[ToolResult]:
        """Get the result of a task, waiting if necessary."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            if task_id in self.command_queue.completed_tasks:
                return self.command_queue.completed_tasks[task_id].result

            await asyncio.sleep(TASK_POLLING_INTERVAL)

        return None

    async def execute_task_group(
        self, tasks: List[Tuple[str, Dict[str, Any], Priority]], parallel: bool = True
    ) -> List[ToolResult]:
        """Execute a group of tasks, optionally in parallel."""
        task_objects = []

        for tool_name, arguments, priority in tasks:
            task = CommandTask(
                task_id=str(uuid.uuid4()),
                tool_name=tool_name,
                arguments=arguments,
                priority=priority,
            )
            task_objects.append(task)

        if parallel:
            return await self.concurrent_executor.execute_parallel_tools(
                task_objects, self.tool_registry, self.side_effect_broker
            )
        else:
            results = []
            for task in task_objects:
                result = await self.concurrent_executor._execute_single_task(
                    task, self.tool_registry, self.side_effect_broker
                )
                results.append(result)
            return results

    async def _worker_loop(self) -> None:
        """Main worker loop for processing queued tasks."""
        while self.running:
            try:
                task = await self.command_queue.dequeue()
                if task:
                    # Execute task with retry logic
                    result = await self.retry_manager.execute_with_retry(
                        task,
                        lambda t: self.concurrent_executor._execute_single_task(
                            t, self.tool_registry, self.side_effect_broker
                        ),
                        self.side_effect_broker,
                        tool_registry=self.tool_registry,
                        original_goal=self.current_goal,
                        execution_context={"worker_mode": True},
                    )

                    await self.command_queue.mark_completed(task.task_id, result)
                else:
                    # No tasks available, wait a bit
                    await asyncio.sleep(TASK_POLLING_INTERVAL)

            except Exception as e:
                logging.error(f"Worker loop error: {e}")
                await asyncio.sleep(ERROR_RECOVERY_DELAY)

    async def execute_tool_with_context(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        """Execute tool directly with context, bypassing queue for execution."""
        # Add context to arguments if provided
        if context:
            arguments = {**arguments, "_context": context}

        task = CommandTask(
            task_id=str(uuid.uuid4()),
            tool_name=tool_name,
            arguments=arguments,
            priority=Priority.HIGH,  # Direct execution gets high priority
        )

        # Execute immediately with retry logic
        return await self.retry_manager.execute_with_retry(
            task,
            lambda t: self.concurrent_executor._execute_single_task(
                t, self.tool_registry, self.side_effect_broker
            ),
            self.side_effect_broker,
            tool_registry=self.tool_registry,
            original_goal=self.current_goal,
            execution_context={"direct_execution": True},
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Get orchestrator metrics."""
        return {
            "active_tasks": len(self.command_queue.tasks),
            "completed_tasks": len(self.command_queue.completed_tasks),
            "total_side_effects": len(self.side_effect_broker.effects),
            "running": self.running,
        }
