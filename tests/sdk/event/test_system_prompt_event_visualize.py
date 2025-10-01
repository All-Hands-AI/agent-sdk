"""Tests for SystemPromptEvent.visualize method."""

import copy

from pydantic import Field

from openhands.sdk.event.llm_convertible import SystemPromptEvent
from openhands.sdk.llm import TextContent
from openhands.sdk.tool import ActionBase, Tool


class SimpleAction(ActionBase):
    """Simple test action."""

    pass


def test_visualize_no_data_mutation():
    """Test that visualize does not mutate the original event data."""
    # Create a test tool
    tool = Tool(
        name="test_tool",
        description="Test description",
        action_type=SimpleAction,
    )

    event = SystemPromptEvent(
        system_prompt=TextContent(text="Test system prompt"),
        tools=[tool],
    )

    # Store initial state
    initial_tool_state = copy.deepcopy(event.tools[0])

    # Call visualize multiple times
    for _ in range(3):
        _ = event.visualize

    # Verify no mutation occurred
    assert event.tools[0] == initial_tool_state
    assert event.tools[0].name == initial_tool_state.name
    assert event.tools[0].description == initial_tool_state.description


class LongParametersAction(ActionBase):
    """Action with many parameters to test truncation."""

    param_0: str = Field(description="Parameter 0 with very long description")
    param_1: str = Field(description="Parameter 1 with very long description")
    param_2: str = Field(description="Parameter 2 with very long description")
    param_3: str = Field(description="Parameter 3 with very long description")
    param_4: str = Field(description="Parameter 4 with very long description")
    param_5: str = Field(description="Parameter 5 with very long description")
    param_6: str = Field(description="Parameter 6 with very long description")
    param_7: str = Field(description="Parameter 7 with very long description")
    param_8: str = Field(description="Parameter 8 with very long description")
    param_9: str = Field(description="Parameter 9 with very long description")


def test_visualize_parameter_truncation():
    """Test that long parameter JSON strings are truncated in display."""
    # Create tool with many parameters
    tool = Tool(
        name="test_tool",
        description="Test tool",
        action_type=LongParametersAction,
    )

    event = SystemPromptEvent(
        system_prompt=TextContent(text="Test system prompt"),
        tools=[tool],
    )

    # Get visualization
    visualization = event.visualize
    visualization_text = visualization.plain

    # Find parameters line
    params_lines = [
        line for line in visualization_text.split("\n") if "Parameters:" in line
    ]
    assert len(params_lines) == 1

    params_text = params_lines[0].split("Parameters: ")[1]

    # Verify truncation
    assert len(params_text) <= 200
    assert params_text.endswith("...")


def test_visualize_string_truncation_logic():
    """Test the string truncation logic for tool fields."""
    # Create tool with long description
    long_description = (
        "This is a very long description that should be truncated when displayed "
        "in the visualization because it exceeds the 100 character limit that is "
        "applied to the first line of the description in the visualize method"
    )

    tool = Tool(
        name="test_tool_with_very_long_name_exceeding_limit",
        description=long_description,
        action_type=SimpleAction,
    )

    event = SystemPromptEvent(
        system_prompt=TextContent(text="Test system prompt"),
        tools=[tool],
    )

    # Store original lengths
    original_name_len = len(tool.name)
    original_desc_len = len(tool.description)

    # Call visualize
    visualization = event.visualize
    visualization_text = visualization.plain

    # Verify original data unchanged
    assert len(event.tools[0].name) == original_name_len
    assert len(event.tools[0].description) == original_desc_len

    # Verify visualization contains truncated display
    assert "..." in visualization_text  # Some truncation occurred in display
