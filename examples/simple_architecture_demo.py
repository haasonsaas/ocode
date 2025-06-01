#!/usr/bin/env python3
"""
Simple demonstration of the key architecture improvements.
"""

import asyncio
import tempfile
from pathlib import Path

from ocode_python.core.context_manager import ContextManager
from ocode_python.core.orchestrator import AdvancedOrchestrator, Priority
from ocode_python.core.stream_processor import Operation, StreamProcessor
from ocode_python.tools.base import ToolRegistry


async def demo_priority_queue():
    """Show priority-based task execution."""
    print("🚀 Priority Queue Demo")
    print("-" * 30)

    tool_registry = ToolRegistry()
    tool_registry.register_core_tools()

    orchestrator = AdvancedOrchestrator(tool_registry)
    await orchestrator.start()

    try:
        # Submit tasks in reverse priority order
        print("Submitting tasks:")

        bg_task = await orchestrator.submit_task(
            "ls", {"path": "."}, Priority.BACKGROUND
        )
        print("  📤 Background: ls")

        normal_task = await orchestrator.submit_task(
            "which", {"command": "python3"}, Priority.NORMAL
        )
        print("  📤 Normal: which python3")

        high_task = await orchestrator.submit_task(
            "ls", {"path": "/usr"}, Priority.HIGH
        )
        print("  📤 High: ls /usr")

        # Collect results in submission order to see priority effect
        tasks = [(bg_task, "BG"), (normal_task, "NORMAL"), (high_task, "HIGH")]

        print("\nResults (should show HIGH first):")
        for task_id, priority in tasks:
            result = await orchestrator.get_task_result(task_id, timeout=5)
            if result and result.success:
                output_preview = result.output[:30].replace("\n", " ")
                print(f"  ✅ {priority}: {output_preview}...")
            else:
                print(f"  ❌ {priority}: Failed")

        metrics = orchestrator.get_metrics()
        print(f"\nMetrics: {metrics['completed_tasks']} tasks completed")

    finally:
        await orchestrator.stop()


async def demo_stream_processing():
    """Show read-write pipeline separation."""
    print("\n🌊 Stream Processing Demo")
    print("-" * 30)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Create test files
        (tmp_path / "file1.txt").write_text("Hello from file 1")
        (tmp_path / "file2.txt").write_text("Hello from file 2")

        context_manager = ContextManager(tmp_path)
        processor = StreamProcessor(context_manager)

        operations = [
            # Read operations (can be parallel)
            Operation(
                operation_id="read1",
                operation_type="read",
                tool_name="file_read",
                arguments={"path": str(tmp_path / "file1.txt")},
                priority=1,
            ),
            Operation(
                operation_id="read2",
                operation_type="read",
                tool_name="file_read",
                arguments={"path": str(tmp_path / "file2.txt")},
                priority=1,
            ),
            # Write operation (sequential after reads)
            Operation(
                operation_id="write_summary",
                operation_type="write",
                tool_name="file_write",
                arguments={
                    "path": str(tmp_path / "summary.txt"),
                    "content": "Files processed successfully",
                },
                priority=1,
                dependencies={"read1", "read2"},
            ),
        ]

        print("Processing pipeline:")
        print("  📖 Read file1.txt")
        print("  📖 Read file2.txt")
        print("  ✏️  Write summary.txt")

        results = []
        async for result in processor.process_pipeline(operations):
            status = "✅" if result.success else "❌"
            print(f"  {status} {result.operation_id}")
            results.append(result)

        success_count = sum(1 for r in results if r.success)
        print(f"\nCompleted: {success_count}/{len(results)} operations")

        # Check if summary file was created
        summary_file = tmp_path / "summary.txt"
        if summary_file.exists():
            print(f"✅ Summary file created: {summary_file.read_text()}")


async def demo_semantic_context():
    """Show semantic file selection."""
    print("\n🧠 Semantic Context Demo")
    print("-" * 30)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Create project files with different content
        files = {
            "main.py": (
                "def main():\n    print('Main application')\n    return start_server()"
            ),
            "server.py": (
                "def start_server():\n    print('Starting web server')\n    "
                "return run_app()"
            ),
            "config.py": "DATABASE_URL = 'sqlite:///app.db'\nDEBUG = True",
            "utils.py": "def helper():\n    return 'utility function'",
            "README.md": "# Project\n\nA web application with database.",
        }

        for filename, content in files.items():
            (tmp_path / filename).write_text(content)

        from ocode_python.core.semantic_context import SemanticContextBuilder

        context_manager = ContextManager(tmp_path)
        semantic_builder = SemanticContextBuilder(context_manager)

        # Test different queries
        queries = [
            ("web server startup", "Should find main.py and server.py"),
            ("database configuration", "Should find config.py"),
            ("project documentation", "Should find README.md"),
        ]

        for query, expected in queries:
            print(f"\n🔍 Query: '{query}'")
            print(f"   Expected: {expected}")

            # Build semantic context
            semantic_files = await semantic_builder.build_semantic_context(
                query, files, max_files=3
            )

            print("   Selected files:")
            for sf in semantic_files:
                print(f"     📄 {sf.path.name} (score: {sf.final_score:.2f})")


async def demo_all_together():
    """Show components working together."""
    print("\n🏗️ Integration Demo")
    print("-" * 30)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Create a simple project
        (tmp_path / "app.py").write_text("print('Hello World')")
        (tmp_path / "test.py").write_text("# Tests for app.py")

        # Set up components
        tool_registry = ToolRegistry()
        tool_registry.register_core_tools()

        orchestrator = AdvancedOrchestrator(tool_registry)

        await orchestrator.start()

        try:
            print("1. 📁 Analyzing project structure...")

            # Use orchestrator with priorities
            high_priority_task = await orchestrator.submit_task(
                "ls", {"path": str(tmp_path)}, Priority.HIGH
            )

            normal_task = await orchestrator.submit_task(
                "file_read", {"path": str(tmp_path / "app.py")}, Priority.NORMAL
            )

            print("2. ⏳ Waiting for analysis...")

            ls_result = await orchestrator.get_task_result(
                high_priority_task, timeout=5
            )
            read_result = await orchestrator.get_task_result(normal_task, timeout=5)

            if ls_result and ls_result.success:
                file_count = len(
                    [line for line in ls_result.output.split("\n") if line.strip()]
                )
                print(f"   📊 Found {file_count} files")

            if read_result and read_result.success:
                content_length = len(read_result.output)
                print(f"   📄 Read app.py ({content_length} chars)")

            print("3. ✅ Integration complete!")

            metrics = orchestrator.get_metrics()
            print(f"   📈 Executed {metrics['completed_tasks']} tasks")

        finally:
            await orchestrator.stop()


async def main():
    """Run all demonstrations."""
    print("🎯 Architecture Improvements - Simple Demo")
    print("=" * 50)

    await demo_priority_queue()
    await demo_stream_processing()
    await demo_semantic_context()
    await demo_all_together()

    print("\n🎉 All demos completed!")
    print("\nKey improvements demonstrated:")
    print("• ⚡ Priority-based task execution")
    print("• 🔀 Read-write pipeline separation")
    print("• 🧠 Semantic context selection")
    print("• 🏗️ Component integration")


if __name__ == "__main__":
    asyncio.run(main())
