"""
Textual-based TUI shell for OCode.

This provides a modern, keyboard-driven interface with panels for conversation,
context, and quick actions. It is intentionally thin for now and can be expanded
incrementally without disturbing the existing Click CLI.
"""

from __future__ import annotations

from typing import Optional

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Log, OptionList, Static

from ..utils.file_operations import read_file_safely  # type: ignore
from .status_line import StatusLine


class OCodeTui(App):
    """Minimal Textual shell with conversation + context panes."""

    CSS_PATH = "tui.tcss"
    BINDINGS = [
        ("ctrl+p", "open_palette", "Command palette"),
        ("ctrl+l", "clear_log", "Clear conversation"),
        ("ctrl+b", "toggle_context", "Toggle context"),
        ("ctrl+y", "copy_code_block", "Copy last code block"),
        ("ctrl+q", "quit", "Quit"),
    ]

    show_context = reactive(True)

    def __init__(self, engine=None, **kwargs):
        super().__init__(**kwargs)
        self.engine = engine

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield ToastBar(id="toast")
        with Horizontal(id="body"):
            with Vertical(id="conversation"):
                yield Log(id="log", auto_scroll=True)
                yield Input(placeholder="Ask OCode…", id="prompt")
            with Vertical(id="context", classes="context-visible"):
                yield OptionList(id="context-list")
                yield Static("Select an item to preview.", id="context-content")
        yield StatusLine(id="status")
        yield Footer()

    def on_mount(self) -> None:
        toast = self.query_one(ToastBar)
        toast.display = False
        self.query_one(Log).write(
            "[b]OCode TUI ready[/b]. Press Ctrl+P to open the palette."
        )
        self.show_toast("TUI ready", style="green")
        self._populate_context()

    def action_focus_prompt(self) -> None:
        self.query_one(Input).focus()

    def action_clear_log(self) -> None:
        log = self.query_one(Log)
        log.clear()
        self.show_toast("Log cleared", style="yellow")

    def action_toggle_context(self) -> None:
        self.show_context = not self.show_context
        context_container = self.query_one("#context")
        context_container.display = self.show_context
        self.show_toast(
            "Context shown" if self.show_context else "Context hidden",
            style="cyan",
        )

    def action_open_palette(self) -> None:
        self.push_screen(CommandPaletteScreen())

    def action_copy_code_block(self) -> None:
        if not getattr(self, "last_code_block", None):
            self.show_toast("No code block found yet", style="yellow")
            return
        # Textual doesn't expose clipboard on all platforms; store for reference.
        self.copied_code_block = self.last_code_block
        self.show_toast("Copied last code block", style="green")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        prompt = event.value.strip()
        if not prompt:
            return
        log = self.query_one(Log)
        log.write(f"[bold cyan]You:[/bold cyan] {prompt}")
        event.input.value = ""

        import time

        start = time.time()
        tokens = 0

        if self.engine is None:
            log.write("[dim]Engine not wired yet; placeholder response.[/dim]")
            return

        # Stream from engine if available
        try:
            async for chunk in self.engine.stream_prompt(prompt):
                if chunk:
                    log.write(chunk)
                    tokens += len(chunk.split())
                    self._update_last_code_block(chunk)
            elapsed_ms = int((time.time() - start) * 1000)
            self.query_one(StatusLine).update_metrics(elapsed_ms, tokens)
            self.show_toast(f"Done in {elapsed_ms} ms • {tokens} tokens", style="green")
        except Exception as exc:  # pragma: no cover - defensive
            log.write(f"[red]Error:[/red] {exc}")

    async def on_key(self, event: events.Key) -> None:
        # Enter in the prompt already handled by Input.Submitted; skip global handling
        if event.key == "escape":
            self.action_focus_prompt()

    def show_toast(self, message: str, *, style: str = "white", duration: float = 2.5):
        """Display a transient toast message in the header area."""
        toast = self.query_one("#toast", ToastBar)
        toast.show(message, style=style, duration=duration)

    def _populate_context(self) -> None:
        """Fill the context list from the engine if possible."""
        items = []
        if self.engine:
            if hasattr(self.engine, "get_context_files"):
                items = list(
                    self.engine.get_context_files()  # type: ignore[attr-defined]
                )
            elif hasattr(self.engine, "context_manager"):
                recent = getattr(self.engine.context_manager, "recent_files", None)
                if recent:
                    items = [(path, "") for path in recent]
        if not items:
            from pathlib import Path

            cwd = Path.cwd()
            sample = cwd / "README.md"
            items = [(sample, "")]

        opt_list = self.query_one("#context-list", OptionList)
        opt_list.clear_options()
        for path, _ in items:
            opt_list.add_option(OptionList.Option(str(path), id=str(path)))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Preview selected context file."""
        path = event.option.id
        preview = "Unavailable"
        try:
            content = read_file_safely(path, max_bytes=4000)  # type: ignore
            preview = content or "(empty file)"
        except Exception:
            preview = "(unable to read file)"
        self.query_one("#context-content", Static).update(preview)

    def _update_last_code_block(self, chunk: str) -> None:
        """Track most recent fenced code block for copy shortcut."""
        if "```" not in chunk:
            return
        parts = chunk.split("```")
        if len(parts) >= 3:
            self.last_code_block = parts[-2].strip()


class CommandPaletteScreen(ModalScreen):
    """Simple command palette."""

    def compose(self) -> ComposeResult:
        options = OptionList(
            OptionList.Option("Focus prompt", id="focus"),
            OptionList.Option("Toggle context", id="toggle_context"),
            OptionList.Option("Clear conversation", id="clear_log"),
            OptionList.Option("Quit", id="quit"),
        )
        options.border_title = "Command Palette"
        return options

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        choice = event.option.id
        app: OCodeTui = self.app  # type: ignore[assignment]
        if choice == "focus":
            app.action_focus_prompt()
        elif choice == "toggle_context":
            app.action_toggle_context()
        elif choice == "clear_log":
            app.action_clear_log()
        elif choice == "quit":
            app.exit()
        self.app.pop_screen()


class ToastBar(Static):
    """Lightweight toast area that auto-hides."""

    def show(self, message: str, *, style: str = "white", duration: float = 2.5):
        self.update(f"[{style}]{message}[/{style}]")
        self.display = True
        if duration:
            self.set_timer(duration, lambda: self.hide())

    def hide(self):
        self.display = False


def run_tui(engine: Optional[object] = None) -> None:
    """Entry helper to launch the Textual app."""
    app = OCodeTui(engine=engine)
    # Textual manages its own loop; run() blocks until exit.
    app.run()
