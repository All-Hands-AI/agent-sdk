"""Test that an agent can use Jupyter IPython to write a text file."""

import os

from openhands.sdk import get_logger
from openhands.sdk.tool import Tool, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.file_editor import FileEditorTool
from tests.integration.base import BaseIntegrationTest, TestResult


INSTRUCTION = (
    "Use Jupyter IPython to write a text file containing 'hello world' "
    "to '/workspace/test.txt'."
)


logger = get_logger(__name__)


class JupyterWriteFileTest(BaseIntegrationTest):
    """Test that an agent can use Jupyter IPython to write a text file."""

    INSTRUCTION = INSTRUCTION

    @property
    def tools(self) -> list[Tool]:
        """List of tools available to the agent."""
        if self.cwd is None:
            raise ValueError("CWD must be set before accessing tools")
        register_tool("BashTool", BashTool)
        register_tool("FileEditorTool", FileEditorTool)
        return [
            Tool(name="BashTool"),
            Tool(name="FileEditorTool"),
        ]

    def setup(self) -> None:
        """Create workspace directory for the test."""
        if self.cwd is None:
            raise ValueError("CWD must be set before setup")

        # Create workspace directory
        workspace_dir = os.path.join(self.cwd, "workspace")
        os.makedirs(workspace_dir, exist_ok=True)

        logger.info(f"Created workspace directory at: {workspace_dir}")

    def verify_result(self) -> TestResult:
        """Verify that the agent successfully created the text file using IPython."""
        if self.cwd is None:
            return TestResult(success=False, reason="CWD not set")

        file_path = os.path.join(self.cwd, "workspace", "test.txt")

        if not os.path.exists(file_path):
            return TestResult(
                success=False, reason="Text file '/workspace/test.txt' not found"
            )

        # Read the file content
        with open(file_path) as f:
            file_content = f.read().strip()

        # Check if the file contains the expected content
        if "hello world" not in file_content.lower():
            return TestResult(
                success=False,
                reason=f"File does not contain 'hello world': {file_content}",
            )

        return TestResult(
            success=True,
            reason=f"Successfully created file with content: {file_content}",
        )

    def teardown(self):
        """Clean up test resources."""
        # Note: In this implementation, cwd is managed externally
        # so we don't need to clean it up here
        pass
