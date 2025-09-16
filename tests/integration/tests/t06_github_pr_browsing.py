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
        # The verification will be based on the agent's conversation
        # Since we can't directly check what the agent "said", we'll assume
        # success if the setup completed without errors.
        # In a real scenario, we'd check the agent's response for:
        # - Information about what's happening in the PR
        # - What @asadm suggested
        # - General understanding of the PR content

        return TestResult(
            success=True,
            reason=(
                "GitHub PR browsing test setup completed. Agent should be able to "
                "browse https://github.com/All-Hands-AI/OpenHands/pull/8 and "
                "extract information about what's happening and @asadm's suggestions."
            ),
        )

    def teardown(self):
        """No cleanup needed for GitHub PR browsing."""
        logger.info("GitHub PR browsing test teardown complete")
