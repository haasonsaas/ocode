"""
Configuration management for OCode.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Default configuration
DEFAULT_CONFIG = {
    "model": "llama3.2:latest",
    "temperature": 0.1,
    "top_p": 0.9,
    "max_tokens": 4096,
    "max_context_files": 20,
    "context_window": 8192,
    "output_format": "text",
    "verbose": False,
    "auto_save_sessions": True,
    "session_cleanup_days": 30,
    "max_concurrent_tools": 5,
    "tool_timeout": 300,
    "ollama_host": "http://localhost:11434",
    "use_ripgrep": True,
    "parallel_grep_workers": 4,
    "permissions": {
        "allow_file_read": True,
        "allow_file_write": True,
        "allow_shell_exec": False,
        "allow_git_ops": True,
        "allowed_paths": [],
        "blocked_paths": ["/etc", "/bin", "/usr/bin", "/sbin"],
    },
    "ignore_patterns": [
        ".git",
        ".ocode",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        ".venv",
        "venv",
        ".env",
        "*.pyc",
        "*.pyo",
        "*.egg-info",
        ".DS_Store",
        "*.log",
        "*.tmp",
        ".idea",
        ".vscode",
    ],
    "mcp_servers": {},
    "architecture": {
        "enable_advanced_orchestrator": True,
        "enable_stream_processing": True,
        "enable_semantic_context": True,
        "enable_predictive_execution": True,
        "enable_dynamic_context": True,
        "orchestrator_max_concurrent": 5,
        "stream_processor_batch_size": 1048576,  # 1MB
        "semantic_context_max_files": 20,
        "embedding_model": "all-MiniLM-L6-v2",
        "predictive_cache_warm": True,
        "context_expansion_factor": 1.5,
    },
}


class ConfigManager:
    """
    Manages OCode configuration with hierarchical settings.

    Configuration hierarchy (higher priority first):
    1. Environment variables (OCODE_*)
    2. .ocode/settings.local.json (project-specific, local)
    3. .ocode/settings.json (project-specific, shared)
    4. ~/.ocode/settings.json (user global)
    5. Default values
    """

    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize configuration manager.

        Args:
            project_root: Project root directory for project-specific config
        """
        self.project_root = project_root or Path.cwd()
        self._config_cache: Optional[Dict[str, Any]] = None

        # Use the global default configuration
        self.defaults = DEFAULT_CONFIG.copy()

    def _get_config_paths(self) -> List[Path]:
        """Get all possible configuration file paths in priority order.

        Returns:
            List of paths ordered from highest to lowest priority:
            - .ocode/settings.local.json (project-specific, local)
            - .ocode/settings.json (project-specific, shared)
            - ~/.ocode/settings.json (user global)
        """
        paths = []

        # Project-specific configs
        project_ocode = self.project_root / ".ocode"
        if project_ocode.exists():
            paths.append(project_ocode / "settings.local.json")
            paths.append(project_ocode / "settings.json")

        # User global config
        user_ocode = Path.home() / ".ocode"
        if user_ocode.exists():
            paths.append(user_ocode / "settings.json")

        return paths

    def _load_config_file(self, path: Path) -> Dict[str, Any]:
        """Load configuration from a JSON file.

        Args:
            path: Path to the JSON configuration file.

        Returns:
            Dictionary of configuration values, empty dict on error.
        """
        if not path.exists():
            return {}

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Failed to load config from {path}: {e}")
            return {}

    def _get_env_config(self) -> Dict[str, Any]:
        """Get configuration from environment variables.

        Maps OCODE_* and OLLAMA_HOST environment variables to
        configuration keys with appropriate type conversion.

        Returns:
            Dictionary of configuration values from environment.
        """
        env_config = {}

        # Map environment variables to config keys
        env_mappings = {
            "OCODE_MODEL": "model",
            "OCODE_TEMPERATURE": ("temperature", float),
            "OCODE_TOP_P": ("top_p", float),
            "OCODE_MAX_TOKENS": ("max_tokens", int),
            "OCODE_MAX_CONTEXT_FILES": ("max_context_files", int),
            "OCODE_CONTEXT_WINDOW": ("context_window", int),
            "OCODE_OUTPUT_FORMAT": "output_format",
            "OCODE_VERBOSE": ("verbose", lambda x: x.lower() in ("true", "1", "yes")),
            "OLLAMA_HOST": "ollama_host",
        }

        for env_var, config_key in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                if isinstance(config_key, tuple):
                    key, converter = config_key
                    try:
                        env_config[key] = converter(value)
                    except (ValueError, TypeError):
                        print(f"Warning: Invalid value for {env_var}: {value}")
                else:
                    env_config[config_key] = value

        return env_config

    def _merge_configs(self, *configs: Dict[str, Any]) -> Dict[str, Any]:
        """Merge multiple configuration dictionaries.

        Later configs override earlier ones. Nested dictionaries
        are merged recursively.

        Args:
            *configs: Configuration dictionaries to merge.

        Returns:
            Merged configuration dictionary.
        """
        result: Dict[str, Any] = {}

        for config in configs:
            for key, value in config.items():
                if (
                    isinstance(value, dict)
                    and key in result
                    and isinstance(result[key], dict)
                ):
                    # Recursively merge nested dictionaries
                    result[key] = self._merge_configs(result[key], value)
                else:
                    result[key] = value

        return result

    def _load_all_config(self) -> Dict[str, Any]:
        """Load and merge all configuration sources.

        Loads configuration from all sources in priority order
        and merges them into a single configuration dictionary.

        Returns:
            Complete merged configuration.
        """
        configs = [self.defaults]

        # Load file-based configs
        for path in reversed(self._get_config_paths()):  # Reverse for priority order
            config = self._load_config_file(path)
            if config:
                configs.append(config)

        # Environment variables have highest priority
        env_config = self._get_env_config()
        if env_config:
            configs.append(env_config)

        return self._merge_configs(*configs)

    def reload(self) -> None:
        """Reload configuration from all sources.

        Clears the configuration cache to force reloading from
        files and environment on next access.
        """
        self._config_cache = None

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration as a dictionary.

        Returns:
            Copy of the complete configuration dictionary.
        """
        if self._config_cache is None:
            self._config_cache = self._load_all_config()
        return self._config_cache.copy()

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key (supports dot notation for nested keys)
            default: Default value if key not found

        Returns:
            Configuration value
        """
        config = self.get_all()

        # Support dot notation for nested keys
        keys = key.split(".")
        value = config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any, scope: str = "project") -> bool:
        """
        Set a configuration value.

        Args:
            key: Configuration key (supports dot notation)
            value: Value to set
            scope: Configuration scope ('project', 'user')

        Returns:
            True if successfully saved
        """
        # Determine target file
        if scope == "user":
            config_dir = Path.home() / ".ocode"
            config_file = config_dir / "settings.json"
        else:
            config_dir = self.project_root / ".ocode"
            config_file = config_dir / "settings.local.json"

        # Create directory if needed
        config_dir.mkdir(parents=True, exist_ok=True)

        # Load existing config
        existing_config = self._load_config_file(config_file)

        # Set the value (support dot notation)
        keys = key.split(".")
        target = existing_config

        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]

        target[keys[-1]] = value

        # Save the config
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(existing_config, f, indent=2)

            # Clear cache to force reload
            self._config_cache = None
            return True

        except OSError as e:
            print(f"Failed to save config to {config_file}: {e}")
            return False

    def create_project_config(self, overrides: Optional[Dict[str, Any]] = None) -> Path:
        """
        Create a project-specific configuration file.

        Args:
            overrides: Configuration overrides

        Returns:
            Path to created config file
        """
        config_dir = self.project_root / ".ocode"
        config_dir.mkdir(parents=True, exist_ok=True)

        config_file = config_dir / "settings.json"

        # Base project config
        project_config = {
            "model": self.get("model"),
            "max_context_files": 20,
            "permissions": {
                "allow_file_read": True,
                "allow_file_write": True,
                "allow_shell_exec": False,
                "allow_git_ops": True,
                "allowed_paths": [str(self.project_root)],
            },
        }

        # Apply overrides
        if overrides:
            project_config = self._merge_configs(project_config, overrides)

        # Save config
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(project_config, f, indent=2)

        # Clear cache
        self._config_cache = None

        return config_file

    def validate_config(self) -> List[str]:
        """
        Validate current configuration.

        Returns:
            List of validation errors
        """
        config = self.get_all()
        errors = []

        # Check required values
        if not config.get("model"):
            errors.append("Model not specified")

        # Check numeric ranges
        if not (0.0 <= config.get("temperature", 0.1) <= 2.0):
            errors.append("Temperature must be between 0.0 and 2.0")

        if not (0.0 <= config.get("top_p", 0.9) <= 1.0):
            errors.append("top_p must be between 0.0 and 1.0")

        if config.get("max_tokens", 4096) <= 0:
            errors.append("max_tokens must be positive")

        if config.get("max_context_files", 20) <= 0:
            errors.append("max_context_files must be positive")

        # Check permissions
        permissions = config.get("permissions", {})
        allowed_paths = permissions.get("allowed_paths", [])
        # blocked_paths = permissions.get("blocked_paths", [])  # Currently unused

        for path in allowed_paths:
            if not Path(path).exists():
                errors.append(f"Allowed path does not exist: {path}")

        return errors

    def show_config_sources(self) -> Dict[str, Any]:
        """Show which configuration sources are being used.

        Useful for debugging configuration precedence issues.

        Returns:
            Dictionary showing:
            - defaults: Default configuration
            - files: Configuration from each file
            - environment: Environment variable configuration
            - final: Merged final configuration
        """
        sources = {
            "defaults": self.defaults,
            "files": {},
            "environment": self._get_env_config(),
            "final": self.get_all(),
        }

        # Check each config file
        for path in self._get_config_paths():
            if path.exists():
                sources["files"][str(path)] = self._load_config_file(path)

        return sources


def main() -> None:
    """Example usage of ConfigManager.

    Demonstrates configuration loading, access, and validation.
    """
    config = ConfigManager()

    print("Current configuration:")
    for key, value in config.get_all().items():
        print(f"  {key}: {value}")

    print(f"\nModel: {config.get('model')}")
    print(f"Temperature: {config.get('temperature')}")
    print(f"Max tokens: {config.get('max_tokens')}")

    # Validation
    errors = config.validate_config()
    if errors:
        print("\nConfiguration errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\n✓ Configuration is valid")


if __name__ == "__main__":
    main()
