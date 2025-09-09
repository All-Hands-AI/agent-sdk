from typing import Dict

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from openhands.sdk.event import (
    ActionEvent,
    AgentErrorEvent,
    Event,
    MessageEvent,
    ObservationEvent,
    PauseEvent,
    SystemPromptEvent,
)


class ConversationVisualizer:
    """Handles visualization of conversation events with Rich formatting.

    Provides Rich-formatted output with panels and complete content display.
    """

    def __init__(self, highlight_regex: Dict[str, str] | None = None):
        """Initialize the visualizer.

        Args:
            highlight_regex: Dictionary mapping regex patterns to Rich color styles
                           for highlighting keywords in the visualizer.
                           For example: {"Reasoning:": "bold blue",
                           "Thought:": "bold green"}
        """
        self._console = Console()
        self._highlight_patterns: Dict[str, str] = highlight_regex or {}

    def on_event(self, event: Event) -> None:
        """Main event handler that displays events with Rich formatting."""
        panel = self._create_event_panel(event)
        self._console.print(panel)
        self._console.print()  # Add spacing between events

    def _apply_highlighting(self, text: Text) -> Text:
        """Apply regex-based highlighting to text content.

        Args:
            text: The Rich Text object to highlight

        Returns:
            A new Text object with highlighting applied
        """
        if not self._highlight_patterns:
            return text

        # Create a copy to avoid modifying the original
        highlighted = text.copy()

        # Apply each pattern using Rich's built-in highlight_regex method
        for pattern, style in self._highlight_patterns.items():
            highlighted.highlight_regex(pattern, style)

        return highlighted

    def _create_event_panel(self, event: Event) -> Panel:
        """Create a Rich Panel for the event with appropriate styling."""
        # Use the event's visualize property for content
        content = event.visualize

        # Apply highlighting if configured
        if self._highlight_patterns:
            content = self._apply_highlighting(content)

        # Determine panel styling based on event type
        if isinstance(event, SystemPromptEvent):
            return Panel(
                content,
                title="[bold magenta]System Prompt[/bold magenta]",
                border_style="magenta",
                expand=True,
            )
        elif isinstance(event, ActionEvent):
            return Panel(
                content,
                title="[bold green]Agent Action[/bold green]",
                subtitle=self._format_metrics_subtitle(event),
                border_style="green",
                expand=True,
            )
        elif isinstance(event, ObservationEvent):
            return Panel(
                content,
                title="[bold blue]Tool Observation[/bold blue]",
                border_style="blue",
                expand=True,
            )
        elif isinstance(event, MessageEvent):
            # Role-based styling
            role_colors = {
                "user": "bright_cyan",
                "assistant": "bright_green",
                "system": "bright_magenta",
            }
            role_color = role_colors.get(event.llm_message.role, "white")

            # Panel styling based on role
            panel_colors = {
                "user": "cyan",
                "assistant": "green",
                "system": "magenta",
            }
            border_color = panel_colors.get(event.llm_message.role, "white")

            title_text = (
                f"[bold {role_color}]Message (source={event.source})"
                f"[/bold {role_color}]"
            )
            return Panel(
                content,
                title=title_text,
                subtitle=self._format_metrics_subtitle(event),
                border_style=border_color,
                expand=True,
            )
        elif isinstance(event, AgentErrorEvent):
            return Panel(
                content,
                title="[bold red]Agent Error[/bold red]",
                subtitle=self._format_metrics_subtitle(event),
                border_style="red",
                expand=True,
            )
        elif isinstance(event, PauseEvent):
            return Panel(
                content,
                title="[bold yellow]User Paused[/bold yellow]",
                border_style="yellow",
                expand=True,
            )
        else:
            # Fallback panel for unknown event types
            return Panel(
                content,
                title=f"[bold blue]{event.__class__.__name__}[/bold blue]",
                subtitle=f"[dim]({event.source})[/dim]",
                border_style="blue",
                expand=True,
            )

    def _format_metrics_subtitle(
        self, event: ActionEvent | MessageEvent | AgentErrorEvent
    ) -> str | None:
        """Format LLM metrics as a visually appealing subtitle string with icons,
        colors, and k/m abbreviations (cache hit rate only)."""
        if not event.metrics or not event.metrics.accumulated_token_usage:
            return None

        usage = event.metrics.accumulated_token_usage
        cost = event.metrics.accumulated_cost or 0.0

        # helper: 1234 -> "1.2K", 1200000 -> "1.2M"
        def abbr(n: int | float) -> str:
            n = int(n or 0)
            if n >= 1_000_000_000:
                s = f"{n / 1_000_000_000:.2f}B"
            elif n >= 1_000_000:
                s = f"{n / 1_000_000:.2f}M"
            elif n >= 1_000:
                s = f"{n / 1_000:.2f}K"
            else:
                return str(n)
            return s.replace(".0", "")

        input_tokens = abbr(usage.prompt_tokens or 0)
        output_tokens = abbr(usage.completion_tokens or 0)

        # Cache hit rate (prompt + cache)
        prompt = usage.prompt_tokens or 0
        cache_read = usage.cache_read_tokens or 0
        cache_rate = f"{(cache_read / prompt * 100):.2f}%" if prompt > 0 else "N/A"
        reasoning_tokens = usage.reasoning_tokens or 0

        # Cost
        cost_str = f"{cost:.4f}" if cost > 0 else "$0.00"

        # Build with fixed color scheme
        parts: list[str] = []
        parts.append(f"[cyan]↑ input {input_tokens}[/cyan]")
        parts.append(f"[magenta]cache hit {cache_rate}[/magenta]")
        if reasoning_tokens > 0:
            parts.append(f"[yellow] reasoning {abbr(reasoning_tokens)}[/yellow]")
        parts.append(f"[blue]↓ output {output_tokens}[/blue]")
        parts.append(f"[green]$ {cost_str}[/green]")

        return "Tokens: " + " [dim]•[/dim] ".join(parts)


def create_default_visualizer(
    highlight_regex: Dict[str, str] | None = None,
) -> ConversationVisualizer:
    """Create a default conversation visualizer instance.

    Args:
        highlight_regex: Dictionary mapping regex patterns to Rich color styles
                       for highlighting keywords in the visualizer.
                       For example: {"Reasoning:": "bold blue",
                       "Thought:": "bold green"}
    """
    return ConversationVisualizer(highlight_regex=highlight_regex)
