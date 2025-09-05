from typing import cast

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from openhands.sdk.event import EventType
from openhands.sdk.event.llm_convertible import (
    ActionEvent,
    AgentErrorEvent,
    MessageEvent,
    ObservationEvent,
    SystemPromptEvent,
)
from openhands.sdk.llm import ImageContent, TextContent


class ConversationVisualizer:
    """Handles visualization of conversation events with Rich formatting.

    Provides Rich-formatted output with panels and complete content display.
    """

    def __init__(self):
        self._console = Console()

    def on_event(self, event: EventType) -> None:
        """Main event handler that displays events with Rich formatting."""
        panel = self._create_event_panel(event)
        self._console.print(panel)
        self._console.print()  # Add spacing between events

    def _create_event_panel(self, event: EventType) -> Panel:
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
        content.append(f"\n\nTools Available: {len(event.tools)}", style="dim cyan")

        return Panel(
            content,
            title="[bold magenta]System Prompt[/bold magenta]",
            subtitle=f"[dim]({event.source})[/dim]",
            border_style="magenta",
            expand=True,
        )

    def _create_action_panel(self, event: ActionEvent) -> Panel:
        """Create a Rich Panel for ActionEvent with complete content."""
        content = Text()

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
            subtitle=f"[dim]({event.source})[/dim]",
            border_style="green",
            expand=True,
        )

    def _create_observation_panel(self, event: ObservationEvent) -> Panel:
        """Create a Rich Panel for ObservationEvent with complete content."""
        content = Text()
        content.append("Tool: ", style="bold blue")
        content.append(event.tool_name, style="cyan")
        content.append("\n\nResult:\n", style="bold blue")
        content.append(event.observation.agent_observation, style="white")

        return Panel(
            content,
            title="[bold blue]Tool Observation[/bold blue]",
            subtitle=f"[dim]({event.source})[/dim]",
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

        # Extract and display all content
        def _display_content(contents: list[TextContent | ImageContent]) -> list[str]:
            text_parts = []
            for content_item in contents:
                if isinstance(content_item, TextContent):
                    text_parts.append(content_item.text)
                elif isinstance(content_item, ImageContent):
                    text_parts.append(f"[Image: {len(content_item.image_urls)} URLs]")
            return text_parts

        text_parts = _display_content(event.llm_message.content)
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
            text_parts = _display_content(
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
            f"[bold {role_color}]Message ({event.llm_message.role})[/bold {role_color}]"
        )
        return Panel(
            content,
            title=title_text,
            subtitle=f"[dim]({event.source})[/dim]",
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
            subtitle=f"[dim]({event.source})[/dim]",
            border_style="red",
            expand=True,
        )
