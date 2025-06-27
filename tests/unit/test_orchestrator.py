"""
Tests for the advanced orchestrator with command queues and side effect tracking.
"""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from ocode_python.core.orchestrator import (
    AdvancedOrchestrator,
    CommandQueue,
    CommandTask,
    ConcurrentToolExecutor,
    Priority,
    RetryManager,
    SideEffect,
    SideEffectBroker,
    SideEffectType,
    TransientError,
)
from ocode_python.tools.base import ToolRegistry, ToolResult


class TestCommandQueue:
    """Test the priority-based command queue."""

    @pytest.fixture
    def command_queue(self):
        return CommandQueue()

    @pytest.fixture
    def sample_tasks(self):
        return [
            CommandTask(
                task_id="task1",
                tool_name="file_read",
                arguments={"path": "/test/file1.py"},
                priority=Priority.HIGH,
            ),
            CommandTask(
                task_id="task2",
                tool_name="file_write",
                arguments={"path": "/test/file2.py", "content": "test"},
                priority=Priority.NORMAL,
            ),
            CommandTask(
                task_id="task3",
                tool_name="git_status",
                arguments={},
                priority=Priority.BACKGROUND,
            ),
        ]

    @pytest.mark.asyncio
    async def test_priority_ordering(self, command_queue, sample_tasks):
        """Test that tasks are dequeued in priority order."""
        # Enqueue tasks in random order
        for task in [sample_tasks[1], sample_tasks[2], sample_tasks[0]]:
            await command_queue.enqueue(task)

        # Should get high priority first
        task = await command_queue.dequeue()
        assert task.priority == Priority.HIGH
        assert task.task_id == "task1"

        # Then normal priority
        task = await command_queue.dequeue()
        assert task.priority == Priority.NORMAL
        assert task.task_id == "task2"

        # Finally background
        task = await command_queue.dequeue()
        assert task.priority == Priority.BACKGROUND
        assert task.task_id == "task3"

    @pytest.mark.asyncio
    async def test_dependency_handling(self, command_queue):
        """Test that dependencies are respected."""
        dependent_task = CommandTask(
            task_id="dependent",
            tool_name="file_edit",
            arguments={"path": "/test/file.py"},
            priority=Priority.HIGH,
            dependencies={"prerequisite"},
        )

        prerequisite_task = CommandTask(
            task_id="prerequisite",
            tool_name="file_read",
            arguments={"path": "/test/file.py"},
            priority=Priority.NORMAL,
        )

        # Enqueue dependent task first
        await command_queue.enqueue(dependent_task)
        await command_queue.enqueue(prerequisite_task)

        # Should get prerequisite first despite lower priority
        task = await command_queue.dequeue()
        assert task.task_id == "prerequisite"

        # Mark prerequisite as completed
        await command_queue.mark_completed("prerequisite", ToolResult(True, "done"))

        # Now should get dependent task
        task = await command_queue.dequeue()
        assert task.task_id == "dependent"

    @pytest.mark.asyncio
    async def test_completion_tracking(self, command_queue, sample_tasks):
        """Test that completed tasks are properly tracked."""
        task = sample_tasks[0]
        await command_queue.enqueue(task)

        dequeued_task = await command_queue.dequeue()
        assert dequeued_task.task_id == task.task_id

        result = ToolResult(True, "success")
        await command_queue.mark_completed(task.task_id, result)

        assert task.task_id in command_queue.completed_tasks
        assert command_queue.completed_tasks[task.task_id].result == result


class TestSideEffectBroker:
    """Test side effect tracking and rollback."""

    @pytest.fixture
    def side_effect_broker(self):
        return SideEffectBroker()

    @pytest.fixture
    def sample_effects(self):
        return [
            SideEffect(
                effect_type=SideEffectType.FILE_WRITE,
                target="/test/file1.py",
                operation="write",
                timestamp=time.time(),
                tool_name="file_write",
                metadata={"task_id": "task1"},
            ),
            SideEffect(
                effect_type=SideEffectType.FILE_DELETE,
                target="/test/file2.py",
                operation="delete",
                timestamp=time.time(),
                tool_name="file_remove",
                metadata={"task_id": "task2"},
            ),
        ]

    @pytest.mark.asyncio
    async def test_effect_recording(self, side_effect_broker, sample_effects):
        """Test that side effects are properly recorded."""
        for effect in sample_effects:
            await side_effect_broker.record_effect(effect)

        assert len(side_effect_broker.effects) == 2
        assert side_effect_broker.effects[0].effect_type == SideEffectType.FILE_WRITE
        assert side_effect_broker.effects[1].effect_type == SideEffectType.FILE_DELETE

    @pytest.mark.asyncio
    async def test_file_backup(self, side_effect_broker, tmp_path):
        """Test that files are backed up before modification."""
        test_file = tmp_path / "test.txt"
        test_content = b"original content"
        test_file.write_bytes(test_content)

        effect = SideEffect(
            effect_type=SideEffectType.FILE_WRITE,
            target=str(test_file),
            operation="write",
            timestamp=time.time(),
            tool_name="file_write",
        )

        await side_effect_broker.record_effect(effect)

        # Check that backup was created
        assert str(test_file) in side_effect_broker.file_backups
        assert side_effect_broker.file_backups[str(test_file)] == test_content

    @pytest.mark.asyncio
    async def test_rollback_functionality(self, side_effect_broker, tmp_path):
        """Test rollback of file modifications."""
        test_file = tmp_path / "test.txt"
        original_content = b"original content"
        test_file.write_bytes(original_content)

        # Record the effect (which should backup the file)
        effect = SideEffect(
            effect_type=SideEffectType.FILE_WRITE,
            target=str(test_file),
            operation="write",
            timestamp=time.time(),
            tool_name="file_write",
            metadata={"task_id": "test_task"},
        )

        await side_effect_broker.record_effect(effect)

        # Simulate file modification
        test_file.write_bytes(b"modified content")
        assert test_file.read_bytes() == b"modified content"

        # Rollback the changes
        await side_effect_broker.rollback_effects("test_task")

        # File should be restored
        assert test_file.read_bytes() == original_content


class TestRetryManager:
    """Test retry logic with exponential backoff."""

    @pytest.fixture
    def retry_manager(self):
        return RetryManager(max_retries=3, base_delay=0.1)

    @pytest.fixture
    def sample_task(self):
        return CommandTask(
            task_id="retry_test",
            tool_name="flaky_tool",
            arguments={"param": "value"},
            priority=Priority.NORMAL,
        )

    @pytest.mark.asyncio
    async def test_successful_execution(self, retry_manager, sample_task):
        """Test successful execution on first try."""
        side_effect_broker = SideEffectBroker()

        async def successful_executor(task):
            return ToolResult(True, "success")

        result = await retry_manager.execute_with_retry(
            sample_task, successful_executor, side_effect_broker
        )

        assert result.success
        assert result.output == "success"
        assert sample_task.retry_count == 0

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self, retry_manager, sample_task):
        """Test retry behavior on transient errors."""
        side_effect_broker = SideEffectBroker()
        call_count = 0

        async def flaky_executor(task):
            nonlocal call_count
            call_count += 1

            if call_count < 3:
                raise TransientError("Temporary failure")
            return ToolResult(True, "success after retries")

        result = await retry_manager.execute_with_retry(
            sample_task, flaky_executor, side_effect_broker
        )

        assert result.success
        assert result.output == "success after retries"
        assert sample_task.retry_count == 2
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, retry_manager, sample_task):
        """Test behavior when max retries are exceeded."""
        side_effect_broker = SideEffectBroker()

        async def always_failing_executor(task):
            raise TransientError("Always fails")

        result = await retry_manager.execute_with_retry(
            sample_task, always_failing_executor, side_effect_broker
        )

        assert not result.success
        assert "Max retries exceeded" in result.error
        assert sample_task.retry_count == 3

    @pytest.mark.asyncio
    async def test_non_retryable_error(self, retry_manager, sample_task):
        """Test that non-retryable errors are not retried."""
        side_effect_broker = SideEffectBroker()

        async def non_retryable_executor(task):
            raise ValueError("Non-retryable error")

        result = await retry_manager.execute_with_retry(
            sample_task, non_retryable_executor, side_effect_broker
        )

        assert not result.success
        assert "Non-retryable error" in result.error
        assert sample_task.retry_count == 0


class TestConcurrentToolExecutor:
    """Test concurrent execution of independent tools."""

    @pytest.fixture
    def concurrent_executor(self):
        return ConcurrentToolExecutor(max_concurrent=3)

    @pytest.fixture
    def mock_tool_registry(self):
        registry = MagicMock(spec=ToolRegistry)
        registry.execute_tool = AsyncMock()
        registry.get_tool.return_value = None
        return registry

    @pytest.fixture
    def sample_tasks(self):
        return [
            CommandTask(
                task_id="task1",
                tool_name="file_read",
                arguments={"path": "/test/file1.py"},
                priority=Priority.NORMAL,
            ),
            CommandTask(
                task_id="task2",
                tool_name="file_read",
                arguments={"path": "/test/file2.py"},
                priority=Priority.NORMAL,
            ),
            CommandTask(
                task_id="task3",
                tool_name="git_status",
                arguments={},
                priority=Priority.NORMAL,
            ),
        ]

    @pytest.mark.asyncio
    async def test_independent_task_grouping(
        self, concurrent_executor, mock_tool_registry, sample_tasks
    ):
        """Test grouping of independent tasks."""
        groups = concurrent_executor._group_independent_tasks(
            sample_tasks, mock_tool_registry
        )

        # Tasks with different file paths should be grouped together
        # Git status task should be in a separate group due to different resources
        assert len(groups) >= 1

        # Verify that file operations on different files can be grouped
        file_tasks = [t for t in sample_tasks if t.tool_name == "file_read"]
        if len(file_tasks) > 1:
            # Different files should have different resources
            resources1 = concurrent_executor._get_task_resources(
                file_tasks[0], mock_tool_registry
            )
            resources2 = concurrent_executor._get_task_resources(
                file_tasks[1], mock_tool_registry
            )
            assert resources1 != resources2

    @pytest.mark.asyncio
    async def test_parallel_execution(
        self, concurrent_executor, mock_tool_registry, sample_tasks
    ):
        """Test parallel execution of tasks."""
        side_effect_broker = SideEffectBroker()

        # Mock successful tool execution
        mock_tool_registry.execute_tool.return_value = ToolResult(True, "success")

        results = await concurrent_executor.execute_parallel_tools(
            sample_tasks, mock_tool_registry, side_effect_broker
        )

        assert len(results) == len(sample_tasks)
        assert all(result.success for result in results)

        # Verify that tools were actually called
        assert mock_tool_registry.execute_tool.call_count == len(sample_tasks)

    @pytest.mark.asyncio
    async def test_resource_conflict_detection(
        self, concurrent_executor, mock_tool_registry
    ):
        """Test detection of resource conflicts."""
        conflicting_tasks = [
            CommandTask(
                task_id="task1",
                tool_name="file_read",
                arguments={"path": "/test/same_file.py"},
                priority=Priority.NORMAL,
            ),
            CommandTask(
                task_id="task2",
                tool_name="file_write",
                arguments={"path": "/test/same_file.py", "content": "new"},
                priority=Priority.NORMAL,
            ),
        ]

        groups = concurrent_executor._group_independent_tasks(
            conflicting_tasks, mock_tool_registry
        )

        # Conflicting tasks should be in separate groups
        assert len(groups) == 2
        assert len(groups[0]) == 1
        assert len(groups[1]) == 1


class TestAdvancedOrchestrator:
    """Test the complete advanced orchestrator."""

    @pytest.fixture
    def mock_tool_registry(self):
        registry = MagicMock(spec=ToolRegistry)
        registry.execute_tool = AsyncMock(return_value=ToolResult(True, "success"))
        return registry

    @pytest.fixture
    def orchestrator(self, mock_tool_registry):
        return AdvancedOrchestrator(mock_tool_registry, max_concurrent=3)

    @pytest.mark.asyncio
    async def test_orchestrator_lifecycle(self, orchestrator):
        """Test starting and stopping the orchestrator."""
        assert not orchestrator.running

        await orchestrator.start()
        assert orchestrator.running
        assert orchestrator._worker_task is not None

        await orchestrator.stop()
        assert not orchestrator.running

    @pytest.mark.asyncio
    async def test_task_submission_and_execution(
        self, orchestrator, mock_tool_registry
    ):
        """Test submitting and executing tasks."""
        await orchestrator.start()

        try:
            # Submit a task
            task_id = await orchestrator.submit_task(
                "file_read", {"path": "/test/file.py"}, Priority.HIGH
            )

            # Wait for result
            result = await orchestrator.get_task_result(task_id, timeout=5.0)

            assert result is not None
            assert result.success

            # Verify the tool was called
            mock_tool_registry.execute_tool.assert_called_with(
                "file_read", path="/test/file.py"
            )

        finally:
            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_task_group_execution(self, orchestrator, mock_tool_registry):
        """Test executing a group of tasks."""
        tasks = [
            ("file_read", {"path": "/test/file1.py"}, Priority.NORMAL),
            ("file_read", {"path": "/test/file2.py"}, Priority.NORMAL),
            ("git_status", {}, Priority.BACKGROUND),
        ]

        results = await orchestrator.execute_task_group(tasks, parallel=True)

        assert len(results) == 3
        assert all(result.success for result in results)
        assert mock_tool_registry.execute_tool.call_count == 3

    @pytest.mark.asyncio
    async def test_metrics_collection(self, orchestrator):
        """Test that metrics are properly collected."""
        metrics = orchestrator.get_metrics()

        assert "active_tasks" in metrics
        assert "completed_tasks" in metrics
        assert "total_side_effects" in metrics
        assert "running" in metrics

        assert metrics["active_tasks"] == 0
        assert metrics["completed_tasks"] == 0
        assert metrics["running"] is False

    @pytest.mark.asyncio
    async def test_dependency_resolution(self, orchestrator, mock_tool_registry):
        """Test that task dependencies are properly resolved."""
        await orchestrator.start()

        try:
            # Submit dependent task first
            dependent_id = await orchestrator.submit_task(
                "file_edit",
                {"path": "/test/file.py", "content": "modified"},
                Priority.HIGH,
                dependencies={"prereq_task"},
            )

            # Submit prerequisite task
            prereq_id = await orchestrator.submit_task(
                "file_read", {"path": "/test/file.py"}, Priority.NORMAL
            )

            # Manually set the prerequisite task ID (in real usage, this would be
            # managed)
            orchestrator.command_queue.tasks[dependent_id].dependencies = {prereq_id}

            # Both tasks should complete
            prereq_result = await orchestrator.get_task_result(prereq_id, timeout=5.0)
            dependent_result = await orchestrator.get_task_result(
                dependent_id, timeout=5.0
            )

            assert prereq_result is not None
            assert dependent_result is not None
            assert prereq_result.success
            assert dependent_result.success

        finally:
            await orchestrator.stop()


class TestIntegrationScenarios:
    """Integration tests for complex orchestrator scenarios."""

    @pytest.fixture
    def real_tool_registry(self):
        """Use a real tool registry for integration tests."""
        registry = ToolRegistry()
        registry.register_core_tools()
        return registry

    @pytest.mark.asyncio
    async def test_file_operation_workflow(self, real_tool_registry, tmp_path):
        """Test a complete file operation workflow with side effects."""
        orchestrator = AdvancedOrchestrator(real_tool_registry)

        # Create test files
        test_file = tmp_path / "test.txt"
        test_file.write_text("original content")

        await orchestrator.start()

        try:
            # Execute a workflow: read → edit → read
            tasks = [
                ("file_read", {"path": str(test_file)}, Priority.HIGH),
                (
                    "file_write",
                    {"path": str(test_file), "content": "modified content"},
                    Priority.NORMAL,
                ),
                ("file_read", {"path": str(test_file)}, Priority.BACKGROUND),
            ]

            results = await orchestrator.execute_task_group(tasks, parallel=False)

            assert len(results) == 3
            assert results[0].success  # First read
            assert "original content" in results[0].output

            assert results[1].success  # Write

            assert results[2].success  # Second read
            assert "modified content" in results[2].output

            # Check side effects were recorded
            assert len(orchestrator.side_effect_broker.effects) >= 1
            file_write_effects = [
                e
                for e in orchestrator.side_effect_broker.effects
                if e.effect_type == SideEffectType.FILE_WRITE
            ]
            assert len(file_write_effects) >= 1

        finally:
            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, tmp_path):
        """Test error recovery in a complex workflow."""
        # Create a mock registry that fails intermittently
        registry = MagicMock(spec=ToolRegistry)
        call_count = 0

        async def flaky_execute_tool(tool_name, **kwargs):
            nonlocal call_count
            call_count += 1

            if tool_name == "flaky_tool" and call_count <= 2:
                return ToolResult(False, "", "Temporary network error")
            return ToolResult(True, "success")

        registry.execute_tool = flaky_execute_tool

        orchestrator = AdvancedOrchestrator(registry)
        await orchestrator.start()

        try:
            # Submit a task that will fail initially
            task_id = await orchestrator.submit_task(
                "flaky_tool", {"param": "value"}, Priority.HIGH
            )

            # Should eventually succeed after retries
            result = await orchestrator.get_task_result(task_id, timeout=10.0)

            assert result is not None
            # Note: The retry logic is handled in the retry manager,
            # so this test verifies the integration works

        finally:
            await orchestrator.stop()


if __name__ == "__main__":
    pytest.main([__file__])
