"""
Demonstration of enhanced shell command tools with process management.

This example shows the improvements in the enhanced shell command tool:
- Better process management and cleanup
- Output size limits and truncation
- Resource limits (CPU, memory)
- Enhanced timeout handling
- Migration path from legacy tools
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Imports after path setup  # noqa: E402
from ocode_python.tools.shell_tools_enhanced import (  # noqa: E402
    EnhancedShellCommandTool,
)
from ocode_python.tools.shell_tools_migration import (  # noqa: E402
    MigrationShellCommandTool,
    ShellToolsMigrationHelper,
)


async def demo_basic_features():
    """Demonstrate basic enhanced features."""
    print("=== Basic Enhanced Features Demo ===\n")

    tool = EnhancedShellCommandTool()

    # 1. Simple command with execution time tracking
    print("1. Simple command with execution time tracking:")
    result = await tool.execute(
        command="echo 'Hello from enhanced shell!'", capture_output=True
    )
    print(f"Output: {result.output}")
    print(f"Execution time: {result.metadata['execution_time']:.3f}s\n")

    # 2. Command with environment variables
    print("2. Command with custom environment variables:")
    result = await tool.execute(
        command="echo $DEMO_VAR",
        env_vars={"DEMO_VAR": "Enhanced Shell Tools!"},
        capture_output=True,
    )
    print(f"Output: {result.output}\n")

    # 3. Command with timeout
    print("3. Command with timeout (will timeout):")
    result = await tool.execute(command="sleep 5", timeout=1, capture_output=True)
    print(f"Success: {result.success}")
    print(f"Error: {result.error}\n")


async def demo_output_management():
    """Demonstrate output size management."""
    print("=== Output Management Demo ===\n")

    tool = EnhancedShellCommandTool()

    # Generate large output that will be truncated
    print("Generating large output with truncation:")
    result = await tool.execute(
        command="seq 1 100000",
        capture_output=True,
        max_output_size=0.1,  # 100KB limit
        confirmed=True,
    )

    print(f"Output length: {len(result.output)} characters")
    print(f"Truncated: {'truncated' in result.output.lower()}")
    print("Last few lines:")
    print(result.output.split("\n")[-5:])


async def demo_process_management():
    """Demonstrate improved process management."""
    print("\n=== Process Management Demo ===\n")

    tool = EnhancedShellCommandTool()

    # Command that creates subprocesses
    print("Running command with subprocess cleanup on timeout:")
    result = await tool.execute(
        command="(sleep 10 & echo 'Started background process') && sleep 10",
        timeout=2,
        kill_timeout=1,
        capture_output=True,
        confirmed=True,
    )

    print(f"Success: {result.success}")
    print(f"Output: {result.output}")
    print(f"Error: {result.error}")
    print("Background processes were cleaned up automatically!\n")


async def demo_migration_tool():
    """Demonstrate migration compatibility tool."""
    print("=== Migration Tool Demo ===\n")

    # Use migration tool as drop-in replacement
    tool = MigrationShellCommandTool()

    print("Using MigrationShellCommandTool (drop-in replacement):")
    result = await tool.execute(
        command="echo 'Works with legacy interface!'", capture_output=True
    )
    print(f"Output: {result.output}")
    print(
        f"Tool name: {tool.definition.name}"
    )  # Will be 'shell_command' for compatibility


def demo_migration_helper():
    """Demonstrate migration helper utilities."""
    print("\n=== Migration Helper Demo ===\n")

    # Sample code using legacy tool
    legacy_code = """
from ocode_python.tools.shell_tools import ShellCommandTool

async def run_command():
    tool = ShellCommandTool()
    result = await tool.execute(
        command="ls -la",
        working_dir="/tmp",
        timeout=30,
        capture_output=True
    )
    return result
"""

    # Analyze usage
    print("Analyzing legacy code usage:")
    analysis = ShellToolsMigrationHelper.analyze_usage(legacy_code)
    print(f"Uses ShellCommandTool: {analysis['uses_shell_command_tool']}")
    print(f"Uses timeout: {analysis['uses_timeout']}")
    print(f"Uses working_dir: {analysis['uses_working_dir']}")
    print(f"Migration complexity: {analysis['migration_complexity']}")
    print("\nSuggestions:")
    for suggestion in analysis["suggestions"]:
        print(f"  - {suggestion}")

    # Generate migrated code
    print("\nMigrated code:")
    migrated = ShellToolsMigrationHelper.generate_migration_code(legacy_code)
    print(migrated)


async def main():
    """Run all demonstrations."""
    print("Enhanced Shell Command Tools Demonstration")
    print("=" * 50)

    await demo_basic_features()
    await demo_output_management()
    await demo_process_management()
    await demo_migration_tool()
    demo_migration_helper()

    print("\n" + "=" * 50)
    print("Demo completed!")
    print("\nKey improvements in enhanced shell tools:")
    print("- Robust process management with guaranteed cleanup")
    print("- Output size limits to prevent memory issues")
    print("- Resource limits (CPU, memory) on Unix systems")
    print("- Better timeout handling with kill escalation")
    print("- Smooth migration path from legacy tools")


if __name__ == "__main__":
    asyncio.run(main())
