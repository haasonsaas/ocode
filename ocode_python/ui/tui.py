"""
Textual-based TUI shell for OCode.

This provides a modern, keyboard-driven interface with panels for conversation,
context, and quick actions. It is intentionally thin for now and can be expanded
incrementally without disturbing the existing Click CLI.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Input, Static, TextLog


class OCodeTui(App):
    """Minimal Textual shell with conversation + context panes."""

    CSS_PATH = "tui.tcss"
    BINDINGS = [
        ("ctrl+p", "focus_prompt", "Focus prompt"),
        ("ctrl+l", "clear_log", "Clear conversation"),
        ("ctrl+b", "toggle_context", "Toggle context"),
        ("ctrl+q", "quit", "Quit"),
    ]

    show_context = reactive(True)

    def __init__(self, engine=None, **kwargs):
        super().__init__(**kwargs)
        self.engine = engine

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            with Vertical(id="conversation"):
                yield TextLog(id="log", highlight=True, markup=True)
                yield Input(placeholder="Ask OCode…", id="prompt")
            with Vertical(id="context", classes="context-visible"):
                yield Static("Context will appear here.", id="context-content")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(TextLog).write("[b]OCode TUI ready[/b]. Press Ctrl+P to focus the prompt.")

    def action_focus_prompt(self) -> None:
        self.query_one(Input).focus()

    def action_clear_log(self) -> None:
        self.query_one(TextLog).clear()

    def action_toggle_context(self) -> None:
        self.show_context = not self.show_context
        context_container = self.query_one("#context")
        context_container.display = self.show_context

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        prompt = event.value.strip()
        if not prompt:
            return
        log = self.query_one(TextLog)
        log.write(f"[bold cyan]You:[/bold cyan] {prompt}")
        event.input.value = ""

        if self.engine is None:
            log.write("[dim]Engine not wired yet; placeholder response.[/dim]")
            return

        # Stream from engine if available
        try:
            async for chunk in self.engine.stream_prompt(prompt):
                if chunk:
                    log.write(chunk, end="")
            log.write("")  # newline after stream
        except Exception as exc:  # pragma: no cover - defensive
            log.write(f"[red]Error:[/red] {exc}")

    async def on_key(self, event: events.Key) -> None:
        # Enter in the prompt already handled by Input.Submitted; skip global handling
        if event.key == "escape":
            self.action_focus_prompt()


def run_tui(engine: Optional[object] = None) -> None:
    """Entry helper to launch the Textual app."""
    app = OCodeTui(engine=engine)
    # Textual manages its own loop; run() blocks until exit.
    app.run()

