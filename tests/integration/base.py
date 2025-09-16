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
from openhands.sdk.llm import content_to_str
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

    def get_agent_final_response(self) -> str:
        """Extract the agent's final response from the conversation."""

        print("=== EXTRACTING AGENT FINAL RESPONSE ===", flush=True)
        print(
            f"Total events in conversation: {len(self.conversation.state.events)}",
            flush=True,
        )

        # Get the last MessageEvent from agent
        agent_messages = []
        for event in self.conversation.state.events:
            if isinstance(event, MessageEvent) and event.source == "agent":
                agent_messages.append(event)

        print(f"Found {len(agent_messages)} agent messages", flush=True)

        if agent_messages:
            last_agent_message = agent_messages[-1]
            msg_type = type(last_agent_message.llm_message.content)
            print(f"Last agent message type: {msg_type}", flush=True)

            # Use the utility function to extract text content
            text_parts = content_to_str(last_agent_message.llm_message.content)
            print(
                f"Extracted text parts: {len(text_parts) if text_parts else 0}",
                flush=True,
            )

            if text_parts:
                result = " ".join(text_parts)
                print(f"Final response length: {len(result)} characters", flush=True)
                print(f"Final response preview: {result[:200]}...", flush=True)
                return result
            else:
                print("No text parts extracted from agent message", flush=True)
        else:
            print("No agent messages found in conversation", flush=True)

        print("Returning empty string as final response", flush=True)
        return ""

    @abstractmethod
    def teardown(self):
        """Clean up test resources."""
        pass
