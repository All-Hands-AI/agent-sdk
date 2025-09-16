"""Test that an agent can browse a GitHub PR and extract information."""

from openhands.sdk import get_logger
from openhands.sdk.tool import Tool
from openhands.tools import BashTool, FileEditorTool
from tests.integration.base import BaseIntegrationTest, TestResult


INSTRUCTION = (
    "Look at https://github.com/All-Hands-AI/OpenHands/pull/8, and tell me "
    "what is happening there and what did @asadm suggest."
)


logger = get_logger(__name__)


class GitHubPRBrowsingTest(BaseIntegrationTest):
    """Test that an agent can browse a GitHub PR and extract information."""

    INSTRUCTION = INSTRUCTION

    @property
    def tools(self) -> list[Tool]:
        """List of tools available to the agent."""
        if self.cwd is None:
            raise ValueError("CWD must be set before accessing tools")
        return [
            BashTool.create(working_dir=self.cwd),
            FileEditorTool.create(workspace_root=self.cwd),
        ]

    def setup(self) -> None:
        """No special setup needed for GitHub PR browsing."""
        if self.cwd is None:
            raise ValueError("CWD must be set before setup")

        logger.info("GitHub PR browsing test setup complete")

    def verify_result(self) -> TestResult:
        """Verify that the agent successfully browsed the GitHub PR."""
        # Get the agent's final answer/response to the instruction
        agent_final_answer = self._get_agent_final_response()

        if not agent_final_answer:
            return TestResult(
                success=False,
                reason=(
                    "No final answer found from agent. "
                    f"Events: {len(list(self.conversation.state.events))}, "
                    f"LLM messages: {len(self.llm_messages)}"
                ),
            )

        # Convert to lowercase for case-insensitive matching
        answer_text = agent_final_answer.lower()

        github_indicators = ["mit", "apache", "license"]

        if any(indicator in answer_text for indicator in github_indicators):
            return TestResult(
                success=True,
                reason="Agent's final answer contains information about the PR content",
            )
        else:
            return TestResult(
                success=False,
                reason=(
                    "Agent's final answer does not contain the expected information "
                    "about the PR content. "
                    f"Final answer preview: {agent_final_answer[:200]}..."
                ),
            )

    def _get_agent_final_response(self) -> str:
        """Extract the agent's final response from the conversation."""
        from openhands.sdk.event.llm_convertible import MessageEvent
        from openhands.sdk.llm import content_to_str

        # Method 1: Get the last MessageEvent from agent
        agent_messages = []
        for event in self.conversation.state.events:
            if isinstance(event, MessageEvent) and event.source == "agent":
                agent_messages.append(event)

        if agent_messages:
            last_agent_message = agent_messages[-1]
            # Use the utility function to extract text content
            text_parts = content_to_str(last_agent_message.llm_message.content)
            if text_parts:
                return " ".join(text_parts)

        # Method 2: Get from llm_messages (last assistant message)
        for msg in reversed(self.llm_messages):
            if msg.get("role") == "assistant":
                content = msg.get("content", [])
                if isinstance(content, list):
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            text_parts.append(item["text"])
                    if text_parts:
                        return " ".join(text_parts)
                elif isinstance(content, str):
                    return content

        return ""

    def teardown(self):
        """No cleanup needed for GitHub PR browsing."""
        logger.info("GitHub PR browsing test teardown complete")
