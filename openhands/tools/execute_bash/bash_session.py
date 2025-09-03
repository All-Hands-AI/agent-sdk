import os
import re
import time
import uuid
from enum import Enum

import libtmux

from openhands.core.logger import get_logger

from .constants import (
    CMD_OUTPUT_PS1_END,
    HISTORY_LIMIT,
    NO_CHANGE_TIMEOUT_SECONDS,
    POLL_INTERVAL,
    TIMEOUT_MESSAGE_TEMPLATE,
)
from .definition import ExecuteBashAction, ExecuteBashObservation
from .metadata import CmdOutputMetadata
from .utils.command import escape_bash_special_chars, split_bash_commands


logger = get_logger(__name__)


class BashCommandStatus(Enum):
    CONTINUE = "continue"
    COMPLETED = "completed"
    NO_CHANGE_TIMEOUT = "no_change_timeout"
    HARD_TIMEOUT = "hard_timeout"


def _remove_command_prefix(command_output: str, command: str) -> str:
    return command_output.lstrip().removeprefix(command.lstrip()).lstrip()


class BashSession:
    PS1 = CmdOutputMetadata.to_ps1_prompt()

    def __init__(
        self,
        work_dir: str,
        username: str | None = None,
        max_memory_mb: int | None = None,
        no_change_timeout_seconds: int | None = None,
    ):
        self.work_dir = work_dir
        self.username = username
        self._initialized = False
        self.max_memory_mb = max_memory_mb
        self.no_change_timeout_seconds = (
            no_change_timeout_seconds or NO_CHANGE_TIMEOUT_SECONDS
        )
        self._closed = False

    def initialize(self) -> None:
        self.server = libtmux.Server()
        _shell_command = "/bin/bash"
        if self.username in ["root", "openhands"]:
            # This starts a non-login (new) shell for the given user
            _shell_command = f"su {self.username} -"

        window_command = _shell_command

        logger.debug(f"Initializing bash session with command: {window_command}")
        session_name = f"openhands-{self.username}-{uuid.uuid4()}"
        self.session = self.server.new_session(
            session_name=session_name,
            start_directory=self.work_dir,  # This parameter is supported by libtmux
            kill_session=True,
            x=1000,
            y=1000,
        )

        # Set history limit to a large number to avoid losing history
        # https://unix.stackexchange.com/questions/43414/unlimited-history-in-tmux
        self.session.set_option("history-limit", str(HISTORY_LIMIT))
        self.session.history_limit = str(HISTORY_LIMIT)
        # We need to create a new pane because the initial
        # pane's history limit is (default) 2000
        _initial_window = self.session.active_window
        self.window = self.session.new_window(
            window_name="bash",
            window_shell=window_command,
            start_directory=self.work_dir,  # This parameter is supported by libtmux
        )
        self.pane = self.window.active_pane
        assert isinstance(self.pane, libtmux.Pane)
        logger.debug(f"pane: {self.pane}; history_limit: {self.session.history_limit}")
        _initial_window.kill()

        # Configure bash to use simple PS1 and disable PS2
        self.pane.send_keys(
            f'export PROMPT_COMMAND=\'export PS1="{self.PS1}"\'; export PS2=""'
        )
        time.sleep(0.1)  # Wait for command to take effect

        # Store the last command for interactive input handling
        self.prev_status: BashCommandStatus | None = None
        self.prev_output: str = ""
        logger.debug(f"Bash session initialized with work dir: {self.work_dir}")

        # Maintain the current working directory
        self._cwd = os.path.abspath(self.work_dir)
        self._initialized = True

        self._clear_screen()

    def __del__(self) -> None:
        """Ensure the session is closed when the object is destroyed."""
        self.close()

    def _get_pane_content(self) -> str:
        """Capture the current pane content and update the buffer."""
        assert self._initialized, "Bash session is not initialized"
        assert isinstance(self.pane, libtmux.Pane)
        content = "\n".join(
            map(
                # avoid double newlines
                lambda line: line.rstrip(),
                self.pane.cmd("capture-pane", "-J", "-pS", "-").stdout,
            )
        )
        return content

    def close(self) -> None:
        """Clean up the session."""
        if self._closed:
            return
        if hasattr(self, "session"):
            self.session.kill()
        self._closed = True

    @property
    def cwd(self) -> str:
        return self._cwd

    def _is_special_key(self, command: str) -> bool:
        """Check if the command is a special key."""
        # Special keys are of the form C-<key>
        _command = command.strip()
        return _command.startswith("C-") and len(_command) == 3

    def _clear_screen(self) -> None:
        """Clear the tmux pane screen and history."""
        assert self._initialized, "Bash session is not initialized"
        assert isinstance(self.pane, libtmux.Pane)
        self.pane.send_keys("C-l", enter=False)
        time.sleep(0.1)
        self.pane.cmd("clear-history")

    def _get_command_output(
        self,
        command: str,
        raw_command_output: str,
        metadata: CmdOutputMetadata,
        continue_prefix: str = "",
    ) -> str:
        """Get the command output with the previous command output removed.

        Args:
            command: The command that was executed.
            raw_command_output: The raw output from the command.
            metadata: The metadata object to store prefix/suffix in.
            continue_prefix: The prefix to add to the command output if it's a
                continuation of the previous command.
        """
        # remove the previous command output from the new output if any
        if self.prev_output:
            command_output = raw_command_output.removeprefix(self.prev_output)
            metadata.prefix = continue_prefix
        else:
            command_output = raw_command_output
        self.prev_output = raw_command_output  # update current command output anyway
        command_output = _remove_command_prefix(command_output, command)
        return command_output.rstrip()

    def _handle_completed_command(
        self,
        command: str,
        pane_content: str,
        ps1_matches: list[re.Match],
    ) -> ExecuteBashObservation:
        is_special_key = self._is_special_key(command)
        assert len(ps1_matches) >= 1, (
            f"Expected at least one PS1 metadata block, but got {len(ps1_matches)}.\n---FULL OUTPUT---\n{pane_content!r}\n---END OF OUTPUT---"  # noqa: E501
        )
        metadata = CmdOutputMetadata.from_ps1_match(ps1_matches[-1])

        # Special case where the previous command output is truncated
        # due to history limit
        # We should get the content BEFORE the last PS1 prompt
        get_content_before_last_match = bool(len(ps1_matches) == 1)

        # Update the current working directory if it has changed
        if metadata.working_dir != self._cwd and metadata.working_dir:
            self._cwd = metadata.working_dir

        logger.debug(f"COMMAND OUTPUT: {pane_content}")
        # Extract the command output between the two PS1 prompts
        raw_command_output = self._combine_outputs_between_matches(
            pane_content,
            ps1_matches,
            get_content_before_last_match=get_content_before_last_match,
        )

        if get_content_before_last_match:
            # Count the number of lines in the truncated output
            num_lines = len(raw_command_output.splitlines())
            metadata.prefix = f"[Previous command outputs are truncated. Showing the last {num_lines} lines of the output below.]\n"  # noqa: E501

        metadata.suffix = (
            f"\n[The command completed with exit code {metadata.exit_code}.]"
            if not is_special_key
            else f"\n[The command completed with exit code {metadata.exit_code}. CTRL+{command[-1].upper()} was sent.]"  # noqa: E501
        )
        command_output = self._get_command_output(
            command,
            raw_command_output,
            metadata,
        )
        self.prev_status = BashCommandStatus.COMPLETED
        self.prev_output = ""  # Reset previous command output
        self._ready_for_next_command()
        return ExecuteBashObservation(
            output=command_output,
            command=command,
            metadata=metadata,
        )

    def _handle_nochange_timeout_command(
        self,
        command: str,
        pane_content: str,
        ps1_matches: list[re.Match],
    ) -> ExecuteBashObservation:
        self.prev_status = BashCommandStatus.NO_CHANGE_TIMEOUT
        if len(ps1_matches) != 1:
            logger.warning(
                f"Expected exactly one PS1 metadata block BEFORE the execution of a command, but got {len(ps1_matches)} PS1 metadata blocks:\n---\n{pane_content!r}\n---"  # noqa: E501
            )
        raw_command_output = self._combine_outputs_between_matches(
            pane_content, ps1_matches
        )
        metadata = CmdOutputMetadata()  # No metadata available
        metadata.suffix = f"\n[The command has no new output after {self.no_change_timeout_seconds} seconds. {TIMEOUT_MESSAGE_TEMPLATE}]"  # noqa: E501
        command_output = self._get_command_output(
            command,
            raw_command_output,
            metadata,
            continue_prefix="[Below is the output of the previous command.]\n",
        )
        return ExecuteBashObservation(
            output=command_output,
            command=command,
            metadata=metadata,
        )

    def _handle_hard_timeout_command(
        self,
        command: str,
        pane_content: str,
        ps1_matches: list[re.Match],
        timeout: float,
    ) -> ExecuteBashObservation:
        self.prev_status = BashCommandStatus.HARD_TIMEOUT
        if len(ps1_matches) != 1:
            logger.warning(
                f"Expected exactly one PS1 metadata block BEFORE the execution of a command, but got {len(ps1_matches)} PS1 metadata blocks:\n---\n{pane_content!r}\n---"  # noqa: E501
            )
        raw_command_output = self._combine_outputs_between_matches(
            pane_content, ps1_matches
        )
        metadata = CmdOutputMetadata()  # No metadata available
        metadata.suffix = f"\n[The command timed out after {timeout} seconds. {TIMEOUT_MESSAGE_TEMPLATE}]"  # noqa: E501
        command_output = self._get_command_output(
            command,
            raw_command_output,
            metadata,
            continue_prefix="[Below is the output of the previous command.]\n",
        )

        return ExecuteBashObservation(
            output=command_output,
            command=command,
            metadata=metadata,
        )

    def _ready_for_next_command(self) -> None:
        """Reset the content buffer for a new command."""
        # Clear the current content
        self._clear_screen()

    def _combine_outputs_between_matches(
        self,
        pane_content: str,
        ps1_matches: list[re.Match],
        get_content_before_last_match: bool = False,
    ) -> str:
        """Combine all outputs between PS1 matches.

        Args:
            pane_content: The full pane content containing PS1 prompts and command
                outputs
            ps1_matches: List of regex matches for PS1 prompts
            get_content_before_last_match: when there's only one PS1 match, whether
                to get the content before the last PS1 prompt (True) or after the
                last PS1 prompt (False)

        Returns:
            Combined string of all outputs between matches
        """
        if len(ps1_matches) == 1:
            if get_content_before_last_match:
                # The command output is the content before the last PS1 prompt
                return pane_content[: ps1_matches[0].start()]
            else:
                # The command output is the content after the last PS1 prompt
                return pane_content[ps1_matches[0].end() + 1 :]
        elif len(ps1_matches) == 0:
            return pane_content
        combined_output = ""
        for i in range(len(ps1_matches) - 1):
            # Extract content between current and next PS1 prompt
            output_segment = pane_content[
                ps1_matches[i].end() + 1 : ps1_matches[i + 1].start()
            ]
            combined_output += output_segment + "\n"
        # Add the content after the last PS1 prompt
        combined_output += pane_content[ps1_matches[-1].end() + 1 :]
        logger.debug(f"COMBINED OUTPUT: {combined_output}")
        return combined_output

    def execute(self, action: ExecuteBashAction) -> ExecuteBashObservation:
        """Execute a command in the bash session."""
        if not self._initialized or not isinstance(self.pane, libtmux.Pane):
            raise RuntimeError("Bash session is not initialized")

        # Strip the command of any leading/trailing whitespace
        logger.debug(f"RECEIVED ACTION: {action}")
        command = action.command.strip()
        is_input: bool = action.is_input

        # If the previous command is not completed,
        # we need to check if the command is empty
        if self.prev_status not in {
            BashCommandStatus.CONTINUE,
            BashCommandStatus.NO_CHANGE_TIMEOUT,
            BashCommandStatus.HARD_TIMEOUT,
        }:
            if command == "":
                return ExecuteBashObservation(
                    output="ERROR: No previous running command to retrieve logs from.",
                    error=True,
                )
            if is_input:
                return ExecuteBashObservation(
                    output="ERROR: No previous running command to interact with.",
                    error=True,
                )

        # Check if the command is a single command or multiple commands
        splited_commands = split_bash_commands(command)
        if len(splited_commands) > 1:
            return ExecuteBashObservation(
                output=(
                    f"ERROR: Cannot execute multiple commands at once.\nPlease run each command separately OR chain them into a single command via && or ;\nProvided commands:\n{'\n'.join(f'({i + 1}) {cmd}' for i, cmd in enumerate(splited_commands))}"  # noqa: E501
                ),
                error=True,
            )

        # Get initial state before sending command
        initial_pane_output = self._get_pane_content()
        initial_ps1_matches = CmdOutputMetadata.matches_ps1_metadata(
            initial_pane_output
        )
        initial_ps1_count = len(initial_ps1_matches)
        logger.debug(f"Initial PS1 count: {initial_ps1_count}")

        start_time = time.time()
        last_change_time = start_time
        last_pane_output = (
            initial_pane_output  # Use initial output as the starting point
        )

        # When prev command is still running, and we are trying to send a new command
        if (
            self.prev_status
            in {
                BashCommandStatus.HARD_TIMEOUT,
                BashCommandStatus.NO_CHANGE_TIMEOUT,
            }
            and not last_pane_output.rstrip().endswith(
                CMD_OUTPUT_PS1_END.rstrip()
            )  # prev command is not completed
            and not is_input
            and command != ""  # not input and not empty command
        ):
            _ps1_matches = CmdOutputMetadata.matches_ps1_metadata(last_pane_output)
            # Use initial_ps1_matches if _ps1_matches is empty,
            # otherwise use _ps1_matches. This handles the case where
            # the prompt might be scrolled off screen but existed before
            current_matches_for_output = (
                _ps1_matches if _ps1_matches else initial_ps1_matches
            )
            raw_command_output = self._combine_outputs_between_matches(
                last_pane_output, current_matches_for_output
            )
            metadata = CmdOutputMetadata()  # No metadata available
            metadata.suffix = f'\n[Your command "{command}" is NOT executed. The previous command is still running - You CANNOT send new commands until the previous command is completed. By setting `is_input` to `true`, you can interact with the current process: {TIMEOUT_MESSAGE_TEMPLATE}]'  # noqa: E501
            logger.debug(f"PREVIOUS COMMAND OUTPUT: {raw_command_output}")
            command_output = self._get_command_output(
                command,
                raw_command_output,
                metadata,
                continue_prefix="[Below is the output of the previous command.]\n",
            )
            return ExecuteBashObservation(
                output=command_output,
                command=command,
                metadata=metadata,
            )

        # Send actual command/inputs to the pane
        if command != "":
            is_special_key = self._is_special_key(command)
            if is_input:
                logger.debug(f"SENDING INPUT TO RUNNING PROCESS: {command!r}")
                self.pane.send_keys(
                    command,
                    enter=not is_special_key,
                )
            else:
                # convert command to raw string
                command = escape_bash_special_chars(command)
                logger.debug(f"SENDING COMMAND: {command!r}")
                self.pane.send_keys(
                    command,
                    enter=not is_special_key,
                )

        # Loop until the command completes or times out
        while True:
            _start_time = time.time()
            logger.debug(f"GETTING PANE CONTENT at {_start_time}")
            cur_pane_output = self._get_pane_content()
            logger.debug(
                f"PANE CONTENT GOT after {time.time() - _start_time:.2f} seconds"
            )
            logger.debug(f"BEGIN OF PANE CONTENT: {cur_pane_output.split('\n')[:10]}")
            logger.debug(f"END OF PANE CONTENT: {cur_pane_output.split('\n')[-10:]}")
            ps1_matches = CmdOutputMetadata.matches_ps1_metadata(cur_pane_output)
            current_ps1_count = len(ps1_matches)

            if cur_pane_output != last_pane_output:
                last_pane_output = cur_pane_output
                last_change_time = time.time()
                logger.debug(f"CONTENT UPDATED DETECTED at {last_change_time}")

            # 1) Execution completed:
            # Condition 1: A new prompt has appeared since the command started.
            # Condition 2: The prompt count hasn't increased (potentially because the
            # initial one scrolled off),
            # BUT the *current* visible pane ends with a prompt, indicating completion.
            if (
                current_ps1_count > initial_ps1_count
                or cur_pane_output.rstrip().endswith(CMD_OUTPUT_PS1_END.rstrip())
            ):
                return self._handle_completed_command(
                    command,
                    pane_content=cur_pane_output,
                    ps1_matches=ps1_matches,
                )

            # Timeout checks should only trigger if a new prompt hasn't appeared yet.

            # 2) Execution timed out since there's no change in output
            # for a while (NO_CHANGE_TIMEOUT_SECONDS)
            # We ignore this if the command is *blocking*
            time_since_last_change = time.time() - last_change_time
            is_blocking = action.timeout is not None
            logger.debug(
                f"CHECKING NO CHANGE TIMEOUT ({self.no_change_timeout_seconds}s): "
                f"elapsed {time_since_last_change}. Action blocking: {is_blocking}"
            )
            if (
                not is_blocking
                and time_since_last_change >= self.no_change_timeout_seconds
            ):
                return self._handle_nochange_timeout_command(
                    command,
                    pane_content=cur_pane_output,
                    ps1_matches=ps1_matches,
                )

            # 3) Execution timed out due to hard timeout
            elapsed_time = time.time() - start_time
            logger.debug(
                f"CHECKING HARD TIMEOUT ({action.timeout}s): elapsed {elapsed_time:.2f}"
            )
            if action.timeout and elapsed_time >= action.timeout:
                logger.debug("Hard timeout triggered.")
                return self._handle_hard_timeout_command(
                    command,
                    pane_content=cur_pane_output,
                    ps1_matches=ps1_matches,
                    timeout=action.timeout,
                )

            logger.debug(f"SLEEPING for {POLL_INTERVAL} seconds for next poll")
            time.sleep(POLL_INTERVAL)
        raise RuntimeError("Bash session was likely interrupted...")
