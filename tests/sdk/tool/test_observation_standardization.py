"""Tests for standardized Observation class functionality."""

from collections.abc import Sequence
from typing import Any

import pytest
from pydantic import Field

from openhands.sdk.llm import ImageContent, TextContent
from openhands.sdk.tool.schema import Observation, ObservationStatus


class StandardObservation(Observation):
    """Standard observation using base class defaults."""

    # Uses inherited error: Any and output: str fields
    pass


class CustomErrorObservation(Observation):
    """Observation with custom error field type."""

    error: bool = Field(default=False, description="Boolean error flag")
    custom_data: str = Field(default="", description="Custom data field")

    @property
    def has_error(self) -> bool:
        """Override to handle boolean error field."""
        return self.error

    def _format_error(self) -> TextContent:
        """Custom error formatting."""
        return TextContent(text="[Custom error occurred]")


class CustomOutputObservation(Observation):
    """Observation with custom output field name."""

    content: str = Field(default="", description="Content instead of output")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata")

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        """Override to use content field."""
        if self.has_error:
            return [self._format_error()]
        return [TextContent(text=self.content)]


class RichContentObservation(Observation):
    """Observation with rich content support."""

    content: list[TextContent | ImageContent] = Field(
        default_factory=list, description="Rich content list"
    )

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        """Override to return rich content."""
        if self.has_error:
            return [self._format_error()] + self.content
        return self.content


def test_observation_status_enum():
    """Test ObservationStatus enum values."""
    assert ObservationStatus.SUCCESS == "success"
    assert ObservationStatus.ERROR == "error"


def test_standard_observation_no_error():
    """Test standard observation without error."""
    obs = StandardObservation(output="Test output")

    assert obs.error is None
    assert not obs.has_error
    assert obs.status == ObservationStatus.SUCCESS
    assert obs.output == "Test output"

    content = obs.to_llm_content
    assert len(content) == 1
    assert isinstance(content[0], TextContent)
    assert content[0].text == "Test output"


def test_standard_observation_with_error():
    """Test standard observation with error."""
    obs = StandardObservation(error="Something went wrong", output="Failed output")

    assert obs.error == "Something went wrong"
    assert obs.has_error
    assert obs.status == ObservationStatus.ERROR

    content = obs.to_llm_content
    assert len(content) == 1
    assert isinstance(content[0], TextContent)
    assert content[0].text == "Error: Something went wrong"


def test_custom_error_observation():
    """Test observation with custom boolean error field."""
    # No error case
    obs_success = CustomErrorObservation(error=False, output="Success")
    assert not obs_success.has_error
    assert obs_success.status == ObservationStatus.SUCCESS

    content = obs_success.to_llm_content
    assert len(content) == 1
    assert isinstance(content[0], TextContent)
    assert content[0].text == "Success"

    # Error case
    obs_error = CustomErrorObservation(error=True, output="Failed")
    assert obs_error.has_error
    assert obs_error.status == ObservationStatus.ERROR

    content = obs_error.to_llm_content
    assert len(content) == 1
    assert isinstance(content[0], TextContent)
    assert content[0].text == "[Custom error occurred]"


def test_custom_output_observation():
    """Test observation with custom output field name."""
    obs = CustomOutputObservation(content="Custom content", metadata={"key": "value"})

    assert not obs.has_error
    assert obs.status == ObservationStatus.SUCCESS

    content = obs.to_llm_content
    assert len(content) == 1
    assert isinstance(content[0], TextContent)
    assert content[0].text == "Custom content"


def test_custom_output_observation_with_error():
    """Test custom output observation with error."""
    obs = CustomOutputObservation(
        error="Custom error", content="Content", metadata={"key": "value"}
    )

    assert obs.has_error
    assert obs.status == ObservationStatus.ERROR

    content = obs.to_llm_content
    assert len(content) == 1
    assert isinstance(content[0], TextContent)
    assert content[0].text == "Error: Custom error"


def test_rich_content_observation():
    """Test observation with rich content support."""
    text_content = TextContent(text="Text content")
    image_content = ImageContent(image_urls=["data:image/png;base64,test"])

    obs = RichContentObservation(content=[text_content, image_content])

    assert not obs.has_error
    assert obs.status == ObservationStatus.SUCCESS

    content = obs.to_llm_content
    assert len(content) == 2
    assert content[0] == text_content
    assert content[1] == image_content


def test_rich_content_observation_with_error():
    """Test rich content observation with error."""
    text_content = TextContent(text="Text content")
    obs = RichContentObservation(error="Rich error", content=[text_content])

    assert obs.has_error
    assert obs.status == ObservationStatus.ERROR

    content = obs.to_llm_content
    assert len(content) == 2
    assert isinstance(content[0], TextContent)
    assert content[0].text == "Error: Rich error"
    assert content[1] == text_content


def test_observation_base_fields():
    """Test that base observation has expected fields."""
    obs = StandardObservation()

    # Check default values
    assert obs.error is None
    assert obs.output == ""
    assert not obs.has_error
    assert obs.status == ObservationStatus.SUCCESS


def test_observation_error_field_flexibility():
    """Test that error field can be different types in subclasses."""
    # String error
    obs1 = StandardObservation(error="string error")
    assert obs1.error == "string error"
    assert obs1.has_error

    # Boolean error
    obs2 = CustomErrorObservation(error=True)
    assert obs2.error is True
    assert obs2.has_error

    # None error
    obs3 = StandardObservation(error=None)
    assert obs3.error is None
    assert not obs3.has_error


def test_observation_immutability():
    """Test that observations are immutable."""
    obs = StandardObservation(output="test", error="error")

    # Should not be able to modify fields
    with pytest.raises(Exception):  # ValidationError from pydantic
        obs.output = "modified"

    with pytest.raises(Exception):  # ValidationError from pydantic
        obs.error = "modified"


def test_observation_model_copy():
    """Test that observations can be copied with updates."""
    original = StandardObservation(output="original", error="original error")

    # Create copy with updates
    updated = original.model_copy(update={"output": "updated", "error": None})

    # Original should be unchanged
    assert original.output == "original"
    assert original.error == "original error"
    assert original.has_error

    # Updated should have new values
    assert updated.output == "updated"
    assert updated.error is None
    assert not updated.has_error

    # Should be different instances
    assert original is not updated


def test_observation_status_property():
    """Test the status property computation."""
    # Success case
    obs_success = StandardObservation(output="success")
    assert obs_success.status == ObservationStatus.SUCCESS

    # Error case with string
    obs_error_str = StandardObservation(error="error message")
    assert obs_error_str.status == ObservationStatus.ERROR

    # Error case with boolean
    obs_error_bool = CustomErrorObservation(error=True)
    assert obs_error_bool.status == ObservationStatus.ERROR


def test_format_error_method():
    """Test the _format_error method."""
    obs = StandardObservation(error="Test error message")
    error_content = obs._format_error()

    assert isinstance(error_content, TextContent)
    assert error_content.text == "Error: Test error message"


def test_observation_inheritance_compatibility():
    """Test that existing observation patterns still work."""

    class LegacyObservation(Observation):
        """Legacy observation that doesn't use base fields."""

        result: str = Field(description="Legacy result field")
        success: bool = Field(default=True, description="Legacy success field")

        @property
        def has_error(self) -> bool:
            """Override error detection."""
            return not self.success

        @property
        def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
            """Custom content generation."""
            if self.has_error:
                return [TextContent(text=f"Failed: {self.result}")]
            return [TextContent(text=f"Success: {self.result}")]

    # Test success case
    obs_success = LegacyObservation(result="completed", success=True)
    assert not obs_success.has_error
    assert obs_success.status == ObservationStatus.SUCCESS

    content = obs_success.to_llm_content
    assert len(content) == 1
    assert isinstance(content[0], TextContent)
    assert content[0].text == "Success: completed"

    # Test error case
    obs_error = LegacyObservation(result="failed", success=False)
    assert obs_error.has_error
    assert obs_error.status == ObservationStatus.ERROR

    content = obs_error.to_llm_content
    assert len(content) == 1
    assert isinstance(content[0], TextContent)
    assert content[0].text == "Failed: failed"
