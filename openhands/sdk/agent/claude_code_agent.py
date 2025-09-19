"""Claude Code Agent implementation using the Claude Code SDK."""

import asyncio
import json
from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field, field_validator

from openhands.sdk.agent.base import AgentBase
from openhands.sdk.conversation import ConversationCallbackType, ConversationState
from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.sdk.event import (
    ActionEvent,
    AgentErrorEvent,
    LLMConvertibleEvent,
    MessageEvent,
    ObservationEvent,
    SystemPromptEvent,
)
from openhands.sdk.llm import Message, TextContent
from openhands.sdk.logger import get_logger
from openhands.sdk.tool import ActionBase, ObservationBase, Tool


if TYPE_CHECKING:
    from claude_code_sdk import (
        AssistantMessage,
        ClaudeCodeOptions,
        ClaudeSDKClient,
        TextBlock,
        ToolResultBlock,
        ToolUseBlock,
        UserMessage,
    )
else:
    try:
        from claude_code_sdk import (
            AssistantMessage,
            ClaudeCodeOptions,
            ClaudeSDKClient,
            TextBlock,
            ToolResultBlock,
            ToolUseBlock,
            UserMessage,
        )
    except ImportError as e:
        raise ImportError(
            "Claude Code SDK is required for ClaudeCodeAgent. "
            "Install it with: pip install claude-code-sdk"
        ) from e


logger = get_logger(__name__)


class ClaudeCodeAgent(AgentBase):
    """Agent implementation using Claude Code SDK under the hood.

    This agent maintains the same API/interface as the standard Agent
    but uses Claude Code SDK for LLM interactions and tool execution.
    """

    claude_options: Optional[dict] = Field(
        default=None,
        description=(
            "Options for Claude Code SDK client (as dict to avoid forward references)"
        ),
    )

    @field_validator("tools", mode="before")
    @classmethod
    def _normalize_tools(cls, v: Any) -> dict[str, "Tool"]:
        """Normalize tools to dict format (same as base Agent)."""
        # Use the same validation logic as the base Agent class
        from openhands.sdk.agent.agent import Agent

        return Agent._normalize_tools(v)

    def _create_claude_client(self) -> ClaudeSDKClient:
        """Create and configure Claude Code SDK client."""
        # Convert OpenHands tools to Claude Code MCP tools
        mcp_tools = []
        tool_names = []

        if isinstance(self.tools, dict):
            for tool_name, tool in self.tools.items():
                # Create MCP tool from OpenHands tool
                mcp_tool = self._convert_tool_to_mcp(tool)
                if mcp_tool:
                    mcp_tools.append(mcp_tool)
                    tool_names.append(f"mcp__openhands__{tool_name}")

        # Create SDK MCP server with converted tools
        if mcp_tools:
            from claude_code_sdk import create_sdk_mcp_server

            mcp_server = create_sdk_mcp_server(
                name="openhands", version="1.0.0", tools=mcp_tools
            )

            # Update claude options with MCP server and allowed tools
            base_options = self.claude_options if self.claude_options else {}
            options = ClaudeCodeOptions(
                mcp_servers={"openhands": mcp_server},
                allowed_tools=tool_names,
                system_prompt=self.system_message,
                **base_options,
            )
        else:
            base_options = self.claude_options if self.claude_options else {}
            options = ClaudeCodeOptions(
                system_prompt=self.system_message, **base_options
            )

        return ClaudeSDKClient(options=options)

    def _convert_tool_to_mcp(self, openhands_tool: Tool) -> Any:
        """Convert an OpenHands tool to an MCP tool function."""
        if not openhands_tool.executor:
            logger.warning(f"Tool {openhands_tool.name} has no executor, skipping")
            return None

        # Create parameter schema from OpenAI tool schema
        openai_schema = openhands_tool.to_openai_tool()
        parameters = openai_schema.get("function", {}).get("parameters", {})

        # Convert JSON schema to Python types for the @tool decorator
        param_types = {}
        if "properties" in parameters:
            for param_name, param_def in parameters["properties"].items():
                param_type = param_def.get("type", "string")
                if param_type == "string":
                    param_types[param_name] = str
                elif param_type == "integer":
                    param_types[param_name] = int
                elif param_type == "boolean":
                    param_types[param_name] = bool
                elif param_type == "array":
                    param_types[param_name] = list
                elif param_type == "object":
                    param_types[param_name] = dict
                else:
                    param_types[param_name] = str  # fallback

        # Create the MCP tool function
        from claude_code_sdk import tool

        @tool(
            openhands_tool.name,
            openhands_tool.description or f"Execute {openhands_tool.name}",
            param_types,
        )
        async def mcp_tool_func(args: dict[str, Any]) -> dict[str, Any]:
            """Execute the OpenHands tool and return results."""
            try:
                # Create action from arguments
                action: ActionBase = openhands_tool.action_type.model_validate(args)

                # Execute the tool
                if openhands_tool.executor is None:
                    raise ValueError(f"Tool {openhands_tool.name} has no executor")
                observation: ObservationBase = openhands_tool.executor(action)

                # Convert observation to MCP result format
                return {
                    "content": [{"type": "text", "text": str(observation.model_dump())}]
                }
            except Exception as e:
                logger.error(f"Error executing tool {openhands_tool.name}: {e}")
                return {"content": [{"type": "text", "text": f"Error: {str(e)}"}]}

        return mcp_tool_func

    def init_state(
        self,
        state: ConversationState,
        on_event: ConversationCallbackType,
    ) -> None:
        """Initialize the conversation state."""
        # Configure bash tools with env provider (same as base Agent)
        self._configure_bash_tools_env_provider(state)

        llm_convertible_messages = [
            event for event in state.events if isinstance(event, LLMConvertibleEvent)
        ]

        if len(llm_convertible_messages) == 0:
            # Prepare system message
            assert isinstance(self.tools, dict)
            event = SystemPromptEvent(
                source="agent",
                system_prompt=TextContent(text=self.system_message),
                tools=[t.to_openai_tool() for t in self.tools.values()],
            )
            on_event(event)

    def _configure_bash_tools_env_provider(self, state: ConversationState) -> None:
        """Configure bash tool with reference to secrets manager."""
        # Same implementation as base Agent
        if not isinstance(self.tools, dict):
            return

        secrets_manager = state.secrets_manager

        def env_for_cmd(cmd: str) -> dict[str, str]:
            try:
                return secrets_manager.get_secrets_as_env_vars(cmd)
            except Exception:
                return {}

        def env_masker(output: str) -> str:
            try:
                return secrets_manager.mask_secrets_in_output(output)
            except Exception:
                return ""

        execute_bash_exists = False
        for tool in self.tools.values():
            if (
                tool.name == "execute_bash"
                and hasattr(tool, "executor")
                and tool.executor is not None
            ):
                # Wire the env provider and env masker for the bash executor
                setattr(tool.executor, "env_provider", env_for_cmd)
                setattr(tool.executor, "env_masker", env_masker)
                execute_bash_exists = True

        if not execute_bash_exists:
            logger.warning("Skipped wiring SecretsManager: missing bash tool")

    def step(
        self,
        state: ConversationState,
        on_event: ConversationCallbackType,
    ) -> None:
        """Take a step in the conversation using Claude Code SDK."""
        # Run the async step in the event loop
        try:
            # Get or create event loop
            try:
                asyncio.get_running_loop()
                # If we're already in an event loop, we need to run in a thread
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, self._async_step(state, on_event)
                    )
                    future.result()
            except RuntimeError:
                # No running loop, we can use asyncio.run directly
                asyncio.run(self._async_step(state, on_event))
        except Exception as e:
            logger.error(f"Error in Claude Code agent step: {e}")
            error_event = AgentErrorEvent(error=str(e))
            on_event(error_event)
            state.agent_status = AgentExecutionStatus.FINISHED

    async def _async_step(
        self,
        state: ConversationState,
        on_event: ConversationCallbackType,
    ) -> None:
        """Async implementation of the step method."""
        # Get the latest user message to send to Claude
        user_messages = [
            event
            for event in reversed(state.events)
            if isinstance(event, MessageEvent) and event.source == "user"
        ]

        if not user_messages:
            logger.warning("No user message found for Claude Code agent step")
            state.agent_status = AgentExecutionStatus.FINISHED
            return

        latest_user_message = user_messages[0]
        user_content = ""

        # Extract text content from the user message
        if latest_user_message.llm_message and latest_user_message.llm_message.content:
            for content in latest_user_message.llm_message.content:
                if isinstance(content, TextContent):
                    user_content += content.text

        if not user_content:
            logger.warning("No text content found in user message")
            state.agent_status = AgentExecutionStatus.FINISHED
            return

        # Create Claude Code client and send query
        async with self._create_claude_client() as client:
            try:
                await client.query(user_content)

                # Process the response
                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        # Convert Claude message to OpenHands events
                        self._process_assistant_message(message, state, on_event)
                    elif isinstance(message, UserMessage):
                        # Handle user messages if needed
                        pass

            except Exception as e:
                logger.error(f"Error querying Claude Code: {e}")
                error_event = AgentErrorEvent(error=str(e))
                on_event(error_event)
                state.agent_status = AgentExecutionStatus.FINISHED

    def _process_assistant_message(
        self,
        claude_message: AssistantMessage,
        state: ConversationState,
        on_event: ConversationCallbackType,
    ) -> None:
        """Process an AssistantMessage from Claude Code and convert to OpenHands events."""  # noqa: E501
        # Check if this is a tool use or a regular message
        has_tool_use = any(
            isinstance(block, ToolUseBlock) for block in claude_message.content
        )

        if has_tool_use:
            # Process tool use blocks
            for block in claude_message.content:
                if isinstance(block, ToolUseBlock):
                    self._process_tool_use_block(block, state, on_event)
                elif isinstance(block, ToolResultBlock):
                    self._process_tool_result_block(block, state, on_event)
        else:
            # Regular assistant message
            text_content = []
            for block in claude_message.content:
                if isinstance(block, TextBlock):
                    text_content.append(TextContent(text=block.text))

            if text_content:
                message = Message(role="assistant", content=text_content)
                msg_event = MessageEvent(source="agent", llm_message=message)
                on_event(msg_event)

            state.agent_status = AgentExecutionStatus.FINISHED

    def _process_tool_use_block(
        self,
        tool_block: ToolUseBlock,
        state: ConversationState,
        on_event: ConversationCallbackType,
    ) -> None:
        """Process a tool use block from Claude Code."""
        # Extract tool name (remove MCP prefix if present)
        tool_name = tool_block.name
        if tool_name.startswith("mcp__openhands__"):
            tool_name = tool_name[len("mcp__openhands__") :]

        # Find the corresponding OpenHands tool
        assert isinstance(self.tools, dict)
        tool = self.tools.get(tool_name)
        if not tool:
            error_msg = f"Tool '{tool_name}' not found"
            logger.error(error_msg)
            error_event = AgentErrorEvent(error=error_msg)
            on_event(error_event)
            return

        try:
            # Create action from tool input
            action: ActionBase = tool.action_type.model_validate(tool_block.input)

            # Create a mock tool call for compatibility
            from litellm import ChatCompletionMessageToolCall

            mock_tool_call = ChatCompletionMessageToolCall(
                id=tool_block.id,
                type="function",
                function={"name": tool_name, "arguments": json.dumps(tool_block.input)},
            )

            # Create action event
            action_event = ActionEvent(
                action=action,
                thought=[],  # No thought content from Claude Code
                tool_name=tool_name,
                tool_call_id=tool_block.id,
                tool_call=mock_tool_call,
                llm_response_id="claude_code_response",  # Mock response ID
            )
            on_event(action_event)

            # Execute the tool
            if tool.executor:
                observation: ObservationBase = tool.executor(action)

                # Create observation event
                obs_event = ObservationEvent(
                    observation=observation,
                    action_id=action_event.id,
                    tool_name=tool_name,
                    tool_call_id=tool_block.id,
                )
                on_event(obs_event)
            else:
                error_msg = f"Tool '{tool_name}' has no executor"
                logger.error(error_msg)
                error_event = AgentErrorEvent(error=error_msg)
                on_event(error_event)

        except Exception as e:
            error_msg = f"Error processing tool use: {e}"
            logger.error(error_msg)
            error_event = AgentErrorEvent(error=error_msg)
            on_event(error_event)

    def _process_tool_result_block(
        self,
        result_block: ToolResultBlock,
        state: ConversationState,
        on_event: ConversationCallbackType,
    ) -> None:
        """Process a tool result block from Claude Code."""
        # Tool results are typically handled by the MCP system
        # We may not need to do anything special here
        pass


# Rebuild the model to resolve forward references from ClaudeCodeOptions
try:
    # Import the MCP server types to ensure they're available

    ClaudeCodeAgent.model_rebuild()
except Exception:
    # If model_rebuild fails, it's likely due to missing dependencies
    # This is expected when claude-code-sdk is not available
    pass
