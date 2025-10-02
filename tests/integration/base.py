"""
Base classes for agent-sdk integration tests.
"""

import os
import sys
from abc import ABC, abstractmethod
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from typing import Any

from pydantic import BaseModel, SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Message,
    TextContent,
)
from openhands.sdk.conversation.impl.local_conversation import LocalConversation
from openhands.sdk.event.base import Event
from openhands.sdk.event.llm_convertible import (
    MessageEvent,
)
from openhands.sdk.tool import Tool


class TestResult(BaseModel):
    """Result of an integration test."""

    success: bool
    reason: str | None = None


class BaseIntegrationTest(ABC):
    """
    Base class for agent-sdk integration tests.

    This class provides a structured approach to writing integration tests
    that use real LLM calls. It handles common setup like LLM configuration,
    temporary directory management, and agent creation.

    Unlike the OpenHands approach which uses a Runtime, this uses tools
    directly with temporary directories for isolation.
    """

    INSTRUCTION: str

    def __init__(
        self,
        instruction: str,
        llm_config: dict[str, Any],
        instance_id: str,
        cwd: str | None = None,
    ):
        self.instruction = instruction
        self.llm_config = llm_config
        self.cwd = cwd
        self.instance_id = instance_id
        api_key = os.getenv("LLM_API_KEY")
        if not api_key:
            raise ValueError(
                "LLM_API_KEY environment variable not set. Skipping real LLM test."
            )
        base_url = os.getenv("LLM_BASE_URL")
        if not base_url:
            raise ValueError(
                "LLM_BASE_URL environment variable not set. Skipping real LLM test."
            )

        # Create LLM with all config parameters
        llm_kwargs = {
            **self.llm_config,  # Pass through all config parameters
            "base_url": base_url,
            "api_key": SecretStr(api_key),
        }

        self.llm = LLM(**llm_kwargs, service_id="test-llm")
        self.agent = Agent(llm=self.llm, tools=self.tools)
        self.collected_events: list[Event] = []
        self.llm_messages: list[dict[str, Any]] = []

        # Create log file path for this test instance
        self.log_file_path = os.path.join(
            self.cwd or "/tmp", f"{self.instance_id}_agent_logs.txt"
        )

        self.conversation: LocalConversation = LocalConversation(
            agent=self.agent,
            workspace=self.cwd or "/tmp",
            callbacks=[self.conversation_callback],
            visualize=True,  # Use default visualizer and capture its output
        )

    def conversation_callback(self, event: Event):
        """Callback to collect conversation events."""
        self.collected_events.append(event)
        if isinstance(event, MessageEvent):
            self.llm_messages.append(event.llm_message.model_dump())

    def run_instruction(self) -> TestResult:
        """
        Run user instruction through the agent and verify results.

        Returns:
            TestResult: The result of the test
        """
        try:
            # Setup
            self.setup()

            # Initialize log file with header
            with open(self.log_file_path, "w") as f:
                f.write(f"Agent Logs for Test: {self.instance_id}\n")
                f.write("=" * 50 + "\n\n")

            # Capture stdout and stderr during conversation
            stdout_buffer = StringIO()
            stderr_buffer = StringIO()

            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                self.conversation.send_message(
                    message=Message(
                        role="user", content=[TextContent(text=self.instruction)]
                    )
                )
                self.conversation.run()

            # Save captured output to log file
            captured_output = stdout_buffer.getvalue()
            captured_errors = stderr_buffer.getvalue()

            with open(self.log_file_path, "a") as f:
                if captured_output:
                    f.write("STDOUT:\n")
                    f.write(captured_output)
                    f.write("\n")
                if captured_errors:
                    f.write("STDERR:\n")
                    f.write(captured_errors)
                    f.write("\n")

            # Also print to console for debugging
            if captured_output:
                print(captured_output, end="")
            if captured_errors:
                print(captured_errors, file=sys.stderr, end="")

            # Verify results
            result = self.verify_result()

            return result

        except Exception as e:
            return TestResult(success=False, reason=f"Test execution failed: {str(e)}")

        finally:
            self.teardown()

    @property
    @abstractmethod
    def tools(self) -> list[Tool]:
        """List of tools available to the agent."""
        pass

    @abstractmethod
    def setup(self) -> None:
        """
        Initialize test-specific setup.

        This method should create any files, directories, or other
        resources needed for the test.
        """
        pass

    @abstractmethod
    def verify_result(self) -> TestResult:
        """
        Verify the result of the test.

        This method should check if the agent successfully completed
        the task by examining files in self.temp_dir, checking the
        events in self.events, or other verification methods.

        Returns:
            TestResult: The result of the verification
        """
        pass

    def get_agent_final_response(self) -> str:
        """Extract the final response from the agent's finish tool call."""

        # Find the last finish action from the agent
        for event in reversed(self.conversation.state.events):
            if (
                type(event).__name__ == "ActionEvent"
                and hasattr(event, "source")
                and getattr(event, "source") == "agent"
                and hasattr(event, "tool_name")
                and getattr(event, "tool_name") == "finish"
            ):
                # Extract message from finish tool call
                if hasattr(event, "action") and hasattr(
                    getattr(event, "action"), "message"
                ):
                    message = getattr(getattr(event, "action"), "message")
                    return message
                else:
                    break
        return ""

    @abstractmethod
    def teardown(self):
        """Clean up test resources."""
        pass
