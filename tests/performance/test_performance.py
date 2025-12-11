"""
Performance tests for OCode components.
"""

import asyncio
import time
from pathlib import Path

import pytest

from ocode_python.core.context_manager import ContextManager
from ocode_python.core.engine import OCodeEngine


@pytest.mark.performance
@pytest.mark.slow
class TestPerformance:
    """Performance tests for OCode."""

    @pytest.mark.asyncio
    async def test_context_building_performance(self, mock_project_dir: Path):
        """Test context building performance."""
        manager = ContextManager(mock_project_dir)

        start_time = time.time()
        context = await manager.build_context("test query", max_files=20)
        end_time = time.time()

        duration = end_time - start_time

        # Should complete within reasonable time
        assert duration < 5.0, f"Context building took {duration:.2f}s, expected < 5s"

        # Should have analyzed files
        assert len(context.files) > 0
        assert len(context.file_info) > 0

    @pytest.mark.asyncio
    async def test_large_file_handling(self, temp_dir: Path):
        """Test handling of larger files."""
        manager = ContextManager(temp_dir)

        # Create a larger Python file
        large_file = temp_dir / "large.py"
        content = "\n".join(
            line
            for i in range(1000)
            for line in [
                f"def function_{i}():",
                f"    '''Function {i}'''",
                f"    return {i}",
                "",
            ]
        )

        large_file.write_text(content)

        start_time = time.time()
        file_info = await manager.analyze_file(large_file)
        end_time = time.time()

        duration = end_time - start_time

        # Should complete within reasonable time
        assert (
            duration < 2.0
        ), f"Large file analysis took {duration:.2f}s, expected < 2s"

        # Should have extracted symbols
        assert file_info is not None
        assert len(file_info.symbols) > 0

    @pytest.mark.asyncio
    async def test_concurrent_file_analysis(self, mock_project_dir: Path):
        """Test concurrent file analysis performance."""
        manager = ContextManager(mock_project_dir)

        # Get all Python files
        python_files = list(mock_project_dir.glob("**/*.py"))

        start_time = time.time()

        # Analyze files concurrently
        tasks = [manager.analyze_file(f) for f in python_files]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()
        duration = end_time - start_time

        # Should be faster than sequential
        valid_results = [
            r for r in results if not isinstance(r, Exception) and r is not None
        ]
        assert len(valid_results) > 0

        # Should complete quickly for small project
        assert (
            duration < 3.0
        ), f"Concurrent analysis took {duration:.2f}s, expected < 3s"

    @pytest.mark.asyncio
    async def test_engine_response_time(self, ocode_engine: OCodeEngine):
        """Test engine response time."""
        query = "What is this project about?"

        start_time = time.time()

        responses = []
        async for chunk in ocode_engine.process(query):
            responses.append(chunk)
            # Break after getting some response to measure time to first byte
            if len(responses) >= 3:
                break

        end_time = time.time()
        duration = end_time - start_time

        # Should start responding quickly
        assert duration < 2.0, f"Engine response took {duration:.2f}s, expected < 2s"
        assert len(responses) > 0

    @pytest.mark.asyncio
    async def test_knowledge_only_latency(self, ocode_engine: OCodeEngine):
        """Ensure knowledge-only responses start quickly."""
        query = "What is the capital of France?"

        start_time = time.time()
        responses = []
        async for chunk in ocode_engine.process(query):
            responses.append(chunk)
            if len(responses) >= 2:  # measure time-to-first-few bytes
                break

        duration = time.time() - start_time

        assert duration < 1.0, f"Knowledge-only response took {duration:.2f}s, expected < 1s"
        assert len(responses) > 0

    @pytest.mark.asyncio
    async def test_memory_usage(self, mock_project_dir: Path):
        """Test memory usage during processing."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        manager = ContextManager(mock_project_dir)

        # Build context multiple times to test memory leaks
        for i in range(5):
            context = await manager.build_context(f"query {i}", max_files=10)
            del context  # Explicit cleanup

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable
        assert (
            memory_increase < 100
        ), f"Memory increased by {memory_increase:.1f}MB, expected < 100MB"

    def test_tool_registry_performance(self):
        """Test tool registry performance."""
        from ocode_python.tools.base import ToolRegistry

        registry = ToolRegistry()

        start_time = time.time()
        registry.register_core_tools()
        end_time = time.time()

        duration = end_time - start_time

        # Should register quickly
        assert duration < 1.0, f"Tool registration took {duration:.2f}s, expected < 1s"
        assert len(registry.tools) > 0

    @pytest.mark.asyncio
    async def test_file_caching_performance(self, temp_dir: Path):
        """Test file caching performance."""
        manager = ContextManager(temp_dir)

        # Create test file
        test_file = temp_dir / "test.py"
        test_file.write_text("def test(): pass")

        # First analysis (no cache)
        start_time = time.time()
        result1 = await manager.analyze_file(test_file)
        first_duration = time.time() - start_time

        # Second analysis (should use cache)
        start_time = time.time()
        result2 = await manager.analyze_file(test_file)
        second_duration = time.time() - start_time

        # Cached version should be faster (or at least not significantly slower)
        assert result1 is not None
        assert result2 is not None
        assert result1.content_hash == result2.content_hash

        # Cache should provide some benefit or at least not hurt performance
        assert second_duration <= first_duration * 2  # Allow some variation
