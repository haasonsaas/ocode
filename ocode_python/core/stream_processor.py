"""
Enhanced read-write pipeline with streaming processing and intelligent batching.

This module implements the stream processing architecture that separates reads from
writes, provides real-time streaming of intermediate results, and enables intelligent
context batching.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Set

from ..tools.base import ToolResult
from .context_manager import ContextManager


@dataclass
class Operation:
    """Represents a single operation in the pipeline."""

    operation_id: str
    operation_type: str  # 'read', 'write', 'analyze'
    tool_name: str
    arguments: Dict[str, Any]
    dependencies: Set[str] = field(default_factory=set)
    priority: int = 0  # Higher number = higher priority
    estimated_duration: float = 1.0  # Seconds
    created_at: float = field(default_factory=time.time)


@dataclass
class OperationResult:
    """Result of an operation execution."""

    operation_id: str
    success: bool
    result: ToolResult
    execution_time: float
    side_effects: List[str] = field(default_factory=list)


@dataclass
class PipelinePhase:
    """Represents a phase in the pipeline execution."""

    phase_name: str
    operations: List[Operation]
    can_parallelize: bool = True
    depends_on: List[str] = field(default_factory=list)


class ContextBatcher:
    """Intelligent context batching based on file types and dependencies."""

    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager
        self.size_estimates = {
            ".py": 5000,  # Average Python file size in bytes
            ".js": 3000,  # Average JavaScript file size
            ".ts": 4000,  # Average TypeScript file size
            ".md": 2000,  # Average Markdown file size
            ".json": 1000,  # Average JSON file size
            ".yaml": 500,  # Average YAML file size
            ".yml": 500,
        }

    async def predict_context_size(self, files: List[Path]) -> int:
        """Predict the total context size for a list of files."""
        total_size = 0

        for file_path in files:
            if file_path.exists():
                try:
                    actual_size = file_path.stat().st_size
                    total_size += actual_size
                except OSError:
                    # Use estimate based on extension
                    estimated_size = self.size_estimates.get(file_path.suffix, 2000)
                    total_size += estimated_size
            else:
                estimated_size = self.size_estimates.get(file_path.suffix, 2000)
                total_size += estimated_size

        return total_size

    async def create_smart_batches(
        self, files: List[Path], max_batch_size: int = 1024 * 1024  # 1MB
    ) -> List[List[Path]]:
        """Create intelligent batches based on file types and dependencies."""
        # Group files by type and estimated processing complexity
        file_groups = self._group_files_by_characteristics(files)

        batches: List[List[Path]] = []
        current_batch: List[Path] = []
        current_size = 0

        # Process groups in order of priority
        for group_name, group_files in file_groups.items():
            for file_path in group_files:
                estimated_size = await self._estimate_processing_size(file_path)

                if current_size + estimated_size > max_batch_size and current_batch:
                    # Start new batch
                    batches.append(current_batch)
                    current_batch = [file_path]
                    current_size = estimated_size
                else:
                    current_batch.append(file_path)
                    current_size += estimated_size

        if current_batch:
            batches.append(current_batch)

        return batches

    def _group_files_by_characteristics(
        self, files: List[Path]
    ) -> Dict[str, List[Path]]:
        """Group files by their processing characteristics."""
        groups: Dict[str, List[Path]] = {
            "source_code": [],  # .py, .js, .ts - needs symbol extraction
            "config": [],  # .json, .yaml, .yml - structured data
            "documentation": [],  # .md, .rst, .txt - text processing
            "data": [],  # .csv, .xml - data files
            "other": [],  # Everything else
        }

        type_mapping = {
            ".py": "source_code",
            ".js": "source_code",
            ".ts": "source_code",
            ".tsx": "source_code",
            ".jsx": "source_code",
            ".java": "source_code",
            ".cpp": "source_code",
            ".c": "source_code",
            ".go": "source_code",
            ".rs": "source_code",
            ".json": "config",
            ".yaml": "config",
            ".yml": "config",
            ".toml": "config",
            ".ini": "config",
            ".md": "documentation",
            ".rst": "documentation",
            ".txt": "documentation",
            ".csv": "data",
            ".xml": "data",
        }

        for file_path in files:
            group = type_mapping.get(file_path.suffix, "other")
            groups[group].append(file_path)

        return groups

    async def _estimate_processing_size(self, file_path: Path) -> int:
        """Estimate the processing complexity/size for a file."""
        try:
            if file_path.exists():
                base_size = file_path.stat().st_size

                # Multiply by complexity factor based on file type
                complexity_factors = {
                    ".py": 3,  # Python needs AST parsing
                    ".js": 2,  # JavaScript parsing
                    ".ts": 2,  # TypeScript parsing
                    ".json": 1,  # Simple JSON parsing
                    ".md": 1,  # Text processing
                }

                factor = complexity_factors.get(file_path.suffix, 1)
                return base_size * factor
            else:
                return self.size_estimates.get(file_path.suffix, 2000)

        except OSError:
            return self.size_estimates.get(file_path.suffix, 2000)


class StreamProcessor:
    """Core stream processing engine with read-write separation."""

    def __init__(self, context_manager: ContextManager, enable_predictive: bool = True):
        self.context_manager = context_manager
        self.context_batcher = ContextBatcher(context_manager)
        self.operation_results: Dict[str, OperationResult] = {}
        self.read_cache: Dict[str, Any] = {}
        self._read_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()

        # Initialize predictive engine if enabled
        if enable_predictive:
            self.predictive_engine = PredictiveEngine(self)
        else:
            self.predictive_engine = None

    async def process_pipeline(
        self, operations: List[Operation]
    ) -> AsyncGenerator[OperationResult, None]:
        """Process a pipeline of operations with streaming results."""
        # Separate operations into phases
        phases = self._organize_into_phases(operations)

        # Execute phases in order
        for phase in phases:
            if phase.can_parallelize and len(phase.operations) > 1:
                # Execute operations in parallel
                async for result in self._execute_parallel_operations(phase.operations):
                    self.operation_results[result.operation_id] = result
                    yield result
            else:
                # Execute operations sequentially
                for operation in phase.operations:
                    result = await self._execute_single_operation(operation)
                    self.operation_results[result.operation_id] = result
                    yield result

    def _organize_into_phases(self, operations: List[Operation]) -> List[PipelinePhase]:
        """Organize operations into executable phases."""
        read_ops = [op for op in operations if op.operation_type == "read"]
        analyze_ops = [op for op in operations if op.operation_type == "analyze"]
        write_ops = [op for op in operations if op.operation_type == "write"]

        phases = []

        if read_ops:
            phases.append(
                PipelinePhase(
                    phase_name="read",
                    operations=sorted(read_ops, key=lambda x: x.priority, reverse=True),
                    can_parallelize=True,
                )
            )

        if analyze_ops:
            phases.append(
                PipelinePhase(
                    phase_name="analyze",
                    operations=sorted(
                        analyze_ops, key=lambda x: x.priority, reverse=True
                    ),
                    can_parallelize=True,
                    depends_on=["read"] if read_ops else [],
                )
            )

        if write_ops:
            phases.append(
                PipelinePhase(
                    phase_name="write",
                    operations=sorted(
                        write_ops, key=lambda x: x.priority, reverse=True
                    ),
                    can_parallelize=False,  # Writes must be sequential
                    depends_on=(
                        ["read", "analyze"] if (read_ops or analyze_ops) else []
                    ),
                )
            )

        return phases

    async def _execute_parallel_operations(
        self, operations: List[Operation]
    ) -> AsyncGenerator[OperationResult, None]:
        """Execute multiple operations in parallel."""
        semaphore = asyncio.Semaphore(5)  # Limit concurrency

        async def execute_with_semaphore(operation):
            async with semaphore:
                return await self._execute_single_operation(operation)

        # Start all operations
        tasks = [asyncio.create_task(execute_with_semaphore(op)) for op in operations]

        # Yield results as they complete
        for task in asyncio.as_completed(tasks):
            result = await task
            yield result

    async def _execute_single_operation(self, operation: Operation) -> OperationResult:
        """Execute a single operation."""
        start_time = time.time()

        try:
            if operation.operation_type == "read":
                result = await self._execute_read_operation(operation)
            elif operation.operation_type == "write":
                result = await self._execute_write_operation(operation)
            elif operation.operation_type == "analyze":
                result = await self._execute_analyze_operation(operation)
            else:
                result = ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown operation type: {operation.operation_type}",
                )

            execution_time = time.time() - start_time

            return OperationResult(
                operation_id=operation.operation_id,
                success=result.success,
                result=result,
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = time.time() - start_time

            return OperationResult(
                operation_id=operation.operation_id,
                success=False,
                result=ToolResult(
                    success=False,
                    output="",
                    error=f"Operation execution failed: {str(e)}",
                ),
                execution_time=execution_time,
            )

    async def _execute_read_operation(self, operation: Operation) -> ToolResult:
        """Execute a read operation with caching."""
        async with self._read_lock:
            cache_key = f"{operation.tool_name}:{hash(str(operation.arguments))}"

            if cache_key in self.read_cache:
                return self.read_cache[cache_key]  # type: ignore[no-any-return]

            # Execute the read operation
            from ..tools.base import ToolRegistry

            registry = ToolRegistry()
            registry.register_core_tools()

            result = await registry.execute_tool(
                operation.tool_name, **operation.arguments
            )

            # Cache successful read results
            if result.success:
                self.read_cache[cache_key] = result

            return result

    async def _execute_write_operation(self, operation: Operation) -> ToolResult:
        """Execute a write operation (sequential to avoid conflicts)."""
        async with self._write_lock:
            from ..tools.base import ToolRegistry

            registry = ToolRegistry()
            registry.register_core_tools()

            result = await registry.execute_tool(
                operation.tool_name, **operation.arguments
            )
            return result

    async def _execute_analyze_operation(self, operation: Operation) -> ToolResult:
        """Execute an analysis operation."""
        from ..tools.base import ToolRegistry

        registry = ToolRegistry()
        registry.register_core_tools()

        result = await registry.execute_tool(operation.tool_name, **operation.arguments)
        return result

    async def stream_analysis(
        self, read_results: List[OperationResult]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream intermediate analysis results."""
        for result in read_results:
            if result.success and result.result.output:
                # Extract useful information from read results
                analysis = {
                    "operation_id": result.operation_id,
                    "content_preview": (
                        result.result.output[:200] + "..."
                        if len(result.result.output) > 200
                        else result.result.output
                    ),
                    "content_size": len(result.result.output),
                    "execution_time": result.execution_time,
                    "timestamp": time.time(),
                }

                yield analysis

    async def batch_reads(
        self, read_operations: List[Operation]
    ) -> List[OperationResult]:
        """Execute read operations in optimized batches."""
        # Group operations by target for efficiency
        file_operations = [op for op in read_operations if "path" in op.arguments]
        other_operations = [op for op in read_operations if "path" not in op.arguments]

        results = []

        # Process file operations in batches
        if file_operations:
            file_paths = [Path(op.arguments["path"]) for op in file_operations]
            batches = await self.context_batcher.create_smart_batches(file_paths)

            for batch in batches:
                batch_operations = [
                    op for op in file_operations if Path(op.arguments["path"]) in batch
                ]

                # Execute batch operations in parallel
                batch_results = []
                async for result in self._execute_parallel_operations(batch_operations):
                    batch_results.append(result)

                results.extend(batch_results)

        # Process other operations
        for operation in other_operations:
            result = await self._execute_single_operation(operation)
            results.append(result)

        return results

    async def batch_writes(
        self, write_operations: List[Operation]
    ) -> List[OperationResult]:
        """Execute write operations sequentially to avoid conflicts."""
        results = []

        # Sort by priority and dependencies
        sorted_operations = sorted(
            write_operations,
            key=lambda x: (x.priority, len(x.dependencies)),
            reverse=True,
        )

        for operation in sorted_operations:
            result = await self._execute_single_operation(operation)
            results.append(result)

            # Add delay between writes to prevent race conditions
            await asyncio.sleep(0.01)

        return results

    def clear_cache(self) -> None:
        """Clear the read operation cache."""
        self.read_cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self.read_cache),
            "total_operations": len(self.operation_results),
            "successful_operations": sum(
                1 for r in self.operation_results.values() if r.success
            ),
            "failed_operations": sum(
                1 for r in self.operation_results.values() if not r.success
            ),
        }

    async def cleanup(self) -> None:
        """Clean up stream processor resources."""
        if self.predictive_engine:
            await self.predictive_engine.cleanup()

        # Clear caches
        self.read_cache.clear()
        self.operation_results.clear()


class PredictiveEngine:
    """Predictive engine for pre-execution and cache warming."""

    def __init__(self, stream_processor: StreamProcessor):
        self.stream_processor = stream_processor
        self.prediction_patterns: Dict[str, List[str]] = {
            # Tool sequences that commonly follow each other
            "file_read": ["file_edit", "grep", "architect"],
            "git_status": ["git_diff", "git_commit"],
            "grep": ["file_edit", "file_read"],
            "ls": ["file_read", "cd"],
            "architect": ["file_read", "grep"],
        }
        self.execution_history: List[str] = []
        self.cache_warm_tasks: Set[asyncio.Task] = set()

    def predict_next_tools(
        self, current_tool: str, query_analysis: Dict[str, Any]
    ) -> List[str]:
        """Predict likely next tool calls based on patterns."""
        predictions = []

        # Pattern-based predictions
        if current_tool in self.prediction_patterns:
            predictions.extend(self.prediction_patterns[current_tool])

        # Query-based predictions
        suggested_tools = query_analysis.get("suggested_tools", [])
        for tool in suggested_tools:
            if tool != current_tool and tool not in predictions:
                predictions.append(tool)

        # History-based predictions (simple implementation)
        if len(self.execution_history) >= 2:
            # last_two = tuple(self.execution_history[-2:])
            # Could implement more sophisticated sequence prediction here
            pass

        return predictions[:3]  # Limit to top 3 predictions

    async def warm_cache_for_predictions(
        self, predictions: List[str], current_context: Dict[str, Any]
    ) -> None:
        """Pre-warm caches for predicted operations."""
        for tool_name in predictions:
            task = asyncio.create_task(
                self._warm_cache_for_tool(tool_name, current_context)
            )
            self.cache_warm_tasks.add(task)

            # Clean up completed tasks
            task.add_done_callback(self.cache_warm_tasks.discard)

    async def _warm_cache_for_tool(
        self, tool_name: str, context: Dict[str, Any]
    ) -> None:
        """Pre-warm cache for a specific tool."""
        try:
            # Create a background operation for cache warming
            if tool_name == "file_read" and "files" in context:
                # Pre-read likely files
                for file_path in context["files"][:5]:  # Limit to first 5 files
                    operation = Operation(
                        operation_id=f"cache_warm_{tool_name}_{hash(file_path)}",
                        operation_type="read",
                        tool_name=tool_name,
                        arguments={"path": file_path},
                        priority=-1,  # Low priority for cache warming
                    )

                    await self.stream_processor._execute_single_operation(operation)

        except Exception as e:
            logging.debug(f"Cache warming failed for {tool_name}: {e}")

    def record_execution(self, tool_name: str) -> None:
        """Record tool execution for pattern learning."""
        self.execution_history.append(tool_name)

        # Keep history manageable - maintain exactly 50 items max
        if len(self.execution_history) > 50:
            self.execution_history = self.execution_history[-50:]

    async def cleanup(self) -> None:
        """Clean up any running cache warming tasks."""
        for task in list(self.cache_warm_tasks):
            if not task.done():
                task.cancel()

        # Wait for all tasks to complete or be cancelled
        if self.cache_warm_tasks:
            await asyncio.gather(*self.cache_warm_tasks, return_exceptions=True)

        self.cache_warm_tasks.clear()
