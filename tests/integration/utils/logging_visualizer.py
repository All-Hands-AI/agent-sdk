"""
Logging visualizer for integration tests that captures visualizer output to files.
"""

import os
from io import StringIO
from typing import TYPE_CHECKING

from rich.console import Console

from openhands.sdk.conversation.visualizer import ConversationVisualizer
from openhands.sdk.event.base import Event


if TYPE_CHECKING:
    from openhands.sdk.conversation.conversation_stats import ConversationStats


class LoggingVisualizer(ConversationVisualizer):
    """A visualizer that captures output to both console and log file."""

    def __init__(
        self,
        log_file_path: str,
        highlight_regex: dict[str, str] | None = None,
        skip_user_messages: bool = False,
        conversation_stats: "ConversationStats | None" = None,
        enable_console_output: bool = True,
    ):
        """Initialize the logging visualizer.

        Args:
            log_file_path: Path to the log file where output will be written
            highlight_regex: Dictionary mapping regex patterns to Rich color styles
            skip_user_messages: If True, skip displaying user messages
            conversation_stats: ConversationStats object to display metrics information
            enable_console_output: If True, also output to console (default behavior)
        """
        super().__init__(highlight_regex, skip_user_messages, conversation_stats)
        self.log_file_path = log_file_path
        self.enable_console_output = enable_console_output

        # Create log directory if it doesn't exist
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

        # Initialize log file
        with open(log_file_path, "w") as f:
            f.write("# Agent/LLM Integration Test Logs\n")
            f.write(
                "# This file contains the detailed agent reasoning and tool "
                "interactions\n\n"
            )

    def on_event(self, event: Event) -> None:
        """Handle event by writing to both console and log file."""
        panel = self._create_event_panel(event)
        if panel:
            # Write to console if enabled
            if self.enable_console_output:
                self._console.print(panel)
                self._console.print()  # Add spacing between events

            # Capture the panel output as plain text for the log file
            string_buffer = StringIO()
            log_console = Console(file=string_buffer, width=120, legacy_windows=False)
            log_console.print(panel)
            log_console.print()

            # Get the captured output
            log_output = string_buffer.getvalue()

            # Write to log file
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(log_output)
