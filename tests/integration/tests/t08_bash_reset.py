"""Test that an agent can use bash terminal reset functionality when needed."""

import os

from openhands.sdk import get_logger
from openhands.sdk.tool import ToolSpec, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool
from tests.integration.base import BaseIntegrationTest, TestResult


INSTRUCTION = (
    "I need you to help me test the bash terminal reset functionality. "
    "Please follow these steps:\n"
    "1. Set an environment variable TEST_RESET_VAR to 'before_reset'\n"
    "2. Verify the variable is set by echoing it\n"
    "3. Use the reset functionality (set reset=True in your bash command) "
    "to reset the terminal session\n"
    "4. After reset, verify that the TEST_RESET_VAR is no longer set "
    "(should be empty when echoed)\n"
    "5. Set a new environment variable POST_RESET_VAR to 'after_reset' "
    "to confirm the terminal is working\n"
    "Please tell me the results of each step."
)


logger = get_logger(__name__)


class BashResetTest(BaseIntegrationTest):
    """Test that an agent can use bash terminal reset functionality."""

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
        """Create workspace directory for the test."""
        if self.cwd is None:
            raise ValueError("CWD must be set before setup")

        # Create workspace directory
        workspace_dir = os.path.join(self.cwd, "workspace")
        os.makedirs(workspace_dir, exist_ok=True)

        logger.info(f"Created workspace directory at: {workspace_dir}")

    def verify_result(self) -> TestResult:
        """Verify that the agent successfully used the reset functionality."""
        if self.cwd is None:
            return TestResult(success=False, reason="CWD not set")

        # Check the conversation events to see if reset was used
        reset_used = False
        pre_reset_var_set = False
        post_reset_var_set = False

        # Look through the conversation events for bash commands
        for event in self.conversation.state.events:
            # Check for ActionEvent with BashTool
            if (
                type(event).__name__ == "ActionEvent"
                and hasattr(event, "tool_name")
                and getattr(event, "tool_name") == "BashTool"
            ):
                action = getattr(event, "action", None)
                if action:
                    # Check if reset was used
                    if hasattr(action, "reset") and getattr(action, "reset"):
                        reset_used = True
                        logger.info("Found reset=True in bash action")

                    # Check commands for environment variable operations
                    command = getattr(action, "command", "")
                    if "export TEST_RESET_VAR=before_reset" in command:
                        pre_reset_var_set = True
                    elif "export POST_RESET_VAR=after_reset" in command:
                        post_reset_var_set = True

        # Check if the agent mentioned reset in their final response
        final_response = self.get_agent_final_response()
        reset_mentioned = "reset" in final_response.lower()

        # Verify all expected behaviors occurred
        if not reset_used:
            return TestResult(
                success=False,
                reason=(
                    "Agent did not use the reset functionality "
                    "(reset=True not found in bash actions)"
                ),
            )

        if not pre_reset_var_set:
            return TestResult(
                success=False,
                reason=(
                    "Agent did not set the initial TEST_RESET_VAR environment variable"
                ),
            )

        if not post_reset_var_set:
            return TestResult(
                success=False,
                reason="Agent did not set POST_RESET_VAR after reset",
            )

        if not reset_mentioned:
            return TestResult(
                success=False,
                reason=(
                    "Agent did not mention the reset functionality in their response"
                ),
            )

        # Additional verification: check if reset message appeared in outputs
        reset_message_found = False
        for event in self.conversation.state.events:
            if (
                type(event).__name__ == "ObservationEvent"
                and hasattr(event, "tool_name")
                and getattr(event, "tool_name") == "BashTool"
            ):
                observation = getattr(event, "observation", None)
                if observation and hasattr(observation, "output"):
                    output = getattr(observation, "output")
                    if "Terminal session has been reset" in output:
                        reset_message_found = True
                        break

        if not reset_message_found:
            return TestResult(
                success=False,
                reason="Reset confirmation message not found in bash outputs",
            )

        return TestResult(
            success=True,
            reason=(
                "Agent successfully used bash reset functionality: "
                f"reset_used={reset_used}, pre_reset_var_set={pre_reset_var_set}, "
                f"post_reset_var_set={post_reset_var_set}, "
                f"reset_mentioned={reset_mentioned}, "
                f"reset_message_found={reset_message_found}"
            ),
        )

    def teardown(self):
        """Clean up test resources."""
        # Note: In this implementation, cwd is managed externally
        # so we don't need to clean it up here
        pass
