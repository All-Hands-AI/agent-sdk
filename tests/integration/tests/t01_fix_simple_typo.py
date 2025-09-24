"""Test that an agent can fix typos in a text file using BaseIntegrationTest."""

import os

from openhands.sdk import get_logger
from openhands.sdk.tool import ToolSpec, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool
from tests.integration.base import BaseIntegrationTest, TestResult


INSTRUCTION = (
    "Please fix all the typos in the file 'document.txt' that is in "
    "the current directory. "
    "Read the file first, identify the typos, and correct them. "
)

TYPO_CONTENT = """
This is a sample documnet with three typos that need to be fixed.
The purpse of this document is to test the agent's ability to correct spelling mistakes.
Please fix all the mispelled words in this document.
"""


logger = get_logger(__name__)


class TypoFixTest(BaseIntegrationTest):
    """Test that an agent can fix typos in a text file."""

    INSTRUCTION = INSTRUCTION

    @property
    def tools(self) -> list[ToolSpec]:
        """List of tools available to the agent."""
        if self.cwd is None:
            raise ValueError("CWD must be set before accessing tools")
        register_tool("BashTool", BashTool)
        register_tool("FileEditorTool", FileEditorTool)
        return [
            ToolSpec(name="BashTool", params={"working_dir": self.cwd}),
            ToolSpec(name="FileEditorTool", params={"workspace_root": self.cwd}),
        ]

    def setup(self) -> None:
        """Create a text file with typos for the agent to fix."""
        if self.cwd is None:
            raise ValueError("CWD must be set before setup")

        # Create the test file with typos
        typo_content = TYPO_CONTENT
        document_path = os.path.join(self.cwd, "document.txt")
        with open(document_path, "w") as f:
            f.write(typo_content)

        logger.info(f"Created test document with typos at: {document_path}")

    def verify_result(self) -> TestResult:
        """Verify that the agent successfully fixed the typos."""
        if self.cwd is None:
            return TestResult(success=False, reason="CWD not set")
        document_path = os.path.join(self.cwd, "document.txt")

        if not os.path.exists(document_path):
            return TestResult(
                success=False, reason="Document file not found after agent execution"
            )
        with open(document_path) as f:
            corrected_content = f.read()

        are_typos_fixed: bool = (
            "document" in corrected_content
            and "purpose" in corrected_content
            and "misspelled" in corrected_content
        )
        if are_typos_fixed:
            return TestResult(success=True, reason="Successfully fixed all typos")
        else:
            return TestResult(
                success=False,
                reason=f"Typos were not fully corrected:\n{corrected_content}",
            )

    def teardown(self):
        """Clean up the temporary directory."""
        # Note: In this implementation, cwd is managed externally
        # so we don't need to clean it up here
        pass
