"""
Tests for the retry handler utility.
"""

import asyncio
import pytest
from unittest.mock import patch

from ocode_python.utils.retry_handler import (
    RetryConfig,
    RetryError,
    retry_sync,
    retry_async,
    with_retry,
    with_retry_async,
    NETWORK_RETRY,
    API_RETRY,
    FILE_RETRY,
)


class TestRetryConfig:
    """Test RetryConfig class."""

    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
        assert config.retryable_exceptions == (Exception,)

    def test_custom_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            max_delay=30.0,
            exponential_base=1.5,
            jitter=False,
            retryable_exceptions=(ValueError, ConnectionError)
        )
        assert config.max_attempts == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.exponential_base == 1.5
        assert config.jitter is False
        assert config.retryable_exceptions == (ValueError, ConnectionError)

    def test_calculate_delay(self):
        """Test delay calculation."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)
        
        # Test exponential backoff
        assert config.calculate_delay(0) == 1.0  # 1.0 * (2^0)
        assert config.calculate_delay(1) == 2.0  # 1.0 * (2^1)
        assert config.calculate_delay(2) == 4.0  # 1.0 * (2^2)

    def test_calculate_delay_with_max(self):
        """Test delay calculation with max_delay limit."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, max_delay=3.0, jitter=False)
        
        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 3.0  # Capped at max_delay
        assert config.calculate_delay(3) == 3.0  # Still capped

    def test_calculate_delay_with_jitter(self):
        """Test delay calculation with jitter."""
        config = RetryConfig(base_delay=2.0, exponential_base=2.0, jitter=True)
        
        # With jitter, delay should be between 50%-100% of calculated value
        delay = config.calculate_delay(1)  # Base would be 4.0
        assert 2.0 <= delay <= 4.0

    def test_should_retry(self):
        """Test retry decision logic."""
        config = RetryConfig(
            max_attempts=3,
            retryable_exceptions=(ValueError, ConnectionError)
        )
        
        # Should retry for retryable exceptions within max attempts
        assert config.should_retry(ValueError("test"), 0) is True
        assert config.should_retry(ConnectionError("test"), 1) is True
        
        # Should not retry for non-retryable exceptions
        assert config.should_retry(TypeError("test"), 0) is False
        
        # Should not retry if max attempts reached
        assert config.should_retry(ValueError("test"), 3) is False


class TestRetrySyncDecorator:
    """Test synchronous retry decorator."""

    def test_successful_function(self):
        """Test function that succeeds on first try."""
        call_count = 0
        
        @retry_sync(max_attempts=3)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = success_func()
        assert result == "success"
        assert call_count == 1

    def test_function_succeeds_after_retries(self):
        """Test function that succeeds after some failures."""
        call_count = 0
        
        @retry_sync(max_attempts=3, base_delay=0.01)  # Fast for testing
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("temporary failure")
            return "success"
        
        result = flaky_func()
        assert result == "success"
        assert call_count == 3

    def test_function_fails_all_attempts(self):
        """Test function that fails all retry attempts."""
        call_count = 0
        
        @retry_sync(max_attempts=3, base_delay=0.01)
        def failing_func():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("persistent failure")
        
        with pytest.raises(RetryError) as exc_info:
            failing_func()
        
        assert call_count == 3
        assert "failed after 3 attempts" in str(exc_info.value)
        assert isinstance(exc_info.value.last_exception, ConnectionError)
        assert exc_info.value.attempts == 3

    def test_non_retryable_exception(self):
        """Test that non-retryable exceptions are not retried."""
        call_count = 0
        
        @retry_sync(
            max_attempts=3,
            retryable_exceptions=(ConnectionError,)
        )
        def func_with_non_retryable_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")
        
        with pytest.raises(RetryError):
            func_with_non_retryable_error()
        
        assert call_count == 1  # Should not retry

    def test_on_retry_callback(self):
        """Test the on_retry callback functionality."""
        retry_calls = []
        
        def on_retry_callback(exception, attempt, delay):
            retry_calls.append((str(exception), attempt, delay))
        
        @retry_sync(max_attempts=3, base_delay=0.01, on_retry=on_retry_callback)
        def failing_func():
            raise ConnectionError("test error")
        
        with pytest.raises(RetryError):
            failing_func()
        
        assert len(retry_calls) == 2  # 2 retries for 3 total attempts
        assert retry_calls[0][0] == "test error"
        assert retry_calls[0][1] == 1  # First retry
        assert retry_calls[1][1] == 2  # Second retry


class TestRetryAsyncDecorator:
    """Test asynchronous retry decorator."""

    @pytest.mark.asyncio
    async def test_successful_async_function(self):
        """Test async function that succeeds on first try."""
        call_count = 0
        
        @retry_async(max_attempts=3)
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await success_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_function_succeeds_after_retries(self):
        """Test async function that succeeds after some failures."""
        call_count = 0
        
        @retry_async(max_attempts=3, base_delay=0.01)
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("temporary failure")
            return "success"
        
        result = await flaky_func()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_function_fails_all_attempts(self):
        """Test async function that fails all retry attempts."""
        call_count = 0
        
        @retry_async(max_attempts=3, base_delay=0.01)
        async def failing_func():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("persistent failure")
        
        with pytest.raises(RetryError) as exc_info:
            await failing_func()
        
        assert call_count == 3
        assert "failed after 3 attempts" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_async_sleep_called(self):
        """Test that asyncio.sleep is called during retries."""
        with patch('asyncio.sleep') as mock_sleep:
            @retry_async(max_attempts=2, base_delay=1.0, jitter=False)
            async def failing_func():
                raise ConnectionError("test")
            
            with pytest.raises(RetryError):
                await failing_func()
            
            mock_sleep.assert_called_once_with(1.0)


class TestWithRetryFunctions:
    """Test with_retry utility functions."""

    def test_with_retry_success(self):
        """Test with_retry utility function with successful operation."""
        def success_func(value):
            return value * 2
        
        result = with_retry(success_func, NETWORK_RETRY, 5)
        assert result == 10

    def test_with_retry_failure(self):
        """Test with_retry utility function with failing operation."""
        def failing_func():
            raise ConnectionError("network error")
        
        with pytest.raises(RetryError):
            with_retry(failing_func, NETWORK_RETRY)

    @pytest.mark.asyncio
    async def test_with_retry_async_success(self):
        """Test with_retry_async utility function with successful operation."""
        async def success_func(value):
            return value * 2
        
        result = await with_retry_async(success_func, API_RETRY, 5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_with_retry_async_failure(self):
        """Test with_retry_async utility function with failing operation."""
        async def failing_func():
            raise ConnectionError("network error")
        
        with pytest.raises(RetryError):
            await with_retry_async(failing_func, API_RETRY)


class TestPredefinedConfigs:
    """Test predefined retry configurations."""

    def test_network_retry_config(self):
        """Test NETWORK_RETRY configuration."""
        assert NETWORK_RETRY.max_attempts == 3
        assert NETWORK_RETRY.base_delay == 1.0
        assert NETWORK_RETRY.max_delay == 30.0
        assert ConnectionError in NETWORK_RETRY.retryable_exceptions
        assert TimeoutError in NETWORK_RETRY.retryable_exceptions
        assert OSError in NETWORK_RETRY.retryable_exceptions

    def test_api_retry_config(self):
        """Test API_RETRY configuration."""
        assert API_RETRY.max_attempts == 5
        assert API_RETRY.base_delay == 0.5
        assert API_RETRY.max_delay == 60.0
        assert ConnectionError in API_RETRY.retryable_exceptions

    def test_file_retry_config(self):
        """Test FILE_RETRY configuration."""
        assert FILE_RETRY.max_attempts == 3
        assert FILE_RETRY.base_delay == 0.1
        assert FILE_RETRY.max_delay == 5.0
        assert PermissionError in FILE_RETRY.retryable_exceptions
        assert FileNotFoundError in FILE_RETRY.retryable_exceptions
        assert OSError in FILE_RETRY.retryable_exceptions


class TestRetryError:
    """Test RetryError exception class."""

    def test_retry_error_attributes(self):
        """Test RetryError exception attributes."""
        original_error = ConnectionError("original")
        retry_error = RetryError(
            "Function failed after 3 attempts",
            original_error,
            3
        )
        
        assert str(retry_error) == "Function failed after 3 attempts"
        assert retry_error.last_exception is original_error
        assert retry_error.attempts == 3


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_zero_max_attempts(self):
        """Test behavior with zero max attempts."""
        @retry_sync(max_attempts=0)
        def test_func():
            return "should not run"
        
        with pytest.raises(RetryError):
            test_func()

    def test_negative_delays(self):
        """Test behavior with negative delays."""
        config = RetryConfig(base_delay=-1.0, jitter=False)
        # Negative delays should still work (though unusual)
        delay = config.calculate_delay(0)
        assert delay == -1.0

    @pytest.mark.asyncio
    async def test_async_exception_during_sleep(self):
        """Test handling of exceptions during async sleep."""
        call_count = 0
        
        async def mock_sleep(delay):
            raise asyncio.CancelledError("sleep cancelled")
        
        with patch('asyncio.sleep', side_effect=mock_sleep):
            @retry_async(max_attempts=2, base_delay=0.1)
            async def failing_func():
                nonlocal call_count
                call_count += 1
                raise ConnectionError("test")
            
            with pytest.raises(asyncio.CancelledError):
                await failing_func()
            
            # Should have tried once before the sleep error
            assert call_count == 1

    def test_function_with_args_and_kwargs(self):
        """Test retry decorator with functions that have arguments."""
        call_count = 0
        
        @retry_sync(max_attempts=2, base_delay=0.01)
        def func_with_args(a, b, c=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("first attempt")
            return f"{a}-{b}-{c}"
        
        result = func_with_args("x", "y", c="z")
        assert result == "x-y-z"
        assert call_count == 2