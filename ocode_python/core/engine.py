"""
OCode Engine - Main processing engine for AI-powered coding assistance.
"""

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from ..tools.base import Tool, ToolRegistry, ToolResult
from ..utils.auth import AuthenticationManager
from ..utils.config import ConfigManager
from .api_client import CompletionRequest, Message, OllamaAPIClient
from .context_manager import ContextManager, ProjectContext
from .orchestrator import AdvancedOrchestrator
from .semantic_context import DynamicContextManager, SemanticContextBuilder
from .session import SessionManager
from .stream_processor import StreamProcessor


@dataclass
class ProcessingMetrics:
    """Metrics for processing performance."""

    start_time: float
    end_time: Optional[float] = None
    tokens_processed: int = 0
    files_analyzed: int = 0
    tools_executed: int = 0
    context_size: int = 0

    @property
    def duration(self) -> float:
        """Calculate the duration of processing in seconds.

        Returns:
            Time elapsed since start_time. If processing is complete (end_time is set),
            returns the total duration. Otherwise, returns time elapsed so far.
        """
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time


class OCodeEngine:
    """
    Main OCode processing engine.

    Orchestrates AI interactions, context management, and tool execution
    to provide intelligent coding assistance.
    """

    def __init__(
        self,
        model: str = "MFDoom/deepseek-coder-v2-tool-calling:latest",
        api_key: Optional[str] = None,
        output_format: str = "text",
        verbose: bool = False,
        root_path: Optional[Path] = None,
        confirmation_callback=None,
        max_continuations: int = 10,  # Increased default for complex workflows
        chunk_size: int = 8192,  # Increased default for better performance
    ) -> None:
        """
        Initialize the OCode engine with all necessary components.

        The engine serves as the central orchestrator that coordinates:
        - AI model interactions through the Ollama API
        - Project context analysis and file understanding
        - Tool execution and workflow management
        - Session management and conversation history
        - Authentication and configuration management

        Args:
            model: Ollama model identifier for AI interactions. Should support function calling  # noqa: E501
                  for optimal tool usage. Default is a code-specialized model.
            api_key: Optional API key for authentication. If not provided, will attempt  # noqa: E501
                    to use stored credentials or fall back to unauthenticated access.
            output_format: Response format - 'text' for human-readable, 'json' for structured,  # noqa: E501
                          'stream-json' for real-time streaming with JSON markers.
            verbose: Enable detailed logging and debug output. Useful for development  # noqa: E501
                    and troubleshooting but may be noisy in production.
            root_path: Project root directory. If None, uses current working directory.  # noqa: E501
                      This defines the scope of file operations and context analysis.
            confirmation_callback: Async function(command: str, reason: str) -> bool
                                  Called before executing potentially destructive operations.  # noqa: E501
                                  Should present the command to user and return their decision.  # noqa: E501
            max_continuations: Maximum automatic response continuations. Prevents infinite  # noqa: E501
                              loops while allowing complex multi-part responses.
            chunk_size: Response streaming chunk size in bytes. Larger chunks improve
                       throughput but may impact responsiveness.
        """

        # Core configuration - store user-provided settings
        self.model = model
        self.output_format = output_format
        self.verbose = verbose
        self.confirmation_callback = confirmation_callback
        self.max_continuations = max_continuations
        self.chunk_size = chunk_size

        # Initialize core management components
        # These handle cross-cutting concerns like config, auth, and external API access
        self.config = (
            ConfigManager()
        )  # Handles .ocode/settings.json and environment vars
        self.auth = (
            AuthenticationManager()
        )  # Manages API keys and authentication tokens
        self.api_client = OllamaAPIClient()  # Handles communication with Ollama server

        # Initialize AI workflow components
        # These handle the core AI and automation functionality
        self.context_manager = ContextManager(
            root_path
        )  # Analyzes project structure and files
        self.tool_registry = (
            ToolRegistry()
        )  # Manages available tools and their execution
        self.session_manager = SessionManager()  # Handles conversation persistence

        # Register all available tools with the registry
        # This makes them available for AI function calling
        self.tool_registry.register_core_tools()

        # Pre-declare architecture component attributes
        self.orchestrator: Optional[AdvancedOrchestrator] = None
        self.stream_processor: Optional[StreamProcessor] = None
        self.semantic_context_builder: Optional[SemanticContextBuilder] = None
        self.dynamic_context_manager: Optional[DynamicContextManager] = None

        # Store architecture configuration for lazy initialization
        self._arch_config = self.config.get("architecture", {})

        # Detect CI environment and adjust configuration for stability
        import os

        is_ci = bool(
            os.getenv("CI") or os.getenv("GITHUB_ACTIONS") or os.getenv("JENKINS_URL")
        )
        if is_ci:
            # In CI, disable potentially unstable features
            self._arch_config = dict(
                self._arch_config
            )  # Copy to avoid modifying original
            self._arch_config["enable_semantic_context"] = False
            self._arch_config["enable_dynamic_context"] = False
            if self.verbose:
                print(
                    "🤖 CI environment detected: disabled semantic features "
                    "for stability"
                )

        # Flag to track initialization of asyncio-dependent components
        self._components_initialized = False

        # Processing state management
        # These track the current conversation and processing state
        self.current_context: Optional[ProjectContext] = (
            None  # Current project analysis
        )
        self.conversation_history: List[Message] = []  # Full conversation for context
        self.current_response: str = ""  # Partial response for continuation support
        self.response_complete: bool = False  # Flag indicating if response is finished
        self.auto_continue: bool = (
            True  # Whether to automatically continue incomplete responses
        )

        # Performance optimization through caching
        # Tool descriptions are expensive to generate and rarely change
        self._tool_descriptions_cache: Optional[str] = None

    async def _ensure_components_initialized(self) -> None:
        """Ensure asyncio-dependent components are initialized with event loop."""
        if self._components_initialized:
            return

        # Advanced orchestrator for priority-based command queuing and side effects
        if self._arch_config.get("enable_advanced_orchestrator", True):
            max_concurrent = self._arch_config.get("orchestrator_max_concurrent", 5)
            self.orchestrator = AdvancedOrchestrator(self.tool_registry, max_concurrent)
        else:
            self.orchestrator = None

        # Stream processor for read-write pipeline separation and intelligent batching
        if self._arch_config.get("enable_stream_processing", True):
            self.stream_processor = StreamProcessor(self.context_manager)
        else:
            self.stream_processor = None

        # Semantic context builder for embedding-based file selection
        if self._arch_config.get("enable_semantic_context", True):
            self.semantic_context_builder = SemanticContextBuilder(self.context_manager)
        else:
            self.semantic_context_builder = None

        # Dynamic context manager for intelligent context expansion
        if self._arch_config.get("enable_dynamic_context", True):
            self.dynamic_context_manager = DynamicContextManager(self.context_manager)
        else:
            self.dynamic_context_manager = None

        self._components_initialized = True

        # Build the comprehensive system prompt that guides AI behavior
        # This includes role definition, tool descriptions, and workflow guidance
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """
        Build a comprehensive system prompt with deep guidance.

        Constructs a detailed system prompt that includes:
        - Core role and capabilities definition
        - Query analysis framework for understanding user intent
        - Tool usage decision criteria
        - Workflow patterns for different task types
        - Error handling and communication guidelines
        - Thinking framework for systematic analysis

        Returns:
            str: A complete system prompt with structured guidance
        """
        # Get available tools dynamically
        tool_descriptions = self._get_tool_descriptions_by_category()

        return f"""<role>
You are an expert AI coding assistant with deep knowledge of software engineering, programming languages, and development workflows. You specialize in intelligent task analysis, strategic tool usage, and providing comprehensive coding assistance. # noqa: E501
</role>

<core_capabilities>
- Advanced code analysis and architecture understanding
- Intelligent file system navigation and manipulation
- Strategic workflow orchestration using available tools
- Context-aware project understanding
- Multi-step task decomposition and execution
</core_capabilities>

<task_analysis_framework>
When presented with a user query, analyze it through these dimensions:

1. **Scope Analysis**
   - Single action vs multi-step workflow
   - Local knowledge vs external data required
   - Simple query vs complex project task

2. **Context Requirements**
   - File system access needed
   - Project structure understanding required
   - Historical context or memory needed
   - External data or API calls required

3. **Tool Strategy**
   - Direct tool execution for simple tasks
   - Sequential tool chaining for workflows
   - Agent delegation for complex multi-domain tasks
   - Hybrid approaches combining tools and knowledge
</task_analysis_framework>

<available_tools>
{tool_descriptions}
</available_tools>

<decision_criteria>
**DIRECT KNOWLEDGE RESPONSE** when query involves:
- General programming concepts, patterns, or best practices
- Theoretical explanations of algorithms or data structures
- Language syntax, features, or standard library information
- Architectural patterns, design principles, or methodology discussions
- Troubleshooting common programming issues with known solutions
- Code review or optimization suggestions for provided code snippets

**SINGLE TOOL EXECUTION** when query involves:
- Simple file operations (read, write, list, search)
- Basic system commands or checks
- Memory storage/retrieval operations
- Direct data transformation or analysis
- Git operations on current repository

**SEQUENTIAL TOOL CHAIN** when query involves:
- Multi-step file manipulations
- Code analysis followed by modifications
- Project setup or scaffolding tasks
- Data processing pipelines
- Testing and validation workflows

**AGENT DELEGATION** when query involves:
- Complex, multi-domain tasks requiring specialized expertise
- Large-scale refactoring or architectural changes
- Comprehensive testing or quality assurance workflows
- Documentation generation across multiple files
- Performance optimization requiring deep analysis
</decision_criteria>

<workflow_patterns>
**Analysis → Action Pattern:**
1. Understand project structure (architect, find, ls)
2. Analyze specific components (file_read, grep)
3. Execute changes (file_write, file_edit)
4. Validate results (testing tools, git_diff)

**Research → Implementation Pattern:**
1. Gather requirements and context
2. Research best practices or existing solutions
3. Design solution architecture
4. Implement step-by-step with validation

**Memory-Driven Pattern:**
1. Check existing knowledge (memory_read)
2. Gather new information as needed
3. Process and analyze information
4. Store insights for future use (memory_write)
</workflow_patterns>

<response_strategies>
**For Knowledge Queries:**
- Provide comprehensive explanations with examples
- Include practical code snippets when relevant
- Explain trade-offs and considerations
- Reference best practices and common pitfalls

**For Action Queries:**
- Execute appropriate tools efficiently
- Provide clear progress updates
- Explain the reasoning behind tool choices
- Anticipate and handle potential errors gracefully

**For Complex Workflows:**
- Break down into logical phases
- Use appropriate tools for each phase
- Maintain context between operations
- Provide summary of completed actions
</response_strategies>

<error_handling>
- Gracefully handle tool failures with alternative approaches
- Provide clear error explanations and potential solutions
- Use fallback strategies when primary approach fails
- Ask for clarification when query intent is ambiguous
</error_handling>

<output_guidelines>
- Be concise for simple queries, comprehensive for complex ones
- Use appropriate formatting (code blocks, lists, etc.)
- Provide actionable insights and next steps
- Include relevant examples and context
- Maintain professional but approachable tone
</output_guidelines>

<thinking_framework>
Before responding, consider:
1. What is the user really trying to achieve?
2. What's the most efficient path to their goal?
3. What context do I need to understand their project?
4. Which tools would be most effective?
5. What potential issues should I anticipate?
6. How can I provide the most value?
</thinking_framework>"""

    def _get_tool_descriptions_by_category(self) -> str:
        """Organize tool descriptions by functional category.

        Dynamically groups tools based on their category metadata,
        ensuring the categorization stays accurate as tools are added
        or modified without requiring manual updates to this method.

        Returns:
            str: Formatted tool descriptions grouped by category
        """
        # Return cached descriptions if available
        if self._tool_descriptions_cache is not None:
            return self._tool_descriptions_cache

        # Dynamically group tools by their category
        categories: Dict[str, List[Tool]] = {}

        for tool in self.tool_registry.get_all_tools():
            # Get category from tool definition, default to "General" if not specified
            category = getattr(tool.definition, "category", "General")

            if category not in categories:
                categories[category] = []
            categories[category].append(tool)

        # Sort categories for consistent output
        sorted_categories = sorted(categories.items())

        output = []
        for category, tools in sorted_categories:
            output.append(f"**{category}:**")
            # Sort tools within category by name for consistency
            sorted_tools = sorted(tools, key=lambda t: t.definition.name)
            for tool in sorted_tools:
                output.append(
                    f"  - {tool.definition.name}: {tool.definition.description}"
                )
            output.append("")  # Add blank line between categories

        # Cache the result for future use
        self._tool_descriptions_cache = "\n".join(output).strip()
        return self._tool_descriptions_cache

    def invalidate_tool_cache(self) -> None:
        """Invalidate the tool descriptions cache.

        Call this method if tools are dynamically added or removed
        to ensure the descriptions are regenerated on next access.
        """
        self._tool_descriptions_cache = None

    def _add_examples_to_system_prompt(self, base_prompt: str) -> str:
        """Add concrete examples to the system prompt.

        Appends practical examples that demonstrate:
        - Knowledge queries that require direct responses
        - Simple tool usage for basic operations
        - Complex workflows requiring multiple tools

        These examples help guide the AI's decision-making process
        about when to use tools versus direct knowledge.

        Args:
            base_prompt: The base system prompt to extend

        Returns:
            str: The system prompt with examples appended
        """
        examples = """
<examples>
**Knowledge Query Example:**
  User: "Explain the difference between REST and GraphQL"
  Response: [Comprehensive explanation without tools]

**Simple Action Example:**
  User: "List files in the current directory"
  Response: [Execute ls tool immediately]

**Complex Workflow Example:**
  User: "Refactor this codebase to use dependency injection"
  Response: [Multi-step process: analyze → plan → implement → test]

**Agent Delegation Example:**
  User: "Set up a complete CI/CD pipeline for this project"
  Response: [Create specialized agents for different aspects]
</examples>"""

        return base_prompt + examples

    def _add_project_context_guidance(
        self, base_prompt: str, context: ProjectContext
    ) -> str:
        """Add project-specific guidance to the system prompt.

        Enhances the system prompt with project-specific information:
        - Detected programming languages in the project
        - Project structure and file organization
        - Best practices for the detected languages
        - Contextual guidance based on project type

        This helps tailor responses to the specific project environment.

        Args:
            base_prompt: The base system prompt to extend
            context: Project context containing file information

        Returns:
            str: The system prompt with project-specific guidance
        """
        if not context:
            return base_prompt

        # Detect languages from file extensions in the context
        languages = set()
        ext_to_lang = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".java": "Java",
            ".cpp": "C++",
            ".c": "C",
            ".go": "Go",
            ".rb": "Ruby",
            ".php": "PHP",
            ".rs": "Rust",
            ".swift": "Swift",
        }
        for file_path in context.files:
            ext = file_path.suffix.lower()
            if ext in ext_to_lang:
                languages.add(ext_to_lang[ext])

        context_guidance = f"""
<project_context>
  Current Project: {context.project_root}
  Languages Detected: {', '.join(sorted(languages)) if languages else 'Unknown'}
  Key Files: {len(context.files)} analyzed
  Git Branch: {context.git_info.get('branch', 'unknown') if context.git_info else 'not a git repo'} # noqa: E501

  Adapt your responses to this project context and prefer tools that work well with the detected languages and project structure. # noqa: E501
</project_context>"""

        return base_prompt + context_guidance

    async def _prepare_context(self, query: str) -> ProjectContext:
        """Prepare project context for the query.

        Uses advanced semantic context selection and dynamic expansion when available.
        Shows progress information if verbose mode is enabled.

        Args:
            query: User query to analyze context for.

        Returns:
            ProjectContext object with relevant files and metadata.
        """
        # Ensure asyncio-dependent components are initialized
        await self._ensure_components_initialized()

        if self.verbose:
            print("🔍 Analyzing project context...")

        # Use dynamic context manager if available for enhanced context selection
        if self.dynamic_context_manager:
            arch_config = self.config.get("architecture", {})
            max_files = arch_config.get("semantic_context_max_files", 20)
            expansion_factor = arch_config.get("context_expansion_factor", 1.5)
            context = await self.dynamic_context_manager.build_dynamic_context(
                query=query,
                initial_max_files=max_files,
                expansion_factor=expansion_factor,
            )
            if self.verbose:
                insights = self.dynamic_context_manager.get_context_insights()
                if insights:
                    embeddings_enabled = insights.get("embeddings_enabled", False)
                    print(f"🧠 Semantic analysis: {embeddings_enabled}")
        else:
            # Fallback to basic context manager
            context = await self.context_manager.build_context(
                query=query, max_files=self.config.get("max_context_files", 20)
            )

        if self.verbose:
            print(f"📁 Analyzed {len(context.files)} files")
            if context.git_info:
                print(
                    f"🌿 Git: {context.git_info.get('branch', 'unknown')} ({context.git_info.get('commit', 'unknown')})"  # noqa: E501
                )

        self.current_context = context
        return context

    async def _llm_should_use_tools(self, query: str) -> Dict[str, Any]:
        """Use LLM to determine if and which tools should be used for the query.

        Sends the query to the LLM with detailed criteria for determining
        whether tools are needed or if a direct knowledge response suffices.

        Args:
            query: User query to analyze.

        Returns:
            Dictionary containing:
            - should_use_tools: Boolean indicating if tools are needed
            - suggested_tools: List of recommended tool names
            - reasoning: Explanation of the decision
            - context_complexity: "simple" or "full"
        """
        tool_names = [
            tool.definition.name for tool in self.tool_registry.get_all_tools()
        ]

        analysis_prompt = f"""<role>You are an expert AI assistant specialized in distinguishing between general knowledge questions and actionable tasks that require tools.</role> # noqa: E501

<task>Analyze the user query and determine if it requires tools or can be answered directly with knowledge.</task> # noqa: E501

<query>"{query}"</query>

<available_tools>
{', '.join(tool_names)}
</available_tools>

<decision_criteria>
USE TOOLS (should_use_tools: true) when the query:
- Requests interaction with files, directories, or filesystem
- Needs to execute system commands or check system state
- Requires downloading data from external sources
- Asks to store or retrieve information from memory
- Involves analyzing or modifying code in the current project
- Needs to perform git operations
- Requests text processing on specific files

DO NOT USE TOOLS (should_use_tools: false) when the query:
- Asks for general programming concepts or language explanations
- Requests theoretical knowledge or definitions
- Seeks best practices, patterns, or general advice
- Asks "what is", "how does", "why", "when to use" about general topics
- Requests explanations of algorithms, data structures, or concepts
- Asks for comparisons between technologies or approaches
- Seeks tutorials or learning guidance
</decision_criteria>

<tool_categories>
File Operations: file_read, file_write, file_list, file_edit, copy, move, remove, find
Text Processing: head, tail, wc, sort, uniq, grep, diff
Git Operations: git_status, git_commit, git_diff
System: bash, which, curl
Analysis: architect, agent (for project-specific analysis only)
Memory: memory_read, memory_write
Notebooks: notebook_read, notebook_edit
</tool_categories>

<examples>
Query: "List files in the current directory"
Response: {{"should_use_tools": true, "suggested_tools": ["ls"], "reasoning": "Direct file system interaction required", "context_complexity": "simple"}} # noqa: E501

Query: "Show me the first 5 lines of README.md"
Response: {{"should_use_tools": true, "suggested_tools": ["head"], "reasoning": "Reading specific file content", "context_complexity": "simple"}} # noqa: E501

Query: "Find all Python files in the project"
Response: {{"should_use_tools": true, "suggested_tools": ["find"], "reasoning": "Filesystem search operation", "context_complexity": "simple"}} # noqa: E501

Query: "Remember my email is john@example.com"
Response: {{"should_use_tools": true, "suggested_tools": ["memory_write"], "reasoning": "Store personal information", "context_complexity": "simple"}} # noqa: E501

Query: "Download data from https://api.example.com"
Response: {{"should_use_tools": true, "suggested_tools": ["curl"], "reasoning": "External HTTP request needed", "context_complexity": "simple"}} # noqa: E501

Query: "Analyze the architecture of THIS codebase"
Response: {{"should_use_tools": true, "suggested_tools": ["architect", "find"], "reasoning": "Project-specific code analysis", "context_complexity": "full"}} # noqa: E501

Query: "What is Python and how does it work?"
Response: {{"should_use_tools": false, "suggested_tools": [], "reasoning": "General programming language explanation", "context_complexity": "simple"}} # noqa: E501

Query: "Explain object-oriented programming"
Response: {{"should_use_tools": false, "suggested_tools": [], "reasoning": "General programming concept explanation", "context_complexity": "simple"}} # noqa: E501

Query: "What are the differences between REST and GraphQL?"
Response: {{"should_use_tools": false, "suggested_tools": [], "reasoning": "General technology comparison", "context_complexity": "simple"}} # noqa: E501

Query: "How do I implement a binary search algorithm?"
Response: {{"should_use_tools": false, "suggested_tools": [], "reasoning": "General algorithm explanation", "context_complexity": "simple"}} # noqa: E501

Query: "What are Python best practices for error handling?"
Response: {{"should_use_tools": false, "suggested_tools": [], "reasoning": "General best practices question", "context_complexity": "simple"}} # noqa: E501

Query: "When should I use async/await in Python?"
Response: {{"should_use_tools": false, "suggested_tools": [], "reasoning": "General usage guidance question", "context_complexity": "simple"}} # noqa: E501

Query: "Explain how machine learning works"
Response: {{"should_use_tools": false, "suggested_tools": [], "reasoning": "General ML concept explanation", "context_complexity": "simple"}} # noqa: E501
</examples>

<thinking>
Key questions to ask:
1. Is this asking for general knowledge/concepts OR specific file/system actions?
2. Does it mention specific files, directories, URLs, or system operations?
3. Is it theoretical ("what is", "how does", "explain") or actionable ("show me", "find", "download")? # noqa: E501
4. Would answering this require accessing the user's actual files or system?
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

        # Simple API call for analysis
        from .api_client import CompletionRequest

        request = CompletionRequest(
            model=self.model,
            messages=[{"role": "user", "content": analysis_prompt}],
            stream=False,
            options={"temperature": 0.0},  # Deterministic for analysis
        )

        try:
            response_content = ""
            async for chunk in self.api_client.stream_chat(request):
                if chunk.content:
                    response_content += chunk.content

            if self.verbose:
                print(f"🔍 LLM analysis response: {response_content[:200]}...")

            # Parse JSON response - extract JSON from response if wrapped in text
            import json
            import re

            # Try to find JSON object in the response
            json_match = re.search(r"\{.*\}", response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                result: Dict[str, Any] = json.loads(json_str)
                return result
            else:
                raise ValueError("No JSON found in response")

        except Exception as e:
            if self.verbose:
                print(f"⚠️ LLM analysis failed: {e}, falling back to heuristics")
            # Fallback to simple heuristics
            return {
                "should_use_tools": True,
                "suggested_tools": [],
                "reasoning": "Fallback analysis",
                "context_complexity": "full",
            }

    async def _llm_infer_memory_key(
        self, query: str, requested_key: str, available_keys: List[str]
    ) -> Optional[str]:
        """Use LLM to infer the correct memory key based on user query and available keys."""  # noqa: E501

        analysis_prompt = f"""Given this user query: "{query}"
The LLM tried to access memory key: "{requested_key}"
Available memory keys: {available_keys}

Analyze which existing key contains the information the user wants, or if all entries should be shown. # noqa: E501

Important: You must choose from the AVAILABLE KEYS ONLY, not create new ones.

Common patterns:
- Location/city/address info is often in "address" key
- Personal details like age/name in "name" key
- Project config in "config" or similar keys
- Pet info in "cats", "pets", etc.

Respond with ONLY a JSON object:
{{
    "action": "exact_key" or "show_all",
    "key": "exact_key_name" or null,
    "reasoning": "brief explanation"
}}

Examples:
- Query: "what city do I live in?" with requested_key "city" and available keys ["name", "address", "cats"] # noqa: E501
  -> {{"action": "exact_key", "key": "address", "reasoning": "City info would be stored in address key"}} # noqa: E501
- Query: "what is my project's configuration?" with available keys ["name", "project_config", "address"] # noqa: E501
  -> {{"action": "exact_key", "key": "project_config", "reasoning": "Question specifically asks for project configuration"}} # noqa: E501
- Query: "what do I have stored?" with any keys
  -> {{"action": "show_all", "key": null, "reasoning": "General query should show all entries"}}"""  # noqa: E501

        from .api_client import CompletionRequest

        request = CompletionRequest(
            model=self.model,
            messages=[{"role": "user", "content": analysis_prompt}],
            stream=False,
            options={"temperature": 0.0},
        )

        try:
            response_content = ""
            async for chunk in self.api_client.stream_chat(request):
                if chunk.content:
                    response_content += chunk.content

            # Parse JSON response
            import re

            json_match = re.search(r"\{.*\}", response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                result: Dict[str, Any] = json.loads(json_str)

                if result.get("action") == "exact_key":
                    return str(result.get("key", ""))
                elif result.get("action") == "show_all":
                    return "SHOW_ALL"

        except Exception as e:
            if self.verbose:
                print(f"❌ Error in memory key inference: {e}")

        return None

    async def _get_available_memory_keys(self, memory_type: str) -> List[str]:
        """Get list of available memory keys for the specified memory type."""
        try:
            # Direct file access to avoid recursion
            from pathlib import Path

            memory_dir = Path.home() / ".ocode" / "memory"
            if memory_type == "persistent":
                persistent_file = memory_dir / "persistent.json"
                if persistent_file.exists():
                    with open(persistent_file, "r") as f:
                        data = json.load(f)
                    return [k for k in data.keys() if k not in {"created", "updated"}]
        except Exception as e:
            if self.verbose:
                print(f"❌ Error getting memory keys: {e}")

        return []

    def _should_use_simple_context(
        self, query: str, llm_analysis: Dict[str, Any]
    ) -> bool:
        """Determine if query should use simple context based on LLM analysis.

        Args:
            query: User query (currently unused).
            llm_analysis: Analysis result from _llm_should_use_tools.

        Returns:
            True if simple context should be used, False for full context.
        """
        return bool(llm_analysis.get("context_complexity", "full") == "simple")

    def _build_context_message(
        self, context: ProjectContext, query: str, use_simple: bool = False
    ) -> str:
        """Build context message with project information.

        Creates a formatted message containing project context, query analysis,
        and guidance for the AI based on the query type.

        Args:
            context: Project context with files and metadata.
            query: User query string.
            use_simple: Whether to use simplified context format.

        Returns:
            Formatted context message string.
        """
        # Categorize the query to provide better context to the AI
        query_analysis = self.context_manager._categorize_query(query)
        query_category = query_analysis["category"]
        suggested_tools = query_analysis["suggested_tools"]
        confidence = query_analysis["confidence"]

        if use_simple:
            # Simple context for direct tool calls - make it explicit
            if any(
                keyword in query.lower()
                for keyword in ["remember", "save to memory", "recall"]
            ):
                return f"Use the memory_write function to: {query}"
            elif "list files" in query.lower() or "ls" in query.lower():
                return f"Use the ls function to: {query}"
            elif "git status" in query.lower() or "check git" in query.lower():
                return f"Use the git_status function to: {query}"
            else:
                return query

        lines = [
            f"Project: {context.project_root}",
            f"Query: {query}",
            f"Query Type: {query_category} (confidence: {confidence:.1f})",
            "",
        ]

        # Add suggested tools if available
        if suggested_tools:
            lines.extend([f"Suggested Tools: {', '.join(suggested_tools)}", ""])

        # Add specific guidance based on query type
        if query_analysis.get("multi_action", False):
            lines.extend(
                [
                    "GUIDANCE: This is a multi-action query requiring sequential operations:",  # noqa: E501
                    f"- Description: {query_analysis.get('description', 'Multiple sequential actions')}",  # noqa: E501
                    f"- Primary tools: {', '.join(query_analysis.get('primary_tools', []))}",  # noqa: E501
                    f"- Secondary tools: {', '.join(query_analysis.get('secondary_tools', []))}",  # noqa: E501
                    f"- Workflow: {query_analysis.get('workflow', 'sequential_actions')}",  # noqa: E501
                    "",
                    "RECOMMENDATION: Consider delegating this to specialized agents:",
                    "1. Create agents for each major task using the 'agent' tool",
                    "2. Delegate primary task first, then secondary tasks",
                    "3. Or execute tools in sequence if appropriate",
                    "",
                ]
            )
        elif query_category == "agent_management":
            lines.extend(
                [
                    "GUIDANCE: This is an agent management query. Use the 'agent' tool with appropriate actions:",  # noqa: E501
                    "- To create agents: action='create', agent_type='reviewer'|'coder'|'tester'|etc",  # noqa: E501
                    "- To list agents: action='list'",
                    "- To check status: action='status'",
                    "- To delegate tasks: action='delegate', task_description='...'",
                    "Do NOT create Python files or shell scripts for agent management.",
                    "",
                ]
            )
        elif query_category == "tool_listing":
            lines.extend(
                [
                    "GUIDANCE: User is asking about available tools. Provide a comprehensive list of all tools with descriptions.",  # noqa: E501
                    "",
                ]
            )
        elif query_category.startswith("workflow_"):
            lines.extend(
                [
                    "GUIDANCE: This is a complex workflow. Consider using multiple tools in sequence:",  # noqa: E501
                    f"- Suggested workflow tools: {', '.join(suggested_tools)}",
                    "- Start with analysis tools, then proceed with implementation",
                    "",
                ]
            )
        elif suggested_tools:
            lines.extend(
                [
                    f"GUIDANCE: For this {query_category} task, consider using: {', '.join(suggested_tools)}",  # noqa: E501
                    "",
                ]
            )

        # Add git information
        if context.git_info:
            lines.extend(
                [
                    "Git Information:",
                    f"  Branch: {context.git_info.get('branch', 'unknown')}",
                    f"  Commit: {context.git_info.get('commit', 'unknown')}",
                    "",
                ]
            )

        # Add file summaries
        if context.files:
            lines.append("Relevant Files:")
            for file_path, content in context.files.items():
                file_info = context.file_info.get(file_path)
                if file_info:
                    symbols_info = (
                        f" ({len(file_info.symbols)} symbols)"
                        if file_info.symbols
                        else ""
                    )
                    language_info = (
                        f" [{file_info.language}]" if file_info.language else ""
                    )
                    lines.append(f"  {file_path}{language_info}{symbols_info}")
                else:
                    lines.append(f"  {file_path}")
            lines.append("")

        # Add symbol index
        if context.symbols:
            lines.append("Available Symbols:")
            for symbol, files in list(context.symbols.items())[
                :20
            ]:  # Limit to first 20
                file_list = ", ".join(str(f.name) for f in files[:3])
                if len(files) > 3:
                    file_list += f" (+{len(files) - 3} more)"
                lines.append(f"  {symbol}: {file_list}")
            lines.append("")

        return "\n".join(lines)

    def _prepare_messages(
        self,
        query: str,
        context: ProjectContext,
        llm_analysis: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, str]]:
        """Prepare message history for API call.

        Constructs the message list including system prompt, conversation
        history, and current query with appropriate context.

        Args:
            query: Current user query.
            context: Project context information.
            llm_analysis: Optional analysis of whether to use tools.

        Returns:
            List of message dictionaries ready for API submission.
        """
        messages = []

        # Use provided LLM analysis or fallback to heuristics
        if llm_analysis:
            use_simple_context = self._should_use_simple_context(query, llm_analysis)
        else:
            query_analysis = self.context_manager._categorize_query(query)
            use_simple_context = query_analysis.get("context_strategy") == "minimal"

        # System message - adapt based on whether tools will be used
        should_use_tools = (
            llm_analysis.get("should_use_tools", True) if llm_analysis else True
        )

        if not should_use_tools:
            # Direct knowledge response system prompt
            system_content = """You are an expert AI coding assistant with deep knowledge of programming languages, software engineering concepts, algorithms, and best practices. # noqa: E501

Provide clear, comprehensive explanations using your knowledge. Since this is a general knowledge question, you should answer directly without using any tools. # noqa: E501

Focus on:
- Clear explanations with examples
- Practical insights and best practices
- Code examples when relevant
- Step-by-step breakdowns for complex topics
- Comparisons and trade-offs when appropriate

Be educational and thorough in your response."""
        elif use_simple_context:
            # Simple system prompt for direct tool calls with examples
            system_content = """You are an AI assistant with access to function calling tools. Use them when appropriate. # noqa: E501

Examples:
- User: "Remember my name is John" -> Call memory_write function
- User: "List files" -> Call ls function
- User: "What's in my memory?" -> Call memory_read function
- User: "Show first 5 lines of file.txt" -> Call head function

When a user asks you to perform an action, call the appropriate function."""
        else:
            # Full enhanced system prompt with context awareness
            base_prompt = self._build_system_prompt()

            # Add examples to the prompt
            enhanced_prompt = self._add_examples_to_system_prompt(base_prompt)

            # Add project context guidance if available
            if context:
                enhanced_prompt = self._add_project_context_guidance(
                    enhanced_prompt, context
                )

            system_content = enhanced_prompt

        messages.append({"role": "system", "content": system_content})

        # Add conversation history (less for simple context)
        history_limit = 3 if use_simple_context else 10
        for msg in self.conversation_history[-history_limit:]:
            messages.append(msg.to_dict())

        # Context and current query
        context_message = self._build_context_message(
            context, query, use_simple_context
        )
        messages.append({"role": "user", "content": context_message})

        if self.verbose and use_simple_context:
            print("🎯 Using simple context for direct tool call")

        return messages

    def _map_tool_name(self, function_name: str) -> str:
        """Map function definition names to registry names.

        Converts camelCase function names to snake_case for registry lookup.
        This ensures consistency between tool names in function calls
        and the tool registry.

        Args:
            function_name: Name from function call (may be camelCase).

        Returns:
            snake_case name for registry lookup.
        """
        import re

        # Convert camelCase to snake_case
        # e.g., "memoryWrite" -> "memory_write", "gitStatus" -> "git_status"
        snake_case = re.sub(r"([a-z0 - 9])([A-Z])", r"\1_\2", function_name)
        return snake_case.lower()

    async def _execute_tool_call(
        self, tool_name: str, arguments: Dict[str, Any], query: Optional[str] = None
    ) -> ToolResult:
        """Execute a tool call and return the result.

        Handles tool execution with smart defaults for memory operations,
        confirmation requests for dangerous commands, and error handling.
        Uses the AdvancedOrchestrator when available for enhanced execution.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Arguments to pass to the tool.
            query: Optional original query for context.

        Returns:
            ToolResult with success status, output, and any errors.
        """
        # Ensure asyncio-dependent components are initialized
        await self._ensure_components_initialized()

        if self.verbose:
            print(f"🔧 Executing tool: {tool_name}")
            print(f"📋 Arguments: {arguments}")

        # Map function name to registry name
        registry_name = self._map_tool_name(tool_name)

        # Add smart defaults for memory operations
        if registry_name == "memory_write":
            # Default to persistent memory for profile-style facts
            if "memory_type" not in arguments:
                arguments["memory_type"] = "persistent"
            # Default operation to "set" if not specified
            if "operation" not in arguments:
                arguments["operation"] = "set"

            # Special handling for lobotomize/clear commands
            if "operation" in arguments and arguments["operation"] in [
                "lobotomize",
                "clear",
            ]:
                # For destructive operations, remove unnecessary parameters
                arguments.pop("key", None)
                arguments.pop("value", None)
                arguments.pop("category", None)
        elif registry_name == "memory_read":
            # Smart defaults based on query context
            if "memory_type" not in arguments:
                arguments["memory_type"] = "persistent"
            # Override session memory for profile-style questions
            elif arguments.get("memory_type") == "session" and not arguments.get(
                "session_id"
            ):
                # Default to persistent for general profile questions
                arguments["memory_type"] = "persistent"

            # Smart key inference for memory queries using LLM
            if "key" in arguments and arguments["key"]:
                # Get keys for the specified memory type, defaulting to persistent
                memory_type_for_keys = arguments.get("memory_type", "persistent")
                if memory_type_for_keys == "all":
                    memory_type_for_keys = (
                        "persistent"  # Use persistent keys for 'all' queries
                    )

                available_keys = await self._get_available_memory_keys(
                    memory_type_for_keys
                )
                if available_keys:  # Only if we have keys to work with
                    corrected_key = await self._llm_infer_memory_key(
                        query=query or "",
                        requested_key=arguments["key"],
                        available_keys=available_keys,
                    )

                    if corrected_key == "SHOW_ALL":
                        arguments.pop("key", None)  # Remove key filter to show all
                        arguments.pop("category", None)  # Also remove category filter
                    elif corrected_key and corrected_key in available_keys:
                        arguments["key"] = corrected_key
                        # Remove category filter when using corrected key to avoid mismatches # noqa: E501
                        arguments.pop("category", None)
                        # For profile queries, prefer persistent over 'all' for cleaner output # noqa: E501
                        if arguments.get("memory_type") == "all":
                            arguments["memory_type"] = "persistent"

            # Debug logging for memory read calls
            if self.verbose:
                print(f"Memory read arguments: {arguments}")

        try:
            # Use advanced orchestrator if available for enhanced tool execution
            if self.orchestrator:
                # Execute through orchestrator for priority queuing and side effects
                result = await self.orchestrator.execute_tool_with_context(
                    tool_name=registry_name,
                    arguments=arguments,
                    context={"query": query, "engine": self},
                )
            else:
                # Fallback to direct tool registry execution
                result = await self.tool_registry.execute_tool(
                    registry_name, **arguments
                )

            # Handle confirmation requests for shell commands
            if (
                not result.success
                and result.error == "confirmation_required"
                and result.metadata
                and result.metadata.get("requires_confirmation")
            ):

                confirmation_payload = result.metadata
                command = confirmation_payload.get("command", "")
                reason = confirmation_payload.get("reason", "")

                # Request user confirmation
                confirmed = await self._request_user_confirmation(command, reason)

                if confirmed:
                    # Re-execute with confirmation
                    arguments["confirmed"] = True
                    if self.orchestrator:
                        result = await self.orchestrator.execute_tool_with_context(
                            tool_name=registry_name,
                            arguments=arguments,
                            context={"query": query, "engine": self},
                        )
                    else:
                        result = await self.tool_registry.execute_tool(
                            registry_name, **arguments
                        )
                else:
                    result = ToolResult(
                        success=False, output="", error="Command cancelled by user"
                    )

            if self.verbose:
                if result.success:
                    print(f"✅ Tool {tool_name} completed successfully")
                else:
                    print(f"❌ Tool {tool_name} failed: {result.error}")

            return result

        except Exception as e:
            if self.verbose:
                print(f"💥 Tool {tool_name} crashed: {str(e)}")

            return ToolResult(
                success=False, output="", error=f"Tool execution failed: {str(e)}"
            )

    async def _request_user_confirmation(self, command: str, reason: str) -> bool:
        """Request user confirmation for potentially dangerous commands.

        Uses the configured confirmation callback if available.
        In API contexts without a callback, denies by default for safety.

        Args:
            command: The command requiring confirmation.
            reason: Explanation of why confirmation is needed.

        Returns:
            True if confirmed, False otherwise.
        """
        if self.confirmation_callback:
            try:
                return bool(await self.confirmation_callback(command, reason))
            except Exception as e:
                if self.verbose:
                    print(f"Confirmation callback failed: {e}")
                return False
        else:
            # No confirmation callback available - this could be an API context
            # In API contexts, the calling application should handle confirmation
            # Deny for safety unless confirmed parameter is explicitly set
            if self.verbose:
                print(
                    f"⚠️  Command requires confirmation but no callback available: {command}"  # noqa: E501
                )
                print(f"Reason: {reason}")
                print(
                    "API contexts should re-call with confirmed=True after user approval"  # noqa: E501
                )
            return False

    def _should_continue_response(
        self,
        chunk_done: bool,
        response_content: str,
        total_tokens: int = 0,
        max_tokens: int = 4096,
    ) -> bool:
        """
        Determine if we should continue the response based on API signals and content analysis. # noqa: E501

        Args:
            chunk_done: Whether the API indicated the stream is done
            response_content: The actual response content to analyze
            total_tokens: Total tokens generated so far (if available)
            max_tokens: Maximum tokens before forcing continuation

        Returns:
            True if we should continue, False if response is complete
        """
        # If we have very little content and API says done, it might be truncated
        if chunk_done and len(response_content.strip()) < 200:
            return True

        # If response ends abruptly mid-sentence, continue
        if chunk_done and response_content.strip():
            last_char = response_content.strip()[-1]
            if last_char not in ".!?":
                # Check if it looks like it was cut off
                lines = response_content.strip().split("\n")
                last_line = lines[-1].strip() if lines else ""
                if len(last_line) > 10 and not last_line.endswith(
                    (".", "!", "?", ":", ")")
                ):
                    return True

        # If we've hit token limits, we may need to continue
        if total_tokens > 0 and total_tokens >= max_tokens * 0.9:  # 90% of max tokens
            return True

        # Default to not continuing
        return False

    async def process(
        self, query: str, continue_previous: bool = False
    ) -> AsyncGenerator[str, None]:
        """
        Process a user query through the complete AI workflow pipeline.

        This is the main entry point that orchestrates the entire processing flow:
        1. Query preprocessing and continuation handling
        2. Project context analysis and preparation
        3. AI-driven tool usage decision making
        4. Message preparation with appropriate context
        5. Streaming response generation with tool execution
        6. Automatic continuation for incomplete responses

        The method uses an async generator pattern to stream responses in real-time,
        providing immediate feedback while processing complex workflows.

        Args:
            query: User's natural language query or command. Can be anything from
                   simple questions to complex multi-step requests.
            continue_previous: Whether to continue from a previous incomplete response.
                              This allows handling of responses that were cut off due
                              to token limits or connection issues.

        Yields:
            str: Response chunks as they are generated. Chunks may contain:
                 - Natural language responses from the AI
                 - Tool execution results and outputs
                 - Progress indicators and status messages
                 - Error messages and warnings

        Raises:
            Exception: Various exceptions may be raised for API failures,
                      tool execution errors, or context preparation issues.
        """
        metrics = ProcessingMetrics(start_time=time.time())

        try:
            # Handle continuation if enabled
            if continue_previous and self.current_response:
                query = f"Continue from: {self.current_response[-200:]}\n\n{query}"
                self.current_response = ""
                self.response_complete = False

            # Add user message to conversation history
            self.conversation_history.append(Message("user", query))

            # Prepare context
            context = await self._prepare_context(query)
            metrics.files_analyzed = len(context.files)

            # Analyze if tools should be used
            llm_analysis = await self._llm_should_use_tools(query)

            if self.verbose:
                print(f"🤖 LLM Analysis: {llm_analysis.get('reasoning', '')}")
                if llm_analysis.get("suggested_tools"):
                    print(
                        f"🔧 Suggested tools: {', '.join(llm_analysis['suggested_tools'])}"  # noqa: E501
                    )

            # Prepare messages for API
            messages = self._prepare_messages(query, context, llm_analysis)

            # Add tools to request if tools should be used
            tools = None
            if llm_analysis.get("should_use_tools", False):
                use_simple_context = self._should_use_simple_context(
                    query, llm_analysis
                )
                if use_simple_context and llm_analysis.get("suggested_tools"):
                    # For simple context, only include suggested tools to avoid confusion # noqa: E501
                    suggested_tool_names = llm_analysis.get("suggested_tools", [])
                    tools = []
                    for tool_name in suggested_tool_names:
                        tool = self.tool_registry.get_tool(tool_name)
                        if tool:
                            tools.append(tool.definition.to_ollama_format())
                else:
                    # For complex context, include all tools
                    tools = self.tool_registry.get_tool_definitions()
            else:
                if self.verbose:
                    print("💭 Direct knowledge response - no tools needed")

            # Make API request
            request = CompletionRequest(
                model=self.model,
                messages=messages,
                stream=True,
                tools=tools,
                options={
                    "temperature": 0.7,
                    "max_tokens": 32768,  # Increased from 4096
                    "top_p": 0.95,
                    "frequency_penalty": 0.0,
                    "presence_penalty": 0.0,
                },
            )

            # Process streaming response with continuation support
            chunk_buffer = ""
            chunk_size = self.chunk_size
            continuation_count = 0
            max_continuations = self.max_continuations
            last_response_length = 0  # Track response growth to detect loops

            while continuation_count <= max_continuations:
                try:
                    async for chunk in self.api_client.stream_chat(request):
                        if chunk.tool_call:
                            # Handle tool call
                            tool_name = self._map_tool_name(chunk.tool_call.name)
                            if self.tool_registry.get_tool(tool_name):
                                try:
                                    result = await self._execute_tool_call(
                                        tool_name, chunk.tool_call.arguments, query
                                    )
                                    yield f"\n🔧 Tool: {tool_name}\n{result.output}\n"
                                    metrics.tools_executed += 1
                                    # After tool execution, mark response as complete
                                    self.response_complete = True
                                except Exception as e:
                                    yield f"\n⚠️ Tool error: {str(e)}\n"
                                    self.response_complete = True
                            else:
                                yield f"\n⚠️ Unknown tool: {tool_name}\n"
                                self.response_complete = True
                        elif chunk.content:
                            # Handle regular content
                            chunk_buffer += chunk.content
                            self.current_response += chunk.content

                            # Yield when buffer is full
                            if len(chunk_buffer) >= chunk_size:
                                metrics.tokens_processed += len(chunk_buffer.split())
                                yield chunk_buffer
                                chunk_buffer = ""
                        elif chunk.done:
                            # Handle completion
                            if chunk_buffer:
                                yield chunk_buffer
                                metrics.tokens_processed += len(chunk_buffer.split())

                            # Check if we should continue based on API signals
                            total_tokens = metrics.tokens_processed
                            should_continue = self._should_continue_response(
                                chunk_done=True,  # API says it's done
                                response_content=self.current_response,
                                total_tokens=total_tokens,
                            )

                            if (
                                should_continue
                                and continuation_count < max_continuations
                            ):
                                # Check for infinite loop (no response growth)
                                current_length = len(self.current_response)
                                if (
                                    current_length <= last_response_length + 50
                                ):  # Minimal growth threshold
                                    if self.verbose:
                                        print(
                                            "\n⚠️ Stopping continuation: minimal response growth detected"  # noqa: E501
                                        )
                                    self.response_complete = True
                                    break

                                last_response_length = current_length
                                continuation_count += 1

                                if self.verbose:
                                    print(
                                        f"\n🔄 Auto-continuing response (attempt {continuation_count}/{max_continuations})"  # noqa: E501
                                    )
                                    response_len = len(self.current_response.strip())
                                    last_chars = (
                                        self.current_response.strip()[-50:]
                                        if response_len > 50
                                        else self.current_response.strip()
                                    )
                                    print(
                                        f"🔄 Response length: {response_len} chars, ending with: ...{last_chars}"  # noqa: E501
                                    )
                                    if response_len < 200:
                                        print(
                                            f"🔄 Reason: Response too short ({response_len} chars)"  # noqa: E501
                                        )
                                    elif total_tokens >= 4096 * 0.9:
                                        print(
                                            f"🔄 Reason: Token limit reached ({total_tokens} tokens)"  # noqa: E501
                                        )
                                    else:
                                        print("🔄 Reason: Response appears truncated")

                                # Prepare continuation request
                                continuation_query = f"Continue from where you left off. Previous content ended with: {self.current_response[-200:]}"  # noqa: E501
                                messages = self._prepare_messages(
                                    continuation_query, context, llm_analysis
                                )
                                request = CompletionRequest(
                                    model=self.model,
                                    messages=messages,
                                    stream=True,
                                    tools=tools,
                                    options={
                                        "temperature": 0.7,
                                        "max_tokens": 32768,
                                        "top_p": 0.95,
                                        "frequency_penalty": 0.0,
                                        "presence_penalty": 0.0,
                                    },
                                )
                                # Break out of the inner chunk loop to restart with new request # noqa: E501
                                break
                            else:
                                # No continuation needed, mark as complete
                                self.response_complete = True
                                break

                    # If we get here, either we completed or need to continue
                    if self.response_complete:
                        break

                except Exception as e:
                    if self.verbose:
                        print(f"⚠️ Stream error: {str(e)}")
                    yield f"\nStream error: {str(e)}\n"
                    break

        except Exception as e:
            if self.verbose:
                print(f"⚠️ Error: {str(e)}")
            yield f"\nError: {str(e)}\n"
        finally:
            metrics.end_time = time.time()
            if self.verbose:
                print(
                    f"\n📊 Metrics: {metrics.duration:.1f}s, {metrics.tokens_processed} tokens, {metrics.files_analyzed} files, {metrics.tools_executed} tools\n"  # noqa: E501
                )

            # Add assistant response to conversation history
            if self.current_response:
                self.conversation_history.append(
                    Message("assistant", self.current_response)
                )

    def is_response_complete(self) -> bool:
        """Check if the current response is complete.

        Returns:
            True if the response has been marked as complete.
        """
        return self.response_complete

    def get_current_response(self) -> str:
        """Get the current response content.

        Returns:
            The accumulated response text.
        """
        return self.current_response

    async def continue_session(self, session_id: Optional[str] = None) -> bool:
        """Continue a previous session.

        Loads a saved session and restores its conversation history.

        Args:
            session_id: ID of the session to continue.

        Returns:
            True if session was loaded successfully, False otherwise.
        """
        if session_id:
            session = await self.session_manager.load_session(session_id)
            if session:
                self.conversation_history = session.messages
                return True
        return False

    async def save_session(self, session_id: Optional[str] = None) -> str:
        """Save current session.

        Persists the current conversation history and context.

        Args:
            session_id: Optional ID to save as (creates new if None).

        Returns:
            The session ID that was saved.
        """
        return await self.session_manager.save_session(
            messages=self.conversation_history,
            context=self.current_context,
            session_id=session_id,
        )

    def clear_context(self) -> None:
        """Clear current context and conversation history.

        Resets the engine to a clean state for a new conversation.
        """
        self.current_context = None
        self.conversation_history = []

    def get_status(self) -> Dict[str, Any]:
        """Get current engine status.

        Returns:
            Dictionary containing:
            - model: Current model name
            - context_files: Number of files in context
            - conversation_length: Number of messages
            - tools_available: Number of registered tools
            - project_root: Current project root path
        """
        return {
            "model": self.model,
            "context_files": (
                len(self.current_context.files) if self.current_context else 0
            ),
            "conversation_length": len(self.conversation_history),
            "tools_available": len(self.tool_registry.tools),
            "project_root": str(self.context_manager.root),
            "orchestrator_enabled": self.orchestrator is not None,
            "stream_processor_enabled": self.stream_processor is not None,
            "semantic_context_enabled": self.semantic_context_builder is not None,
            "dynamic_context_enabled": self.dynamic_context_manager is not None,
        }

    async def start_orchestrator(self) -> None:
        """Start the advanced orchestrator if available."""
        await self._ensure_components_initialized()
        if self.orchestrator:
            await self.orchestrator.start()
            if self.verbose:
                print("🚀 Advanced orchestrator started")

    async def stop_orchestrator(self) -> None:
        """Stop the advanced orchestrator if available."""
        await self._ensure_components_initialized()
        if self.orchestrator:
            await self.orchestrator.stop()
            if self.verbose:
                print("🛑 Advanced orchestrator stopped")

    async def cleanup_architecture_components(self) -> None:
        """Clean up all architecture components."""
        await self._ensure_components_initialized()
        # Clean up stream processor
        if self.stream_processor:
            try:
                await self.stream_processor.cleanup()
                if self.verbose:
                    print("🧹 Stream processor cleaned up")
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Stream processor cleanup error: {e}")

        # Clean up orchestrator
        await self.stop_orchestrator()

        # Other components don't need explicit cleanup but we could add logging
        if self.verbose and (
            self.semantic_context_builder or self.dynamic_context_manager
        ):
            print("🧹 Architecture components cleaned up")

    async def __aenter__(self):
        """Async context manager entry - start orchestrator."""
        await self.start_orchestrator()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup all architecture components."""
        await self.cleanup_architecture_components()


async def main() -> None:
    """Example usage of OCodeEngine."""
    engine = OCodeEngine(verbose=True)

    query = "Show me the main components of this project and explain the architecture"

    print("Processing query...")
    async for chunk in engine.process(query):
        print(chunk, end="", flush=True)

    print("\n\nEngine status:", engine.get_status())


if __name__ == "__main__":
    asyncio.run(main())
