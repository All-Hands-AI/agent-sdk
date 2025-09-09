import json
from typing import cast

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
from openhands.sdk.llm import ImageContent, TextContent, content_to_str


class ConversationVisualizer:
    """Handles visualization of conversation events with Rich formatting.

    Provides Rich-formatted output with panels and complete content display.
    """

    def __init__(self):
        self._console = Console()

    def on_event(self, event: Event) -> None:
        """Main event handler that displays events with Rich formatting."""
        panel = self._create_event_panel(event)
        self._console.print(panel)
        self._console.print()  # Add spacing between events

    def _create_event_panel(self, event: Event) -> Panel:
        """Create a Rich Panel for the event with appropriate styling."""
        if isinstance(event, SystemPromptEvent):
            return self._create_system_prompt_panel(event)
        elif isinstance(event, ActionEvent):
            return self._create_action_panel(event)
        elif isinstance(event, ObservationEvent):
            return self._create_observation_panel(event)
        elif isinstance(event, MessageEvent):
            return self._create_message_panel(event)
        elif isinstance(event, AgentErrorEvent):
            return self._create_error_panel(event)
        elif isinstance(event, PauseEvent):
            return self._create_pause_panel(event)
        else:
            # Fallback panel for unknown event types
            content = Text(f"Unknown event type: {event.__class__.__name__}")
            return Panel(
                content,
                title=f"[bold blue]{event.__class__.__name__}[/bold blue]",
                subtitle=f"[dim]({event.source})[/dim]",
                border_style="blue",
                expand=True,
            )

    def _create_system_prompt_panel(self, event: SystemPromptEvent) -> Panel:
        """Create a Rich Panel for SystemPromptEvent with complete content."""
        content = Text()
        content.append("System Prompt:\n", style="bold cyan")
        content.append(event.system_prompt.text, style="white")
        content.append(f"\n\nTools Available: {len(event.tools)}", style="cyan")
        for tool in event.tools:
            tool_fn = tool.get("function", None)
            # make each field short
            for k, v in tool.items():
                if isinstance(v, str) and len(v) > 30:
                    tool[k] = v[:27] + "..."
            if tool_fn:
                assert "name" in tool_fn
                assert "description" in tool_fn
                assert "parameters" in tool_fn
                params_str = json.dumps(tool_fn["parameters"])
                content.append(
                    f"\n  - {tool_fn['name']}: "
                    f"{tool_fn['description'].split('\n')[0][:100]}...\n",
                    style="dim cyan",
                )
                content.append(f"  Parameters: {params_str}", style="dim white")
            else:
                content.append(
                    f"\n  - Cannot access .function for {tool}", style="dim cyan"
                )

        return Panel(
            content,
            title="[bold magenta]System Prompt[/bold magenta]",
            border_style="magenta",
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

    def _create_action_panel(self, event: ActionEvent) -> Panel:
        """Create a Rich Panel for ActionEvent with complete content."""
        content = Text()

        # Display reasoning content first if available (common to all three types)
        if event.reasoning_content:
            content.append("Reasoning:\n", style="bold magenta")
            content.append(event.reasoning_content, style="white")
            content.append("\n\n")

        # Display complete thought content
        thought_text = " ".join([t.text for t in event.thought])
        if thought_text:
            content.append("Thought:\n", style="bold green")
            content.append(thought_text, style="white")
            content.append("\n\n")

        # Display action information
        action_name = event.action.__class__.__name__
        content.append("Action: ", style="bold green")
        content.append(action_name, style="yellow")
        content.append("\n\n")

        # Display all action fields systematically
        content.append("Action Fields:\n", style="bold green")
        action_fields = event.action.model_dump()
        for field_name, field_value in action_fields.items():
            content.append(f"  {field_name}: ", style="cyan")
            if field_value is None:
                content.append("None", style="dim white")
            elif isinstance(field_value, str):
                # Handle multiline strings with proper indentation
                if "\n" in field_value:
                    content.append("\n", style="white")
                    for line in field_value.split("\n"):
                        content.append(f"    {line}\n", style="white")
                else:
                    content.append(f'"{field_value}"', style="white")
            elif isinstance(field_value, (list, dict)):
                content.append(str(field_value), style="white")
            else:
                content.append(str(field_value), style="white")
            content.append("\n")

        return Panel(
            content,
            title="[bold green]Agent Action[/bold green]",
            subtitle=self._format_metrics_subtitle(event),
            border_style="green",
            expand=True,
        )

    def _create_observation_panel(self, event: ObservationEvent) -> Panel:
        """Create a Rich Panel for ObservationEvent with complete content."""
        content = Text()
        content.append("Tool: ", style="bold blue")
        content.append(event.tool_name, style="cyan")
        content.append("\n\nResult:\n", style="bold blue")

        text_parts = content_to_str(event.observation.agent_observation)
        if text_parts:
            full_content = " ".join(text_parts)
            content.append(full_content, style="white")
        else:
            content.append("[no text content]", style="dim white")

        return Panel(
            content,
            title="[bold blue]Tool Observation[/bold blue]",
            border_style="blue",
            expand=True,
        )

    def _create_message_panel(self, event: MessageEvent) -> Panel:
        """Create a Rich Panel for MessageEvent with complete content."""
        content = Text()

        # Role-based styling
        role_colors = {
            "user": "bright_cyan",
            "assistant": "bright_green",
            "system": "bright_magenta",
        }
        role_color = role_colors.get(event.llm_message.role, "white")

        content.append(
            f"{event.llm_message.role.title()}:\n", style=f"bold {role_color}"
        )

        text_parts = content_to_str(event.llm_message.content)
        if text_parts:
            full_content = " ".join(text_parts)
            content.append(full_content, style="white")
        else:
            content.append("[no text content]", style="dim white")

        # Add microagent information if present
        if event.activated_microagents:
            content.append(
                f"\n\nActivated Microagents: {', '.join(event.activated_microagents)}",
                style="dim yellow",
            )

        # Add extended content if available
        if event.extended_content:
            assert not any(
                isinstance(c, ImageContent) for c in event.extended_content
            ), "Extended content should not contain images"
            text_parts = content_to_str(
                cast(list[TextContent | ImageContent], event.extended_content)
            )
            content.append("\n\nExtended Content:\n", style="dim yellow")
            content.append(" ".join(text_parts), style="white")

        # Panel styling based on role
        panel_colors = {
            "user": "cyan",
            "assistant": "green",
            "system": "magenta",
        }
        border_color = panel_colors.get(event.llm_message.role, "white")

        title_text = (
            f"[bold {role_color}]Message (source={event.source})[/bold {role_color}]"
        )
        return Panel(
            content,
            title=title_text,
            subtitle=self._format_metrics_subtitle(event),
            border_style=border_color,
            expand=True,
        )

    def _create_error_panel(self, event: AgentErrorEvent) -> Panel:
        """Create a Rich Panel for AgentErrorEvent with complete content."""
        content = Text()

        content.append("Error Details:\n", style="bold red")
        content.append(event.error, style="bright_red")

        return Panel(
            content,
            title="[bold red]Agent Error[/bold red]",
            subtitle=self._format_metrics_subtitle(event),
            border_style="red",
            expand=True,
        )

    def _create_pause_panel(self, event: PauseEvent) -> Panel:
        """Create a Rich Panel for PauseEvent with complete content."""
        content = Text()
        content.append("Conversation Paused", style="bold yellow")

        return Panel(
            content,
            title="[bold yellow]User Paused[/bold yellow]",
            border_style="yellow",
            expand=True,
        )
