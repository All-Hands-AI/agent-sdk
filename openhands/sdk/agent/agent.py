import json
from typing import cast

from litellm.types.utils import (
    ChatCompletionMessageToolCall,
    Choices,
    Message as LiteLLMMessage,
)
from pydantic import ValidationError

from openhands.sdk.agent.base import AgentBase
from openhands.sdk.context.view import View
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
from openhands.sdk.event.condenser import Condensation
from openhands.sdk.event.utils import get_unmatched_actions
from openhands.sdk.llm import (
    Message,
    MetricsSnapshot,
    TextContent,
    get_llm_metadata,
)
from openhands.sdk.logger import get_logger
from openhands.sdk.security import risk
from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer
from openhands.sdk.tool import (
    ActionBase,
    FinishTool,
    ObservationBase,
)
from openhands.sdk.tool.builtins import FinishAction


logger = get_logger(__name__)


class Agent(AgentBase):
    @property
    def _add_security_risk_prediction(self) -> bool:
        return isinstance(self.security_analyzer, LLMSecurityAnalyzer)

    def _configure_bash_tools_env_provider(self, state: ConversationState) -> None:
        """
        Configure bash tool with reference to secrets manager.
        Updated secrets automatically propagate.
        """

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
        for tool in self.tools_map.values():
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

    def init_state(
        self,
        state: ConversationState,
        on_event: ConversationCallbackType,
    ) -> None:
        super().init_state(state, on_event=on_event)
        # TODO(openhands): we should add test to test this init_state will actually
        # modify state in-place

        # Configure bash tools with env provider
        self._configure_bash_tools_env_provider(state)

        llm_convertible_messages = [
            event for event in state.events if isinstance(event, LLMConvertibleEvent)
        ]
        if len(llm_convertible_messages) == 0:
            # Prepare system message
            event = SystemPromptEvent(
                source="agent",
                system_prompt=TextContent(text=self.system_message),
                tools=[
                    t.to_openai_tool(
                        add_security_risk_prediction=self._add_security_risk_prediction
                    )
                    for t in self.tools_map.values()
                ],
            )
            on_event(event)

    def _execute_actions(
        self,
        state: ConversationState,
        action_events: list[ActionEvent],
        on_event: ConversationCallbackType,
    ):
        for action_event in action_events:
            self._execute_action_events(state, action_event, on_event=on_event)

    def step(
        self,
        state: ConversationState,
        on_event: ConversationCallbackType,
    ) -> None:
        # Check for pending actions (implicit confirmation)
        # and execute them before sampling new actions.
        pending_actions = get_unmatched_actions(state.events)
        if pending_actions:
            logger.info(
                "Confirmation mode: Executing %d pending action(s)",
                len(pending_actions),
            )
            self._execute_actions(state, pending_actions, on_event)
            return

        # If a condenser is registered with the agent, we need to give it an
        # opportunity to transform the events. This will either produce a list
        # of events, exactly as expected, or a new condensation that needs to be
        # processed before the agent can sample another action.
        if self.condenser is not None:
            view = View.from_events(state.events)
            condensation_result = self.condenser.condense(view)

            match condensation_result:
                case View():
                    llm_convertible_events = condensation_result.events

                case Condensation():
                    on_event(condensation_result)
                    return None

        else:
            llm_convertible_events = cast(
                list[LLMConvertibleEvent],
                [e for e in state.events if isinstance(e, LLMConvertibleEvent)],
            )

        # Get LLM Response (Action)
        _messages = LLMConvertibleEvent.events_to_messages(llm_convertible_events)
        logger.debug(
            "Sending messages to LLM: "
            f"{json.dumps([m.model_dump() for m in _messages], indent=2)}"
        )
        response = self.llm.completion(
            messages=_messages,
            tools=list(self.tools_map.values()),
            add_security_risk_prediction=self._add_security_risk_prediction,
            extra_body={
                "metadata": get_llm_metadata(
                    model_name=self.llm.model, agent_name=self.name
                )
            },
        )
        assert len(response.choices) == 1 and isinstance(response.choices[0], Choices)
        llm_message: LiteLLMMessage = response.choices[0].message  # type: ignore
        message = Message.from_litellm_message(llm_message)

        assert self.llm.metrics is not None, "LLM metrics should not be None"
        metrics = self.llm.metrics.get_snapshot()  # take a snapshot of metrics

        if message.tool_calls and len(message.tool_calls) > 0:
            tool_call: ChatCompletionMessageToolCall
            if any(tc.type != "function" for tc in message.tool_calls):
                logger.warning(
                    "LLM returned tool calls but some are not of type 'function' - "
                    "ignoring those"
                )

            tool_calls = [
                tool_call
                for tool_call in message.tool_calls
                if tool_call.type == "function"
            ]
            assert len(tool_calls) > 0, (
                "LLM returned tool calls but none are of type 'function'"
            )
            if not all(isinstance(c, TextContent) for c in message.content):
                logger.warning(
                    "LLM returned tool calls but message content is not all "
                    "TextContent - ignoring non-text content"
                )

            # Generate unique batch ID for this LLM response
            thought_content = [c for c in message.content if isinstance(c, TextContent)]

            action_events: list[ActionEvent] = []
            for i, tool_call in enumerate(tool_calls):
                action_event = self._get_action_events(
                    state,
                    tool_call,
                    llm_response_id=response.id,
                    on_event=on_event,
                    thought=thought_content
                    if i == 0
                    else [],  # Only first gets thought
                    metrics=metrics if i == len(tool_calls) - 1 else None,
                    # Only first gets reasoning content
                    reasoning_content=message.reasoning_content if i == 0 else None,
                )
                if action_event is None:
                    continue
                action_events.append(action_event)

            # Handle confirmation mode - exit early if actions need confirmation
            if self._requires_user_confirmation(state, action_events):
                return

            if action_events:
                self._execute_actions(state, action_events, on_event)

        else:
            logger.info("LLM produced a message response - awaits user input")
            state.agent_status = AgentExecutionStatus.FINISHED
            msg_event = MessageEvent(
                source="agent",
                llm_message=message,
                metrics=metrics,
            )
            on_event(msg_event)

    def _requires_user_confirmation(
        self, state: ConversationState, action_events: list[ActionEvent]
    ) -> bool:
        """
        Decide whether user confirmation is needed to proceed.

        Rules:
            1. Confirmation mode is enabled
            2. Every action requires confirmation
            3. A single `FinishAction` never requires confirmation
        """
        # A single `FinishAction` never requires confirmation
        if len(action_events) == 1 and isinstance(
            action_events[0].action, FinishAction
        ):
            return False

        # If there are no actions there is nothing to confirm
        if len(action_events) == 0:
            return False

        # If a security analyzer is registered, use it to check the action events and
        # see if confirmation is needed.
        if self.security_analyzer is not None:
            risks = self.security_analyzer.analyze_pending_actions(action_events)
            for _, risk in risks:
                if self.security_analyzer.should_require_confirmation(
                    risk, state.confirmation_mode
                ):
                    state.agent_status = AgentExecutionStatus.WAITING_FOR_CONFIRMATION
                    return True
            # If the security analyzer doesn't tell us to stop, we shouldn't stop, even
            # if the confirmation mode is on.
            return False

        # If confirmation mode is disabled, no confirmation is needed
        if not state.confirmation_mode:
            return False

        state.agent_status = AgentExecutionStatus.WAITING_FOR_CONFIRMATION
        return True

    def _get_action_events(
        self,
        state: ConversationState,
        tool_call: ChatCompletionMessageToolCall,
        llm_response_id: str,
        on_event: ConversationCallbackType,
        thought: list[TextContent] = [],
        metrics: MetricsSnapshot | None = None,
        reasoning_content: str | None = None,
    ) -> ActionEvent | None:
        """Handle tool calls from the LLM.

        NOTE: state will be mutated in-place.
        """
        assert tool_call.type == "function"
        tool_name = tool_call.function.name
        assert tool_name is not None, "Tool call must have a name"
        tool = self.tools_map.get(tool_name, None)
        # Handle non-existing tools
        if tool is None:
            available = list(self.tools_map.keys())
            err = f"Tool '{tool_name}' not found. Available: {available}"
            logger.error(err)
            event = AgentErrorEvent(
                error=err,
                metrics=metrics,
            )
            on_event(event)
            state.agent_status = AgentExecutionStatus.FINISHED
            return

        # Validate arguments
        security_risk: risk.SecurityRisk = risk.SecurityRisk.UNKNOWN
        try:
            arguments = json.loads(tool_call.function.arguments)

            # if the tool has a security_risk field (when security analyzer = LLM),
            # pop it out as it's not part of the tool's action schema
            if (_predicted_risk := arguments.pop("security_risk", None)) is not None:
                if not isinstance(self.security_analyzer, LLMSecurityAnalyzer):
                    raise RuntimeError(
                        "LLM provided a security_risk but no security analyzer is "
                        "configured - THIS SHOULD NOT HAPPEN!"
                    )
                try:
                    security_risk = risk.SecurityRisk(_predicted_risk)
                except ValueError:
                    logger.warning(
                        f"Invalid security_risk value from LLM: {_predicted_risk}"
                    )

            # Arguments we passed in should not contains `security_risk`
            # as a field
            action: ActionBase = tool.action_from_arguments(arguments)
        except (json.JSONDecodeError, ValidationError) as e:
            err = (
                f"Error validating args {tool_call.function.arguments} for tool "
                f"'{tool.name}': {e}"
            )
            event = AgentErrorEvent(
                error=err,
                metrics=metrics,
            )
            on_event(event)
            return

        # Create one ActionEvent per action
        action_event = ActionEvent(
            action=action,
            thought=thought,
            reasoning_content=reasoning_content,
            tool_name=tool.name,
            tool_call_id=tool_call.id,
            tool_call=tool_call,
            llm_response_id=llm_response_id,
            metrics=metrics,
            security_risk=security_risk,
        )
        on_event(action_event)
        return action_event

    def _execute_action_events(
        self,
        state: ConversationState,
        action_event: ActionEvent,
        on_event: ConversationCallbackType,
    ):
        """Execute action events and update the conversation state.

        It will call the tool's executor and update the state & call callback fn
        with the observation.
        """
        tool = self.tools_map.get(action_event.tool_name, None)
        if tool is None:
            raise RuntimeError(
                f"Tool '{action_event.tool_name}' not found. This should not happen "
                "as it was checked earlier."
            )

        # Execute actions!
        observation: ObservationBase = tool(action_event.action)
        assert isinstance(observation, ObservationBase), (
            f"Tool '{tool.name}' executor must return an ObservationBase"
        )

        obs_event = ObservationEvent(
            observation=observation,
            action_id=action_event.id,
            tool_name=tool.name,
            tool_call_id=action_event.tool_call.id,
        )
        on_event(obs_event)

        # Set conversation state
        if tool.name == FinishTool.name:
            state.agent_status = AgentExecutionStatus.FINISHED
        return obs_event
