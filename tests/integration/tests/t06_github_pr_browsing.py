"""Test that an agent can browse a GitHub PR and extract information."""

from openhands.sdk import get_logger
from openhands.sdk.tool import Tool, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool
from tests.integration.base import BaseIntegrationTest, TestResult


INSTRUCTION = (
    "Look at https://github.com/All-Hands-AI/OpenHands/pull/8, and tell me "
    "what is happening there and what did @asadm suggest. "
    "Note: If you encounter rate limiting issues, use the GITHUB_TOKEN "
    "environment variable if available."
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
        register_tool("BashTool", BashTool)
        register_tool("FileEditorTool", FileEditorTool)
        return [
            Tool(name="BashTool", params={"working_dir": self.cwd}),
            Tool(name="FileEditorTool", params={"workspace_root": self.cwd}),
        ]

    def setup(self) -> None:
        """No special setup needed for GitHub PR browsing."""
        if self.cwd is None:
            raise ValueError("CWD must be set before setup")

    def verify_result(self) -> TestResult:
        """Verify that the agent successfully browsed the GitHub PR."""

        # Get the agent's final answer/response to the instruction
        agent_final_answer = self.get_agent_final_response()

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

    def teardown(self):
        """No cleanup needed for GitHub PR browsing."""
        logger.info("GitHub PR browsing test teardown complete")
