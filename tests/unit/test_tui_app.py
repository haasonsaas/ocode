"""Tests for the Textual TUI shell."""

import asyncio

import pytest
from textual.pilot import Pilot
from textual.widgets import OptionList

from ocode_python.ui.tui import OCodeTui


class MockEngine:
    """Tiny engine stub for streaming tests."""

    async def stream_prompt(self, prompt: str):
        yield "Hello "
        yield "world"


@pytest.mark.asyncio
async def test_tui_renders_and_streams():
    async with OCodeTui(engine=MockEngine()).run_test() as pilot:  # type: Pilot
        prompt = pilot.app.query_one("#prompt")
        prompt.value = "test"
        await prompt.action_submit()
        await pilot.pause()
        log = pilot.app.query_one("#log")
        assert any("Hello world" in line for line in log.lines)


@pytest.mark.asyncio
async def test_toggle_context():
    async with OCodeTui(engine=MockEngine()).run_test() as pilot:
        context = pilot.app.query_one("#context")
        assert context.display is True
        pilot.app.action_toggle_context()
        assert context.display is False


@pytest.mark.asyncio
async def test_command_palette_toggle_context():
    async with OCodeTui(engine=MockEngine()).run_test() as pilot:
        # Open palette
        await pilot.press("ctrl+p")
        await pilot.pause(0.05)
        # Palette should be on the screen stack
        assert len(pilot.app._screen_stack) > 1  # type: ignore[attr-defined]
        # Close palette
        await pilot.press("escape")
        await pilot.pause(0.05)
        # Invoke the same action directly to ensure it works
        pilot.app.action_toggle_context()
        context = pilot.app.query_one("#context")
        assert context.display is False


"""Tests for the Textual TUI shell."""
