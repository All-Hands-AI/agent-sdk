"""Datadog API tool implementation."""

import os
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

import requests
from pydantic import Field
from rich.text import Text

from openhands.sdk.llm import ImageContent, TextContent
from openhands.sdk.tool import (
    ActionBase,
    ObservationBase,
    Tool,
    ToolAnnotations,
    ToolExecutor,
)


class DatadogSearchLogsAction(ActionBase):
    """Schema for Datadog logs search."""

    query: str = Field(
        description=(
            "The search query to execute. Use Datadog search syntax, e.g., "
            "'status:error service:my-service', "
            "'-(status:warn OR status:notice OR status:info OR status:debug "
            'OR status:ok) service:deploy status:error "no tokens for user"\''
        )
    )
    from_time: str | None = Field(
        default=None,
        description=(
            "Start time for the search in ISO format "
            "(e.g., '2024-01-01T00:00:00+00:00'). "
            "If not provided, defaults to 24 hours ago."
        ),
    )
    to_time: str | None = Field(
        default=None,
        description=(
            "End time for the search in ISO format "
            "(e.g., '2024-01-01T23:59:59+00:00'). "
            "If not provided, defaults to current time."
        ),
    )
    limit: int = Field(
        default=10,
        description="Maximum number of log entries to retrieve (1-1000).",
        ge=1,
        le=1000,
    )
    sort: str = Field(
        default="-timestamp",
        description=(
            "Sort order for results. Use 'timestamp' for ascending, "
            "'-timestamp' for descending (default), or sort by facets like "
            "'@field_name'."
        ),
    )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation."""
        content = Text()
        content.append("🔍 Datadog Search: ", style="bold blue")
        content.append(f'"{self.query}"', style="white")

        if self.from_time or self.to_time:
            content.append(" | ", style="dim")
            if self.from_time:
                content.append(f"from: {self.from_time}", style="dim cyan")
            if self.to_time:
                content.append(f" to: {self.to_time}", style="dim cyan")

        content.append(f" | limit: {self.limit}", style="dim yellow")
        return content


class DatadogSearchLogsObservation(ObservationBase):
    """Observation from Datadog logs search."""

    logs: list[dict[str, Any]] = Field(
        default_factory=list, description="List of log entries found."
    )
    total_count: int = Field(default=0, description="Total number of logs found.")
    query: str = Field(description="The query that was executed.")
    error: str | None = Field(default=None, description="Error message if any.")
    next_cursor: str | None = Field(
        default=None, description="Cursor for pagination if more results available."
    )

    @property
    def agent_observation(self) -> Sequence[TextContent | ImageContent]:
        if self.error:
            return [TextContent(text=f"❌ Datadog API Error: {self.error}")]

        if not self.logs:
            return [TextContent(text=f"No logs found for query: {self.query}")]

        # Format the logs for the agent
        result_lines = [
            f"Found {len(self.logs)} logs (total: {self.total_count}) "
            f"for query: {self.query}",
            "",
        ]

        for i, log in enumerate(self.logs, 1):
            attrs = log.get("attributes", {})
            timestamp = attrs.get("timestamp", "Unknown time")
            status = attrs.get("status", "unknown")
            service = attrs.get("service", "unknown")
            message = attrs.get("message", "No message")
            host = attrs.get("host", "unknown")

            # Truncate long messages
            if len(message) > 200:
                message = message[:200] + "..."

            result_lines.extend(
                [
                    f"--- Log {i} ---",
                    f"Timestamp: {timestamp}",
                    f"Status: {status}",
                    f"Service: {service}",
                    f"Host: {host}",
                    f"Message: {message}",
                    "",
                ]
            )

        if self.next_cursor:
            result_lines.append("More results available (use pagination cursor)")

        return [TextContent(text="\n".join(result_lines))]

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation."""
        content = Text()

        if self.error:
            content.append("❌ ", style="red bold")
            content.append(f"Datadog API Error: {self.error}", style="red")
            return content

        if not self.logs:
            content.append("🔍 ", style="blue")
            content.append(f"No logs found for query: {self.query}", style="dim")
            return content

        # Header
        content.append("📊 ", style="green bold")
        content.append(
            f"Found {len(self.logs)} logs (total: {self.total_count})", style="green"
        )
        content.append("\n")

        # Show first few logs with styling
        for i, log in enumerate(self.logs[:3], 1):
            attrs = log.get("attributes", {})
            status = attrs.get("status", "unknown")
            service = attrs.get("service", "unknown")
            message = attrs.get("message", "No message")

            # Status styling
            if status == "error":
                status_style = "red bold"
            elif status == "warn":
                status_style = "yellow"
            else:
                status_style = "green"

            content.append(f"\n{i}. ", style="bold")
            content.append(f"[{status}] ", style=status_style)
            content.append(f"{service}: ", style="blue")

            # Truncate message for display
            display_message = message[:100] + "..." if len(message) > 100 else message
            content.append(display_message, style="white")

        if len(self.logs) > 3:
            content.append(f"\n... and {len(self.logs) - 3} more logs", style="dim")

        return content


class DatadogExecutor(
    ToolExecutor[DatadogSearchLogsAction, DatadogSearchLogsObservation]
):
    """Executor for Datadog API operations."""

    def __init__(self, api_key: str | None = None, app_key: str | None = None):
        """Initialize Datadog executor.

        Args:
            api_key: Datadog API key. If None, reads from DATADOG_API_KEY env var.
            app_key: Datadog application key. If None, reads from
                DATADOG_APP_KEY env var.
        """
        self.api_key = api_key or os.getenv("DATADOG_API_KEY")
        self.app_key = app_key or os.getenv("DATADOG_APP_KEY")

        if not self.api_key:
            raise ValueError(
                "Datadog API key is required. Set DATADOG_API_KEY environment "
                "variable or pass api_key parameter."
            )

        if not self.app_key:
            raise ValueError(
                "Datadog application key is required. Set DATADOG_APP_KEY "
                "environment variable or pass app_key parameter."
            )

        self.base_url = "https://api.datadoghq.com"

    def __call__(self, action: DatadogSearchLogsAction) -> DatadogSearchLogsObservation:
        """Execute Datadog logs search."""
        try:
            # Set default time range if not provided
            if not action.to_time:
                to_time = datetime.utcnow()
            else:
                to_time = datetime.fromisoformat(action.to_time.replace("Z", "+00:00"))

            if not action.from_time:
                from_time = to_time - timedelta(hours=24)
            else:
                from_time = datetime.fromisoformat(
                    action.from_time.replace("Z", "+00:00")
                )

            # Prepare the request
            url = f"{self.base_url}/api/v2/logs/events/search"
            headers = {
                "Content-Type": "application/json",
                "DD-API-KEY": self.api_key,
                "DD-APPLICATION-KEY": self.app_key,
            }

            payload = {
                "filter": {
                    "from": from_time.isoformat(),
                    "to": to_time.isoformat(),
                    "query": action.query,
                },
                "sort": action.sort,
                "page": {"limit": action.limit},
            }

            # Make the API request
            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                return DatadogSearchLogsObservation(query=action.query, error=error_msg)

            data = response.json()
            logs = data.get("data", [])

            # Extract pagination info
            meta = data.get("meta", {})
            page_info = meta.get("page", {})
            next_cursor = page_info.get("after")

            # For total count, we use the length of returned logs
            # Note: Datadog API doesn't always return total count in search results
            total_count = len(logs)

            return DatadogSearchLogsObservation(
                logs=logs,
                total_count=total_count,
                query=action.query,
                next_cursor=next_cursor,
            )

        except requests.exceptions.RequestException as e:
            return DatadogSearchLogsObservation(
                query=action.query, error=f"Request failed: {str(e)}"
            )
        except Exception as e:
            return DatadogSearchLogsObservation(
                query=action.query, error=f"Unexpected error: {str(e)}"
            )


TOOL_DESCRIPTION = """Search and retrieve logs from Datadog using the Logs Search API.

This tool allows you to query Datadog logs using the same search syntax
available in the Datadog UI.

### Authentication
Requires DATADOG_API_KEY and DATADOG_APP_KEY environment variables to be set.

### Query Syntax
Use Datadog's search syntax:
- `status:error` - Find logs with error status
- `service:my-service` - Filter by service name
- `host:my-host` - Filter by hostname
- `"exact phrase"` - Search for exact phrases
- `field:value` - Search by custom fields
- `-(status:info OR status:debug)` - Exclude certain statuses
- `*` - Match all logs

### Time Range
- If no time range is specified, searches the last 24 hours
- Use ISO format for custom ranges: "2024-01-01T00:00:00+00:00"

### Examples
- Find all error logs: `status:error`
- Find specific error in deploy service:
  `service:deploy status:error "no tokens for user"`
- Exclude info/debug logs: `-(status:info OR status:debug)`

### Output
Returns structured log data including timestamp, status, service, host, message,
and other attributes.
"""


datadog_search_logs_tool = Tool(
    name="datadog_search_logs",
    action_type=DatadogSearchLogsAction,
    observation_type=DatadogSearchLogsObservation,
    description=TOOL_DESCRIPTION,
    annotations=ToolAnnotations(
        title="datadog_search_logs",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)


class DatadogTool(Tool[DatadogSearchLogsAction, DatadogSearchLogsObservation]):
    """A Tool subclass for Datadog API operations."""

    @classmethod
    def create(
        cls,
        api_key: str | None = None,
        app_key: str | None = None,
    ) -> "DatadogTool":
        """Initialize DatadogTool with API credentials.

        Args:
            api_key: Datadog API key. If None, reads from DATADOG_API_KEY env var.
            app_key: Datadog application key. If None, reads from
                DATADOG_APP_KEY env var.
        """
        executor = DatadogExecutor(api_key=api_key, app_key=app_key)

        return cls(
            name=datadog_search_logs_tool.name,
            description=TOOL_DESCRIPTION,
            action_type=DatadogSearchLogsAction,
            observation_type=DatadogSearchLogsObservation,
            annotations=datadog_search_logs_tool.annotations,
            executor=executor,
        )
