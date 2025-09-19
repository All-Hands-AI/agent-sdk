"""Utility functions for MCP integration."""

import re
from typing import Any

import mcp.types
from litellm import ChatCompletionToolParam
from pydantic import Field, ValidationError

from openhands.sdk.llm import TextContent
from openhands.sdk.logger import get_logger
from openhands.sdk.mcp.client import MCPClient
from openhands.sdk.mcp.definition import MCPToolAction, MCPToolObservation
from openhands.sdk.tool import (
    ActionBase,
    ObservationBase,
    ToolAnnotations,
    ToolExecutor,
)
from openhands.sdk.tool.tool import ToolBase


logger = get_logger(__name__)


# NOTE: We don't define MCPToolAction because it
# will be a pydantic BaseModel dynamically created from the MCP tool schema.
# It will be available as "tool.action_type".


def to_camel_case(s: str) -> str:
    parts = re.split(r"[_\-\s]+", s)
    return "".join(word.capitalize() for word in parts if word)


class MCPToolExecutor(ToolExecutor):
    """Executor for MCP tools."""

    def __init__(self, tool_name: str, client: MCPClient):
        self.tool_name = tool_name
        self.client = client

    async def call_tool(self, action: MCPToolAction) -> MCPToolObservation:
        async with self.client:
            assert self.client.is_connected(), "MCP client is not connected."
            try:
                logger.debug(
                    f"Calling MCP tool {self.tool_name} "
                    f"with args: {action.model_dump()}"
                )
                result: mcp.types.CallToolResult = await self.client.call_tool_mcp(
                    name=self.tool_name, arguments=action.to_mcp_arguments()
                )
                return MCPToolObservation.from_call_tool_result(
                    tool_name=self.tool_name, result=result
                )
            except Exception as e:
                error_msg = f"Error calling MCP tool {self.tool_name}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return MCPToolObservation(
                    content=[TextContent(text=error_msg)],
                    is_error=True,
                    tool_name=self.tool_name,
                )

    def __call__(self, action: MCPToolAction) -> MCPToolObservation:
        """Execute an MCP tool call."""
        return self.client.call_async_from_sync(
            self.call_tool, action=action, timeout=300
        )


_mcp_dynamic_action_type: dict[mcp.types.Tool, type[ActionBase]] = {}


def _create_mcp_action_type(name: str, action_type: mcp.types.Tool) -> type[ActionBase]:
    """Dynamically create a Pydantic model for MCP tool action from schema.

    We create from "ActionBase" instead of "MCPToolAction" because
    MCPToolAction has a "data" field that wraps all dynamic fields,
    while ActionBase directly defines the fields.

    .from_mcp_schema simply defines a new Pydantic model class
    that inherits from the given base class.

    We may want to use the returned class to convert fields definitions
    to openai tool schema. If we use MCPToolAction as base,
    the generated schema will have an additional "data" field,
    which is not what we want.
    """

    mcp_action_type = _mcp_dynamic_action_type.get(action_type)
    if mcp_action_type:
        return mcp_action_type

    mcp_action_type = ActionBase.from_mcp_schema(
        f"{to_camel_case(name)}Action", action_type.inputSchema
    )
    _mcp_dynamic_action_type[action_type] = mcp_action_type
    return mcp_action_type


class MCPTool(ToolBase[MCPToolAction, MCPToolObservation]):
    """MCP Tool that wraps an MCP client and provides tool functionality."""

    mcp_tool: mcp.types.Tool = Field(description="The MCP tool definition.")

    def __call__(self, action: MCPToolAction) -> ObservationBase:
        """Execute the tool action using the MCP client.

        We dynamically create a new MCPToolAction class with
        the tool's input schema to validate the action.

        Args:
            action: The action to execute.

        Returns:
            The observation result from executing the action.
        """
        mcp_action_type = _create_mcp_action_type(self.name, self.mcp_tool)
        mcp_action_type.model_validate(action.data)

        return super().__call__(action)

    def action_from_arguments(self, arguments: dict[str, Any]) -> MCPToolAction:
        """Create an MCPToolAction from parsed arguments.

        This method puts the arguments into the .data field
        of the MCPToolAction, avoiding the need for dynamic class creation
        during action instantiation.

        Args:
            arguments: The parsed arguments from the tool call.

        Returns:
            The MCPToolAction instance with data populated from the arguments.
        """
        return MCPToolAction(data=arguments)

    @classmethod
    def create(
        cls,
        mcp_tool: mcp.types.Tool,
        mcp_client: MCPClient,
    ) -> "MCPTool":
        try:
            annotations = (
                ToolAnnotations.model_validate(
                    mcp_tool.annotations.model_dump(exclude_none=True)
                )
                if mcp_tool.annotations
                else None
            )

            return cls(
                name=mcp_tool.name,
                description=mcp_tool.description or "No description provided",
                action_type=MCPToolAction,
                observation_type=MCPToolObservation,
                annotations=annotations,
                meta=mcp_tool.meta,
                executor=MCPToolExecutor(tool_name=mcp_tool.name, client=mcp_client),
                # pass-through fields (enabled by **extra in Tool.create)
                mcp_tool=mcp_tool,
            )
        except ValidationError as e:
            logger.error(
                f"Validation error creating MCPTool for {mcp_tool.name}: "
                f"{e.json(indent=2)}",
                exc_info=True,
            )
            raise e

    def to_mcp_tool(
        self,
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if input_schema is not None or output_schema is not None:
            raise ValueError("MCPTool.to_mcp_tool does not support overriding schemas")

        return super().to_mcp_tool(
            input_schema=self.mcp_tool.inputSchema,
            output_schema=self.observation_type.to_mcp_schema()
            if self.observation_type
            else None,
        )

    def to_openai_tool(
        self,
        add_security_risk_prediction: bool = False,
        action_type: type[ActionBase] | None = None,
    ) -> ChatCompletionToolParam:
        """Convert a Tool to an OpenAI tool.

        For MCP, we dynamically create the action_type (type: ActionBase)
        from the MCP tool input schema, and pass it to the parent method.
        It will use the .model_fields from this pydantic model to
        generate the OpenAI-compatible tool schema.

        Args:
            add_security_risk_prediction: Whether to add a `security_risk` field
                to the action schema for LLM to predict. This is useful for
                tools that may have safety risks, so the LLM can reason about
                the risk level before calling the tool.
        """
        if action_type is not None:
            raise ValueError(
                "MCPTool.to_openai_tool does not support overriding action_type"
            )

        mcp_action_type = _create_mcp_action_type(self.name, self.mcp_tool)
        return super().to_openai_tool(
            add_security_risk_prediction=add_security_risk_prediction,
            action_type=mcp_action_type,
        )
