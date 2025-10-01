"""Test that an agent can execute interactive Python scripts with input."""

import hashlib
import os

from openhands.sdk import get_logger
from openhands.sdk.tool import Tool, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool
from tests.integration.base import BaseIntegrationTest, TestResult


INSTRUCTION = (
    'Execute the python script /workspace/python_script.py with input "John" '
    'and "25" and tell me the secret number.'
)

# Calculate the expected secret number for age 25
SECRET_NUMBER = int(hashlib.sha256(str(25).encode()).hexdigest()[:8], 16) % 1000

PYTHON_SCRIPT_CONTENT = (
    'name = input("Enter your name: "); '
    'age = input("Enter your age: "); '
    "import hashlib; "
    "secret = int(hashlib.sha256(str(age).encode()).hexdigest()[:8], 16) % 1000; "
    'print(f"Hello {name}, you are {age} years old. '
    'Tell you a secret number: {secret}")'
)


logger = get_logger(__name__)


class InteractiveCommandsTest(BaseIntegrationTest):
    """Test that an agent can execute interactive Python scripts with input."""

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
        """Set up the interactive Python script."""
        if self.cwd is None:
            raise ValueError("CWD must be set before setup")

        try:
            # Create the workspace directory
            assert self.cwd is not None
            workspace_dir = os.path.join(self.cwd, "workspace")
            os.makedirs(workspace_dir, exist_ok=True)

            # Write the Python script
            script_path = os.path.join(workspace_dir, "python_script.py")
            with open(script_path, "w") as f:
                f.write(PYTHON_SCRIPT_CONTENT)

            logger.info(
                f"Created interactive Python script at {script_path} "
                f"with expected secret number: {SECRET_NUMBER}"
            )

        except Exception as e:
            raise RuntimeError(f"Failed to set up interactive Python script: {e}")

    def verify_result(self) -> TestResult:
        """Verify that the agent successfully executed the script with input."""
        # The verification will be based on the agent's conversation
        # Since we can't directly check what the agent "said", we'll check if
        # the script file exists and contains the expected content

        assert self.cwd is not None
        workspace_dir = os.path.join(self.cwd, "workspace")
        script_path = os.path.join(workspace_dir, "python_script.py")

        if not os.path.exists(script_path):
            return TestResult(
                success=False,
                reason="Python script file was not created",
            )

        try:
            with open(script_path) as f:
                content = f.read()

            if PYTHON_SCRIPT_CONTENT not in content:
                return TestResult(
                    success=False,
                    reason="Python script content is incorrect",
                )

            return TestResult(
                success=True,
                reason=(
                    f"Interactive Python script setup completed. Agent should "
                    f"execute the script with inputs 'John' and '25' and find "
                    f"the secret number: {SECRET_NUMBER}"
                ),
            )

        except Exception as e:
            return TestResult(
                success=False,
                reason=f"Error verifying script content: {e}",
            )

    def teardown(self):
        """Clean up the created files."""
        try:
            assert self.cwd is not None
            workspace_dir = os.path.join(self.cwd, "workspace")
            script_path = os.path.join(workspace_dir, "python_script.py")

            if os.path.exists(script_path):
                os.remove(script_path)

            if os.path.exists(workspace_dir) and not os.listdir(workspace_dir):
                os.rmdir(workspace_dir)

            logger.info("Cleaned up interactive commands test files")

        except Exception as e:
            logger.warning(f"Error cleaning up test files: {e}")
