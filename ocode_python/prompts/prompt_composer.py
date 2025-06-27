"""
Prompt Composer - Dynamically assembles system prompts from modular components.

This module provides functionality to build system prompts by composing
smaller, reusable prompt components stored as markdown files. This approach
improves maintainability and allows for dynamic prompt construction based
on query requirements.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .prompt_repository import PromptRepository


class PromptComposer:
    """Composes system prompts from modular components."""

    def __init__(
        self, prompts_dir: Optional[Path] = None, use_repository: bool = False
    ):
        """Initialize the prompt composer.

        Args:
            prompts_dir: Directory containing prompt component files.
                        Defaults to ocode_python/prompts/
            use_repository: Whether to use the prompt repository for
                          dynamic example selection and versioning
        """
        if prompts_dir is None:
            # Get the default prompts directory relative to this file
            prompts_dir = Path(__file__).parent

        self.prompts_dir = prompts_dir
        self.system_dir = prompts_dir / "system"
        self.analysis_dir = prompts_dir / "analysis"

        # Component cache to avoid repeated file reads
        self._component_cache: Dict[str, str] = {}

        # Initialize repository if requested
        self.repository = None
        if use_repository:
            data_dir = prompts_dir / "data"
            self.repository = PromptRepository(data_dir)

        # Define the standard prompt structure and components
        self.core_components = [
            "role",
            "core_capabilities",
            "task_analysis_framework",
            "workflow_patterns",
            "response_strategies",
            "error_handling",
            "output_guidelines",
            "thinking_framework",
        ]

        self.analysis_components = ["decision_criteria", "tool_usage_criteria"]

    @lru_cache(maxsize=128)
    def load_component(
        self, component_name: str, component_type: str = "system"
    ) -> str:
        """Load a prompt component from file with caching.

        Args:
            component_name: Name of the component file (without .md extension)
            component_type: Type of component ("system" or "analysis")

        Returns:
            Content of the component file

        Raises:
            FileNotFoundError: If component file doesn't exist
        """
        cache_key = f"{component_type}/{component_name}"

        if cache_key in self._component_cache:
            return self._component_cache[cache_key]

        # Determine the directory based on component type
        if component_type == "system":
            component_dir = self.system_dir
        elif component_type == "analysis":
            component_dir = self.analysis_dir
        else:
            raise ValueError(f"Invalid component type: {component_type}")

        # Load the component file
        file_path = component_dir / f"{component_name}.md"

        if not file_path.exists():
            raise FileNotFoundError(f"Component file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        # Cache the content
        self._component_cache[cache_key] = content

        return content

    def _determine_components_to_include(
        self,
        include_components: Optional[Set[str]],
        exclude_components: Optional[Set[str]],
    ) -> Set[str]:
        """Determine which components to include in the prompt."""
        if include_components is None:
            components_to_include = set(self.core_components)
        else:
            components_to_include = set(include_components)

        if exclude_components:
            components_to_include -= set(exclude_components)

        return components_to_include

    def _add_basic_sections(self, sections: List[str], components: Set[str]) -> None:
        """Add basic system prompt sections."""
        if "role" in components:
            role_content = self.load_component("role")
            sections.append(f"<role>\n{role_content}\n</role>")

        if "core_capabilities" in components:
            capabilities = self.load_component("core_capabilities")
            sections.append(
                f"<core_capabilities>\n{capabilities}\n</core_capabilities>"
            )

        if "task_analysis_framework" in components:
            framework = self.load_component("task_analysis_framework")
            sections.append(
                f"<task_analysis_framework>\n{framework}\n</task_analysis_framework>"
            )

    def _add_decision_sections(self, sections: List[str], components: Set[str]) -> None:
        """Add decision-making and workflow sections."""
        if "decision_criteria" in components:
            try:
                criteria = self.load_component("decision_criteria", "analysis")
                sections.append(
                    f"<decision_criteria>\n{criteria}\n</decision_criteria>"
                )
            except FileNotFoundError:
                pass  # Skip if not available

        if "workflow_patterns" in components:
            patterns = self.load_component("workflow_patterns")
            sections.append(f"<workflow_patterns>\n{patterns}\n</workflow_patterns>")

    def _add_response_sections(self, sections: List[str], components: Set[str]) -> None:
        """Add response and output guidance sections."""
        if "response_strategies" in components:
            strategies = self.load_component("response_strategies")
            sections.append(
                f"<response_strategies>\n{strategies}\n</response_strategies>"
            )

        if "error_handling" in components:
            error_handling = self.load_component("error_handling")
            sections.append(f"<error_handling>\n{error_handling}\n</error_handling>")

        if "output_guidelines" in components:
            guidelines = self.load_component("output_guidelines")
            sections.append(f"<output_guidelines>\n{guidelines}\n</output_guidelines>")

        if "thinking_framework" in components:
            thinking = self.load_component("thinking_framework")
            sections.append(f"<thinking_framework>\n{thinking}\n</thinking_framework>")

    def build_system_prompt(
        self,
        tool_descriptions: str,
        include_components: Optional[Set[str]] = None,
        exclude_components: Optional[Set[str]] = None,
        additional_context: Optional[Dict[str, str]] = None,
    ) -> str:
        """Build a complete system prompt from components.

        Args:
            tool_descriptions: Formatted string of available tool descriptions
            include_components: Set of component names to include.
                              If None, includes all core components.
            exclude_components: Set of component names to exclude.
            additional_context: Additional context sections to add.

        Returns:
            Complete system prompt with XML-style tags
        """
        # Determine which components to include
        components_to_include = self._determine_components_to_include(
            include_components, exclude_components
        )

        # Build the prompt sections
        sections: List[str] = []

        # Add basic sections
        self._add_basic_sections(sections, components_to_include)

        # Add available tools section
        sections.append(f"<available_tools>\n{tool_descriptions}\n</available_tools>")

        # Add decision and workflow sections
        self._add_decision_sections(sections, components_to_include)

        # Add response and output sections
        self._add_response_sections(sections, components_to_include)

        # Add any additional context sections
        if additional_context:
            for tag, content in additional_context.items():
                sections.append(f"<{tag}>\n{content}\n</{tag}>")

        # Join all sections
        return "\n\n".join(sections)

    def build_minimal_prompt(self, tool_descriptions: str) -> str:
        """Build a minimal system prompt for simple queries.

        This includes only the essential components needed for basic
        task execution, reducing token usage.

        Args:
            tool_descriptions: Formatted string of available tool descriptions

        Returns:
            Minimal system prompt
        """
        return self.build_system_prompt(
            tool_descriptions=tool_descriptions,
            include_components={"role", "core_capabilities"},
            additional_context={
                "instruction": (
                    "Execute the user's request efficiently using available tools."
                )
            },
        )

    def build_analysis_prompt(self, query: str, tool_names: List[str]) -> str:
        """Build a specialized prompt for query analysis.

        This method constructs a comprehensive analysis prompt that includes:
        - Tool usage criteria
        - Tool categories
        - Concrete examples
        - Thinking framework questions

        Args:
            query: User query to analyze
            tool_names: List of available tool names

        Returns:
            Analysis-focused prompt with all necessary components
        """
        # Load analysis components
        try:
            tool_usage_criteria = self.load_component("tool_usage_criteria", "analysis")
        except FileNotFoundError:
            tool_usage_criteria = "Analyze the query to determine if tools are needed."

        try:
            tool_categories = self.load_component("tool_categories", "analysis")
        except FileNotFoundError:
            tool_categories = "Tools are available for various operations."

        try:
            tool_examples = self.load_component("tool_examples", "analysis")
        except FileNotFoundError:
            tool_examples = ""

        try:
            thinking_questions = self.load_component("thinking_questions", "analysis")
        except FileNotFoundError:
            thinking_questions = ""

        prompt_header = (
            "<role>You are an expert AI assistant specialized in distinguishing "
            "between general knowledge questions and actionable tasks that "
            "require tools.</role>\\n\\n"
            "<task>Analyze the user query and determine if it requires tools or can be "
            "answered directly with knowledge.</task>"
        )
        return f"""{prompt_header}

<query>"{query}"</query>

<available_tools>
{', '.join(tool_names)}
</available_tools>

<decision_criteria>
{tool_usage_criteria}
</decision_criteria>

<tool_categories>
{tool_categories}
</tool_categories>

<examples>
{tool_examples}
</examples>

<thinking>
{thinking_questions}
</thinking>

<instructions>
Respond with ONLY a JSON object following this exact format:
{{
    "should_use_tools": true/false,
    "suggested_tools": ["tool1", "tool2"] or [],
    "reasoning": "brief explanation of decision",
    "context_complexity": "simple" or "full"
}}
</instructions>"""

    def build_adaptive_prompt(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        query_type: Optional[str] = None,
    ) -> str:
        """Build an adaptive system prompt based on query analysis.

        This method creates optimized prompts by including only the
        components necessary for the specific query type, reducing
        token usage while maintaining effectiveness.

        Args:
            query: User query
            context: Optional context information
            query_type: Type of query (knowledge, action, complex)

        Returns:
            Optimized system prompt for the query type
        """
        # Determine components based on query type
        if query_type == "knowledge":
            # Minimal components for knowledge queries
            include_components = {
                "role",
                "core_capabilities",
                "response_strategies",
                "output_guidelines",
            }
        elif query_type == "action":
            # Tool-focused components for action queries
            include_components = {
                "role",
                "core_capabilities",
                "workflow_patterns",
                "error_handling",
            }
        elif query_type == "complex":
            # All components for complex queries
            include_components = None  # Use all
        else:
            # Default to moderate set
            include_components = {
                "role",
                "core_capabilities",
                "task_analysis_framework",
                "response_strategies",
                "thinking_framework",
            }

        # Get tool descriptions if needed
        tool_descriptions = ""
        if query_type != "knowledge":
            # This would be passed in from the engine
            tool_descriptions = context.get("tool_descriptions", "") if context else ""

        return self.build_system_prompt(
            tool_descriptions=tool_descriptions,
            include_components=include_components,
            additional_context=context,
        )

    def get_dynamic_examples(
        self, query: str, example_count: int = 5, strategy: str = "similar"
    ) -> str:
        """Get dynamically selected examples from the repository.

        Args:
            query: User query to find examples for
            example_count: Number of examples to retrieve
            strategy: Selection strategy (similar, diverse, performance)

        Returns:
            Formatted examples string
        """
        if not self.repository:
            # Fallback to static examples
            try:
                return self.load_component("tool_examples", "analysis")
            except FileNotFoundError:
                return ""

        # Get examples from repository
        examples = self.repository.get_examples_for_prompt(
            query=query, strategy=strategy
        )[:example_count]

        # Format examples
        formatted_examples = []
        for example in examples:
            formatted = f'Query: "{example.query}"\n'
            formatted += f"Response: {json.dumps(example.response)}"
            formatted_examples.append(formatted)

            # Track usage for performance metrics
            self.repository.track_example_performance(
                example.id, success=True  # Will be updated based on actual results
            )

        return "\n\n".join(formatted_examples)

    def build_analysis_prompt_dynamic(
        self, query: str, tool_names: List[str], use_dynamic_examples: bool = True
    ) -> str:
        """Build analysis prompt with dynamic example selection.

        This enhanced version can pull examples from a large repository
        based on query similarity, performance metrics, or diversity.

        Args:
            query: User query to analyze
            tool_names: List of available tool names
            use_dynamic_examples: Whether to use dynamic example selection

        Returns:
            Analysis prompt with optimized examples
        """
        # Load static components
        tool_usage_criteria = self._load_or_default(
            "tool_usage_criteria",
            "analysis",
            "Analyze the query to determine if tools are needed.",
        )

        tool_categories = self._load_or_default(
            "tool_categories", "analysis", "Tools are available for various operations."
        )

        thinking_questions = self._load_or_default("thinking_questions", "analysis", "")

        # Get examples - dynamic or static
        if use_dynamic_examples and self.repository:
            examples = self.get_dynamic_examples(query, example_count=8)
        else:
            examples = self._load_or_default("tool_examples", "analysis", "")

        prompt_header = (
            "<role>You are an expert AI assistant specialized in distinguishing "
            "between general knowledge questions and actionable tasks that "
            "require tools.</role>\\n\\n"
            "<task>Analyze the user query and determine if it requires tools or can be "
            "answered directly with knowledge.</task>"
        )
        return f"""{prompt_header}

<query>"{query}"</query>

<available_tools>
{', '.join(tool_names)}
</available_tools>

<decision_criteria>
{tool_usage_criteria}
</decision_criteria>

<tool_categories>
{tool_categories}
</tool_categories>

<examples>
{examples}
</examples>

<thinking>
{thinking_questions}
</thinking>

<instructions>
Respond with ONLY a JSON object following this exact format:
{{
    "should_use_tools": true/false,
    "suggested_tools": ["tool1", "tool2"] or [],
    "reasoning": "brief explanation of decision",
    "context_complexity": "simple" or "full"
}}
</instructions>"""

    def _load_or_default(
        self, component_name: str, component_type: str, default: str
    ) -> str:
        """Load component with fallback to default."""
        try:
            return self.load_component(component_name, component_type)
        except FileNotFoundError:
            return default

    def clear_cache(self):
        """Clear the component cache to force reloading from files."""
        self._component_cache.clear()
        self.load_component.cache_clear()
