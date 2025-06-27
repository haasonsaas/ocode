"""Test timeout handler utilities."""

import asyncio
import time

import pytest

from ocode_python.utils.timeout_handler import (
    AdaptiveTimeout,
    TimeoutError,
    TimeoutManager,
    async_timeout,
    sync_timeout,
    with_timeout,
)


class TestAsyncTimeout:
    """Test async_timeout context manager."""

    @pytest.mark.asyncio
    async def test_async_timeout_success(self):
        """Test successful operation within timeout."""
        async with async_timeout(1.0, "test_operation"):
            await asyncio.sleep(0.1)
            result = "success"

        assert result == "success"

    @pytest.mark.asyncio
    async def test_async_timeout_failure(self):
        """Test timeout when operation takes too long."""
        with pytest.raises(TimeoutError) as exc_info:
            async with async_timeout(0.1, "test_operation"):
                await asyncio.sleep(0.5)

        assert "timed out after 0.1 seconds" in str(exc_info.value)
        assert "test_operation" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_async_timeout_with_cleanup(self):
        """Test cleanup function is called on timeout."""
        cleanup_called = False

        async def cleanup():
            nonlocal cleanup_called
            cleanup_called = True

        with pytest.raises(TimeoutError):
            async with async_timeout(0.1, "test_operation", cleanup=cleanup):
                await asyncio.sleep(0.5)

        assert cleanup_called


class TestSyncTimeout:
    """Test sync_timeout decorator."""

    def test_sync_timeout_success(self):
        """Test successful operation within timeout."""

        @sync_timeout(1.0, "test_function")
        def fast_function():
            time.sleep(0.1)
            return "success"

        result = fast_function()
        assert result == "success"

    def test_sync_timeout_failure(self):
        """Test timeout when function takes too long."""

        @sync_timeout(0.1, "test_function")
        def slow_function():
            time.sleep(0.5)
            return "should not return"

        with pytest.raises(TimeoutError) as exc_info:
            slow_function()

        assert "timed out after 0.1 seconds" in str(exc_info.value)
        assert "test_function" in str(exc_info.value)

    def test_sync_timeout_with_exception(self):
        """Test that exceptions are properly propagated."""

        @sync_timeout(1.0, "test_function")
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            failing_function()


class TestWithTimeout:
    """Test with_timeout utility function."""

    @pytest.mark.asyncio
    async def test_with_timeout_success(self):
        """Test successful coroutine execution."""

        async def test_coro():
            await asyncio.sleep(0.1)
            return "success"

        result = await with_timeout(test_coro(), 1.0, "test_op")
        assert result == "success"

    @pytest.mark.asyncio
    async def test_with_timeout_failure_raise(self):
        """Test timeout with exception raising."""

        async def slow_coro():
            await asyncio.sleep(0.5)
            return "should not return"

        with pytest.raises(TimeoutError) as exc_info:
            await with_timeout(slow_coro(), 0.1, "test_op")

        assert "timed out after 0.1 seconds" in str(exc_info.value)
        assert "test_op" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_with_timeout_failure_default(self):
        """Test timeout with default value."""

        async def slow_coro():
            await asyncio.sleep(0.5)
            return "should not return"

        result = await with_timeout(
            slow_coro(), 0.1, "test_op", default="default_value", raise_on_timeout=False
        )
        assert result == "default_value"


class TestTimeoutManager:
    """Test TimeoutManager for cascading timeouts."""

    @pytest.mark.asyncio
    async def test_timeout_manager_success(self):
        """Test successful operations within total timeout."""
        tm = TimeoutManager(total_timeout=5.0)

        async with tm.operation("step1", 2.0):
            await asyncio.sleep(0.1)

        async with tm.operation("step2", 2.0):
            await asyncio.sleep(0.1)

        assert len(tm.operations) == 2
        assert tm.remaining_time() > 0

    @pytest.mark.asyncio
    async def test_timeout_manager_total_exceeded(self):
        """Test when total timeout is exceeded."""
        tm = TimeoutManager(total_timeout=0.5)

        async with tm.operation("step1", 0.3):
            await asyncio.sleep(0.2)

        # Sleep to exceed total timeout
        await asyncio.sleep(0.4)

        with pytest.raises(TimeoutError) as exc_info:
            async with tm.operation("step2", 1.0):
                pass

        assert "Total timeout exceeded" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_timeout_manager_operation_timeout(self):
        """Test individual operation timeout."""
        tm = TimeoutManager(total_timeout=5.0)

        with pytest.raises(TimeoutError):
            async with tm.operation("slow_op", 0.1):
                await asyncio.sleep(0.5)


class TestAdaptiveTimeout:
    """Test AdaptiveTimeout for dynamic timeout adjustment."""

    @pytest.mark.asyncio
    async def test_adaptive_timeout_initial(self):
        """Test initial timeout value."""
        at = AdaptiveTimeout(base_timeout=1.0)
        assert at.get_timeout() == 1.0

    @pytest.mark.asyncio
    async def test_adaptive_timeout_adjustment(self):
        """Test timeout adjustment based on history."""
        at = AdaptiveTimeout(
            base_timeout=1.0, min_timeout=0.5, max_timeout=5.0, adjustment_factor=2.0
        )

        # Record fast operations
        at.record_duration(0.1)
        at.record_duration(0.2)
        at.record_duration(0.15)

        # Timeout should adjust to average * factor
        # Average = 0.15, * 2.0 = 0.3, but min is 0.5
        assert at.get_timeout() == 0.5

    @pytest.mark.asyncio
    async def test_adaptive_timeout_max_limit(self):
        """Test maximum timeout limit."""
        at = AdaptiveTimeout(base_timeout=1.0, max_timeout=2.0, adjustment_factor=10.0)

        # Record slow operation
        at.record_duration(5.0)

        # Should be capped at max_timeout
        assert at.get_timeout() == 2.0

    @pytest.mark.asyncio
    async def test_adaptive_timeout_execute(self):
        """Test execute method with adaptive timeout."""
        at = AdaptiveTimeout(base_timeout=1.0)

        async def fast_op():
            await asyncio.sleep(0.1)
            return "success"

        result = await at.execute(fast_op(), "test_op")
        assert result == "success"

        # Check that duration was recorded
        assert len(at.history) == 1
        assert 0.05 < at.history[0] < 0.2  # Approximate timing

    @pytest.mark.asyncio
    async def test_adaptive_timeout_execute_timeout(self):
        """Test execute method when operation times out."""
        at = AdaptiveTimeout(base_timeout=0.1, adjustment_factor=2.0)

        async def slow_op():
            await asyncio.sleep(0.5)
            return "should not return"

        with pytest.raises(TimeoutError):
            await at.execute(slow_op(), "test_op")

        # Timeout should increase after failure
        assert at.get_timeout() == 0.2


class TestTimeoutError:
    """Test enhanced TimeoutError class."""

    def test_timeout_error_basic(self):
        """Test basic TimeoutError creation."""
        error = TimeoutError("Operation failed")
        assert str(error) == "Operation failed"

    def test_timeout_error_with_context(self):
        """Test TimeoutError with full context."""
        error = TimeoutError(
            "Operation failed",
            operation="file_read",
            duration=5.0,
            context={"file": "test.txt", "size": 1024},
        )

        assert error.operation == "file_read"
        assert error.duration == 5.0
        assert error.context["file"] == "test.txt"
        assert "file_read" in str(error)
        assert "5.0s" in str(error)
