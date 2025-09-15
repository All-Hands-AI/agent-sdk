"""Tests for DatadogTool."""

from unittest.mock import Mock, patch

import pytest
import requests

from openhands.tools.datadog_api.definition import (
    DatadogExecutor,
    DatadogSearchLogsAction,
    DatadogTool,
)


def test_datadog_executor_init():
    """Test DatadogExecutor initialization."""
    executor = DatadogExecutor(api_key="test_key", app_key="test_app_key")
    assert executor.api_key == "test_key"
    assert executor.app_key == "test_app_key"
    assert executor.base_url == "https://api.datadoghq.com"


@patch.dict("os.environ", {}, clear=True)
def test_datadog_executor_init_missing_keys():
    """Test DatadogExecutor initialization with missing keys."""
    with pytest.raises(ValueError, match="Datadog API key is required"):
        DatadogExecutor(api_key=None, app_key="test_app_key")

    with pytest.raises(ValueError, match="Datadog application key is required"):
        DatadogExecutor(api_key="test_key", app_key=None)


@patch("requests.post")
def test_executor_call_success(mock_post):
    """Test successful log search via executor call."""
    # Mock response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {
                "id": "log1",
                "attributes": {
                    "timestamp": "2023-01-01T00:00:00Z",
                    "message": "Test error message",
                    "service": "test-service",
                    "status": "error",
                },
            }
        ],
        "meta": {"page": {"after": None}},
    }
    mock_post.return_value = mock_response

    executor = DatadogExecutor(api_key="test_key", app_key="test_app_key")
    action = DatadogSearchLogsAction(query="status:error", limit=10)
    result = executor(action)

    # Verify request was made correctly
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://api.datadoghq.com/api/v2/logs/events/search"
    assert call_args[1]["headers"]["DD-API-KEY"] == "test_key"
    assert call_args[1]["headers"]["DD-APPLICATION-KEY"] == "test_app_key"

    # Verify result
    assert result.error is None
    assert len(result.logs) == 1
    assert result.logs[0]["id"] == "log1"
    assert result.query == "status:error"


@patch("requests.post")
def test_executor_call_api_error(mock_post):
    """Test API error handling."""
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    mock_post.return_value = mock_response

    executor = DatadogExecutor(api_key="test_key", app_key="test_app_key")
    action = DatadogSearchLogsAction(query="invalid query")
    result = executor(action)

    assert result.error is not None
    assert "HTTP 400" in result.error
    assert "Bad Request" in result.error


@patch("requests.post")
def test_executor_call_request_exception(mock_post):
    """Test request exception handling."""
    mock_post.side_effect = requests.RequestException("Network error")

    executor = DatadogExecutor(api_key="test_key", app_key="test_app_key")
    action = DatadogSearchLogsAction(query="status:error")
    result = executor(action)

    assert result.error is not None
    assert "Request failed" in result.error
    assert "Network error" in result.error


def test_datadog_tool_create():
    """Test DatadogTool.create() method."""
    tool = DatadogTool.create(api_key="test_key", app_key="test_app_key")
    assert isinstance(tool.executor, DatadogExecutor)
    assert tool.executor.api_key == "test_key"
    assert tool.executor.app_key == "test_app_key"


@patch("requests.post")
def test_datadog_tool_execution(mock_post):
    """Test DatadogTool execution."""
    # Mock response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {
                "id": "log1",
                "attributes": {
                    "timestamp": "2023-01-01T00:00:00Z",
                    "message": "Test error message",
                    "service": "test-service",
                    "status": "error",
                },
            }
        ],
        "meta": {"page": {"after": None}},
    }
    mock_post.return_value = mock_response

    tool = DatadogTool.create(api_key="test_key", app_key="test_app_key")
    action = DatadogSearchLogsAction(query="status:error", limit=5)
    assert isinstance(tool.executor, DatadogExecutor)
    result = tool.executor(action)

    # Verify the result
    assert result.error is None
    assert len(result.logs) == 1
    assert result.logs[0]["id"] == "log1"


@patch("requests.post")
def test_executor_with_time_range(mock_post):
    """Test executor with time range parameters."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [], "meta": {"page": {"after": None}}}
    mock_post.return_value = mock_response

    executor = DatadogExecutor(api_key="test_key", app_key="test_app_key")
    action = DatadogSearchLogsAction(
        query="status:error",
        limit=10,
        from_time="2023-01-01T00:00:00Z",
        to_time="2023-01-02T00:00:00Z",
    )
    executor(action)

    # Verify the request payload includes time range
    call_args = mock_post.call_args
    payload = call_args[1]["json"]
    assert "from" in payload["filter"]
    assert "to" in payload["filter"]


def test_datadog_search_logs_action():
    """Test DatadogSearchLogsAction creation and validation."""
    action = DatadogSearchLogsAction(query="status:error", limit=5)
    assert action.query == "status:error"
    assert action.limit == 5
    assert action.sort == "-timestamp"  # default value

    # Test validation
    with pytest.raises(ValueError):
        DatadogSearchLogsAction(query="test", limit=0)  # limit too low

    with pytest.raises(ValueError):
        DatadogSearchLogsAction(query="test", limit=1001)  # limit too high
