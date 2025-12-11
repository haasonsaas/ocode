"""
Interactive onboarding flow for first-time OCode users.
"""

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt
    from rich.theme import Theme

    RICH_AVAILABLE = True

    # Import our theming components
    from ..ui.components import ThemeSelector
    from ..ui.theme import get_themed_console, theme_manager
except ImportError:
    RICH_AVAILABLE = False


class OnboardingManager:
    """Manages the interactive onboarding experience for new users."""

    def __init__(self):
        self.config_dir = Path.home() / ".ocode"
        self.config_file = self.config_dir / "config.json"

        if RICH_AVAILABLE:
            # Define themes
            self.themes: Dict[str, Theme] = {
                "default": Theme(
                    {
                        "info": "cyan",
                        "warning": "yellow",
                        "error": "red",
                        "success": "green",
                        "accent": "magenta bold",
                        "muted": "dim",
                    }
                ),
                "dark": Theme(
                    {
                        "info": "bright_cyan",
                        "warning": "bright_yellow",
                        "error": "bright_red",
                        "success": "bright_green",
                        "accent": "bright_magenta bold",
                        "muted": "bright_black",
                    }
                ),
                "light": Theme(
                    {
                        "info": "blue",
                        "warning": "orange3",
                        "error": "red3",
                        "success": "green3",
                        "accent": "purple bold",
                        "muted": "grey50",
                    }
                ),
                "minimal": Theme(
                    {
                        "info": "default",
                        "warning": "default",
                        "error": "default",
                        "success": "default",
                        "accent": "bold",
                        "muted": "dim",
                    }
                ),
            }

            self.console: Optional[Console] = get_themed_console()
        else:
            self.console = None

    def print(self, text: str, style: str = "default", **kwargs):
        """Print text with styling if Rich is available."""
        if RICH_AVAILABLE and self.console:
            self.console.print(text, style=style, **kwargs)
        else:
            print(text)

    def print_panel(self, text: str, title: str = "", style: str = "info", **kwargs):
        """Print a panel with styling if Rich is available."""
        if RICH_AVAILABLE and self.console:
            self.console.print(Panel(text, title=title, style=style, **kwargs))
        else:
            print(f"\n=== {title} ===")
            print(text)
            print("=" * (len(title) + 8))

    def prompt_choice(
        self, question: str, choices: List[str], default: Optional[str] = None
    ) -> str:
        """Prompt user for choice with validation."""
        if RICH_AVAILABLE:
            return Prompt.ask(
                question,
                choices=choices,
                default=default if default is not None else "",
                show_choices=True,
                show_default=True,
            )
        else:
            while True:
                choices_str = "/".join(choices)
                default_str = f" (default: {default})" if default else ""
                response = input(f"{question} [{choices_str}]{default_str}: ").strip()

                if not response and default:
                    return default
                if response in choices:
                    return response

                print(f"Please choose from: {choices_str}")

    def prompt_confirm(self, question: str, default: bool = True) -> bool:
        """Prompt user for yes/no confirmation."""
        if RICH_AVAILABLE:
            return Confirm.ask(question, default=default)
        else:
            default_str = " (Y/n)" if default else " (y/N)"
            response = input(f"{question}{default_str}: ").strip().lower()

            if not response:
                return default
            return response in ["y", "yes", "true", "1"]

    def prompt_text(self, question: str, default: Optional[str] = None) -> str:
        """Prompt user for text input."""
        if RICH_AVAILABLE:
            return Prompt.ask(question, default=default if default is not None else "")
        else:
            default_str = f" (default: {default})" if default else ""
            response = input(f"{question}{default_str}: ").strip()
            return response if response else (default or "")

    async def check_first_run(self) -> bool:
        """Check if this is a first-time run."""
        return not self.config_file.exists()

    async def welcome_screen(self):
        """Display welcome screen."""
        welcome_text = """
🚀 Welcome to OCode!

OCode is an AI-powered coding assistant that helps you understand, write,
and improve code across different programming languages. Let's get you set up!

Features you'll unlock:
• Intelligent code analysis and refactoring
• Web search integration for current information
• Session management with checkpointing
• Advanced file operations and git integration
• Context-aware assistance for your projects

This quick setup will take just a few minutes.
        """.strip()

        self.print_panel(welcome_text, title="🎉 Welcome to OCode", style="accent")

    async def select_theme(self) -> str:
        """Let user select a color theme."""
        if not RICH_AVAILABLE:
            return "minimal"

        self.print("\n🎨 Choose your color theme:", style="info")

        # Use the new ThemeSelector for a better experience
        selector = ThemeSelector(self.console)
        selected = selector.select_theme()

        if selected:
            # Apply the selected theme
            theme_manager.set_active_theme(selected)
            self.console = get_themed_console()
            self.print("✓ Theme applied successfully", style="success")
            return selected
        else:
            # Default fallback
            self.print("Using default theme", style="info")
            return "default_dark"

    async def configure_model(self) -> Dict[str, Any]:
        """Configure AI model settings."""
        self.print("\n🤖 Configure your AI model:", style="info")

        # Check for common AI providers
        model_configs = []

        # Check for Ollama
        if shutil.which("ollama"):
            self.print("  ✓ Ollama detected", style="success")
            model_configs.append(
                {
                    "name": "ollama",
                    "display_name": "Ollama (Local)",
                    "description": "Use local Ollama models",
                }
            )

        # Check for OpenAI API key
        if os.getenv("OPENAI_API_KEY"):
            self.print("  ✓ OpenAI API key detected", style="success")
            model_configs.append(
                {
                    "name": "openai",
                    "display_name": "OpenAI",
                    "description": "Use OpenAI models (GPT-3.5, GPT-4)",
                }
            )

        # Check for Anthropic API key
        if os.getenv("ANTHROPIC_API_KEY"):
            self.print("  ✓ Anthropic API key detected", style="success")
            model_configs.append(
                {
                    "name": "anthropic",
                    "display_name": "Anthropic",
                    "description": "Use Claude models",
                }
            )

        if not model_configs:
            self.print("  ⚠ No AI providers detected", style="warning")
            model_configs.append(
                {
                    "name": "manual",
                    "display_name": "Manual Setup",
                    "description": "Configure manually later",
                }
            )

        # Let user choose
        if len(model_configs) == 1:
            selected = model_configs[0]
            self.print(f"Using {selected['display_name']}", style="info")
        else:
            choices = [config["name"] for config in model_configs]
            choice = self.prompt_choice(
                "Which AI provider would you like to use?", choices, default=choices[0]
            )
            selected = next(
                config for config in model_configs if config["name"] == choice
            )

        config = {"provider": selected["name"]}

        # Provider-specific configuration
        if selected["name"] == "ollama":
            config.update(
                {
                    "base_url": "http://localhost:11434",
                    "model": "llama3.1:8b",  # Default model
                    "timeout": "300",
                }
            )

            # Check if we can connect to Ollama
            try:
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "http://localhost:11434/api/tags",
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            models = [model["name"] for model in data.get("models", [])]
                            if models:
                                self.print(
                                    f"Available models: "
                                    f"{', '.join(models[:3])}"
                                    f"{'...' if len(models) > 3 else ''}",
                                    style="muted",
                                )

                                if self.prompt_confirm(
                                    f"Use default model '{config['model']}'?",
                                    default=True,
                                ):
                                    pass  # Keep default
                                else:
                                    model = self.prompt_choice(
                                        "Select model:", models, default=models[0]
                                    )
                                    config["model"] = model
            except Exception:
                self.print("  ⚠ Could not connect to Ollama", style="warning")

        elif selected["name"] == "openai":
            config.update(
                {"model": "gpt-3.5-turbo", "max_tokens": "4000", "temperature": "0.1"}
            )

        elif selected["name"] == "anthropic":
            config.update(
                {
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": "4000",
                    "temperature": "0.1",
                }
            )

        self.print("✓ Model configuration ready", style="success")
        return config

    async def configure_features(self) -> Dict[str, Any]:
        """Configure optional features."""
        self.print("\n⚙️ Configure features:", style="info")

        features: Dict[str, Any] = {}

        # Web search
        features["web_search"] = self.prompt_confirm(
            "Enable web search for grounding responses with current information?",
            default=True,
        )

        # Session management
        features["session_management"] = self.prompt_confirm(
            "Enable session management and checkpointing?", default=True
        )

        # Auto-save interval
        if features["session_management"]:
            auto_save = self.prompt_confirm(
                "Enable automatic session saving?", default=True
            )
            features["auto_save"] = auto_save

            if auto_save:
                interval = self.prompt_text("Auto-save interval (minutes)", default="5")
                try:
                    features["auto_save_interval_minutes"] = int(interval)
                except ValueError:
                    features["auto_save_interval_minutes"] = 5

        # Memory limits
        memory_limit = self.prompt_text("Maximum context memory (MB)", default="100")
        try:
            features["memory_limit_mb"] = int(memory_limit)
        except ValueError:
            features["memory_limit_mb"] = 100

        # Git integration
        features["git_integration"] = self.prompt_confirm(
            "Enable enhanced Git integration?", default=True
        )

        self.print("✓ Features configured", style="success")
        return features

    async def configure_security(self) -> Dict[str, Any]:
        """Configure security settings."""
        self.print("\n🔒 Configure security settings:", style="info")

        security: Dict[str, Any] = {}

        # Safe mode
        security["safe_mode"] = self.prompt_confirm(
            "Enable safe mode (requires confirmation for file operations)?",
            default=True,
        )

        # Allowed directories
        if self.prompt_confirm(
            "Restrict file access to specific directories?", default=False
        ):
            allowed_dirs = []
            while True:
                dir_path = self.prompt_text(
                    "Enter allowed directory path (empty to finish):"
                )
                if not dir_path:
                    break

                path = Path(dir_path).expanduser().absolute()
                if path.exists():
                    allowed_dirs.append(str(path))
                    self.print(f"  ✓ Added: {path}", style="success")
                else:
                    self.print(f"  ⚠ Directory not found: {path}", style="warning")

            security["allowed_directories"] = allowed_dirs

        # Command restrictions
        security["restrict_commands"] = self.prompt_confirm(
            "Restrict dangerous shell commands?", default=True
        )

        self.print("✓ Security settings configured", style="success")
        return security

    async def save_configuration(self, config: Dict[str, Any]):
        """Save configuration to file."""
        self.config_dir.mkdir(exist_ok=True)

        # Add metadata
        config["_meta"] = {
            "created": asyncio.get_event_loop().time(),
            "version": "1.0.0",
            "onboarding_completed": True,
        }

        try:
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=2)

            self.print(f"✓ Configuration saved to {self.config_file}", style="success")

        except Exception as e:
            self.print(f"✗ Failed to save configuration: {e}", style="error")
            raise

    async def show_quick_start(self):
        """Show quick start guide."""
        quick_start = """
🎯 Quick Start Guide

Now that OCode is configured, here are some things to try:

📁 Explore a codebase:
   "Analyze the structure of this project"
   "What are the main components of this system?"

🔍 Search and understand:
   "Find all functions that handle user authentication"
   "Explain how this module works"

🛠 Code improvement:
   "Refactor this function to be more readable"
   "Add error handling to this code"

💾 Session management:
   "Save this conversation as a checkpoint"
   "Resume from my last session"

🌐 Web search integration:
   "Search for best practices for REST API design"
   "What's new in Python 3.12?"

📝 Git operations:
   "Show me the recent commits"
   "Help me write a good commit message"

💡 Pro tip: Start conversations with context about what you're working on!
        """.strip()

        self.print_panel(quick_start, title="🚀 You're all set!", style="success")

    async def run_onboarding(self) -> Dict[str, Any]:
        """Run the complete onboarding flow."""
        config: Dict[str, Any] = {}

        try:
            # Welcome
            await self.welcome_screen()

            if not self.prompt_confirm(
                "\nWould you like to run the setup wizard?", default=True
            ):
                self.print(
                    "Skipping setup. You can run 'ocode --setup' later.", style="muted"
                )
                return {}

            # Theme selection
            config["theme"] = await self.select_theme()

            # Model configuration
            config["model"] = await self.configure_model()

            # Features
            config["features"] = await self.configure_features()

            # Security
            config["security"] = await self.configure_security()

            # Save configuration
            await self.save_configuration(config)

            # Show quick start
            await self.show_quick_start()

            self.print("\n🎉 Welcome to OCode! Happy coding!", style="accent")

            return config

        except KeyboardInterrupt:
            self.print(
                "\n\nSetup cancelled. You can run 'ocode --setup' later.", style="muted"
            )
            return {}
        except Exception as e:
            self.print(f"\n✗ Setup failed: {e}", style="error")
            self.print("You can run 'ocode --setup' to try again.", style="muted")
            return {}


async def main():
    """Test the onboarding flow."""
    manager = OnboardingManager()

    if await manager.check_first_run():
        print("Running onboarding flow...")
        config = await manager.run_onboarding()
        print(f"Configuration: {config}")
    else:
        print("OCode is already configured.")


if __name__ == "__main__":
    asyncio.run(main())
