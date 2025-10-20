import re
from typing import TYPE_CHECKING, Any

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from openhands.sdk.event import (
    ActionEvent,
    AgentErrorEvent,
    MessageEvent,
    ObservationEvent,
    PauseEvent,
    StreamingDeltaEvent,
    SystemPromptEvent,
    UserRejectObservation,
)
from openhands.sdk.event.base import Event
from openhands.sdk.event.condenser import Condensation
from openhands.sdk.llm.llm import RESPONSES_COMPLETION_EVENT_TYPES
from openhands.sdk.llm.streaming import StreamPartKind


if TYPE_CHECKING:
    from openhands.sdk.conversation.conversation_stats import ConversationStats
    from openhands.sdk.llm.streaming import LLMStreamChunk


# These are external inputs
_OBSERVATION_COLOR = "yellow"
_MESSAGE_USER_COLOR = "gold3"
_PAUSE_COLOR = "bright_yellow"
# These are internal system stuff
_SYSTEM_COLOR = "magenta"
_THOUGHT_COLOR = "bright_black"
_ERROR_COLOR = "red"
# These are agent actions
_ACTION_COLOR = "blue"
_MESSAGE_ASSISTANT_COLOR = _ACTION_COLOR

DEFAULT_HIGHLIGHT_REGEX = {
    r"^Reasoning:": f"bold {_THOUGHT_COLOR}",
    r"^Thought:": f"bold {_THOUGHT_COLOR}",
    r"^Action:": f"bold {_ACTION_COLOR}",
    r"^Arguments:": f"bold {_ACTION_COLOR}",
    r"^Tool:": f"bold {_OBSERVATION_COLOR}",
    r"^Result:": f"bold {_OBSERVATION_COLOR}",
    r"^Rejection Reason:": f"bold {_ERROR_COLOR}",
    # Markdown-style
    r"\*\*(.*?)\*\*": "bold",
    r"\*(.*?)\*": "italic",
}

_PANEL_PADDING = (1, 1)
_SECTION_CONFIG: dict[str, tuple[str, str]] = {
    "reasoning": ("Reasoning", _THOUGHT_COLOR),
    "assistant": ("Assistant", _ACTION_COLOR),
    "function_arguments": ("Function Arguments", _ACTION_COLOR),
    "tool_output": ("Tool Output", _ACTION_COLOR),
    "refusal": ("Refusal", _ERROR_COLOR),
}

_SESSION_CONFIG: dict[str, tuple[str, str]] = {
    "message": (
        f"[bold {_MESSAGE_ASSISTANT_COLOR}]Message from Agent (streaming)"  # type: ignore[str-format]
        f"[/bold {_MESSAGE_ASSISTANT_COLOR}]",
        _MESSAGE_ASSISTANT_COLOR,
    ),
    "action": (
        f"[bold {_ACTION_COLOR}]Agent Action (streaming)[/bold {_ACTION_COLOR}]",
        _ACTION_COLOR,
    ),
}

_SECTION_ORDER = [
    "reasoning",
    "assistant",
    "function_arguments",
    "tool_output",
    "refusal",
]


class _StreamSection:
    def __init__(self, header: str, style: str) -> None:
        self.header = header
        self.style = style
        self.content: str = ""


class _StreamSession:
    def __init__(
        self,
        *,
        console: Console,
        session_type: str,
        response_id: str | None,
        output_index: int | None,
        use_live: bool,
    ) -> None:
        self._console = console
        self._session_type = session_type
        self._response_id = response_id
        self._output_index = output_index
        self._use_live = use_live
        self._sections: dict[str, _StreamSection] = {}
        self._order: list[str] = []
        self._live: Live | None = None
        self._last_renderable: Panel | None = None

    @property
    def response_id(self) -> str | None:
        return self._response_id

    def append_text(self, section_key: str, text: str | None) -> None:
        if not text:
            return
        header, style = _SECTION_CONFIG.get(section_key, (section_key.title(), "cyan"))
        section = self._sections.get(section_key)
        if section is None:
            section = _StreamSection(header, style)
            self._sections[section_key] = section
            self._order.append(section_key)
            self._order.sort(
                key=lambda key: _SECTION_ORDER.index(key)
                if key in _SECTION_ORDER
                else len(_SECTION_ORDER)
            )
        section.content += text
        self._update()

    def finish(self, *, persist: bool) -> None:
        renderable = self._render_panel()
        if self._use_live:
            if self._live is not None:
                self._live.stop()
                self._live = None
            if persist:
                self._console.print(renderable)
                self._console.print()
            else:
                self._console.print()
        else:
            if persist:
                self._console.print(renderable)
                self._console.print()

    def _update(self) -> None:
        renderable = self._render_panel()
        if self._use_live:
            if self._live is None:
                self._live = Live(
                    renderable,
                    console=self._console,
                    refresh_per_second=24,
                    transient=True,
                )
                self._live.start()
            else:
                self._live.update(renderable)
        else:
            self._last_renderable = renderable

    def _render_panel(self) -> Panel:
        body_parts: list[Any] = []
        for key in self._order:
            section = self._sections[key]
            if not section.content:
                continue
            body_parts.append(Text(f"{section.header}:", style=f"bold {section.style}"))
            body_parts.append(Text(section.content, style=section.style))
        if not body_parts:
            body_parts.append(Text("[streaming...]", style="dim"))

        title, border_style = _SESSION_CONFIG.get(
            self._session_type, ("[bold cyan]Streaming[/bold cyan]", "cyan")
        )
        return Panel(
            Group(*body_parts),
            title=title,
            border_style=border_style,
            padding=_PANEL_PADDING,
            expand=True,
        )


class ConversationVisualizer:
    """Handles visualization of conversation events with Rich formatting.

    Provides Rich-formatted output with panels and complete content display.
    """

    def __init__(
        self,
        highlight_regex: dict[str, str] | None = None,
        skip_user_messages: bool = False,
        conversation_stats: "ConversationStats | None" = None,
    ):
        """Initialize the visualizer.

        Args:
            highlight_regex: Dictionary mapping regex patterns to Rich color styles
                           for highlighting keywords in the visualizer.
                           For example: {"Reasoning:": "bold blue",
                           "Thought:": "bold green"}
            skip_user_messages: If True, skip displaying user messages. Useful for
                                scenarios where user input is not relevant to show.
            conversation_stats: ConversationStats object to display metrics information.
        """
        self._console = Console()
        self._skip_user_messages = skip_user_messages
        base_patterns = dict(DEFAULT_HIGHLIGHT_REGEX)
        if highlight_regex:
            base_patterns.update(highlight_regex)
        self._highlight_patterns = base_patterns
        self._conversation_stats = conversation_stats
        self._use_live = self._console.is_terminal
        self._stream_sessions: dict[tuple[str, int, str], _StreamSession] = {}

    def on_event(self, event: Event) -> None:
        """Main event handler that displays events with Rich formatting."""
        if isinstance(event, StreamingDeltaEvent):
            self._render_streaming_event(event)
            return

        panel = self._create_event_panel(event)  # pyright: ignore[reportAttributeAccessIssue]
        if panel:
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
            pattern_compiled = re.compile(pattern, re.MULTILINE)
            highlighted.highlight_regex(pattern_compiled, style)

        return highlighted

    def _render_streaming_event(self, event: StreamingDeltaEvent) -> None:
        self._handle_stream_chunk(event.stream_chunk, persist_on_finish=False)

    def _handle_stream_chunk(
        self, stream_chunk: "LLMStreamChunk", *, persist_on_finish: bool
    ) -> None:
        if stream_chunk.part_kind == "status":
            if (
                stream_chunk.type in RESPONSES_COMPLETION_EVENT_TYPES
                or stream_chunk.is_final
            ):
                self._finish_stream_sessions(
                    stream_chunk.response_id, persist=persist_on_finish
                )
            return

        session_type = self._session_type_for_part(stream_chunk.part_kind)
        if session_type is None:
            return

        key = self._make_stream_session_key(stream_chunk, session_type)
        session = self._stream_sessions.get(key)
        if session is None:
            session = _StreamSession(
                console=self._console,
                session_type=session_type,
                response_id=stream_chunk.response_id,
                output_index=stream_chunk.output_index,
                use_live=self._use_live,
            )
            self._stream_sessions[key] = session

        section_key = self._section_key_for_part(stream_chunk.part_kind)
        session.append_text(
            section_key, stream_chunk.text_delta or stream_chunk.arguments_delta
        )

        if stream_chunk.is_final:
            if persist_on_finish:
                self._finish_session_by_key(key, persist=True)
            else:
                if not self._use_live:
                    self._finish_session_by_key(key, persist=False)
                elif stream_chunk.response_id is None:
                    self._finish_session_by_key(key, persist=False)

    def _session_type_for_part(self, part_kind: StreamPartKind) -> str | None:
        if part_kind in {"assistant_message", "reasoning_summary", "refusal"}:
            return "message"
        if part_kind in {"function_call_arguments", "tool_call_output"}:
            return "action"
        return None

    def _section_key_for_part(self, part_kind: StreamPartKind) -> str:
        if part_kind == "assistant_message":
            return "assistant"
        if part_kind == "reasoning_summary":
            return "reasoning"
        if part_kind == "function_call_arguments":
            return "function_arguments"
        if part_kind == "tool_call_output":
            return "tool_output"
        if part_kind == "refusal":
            return "refusal"
        return "assistant"

    def _make_stream_session_key(
        self, chunk: "LLMStreamChunk", session_type: str
    ) -> tuple[str, int, str]:
        response_key = (
            chunk.response_id
            or f"unknown::{chunk.item_id or chunk.output_index or chunk.type}"
        )
        output_index = chunk.output_index if chunk.output_index is not None else 0
        return (response_key, output_index, session_type)

    def _finish_stream_sessions(
        self, response_id: str | None, *, persist: bool
    ) -> None:
        if not self._stream_sessions:
            return
        if response_id is None:
            keys = list(self._stream_sessions.keys())
        else:
            keys = [
                key
                for key, session in self._stream_sessions.items()
                if session.response_id == response_id
            ]
            if not keys:
                keys = list(self._stream_sessions.keys())
        for key in keys:
            self._finish_session_by_key(key, persist=persist)

    def _finish_session_by_key(
        self, key: tuple[str, int, str], *, persist: bool
    ) -> None:
        session = self._stream_sessions.pop(key, None)
        if session is not None:
            session.finish(persist=persist)


class StreamingConversationVisualizer(ConversationVisualizer):
    """Streaming-focused visualizer that renders deltas in-place."""

    def __init__(
        self,
        highlight_regex: dict[str, str] | None = None,
        skip_user_messages: bool = False,
        conversation_stats: "ConversationStats | None" = None,
    ) -> None:
        super().__init__(
            highlight_regex=highlight_regex,
            skip_user_messages=skip_user_messages,
            conversation_stats=conversation_stats,
        )

    def on_event(self, event: Event) -> None:
        if isinstance(event, StreamingDeltaEvent):
            self._handle_stream_chunk(event.stream_chunk, persist_on_finish=True)
            return

        if self._should_skip_event(event):
            return

        super().on_event(event)

    def _should_skip_event(self, event: Event) -> bool:
        if isinstance(event, MessageEvent) and event.source == "agent":
            return True
        if isinstance(event, ActionEvent) and event.source == "agent":
            return True
        return False

    def _create_event_panel(self, event: Event) -> Panel | None:
        """Create a Rich Panel for the event with appropriate styling."""
        # Use the event's visualize property for content
        content = event.visualize

        if not content.plain.strip():
            return None

        # Apply highlighting if configured
        if self._highlight_patterns:
            content = self._apply_highlighting(content)

        # Determine panel styling based on event type
        if isinstance(event, SystemPromptEvent):
            return Panel(
                content,
                title=f"[bold {_SYSTEM_COLOR}]System Prompt[/bold {_SYSTEM_COLOR}]",
                border_style=_SYSTEM_COLOR,
                padding=_PANEL_PADDING,
                expand=True,
            )
        elif isinstance(event, ActionEvent):
            # Check if action is None (non-executable)
            if event.action is None:
                title = (
                    f"[bold {_ACTION_COLOR}]Agent Action (Not Executed)"
                    f"[/bold {_ACTION_COLOR}]"
                )
            else:
                title = f"[bold {_ACTION_COLOR}]Agent Action[/bold {_ACTION_COLOR}]"
            return Panel(
                content,
                title=title,
                subtitle=self._format_metrics_subtitle(),
                border_style=_ACTION_COLOR,
                padding=_PANEL_PADDING,
                expand=True,
            )
        elif isinstance(event, ObservationEvent):
            return Panel(
                content,
                title=f"[bold {_OBSERVATION_COLOR}]Observation"
                f"[/bold {_OBSERVATION_COLOR}]",
                border_style=_OBSERVATION_COLOR,
                padding=_PANEL_PADDING,
                expand=True,
            )
        elif isinstance(event, UserRejectObservation):
            return Panel(
                content,
                title=f"[bold {_ERROR_COLOR}]User Rejected Action"
                f"[/bold {_ERROR_COLOR}]",
                border_style=_ERROR_COLOR,
                padding=_PANEL_PADDING,
                expand=True,
            )
        elif isinstance(event, MessageEvent):
            if (
                self._skip_user_messages
                and event.llm_message
                and event.llm_message.role == "user"
            ):
                return
            assert event.llm_message is not None
            # Role-based styling
            role_colors = {
                "user": _MESSAGE_USER_COLOR,
                "assistant": _MESSAGE_ASSISTANT_COLOR,
            }
            role_color = role_colors.get(event.llm_message.role, "white")

            title_text = (
                f"[bold {role_color}]Message from {event.source.capitalize()}"
                f"[/bold {role_color}]"
            )
            return Panel(
                content,
                title=title_text,
                subtitle=self._format_metrics_subtitle(),
                border_style=role_color,
                padding=_PANEL_PADDING,
                expand=True,
            )
        elif isinstance(event, AgentErrorEvent):
            return Panel(
                content,
                title=f"[bold {_ERROR_COLOR}]Agent Error[/bold {_ERROR_COLOR}]",
                subtitle=self._format_metrics_subtitle(),
                border_style=_ERROR_COLOR,
                padding=_PANEL_PADDING,
                expand=True,
            )
        elif isinstance(event, PauseEvent):
            return Panel(
                content,
                title=f"[bold {_PAUSE_COLOR}]User Paused[/bold {_PAUSE_COLOR}]",
                border_style=_PAUSE_COLOR,
                padding=_PANEL_PADDING,
                expand=True,
            )
        elif isinstance(event, Condensation):
            return Panel(
                content,
                title=f"[bold {_SYSTEM_COLOR}]Condensation[/bold {_SYSTEM_COLOR}]",
                subtitle=self._format_metrics_subtitle(),
                border_style=_SYSTEM_COLOR,
                expand=True,
            )
        else:
            # Fallback panel for unknown event types
            return Panel(
                content,
                title=f"[bold {_ERROR_COLOR}]UNKNOWN Event: {event.__class__.__name__}"
                f"[/bold {_ERROR_COLOR}]",
                subtitle=f"({event.source})",
                border_style=_ERROR_COLOR,
                padding=_PANEL_PADDING,
                expand=True,
            )

    def _format_metrics_subtitle(self) -> str | None:
        """Format LLM metrics as a visually appealing subtitle string with icons,
        colors, and k/m abbreviations using conversation stats."""
        if not self._conversation_stats:
            return None

        combined_metrics = self._conversation_stats.get_combined_metrics()
        if not combined_metrics or not combined_metrics.accumulated_token_usage:
            return None

        usage = combined_metrics.accumulated_token_usage
        cost = combined_metrics.accumulated_cost or 0.0

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

        return "Tokens: " + " • ".join(parts)


def create_default_visualizer(
    highlight_regex: dict[str, str] | None = None,
    conversation_stats: "ConversationStats | None" = None,
    **kwargs,
) -> ConversationVisualizer:
    """Create a default conversation visualizer instance.

    Args:
        highlight_regex: Dictionary mapping regex patterns to Rich color styles
                       for highlighting keywords in the visualizer.
                       For example: {"Reasoning:": "bold blue",
                       "Thought:": "bold green"}
        conversation_stats: ConversationStats object to display metrics information.
    """
    return ConversationVisualizer(
        highlight_regex=DEFAULT_HIGHLIGHT_REGEX
        if highlight_regex is None
        else highlight_regex,
        conversation_stats=conversation_stats,
        **kwargs,
    )


def create_streaming_visualizer(
    highlight_regex: dict[str, str] | None = None,
    conversation_stats: "ConversationStats | None" = None,
    **kwargs,
) -> StreamingConversationVisualizer:
    """Create a streaming-aware visualizer instance."""

    return StreamingConversationVisualizer(
        highlight_regex=DEFAULT_HIGHLIGHT_REGEX
        if highlight_regex is None
        else highlight_regex,
        conversation_stats=conversation_stats,
        **kwargs,
    )
