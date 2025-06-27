"""
Retry decorator with exponential backoff for handling transient failures.

This module provides decorators and utilities for automatically retrying operations
that may fail due to temporary conditions like network issues, rate limits, or
temporary resource unavailability.
"""

import asyncio
import functools
import logging
import random
import time
from typing import Any, Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)


class RetryError(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(self, message: str, last_exception: Exception, attempts: int):
        super().__init__(message)
        self.last_exception = last_exception
        self.attempts = attempts


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ):
        """
        Initialize retry configuration.

        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Initial delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            exponential_base: Base for exponential backoff calculation
            jitter: Whether to add random jitter to delays
            retryable_exceptions: Tuple of exception types that should trigger retries
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        # Exponential backoff: base_delay * (exponential_base ^ attempt)
        delay = self.base_delay * (self.exponential_base**attempt)

        # Cap at max_delay
        delay = min(delay, self.max_delay)

        # Add jitter to prevent thundering herd
        if self.jitter:
            delay *= 0.5 + random.random() * 0.5  # nosec B311 # 50%-100% of calculated delay

        return delay

    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """Determine if an exception should trigger a retry."""
        if attempt >= self.max_attempts:
            return False
        return isinstance(exception, self.retryable_exceptions)


def retry_sync(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int, float], None]] = None,
):
    """
    Decorator for synchronous functions with retry logic.

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delays
        retryable_exceptions: Tuple of exception types that should trigger retries
        on_retry: Optional callback called before each retry

    Example:
        @retry_sync(max_attempts=3, base_delay=1.0)
        def fetch_data():
            # This will retry up to 3 times with exponential backoff
            return requests.get("https://api.example.com/data")
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retryable_exceptions=retryable_exceptions,
    )

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not config.should_retry(e, attempt):
                        break

                    if attempt < max_attempts - 1:  # Don't delay after last attempt
                        delay = config.calculate_delay(attempt)

                        if on_retry:
                            on_retry(e, attempt + 1, delay)

                        logger.debug(
                            f"Retrying {func.__name__} "
                            f"(attempt {attempt + 1}/{max_attempts}) "
                            f"after {delay:.2f}s due to: {e}"
                        )

                        time.sleep(delay)

            # All attempts exhausted
            raise RetryError(
                f"Function {func.__name__} failed after {max_attempts} attempts",
                last_exception or Exception("No exception recorded"),
                max_attempts,
            )

        return wrapper

    return decorator


def retry_async(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int, float], None]] = None,
):
    """
    Decorator for async functions with retry logic.

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delays
        retryable_exceptions: Tuple of exception types that should trigger retries
        on_retry: Optional callback called before each retry

    Example:
        @retry_async(max_attempts=3, base_delay=1.0)
        async def fetch_data():
            # This will retry up to 3 times with exponential backoff
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.example.com/data") as response:
                    return await response.json()
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retryable_exceptions=retryable_exceptions,
    )

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not config.should_retry(e, attempt):
                        break

                    if attempt < max_attempts - 1:  # Don't delay after last attempt
                        delay = config.calculate_delay(attempt)

                        if on_retry:
                            on_retry(e, attempt + 1, delay)

                        logger.debug(
                            f"Retrying {func.__name__} "
                            f"(attempt {attempt + 1}/{max_attempts}) "
                            f"after {delay:.2f}s due to: {e}"
                        )

                        await asyncio.sleep(delay)

            # All attempts exhausted
            raise RetryError(
                f"Function {func.__name__} failed after {max_attempts} attempts",
                last_exception or Exception("No exception recorded"),
                max_attempts,
            )

        return wrapper

    return decorator


# Common retry configurations for different use cases
NETWORK_RETRY = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    retryable_exceptions=(
        ConnectionError,
        TimeoutError,
        OSError,
    ),
)

API_RETRY = RetryConfig(
    max_attempts=5,
    base_delay=0.5,
    max_delay=60.0,
    retryable_exceptions=(
        ConnectionError,
        TimeoutError,
        OSError,
    ),
)

FILE_RETRY = RetryConfig(
    max_attempts=3,
    base_delay=0.1,
    max_delay=5.0,
    retryable_exceptions=(
        PermissionError,
        FileNotFoundError,
        OSError,
    ),
)


def with_retry(func: Callable, config: RetryConfig, *args, **kwargs) -> Any:
    """
    Execute a function with retry logic using the provided configuration.

    Args:
        func: Function to execute
        config: Retry configuration
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        Result of the function call

    Example:
        result = with_retry(
            requests.get,
            NETWORK_RETRY,
            "https://api.example.com/data",
            timeout=10
        )
    """
    last_exception = None

    for attempt in range(config.max_attempts):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            if not config.should_retry(e, attempt):
                break

            if attempt < config.max_attempts - 1:  # Don't delay after last attempt
                delay = config.calculate_delay(attempt)

                logger.debug(
                    f"Retrying {func.__name__} (attempt {attempt + 1}/{config.max_attempts}) "
                    f"after {delay:.2f}s due to: {e}"
                )

                time.sleep(delay)

    # All attempts exhausted
    raise RetryError(
        f"Function {func.__name__} failed after {config.max_attempts} attempts",
        last_exception or Exception("No exception recorded"),
        config.max_attempts,
    )


async def with_retry_async(func: Callable, config: RetryConfig, *args, **kwargs) -> Any:
    """
    Execute an async function with retry logic using the provided configuration.

    Args:
        func: Async function to execute
        config: Retry configuration
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        Result of the function call

    Example:
        result = await with_retry_async(
            session.get,
            API_RETRY,
            "https://api.example.com/data",
            timeout=10
        )
    """
    last_exception = None

    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            if not config.should_retry(e, attempt):
                break

            if attempt < config.max_attempts - 1:  # Don't delay after last attempt
                delay = config.calculate_delay(attempt)

                logger.debug(
                    f"Retrying {func.__name__} (attempt {attempt + 1}/{config.max_attempts}) "
                    f"after {delay:.2f}s due to: {e}"
                )

                await asyncio.sleep(delay)

    # All attempts exhausted
    raise RetryError(
        f"Function {func.__name__} failed after {config.max_attempts} attempts",
        last_exception or Exception("No exception recorded"),
        config.max_attempts,
    )
