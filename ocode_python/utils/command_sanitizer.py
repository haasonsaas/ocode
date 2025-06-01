"""
Command sanitization utilities for shell execution safety.
"""

import platform
import re
import shlex
from typing import Dict, List, Optional, Tuple


class CommandSanitizer:
    """Comprehensive command sanitization for shell execution."""

    def __init__(self):
        """Initialize sanitizer with dangerous patterns."""

        # Patterns that should never be allowed - Unix patterns
        unix_patterns = [
            # System destruction
            r"\brm\s+-rf\s+/(?:\s|$)",
            r"\bsudo\s+rm\s+-rf",  # sudo rm -rf
            r"\bdd\s+.*of=/dev/[sh]d[a-z]",
            r"\bmkfs\.",
            r"\bfdisk\s+/dev/",
            # Fork bombs and resource exhaustion
            r":\(\)\s*\{.*:\|:&\s*\}",  # Classic fork bomb
            r"\.{0,2}/dev/zero",
            r"yes\s*\|",
            # Security bypasses
            r"\bsudo\s+-S",  # Reading sudo password from stdin
            r"echo.*\|\s*sudo",  # Piping to sudo
            r"/etc/shadow",
            r"/etc/sudoers",
            # Command substitution with dangerous commands
            r"\$\(.*rm\s+-rf",  # $(rm -rf ...)
            r"`.*rm\s+-rf",  # `rm -rf ...`
            # Network backdoors
            r"nc\s+-l.*-e\s*/bin/[bs]h",
            r"bash\s+-i.*>&.*<&",
            r"exec\s+\d+<>/dev/tcp/",
            # Kernel/system modification
            r"\binsmod\b",
            r"\brmmod\b",
            r"echo.*>/sys/",
            r"echo.*>/proc/sys/",
        ]

        # Windows-specific dangerous patterns
        windows_patterns = [
            # System destruction
            r"\bformat\s+[cC]:",
            r"\bdel\s+/[sS]\s+[cC]:\\\\",
            r"\brd\s+/[sS]\s+[cC]:\\\\",
            r"\brmdir\s+/[sS]\s+[cC]:\\\\",
            r"\bbcdedit\s",
            r"\bdiskpart\s",
            # Registry manipulation
            r"\breg\s+delete.*HKLM",
            r"\breg\s+delete.*HKEY_LOCAL_MACHINE",
            r"\bregsvr32\s+/u\s+/s",
            # Service manipulation
            r"\bsc\s+delete\s",
            r"\bnet\s+stop\s+.*critical",
            # Process termination
            r"\btaskkill\s+/[fF]\s+/[iI][mM]\s+.*\.exe",
            r"\btaskkill\s+/[fF]\s+/[tT]",
            # PowerShell dangerous commands
            r"Remove-Item.*-[rR]ecurse.*[cC]:\\\\",
            r"Get-WmiObject.*Win32_OperatingSystem.*Reboot",
            r"Stop-Computer\s+-Force",
            r"Restart-Computer\s+-Force",
            # Command substitution
            r"`.*del\s+/[sS]",
            r"\$\(.*Remove-Item.*-[rR]ecurse",
        ]

        # Combine patterns based on platform
        if platform.system() == "Windows":
            self.forbidden_patterns = unix_patterns + windows_patterns
        else:
            self.forbidden_patterns = unix_patterns

        # Commands that need careful validation
        self.restricted_commands = {
            "rm": self._validate_rm,
            "mv": self._validate_mv,
            "chmod": self._validate_chmod,
            "chown": self._validate_chown,
            "kill": self._validate_kill,
            "pkill": self._validate_pkill,
            "curl": self._validate_curl,
            "wget": self._validate_wget,
        }

    def sanitize_command(
        self, command: str, strict_mode: bool = True
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Sanitize a shell command for safe execution.

        Args:
            command: Command to sanitize
            strict_mode: If True, apply stricter validation rules

        Returns:
            Tuple of (is_safe, sanitized_command, error_message)
        """
        if not command or not command.strip():
            return False, "", "Empty command"

        # Basic length check
        if len(command) > 10000:
            return False, "", "Command too long (max 10000 characters)"

        # Check for null bytes
        if "\0" in command:
            return False, "", "Command contains null bytes"

        # Check forbidden patterns
        for pattern in self.forbidden_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return False, "", f"Command contains forbidden pattern: {pattern}"

        # Check for backticks (command substitution)
        if strict_mode and "`" in command:
            return False, "", "Backticks not allowed in strict mode (use $() instead)"

        # Parse command to check individual components
        try:
            # Split command respecting quotes and escapes
            parts = shlex.split(command)
            if not parts:
                return False, "", "Invalid command syntax"

            base_command = parts[0]

            # Check if command needs special validation
            if base_command in self.restricted_commands:
                is_valid, error = self.restricted_commands[base_command](parts)
                if not is_valid:
                    return False, "", error

            # Additional strict mode checks
            if strict_mode:
                # Check for suspicious redirections
                if self._has_dangerous_redirection(command):
                    return False, "", "Dangerous output redirection detected"

                # Check for command chaining abuse
                if self._has_dangerous_chaining(command):
                    return False, "", "Dangerous command chaining detected"

            # Command appears safe
            return True, command, None

        except ValueError as e:
            return False, "", f"Invalid command syntax: {str(e)}"

    def sanitize_environment(self, env: Dict[str, str]) -> Dict[str, str]:
        """
        Sanitize environment variables.

        Args:
            env: Environment variables to sanitize

        Returns:
            Sanitized environment variables
        """
        safe_env = {}

        # Dangerous environment variables to exclude
        dangerous_vars = {
            "LD_PRELOAD",  # Can hijack library loading
            "LD_LIBRARY_PATH",  # Can redirect library loading
            "PYTHONPATH",  # Can hijack Python imports
            "NODE_PATH",  # Can hijack Node imports
            "PERL5LIB",  # Can hijack Perl imports
            "RUBYLIB",  # Can hijack Ruby imports
            "IFS",  # Can change field separator
        }

        for key, value in env.items():
            # Skip dangerous variables
            if key.upper() in dangerous_vars:
                continue

            # Validate key format
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                continue

            # Convert to string and limit length
            str_value = str(value)

            # Truncate if too long
            if len(str_value) > 8192:
                str_value = str_value[:8192]

            # Remove null bytes
            safe_value = str_value.replace("\0", "")

            safe_env[key] = safe_value

        return safe_env

    def escape_argument(self, arg: str) -> str:
        """
        Safely escape a single argument for shell execution.

        Args:
            arg: Argument to escape

        Returns:
            Safely escaped argument
        """
        # Use shlex.quote for proper escaping
        return shlex.quote(arg)

    def build_safe_command(self, command: str, args: List[str]) -> str:
        """
        Build a safe command with properly escaped arguments.

        Args:
            command: Base command
            args: List of arguments

        Returns:
            Safe command string
        """
        safe_parts = [self.escape_argument(command)]
        safe_parts.extend(self.escape_argument(arg) for arg in args)
        return " ".join(safe_parts)

    # Validation functions for restricted commands

    def _validate_rm(self, parts: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate rm command."""
        # Don't allow recursive deletion of root directories
        if "-r" in parts or "-rf" in parts or "-fr" in parts:
            for part in parts[1:]:
                if part.startswith("-"):
                    continue
                # Check for root directory patterns
                if part in ["/", "/*", "/.", "/.."]:
                    return False, "Cannot recursively delete root directory"
                # Check for system directories
                if re.match(
                    r"^/(bin|boot|dev|etc|lib|proc|root|sbin|sys|usr)/?$", part
                ):
                    return False, f"Cannot delete system directory: {part}"

        return True, None

    def _validate_mv(self, parts: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate mv command."""
        # Don't allow moving to /dev/null or system directories
        if len(parts) >= 3:
            dest = parts[-1]
            if dest == "/dev/null":
                return False, "Cannot move files to /dev/null"
            if re.match(r"^/(bin|boot|dev|etc|lib|proc|root|sbin|sys)/?$", dest):
                return False, f"Cannot move files to system directory: {dest}"

        return True, None

    def _validate_chmod(self, parts: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate chmod command."""
        # Don't allow chmod on system files
        for part in parts[1:]:
            if part.startswith("-"):
                continue
            if (
                part.startswith("/etc/")
                or part.startswith("/bin/")
                or part.startswith("/usr/bin/")
            ):
                return False, f"Cannot change permissions on system file: {part}"

        # Don't allow setuid/setgid on arbitrary files
        for part in parts[1:]:
            # Check for 4-digit octal permissions with setuid/setgid bits (e.g., 4755, 2755, 6755)  # noqa: E501
            if re.match(
                r"^[4267]\d{3}$", part
            ):  # First digit 4,2,6 means setuid/setgid
                return False, "Cannot set setuid/setgid bits"

        return True, None

    def _validate_chown(self, parts: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate chown command."""
        # Don't allow chown on system files
        for part in parts[1:]:
            if part.startswith("-"):
                continue
            if (
                part.startswith("/etc/")
                or part.startswith("/bin/")
                or part.startswith("/usr/")
            ):
                return False, f"Cannot change ownership of system file: {part}"

        return True, None

    def _validate_kill(self, parts: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate kill command."""
        # Don't allow killing PID 1 (init)
        for part in parts[1:]:
            if part == "1" or part == "-1":
                return False, "Cannot kill init process (PID 1)"

        return True, None

    def _validate_pkill(self, parts: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate pkill command."""
        # Don't allow killing essential processes
        essential_processes = ["init", "systemd", "kernel", "launchd"]
        for part in parts[1:]:
            if part.lower() in essential_processes:
                return False, f"Cannot kill essential process: {part}"

        return True, None

    def _validate_curl(self, parts: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate curl command."""
        # Check for piping to shell
        command_str = " ".join(parts)
        if re.search(r"\|\s*(sh|bash|zsh|fish|ksh)", command_str):
            return False, "Cannot pipe curl output directly to shell"

        return True, None

    def _validate_wget(self, parts: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate wget command."""
        # Check for piping to shell
        command_str = " ".join(parts)
        if re.search(r"\|\s*(sh|bash|zsh|fish|ksh)", command_str):
            return False, "Cannot pipe wget output directly to shell"

        # Check for output to sensitive locations
        for i, part in enumerate(parts):
            if part == "-O" and i + 1 < len(parts):
                output_file = parts[i + 1]
                if output_file.startswith("/etc/") or output_file.startswith("/bin/"):
                    return False, f"Cannot write to sensitive location: {output_file}"

        return True, None

    def _has_dangerous_redirection(self, command: str) -> bool:
        """Check for dangerous output redirections."""
        dangerous_redirects = [
            r">\s*/dev/[sh]d[a-z]",  # Writing to disk devices
            r">\s*/etc/",  # Writing to etc
            r">\s*/sys/",  # Writing to sys
            r">\s*/proc/",  # Writing to proc
            r">>\s*/etc/passwd",  # Appending to passwd
            r">>\s*/etc/shadow",  # Appending to shadow
        ]

        for pattern in dangerous_redirects:
            if re.search(pattern, command):
                return True

        return False

    def _has_dangerous_chaining(self, command: str) -> bool:
        """Check for dangerous command chaining."""
        # Look for multiple pipes or semicolons with dangerous commands
        if command.count("|") > 3 or command.count(";") > 3:
            return True

        # Check for specific dangerous chains
        dangerous_chains = [
            r";\s*rm\s+-rf",
            r"&&\s*rm\s+-rf",
            r"\|\|\s*rm\s+-rf",
            r";\s*curl.*\|\s*sh",
            r"&&\s*curl.*\|\s*sh",
        ]

        for pattern in dangerous_chains:
            if re.search(pattern, command):
                return True

        return False


# Global sanitizer instance
_command_sanitizer = CommandSanitizer()


# Convenience functions
def sanitize_command(
    command: str, strict_mode: bool = True
) -> Tuple[bool, str, Optional[str]]:
    """Sanitize a shell command using the global sanitizer."""
    return _command_sanitizer.sanitize_command(command, strict_mode)


def sanitize_environment(env: Dict[str, str]) -> Dict[str, str]:
    """Sanitize environment variables using the global sanitizer."""
    return _command_sanitizer.sanitize_environment(env)


def escape_argument(arg: str) -> str:
    """Escape a shell argument using the global sanitizer."""
    return _command_sanitizer.escape_argument(arg)


def build_safe_command(command: str, args: List[str]) -> str:
    """Build a safe command using the global sanitizer."""
    return _command_sanitizer.build_safe_command(command, args)
