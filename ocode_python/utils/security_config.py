"""
Security configuration management for shell command validation.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class SecurityPatterns:
    """Security patterns configuration."""

    absolute_blocked: List[str]
    requires_confirmation: List[str]
    redirection_blocked: List[str]
    command_chaining_blocked: List[str]
    safe_pipe_exceptions: List[str]
    confirmation_timeout: int

    def __post_init__(self) -> None:
        """Compile regex patterns for performance."""
        self._absolute_blocked_regex = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.absolute_blocked
        ]
        self._requires_confirmation_regex = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.requires_confirmation
        ]
        self._redirection_blocked_regex = [
            re.compile(pattern) for pattern in self.redirection_blocked
        ]
        self._command_chaining_blocked_regex = [
            re.compile(pattern) for pattern in self.command_chaining_blocked
        ]
        self._safe_pipe_exceptions_regex = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.safe_pipe_exceptions
        ]


class SecurityConfigManager:
    """Manages security patterns for shell command validation."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """Initialize security config manager."""
        if config_path is None:
            config_path = (
                Path(__file__).parent.parent / "config" / "security_patterns.json"
            )

        self.config_path = config_path
        self._patterns: Optional[SecurityPatterns] = None

    def _load_config(self) -> SecurityPatterns:
        """Load security patterns from JSON configuration."""
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)

            patterns = config["patterns"]
            settings = config["settings"]

            return SecurityPatterns(
                absolute_blocked=patterns["absolute_blocked"]["patterns"],
                requires_confirmation=patterns["requires_confirmation"]["patterns"],
                redirection_blocked=patterns["redirection_blocked"]["patterns"],
                command_chaining_blocked=patterns["command_chaining_blocked"][
                    "patterns"
                ],
                safe_pipe_exceptions=config["safe_pipe_exceptions"]["patterns"],
                confirmation_timeout=settings["confirmation_timeout_seconds"],
            )

        except (FileNotFoundError, KeyError, json.JSONDecodeError):
            # Fallback to hardcoded patterns if config file is missing/invalid
            return SecurityPatterns(
                absolute_blocked=[
                    "rm -rf /",
                    "dd if=",
                    "mkfs",
                    "fdisk",
                    "mount",
                    "umount",
                    "sudo rm",
                    "sudo dd",
                    r"curl.*\|\s*bash",
                    r"wget.*\|\s*bash",
                    r"\$\(",
                    "`",
                    r"&&\s*(rm|dd|mkfs)",
                    r"||\s*(rm|dd|mkfs)",
                ],
                requires_confirmation=[
                    r"\|",
                    r"grep\s",
                    r"sort\s",
                    r"wc\s",
                    r"curl\s",
                    r"wget\s",
                    r"tar\s",
                    r"chmod\s",
                    r"chown\s",
                    r"rm\s",
                    r"mv\s",
                    r"cp\s.*-r",
                ],
                redirection_blocked=[">", ">>", "2>", "&>"],
                command_chaining_blocked=[";", "&&", "||"],
                safe_pipe_exceptions=[
                    r"\|\s*wc\s+-l",
                    r"\|\s*head\s",
                    r"\|\s*tail\s",
                    r"\|\s*sort$",
                    r"\|\s*uniq$",
                    r"\|\s*cat$",
                ],
                confirmation_timeout=30,
            )

    @property
    def patterns(self) -> SecurityPatterns:
        """Return cached security patterns, loading if necessary.

        Returns:
            SecurityPatterns: The loaded security patterns
        """
        if self._patterns is None:
            self._patterns = self._load_config()
        return self._patterns

    def reload(self) -> None:
        """Reload configuration from file."""
        self._patterns = None

    def validate_command(self, command: str) -> Tuple[str, Optional[str], bool]:
        """
        Validate a shell command against security patterns.

        Returns:
            tuple: (status, reason, requires_confirmation)
            - status: "allowed", "blocked", "requires_confirmation"
            - reason: Description of why the command was flagged
            - requires_confirmation: True if user confirmation is needed
        """
        patterns = self.patterns

        # Check for absolutely blocked patterns first
        for regex in patterns._absolute_blocked_regex:
            if regex.search(command):
                return (
                    "blocked",
                    f"Command contains prohibited pattern: {regex.pattern}",
                    False,
                )

        # Check for redirection patterns
        for regex in patterns._redirection_blocked_regex:
            if regex.search(command):
                return (
                    "blocked",
                    f"Output redirection not permitted: {regex.pattern}",
                    False,
                )

        # Check for command chaining patterns
        for regex in patterns._command_chaining_blocked_regex:
            if regex.search(command):
                return (
                    "blocked",
                    f"Command chaining not permitted: {regex.pattern}",
                    False,
                )

        # Check if command has pipes - see if it's a safe exception
        if "|" in command:
            is_safe_pipe = any(
                regex.search(command) for regex in patterns._safe_pipe_exceptions_regex
            )
            if is_safe_pipe:
                return "allowed", None, False
            else:
                return "requires_confirmation", "Command uses pipes", True

        # Check for patterns requiring confirmation
        for regex in patterns._requires_confirmation_regex:
            if regex.search(command):
                return (
                    "requires_confirmation",
                    f"Command matches sensitive pattern: {regex.pattern}",
                    True,
                )

        return "allowed", None, False
