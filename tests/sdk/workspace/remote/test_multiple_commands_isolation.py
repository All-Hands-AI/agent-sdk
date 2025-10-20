"""Test command output isolation for sequential execute_command calls.

This test verifies that executing multiple commands sequentially produces
isolated outputs, ensuring each command's result contains only its own output
without contamination from previous commands.
"""

from unittest.mock import Mock

from openhands.sdk.workspace.remote.remote_workspace_mixin import RemoteWorkspaceMixin


class TestRemoteWorkspaceMixin(RemoteWorkspaceMixin):
    """Test implementation of RemoteWorkspaceMixin for testing purposes."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


def test_multiple_commands_output_isolation():
    """Test that executing multiple commands produces isolated outputs.

    Verifies that each execute_command call returns only its own output,
    without including output from previous commands.

    This ensures proper command_id filtering in the API request params,
    so only events for the current command are retrieved.
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

    # With correct command_id filter, the API returns ONLY
    # the current command's events (not previous commands)
    poll_response_2 = Mock()
    poll_response_2.raise_for_status = Mock()
    poll_response_2.json.return_value = {
        "items": [
            # Events from second command only (first command events filtered out by API)
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
        generator_2.send(poll_response_2)
    except StopIteration as e:
        result_2 = e.value

    # Verify output isolation:
    # result_2.stdout should only contain "total 84" and "agent-server" etc
    # It should NOT contain "bash_events", "conversations", "project" from first command
    assert result_2.exit_code == 0
    print(f"Result 2 stdout:\n{result_2.stdout}")

    # Verify that previous command output is not present
    assert "bash_events" not in result_2.stdout, (
        "Second command output incorrectly includes first command output! "
        "The output should NOT contain 'bash_events' from the first command."
    )
    assert "conversations" not in result_2.stdout, (
        "Second command output incorrectly includes first command output! "
        "The output should NOT contain 'conversations' from the first command."
    )
    # Verify that current command output is present
    assert "agent-server" in result_2.stdout


def test_command_id_filter_params_structure():
    """Test that command_id__eq and sort_order are separate params.

    Verifies that the API search params are correctly structured
    with separate keys for command_id filtering and sort_order,
    ensuring proper event filtering by command ID.
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

    # Verify the params dict has separate keys for filtering and sorting
    params = poll_kwargs["params"]

    print(f"\nActual params: {params}")
    print(f"Params keys: {list(params.keys())}")

    # Verify params structure is correct
    assert "command_id__eq" in params, (
        "Missing command_id__eq param for filtering events by command ID"
    )
    assert params["command_id__eq"] == "cmd-123", (
        "The command_id__eq param should filter by the command ID 'cmd-123'"
    )
    assert "sort_order" in params, (
        "Missing sort_order param for sorting events by timestamp"
    )
    assert params["sort_order"] == "TIMESTAMP", (
        "The sort_order param should be set to 'TIMESTAMP'"
    )
