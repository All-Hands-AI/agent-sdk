import json
import os
import uuid

from litellm.types.utils import (
    ChatCompletionMessageToolCall,
    Choices,
    Message as LiteLLMMessage,
    ModelResponse,
)
from pydantic import ValidationError

from openhands.core.context import EnvContext, PromptManager
from openhands.core.conversation import ConversationCallbackType, ConversationState
from openhands.core.event import ActionEvent, AgentErrorEvent, MessageEvent, ObservationEvent, SystemPromptEvent
from openhands.core.llm import LLM, Message, TextContent, get_llm_metadata
from openhands.core.logger import get_logger
from openhands.core.tool import BUILT_IN_TOOLS, ActionBase, FinishTool, ObservationBase, Tool

from ..base import AgentBase


logger = get_logger(__name__)



class CodeActAgent(AgentBase):
    def __init__(
        self,
        llm: LLM,
        tools: list[Tool],
        env_context: EnvContext | None = None,
        system_prompt_filename: str = "system_prompt.j2",
        cli_mode: bool = True,
    ) -> None:
        for tool in BUILT_IN_TOOLS:
            assert tool not in tools, f"{tool} is automatically included and should not be provided."
        super().__init__(llm=llm, tools=tools + BUILT_IN_TOOLS, env_context=env_context)
        self.prompt_manager = PromptManager(
            prompt_dir=os.path.join(os.path.dirname(__file__), "prompts"),
            system_prompt_filename=system_prompt_filename,
        )
        self.system_message: TextContent = self.prompt_manager.get_system_message(cli_mode=cli_mode)
        self.max_iterations: int = 10

    def init_state(
        self,
        state: ConversationState,
        on_event: ConversationCallbackType,
    ) -> None:
        # TODO(openhands): we should add test to test this init_state will actually modify state in-place
        messages = [e.to_llm_message() for e in state.events]
        if len(messages) == 0:
            # Prepare system message
            event = SystemPromptEvent(
                source="agent",
                system_prompt=self.system_message,
                tools=[t.to_openai_tool() for t in self.tools.values()]
            )
            # TODO: maybe we should combine this into on_event?
            state.events.append(event)
            on_event(event)

    def step(
        self,
        state: ConversationState,
        on_event: ConversationCallbackType,
    ) -> None:
        
        # Get LLM Response (Action)
        from typing import cast

        from openhands.core.event.base import LLMConvertibleEvent
        llm_convertible_events = cast(list[LLMConvertibleEvent], state.events)
        _messages = self.llm.format_messages_for_llm(
            LLMConvertibleEvent.events_to_messages(llm_convertible_events)
        )
        logger.debug(f"Sending messages to LLM: {json.dumps(_messages, indent=2)}")
        response: ModelResponse = self.llm.completion(
            messages=_messages,
            tools=[tool.to_openai_tool() for tool in self.tools.values()],
            extra_body={"metadata": get_llm_metadata(model_name=self.llm.config.model, agent_name=self.name)},
        )
        assert len(response.choices) == 1 and isinstance(response.choices[0], Choices)
        llm_message: LiteLLMMessage = response.choices[0].message  # type: ignore
        message = Message.from_litellm_message(llm_message)

        if message.tool_calls and len(message.tool_calls) > 0:
            tool_call: ChatCompletionMessageToolCall
            if any(tc.type != "function" for tc in message.tool_calls):
                logger.warning("LLM returned tool calls but some are not of type 'function' - ignoring those")

            tool_calls = [tool_call for tool_call in message.tool_calls if tool_call.type == "function"]
            assert len(tool_calls) > 0, "LLM returned tool calls but none are of type 'function'"
            if not all(isinstance(c, TextContent) for c in message.content):
                logger.warning("LLM returned tool calls but message content is not all TextContent - ignoring non-text content")
            
            # Generate unique batch ID for this LLM response
            batch_id = str(uuid.uuid4())
            thought_content = [c for c in message.content if isinstance(c, TextContent)]
            
            action_events = []
            obs_events = []
            
            for i, tool_call in enumerate(tool_calls):
                ret = self._handle_tool_call(tool_call, state, on_event)
                if ret is None:
                    continue
                tool_name, action, observation = ret
                
                # Create one ActionEvent per action - clean!
                action_event = ActionEvent(
                    action=action,
                    thought=thought_content if i == 0 else [],  # Only first gets thought
                    tool_call_id=tool_call.id,
                    llm_batch_id=batch_id
                )
                action_events.append(action_event)
                
                obs_event = ObservationEvent(
                    observation=observation,
                    action_id=action_event.id,
                    tool_name=tool_name,
                    tool_call_id=tool_call.id
                )
                obs_events.append(obs_event)

            # Add all events to state
            state.events.extend(action_events)
            state.events.extend(obs_events)
            for event in action_events + obs_events:
                on_event(event)
        else:
            logger.info("LLM produced a message response - awaits user input")
            state.agent_finished = True
            msg_event = MessageEvent(
                source="agent",
                llm_message=message
            )
            state.events.append(msg_event)
            on_event(msg_event)

    def _handle_tool_call(
        self,
        tool_call: ChatCompletionMessageToolCall,
        state: ConversationState,
        on_event: ConversationCallbackType,
    ) -> tuple[str, ActionBase, ObservationBase] | None:
        """Handle tool calls from the LLM.
        
        NOTE: state will be mutated in-place.
        """
        assert tool_call.type == "function"
        tool_name = tool_call.function.name
        assert tool_name is not None, "Tool call must have a name"
        tool = self.tools.get(tool_name, None)
        # Handle non-existing tools
        if tool is None:
            err = f"Tool '{tool_name}' not found. Available: {list(self.tools.keys())}"
            logger.error(err)
            event = AgentErrorEvent(error=err)
            state.events.append(event)
            on_event(event)
            state.agent_finished = True
            return

        # Validate arguments
        try:
            action: ActionBase = tool.action_type.model_validate(json.loads(tool_call.function.arguments))
        except (json.JSONDecodeError, ValidationError) as e:
            err = f"Error validating args {tool_call.function.arguments} for tool '{tool.name}': {e}"
            event = AgentErrorEvent(error=err)
            state.events.append(event)
            on_event(event)
            return
        # Execute actions!
        if tool.executor is None:
            raise RuntimeError(f"Tool '{tool.name}' has no executor")
        observation: ObservationBase = tool.executor(action)
        assert isinstance(observation, ObservationBase), f"Tool '{tool.name}' executor must return an ObservationBase"

        # Set conversation state
        if tool.name == FinishTool.name:
            state.agent_finished = True

        return (tool_name, action, observation)
