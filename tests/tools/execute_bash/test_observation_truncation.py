"""Tests for ExecuteBashObservation truncation functionality."""

from openhands.sdk.utils import DEFAULT_BASH_TRUNCATE_LIMIT
from openhands.tools.execute_bash.definition import ExecuteBashObservation
from openhands.tools.execute_bash.metadata import CmdOutputMetadata


def test_execute_bash_observation_truncation_under_limit():
    """Test ExecuteBashObservation doesn't truncate when under limit."""
    metadata = CmdOutputMetadata(
        prefix="",
        suffix="",
        working_dir="/test",
        py_interpreter_path="/usr/bin/python",
        exit_code=0,
        pid=123,
    )

    observation = ExecuteBashObservation(
        output="Short output",
        metadata=metadata,
        error=False,
    )

    result = observation.agent_observation
    expected = (
        "Short output\n"
        "[Current working directory: /test]\n"
        "[Python interpreter: /usr/bin/python]\n"
        "[Command finished with exit code 0]"
    )
    assert result == expected


def test_execute_bash_observation_truncation_over_limit():
    """Test ExecuteBashObservation truncates when over limit."""
    metadata = CmdOutputMetadata(
        prefix="",
        suffix="",
        working_dir="/test",
        py_interpreter_path="/usr/bin/python",
        exit_code=0,
        pid=123,
    )

    # Create output that exceeds the limit
    long_output = "A" * (DEFAULT_BASH_TRUNCATE_LIMIT + 1000)

    observation = ExecuteBashObservation(
        output=long_output,
        metadata=metadata,
        error=False,
    )

    result = observation.agent_observation

    # The result should be truncated
    assert len(result) < len(long_output) + 200  # Account for metadata
    assert result.endswith("</NOTE>")  # Should end with truncation notice


def test_execute_bash_observation_truncation_with_error():
    """Test ExecuteBashObservation truncates with error prefix."""
    metadata = CmdOutputMetadata(
        prefix="",
        suffix="",
        working_dir="/test",
        py_interpreter_path="/usr/bin/python",
        exit_code=1,
        pid=123,
    )

    # Create output that exceeds the limit
    long_output = "B" * (DEFAULT_BASH_TRUNCATE_LIMIT + 500)

    observation = ExecuteBashObservation(
        output=long_output,
        metadata=metadata,
        error=True,
    )

    result = observation.agent_observation

    # The result should be truncated and have error prefix
    assert result.startswith("[There was an error during command execution.]")
    assert len(result) < len(long_output) + 300  # Account for metadata and error prefix
    assert result.endswith("</NOTE>")  # Should end with truncation notice


def test_execute_bash_observation_truncation_exact_limit():
    """Test ExecuteBashObservation doesn't truncate when exactly at limit."""
    metadata = CmdOutputMetadata(
        prefix="",
        suffix="",
        working_dir="/test",
        py_interpreter_path="/usr/bin/python",
        exit_code=0,
        pid=123,
    )

    # Calculate exact size to hit the limit after adding metadata
    metadata_text = (
        "\n[Current working directory: /test]\n"
        "[Python interpreter: /usr/bin/python]\n"
        "[Command finished with exit code 0]"
    )
    exact_output_size = DEFAULT_BASH_TRUNCATE_LIMIT - len(metadata_text)
    exact_output = "C" * exact_output_size

    observation = ExecuteBashObservation(
        output=exact_output,
        metadata=metadata,
        error=False,
    )

    result = observation.agent_observation

    # Should not be truncated
    assert len(result) == DEFAULT_BASH_TRUNCATE_LIMIT
    assert not result.endswith("</NOTE>")


def test_execute_bash_observation_truncation_with_prefix_suffix():
    """Test ExecuteBashObservation truncates with prefix and suffix."""
    metadata = CmdOutputMetadata(
        prefix="[PREFIX] ",
        suffix=" [SUFFIX]",
        working_dir="/test",
        py_interpreter_path="/usr/bin/python",
        exit_code=0,
        pid=123,
    )

    # Create output that exceeds the limit
    long_output = "D" * (DEFAULT_BASH_TRUNCATE_LIMIT + 200)

    observation = ExecuteBashObservation(
        output=long_output,
        metadata=metadata,
        error=False,
    )

    result = observation.agent_observation

    # The result should be truncated and include prefix/suffix
    assert result.startswith("[PREFIX] ")
    assert (
        len(result) < len(long_output) + 300
    )  # Account for metadata and prefix/suffix
    assert result.endswith("</NOTE>")  # Should end with truncation notice
