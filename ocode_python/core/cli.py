#!/usr/bin/env python3
"""
OCode CLI - Terminal-native AI coding assistant powered by Ollama models.

This module implements the command-line interface for OCode, providing:
- Interactive and single-prompt modes for AI assistance
- Authentication and configuration management commands
- Session management and conversation persistence
- MCP (Model Context Protocol) server integration
- Rich terminal output with colors and formatting

The CLI is built using Click for command structure and Rich for terminal output,
providing a professional and user-friendly experience.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import click

from ..ui.components import ThemedPanel
from ..ui.theme import get_themed_console
from ..utils.auth import AuthenticationManager
from ..utils.config import ConfigManager
from ..utils.onboarding import OnboardingManager
from .engine import OCodeEngine

# Global console instance for rich terminal output with theming
# Used throughout the CLI for consistent formatting and colors
console = get_themed_console()


async def run_setup_wizard():
    """Run the interactive setup wizard."""
    try:
        onboarding = OnboardingManager()
        config = await onboarding.run_onboarding()

        if config:
            console.print("\n[green]✓ Setup completed successfully![/green]")
            console.print("[dim]You can now start using OCode with 'ocode'[/dim]")
        else:
            console.print("[dim]Setup was cancelled or skipped.[/dim]")

    except Exception as e:
        console.print(f"[red]Setup failed: {e}[/red]")
        console.print("[dim]You can try running 'ocode --setup' again.[/dim]")


async def cli_confirmation_callback(command: str, reason: str) -> bool:
    """Interactive confirmation callback for CLI.

    Prompts the user to confirm potentially dangerous commands
    with a yes/no prompt.

    Args:
        command: The command that requires confirmation.
        reason: Explanation of why confirmation is needed.

    Returns:
        True if user confirms (yes/y), False otherwise.
    """
    try:
        console.print("\n[yellow]⚠️  Command requires confirmation:[/yellow]")
        console.print(f"[white]{command}[/white]")
        console.print(f"[dim]Reason: {reason}[/dim]")

        # Use blocking input since we're in CLI context
        response = input("⚠️ Run this command? (yes/no): ").strip().lower()
        return response in ["yes", "y"]

    except (KeyboardInterrupt, EOFError):
        return False


@click.group(invoke_without_command=True)
@click.option(
    "-m",
    "--model",
    default=lambda: os.getenv(
        "OCODE_MODEL", "MFDoom/deepseek-coder-v2-tool-calling:latest"
    ),
    help="Ollama model tag (e.g. llama3:70b). Can be overridden with OCODE_MODEL env var.",  # noqa: E501
)
@click.option(
    "-c",
    "--continue",
    "continue_session",
    is_flag=True,
    help="Resume the last saved conversation session with full context.",
)
@click.option(
    "-p",
    "--print",
    "print_prompt",
    metavar="PROMPT",
    help="Execute a single prompt non-interactively and exit. Useful for scripting.",
)
@click.option(
    "--out",
    type=click.Choice(["text", "json", "stream-json"]),
    default="text",
    help="Output format: 'text' for human-readable, 'json' for structured, 'stream-json' for real-time.",  # noqa: E501
)
@click.option(
    "--config",
    "config_file",
    type=click.Path(exists=True),
    help="Path to custom configuration file. Overrides default .ocode/settings.json.",  # noqa: E501
)
@click.option(
    "-v", "--verbose", is_flag=True, help="Enable verbose logging and debug output."
)
@click.option(
    "--continue-response",
    is_flag=True,
    help="Continue from the previous incomplete response. Useful for long outputs.",
)
@click.option(
    "--setup",
    is_flag=True,
    help="Run the interactive setup wizard to configure OCode.",
)
@click.option(
    "--tui",
    is_flag=True,
    help="Launch the experimental Textual TUI (requires a real terminal).",
)
@click.option(
    "--classic",
    is_flag=True,
    help="Force legacy interactive prompt instead of the Textual TUI.",
)
@click.pass_context
def cli(
    ctx,
    model: str,
    continue_session: bool,
    print_prompt: Optional[str],
    out: str,
    config_file: Optional[str],
    verbose: bool,
    continue_response: bool,
    setup: bool,
    tui: bool,
    classic: bool,
):
    """
    OCode - Terminal-native AI coding assistant powered by Ollama models.

    OCode provides intelligent coding assistance through a terminal interface,
    combining the power of local LLMs with a comprehensive tool system for
    file operations, code analysis, and project management.

    USAGE MODES:

    Interactive Mode (default):
        ocode

    Single Prompt Mode:
        ocode -p "Explain how async/await works"

    Session Continuation:
        ocode -c

    Custom Model:
        ocode -m llama3:70b

    Verbose Output:
        ocode -v -p "Analyze this codebase"

    The assistant can perform file operations, analyze code, execute commands,
    and maintain context across conversations. Use 'ocode --help' for more options.
    """

    # Store CLI options in Click context for access by subcommands
    # This pattern allows subcommands to inherit parent command options
    ctx.ensure_object(dict)
    ctx.obj.update(
        {
            "model": model,  # AI model identifier
            "continue_session": continue_session,  # Session continuation flag
            "output_format": out,  # Response format preference
            "config_file": config_file,  # Custom config file path
            "verbose": verbose,  # Debug output enabled
            "continue_response": continue_response,  # Response continuation flag
        }
    )

    # Handle setup wizard if requested or first run
    if setup:
        # Explicit setup request
        asyncio.run(run_setup_wizard())
        return

    if tui:
        try:
            from ..ui.tui import run_tui
        except Exception as exc:  # pragma: no cover - defensive import
            console.print(f"[red]Failed to launch TUI:[/red] {exc}")
            sys.exit(1)

        engine = OCodeEngine(
            model=model,
            output_format=out,
            verbose=verbose,
        )
        run_tui(engine)
        return

    # Check for first run and offer onboarding
    config_dir = Path.home() / ".ocode"
    config_file_path = config_dir / "config.json"

    if not config_file_path.exists() and ctx.invoked_subcommand is None:
        # First run - offer onboarding
        console.print(
            "[cyan]🎉 Welcome to OCode![/cyan] "
            "It looks like this is your first time here.\n"
        )

        if click.confirm("Would you like to run the setup wizard?", default=True):
            asyncio.run(run_setup_wizard())
            return
        else:
            console.print(
                "[dim]You can run the setup wizard later with: ocode --setup[/dim]\n"
            )

    # Route to appropriate mode based on provided options
    if print_prompt:
        # Single prompt mode: execute one query and exit
        # Ideal for scripting and automation
        asyncio.run(handle_single_prompt(print_prompt, ctx.obj))
    elif ctx.invoked_subcommand is None:
        # Interactive mode: default to Textual TUI when in a real TTY
        should_use_tui = (
            (tui or sys.stdout.isatty())
            and not classic
            and os.getenv("OCODE_TUI", "1") != "0"
        )

        if should_use_tui:
            try:
                from ..ui.tui import run_tui
            except Exception as exc:  # pragma: no cover - defensive import
                console.print(
                    f"[red]Failed to launch TUI, falling back to classic:[/red] {exc}"
                )
                asyncio.run(interactive_mode(ctx.obj))
                return

            engine = OCodeEngine(
                model=model,
                output_format=out,
                verbose=verbose,
            )
            run_tui(engine)
        else:
            # Legacy interactive prompt
            asyncio.run(interactive_mode(ctx.obj))


@cli.command()
@click.argument("path", type=click.Path(), default=".")
def init(path: str):
    """Initialize OCode project configuration.

    Creates the .ocode directory structure and default configuration
    file in the specified path.

    Args:
        path: Project path to initialize. Defaults to current directory.
    """
    project_path = Path(path).resolve()
    ocode_dir = project_path / ".ocode"

    if ocode_dir.exists():
        console.print(f"[yellow]OCode already initialized in {project_path}[/yellow]")
        return

    # Create .ocode directory structure
    ocode_dir.mkdir()
    (ocode_dir / "memory").mkdir()
    (ocode_dir / "commands").mkdir()

    # Create default configuration
    config = {
        "model": "MFDoom/deepseek-coder-v2-tool-calling:latest",
        "max_tokens": 200000,
        "context_window": 4096,
        "permissions": {
            "allow_file_read": True,
            "allow_file_write": True,
            "allow_shell_exec": False,
            "allowed_paths": [str(project_path)],
        },
    }

    config_path = ocode_dir / "settings.json"
    import json

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    console.print(f"[green]✓[/green] Initialized OCode in {project_path}")
    console.print(f"[dim]Configuration: {config_path}[/dim]")


@cli.command()
@click.option("--list", is_flag=True, help="List MCP servers")
@click.option("--start", metavar="NAME", help="Start MCP server")
@click.option("--stop", metavar="NAME", help="Stop MCP server")
@click.option("--restart", metavar="NAME", help="Restart MCP server")
@click.option("--add", nargs=2, metavar="NAME COMMAND", help="Add new MCP server")
@click.option("--remove", metavar="NAME", help="Remove MCP server")
def mcp(
    list: bool,
    start: Optional[str],
    stop: Optional[str],
    restart: Optional[str],
    add: Optional[tuple],
    remove: Optional[str],
):
    """Manage Model Context Protocol servers."""
    from rich.table import Table

    from ..mcp.manager import MCPServerManager

    manager = MCPServerManager()

    if list:
        servers = manager.list_servers()

        if not servers:
            console.print("[dim]No MCP servers configured[/dim]")
            console.print(
                "\n[dim]Add a server with:[/dim] ocode mcp --add <name> <command>"
            )
            return

        # Create table
        table = Table(title="MCP Servers")
        table.add_column("Name", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("PID", style="yellow")
        table.add_column("Command")
        table.add_column("Error", style="red")

        for server in servers:
            status_style = {"running": "green", "stopped": "dim", "error": "red"}.get(
                server.status, "white"
            )

            table.add_row(
                server.name,
                f"[{status_style}]{server.status}[/{status_style}]",
                str(server.pid) if server.pid else "-",
                f"{server.command} {' '.join(server.args)}"[:50] + "...",
                server.error[:30] + "..." if server.error else "",
            )

        console.print(table)

    elif start:
        console.print(f"Starting MCP server: {start}")
        try:
            info = asyncio.run(manager.start_server(start))
            if info.status == "running":
                console.print(
                    f"[green]✓[/green] Server '{start}' started (PID: {info.pid})"
                )
            else:
                console.print(
                    f"[red]✗[/red] Failed to start server '{start}': {info.error}"
                )
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")

    elif stop:
        console.print(f"Stopping MCP server: {stop}")
        try:
            info = asyncio.run(manager.stop_server(stop))
            if info.status == "stopped":
                console.print(f"[green]✓[/green] Server '{stop}' stopped")
            else:
                console.print(
                    f"[red]✗[/red] Failed to stop server '{stop}': {info.error}"
                )
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")

    elif restart:
        console.print(f"Restarting MCP server: {restart}")
        try:
            info = asyncio.run(manager.restart_server(restart))
            if info.status == "running":
                console.print(
                    f"[green]✓[/green] Server '{restart}' restarted (PID: {info.pid})"
                )
            else:
                console.print(
                    f"[red]✗[/red] Failed to restart server '{restart}': {info.error}"
                )
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")

    elif add:
        name, command = add
        # Parse command and args
        import shlex

        cmd_parts = shlex.split(command)

        if manager.add_server(
            name, cmd_parts[0], cmd_parts[1:] if len(cmd_parts) > 1 else []
        ):
            console.print(f"[green]✓[/green] Added MCP server '{name}'")
            console.print(f"[dim]Start it with:[/dim] ocode mcp --start {name}")
        else:
            console.print(f"[red]✗[/red] Failed to add server '{name}'")

    elif remove:
        if manager.remove_server(remove):
            console.print(f"[green]✓[/green] Removed MCP server '{remove}'")
        else:
            console.print(f"[red]✗[/red] Failed to remove server '{remove}'")

    else:
        console.print("Use --help for available options")


@cli.command()
@click.option("--login", is_flag=True, help="Login to OCode service")
@click.option("--logout", is_flag=True, help="Logout from OCode service")
@click.option("--status", is_flag=True, help="Show authentication status")
@click.option("--api-key", metavar="KEY", help="Set API key for authentication")
@click.option("--token", metavar="TOKEN", help="Set authentication token directly")
def auth(
    login: bool,
    logout: bool,
    status: bool,
    api_key: Optional[str],
    token: Optional[str],
):
    """Authentication helpers."""
    auth_manager = AuthenticationManager()
    import getpass

    from rich.table import Table

    if login:
        # Interactive login flow
        console.print("\n[bold]OCode Authentication[/bold]")
        console.print("Choose authentication method:\n")
        console.print("1. API Key")
        console.print("2. Username/Password")
        console.print("3. Cancel\n")

        choice = input("Select option (1 - 3): ").strip()

        if choice == "1":
            # API Key authentication
            api_key = getpass.getpass("Enter API key: ").strip()
            if api_key:
                if auth_manager.save_api_key(api_key):
                    console.print("[green]✓ API key saved successfully[/green]")
                else:
                    console.print("[red]✗ Failed to save API key[/red]")
            else:
                console.print("[yellow]Cancelled[/yellow]")

        elif choice == "2":
            # Username/Password authentication (not implemented)
            console.print(
                "[yellow]Username/Password authentication is not yet implemented[/yellow]"  # noqa: E501
            )

        else:
            console.print("[yellow]Cancelled[/yellow]")

    elif logout:
        if auth_manager.logout():
            console.print("[green]✓ Logged out successfully[/green]")
        else:
            console.print("[red]✗ Logout failed[/red]")

    elif status:
        status_info = auth_manager.get_auth_status()

        # Create status table
        table = Table(title="Authentication Status")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row(
            "Authenticated",
            "[green]Yes[/green]" if status_info["authenticated"] else "[red]No[/red]",
        )

        if status_info["has_token"]:
            table.add_row("Token", "[green]Present[/green]")
            if status_info["token_expires_at"]:
                import datetime

                expires = datetime.datetime.fromtimestamp(
                    status_info["token_expires_at"]
                )
                table.add_row("Token Expires", expires.strftime("%Y-%m-%d %H:%M:%S"))

        if status_info["has_api_key"]:
            table.add_row("API Key", "[green]Present[/green]")

        table.add_row(
            "Auth File",
            (
                "[green]Exists[/green]"
                if status_info["auth_file_exists"]
                else "[dim]Not found[/dim]"
            ),
        )

        console.print(table)

    elif api_key:
        # Direct API key setting
        if auth_manager.save_api_key(api_key):
            console.print("[green]✓ API key saved successfully[/green]")
        else:
            console.print("[red]✗ Failed to save API key[/red]")

    elif token:
        # Direct token setting
        import time

        if auth_manager.save_token(
            token=token,
            expires_at=time.time() + 3600,  # Default 1 hour expiry
            token_type="Bearer",  # nosec B106
        ):
            console.print("[green]✓ Token saved successfully[/green]")
        else:
            console.print("[red]✗ Failed to save token[/red]")

    else:
        console.print("Use --help for available options")


@cli.command()
@click.option("--get", metavar="KEY", help="Get configuration value")
@click.option("--set", metavar="KEY=VALUE", help="Set configuration value")
@click.option("--list", is_flag=True, help="List all configuration")
def config(get: Optional[str], set: Optional[str], list: bool):
    """View and edit configuration."""
    config_manager = ConfigManager()

    if get:
        value = config_manager.get(get)
        console.print(f"{get}: {value}")
    elif set:
        if "=" not in set:
            console.print("[red]Invalid format. Use KEY=VALUE[/red]")
            return
        key, value = set.split("=", 1)
        config_manager.set(key, value)
        console.print(f"[green]Set {key} = {value}[/green]")
    elif list:
        console.print("[bold]Configuration:[/bold]")
        for key, value in config_manager.get_all().items():
            console.print(f"  {key}: {value}")
    else:
        console.print("Use --help for available options")


@cli.command()
@click.option("--list", is_flag=True, help="List available themes")
@click.option("--set", metavar="THEME", help="Set active theme")
@click.option("--preview", metavar="THEME", help="Preview a theme")
@click.option("--current", is_flag=True, help="Show current theme")
def theme(list: bool, set: Optional[str], preview: Optional[str], current: bool):
    """Manage UI themes and color schemes."""
    from rich.table import Table

    from ..ui.components import ThemeSelector
    from ..ui.theme import theme_manager

    if list:
        themes = theme_manager.list_themes()

        if not themes:
            console.print("[dim]No themes available[/dim]")
            return

        table = Table(title="Available Themes")
        table.add_column("Name", style="primary")
        table.add_column("Type", style="secondary")
        table.add_column("Description", style="default")

        for theme in themes:
            type_icon = {
                "dark": "🌙",
                "light": "☀️",
                "high_contrast": "🔍",
                "minimal": "⚡",
            }.get(theme.type.value, "🎨")

            table.add_row(
                theme.name, f"{type_icon} {theme.type.value.title()}", theme.description
            )

        console.print(table)

        # Show current active theme
        active = theme_manager.get_active_theme()
        console.print(f"\n[dim]Current theme:[/dim] [bold]{active.name}[/bold]")

    elif set:
        if theme_manager.set_active_theme(set):
            console.print(f"[green]✓[/green] Theme set to: [bold]{set}[/bold]")
            console.print("[dim]Restart OCode to see the new theme in effect[/dim]")
        else:
            console.print(f"[red]✗[/red] Theme '{set}' not found")
            console.print("[dim]Use 'ocode theme --list' to see available themes[/dim]")

    elif preview:
        selector = ThemeSelector(console)
        selector.show_theme_preview(preview)

    elif current:
        active = theme_manager.get_active_theme()
        console.print(
            ThemedPanel.info(
                f"Name: {active.name}\n"
                f"Type: {active.type.value.title()}\n"
                f"Description: {active.description}",
                title="Current Theme",
            )
        )

    else:
        # Interactive theme selection
        selector = ThemeSelector(console)
        selected = selector.select_theme()

        if selected:
            theme_manager.set_active_theme(selected)
            console.print(
                f"\n[green]✓[/green] Theme changed to: [bold]{selected}[/bold]"
            )
            console.print("[dim]Restart OCode to see the new theme in effect[/dim]")


async def handle_single_prompt(prompt: str, options: dict):
    """Handle single prompt in non-interactive mode.

    Processes a single prompt and outputs the response according
    to the specified output format.

    Args:
        prompt: The user prompt to process.
        options: Dictionary containing CLI options (model, output_format, etc).
    """
    try:
        auth = AuthenticationManager()
        engine = OCodeEngine(
            model=options["model"],
            api_key=auth.token(),
            output_format=options["output_format"],
            verbose=options["verbose"],
            confirmation_callback=cli_confirmation_callback,
        )

        try:
            async for chunk in engine.process(
                prompt, continue_previous=options.get("continue_response", False)
            ):
                if options["output_format"] == "json":
                    import json

                    console.print(json.dumps(chunk))
                elif options["output_format"] == "stream-json":
                    import json

                    print(json.dumps(chunk), flush=True)
                else:
                    print(chunk, end="", flush=True)

            if options["output_format"] == "text":
                print()  # Final newline
        finally:
            # Ensure API client session is closed
            if hasattr(engine.api_client, "session") and engine.api_client.session:
                await engine.api_client.session.close()

    except Exception as e:
        console.print(f"[red]❌ Error: Processing error: {e}[/red]")
        sys.exit(1)


def show_help():
    """Display help for interactive mode commands."""
    help_text = """
[bold]Interactive Mode Commands:[/bold]

[cyan]/help[/cyan]      - Show this help message
[cyan]/exit[/cyan]      - Exit OCode (/quit, /q also work)
[cyan]/continue[/cyan]  - Continue from previous incomplete response
[cyan]/clear[/cyan]     - Clear screen (not implemented yet)

[bold]Tips:[/bold]
• Use arrow keys to navigate command history
• Press Tab for auto-suggestions
• Use Ctrl+C to interrupt current operation
• Type normally to chat with the AI assistant
    """
    console.print(help_text)


async def interactive_mode(options: dict):
    """Start interactive OCode session.

    Runs an interactive REPL with command history and auto-suggestions.
    Supports special commands like /exit, /continue, etc.

    Args:
        options: Dictionary containing CLI options (model, output_format, etc).
    """
    from prompt_toolkit import PromptSession
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.history import FileHistory

    # Welcome banner with themed styling
    welcome_panel = ThemedPanel.info(
        f"Model: {options['model']}\n"
        "Type /help for commands or /exit to quit\n"
        "Type /continue to continue from previous response",
        title="🤖 OCode - AI Coding Assistant",
    )
    console.print(welcome_panel)
    console.print()

    # Create prompt session with history
    history_file = Path.home() / ".ocode" / "history"
    history_file.parent.mkdir(exist_ok=True)

    session: PromptSession[str] = PromptSession(
        history=FileHistory(str(history_file)),
        auto_suggest=AutoSuggestFromHistory(),
    )

    try:
        auth = AuthenticationManager()
        engine = OCodeEngine(
            model=options["model"],
            api_key=auth.token(),
            output_format=options["output_format"],
            verbose=options["verbose"],
            confirmation_callback=cli_confirmation_callback,
        )

        while True:
            try:
                # Get user input
                prompt = await session.prompt_async("ocode> ")

                if not prompt.strip():
                    continue

                if prompt.strip() in ["/exit", "/quit", "/q"]:
                    break
                elif prompt.strip() == "/help":
                    show_help()
                    continue
                elif prompt.strip() == "/continue":
                    if not engine.current_response:
                        console.print(
                            "[yellow]No previous response to continue from[/yellow]"
                        )
                        continue
                    if engine.is_response_complete():
                        console.print(
                            "[yellow]Previous response is already complete[/yellow]"
                        )
                        continue
                    prompt = "Continue the previous response"
                    console.print("[dim]Continuing previous response...[/dim]")

                async for chunk in engine.process(
                    prompt, continue_previous=prompt.strip() == "/continue"
                ):
                    if options["output_format"] == "json":
                        import json

                        console.print(json.dumps(chunk))
                    elif options["output_format"] == "stream-json":
                        import json

                        print(json.dumps(chunk), flush=True)
                    else:
                        print(chunk, end="", flush=True)

                if options["output_format"] == "text":
                    print()  # Final newline

            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted[/yellow]")
                continue
            except Exception as e:
                console.print(f"[red]❌ Error: {e}[/red]")

    finally:
        if hasattr(engine.api_client, "session") and engine.api_client.session:
            await engine.api_client.session.close()


@cli.command()
@click.option(
    "--action",
    type=click.Choice(["list", "load", "delete", "cleanup"]),
    default="list",
    help="Session action to perform",
)
@click.option("--session-id", help="Session ID for load/delete operations")
@click.option("--days", type=int, default=30, help="Days for cleanup operation")
def sessions(action: str, session_id: Optional[str], days: int):
    """Manage conversation sessions and checkpoints."""
    from rich.table import Table

    from ..core.checkpoint import CheckpointManager
    from ..core.session import SessionManager

    session_manager = SessionManager()
    checkpoint_manager = CheckpointManager()

    if action == "list":
        # List recent sessions
        sessions = asyncio.run(session_manager.list_sessions(limit=10))

        if not sessions:
            console.print("[dim]No sessions found.[/dim]")
            return

        table = Table(title="Recent Sessions")
        table.add_column("ID", style="cyan")
        table.add_column("Created", style="dim")
        table.add_column("Messages", style="yellow")
        table.add_column("Preview")

        for session in sessions:
            import time

            created = time.strftime(
                "%Y-%m-%d %H:%M", time.localtime(session["created_at"])
            )
            preview = session.get("preview", "")[:50] + (
                "..." if len(session.get("preview", "")) > 50 else ""
            )

            table.add_row(
                session["id"][:8] + "...",
                created,
                str(session["message_count"]),
                preview,
            )

        console.print(table)

        # Also show checkpoints
        checkpoints = asyncio.run(checkpoint_manager.list_checkpoints(limit=5))

        if checkpoints:
            console.print("\n")
            checkpoint_table = Table(title="Recent Checkpoints")
            checkpoint_table.add_column("ID", style="cyan")
            checkpoint_table.add_column("Session", style="magenta")
            checkpoint_table.add_column("Created", style="dim")
            checkpoint_table.add_column("Description")

            for checkpoint in checkpoints:
                import time as time_module

                created = time_module.strftime(
                    "%Y-%m-%d %H:%M", time_module.localtime(checkpoint["timestamp"])
                )

                checkpoint_table.add_row(
                    checkpoint["id"][:8] + "...",
                    checkpoint["session_id"][:8] + "...",
                    created,
                    checkpoint.get("description", "")[:40]
                    + ("..." if len(checkpoint.get("description", "")) > 40 else ""),
                )

            console.print(checkpoint_table)

    elif action == "load":
        if not session_id:
            console.print("[red]Error:[/red] Session ID required for load operation")
            return

        session_obj = asyncio.run(session_manager.load_session(session_id))
        if not session_obj:
            console.print(f"[red]Error:[/red] Session {session_id} not found")
            return

        console.print(
            f"[green]✓[/green] Session loaded: {len(session_obj.messages)} messages"
        )

        # Show recent messages
        recent = (
            session_obj.messages[-3:]
            if len(session_obj.messages) > 3
            else session_obj.messages
        )
        for msg in recent:
            role_icon = "👤" if msg.role == "user" else "🤖"
            content = (
                msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            )
            console.print(f"{role_icon} [bold]{msg.role}:[/bold] {content}")

    elif action == "delete":
        if not session_id:
            console.print("[red]Error:[/red] Session ID required for delete operation")
            return

        if click.confirm(f"Delete session {session_id}?"):
            success = asyncio.run(session_manager.delete_session(session_id))
            if success:
                console.print(f"[green]✓[/green] Session {session_id} deleted")
            else:
                console.print(f"[red]✗[/red] Failed to delete session {session_id}")

    elif action == "cleanup":
        sessions_deleted = asyncio.run(session_manager.cleanup_old_sessions(days))
        checkpoints_deleted = asyncio.run(
            checkpoint_manager.cleanup_old_checkpoints(days)
        )

        console.print("[green]✓[/green] Cleanup completed:")
        console.print(f"  Sessions deleted: {sessions_deleted}")
        console.print(f"  Checkpoints deleted: {checkpoints_deleted}")


def main():
    """Entry point for the CLI.

    Handles exceptions and provides debug output when OCODE_DEBUG
    environment variable is set.
    """
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        if os.getenv("OCODE_DEBUG"):
            import traceback

            console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
