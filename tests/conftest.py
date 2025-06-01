"""
Pytest configuration and fixtures for OCode tests.
"""

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, Mock

import pytest

from ocode_python.core.api_client import OllamaAPIClient
from ocode_python.core.context_manager import ContextManager
from ocode_python.core.engine import OCodeEngine
from ocode_python.tools.base import ToolRegistry
from ocode_python.utils.auth import AuthenticationManager
from ocode_python.utils.config import ConfigManager
from ocode_python.utils.security import PermissionManager


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def mock_project_dir(temp_dir: Path) -> Path:
    """Create a mock project directory with sample files."""
    project_dir = temp_dir / "test_project"
    project_dir.mkdir()

    # Create sample Python files
    (project_dir / "main.py").write_text(
        '''
"""Main module."""

def main():
    """Main function."""
    print("Hello, world!")

if __name__ == "__main__":
    main()
'''
    )

    (project_dir / "utils.py").write_text(
        '''
"""Utility functions."""

def add(a, b):
    """Add two numbers."""
    return a + b

def multiply(a, b):
    """Multiply two numbers."""
    return a * b

class Calculator:
    """Simple calculator."""

    def calculate(self, operation, a, b):
        """Perform calculation."""
        if operation == "add":
            return self.add(a, b)
        elif operation == "multiply":
            return self.multiply(a, b)
        else:
            raise ValueError("Unknown operation")

    def add(self, a, b):
        return a + b

    def multiply(self, a, b):
        return a * b
'''
    )

    # Create test file
    (project_dir / "test_utils.py").write_text(
        '''
"""Tests for utils module."""

import pytest
from utils import add, multiply, Calculator

def test_add():
    assert add(2, 3) == 5

def test_multiply():
    assert multiply(2, 3) == 6

def test_calculator():
    calc = Calculator()
    assert calc.calculate("add", 2, 3) == 5
    assert calc.calculate("multiply", 2, 3) == 6
'''
    )

    # Create package structure
    package_dir = project_dir / "mypackage"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text('"""My package."""')
    (package_dir / "module.py").write_text(
        '''
"""Package module."""

from typing import List

def process_items(items: List[str]) -> List[str]:
    """Process list of items."""
    return [item.upper() for item in items]
'''
    )

    # Create configuration files
    (project_dir / "pyproject.toml").write_text(
        """
[build-system]
requires = ["setuptools", "wheel"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.black]
line-length = 88
"""
    )

    (project_dir / "requirements.txt").write_text(
        """
pytest>=7.0
black>=23.0
"""
    )

    return project_dir


@pytest.fixture
def mock_config() -> dict:
    """Mock configuration for tests."""
    return {
        "model": "test-model",
        "temperature": 0.1,
        "max_tokens": 1000,
        "max_context_files": 5,
        "output_format": "text",
        "verbose": False,
        "permissions": {
            "allow_file_read": True,
            "allow_file_write": True,
            "allow_shell_exec": False,
            "allow_git_ops": True,
        },
    }


@pytest.fixture
def mock_ollama_client():
    """Mock Ollama API client."""
    client = Mock(spec=OllamaAPIClient)
    client.check_health = AsyncMock(return_value=True)
    client.list_models = AsyncMock(
        return_value=[{"name": "test-model", "size": 1000000}]
    )

    async def mock_stream_chat(request):
        """Mock streaming chat response."""
        from ocode_python.core.api_client import StreamChunk

        chunks = [
            StreamChunk(content="Hello, "),
            StreamChunk(content="this is "),
            StreamChunk(content="a test response."),
            StreamChunk(done=True),
        ]

        for chunk in chunks:
            yield chunk

    client.stream_chat = mock_stream_chat
    return client


@pytest.fixture
def config_manager(temp_dir: Path, mock_config: dict):
    """Create a test configuration manager."""
    config_file = temp_dir / "test_config.json"
    import json

    with open(config_file, "w") as f:
        json.dump(mock_config, f)

    manager = ConfigManager(temp_dir)
    manager._config_cache = mock_config
    return manager


@pytest.fixture
def auth_manager(temp_dir: Path):
    """Create a test authentication manager."""
    return AuthenticationManager(temp_dir)


@pytest.fixture
def permission_manager():
    """Create a test permission manager."""
    return PermissionManager()


@pytest.fixture
def tool_registry():
    """Create a test tool registry."""
    registry = ToolRegistry()
    registry.register_core_tools()
    return registry


@pytest.fixture
def context_manager(mock_project_dir: Path):
    """Create a test context manager."""
    return ContextManager(mock_project_dir)


@pytest.fixture
def ocode_engine(mock_project_dir: Path, mock_ollama_client, mock_config: dict):
    """Create a test OCode engine."""
    engine = OCodeEngine(
        model="test-model",
        output_format="text",
        verbose=False,
        root_path=mock_project_dir,
    )

    # Replace API client with mock
    engine.api_client = mock_ollama_client
    engine.config._config_cache = mock_config

    return engine


@pytest.fixture
def sample_code():
    """Sample code for testing."""
    return {
        "python": '''
def fibonacci(n):
    """Calculate fibonacci number."""
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

class MathUtils:
    @staticmethod
    def factorial(n):
        if n <= 1:
            return 1
        return n * MathUtils.factorial(n-1)
''',
        "javascript": """
function fibonacci(n) {
    if (n <= 1) return n;
    return fibonacci(n-1) + fibonacci(n-2);
}

class MathUtils {
    static factorial(n) {
        if (n <= 1) return 1;
        return n * MathUtils.factorial(n-1);
    }
}
""",
        "invalid_python": """
def broken_function(
    # Missing closing parenthesis and colon
    return "This is broken"
""",
    }


@pytest.fixture
def mock_git_repo(mock_project_dir: Path):
    """Create a mock git repository."""
    import subprocess

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=mock_project_dir, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=mock_project_dir,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=mock_project_dir, check=True
    )
    subprocess.run(["git", "add", "."], cwd=mock_project_dir, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"], cwd=mock_project_dir, check=True
    )

    return mock_project_dir


@pytest.fixture
def mock_environment():
    """Mock environment variables for tests."""
    old_env = os.environ.copy()

    test_env = {
        "OCODE_MODEL": "test-model",
        "OLLAMA_HOST": "http://localhost:11434",
        "OCODE_VERBOSE": "false",
        "OCODE_TEST_MODE": "true",
    }

    os.environ.update(test_env)

    yield test_env

    # Restore original environment
    os.environ.clear()
    os.environ.update(old_env)


@pytest.fixture
def captured_output():
    """Capture stdout/stderr for CLI testing."""
    import io
    import sys
    from contextlib import redirect_stderr, redirect_stdout

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    class OutputCapture:
        def __enter__(self):
            self.stdout_redirect = redirect_stdout(stdout_capture)
            self.stderr_redirect = redirect_stderr(stderr_capture)
            self.stdout_redirect.__enter__()
            self.stderr_redirect.__enter__()
            return self

        def __exit__(self, *args):
            self.stderr_redirect.__exit__(*args)
            self.stdout_redirect.__exit__(*args)

        @property
        def stdout(self):
            return stdout_capture.getvalue()

        @property
        def stderr(self):
            return stderr_capture.getvalue()

    return OutputCapture()


# Async test helpers


async def async_test_helper(coro):
    """Helper for running async code in tests."""
    return await coro


# Skip markers for optional dependencies
pytest.mark.requires_git = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="Git not available",
)

pytest.mark.requires_docker = pytest.mark.skipif(
    shutil.which("docker") is None,
    reason="Docker not available",
)
