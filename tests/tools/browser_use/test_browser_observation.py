"""Tests for BrowserObservation wrapper behavior."""

from openhands.sdk.llm.message import ImageContent, TextContent
from openhands.tools.browser_use.definition import BrowserObservation


def test_browser_observation_basic_output():
    """Test basic BrowserObservation creation with output."""
    observation = BrowserObservation(output="Test output")

    assert observation.output == "Test output"
    assert observation.error is None
    assert observation.screenshot_data is None


def test_browser_observation_with_error():
    """Test BrowserObservation with error."""
    observation = BrowserObservation(output="", error="Test error")

    assert observation.output == ""
    assert observation.error == "Test error"
    assert observation.screenshot_data is None


def test_browser_observation_with_screenshot():
    """Test BrowserObservation with screenshot data."""
    screenshot_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jU77zgAAAABJRU5ErkJggg=="  # noqa: E501
    observation = BrowserObservation(
        output="Screenshot taken", screenshot_data=screenshot_data
    )

    assert observation.output == "Screenshot taken"
    assert observation.error is None
    assert observation.screenshot_data == screenshot_data


def test_browser_observation_agent_observation_text_only():
    """Test agent_observation property with text only."""
    observation = BrowserObservation(output="Test output")
    agent_obs = observation.agent_observation

    assert len(agent_obs) == 1
    assert isinstance(agent_obs[0], TextContent)
    assert agent_obs[0].text == "Test output"


def test_browser_observation_agent_observation_with_screenshot():
    """Test agent_observation property with screenshot."""
    screenshot_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jU77zgAAAABJRU5ErkJggg=="  # noqa: E501
    observation = BrowserObservation(
        output="Screenshot taken", screenshot_data=screenshot_data
    )
    agent_obs = observation.agent_observation

    assert len(agent_obs) == 2
    assert isinstance(agent_obs[0], TextContent)
    assert agent_obs[0].text == "Screenshot taken"
    assert isinstance(agent_obs[1], ImageContent)
    assert len(agent_obs[1].image_urls) == 1
    assert agent_obs[1].image_urls[0].startswith("data:image/png;base64,")
    assert screenshot_data in agent_obs[1].image_urls[0]


def test_browser_observation_agent_observation_with_error():
    """Test agent_observation property with error."""
    observation = BrowserObservation(output="", error="Test error")
    agent_obs = observation.agent_observation

    assert len(agent_obs) == 1
    assert isinstance(agent_obs[0], TextContent)
    assert agent_obs[0].text == "Error: Test error"


def test_browser_observation_output_truncation():
    """Test output truncation for very long outputs."""
    # Create a very long output string
    long_output = "x" * 100000  # 100k characters
    observation = BrowserObservation(output=long_output)

    agent_obs = observation.agent_observation

    # Should be truncated to MAX_BROWSER_OUTPUT_SIZE (50000)
    assert len(agent_obs) == 1
    assert isinstance(agent_obs[0], TextContent)
    assert len(agent_obs[0].text) <= 50000
    assert "<response clipped>" in agent_obs[0].text


def test_browser_observation_screenshot_data_url_conversion():
    """Test that screenshot data is properly converted to data URL."""
    screenshot_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jU77zgAAAABJRU5ErkJggg=="  # noqa: E501
    observation = BrowserObservation(output="Test", screenshot_data=screenshot_data)

    agent_obs = observation.agent_observation
    expected_data_url = f"data:image/png;base64,{screenshot_data}"

    assert len(agent_obs) == 2
    assert isinstance(agent_obs[1], ImageContent)
    assert agent_obs[1].image_urls[0] == expected_data_url


def test_browser_observation_empty_screenshot_handling():
    """Test handling of empty or None screenshot data."""
    observation = BrowserObservation(output="Test", screenshot_data="")
    agent_obs = observation.agent_observation
    assert len(agent_obs) == 1  # Only text content, no image

    observation = BrowserObservation(output="Test", screenshot_data=None)
    agent_obs = observation.agent_observation
    assert len(agent_obs) == 1  # Only text content, no image
