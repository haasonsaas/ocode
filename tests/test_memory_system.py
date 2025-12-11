#!/usr/bin/env python3
"""
Comprehensive tests for OCode Memory System.

This file tests both the memory tools directly and the intelligent
LLM-driven memory system with function calling.
"""

import asyncio
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from ocode_python.core.engine import OCodeEngine

# Import OCode components
from ocode_python.tools.memory_tools import MemoryReadTool, MemoryWriteTool


class TestMemoryTools(unittest.TestCase):
    """Test memory tools directly without LLM."""

    def setUp(self):
        """Set up test environment with temporary directory."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        # Create .ocode directory structure
        self.memory_dir = Path(self.test_dir) / ".ocode" / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def _run_memory_write_persistent(self):
        """Async body for persistent memory write test."""
        tool = MemoryWriteTool()

        result = await tool.execute(
            memory_type="persistent",
            operation="set",
            key="test_key",
            value="test_value",
            category="test_category",
        )

        self.assertTrue(result.success)
        self.assertIn("Set key 'test_key'", result.output)

        # Verify file was created
        persistent_file = self.memory_dir / "persistent.json"
        self.assertTrue(persistent_file.exists())

        # Verify content
        with open(persistent_file) as f:
            data = json.load(f)

        self.assertIn("test_key", data)
        self.assertEqual(data["test_key"]["value"], "test_value")
        self.assertEqual(data["test_key"]["category"], "test_category")

    async def _run_memory_read_persistent(self):
        """Async body for persistent memory read test."""
        # First write some data
        write_tool = MemoryWriteTool()
        await write_tool.execute(
            memory_type="persistent",
            operation="set",
            key="read_test",
            value={"name": "John", "age": 30},
            category="users",
        )

        # Then read it back
        read_tool = MemoryReadTool()
        result = await read_tool.execute(memory_type="persistent", key="read_test")

        self.assertTrue(result.success)
        self.assertIn("read_test", result.output)
        self.assertIn("John", result.output)

    async def _run_memory_operations(self):
        """Async body for various memory operations."""
        tool = MemoryWriteTool()

        # Test set operation
        result = await tool.execute(
            memory_type="persistent", operation="set", key="counter", value=1
        )
        self.assertTrue(result.success)

        # Test update operation
        result = await tool.execute(
            memory_type="persistent", operation="update", key="counter", value=2
        )
        self.assertTrue(result.success)

        # Test append operation
        result = await tool.execute(
            memory_type="persistent",
            operation="append",
            key="items",
            value="first_item",
        )
        self.assertTrue(result.success)

        result = await tool.execute(
            memory_type="persistent",
            operation="append",
            key="items",
            value="second_item",
        )
        self.assertTrue(result.success)

        # Verify append worked
        read_tool = MemoryReadTool()
        result = await read_tool.execute(memory_type="persistent", key="items")
        self.assertTrue(result.success)
        self.assertIn("2 entries", result.output)

    async def _run_memory_types(self):
        """Async body for different memory types."""
        tool = MemoryWriteTool()

        # Test session memory
        result = await tool.execute(
            memory_type="session",
            operation="set",
            key="session_data",
            value="session_value",
        )
        self.assertTrue(result.success)

        # Test context memory
        result = await tool.execute(
            memory_type="context",
            operation="set",
            key="context_data",
            value="context_value",
        )
        self.assertTrue(result.success)

        # Verify files were created
        self.assertTrue((self.memory_dir / "context.json").exists())
        self.assertTrue(len(list((self.memory_dir / "sessions").glob("*.json"))) > 0)

    def test_memory_write_persistent(self):
        """Test writing to persistent memory."""
        asyncio.run(self._run_memory_write_persistent())

    def test_memory_read_persistent(self):
        """Test reading from persistent memory."""
        asyncio.run(self._run_memory_read_persistent())

    def test_memory_operations(self):
        """Test various memory operations."""
        asyncio.run(self._run_memory_operations())

    def test_memory_types(self):
        """Test different memory types."""
        asyncio.run(self._run_memory_types())


class TestIntelligentMemorySystem(unittest.TestCase):
    """Test the intelligent LLM-driven memory system."""

    @classmethod
    def setUpClass(cls):
        """Check if function calling model is available."""
        cls.model_name = "MFDoom/deepseek-coder-v2-tool-calling:latest"
        cls.skip_llm_tests = False

        try:
            # Try to create client and check model availability
            import subprocess

            result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
            if cls.model_name not in result.stdout:
                cls.skip_llm_tests = True
                print(f"Skipping LLM tests: {cls.model_name} not available")
        except Exception as e:
            cls.skip_llm_tests = True
            print(f"Skipping LLM tests: {e}")

    def setUp(self):
        """Set up test environment."""
        if self.skip_llm_tests:
            self.skipTest("Function calling model not available")

        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        self.engine = OCodeEngine(
            model=self.model_name, verbose=False  # Reduce noise in tests
        )

    def tearDown(self):
        """Clean up test environment."""
        if hasattr(self, "original_cwd"):
            os.chdir(self.original_cwd)
            shutil.rmtree(self.test_dir, ignore_errors=True)

    async def _run_llm_memory_store(self):
        """Async body for LLM-driven memory storage."""
        responses = []
        async for chunk in self.engine.process("Remember my favorite color is purple"):
            responses.append(chunk)

        full_response = "".join(responses)

        # Should contain tool execution
        self.assertIn("memory_write", full_response)
        self.assertIn("completed successfully", full_response)

    async def _run_llm_memory_retrieve(self):
        """Async body for LLM-driven memory retrieval."""
        # First store something
        async for chunk in self.engine.process("Remember my name is Alice"):
            pass  # Just let it execute

        # Then try to retrieve
        responses = []
        async for chunk in self.engine.process("What's my name?"):
            responses.append(chunk)

        full_response = "".join(responses)

        # Should use memory_read tool
        self.assertIn("memory_read", full_response)

    async def _run_llm_query_analysis(self):
        """Async body for LLM query analysis system."""
        # Test with a memory query
        analysis = await self.engine._llm_should_use_tools(
            "Remember my email is test@example.com"
        )

        self.assertTrue(analysis["should_use_tools"])
        self.assertIn("memory_write", analysis["suggested_tools"])
        self.assertEqual(analysis["context_complexity"], "simple")

        # Test with a complex query
        analysis = await self.engine._llm_should_use_tools(
            "Analyze the entire codebase architecture"
        )

        self.assertTrue(analysis["should_use_tools"])
        self.assertEqual(analysis["context_complexity"], "full")

    def test_llm_memory_store(self):
        """Test LLM-driven memory storage."""
        if not self.skip_llm_tests:
            asyncio.run(self._run_llm_memory_store())

    def test_llm_memory_retrieve(self):
        """Test LLM-driven memory retrieval."""
        if not self.skip_llm_tests:
            asyncio.run(self._run_llm_memory_retrieve())

    def test_llm_query_analysis(self):
        """Test LLM query analysis system."""
        if not self.skip_llm_tests:
            asyncio.run(self._run_llm_query_analysis())


class TestMemoryExamples(unittest.TestCase):
    """Practical examples of memory system usage."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        # Create .ocode directory structure
        self.memory_dir = Path(self.test_dir) / ".ocode" / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def _run_user_preferences_example(self):
        """Async body: store and retrieve user preferences."""
        write_tool = MemoryWriteTool()
        read_tool = MemoryReadTool()

        # Store user preferences
        preferences = {
            "theme": "dark",
            "language": "python",
            "editor": "vscode",
            "font_size": 14,
        }

        result = await write_tool.execute(
            memory_type="persistent",
            operation="set",
            key="user_preferences",
            value=preferences,
            category="settings",
        )
        self.assertTrue(result.success)

        # Retrieve preferences
        result = await read_tool.execute(
            memory_type="persistent", key="user_preferences"
        )
        self.assertTrue(result.success)
        self.assertIn("dark", result.output)
        self.assertIn("python", result.output)

    async def _run_project_history_example(self):
        """Async body: maintain project history."""
        write_tool = MemoryWriteTool()
        read_tool = MemoryReadTool()

        # Add projects to history
        projects = [
            {"name": "web-app", "language": "javascript", "status": "completed"},
            {"name": "data-analysis", "language": "python", "status": "in-progress"},
            {"name": "mobile-app", "language": "dart", "status": "planning"},
        ]

        for project in projects:
            result = await write_tool.execute(
                memory_type="persistent",
                operation="append",
                key="project_history",
                value=project,
                category="projects",
            )
            self.assertTrue(result.success)

        # Read project history
        result = await read_tool.execute(
            memory_type="persistent", key="project_history"
        )
        self.assertTrue(result.success)
        self.assertIn("3 entries", result.output)

    async def _run_api_keys_example(self):
        """Async body: store API keys (be careful with real keys!)."""
        write_tool = MemoryWriteTool()
        read_tool = MemoryReadTool()

        # Store API keys
        api_keys = {
            "github": "ghp_test_key_123",
            "openai": "sk-test_key_456",
            "anthropic": "ant-test_key_789",
        }

        result = await write_tool.execute(
            memory_type="persistent",
            operation="set",
            key="api_keys",
            value=api_keys,
            category="credentials",
        )
        self.assertTrue(result.success)

        # Retrieve specific category
        result = await read_tool.execute(
            memory_type="persistent", category="credentials"
        )
        self.assertTrue(result.success)
        self.assertIn("api_keys", result.output)

    async def _run_session_notes_example(self):
        """Async body: session-specific notes."""
        write_tool = MemoryWriteTool()
        read_tool = MemoryReadTool()

        # Store session notes
        notes = [
            "Working on user authentication",
            "Found bug in login validation",
            "Need to update password requirements",
        ]

        for note in notes:
            result = await write_tool.execute(
                memory_type="session",
                operation="append",
                key="session_notes",
                value=note,
                category="notes",
            )
            self.assertTrue(result.success)

        # Read session notes
        result = await read_tool.execute(memory_type="session", key="session_notes")
        self.assertTrue(result.success)
        self.assertIn("3 entries", result.output)

    def test_user_preferences_example(self):
        """Example: Store and retrieve user preferences."""
        asyncio.run(self._run_user_preferences_example())

    def test_project_history_example(self):
        """Example: Maintain project history."""
        asyncio.run(self._run_project_history_example())

    def test_api_keys_example(self):
        """Example: Store API keys (be careful with real keys!)."""
        asyncio.run(self._run_api_keys_example())

    def test_session_notes_example(self):
        """Example: Session-specific notes."""
        asyncio.run(self._run_session_notes_example())


def run_memory_tests():
    """Run all memory system tests."""
    print("=" * 60)
    print("OCode Memory System Tests")
    print("=" * 60)

    # Create test loader
    loader = unittest.TestLoader()

    # Create test suite
    suite = unittest.TestSuite()

    # Add direct tool tests
    suite.addTests(loader.loadTestsFromTestCase(TestMemoryTools))
    suite.addTests(loader.loadTestsFromTestCase(TestMemoryExamples))

    # Add LLM tests if model is available
    suite.addTests(loader.loadTestsFromTestCase(TestIntelligentMemorySystem))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("✅ All memory system tests passed!")
    else:
        print("❌ Some tests failed:")
        for failure in result.failures + result.errors:
            print(f"  - {failure[0]}")
    print("=" * 60)

    return result.wasSuccessful()


if __name__ == "__main__":
    """Run tests when executed directly."""
    success = run_memory_tests()
    exit(0 if success else 1)
