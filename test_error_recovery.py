#!/usr/bin/env python3
"""
Test script for the Error Recovery System.

This script demonstrates and verifies the functionality of the new 
Self-Improving Agent Architecture's error recovery capabilities.
"""

import asyncio
import logging
import tempfile
from pathlib import Path

# Configure logging to see the recovery process
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from ocode_python.core.error_recovery import (
    DebuggerPersona, 
    ErrorRecoveryModule, 
    RecoveryStrategyType,
    FailureContext
)
from ocode_python.core.orchestrator import AdvancedOrchestrator
from ocode_python.core.api_client import OllamaAPIClient
from ocode_python.prompts.prompt_composer import PromptComposer
from ocode_python.tools.base import Tool, ToolDefinition, ToolResult, ToolRegistry
from ocode_python.core.orchestrator import CommandTask
from ocode_python.tools.bash_tool import BashTool
from ocode_python.tools.file_tools import FileReadTool


class FailingTool(Tool):
    """A tool that always fails - for testing error recovery."""
    
    def __init__(self, fail_reason: str = "Simulated failure"):
        self.fail_reason = fail_reason
        self.call_count = 0
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="failing_tool",
            description="A tool that always fails for testing",
            parameters=[]
        )
    
    async def execute(self, **kwargs) -> ToolResult:
        self.call_count += 1
        return ToolResult(
            success=False,
            output="",
            error=f"Simulated failure #{self.call_count}: {self.fail_reason}",
            metadata={"error_type": "SIMULATION_ERROR", "call_count": self.call_count}
        )


class FixableTool(Tool):
    """A tool that fails initially but can be 'fixed' by adjusting parameters."""
    
    def __init__(self):
        self.call_count = 0
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="fixable_tool",
            description="A tool that can be fixed with the right parameters",
            parameters=[]
        )
    
    async def execute(self, **kwargs) -> ToolResult:
        self.call_count += 1
        
        # Fail unless magic parameter is provided
        if kwargs.get("magic_fix") == "please_work":
            return ToolResult(
                success=True,
                output=f"Success! Fixed on attempt #{self.call_count}",
                metadata={"call_count": self.call_count, "fixed": True}
            )
        else:
            return ToolResult(
                success=False,
                output="",
                error=f"Missing magic parameter (attempt #{self.call_count})",
                metadata={
                    "error_type": "PARAMETER_ERROR", 
                    "call_count": self.call_count,
                    "hint": "Try adding magic_fix=please_work"
                }
            )


async def test_basic_error_recovery():
    """Test basic error recovery functionality."""
    print("\n=== Testing Basic Error Recovery ===")
    
    # Setup
    api_client = OllamaAPIClient()
    prompt_composer = PromptComposer()
    
    # Create debugger persona and recovery module
    debugger = DebuggerPersona(api_client, prompt_composer)
    recovery_module = ErrorRecoveryModule(debugger, max_recovery_attempts=2)
    
    # Create tool registry with our test tools
    tool_registry = ToolRegistry()
    failing_tool = FailingTool("Permission denied: /root/secret.txt")
    fixable_tool = FixableTool()
    
    tool_registry.register_tool(failing_tool)
    tool_registry.register_tool(fixable_tool)
    tool_registry.register_tool(BashTool())
    tool_registry.register_tool(FileReadTool())
    
    # Create orchestrator with error recovery
    orchestrator = AdvancedOrchestrator(
        tool_registry=tool_registry,
        error_recovery_module=recovery_module
    )
    
    # Set a realistic goal
    orchestrator.set_current_goal("Read configuration file to understand system setup")
    
    # Test 1: Recovery with always-failing tool
    print("\n--- Test 1: Always-failing tool ---")
    try:
        result = await orchestrator.execute_tool_with_context(
            "failing_tool",
            {}
        )
        print(f"Result: {result.success}")
        print(f"Output: {result.output}")
        print(f"Error: {result.error}")
        
        # Check recovery stats
        stats = recovery_module.get_recovery_stats()
        print(f"Recovery attempts: {stats['attempts']}")
        print(f"Recovery successes: {stats['successes']}")
        print(f"Success rate: {stats['success_rate']:.2%}")
        
    except Exception as e:
        print(f"Error during test: {e}")
    
    # Test 2: Recovery with fixable tool
    print("\n--- Test 2: Fixable tool (should recover) ---")
    try:
        result = await orchestrator.execute_tool_with_context(
            "fixable_tool",
            {}
        )
        print(f"Result: {result.success}")
        print(f"Output: {result.output}")
        print(f"Error: {result.error}")
        
        # Check recovery stats
        stats = recovery_module.get_recovery_stats()
        print(f"Recovery attempts: {stats['attempts']}")
        print(f"Recovery successes: {stats['successes']}")
        print(f"Success rate: {stats['success_rate']:.2%}")
        
    except Exception as e:
        print(f"Error during test: {e}")


async def test_strategy_analysis():
    """Test the debugger persona's strategy analysis."""
    print("\n=== Testing Strategy Analysis ===")
    
    # Setup
    api_client = OllamaAPIClient()
    prompt_composer = PromptComposer()
    debugger = DebuggerPersona(api_client, prompt_composer)
    
    # Create a realistic failure context  
    from ocode_python.core.orchestrator import Priority
    failed_command = CommandTask(
        task_id="test-123",
        tool_name="file_read",
        arguments={"file_path": "/etc/passwd"},
        priority=Priority.NORMAL
    )
    
    tool_result = ToolResult(
        success=False,
        output="",
        error="Permission denied: Cannot read /etc/passwd",
        metadata={
            "error_type": "PERMISSION_ERROR",
            "path": "/etc/passwd",
            "attempted_user": "normal_user"
        }
    )
    
    failure_context = FailureContext(
        original_goal="Analyze system users for security audit",
        failed_tool="file_read",
        failed_command=failed_command,
        tool_result=tool_result,
        execution_context={"working_dir": "/home/user", "retry_count": 2}
    )
    
    try:
        print("Analyzing failure...")
        strategies = await debugger.analyze_failure(failure_context)
        
        print(f"\nGenerated {len(strategies)} recovery strategies:")
        for i, strategy in enumerate(strategies, 1):
            print(f"\n{i}. {strategy.strategy_type.value}")
            print(f"   Description: {strategy.description}")
            print(f"   Confidence: {strategy.confidence:.2f}")
            print(f"   Risk: {strategy.risk_level}")
            print(f"   Expected success: {strategy.estimated_success_rate:.2f}")
            if strategy.rationale:
                print(f"   Rationale: {strategy.rationale}")
            if strategy.adjusted_parameters:
                print(f"   Parameter adjustments: {strategy.adjusted_parameters}")
            if strategy.alternative_commands:
                print(f"   Alternative commands: {len(strategy.alternative_commands)}")
    
    except Exception as e:
        print(f"Error during strategy analysis: {e}")
        import traceback
        traceback.print_exc()


async def test_with_real_tools():
    """Test error recovery with real tools that might actually fail."""
    print("\n=== Testing with Real Tools ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Setup
        api_client = OllamaAPIClient()
        prompt_composer = PromptComposer()
        debugger = DebuggerPersona(api_client, prompt_composer)
        recovery_module = ErrorRecoveryModule(debugger)
        
        # Create tool registry
        tool_registry = ToolRegistry()
        tool_registry.register_tool(BashTool())
        tool_registry.register_tool(FileReadTool())
        
        # Create orchestrator
        orchestrator = AdvancedOrchestrator(
            tool_registry=tool_registry,
            error_recovery_module=recovery_module
        )
        
        # Test reading a non-existent file (should trigger recovery)
        orchestrator.set_current_goal("Read project configuration")
        
        try:
            result = await orchestrator.execute_tool_with_context(
                "file_read",
                {"path": str(temp_path / "nonexistent.txt")}
            )
            
            print(f"Reading non-existent file:")
            print(f"Success: {result.success}")
            print(f"Output: {result.output[:200]}...")
            print(f"Error: {result.error}")
            
        except Exception as e:
            print(f"Error: {e}")


async def main():
    """Run all error recovery tests."""
    print("🤖 Testing Error Recovery System")
    print("=" * 50)
    
    try:
        # Check if Ollama is available
        api_client = OllamaAPIClient()
        health = await api_client.check_health()
        
        if not health:
            print("⚠️  Ollama API not available - running limited tests")
            print("   Start Ollama server to test LLM-based recovery strategies")
            return
        
        print("✅ Ollama API available - running full tests")
        
        # Run tests
        await test_strategy_analysis()
        await test_basic_error_recovery()
        await test_with_real_tools()
        
        print("\n🎉 Error recovery system tests completed!")
        print("Check the logs above for detailed recovery behavior.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())