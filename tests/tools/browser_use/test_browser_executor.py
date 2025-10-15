"""Tests for BrowserToolExecutor integration logic."""

from unittest.mock import AsyncMock, patch

from openhands_tools.browser_use.definition import (
    BrowserClickAction,
    BrowserGetStateAction,
    BrowserNavigateAction,
    BrowserObservation,
)
from openhands_tools.browser_use.impl import BrowserToolExecutor

from .conftest import (
    assert_browser_observation_error,
    assert_browser_observation_success,
)


def test_browser_executor_initialization():
    """Test that BrowserToolExecutor initializes correctly."""
    executor = BrowserToolExecutor()

    assert executor._config["headless"] is True
    assert executor._config["allowed_domains"] == []
    assert executor._initialized is False
    assert executor._server is not None
    assert executor._async_executor is not None


def test_browser_executor_config_passing():
    """Test that configuration is passed correctly."""
    executor = BrowserToolExecutor(
        session_timeout_minutes=60,
        headless=False,
        allowed_domains=["example.com", "test.com"],
        custom_param="value",
    )

    assert executor._config["headless"] is False
    assert executor._config["allowed_domains"] == ["example.com", "test.com"]
    assert executor._config["custom_param"] == "value"


@patch("openhands_tools.browser_use.impl.BrowserToolExecutor.navigate")
async def test_browser_executor_action_routing_navigate(
    mock_navigate, mock_browser_executor
):
    """Test that navigate actions are routed correctly."""
    mock_navigate.return_value = "Navigation successful"

    action = BrowserNavigateAction(url="https://example.com", new_tab=False)
    result = await mock_browser_executor._execute_action(action)

    mock_navigate.assert_called_once_with("https://example.com", False)
    assert_browser_observation_success(result, "Navigation successful")


@patch("openhands_tools.browser_use.impl.BrowserToolExecutor.click")
async def test_browser_executor_action_routing_click(mock_click, mock_browser_executor):
    """Test that click actions are routed correctly."""
    mock_click.return_value = "Click successful"

    action = BrowserClickAction(index=5, new_tab=True)
    result = await mock_browser_executor._execute_action(action)

    mock_click.assert_called_once_with(5, True)
    assert_browser_observation_success(result, "Click successful")


@patch("openhands_tools.browser_use.impl.BrowserToolExecutor.get_state")
async def test_browser_executor_action_routing_get_state(
    mock_get_state, mock_browser_executor
):
    """Test that get_state actions are routed correctly and return directly."""
    expected_observation = BrowserObservation(
        output="State retrieved", screenshot_data="base64data"
    )
    mock_get_state.return_value = expected_observation

    action = BrowserGetStateAction(include_screenshot=True)
    result = await mock_browser_executor._execute_action(action)

    mock_get_state.assert_called_once_with(True)
    assert result is expected_observation


async def test_browser_executor_unsupported_action_handling(mock_browser_executor):
    """Test handling of unsupported action types."""

    class UnsupportedAction:
        pass

    action = UnsupportedAction()
    result = await mock_browser_executor._execute_action(action)

    assert_browser_observation_error(result, "Unsupported action type")


@patch("openhands_tools.browser_use.impl.BrowserToolExecutor.navigate")
async def test_browser_executor_error_wrapping(mock_navigate, mock_browser_executor):
    """Test that exceptions are properly wrapped in BrowserObservation."""
    mock_navigate.side_effect = Exception("Browser error occurred")

    action = BrowserNavigateAction(url="https://example.com")
    result = await mock_browser_executor._execute_action(action)

    assert_browser_observation_error(result, "Browser operation failed")
    assert "Browser error occurred" in result.error


def test_browser_executor_async_execution(mock_browser_executor):
    """Test that async execution works through the call method."""
    with patch.object(
        mock_browser_executor, "_execute_action", new_callable=AsyncMock
    ) as mock_execute:
        expected_result = BrowserObservation(output="Test result")
        mock_execute.return_value = expected_result

        action = BrowserNavigateAction(url="https://example.com")
        result = mock_browser_executor(action)

        assert result is expected_result
        mock_execute.assert_called_once_with(action)


async def test_browser_executor_initialization_lazy(mock_browser_executor):
    """Test that browser session initialization is lazy."""
    assert mock_browser_executor._initialized is False

    await mock_browser_executor._ensure_initialized()

    assert mock_browser_executor._initialized is True
    mock_browser_executor._server._init_browser_session.assert_called_once()


async def test_browser_executor_initialization_idempotent(mock_browser_executor):
    """Test that initialization is idempotent."""
    await mock_browser_executor._ensure_initialized()
    await mock_browser_executor._ensure_initialized()

    # Should only be called once
    assert mock_browser_executor._server._init_browser_session.call_count == 1
