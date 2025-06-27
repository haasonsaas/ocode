"""
Error Recovery System - Self-Improving Agent Architecture

This module implements automated error recovery capabilities that enable the agent
to analyze tool failures and propose intelligent recovery strategies. It builds on
the existing RetryManager and extends it with context-aware debugging personas.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..prompts.prompt_composer import PromptComposer
from ..tools.base import ToolResult
from .api_client import CompletionRequest, OllamaAPIClient

if TYPE_CHECKING:
    from .orchestrator import CommandTask


logger = logging.getLogger(__name__)


class RecoveryStrategyType(Enum):
    """Types of recovery strategies the system can attempt."""

    PARAMETER_ADJUSTMENT = "parameter_adjustment"
    ALTERNATIVE_APPROACH = "alternative_approach"
    PERMISSION_ESCALATION = "permission_escalation"
    ENVIRONMENT_SETUP = "environment_setup"
    FALLBACK_TOOL = "fallback_tool"
    USER_INTERVENTION = "user_intervention"
    ABORT_GRACEFULLY = "abort_gracefully"


@dataclass
class FailureContext:
    """Rich context about a tool failure for analysis."""

    # Basic failure information
    original_goal: str
    failed_tool: str
    failed_command: "CommandTask"
    tool_result: ToolResult
    execution_context: Dict[str, Any]

    # Timing and environment
    timestamp: datetime = field(default_factory=datetime.now)
    working_directory: Optional[str] = None
    environment_vars: Dict[str, str] = field(default_factory=dict)

    # Previous attempts
    retry_count: int = 0
    previous_attempts: List[Dict[str, Any]] = field(default_factory=list)

    # Related context
    related_files: List[str] = field(default_factory=list)
    project_context: Optional[Dict[str, Any]] = None


@dataclass
class RecoveryStrategy:
    """A proposed strategy for recovering from a tool failure."""

    strategy_type: RecoveryStrategyType
    description: str
    confidence: float  # 0.0 to 1.0

    # Execution details
    new_tool: Optional[str] = None
    adjusted_parameters: Optional[Dict[str, Any]] = None
    alternative_commands: List["CommandTask"] = field(default_factory=list)
    prerequisite_steps: List["CommandTask"] = field(default_factory=list)

    # Metadata
    rationale: str = ""
    expected_outcome: str = ""
    risk_level: str = "low"  # low, medium, high
    estimated_success_rate: float = 0.5


class DebuggerPersona:
    """
    Specialized LLM persona for analyzing tool failures and proposing recovery strategies.

    This persona acts as an expert debugger that can:
    1. Analyze the context of tool failures
    2. Understand error patterns and root causes
    3. Propose intelligent recovery strategies
    4. Learn from successful and failed recovery attempts
    """

    def __init__(self, api_client: OllamaAPIClient, prompt_composer: PromptComposer):
        self.api_client = api_client
        self.prompt_composer = prompt_composer
        self.recovery_history: List[Dict[str, Any]] = []

    async def analyze_failure(
        self, failure_context: FailureContext
    ) -> List[RecoveryStrategy]:
        """
        Analyze a tool failure and propose recovery strategies.

        Args:
            failure_context: Rich context about the failure

        Returns:
            List of recovery strategies ordered by confidence
        """
        try:
            # Build analysis prompt
            analysis_prompt = self._build_analysis_prompt(failure_context)

            # Get LLM analysis
            messages = [{"role": "user", "content": analysis_prompt}]
            request = CompletionRequest(
                model="llama3.2:latest",  # Use a reliable model for analysis
                messages=messages,
                stream=False,
                options={"temperature": 0.1},  # Low temperature for consistent analysis
            )

            # Get response from stream_chat (since there's no complete method)
            response_content = ""
            async for chunk in self.api_client.stream_chat(request):
                if chunk.content:
                    response_content += chunk.content
                if chunk.done:
                    break

            # Create a simple response object
            class SimpleResponse:
                def __init__(self, content: str):
                    self.content = content

            response = SimpleResponse(response_content)

            # Parse recovery strategies from response
            strategies = self._parse_recovery_strategies(
                response.content, failure_context
            )

            # Log the analysis for learning
            self._log_analysis(failure_context, strategies, response.content)

            return strategies

        except Exception as e:
            logger.error(f"Error in failure analysis: {e}")
            # Return fallback strategy
            return [self._create_fallback_strategy(failure_context)]

    def _build_analysis_prompt(self, failure_context: FailureContext) -> str:
        """Build a specialized prompt for failure analysis."""

        # Get recent successful recoveries for context
        recent_successes = [
            entry
            for entry in self.recovery_history[-10:]
            if entry.get("recovery_successful", False)
        ]

        prompt = f"""<role>
You are an expert software engineering debugger and problem solver. Your job is to analyze tool execution failures and propose intelligent recovery strategies.
</role>

<task>
Analyze the following tool failure and propose specific, actionable recovery strategies. Focus on understanding the root cause and providing practical solutions.
</task>

<failure_context>
**Original Goal:** {failure_context.original_goal}

**Failed Tool:** {failure_context.failed_tool}

**Command Details:**
- Tool: {failure_context.failed_command.tool_name}
- Arguments: {json.dumps(failure_context.failed_command.arguments, indent=2)}

**Error Information:**
- Success: {failure_context.tool_result.success}
- Error Type: {failure_context.tool_result.metadata.get('error_type', 'unknown') if failure_context.tool_result.metadata else 'unknown'}
- Error Message: {failure_context.tool_result.error}
- Output: {failure_context.tool_result.output[:500]}...

**Execution Context:**
- Working Directory: {failure_context.working_directory}
- Retry Count: {failure_context.retry_count}
- Timestamp: {failure_context.timestamp}

**Additional Context:**
{json.dumps(failure_context.execution_context, indent=2)}
</failure_context>"""

        if recent_successes:
            prompt += f"""

<successful_recoveries>
Recent successful recovery patterns:
{json.dumps(recent_successes[-3:], indent=2)}
</successful_recoveries>"""

        prompt += """

<recovery_strategy_types>
Available recovery strategy types:
1. PARAMETER_ADJUSTMENT: Modify tool parameters (paths, options, formats)
2. ALTERNATIVE_APPROACH: Use different tools or methods to achieve the same goal
3. PERMISSION_ESCALATION: Address permission or access issues
4. ENVIRONMENT_SETUP: Install dependencies or configure environment
5. FALLBACK_TOOL: Switch to a more basic but reliable tool
6. USER_INTERVENTION: Request human assistance for complex issues
7. ABORT_GRACEFULLY: Clean up and fail gracefully when recovery isn't possible
</recovery_strategy_types>

<instructions>
Analyze the failure and respond with ONLY a JSON array of recovery strategies. Each strategy should include:

{
  "strategy_type": "one of the types above",
  "description": "clear description of what to do",
  "confidence": 0.8,
  "new_tool": "tool_name or null",
  "adjusted_parameters": {"param": "value"} or null,
  "alternative_commands": [{"tool_name": "tool", "arguments": {...}}] or [],
  "prerequisite_steps": [{"tool_name": "tool", "arguments": {...}}] or [],
  "rationale": "why this strategy should work",
  "expected_outcome": "what success looks like",
  "risk_level": "low/medium/high",
  "estimated_success_rate": 0.7
}

Order strategies by confidence (highest first). Provide 1-3 strategies.
</instructions>"""

        return prompt

    def _parse_recovery_strategies(
        self, response_content: str, failure_context: FailureContext
    ) -> List[RecoveryStrategy]:
        """Parse LLM response into RecoveryStrategy objects."""

        try:
            # Extract JSON from response
            strategies_data = json.loads(response_content.strip())

            if not isinstance(strategies_data, list):
                strategies_data = [strategies_data]

            strategies = []
            for data in strategies_data:
                try:
                    # Convert command dictionaries to CommandTask objects
                    # Import CommandTask at runtime to avoid circular import
                    from .orchestrator import CommandTask
                    from .orchestrator import Priority as OrchestratorPriority

                    alternative_commands = [
                        CommandTask(
                            task_id=str(uuid.uuid4()),
                            tool_name=cmd["tool_name"],
                            arguments=cmd["arguments"],
                            priority=OrchestratorPriority.NORMAL,
                        )
                        for cmd in data.get("alternative_commands", [])
                    ]

                    prerequisite_steps = [
                        CommandTask(
                            task_id=str(uuid.uuid4()),
                            tool_name=cmd["tool_name"],
                            arguments=cmd["arguments"],
                            priority=OrchestratorPriority.HIGH,  # Prerequisites should be high priority
                        )
                        for cmd in data.get("prerequisite_steps", [])
                    ]

                    strategy = RecoveryStrategy(
                        strategy_type=RecoveryStrategyType(data["strategy_type"]),
                        description=data["description"],
                        confidence=float(data["confidence"]),
                        new_tool=data.get("new_tool"),
                        adjusted_parameters=data.get("adjusted_parameters"),
                        alternative_commands=alternative_commands,
                        prerequisite_steps=prerequisite_steps,
                        rationale=data.get("rationale", ""),
                        expected_outcome=data.get("expected_outcome", ""),
                        risk_level=data.get("risk_level", "medium"),
                        estimated_success_rate=float(
                            data.get("estimated_success_rate", 0.5)
                        ),
                    )
                    strategies.append(strategy)

                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"Error parsing strategy: {e}, data: {data}")
                    continue

            return sorted(strategies, key=lambda s: s.confidence, reverse=True)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response content: {response_content}")
            return [self._create_fallback_strategy(failure_context)]

    def _create_fallback_strategy(
        self, failure_context: FailureContext
    ) -> RecoveryStrategy:
        """Create a basic fallback strategy when analysis fails."""

        return RecoveryStrategy(
            strategy_type=RecoveryStrategyType.PARAMETER_ADJUSTMENT,
            description="Retry with basic parameter adjustments",
            confidence=0.3,
            adjusted_parameters={"retry": True},
            rationale="Fallback strategy when analysis is unavailable",
            expected_outcome="May resolve transient issues",
            risk_level="low",
            estimated_success_rate=0.3,
        )

    def _log_analysis(
        self,
        failure_context: FailureContext,
        strategies: List[RecoveryStrategy],
        raw_response: str,
    ) -> None:
        """Log analysis for learning and debugging."""

        analysis_entry = {
            "timestamp": failure_context.timestamp.isoformat(),
            "failed_tool": failure_context.failed_tool,
            "error_type": (
                failure_context.tool_result.metadata.get("error_type")
                if failure_context.tool_result.metadata
                else None
            ),
            "strategies_proposed": len(strategies),
            "highest_confidence": strategies[0].confidence if strategies else 0.0,
            "analysis_success": True,
            "raw_response": raw_response[:1000],  # Truncate for storage
        }

        self.recovery_history.append(analysis_entry)

        # Keep only recent history to prevent memory bloat
        if len(self.recovery_history) > 100:
            self.recovery_history = self.recovery_history[-50:]

    def record_recovery_outcome(
        self,
        failure_context: FailureContext,
        attempted_strategy: RecoveryStrategy,
        recovery_successful: bool,
        final_result: Optional[ToolResult] = None,
    ) -> None:
        """Record the outcome of a recovery attempt for learning."""

        outcome_entry = {
            "timestamp": datetime.now().isoformat(),
            "original_failure": {
                "tool": failure_context.failed_tool,
                "error_type": (
                    failure_context.tool_result.metadata.get("error_type")
                    if failure_context.tool_result.metadata
                    else None
                ),
            },
            "strategy_attempted": {
                "type": attempted_strategy.strategy_type.value,
                "confidence": attempted_strategy.confidence,
                "description": attempted_strategy.description,
            },
            "recovery_successful": recovery_successful,
            "final_success": final_result.success if final_result else False,
        }

        self.recovery_history.append(outcome_entry)

        logger.info(
            f"Recovery attempt {'succeeded' if recovery_successful else 'failed'}: "
            f"{attempted_strategy.strategy_type.value} for {failure_context.failed_tool}"
        )


class ErrorRecoveryModule:
    """
    Coordinates error recovery attempts using the DebuggerPersona.

    This module integrates with the existing RetryManager to provide
    intelligent recovery strategies beyond simple retries.
    """

    def __init__(
        self, debugger_persona: DebuggerPersona, max_recovery_attempts: int = 2
    ):
        self.debugger_persona = debugger_persona
        self.max_recovery_attempts = max_recovery_attempts
        self.recovery_stats: Dict[str, Any] = {
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "strategy_usage": {},
        }

    async def attempt_recovery(
        self,
        original_goal: str,
        failed_command: "CommandTask",
        tool_result: ToolResult,
        execution_context: Dict[str, Any],
        tool_registry: Any,  # ToolRegistry type
    ) -> Optional[ToolResult]:
        """
        Attempt to recover from a tool failure.

        Args:
            original_goal: High-level goal being attempted
            failed_command: The command that failed
            tool_result: The failed result
            execution_context: Additional context about execution
            tool_registry: Registry to get tools for recovery

        Returns:
            ToolResult if recovery successful, None if all strategies failed
        """

        # Build failure context
        failure_context = FailureContext(
            original_goal=original_goal,
            failed_tool=failed_command.tool_name,
            failed_command=failed_command,
            tool_result=tool_result,
            execution_context=execution_context,
            working_directory=execution_context.get("working_dir"),
            retry_count=execution_context.get("retry_count", 0),
        )

        current_attempts = self.recovery_stats.get("attempts", 0)
        if isinstance(current_attempts, int):
            self.recovery_stats["attempts"] = current_attempts + 1

        try:
            # Get recovery strategies from debugger persona
            strategies = await self.debugger_persona.analyze_failure(failure_context)

            if not strategies:
                logger.warning("No recovery strategies proposed")
                return None

            # Attempt each strategy in order of confidence
            for strategy in strategies[: self.max_recovery_attempts]:
                recovery_result = await self._attempt_single_strategy(
                    strategy, failure_context, tool_registry, strategies
                )
                if recovery_result:
                    return recovery_result

            # All strategies failed
            current_failures = self.recovery_stats.get("failures", 0)
            if isinstance(current_failures, int):
                self.recovery_stats["failures"] = current_failures + 1
            logger.error("All recovery strategies failed")
            return None

        except Exception as e:
            current_failures = self.recovery_stats.get("failures", 0)
            if isinstance(current_failures, int):
                self.recovery_stats["failures"] = current_failures + 1
            logger.error(f"Error during recovery attempt: {e}")
            return None

    async def _attempt_single_strategy(
        self,
        strategy: RecoveryStrategy,
        failure_context: FailureContext,
        tool_registry: Any,
        strategies: List[RecoveryStrategy],
    ) -> Optional[ToolResult]:
        """Attempt a single recovery strategy."""
        logger.info(
            f"Attempting recovery strategy: {strategy.strategy_type.value} "
            f"(confidence: {strategy.confidence})"
        )

        # Track strategy usage
        self._track_strategy_usage(strategy)

        # Execute recovery strategy
        recovery_result = await self._execute_recovery_strategy(
            strategy, failure_context, tool_registry
        )

        # Record outcome
        recovery_successful = bool(recovery_result and recovery_result.success)
        self.debugger_persona.record_recovery_outcome(
            failure_context, strategy, recovery_successful, recovery_result
        )

        if recovery_successful:
            self._record_recovery_success(strategy)
            self._add_recovery_context(
                recovery_result, strategy, strategies, failure_context
            )
            return recovery_result
        else:
            logger.warning(f"Recovery strategy failed: {strategy.strategy_type.value}")
            return None

    def _track_strategy_usage(self, strategy: RecoveryStrategy) -> None:
        """Track usage of recovery strategies for analytics."""
        strategy_key = strategy.strategy_type.value
        strategy_usage = self.recovery_stats.get("strategy_usage", {})
        if isinstance(strategy_usage, dict):
            current_usage = strategy_usage.get(strategy_key, 0)
            if isinstance(current_usage, int):
                strategy_usage[strategy_key] = current_usage + 1
                self.recovery_stats["strategy_usage"] = strategy_usage

    def _record_recovery_success(self, strategy: RecoveryStrategy) -> None:
        """Record a successful recovery in stats."""
        current_successes = self.recovery_stats.get("successes", 0)
        if isinstance(current_successes, int):
            self.recovery_stats["successes"] = current_successes + 1
        logger.info(
            f"Recovery successful with strategy: {strategy.strategy_type.value}"
        )

    def _add_recovery_context(
        self,
        recovery_result: Optional[ToolResult],
        strategy: RecoveryStrategy,
        strategies: List[RecoveryStrategy],
        failure_context: FailureContext,
    ) -> None:
        """Add recovery context to the result."""
        if recovery_result and recovery_result.recovery_context is None:
            recovery_result.recovery_context = {}
        if recovery_result and recovery_result.recovery_context is not None:
            recovery_result.recovery_context.update(
                {
                    "recovery_applied": True,
                    "strategy_used": strategy.strategy_type.value,
                    "strategy_confidence": strategy.confidence,
                    "recovery_attempt": len(
                        [
                            s
                            for s in strategies[: self.max_recovery_attempts]
                            if s == strategy
                        ]
                    )
                    + 1,
                    "original_error": failure_context.tool_result.error,
                    "recovery_description": strategy.description,
                }
            )

    async def _execute_recovery_strategy(
        self,
        strategy: RecoveryStrategy,
        failure_context: FailureContext,
        tool_registry: Any,
    ) -> Optional[ToolResult]:
        """Execute a specific recovery strategy."""

        try:
            # Execute prerequisite steps first
            if not await self._execute_prerequisite_steps(strategy, tool_registry):
                return None

            # Execute the main recovery action
            return await self._execute_main_recovery_action(
                strategy, failure_context, tool_registry
            )

        except Exception as e:
            logger.error(f"Error executing recovery strategy: {e}")
            return None

    async def _execute_prerequisite_steps(
        self, strategy: RecoveryStrategy, tool_registry: Any
    ) -> bool:
        """Execute prerequisite steps for a recovery strategy."""
        for prereq_command in strategy.prerequisite_steps:
            tool = tool_registry.get_tool(prereq_command.tool_name)
            if not tool:
                logger.error(f"Prerequisite tool not found: {prereq_command.tool_name}")
                return False

            prereq_result = await tool.execute(**prereq_command.arguments)
            if not prereq_result.success:
                logger.warning(f"Prerequisite step failed: {prereq_command.tool_name}")
                # Continue anyway - some prerequisites might be optional
        return True

    async def _execute_main_recovery_action(
        self,
        strategy: RecoveryStrategy,
        failure_context: FailureContext,
        tool_registry: Any,
    ) -> Optional[ToolResult]:
        """Execute the main recovery action based on strategy type."""
        if strategy.alternative_commands:
            return await self._try_alternative_commands(strategy, tool_registry)
        elif strategy.new_tool:
            return await self._try_new_tool(strategy, failure_context, tool_registry)
        elif strategy.adjusted_parameters:
            return await self._try_adjusted_parameters(
                strategy, failure_context, tool_registry
            )
        else:
            logger.warning("Recovery strategy has no executable actions")
            return None

    async def _try_alternative_commands(
        self, strategy: RecoveryStrategy, tool_registry: Any
    ) -> Optional[ToolResult]:
        """Try alternative command sequence."""
        for alt_command in strategy.alternative_commands:
            tool = tool_registry.get_tool(alt_command.tool_name)
            if not tool:
                logger.error(f"Alternative tool not found: {alt_command.tool_name}")
                continue

            result: ToolResult = await tool.execute(**alt_command.arguments)
            if result.success:
                return result
            # If this alternative failed, try the next one

        return None  # All alternatives failed

    async def _try_new_tool(
        self,
        strategy: RecoveryStrategy,
        failure_context: FailureContext,
        tool_registry: Any,
    ) -> Optional[ToolResult]:
        """Try using a different tool."""
        tool = tool_registry.get_tool(strategy.new_tool)
        if not tool:
            logger.error(f"Recovery tool not found: {strategy.new_tool}")
            return None

        # Use adjusted parameters or original arguments
        args = strategy.adjusted_parameters or failure_context.failed_command.arguments
        result: ToolResult = await tool.execute(**args)
        return result

    async def _try_adjusted_parameters(
        self,
        strategy: RecoveryStrategy,
        failure_context: FailureContext,
        tool_registry: Any,
    ) -> Optional[ToolResult]:
        """Try original tool with adjusted parameters."""
        tool = tool_registry.get_tool(failure_context.failed_tool)
        if not tool:
            logger.error(f"Original tool not found: {failure_context.failed_tool}")
            return None

        # Merge adjusted parameters with original arguments
        original_args = failure_context.failed_command.arguments.copy()
        if strategy.adjusted_parameters:
            original_args.update(strategy.adjusted_parameters)

        result: ToolResult = await tool.execute(**original_args)
        return result

    def get_recovery_stats(self) -> Dict[str, Any]:
        """Get statistics about recovery attempts."""

        total_attempts = self.recovery_stats.get("attempts", 0)
        successes = self.recovery_stats.get("successes", 0)
        success_rate = 0.0
        if (
            isinstance(total_attempts, int)
            and isinstance(successes, int)
            and total_attempts > 0
        ):
            success_rate = successes / total_attempts

        strategy_usage = self.recovery_stats.get("strategy_usage", {})
        most_used_strategies = []
        if isinstance(strategy_usage, dict):
            most_used_strategies = sorted(
                strategy_usage.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5]

        return {
            **self.recovery_stats,
            "success_rate": success_rate,
            "most_used_strategies": most_used_strategies,
        }
