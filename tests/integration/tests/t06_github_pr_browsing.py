"""Test that an agent can browse a GitHub PR and extract information."""

import os

from openhands.sdk import get_logger
from openhands.sdk.tool import Tool
from openhands.tools import BashTool, FileEditorTool
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
        return [
            BashTool.create(working_dir=self.cwd),
            FileEditorTool.create(workspace_root=self.cwd),
        ]

    def setup(self) -> None:
        """No special setup needed for GitHub PR browsing."""
        if self.cwd is None:
            raise ValueError("CWD must be set before setup")

        # Debug environment variables for CI
        print("=== GITHUB PR BROWSING TEST SETUP ===", flush=True)
        github_token = os.environ.get("GITHUB_TOKEN")
        print(f"GITHUB_TOKEN present: {bool(github_token)}", flush=True)
        if github_token:
            print(f"GITHUB_TOKEN format: {github_token[:8]}...", flush=True)
        else:
            print("No GITHUB_TOKEN found in environment", flush=True)

        print(f"Working directory: {self.cwd}", flush=True)
        logger.info("GitHub PR browsing test setup complete")

    def verify_result(self) -> TestResult:
        """Verify that the agent successfully browsed the GitHub PR."""
        print("=== VERIFYING GITHUB PR BROWSING RESULT ===", flush=True)

        # Get the agent's final answer/response to the instruction
        agent_final_answer = self.get_agent_final_response()

        print(f"Agent final answer received: {bool(agent_final_answer)}", flush=True)
        if agent_final_answer:
            print(f"Answer length: {len(agent_final_answer)} characters", flush=True)

        if not agent_final_answer:
            print("ERROR: No final answer found from agent", flush=True)
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

        print(f"Checking for indicators: {github_indicators}", flush=True)
        found_indicators = [
            indicator for indicator in github_indicators if indicator in answer_text
        ]
        print(f"Found indicators: {found_indicators}", flush=True)

        if any(indicator in answer_text for indicator in github_indicators):
            print(
                "SUCCESS: Agent's final answer contains expected PR content", flush=True
            )
            return TestResult(
                success=True,
                reason="Agent's final answer contains information about the PR content",
            )
        else:
            print(
                "FAILURE: Agent's final answer does not contain expected PR content",
                flush=True,
            )
            print(f"Full answer text: {agent_final_answer}", flush=True)
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
