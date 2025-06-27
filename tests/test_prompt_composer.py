"""
Tests for the modular prompt composition system.
"""


import pytest

from ocode_python.prompts.prompt_composer import PromptComposer
from ocode_python.prompts.prompt_repository import (
    PromptExample,
    PromptRepository,
)


class TestPromptComposer:
    """Test the prompt composer functionality."""

    @pytest.fixture
    def composer(self, tmp_path):
        """Create a prompt composer with test components."""
        # Create test prompt files
        system_dir = tmp_path / "system"
        system_dir.mkdir()

        (system_dir / "role.md").write_text("You are an expert AI coding assistant.")

        (system_dir / "core_capabilities.md").write_text(
            "- Advanced code analysis\n- Tool orchestration"
        )
        
        (system_dir / "task_analysis_framework.md").write_text(
            "Task analysis framework for understanding user requests"
        )
        
        (system_dir / "workflow_patterns.md").write_text(
            "Common workflow patterns for task execution"
        )
        
        (system_dir / "response_strategies.md").write_text(
            "Strategies for generating effective responses"
        )
        
        (system_dir / "error_handling.md").write_text(
            "Error handling and recovery procedures"
        )
        
        (system_dir / "output_guidelines.md").write_text(
            "Guidelines for output formatting"
        )
        
        (system_dir / "thinking_framework.md").write_text(
            "Framework for systematic thinking and analysis"
        )

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        (analysis_dir / "tool_usage_criteria.md").write_text(
            "USE TOOLS when: file operations needed"
        )
        
        (analysis_dir / "decision_criteria.md").write_text(
            "Criteria for making tool usage decisions"
        )

        return PromptComposer(prompts_dir=tmp_path)

    def test_load_component(self, composer):
        """Test loading individual components."""
        role = composer.load_component("role", "system")
        assert "expert AI coding assistant" in role

        criteria = composer.load_component("tool_usage_criteria", "analysis")
        assert "USE TOOLS" in criteria

    def test_build_system_prompt(self, composer):
        """Test building a complete system prompt."""
        prompt = composer.build_system_prompt(
            tool_descriptions="- file_read: Read files\n- file_write: Write files"
        )

        # Check that all components are included
        assert "<role>" in prompt
        assert "expert AI coding assistant" in prompt
        assert "<core_capabilities>" in prompt
        assert "Advanced code analysis" in prompt
        assert "<available_tools>" in prompt
        assert "file_read: Read files" in prompt

    def test_build_minimal_prompt(self, composer):
        """Test building a minimal prompt."""
        prompt = composer.build_minimal_prompt(tool_descriptions="- ls: List files")

        # Should only include role and capabilities
        assert "<role>" in prompt
        assert "<core_capabilities>" in prompt
        # Should not include other components
        assert "<workflow_patterns>" not in prompt
        assert "<thinking_framework>" not in prompt

    def test_cache_functionality(self, composer):
        """Test that component caching works."""
        # First load
        role1 = composer.load_component("role", "system")

        # Modify the file
        system_dir = composer.prompts_dir / "system"
        (system_dir / "role.md").write_text("Modified role content")

        # Second load should return cached version
        role2 = composer.load_component("role", "system")
        assert role1 == role2
        assert "Modified" not in role2

        # Clear cache and reload
        composer.clear_cache()
        role3 = composer.load_component("role", "system")
        assert "Modified" in role3


class TestPromptRepository:
    """Test the prompt repository functionality."""

    @pytest.fixture
    def repository(self, tmp_path):
        """Create a test repository."""
        return PromptRepository(tmp_path)

    def test_add_and_retrieve_example(self, repository):
        """Test adding and retrieving examples."""
        example = PromptExample(
            id="test1",
            query="list files in current directory",
            response={"should_use_tools": True, "suggested_tools": ["ls"]},
            category="tool_use",
            tags=["file_ops"],
        )

        # Add example
        example_id = repository.example_store.add_example(example)
        assert example_id == "test1"

        # Retrieve by category
        examples = repository.example_store.get_examples(category="tool_use")
        assert len(examples) == 1
        assert examples[0].query == "list files in current directory"

    def test_search_similar_examples(self, repository):
        """Test searching for similar examples."""
        # Add some examples
        examples = [
            PromptExample(
                id="",
                query="show me all Python files",
                response={"should_use_tools": True},
                category="tool_use",
                tags=[],
            ),
            PromptExample(
                id="",
                query="list Python scripts in src",
                response={"should_use_tools": True},
                category="tool_use",
                tags=[],
            ),
            PromptExample(
                id="",
                query="what is Python",
                response={"should_use_tools": False},
                category="knowledge",
                tags=[],
            ),
        ]

        for example in examples:
            repository.example_store.add_example(example)

        # Search for similar
        results = repository.example_store.search_similar("find Python files", limit=2)
        assert len(results) == 2
        # Should find the file-related queries, not the knowledge query
        assert all("files" in r.query or "scripts" in r.query for r in results)

    def test_performance_tracking(self, repository):
        """Test tracking example performance."""
        example = PromptExample(
            id="perf1", query="test query", response={}, category="test", tags=[]
        )

        repository.example_store.add_example(example)

        # Update performance
        repository.track_example_performance("perf1", success=True)

        # Retrieve and check
        examples = repository.example_store.get_examples(limit=1)
        assert examples[0].performance_score == 1.1
        assert examples[0].usage_count == 1

    def test_component_versioning(self, repository):
        """Test component version management."""
        # Add initial version
        repository.update_component("test_prompt", "Initial content", "system")

        # Get component
        content = repository.get_component("test_prompt")
        assert content == "Initial content"

        # Update component (creates new version)
        repository.update_component("test_prompt", "Updated content", "system")

        # Get latest version
        content = repository.get_component("test_prompt")
        assert content == "Updated content"

        # Check that old version is deactivated
        old_component = repository.example_store.get_component("test_prompt", version=1)
        assert old_component.active is False


class TestPromptComposerWithRepository:
    """Test prompt composer with repository integration."""

    @pytest.fixture
    def composer_with_repo(self, tmp_path):
        """Create composer with repository enabled."""
        # Create basic prompt structure
        system_dir = tmp_path / "system"
        system_dir.mkdir()
        
        # Create all required component files
        (system_dir / "role.md").write_text("AI Assistant")
        (system_dir / "core_capabilities.md").write_text(
            "- Advanced code analysis\n- Tool orchestration"
        )
        (system_dir / "response_strategies.md").write_text(
            "Strategies for generating effective responses"
        )
        (system_dir / "output_guidelines.md").write_text(
            "Guidelines for output formatting"
        )
        (system_dir / "workflow_patterns.md").write_text(
            "Common workflow patterns for task execution"
        )
        (system_dir / "error_handling.md").write_text(
            "Error handling and recovery procedures"
        )

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        return PromptComposer(prompts_dir=tmp_path, use_repository=True)

    def test_dynamic_example_selection(self, composer_with_repo):
        """Test dynamic example selection from repository."""
        # Add examples to repository
        examples = [
            PromptExample(
                id="",
                query="read config.json",
                response={"should_use_tools": True, "suggested_tools": ["file_read"]},
                category="tool_use",
                tags=["file_ops"],
                performance_score=0.9,
            ),
            PromptExample(
                id="",
                query="show me config file",
                response={"should_use_tools": True, "suggested_tools": ["file_read"]},
                category="tool_use",
                tags=["file_ops"],
                performance_score=1.2,
            ),
        ]

        for ex in examples:
            composer_with_repo.repository.example_store.add_example(ex)

        # Get dynamic examples
        formatted = composer_with_repo.get_dynamic_examples(
            "read config file", example_count=2, strategy="similar"
        )

        # Should contain the examples
        assert "config" in formatted
        assert "file_read" in formatted

    def test_adaptive_prompt_building(self, composer_with_repo):
        """Test building adaptive prompts based on query type."""
        # Knowledge query - should get minimal prompt
        prompt = composer_with_repo.build_adaptive_prompt(
            "What is recursion?", query_type="knowledge"
        )

        assert "<role>" in prompt
        assert "<response_strategies>" in prompt
        # Should not include tool-specific components
        assert "<workflow_patterns>" not in prompt

        # Action query - should get tool-focused prompt
        prompt = composer_with_repo.build_adaptive_prompt(
            "Delete all temp files",
            query_type="action",
            context={"tool_descriptions": "- remove: Delete files"},
        )

        assert "<workflow_patterns>" in prompt
        assert "<error_handling>" in prompt
