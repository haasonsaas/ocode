"""
Tests for the enhanced stream processor with read-write separation and intelligent batching.
"""

import asyncio
import time
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from ocode_python.core.stream_processor import (
    StreamProcessor,
    ContextBatcher,
    PredictiveEngine,
    Operation,
    OperationResult,
    PipelinePhase
)
from ocode_python.core.context_manager import ContextManager
from ocode_python.tools.base import ToolResult


class TestOperation:
    """Test the Operation dataclass."""
    
    def test_operation_creation(self):
        """Test creating operations with different parameters."""
        op = Operation(
            operation_id="test_op",
            operation_type="read",
            tool_name="file_read",
            arguments={"path": "/test/file.py"},
            priority=1
        )
        
        assert op.operation_id == "test_op"
        assert op.operation_type == "read"
        assert op.tool_name == "file_read"
        assert op.arguments["path"] == "/test/file.py"
        assert op.priority == 1
        assert len(op.dependencies) == 0
    
    def test_operation_with_dependencies(self):
        """Test creating operations with dependencies."""
        op = Operation(
            operation_id="dependent_op",
            operation_type="write",
            tool_name="file_write",
            arguments={"path": "/test/file.py", "content": "test"},
            dependencies={"read_op_1", "read_op_2"}
        )
        
        assert len(op.dependencies) == 2
        assert "read_op_1" in op.dependencies
        assert "read_op_2" in op.dependencies


class TestContextBatcher:
    """Test intelligent context batching."""
    
    @pytest.fixture
    def mock_context_manager(self):
        context_manager = MagicMock(spec=ContextManager)
        context_manager.cache_dir = Path("/tmp/test_cache")
        return context_manager
    
    @pytest.fixture
    def context_batcher(self, mock_context_manager):
        return ContextBatcher(mock_context_manager)
    
    @pytest.fixture
    def sample_files(self, tmp_path):
        """Create sample files of different types."""
        files = []
        
        # Python files
        py_file1 = tmp_path / "module1.py"
        py_file1.write_text("print('hello')\n" * 100)  # ~1300 bytes
        files.append(py_file1)
        
        py_file2 = tmp_path / "module2.py"
        py_file2.write_text("def func():\n    pass\n" * 50)  # ~700 bytes
        files.append(py_file2)
        
        # Config files
        json_file = tmp_path / "config.json"
        json_file.write_text('{"key": "value"}\n' * 20)  # ~280 bytes
        files.append(json_file)
        
        # Documentation
        md_file = tmp_path / "README.md"
        md_file.write_text("# Title\n\nContent here.\n" * 30)  # ~570 bytes
        files.append(md_file)
        
        return files
    
    @pytest.mark.asyncio
    async def test_size_prediction(self, context_batcher, sample_files):
        """Test predicting context size for files."""
        total_size = await context_batcher.predict_context_size(sample_files)
        
        # Should be roughly the sum of actual file sizes
        expected_size = sum(f.stat().st_size for f in sample_files)
        assert abs(total_size - expected_size) < 1000  # Allow some variance
    
    def test_file_grouping(self, context_batcher, sample_files):
        """Test grouping files by characteristics."""
        groups = context_batcher._group_files_by_characteristics(sample_files)
        
        assert 'source_code' in groups
        assert 'config' in groups
        assert 'documentation' in groups
        
        # Check that files are in correct groups
        py_files = [f for f in sample_files if f.suffix == '.py']
        json_files = [f for f in sample_files if f.suffix == '.json']
        md_files = [f for f in sample_files if f.suffix == '.md']
        
        assert len(groups['source_code']) == len(py_files)
        assert len(groups['config']) == len(json_files)
        assert len(groups['documentation']) == len(md_files)
    
    @pytest.mark.asyncio
    async def test_smart_batching(self, context_batcher, sample_files):
        """Test creating smart batches based on size limits."""
        # Use a small batch size to force multiple batches
        batches = await context_batcher.create_smart_batches(
            sample_files, max_batch_size=1000
        )
        
        assert len(batches) >= 1
        
        # Verify batch size constraints
        for batch in batches:
            batch_size = 0
            for file_path in batch:
                batch_size += await context_batcher._estimate_processing_size(file_path)
            
            # Allow some tolerance for the last batch
            if batch != batches[-1]:
                assert batch_size <= 1000 * 1.2  # 20% tolerance
    
    @pytest.mark.asyncio
    async def test_processing_size_estimation(self, context_batcher, sample_files):
        """Test estimation of processing complexity."""
        for file_path in sample_files:
            estimated_size = await context_batcher._estimate_processing_size(file_path)
            actual_size = file_path.stat().st_size
            
            # Python files should have higher estimated size due to complexity
            if file_path.suffix == '.py':
                assert estimated_size >= actual_size * 2  # At least 2x complexity
            else:
                assert estimated_size >= actual_size  # At least base size


class TestStreamProcessor:
    """Test the core stream processing functionality."""
    
    @pytest.fixture
    def mock_context_manager(self):
        context_manager = MagicMock(spec=ContextManager)
        context_manager.cache_dir = Path("/tmp/test_cache")
        return context_manager
    
    @pytest.fixture
    def stream_processor(self, mock_context_manager):
        return StreamProcessor(mock_context_manager)
    
    @pytest.fixture
    def sample_operations(self):
        """Create sample operations for testing."""
        return [
            Operation(
                operation_id="read_1",
                operation_type="read",
                tool_name="file_read",
                arguments={"path": "/test/file1.py"},
                priority=1
            ),
            Operation(
                operation_id="read_2", 
                operation_type="read",
                tool_name="file_read",
                arguments={"path": "/test/file2.py"},
                priority=2
            ),
            Operation(
                operation_id="analyze_1",
                operation_type="analyze",
                tool_name="architect",
                arguments={"path": "/test"},
                priority=1,
                dependencies={"read_1", "read_2"}
            ),
            Operation(
                operation_id="write_1",
                operation_type="write", 
                tool_name="file_write",
                arguments={"path": "/test/output.py", "content": "result"},
                priority=1,
                dependencies={"analyze_1"}
            )
        ]
    
    def test_phase_organization(self, stream_processor, sample_operations):
        """Test organizing operations into executable phases."""
        phases = stream_processor._organize_into_phases(sample_operations)
        
        # Should have read, analyze, and write phases
        phase_names = [phase.phase_name for phase in phases]
        assert "read" in phase_names
        assert "analyze" in phase_names 
        assert "write" in phase_names
        
        # Read phase should come first
        assert phases[0].phase_name == "read"
        assert phases[0].can_parallelize == True
        
        # Write phase should come last and not be parallelizable
        write_phase = next(p for p in phases if p.phase_name == "write")
        assert write_phase.can_parallelize == False
    
    @pytest.mark.asyncio
    async def test_read_operation_caching(self, stream_processor):
        """Test that read operations are properly cached."""
        operation = Operation(
            operation_id="cached_read",
            operation_type="read",
            tool_name="file_read",
            arguments={"path": "/test/file.py"}
        )
        
        # Mock the tool registry execution
        expected_result = ToolResult(True, "file content")
        
        with patch('ocode_python.tools.base.ToolRegistry') as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry.execute_tool = AsyncMock(return_value=expected_result)
            mock_registry_class.return_value = mock_registry
            
            # First execution
            result1 = await stream_processor._execute_read_operation(operation)
            
            # Second execution should use cache
            result2 = await stream_processor._execute_read_operation(operation)
            
            assert result1 == expected_result
            assert result2 == expected_result
            
            # Tool should only be called once due to caching
            assert mock_registry.execute_tool.call_count == 1
    
    @pytest.mark.asyncio
    async def test_write_operation_serialization(self, stream_processor):
        """Test that write operations are properly serialized."""
        operations = [
            Operation(
                operation_id="write_1",
                operation_type="write",
                tool_name="file_write", 
                arguments={"path": "/test/file1.py", "content": "content1"}
            ),
            Operation(
                operation_id="write_2",
                operation_type="write",
                tool_name="file_write",
                arguments={"path": "/test/file2.py", "content": "content2"}
            )
        ]
        
        start_time = time.time()
        
        with patch('ocode_python.tools.base.ToolRegistry') as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry.execute_tool = AsyncMock()
            
            # Add delay to simulate work
            async def delayed_execute(*args, **kwargs):
                await asyncio.sleep(0.1)
                return ToolResult(True, "success")
            
            mock_registry.execute_tool.side_effect = delayed_execute
            mock_registry_class.return_value = mock_registry
            
            results = await stream_processor.batch_writes(operations)
            
            execution_time = time.time() - start_time
            
            # Should take at least 0.2 seconds (2 operations * 0.1s delay each)
            # Plus small delay between writes
            assert execution_time >= 0.2
            assert len(results) == 2
            assert all(result.success for result in results)
    
    @pytest.mark.asyncio 
    async def test_pipeline_processing(self, stream_processor, sample_operations):
        """Test complete pipeline processing with streaming."""
        with patch('ocode_python.tools.base.ToolRegistry') as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry.execute_tool = AsyncMock(return_value=ToolResult(True, "success"))
            mock_registry_class.return_value = mock_registry
            
            results = []
            async for result in stream_processor.process_pipeline(sample_operations):
                results.append(result)
            
            # Should get results for all operations
            assert len(results) == len(sample_operations)
            assert all(result.success for result in results)
            
            # Results should be in execution order (reads first, then analyze, then write)
            read_results = [r for r in results if r.operation_id.startswith("read")]
            analyze_results = [r for r in results if r.operation_id.startswith("analyze")]
            write_results = [r for r in results if r.operation_id.startswith("write")]
            
            assert len(read_results) == 2
            assert len(analyze_results) == 1
            assert len(write_results) == 1
    
    def test_cache_management(self, stream_processor):
        """Test cache statistics and clearing."""
        # Add some mock data to caches
        stream_processor.read_cache["test_key"] = ToolResult(True, "cached")
        stream_processor.operation_results["op1"] = OperationResult(
            operation_id="op1",
            success=True,
            result=ToolResult(True, "result"),
            execution_time=1.0
        )
        
        stats = stream_processor.get_cache_stats()
        assert stats['cache_size'] == 1
        assert stats['total_operations'] == 1
        assert stats['successful_operations'] == 1
        assert stats['failed_operations'] == 0
        
        # Clear cache
        stream_processor.clear_cache()
        assert len(stream_processor.read_cache) == 0


class TestPredictiveEngine:
    """Test predictive pre-execution functionality."""
    
    @pytest.fixture
    def mock_stream_processor(self):
        processor = MagicMock(spec=StreamProcessor)
        processor._execute_single_operation = AsyncMock(return_value=OperationResult(
            operation_id="cache_warm",
            success=True,
            result=ToolResult(True, "warmed"),
            execution_time=0.1
        ))
        return processor
    
    @pytest.fixture
    def predictive_engine(self, mock_stream_processor):
        return PredictiveEngine(mock_stream_processor)
    
    def test_pattern_based_prediction(self, predictive_engine):
        """Test prediction based on tool usage patterns."""
        predictions = predictive_engine.predict_next_tools(
            "file_read",
            {"suggested_tools": ["grep", "architect"]}
        )
        
        # Should include pattern-based predictions for file_read
        assert "file_edit" in predictions or "grep" in predictions or "architect" in predictions
        
        # Should limit to top 3 predictions
        assert len(predictions) <= 3
    
    def test_query_based_prediction(self, predictive_engine):
        """Test prediction based on query analysis."""
        query_analysis = {
            "suggested_tools": ["git_diff", "git_commit", "file_edit"]
        }
        
        predictions = predictive_engine.predict_next_tools("git_status", query_analysis)
        
        # Should include tools from query analysis
        assert any(tool in predictions for tool in ["git_diff", "git_commit", "file_edit"])
    
    def test_execution_history_tracking(self, predictive_engine):
        """Test tracking of execution history."""
        assert len(predictive_engine.execution_history) == 0
        
        predictive_engine.record_execution("file_read")
        predictive_engine.record_execution("file_edit")
        predictive_engine.record_execution("git_status")
        
        assert len(predictive_engine.execution_history) == 3
        assert predictive_engine.execution_history == ["file_read", "file_edit", "git_status"]
    
    def test_history_size_management(self, predictive_engine):
        """Test that execution history is kept at manageable size."""
        # Add more than 100 entries
        for i in range(150):
            predictive_engine.record_execution(f"tool_{i}")
        
        # Should be trimmed to last 50
        assert len(predictive_engine.execution_history) == 50
        assert predictive_engine.execution_history[0] == "tool_100"
        assert predictive_engine.execution_history[-1] == "tool_149"
    
    @pytest.mark.asyncio
    async def test_cache_warming(self, predictive_engine, mock_stream_processor):
        """Test cache warming for predicted operations."""
        predictions = ["file_read", "file_edit"]
        context = {"files": ["/test/file1.py", "/test/file2.py"]}
        
        await predictive_engine.warm_cache_for_predictions(predictions, context)
        
        # Should have started cache warming tasks
        assert len(predictive_engine.cache_warm_tasks) > 0
        
        # Wait for tasks to complete
        await asyncio.sleep(0.1)
        
        # Verify that cache warming was attempted
        assert mock_stream_processor._execute_single_operation.called
    
    @pytest.mark.asyncio
    async def test_cache_warming_cleanup(self, predictive_engine):
        """Test cleanup of cache warming tasks."""
        # Start some mock tasks
        for i in range(3):
            task = asyncio.create_task(asyncio.sleep(1))
            predictive_engine.cache_warm_tasks.add(task)
        
        assert len(predictive_engine.cache_warm_tasks) == 3
        
        # Cleanup should cancel and wait for tasks
        await predictive_engine.cleanup()
        
        assert len(predictive_engine.cache_warm_tasks) == 0


class TestIntegrationScenarios:
    """Integration tests for stream processor scenarios."""
    
    @pytest.mark.asyncio
    async def test_full_pipeline_with_caching(self, tmp_path):
        """Test a complete pipeline with real file operations and caching."""
        # Create test files
        test_file1 = tmp_path / "input1.py"
        test_file1.write_text("print('hello from input1')")
        
        test_file2 = tmp_path / "input2.py" 
        test_file2.write_text("print('hello from input2')")
        
        # Create mock context manager
        context_manager = MagicMock(spec=ContextManager)
        context_manager.cache_dir = tmp_path / "cache"
        
        processor = StreamProcessor(context_manager)
        
        # Create operations
        operations = [
            Operation(
                operation_id="read_1",
                operation_type="read",
                tool_name="file_read", 
                arguments={"path": str(test_file1)}
            ),
            Operation(
                operation_id="read_2",
                operation_type="read",
                tool_name="file_read",
                arguments={"path": str(test_file2)}
            )
        ]
        
        with patch('ocode_python.tools.base.ToolRegistry') as mock_registry_class:
            mock_registry = MagicMock()
            
            def mock_execute_tool(tool_name, **kwargs):
                if tool_name == "file_read":
                    path = kwargs.get("path")
                    if path:
                        content = Path(path).read_text()
                        return ToolResult(True, content)
                return ToolResult(False, "", "Unknown tool")
            
            mock_registry.execute_tool = AsyncMock(side_effect=mock_execute_tool)
            mock_registry_class.return_value = mock_registry
            
            # Process pipeline
            results = []
            async for result in processor.process_pipeline(operations):
                results.append(result)
            
            assert len(results) == 2
            assert all(result.success for result in results)
            assert "hello from input1" in results[0].result.output
            assert "hello from input2" in results[1].result.output
            
            # Verify caching worked
            assert len(processor.read_cache) == 2
    
    @pytest.mark.asyncio
    async def test_error_handling_in_pipeline(self):
        """Test error handling throughout the pipeline."""
        context_manager = MagicMock(spec=ContextManager)
        context_manager.cache_dir = Path("/tmp/test_cache")
        
        processor = StreamProcessor(context_manager)
        
        operations = [
            Operation(
                operation_id="failing_op",
                operation_type="read", 
                tool_name="nonexistent_tool",
                arguments={"param": "value"}
            ),
            Operation(
                operation_id="success_op",
                operation_type="read",
                tool_name="file_read",
                arguments={"path": "/test/file.py"}
            )
        ]
        
        with patch('ocode_python.tools.base.ToolRegistry') as mock_registry_class:
            mock_registry = MagicMock()
            
            def mock_execute_tool(tool_name, **kwargs):
                if tool_name == "nonexistent_tool":
                    return ToolResult(False, "", "Tool not found")
                return ToolResult(True, "success")
            
            mock_registry.execute_tool = AsyncMock(side_effect=mock_execute_tool)
            mock_registry_class.return_value = mock_registry
            
            results = []
            async for result in processor.process_pipeline(operations):
                results.append(result)
            
            assert len(results) == 2
            assert not results[0].success  # First operation should fail
            assert results[1].success     # Second operation should succeed
            
            # Failed operations should not be cached
            assert len(processor.read_cache) == 1  # Only successful operation cached


if __name__ == "__main__":
    pytest.main([__file__])