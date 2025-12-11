import asyncio

import pytest
from textual.pilot import Pilot

from ocode_python.ui.tui import OCodeTui


class MockEngine:
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
