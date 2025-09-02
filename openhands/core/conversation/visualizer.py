from rich.console import Console

from openhands.core.event import EventType
from openhands.core.event.llm_convertible import (
    ActionEvent,
    AgentErrorEvent,
    MessageEvent,
    ObservationEvent,
    SystemPromptEvent,
)
from openhands.core.llm import ImageContent, TextContent


class ConversationVisualizer:
    """Handles visualization of conversation events with Rich formatting.

    Provides Rich-formatted output while keeping the event's __str__ methods clean.
    """

    def __init__(self):
        self._console = Console()

    def on_event(self, event: EventType) -> None:
        """Main event handler that displays events with Rich formatting."""
        rich_formatted = self._format_event_rich(event)
        self._console.print(rich_formatted)

    def _format_event_rich(self, event: EventType) -> str:
        """Format an event with Rich markup for enhanced display."""
        if isinstance(event, SystemPromptEvent):
            return self._format_system_prompt_rich(event)
        elif isinstance(event, ActionEvent):
            return self._format_action_rich(event)
        elif isinstance(event, ObservationEvent):
            return self._format_observation_rich(event)
        elif isinstance(event, MessageEvent):
            return self._format_message_rich(event)
        elif isinstance(event, AgentErrorEvent):
            return self._format_error_rich(event)
        else:
            # Fallback to base formatting with Rich styling
            return (
                f"[bold blue]{event.__class__.__name__}[/bold blue] "
                f"[dim]({event.source})[/dim]"
            )

    def _format_system_prompt_rich(self, event: SystemPromptEvent) -> str:
        """Rich-formatted string representation for SystemPromptEvent."""
        base_str = (
            f"[bold blue]{event.__class__.__name__}[/bold blue] "
            f"[dim]({event.source})[/dim]"
        )
        prompt_preview = (
            event.system_prompt.text[:100] + "..."
            if len(event.system_prompt.text) > 100
            else event.system_prompt.text
        )
        tool_count = len(event.tools)
        return (
            f"{base_str}\n[dim]  System: {prompt_preview}[/dim]\n"
            f"[dim]  Tools: {tool_count} available[/dim]"
        )

    def _format_action_rich(self, event: ActionEvent) -> str:
        """Rich-formatted string representation for ActionEvent."""
        base_str = (
            f"[bold blue]{event.__class__.__name__}[/bold blue] "
            f"[dim]({event.source})[/dim]"
        )
        thought_text = " ".join([t.text for t in event.thought])
        thought_preview = (
            thought_text[:80] + "..." if len(thought_text) > 80 else thought_text
        )
        action_name = event.action.__class__.__name__
        return (
            f"{base_str}\n[dim]  Thought: {thought_preview}[/dim]\n"
            f"[dim]  Action: {action_name}[/dim]"
        )

    def _format_observation_rich(self, event: ObservationEvent) -> str:
        """Rich-formatted string representation for ObservationEvent."""
        base_str = (
            f"[bold blue]{event.__class__.__name__}[/bold blue] "
            f"[dim]({event.source})[/dim]"
        )
        obs_preview = (
            event.observation.agent_observation[:100] + "..."
            if len(event.observation.agent_observation) > 100
            else event.observation.agent_observation
        )
        return (
            f"{base_str}\n[dim]  Tool: {event.tool_name}[/dim]\n"
            f"[dim]  Result: {obs_preview}[/dim]"
        )

    def _format_message_rich(self, event: MessageEvent) -> str:
        """Rich-formatted string representation for MessageEvent."""
        base_str = (
            f"[bold blue]{event.__class__.__name__}[/bold blue] "
            f"[dim]({event.source})[/dim]"
        )
        # Extract text content from the message
        text_parts = []
        for content in event.llm_message.content:
            if isinstance(content, TextContent):
                text_parts.append(content.text)
            elif isinstance(content, ImageContent):
                text_parts.append(f"[Image: {len(content.image_urls)} URLs]")

        if text_parts:
            content_preview = " ".join(text_parts)
            if len(content_preview) > 100:
                content_preview = content_preview[:97] + "..."
            microagent_info = (
                f" [Microagents: {', '.join(event.activated_microagents)}]"
                if event.activated_microagents
                else ""
            )
            return (
                f"{base_str}\n[dim]  {event.llm_message.role}: "
                f"{content_preview}{microagent_info}[/dim]"
            )
        else:
            return (
                f"{base_str}\n[dim]  {event.llm_message.role}: [no text content][/dim]"
            )

    def _format_error_rich(self, event: AgentErrorEvent) -> str:
        """Rich-formatted string representation for AgentErrorEvent."""
        base_str = (
            f"[bold blue]{event.__class__.__name__}[/bold blue] "
            f"[dim]({event.source})[/dim]"
        )
        error_preview = (
            event.error[:100] + "..." if len(event.error) > 100 else event.error
        )
        return f"{base_str}\n[dim red]  Error: {error_preview}[/dim red]"
