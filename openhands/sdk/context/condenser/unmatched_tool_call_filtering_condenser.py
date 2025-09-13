from openhands.sdk.context.condenser.base import CondenserBase
from openhands.sdk.context.view import View
from openhands.sdk.event import LLMConvertibleEvent
from openhands.sdk.event.condenser import Condensation
from openhands.sdk.event.llm_convertible import ActionEvent, ObservationEvent


class UnmatchedToolCallFilteringCondenser(CondenserBase):
    """A condenser that filters out tool-call events that don't have a matching pair."""

    def _get_action_tool_call_ids(self, events: list[LLMConvertibleEvent]) -> set[str]:
        """Collect tool_call_ids from ActionEvents."""
        return {
            event.tool_call_id
            for event in events
            if isinstance(event, ActionEvent) and event.tool_call_id
        }

    def _get_observation_tool_call_ids(
        self, events: list[LLMConvertibleEvent]
    ) -> set[str]:
        """Collect tool_call_ids from ObservationEvents."""
        return {
            event.tool_call_id
            for event in events
            if isinstance(event, ObservationEvent) and event.tool_call_id
        }

    def _should_keep_event(
        self,
        event: LLMConvertibleEvent,
        action_tool_call_ids: set[str],
        observation_tool_call_ids: set[str],
    ) -> bool:
        """Determine if an event should be kept based on tool call matching."""
        if isinstance(event, ObservationEvent):
            # Keep ObservationEvents only if they have a matching ActionEvent
            return event.tool_call_id in action_tool_call_ids

        elif isinstance(event, ActionEvent):
            # Keep ActionEvents only if they have a matching ObservationEvent
            return event.tool_call_id in observation_tool_call_ids

        else:
            # Keep all other event types
            return True

    def condense(self, view: View) -> View | Condensation:
        action_tool_call_ids = self._get_action_tool_call_ids(view.events)
        observation_tool_call_ids = self._get_observation_tool_call_ids(view.events)

        return View(
            events=[
                event
                for event in view.events
                if self._should_keep_event(
                    event, action_tool_call_ids, observation_tool_call_ids
                )
            ]
        )
