"""
Base classes for agent-sdk integration tests.
"""

import os
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    Event,
    Message,
    TextContent,
)
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
        cwd: str | None = None,
    ):
        self.instruction = instruction
        self.llm_config = llm_config
        self.cwd = cwd
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

        self.llm = LLM(**llm_kwargs)
        self.agent = Agent(llm=self.llm, tools=self.tools)
        self.collected_events: list[Event] = []
        self.llm_messages: list[dict[str, Any]] = []
        self.conversation: Conversation = Conversation(
            agent=self.agent, callbacks=[self.conversation_callback]
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

            self.conversation.send_message(
                message=Message(
                    role="user", content=[TextContent(text=self.instruction)]
                )
            )
            self.conversation.run()

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

    @abstractmethod
    def teardown(self):
        """Clean up test resources."""
        pass
