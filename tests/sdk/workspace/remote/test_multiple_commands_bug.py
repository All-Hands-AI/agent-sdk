"""Test to reproduce bug #825: Output from previous execute_command is included.

This test reproduces the bug where executing multiple commands sequentially
causes the output from previous commands to be included in subsequent command results.
"""

from unittest.mock import Mock

from openhands.sdk.workspace.remote.remote_workspace_mixin import RemoteWorkspaceMixin


class TestRemoteWorkspaceMixin(RemoteWorkspaceMixin):
    """Test implementation of RemoteWorkspaceMixin for testing purposes."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


def test_multiple_commands_should_not_include_previous_output():
    """Test that executing multiple commands doesn't include previous output.

    This reproduces bug #825 where the output from previous execute_command
    calls is included in the most recent command call.

    The bug occurs because the search params don't properly filter by command_id,
    so all events are returned instead of just events for the current command.
    """
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000")

    # ==== First command: ls -l /workspace ====
    start_response_1 = Mock()
    start_response_1.raise_for_status = Mock()
    start_response_1.json.return_value = {"id": "cmd-001"}

    # Events for first command
    poll_response_1 = Mock()
    poll_response_1.raise_for_status = Mock()
    poll_response_1.json.return_value = {
        "items": [
            {
                "kind": "BashOutput",
                "stdout": (
                    "total 12\n"
                    "drwxr-xr-x 2 openhands openhands 4096 Oct 20 17:29 bash_events\n"
                    "drwxr-xr-x 2 openhands openhands 4096 Oct 20 17:29 conversations\n"
                    "drwxr-xr-x 2 openhands openhands 4096 Oct 19 20:07 project\n"
                ),
                "stderr": "",
                "exit_code": 0,
            }
        ]
    }

    generator_1 = mixin._execute_command_generator("ls -l /workspace", None, 30.0)

    # Execute first command
    next(generator_1)  # Start command
    generator_1.send(start_response_1)

    try:
        generator_1.send(poll_response_1)
    except StopIteration as e:
        result_1 = e.value

    # Verify first command result is correct
    assert result_1.exit_code == 0
    assert "bash_events" in result_1.stdout
    assert "conversations" in result_1.stdout
    assert "project" in result_1.stdout

    # ==== Second command: ls -l ./ ====
    start_response_2 = Mock()
    start_response_2.raise_for_status = Mock()
    start_response_2.json.return_value = {"id": "cmd-002"}

    # BUG: Due to missing command_id filter, the API returns BOTH
    # the previous command's events AND the current command's events
    poll_response_2_buggy = Mock()
    poll_response_2_buggy.raise_for_status = Mock()
    poll_response_2_buggy.json.return_value = {
        "items": [
            # Events from FIRST command (should not be here)
            {
                "kind": "BashOutput",
                "stdout": (
                    "total 12\n"
                    "drwxr-xr-x 2 openhands openhands 4096 Oct 20 17:29 bash_events\n"
                    "drwxr-xr-x 2 openhands openhands 4096 Oct 20 17:29 conversations\n"
                    "drwxr-xr-x 2 openhands openhands 4096 Oct 19 20:07 project\n"
                ),
                "stderr": "",
                "exit_code": 0,
            },
            # Events from SECOND command (should be the only ones)
            {
                "kind": "BashOutput",
                "stdout": (
                    "total 84\n"
                    "drwxr-xr-x     1 openhands openhands 4096 "
                    "Oct 19 01:07 agent-server\n"
                    "lrwxrwxrwx     1 root      root         7 "
                    "Aug 24 16:20 bin -> usr/bin\n"
                ),
                "stderr": "",
                "exit_code": 0,
            },
        ]
    }

    generator_2 = mixin._execute_command_generator("ls -l ./", None, 30.0)

    # Execute second command
    next(generator_2)  # Start command
    generator_2.send(start_response_2)

    try:
        generator_2.send(poll_response_2_buggy)
    except StopIteration as e:
        result_2 = e.value

    # BUG MANIFESTATION: The second command's output includes the first command's output
    # This is the bug we're reproducing - the result should NOT contain first_output
    assert result_2.exit_code == 0

    # The buggy behavior: output contains BOTH commands' results
    # In the actual bug scenario, result_2.stdout would contain both outputs
    # because all events are retrieved, not just events for cmd-002

    # What we expect (after fix):
    # result_2.stdout should only contain "total 84" and "agent-server" etc
    # It should NOT contain "bash_events", "conversations", "project"

    # What actually happens (bug):
    # result_2.stdout contains the first output concatenated with the second
    print(f"Result 2 stdout:\n{result_2.stdout}")

    # Test for the CORRECT behavior - these will FAIL with the current buggy code
    # because result_2.stdout incorrectly includes the first command's output
    assert "bash_events" not in result_2.stdout, (
        "BUG: Second command output incorrectly includes first command output! "
        "The output should NOT contain 'bash_events' from the first command."
    )
    assert "conversations" not in result_2.stdout, (
        "BUG: Second command output incorrectly includes first command output! "
        "The output should NOT contain 'conversations' from the first command."
    )
    # The second command's output should be present
    assert "agent-server" in result_2.stdout


def test_command_id_filter_params_are_separate():
    """Test that command_id__eq and sort_order are separate params.

    This test verifies that the search params are correctly structured
    with separate keys for command_id filtering and sort_order.

    BUG: Line 93 in remote_workspace_mixin.py has:
        "command_id__eqsort_order": "TIMESTAMP"
    which should be two separate params:
        "command_id__eq": command_id,
        "sort_order": "TIMESTAMP"
    """
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000")

    start_response = Mock()
    start_response.raise_for_status = Mock()
    start_response.json.return_value = {"id": "cmd-123"}

    generator = mixin._execute_command_generator("echo test", None, 30.0)

    # Start command
    start_kwargs = next(generator)
    assert start_kwargs["method"] == "POST"

    # Send start response, get poll request
    poll_kwargs = generator.send(start_response)

    # BUG: The params dict has a malformed key "command_id__eqsort_order"
    # instead of separate "command_id__eq" and "sort_order" keys
    params = poll_kwargs["params"]

    print(f"\nActual params: {params}")
    print(f"Params keys: {list(params.keys())}")

    # Test for the CORRECT behavior - these will FAIL with the current buggy code
    # The params should have separate keys for command_id filtering and sort_order
    assert "command_id__eq" in params, (
        "Missing command_id__eq param. The buggy code has 'command_id__eqsort_order' "
        "instead of separate 'command_id__eq' and 'sort_order' keys."
    )
    assert params["command_id__eq"] == "cmd-123", (
        "The command_id__eq param should filter by the command ID 'cmd-123'"
    )
    assert "sort_order" in params, (
        "Missing sort_order param. The buggy code has 'command_id__eqsort_order' "
        "instead of separate 'command_id__eq' and 'sort_order' keys."
    )
    assert params["sort_order"] == "TIMESTAMP", (
        "The sort_order param should be set to 'TIMESTAMP'"
    )
