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
        # Check if the agent made any attempts to browse the GitHub PR
        # by examining the conversation events and LLM messages

        # Get all events from the conversation
        events = list(self.conversation.state.events)

        # Convert events to text for analysis
        event_texts = []
        for event in events:
            event_str = str(event)
            event_texts.append(event_str.lower())

        # Convert LLM messages to text for analysis
        llm_message_texts = []
        for msg in self.llm_messages:
            if isinstance(msg, dict) and "content" in msg:
                content = msg["content"]
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            llm_message_texts.append(item["text"].lower())
                elif isinstance(content, str):
                    llm_message_texts.append(content.lower())

        # Combine all text content for analysis
        all_text = " ".join(event_texts + llm_message_texts)

        # Check for evidence of GitHub PR browsing
        github_indicators = [
            "MIT",
            "Apache",
            "License",
        ]

        # Check for evidence of finding information about @asadm
        asadm_indicators = ["asadm", "@asadm", "suggested", "suggestion"]

        # Check if the agent attempted to browse the GitHub PR
        found_github_attempt = any(
            indicator in all_text for indicator in github_indicators
        )
        found_asadm_info = any(indicator in all_text for indicator in asadm_indicators)

        if not found_github_attempt:
            return TestResult(
                success=False,
                reason=(
                    "Agent did not appear to attempt browsing the GitHub PR. "
                    f"No GitHub-related content found in conversation. "
                    f"Events: {len(events)}, LLM messages: {len(self.llm_messages)}"
                ),
            )

        if found_github_attempt and found_asadm_info:
            return TestResult(
                success=True,
                reason=(
                    "Agent successfully browsed the GitHub PR and found information "
                    "about @asadm's suggestions. Found GitHub-related content and "
                    "asadm-related content in the conversation."
                ),
            )
        elif found_github_attempt:
            return TestResult(
                success=True,
                reason=(
                    "Agent successfully attempted to browse the GitHub PR, though "
                    "specific information about @asadm's suggestions may not be "
                    "clearly identifiable in the conversation text."
                ),
            )
        else:
            return TestResult(
                success=False,
                reason=(
                    "Agent did not successfully browse the GitHub PR or extract "
                    "the requested information about what's happening and "
                    "@asadm's suggestions."
                ),
            )

    def teardown(self):
        """No cleanup needed for GitHub PR browsing."""
        logger.info("GitHub PR browsing test teardown complete")
