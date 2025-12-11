"""Simple status line widget for the TUI."""

from textual.widgets import Static


class StatusLine(Static):
    """Displays latency and token counts."""

    def update_metrics(self, latency_ms: int, tokens: int) -> None:
        self.update(f"Latency: {latency_ms} ms | Tokens: {tokens}")
