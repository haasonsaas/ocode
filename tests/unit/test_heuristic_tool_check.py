"""Test the heuristic tool check functionality."""

import pytest

from ocode_python.core.engine import OCodeEngine


class TestHeuristicToolCheck:
    """Test the heuristic-based tool decision logic."""

    @pytest.fixture
    def engine(self):
        """Create an engine instance for testing."""
        engine = OCodeEngine(verbose=False)
        return engine

    def test_knowledge_queries(self, engine):
        """Test that knowledge queries return False."""
        knowledge_queries = [
            "What is Python?",
            "Explain object-oriented programming",
            "How does async/await work?",
            "Compare REST and GraphQL",
            "What are the differences between TCP and UDP?",
            "Tell me about machine learning",
            "Define recursion",
            "Describe the MVC pattern",
            "What are Python best practices?",
            "Give me tips for debugging",
            "When should I use decorators?",
            "Explain the concept of closures",
            "What is the theory behind sorting algorithms?",
        ]

        for query in knowledge_queries:
            result = engine._heuristic_tool_check(query)
            assert result is False, f"Query '{query}' should be knowledge (False)"

    def test_tool_queries(self, engine):
        """Test that tool-requiring queries return True."""
        tool_queries = [
            "List files in the current directory",
            "Show me the files here",
            "Read the README.md file",
            "Write a new config file",
            "Create a test.py file",
            "Edit the main.py file",
            "Delete old.txt",
            "Find all Python files",
            "Search for TODO in files",
            "Run git status",
            "Commit my changes",
            "Execute ls -la",
            "Download https://example.com/data.json",
            "Remember my email is test@example.com",
            "Analyze the architecture of this project",
            "Show me config.json",
            "grep ERROR in logs",
            "head -n 10 data.csv",
        ]

        for query in tool_queries:
            result = engine._heuristic_tool_check(query)
            assert result is True, f"Query '{query}' should need tools (True)"

    def test_ambiguous_queries(self, engine):
        """Test that ambiguous queries return None."""
        ambiguous_queries = [
            "Show me how to use Python",  # Could be knowledge
            "Get the latest version",  # Unclear what to get
            "Check the status",  # Check what?
            "Look into the problem",  # Vague
        ]

        for query in ambiguous_queries:
            result = engine._heuristic_tool_check(query)
            assert result is None, f"Query '{query}' should be ambiguous (None)"

    def test_context_overrides(self, engine):
        """Test that specific context overrides knowledge patterns."""
        # These look like knowledge queries but mention specific files/projects
        context_queries = [
            "Explain how this project works",
            "What is the purpose of this codebase?",
            "How does authentication work in my project?",
            "Explain the algorithm in utils.py",
            "What is the data structure used in parser.py?",
        ]

        for query in context_queries:
            result = engine._heuristic_tool_check(query)
            assert result is True, f"Query '{query}' should need tools due to context"

    def test_file_path_detection(self, engine):
        """Test that queries with file paths are detected as needing tools."""
        path_queries = [
            "What is in ./src/main.py?",
            "Explain the code in utils/helper.js",
            "Show me config/settings.json",
            "../README.md contains what?",
        ]

        for query in path_queries:
            result = engine._heuristic_tool_check(query)
            assert result is True, f"Query '{query}' should need tools due to file path"

    def test_case_insensitive(self, engine):
        """Test that matching is case-insensitive."""
        pairs = [
            ("WHAT IS PYTHON?", False),
            ("LIST FILES", True),
            ("Git Status", True),
            ("EXPLAIN algorithms", False),
        ]

        for query, expected in pairs:
            result = engine._heuristic_tool_check(query)
            assert result == expected, f"Query '{query}' case handling failed"

    def test_mixed_indicators(self, engine):
        """Test queries with both knowledge and tool indicators."""
        # Knowledge pattern but with tool context
        assert engine._heuristic_tool_check("What is in config.py?") is True

        # Tool pattern but hypothetical
        assert (
            engine._heuristic_tool_check("How would I list files in Python?") is False
        )

    def test_performance(self, engine):
        """Test that heuristic is fast."""
        import time

        queries = [
            "What is Python?",
            "List files in directory",
            "Explain OOP concepts",
            "Read the config file",
            "Show me how to code",
        ] * 20  # 100 queries

        start = time.time()
        for query in queries:
            engine._heuristic_tool_check(query)
        elapsed = time.time() - start

        # Should process 100 queries in under 0.1 seconds
        assert elapsed < 0.1, f"Heuristic too slow: {elapsed:.3f}s for 100 queries"
