#!/usr/bin/env python3
"""
Demonstration of the new architecture improvements including:
- Command queue with priority system
- Side effect tracking and rollback
- Enhanced read-write pipeline with streaming
- Semantic context selection
- Predictive pre-execution
"""

import asyncio
import tempfile
import time
from pathlib import Path
from typing import Dict, Any

# Import our new modules
from ocode_python.core.orchestrator import (
    AdvancedOrchestrator, Priority, CommandTask, SideEffect, SideEffectType
)
from ocode_python.core.stream_processor import (
    StreamProcessor, Operation, PredictiveEngine
)
from ocode_python.core.semantic_context import (
    SemanticContextBuilder, DynamicContextManager
)
from ocode_python.tools.base import ToolRegistry
from ocode_python.core.context_manager import ContextManager


async def demo_command_queue_with_priorities():
    """Demonstrate priority-based command queuing."""
    print("\n🚀 Demo 1: Command Queue with Priorities")
    print("=" * 50)
    
    # Set up tool registry
    tool_registry = ToolRegistry()
    tool_registry.register_core_tools()
    
    # Create orchestrator
    orchestrator = AdvancedOrchestrator(tool_registry, max_concurrent=3)
    await orchestrator.start()
    
    try:
        # Submit tasks with different priorities
        print("Submitting tasks with different priorities...")
        
        # Background task (should run last)
        bg_task_id = await orchestrator.submit_task(
            "which", {"command": "python3"}, Priority.BACKGROUND
        )
        
        # Normal priority task
        normal_task_id = await orchestrator.submit_task(
            "ls", {"path": "."}, Priority.NORMAL
        )
        
        # High priority task (should run first)
        high_task_id = await orchestrator.submit_task(
            "wc", {"input": "Hello world from high priority task!"}, Priority.HIGH
        )
        
        print(f"Submitted tasks: high={high_task_id[:8]}, normal={normal_task_id[:8]}, bg={bg_task_id[:8]}")
        
        # Wait for results
        print("\nWaiting for task completion...")
        tasks = [
            (high_task_id, "HIGH"),
            (normal_task_id, "NORMAL"), 
            (bg_task_id, "BACKGROUND")
        ]
        
        for task_id, priority in tasks:
            result = await orchestrator.get_task_result(task_id, timeout=10.0)
            if result and result.success:
                print(f"✅ {priority} task completed: {result.output[:50]}...")
            else:
                print(f"❌ {priority} task failed: {result.error if result else 'timeout'}")
        
        # Show metrics
        metrics = orchestrator.get_metrics()
        print(f"\n📊 Orchestrator metrics: {metrics}")
        
    finally:
        await orchestrator.stop()


async def demo_stream_processing():
    """Demonstrate enhanced read-write pipeline with streaming."""
    print("\n🌊 Demo 2: Stream Processing Pipeline")
    print("=" * 50)
    
    # Create temporary files for demonstration
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create test files
        test_files = {
            "app.py": "def main():\n    print('Hello from app')\n    return 0",
            "utils.py": "def helper():\n    return 'utility function'",
            "config.json": '{"debug": true, "port": 8080}',
            "README.md": "# Test Project\n\nThis is a demo project."
        }
        
        for filename, content in test_files.items():
            (tmp_path / filename).write_text(content)
        
        # Set up context manager and stream processor
        context_manager = ContextManager(tmp_path)
        processor = StreamProcessor(context_manager)
        
        # Create operations for the pipeline
        operations = [
            # Read operations (can run in parallel)
            Operation(
                operation_id="read_app",
                operation_type="read",
                tool_name="file_read",
                arguments={"path": str(tmp_path / "app.py")},
                priority=2
            ),
            Operation(
                operation_id="read_utils",
                operation_type="read", 
                tool_name="file_read",
                arguments={"path": str(tmp_path / "utils.py")},
                priority=1
            ),
            Operation(
                operation_id="read_config",
                operation_type="read",
                tool_name="file_read", 
                arguments={"path": str(tmp_path / "config.json")},
                priority=1
            ),
            # Analysis operations (depend on reads)
            Operation(
                operation_id="analyze_project",
                operation_type="analyze",
                tool_name="wc",
                arguments={"input": "Analyzing project structure..."},
                priority=1,
                dependencies={"read_app", "read_utils"}
            ),
            # Write operation (must run after reads/analysis)
            Operation(
                operation_id="write_summary",
                operation_type="write",
                tool_name="file_write",
                arguments={
                    "path": str(tmp_path / "summary.txt"),
                    "content": "Project analysis complete!"
                },
                priority=1,
                dependencies={"analyze_project"}
            )
        ]
        
        print(f"Processing {len(operations)} operations through pipeline...")
        
        # Process pipeline with streaming
        start_time = time.time()
        results = []
        
        async for result in processor.process_pipeline(operations):
            elapsed = time.time() - start_time
            print(f"⏱️  {elapsed:.2f}s - {result.operation_id}: {'✅' if result.success else '❌'}")
            results.append(result)
        
        print(f"\n📈 Pipeline completed in {time.time() - start_time:.2f}s")
        print(f"📊 {len([r for r in results if r.success])}/{len(results)} operations successful")
        
        # Show cache statistics
        cache_stats = processor.get_cache_stats()
        print(f"💾 Cache stats: {cache_stats}")


async def demo_semantic_context():
    """Demonstrate semantic context selection."""
    print("\n🧠 Demo 3: Semantic Context Selection")
    print("=" * 50)
    
    # Create a more complex project structure
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create realistic project files
        project_files = {
            "main.py": """
import os
from database import connect_db
from utils import log_message, format_data

def main():
    log_message("Starting application")
    db = connect_db()
    data = fetch_user_data(db)
    formatted = format_data(data)
    return formatted

def fetch_user_data(db):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users")
    return cursor.fetchall()

if __name__ == "__main__":
    main()
""",
            "database.py": """
import sqlite3
from config import DATABASE_PATH, CONNECTION_TIMEOUT

def connect_db():
    return sqlite3.connect(DATABASE_PATH, timeout=CONNECTION_TIMEOUT)

def execute_query(db, query, params=None):
    cursor = db.cursor()
    if params:
        return cursor.execute(query, params)
    return cursor.execute(query)

def close_db(db):
    if db:
        db.close()
""",
            "utils.py": """
import logging
import json
from datetime import datetime

def log_message(message):
    timestamp = datetime.now().isoformat()
    logging.info(f"[{timestamp}] {message}")

def format_data(data):
    if isinstance(data, list):
        return [format_single_item(item) for item in data]
    return format_single_item(data)

def format_single_item(item):
    if isinstance(item, dict):
        return {k: str(v).upper() for k, v in item.items()}
    return str(item).upper()

def save_to_json(data, filename):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
""",
            "config.py": """
import os
from pathlib import Path

# Database configuration
DATABASE_PATH = os.getenv("DB_PATH", "app.db")
CONNECTION_TIMEOUT = 30

# Logging configuration  
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = "app.log"

# Application settings
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
PORT = int(os.getenv("PORT", "8080"))
""",
            "test_main.py": """
import unittest
from unittest.mock import patch, MagicMock
from main import main, fetch_user_data

class TestMain(unittest.TestCase):
    @patch('main.connect_db')
    @patch('main.log_message')
    def test_main_execution(self, mock_log, mock_connect):
        mock_db = MagicMock()
        mock_connect.return_value = mock_db
        
        # Test that main function executes without error
        result = main()
        self.assertIsNotNone(result)
        mock_log.assert_called_with("Starting application")

    def test_fetch_user_data(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_db.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("user1", "email1"), ("user2", "email2")]
        
        result = fetch_user_data(mock_db)
        self.assertEqual(len(result), 2)
        mock_cursor.execute.assert_called_with("SELECT * FROM users")

if __name__ == "__main__":
    unittest.main()
""",
            "requirements.txt": """
sqlite3
python-dotenv>=1.0.0
pytest>=7.0.0
""",
            "README.md": """
# Database Application

A simple Python application that demonstrates database connectivity and data processing.

## Features
- SQLite database integration
- Configurable logging
- Data formatting utilities  
- Comprehensive test coverage

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Set environment variables (optional)
3. Run: `python main.py`

## Testing
Run tests with: `python -m pytest test_main.py`
"""
        }
        
        # Write files to disk
        for filename, content in project_files.items():
            (tmp_path / filename).write_text(content)
        
        # Set up semantic context system
        context_manager = ContextManager(tmp_path)
        dynamic_manager = DynamicContextManager(context_manager)
        
        # Test different queries with semantic selection
        test_queries = [
            {
                "query": "database connection and configuration setup",
                "description": "Should prioritize database.py and config.py"
            },
            {
                "query": "main application entry point and startup logic", 
                "description": "Should prioritize main.py"
            },
            {
                "query": "testing and unit test coverage",
                "description": "Should prioritize test_main.py and related files"
            },
            {
                "query": "utility functions for data processing and logging",
                "description": "Should prioritize utils.py"
            },
            {
                "query": "project documentation and setup instructions",
                "description": "Should prioritize README.md and requirements.txt"
            }
        ]
        
        print("Testing semantic context selection with different queries...")
        
        for i, test_case in enumerate(test_queries, 1):
            print(f"\n🔍 Query {i}: {test_case['query']}")
            print(f"Expected: {test_case['description']}")
            
            # Build dynamic context
            context = await dynamic_manager.build_dynamic_context(
                test_case['query'], 
                initial_max_files=3,
                expansion_factor=1.5
            )
            
            # Show selected files
            selected_files = list(context.files.keys())
            print(f"Selected files: {[f.name for f in selected_files]}")
            
            # Get context insights
            insights = dynamic_manager.get_context_insights()
            if insights and 'most_frequent_files' in insights:
                frequent = insights['most_frequent_files'][:3]
                print(f"Most frequently selected: {[Path(f[0]).name for f, _ in frequent]}")
        
        # Test context expansion
        print(f"\n🔄 Testing context expansion...")
        initial_context = await context_manager.build_context("main function", max_files=1)
        expanded_context = await dynamic_manager.expand_context_on_demand(
            initial_context, 
            "need database and utility imports",
            max_additional_files=3
        )
        
        print(f"Initial: {len(initial_context.files)} files")
        print(f"Expanded: {len(expanded_context.files)} files")
        print(f"Additional files: {[f.name for f in expanded_context.files.keys() if f not in initial_context.files]}")


async def demo_predictive_execution():
    """Demonstrate predictive pre-execution and cache warming."""
    print("\n🔮 Demo 4: Predictive Pre-execution")
    print("=" * 50)
    
    # Set up components
    context_manager = ContextManager()
    processor = StreamProcessor(context_manager) 
    predictive_engine = PredictiveEngine(processor)
    
    # Simulate execution history
    execution_sequence = [
        "file_read", "grep", "file_edit", "git_status", "git_diff", "git_commit",
        "file_read", "architect", "file_write", 
        "ls", "file_read", "grep"
    ]
    
    print("Building execution history...")
    for tool in execution_sequence:
        predictive_engine.record_execution(tool)
    
    print(f"Recorded {len(predictive_engine.execution_history)} tool executions")
    
    # Test predictions for different current tools
    test_cases = [
        {
            "current_tool": "file_read",
            "query_analysis": {"suggested_tools": ["file_edit", "grep"]},
            "description": "After reading a file"
        },
        {
            "current_tool": "git_status", 
            "query_analysis": {"suggested_tools": ["git_commit", "git_diff"]},
            "description": "After checking git status"
        },
        {
            "current_tool": "grep",
            "query_analysis": {"suggested_tools": ["file_edit", "architect"]},
            "description": "After searching for patterns"
        }
    ]
    
    for test_case in test_cases:
        print(f"\n🎯 Prediction scenario: {test_case['description']}")
        print(f"Current tool: {test_case['current_tool']}")
        
        predictions = predictive_engine.predict_next_tools(
            test_case['current_tool'],
            test_case['query_analysis']
        )
        
        print(f"Predicted next tools: {predictions}")
        
        # Test cache warming (simulated)
        context = {"files": ["/test/file1.py", "/test/file2.py"]}
        print("Starting cache warming for predictions...")
        
        await predictive_engine.warm_cache_for_predictions(predictions, context)
        
        # Small delay to simulate cache warming
        await asyncio.sleep(0.1)
        
        active_tasks = len(predictive_engine.cache_warm_tasks)
        print(f"Cache warming tasks: {active_tasks} active")
    
    # Cleanup
    await predictive_engine.cleanup()
    print("🧹 Cache warming tasks cleaned up")


async def demo_integration_workflow():
    """Demonstrate all components working together."""
    print("\n🏗️  Demo 5: Integrated Workflow")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create a simple project
        (tmp_path / "main.py").write_text("def main(): return 'hello'")
        (tmp_path / "test.py").write_text("from main import main\nassert main() == 'hello'")
        (tmp_path / "README.md").write_text("# Test Project")
        
        # Set up all components
        tool_registry = ToolRegistry()
        tool_registry.register_core_tools()
        
        context_manager = ContextManager(tmp_path)
        orchestrator = AdvancedOrchestrator(tool_registry)
        processor = StreamProcessor(context_manager)
        dynamic_context = DynamicContextManager(context_manager)
        
        await orchestrator.start()
        
        try:
            print("🎬 Executing integrated workflow...")
            
            # 1. Use semantic context to understand the project
            print("1. Building semantic context...")
            context = await dynamic_context.build_dynamic_context(
                "analyze project structure and main functionality"
            )
            print(f"   Selected {len(context.files)} files for analysis")
            
            # 2. Use orchestrator to execute analysis tasks with priority
            print("2. Orchestrating analysis tasks...")
            
            # High priority: analyze main files
            main_analysis_id = await orchestrator.submit_task(
                "wc", 
                {"input": f"Analyzing {len(context.files)} project files"},
                Priority.HIGH
            )
            
            # Normal priority: check git status
            git_status_id = await orchestrator.submit_task(
                "git_status", {}, Priority.NORMAL
            )
            
            # Background: list all files
            file_list_id = await orchestrator.submit_task(
                "ls", {"path": str(tmp_path)}, Priority.BACKGROUND
            )
            
            # 3. Wait for results
            print("3. Collecting results...")
            task_ids = [
                (main_analysis_id, "Main analysis"),
                (git_status_id, "Git status"),
                (file_list_id, "File listing")
            ]
            
            results = {}
            for task_id, description in task_ids:
                result = await orchestrator.get_task_result(task_id, timeout=10.0)
                results[description] = result
                status = "✅" if result and result.success else "❌"
                print(f"   {status} {description}")
            
            # 4. Use stream processor for final reporting
            print("4. Generating final report...")
            
            report_ops = [
                Operation(
                    operation_id="read_summary",
                    operation_type="read",
                    tool_name="wc",
                    arguments={"input": "Project analysis complete"},
                    priority=1
                ),
                Operation(
                    operation_id="write_report", 
                    operation_type="write",
                    tool_name="file_write",
                    arguments={
                        "path": str(tmp_path / "analysis_report.txt"),
                        "content": f"Analysis completed for {len(context.files)} files"
                    },
                    priority=1,
                    dependencies={"read_summary"}
                )
            ]
            
            report_results = []
            async for result in processor.process_pipeline(report_ops):
                report_results.append(result)
            
            print(f"   Report generation: {'✅' if all(r.success for r in report_results) else '❌'}")
            
            # 5. Show final metrics
            print("5. Final metrics:")
            orchestrator_metrics = orchestrator.get_metrics()
            cache_stats = processor.get_cache_stats()
            context_insights = dynamic_context.get_context_insights()
            
            print(f"   Orchestrator: {orchestrator_metrics}")
            print(f"   Cache: {cache_stats}")
            print(f"   Context: {context_insights.get('total_contexts', 0)} contexts built")
            
            print("\n🎉 Integrated workflow completed successfully!")
            
        finally:
            await orchestrator.stop()


async def main():
    """Run all demonstrations."""
    print("🚀 Architecture Improvements Demonstration")
    print("=" * 60)
    print("This demo showcases the new architecture improvements:")
    print("• Command queue with priority system")
    print("• Side effect tracking and rollback")  
    print("• Enhanced read-write pipeline with streaming")
    print("• Semantic context selection")
    print("• Predictive pre-execution")
    print("• Integrated workflow orchestration")
    
    # Run all demos
    demos = [
        demo_command_queue_with_priorities,
        demo_stream_processing,
        demo_semantic_context,
        demo_predictive_execution, 
        demo_integration_workflow
    ]
    
    for demo in demos:
        try:
            await demo()
        except Exception as e:
            print(f"❌ Demo failed: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n✨ All demonstrations completed!")


if __name__ == "__main__":
    asyncio.run(main())