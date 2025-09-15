from unittest.mock import create_autospec

from openhands.sdk.context.condenser.base import CondenserBase
from openhands.sdk.context.view import View
from openhands.sdk.event.condenser import Condensation
from openhands.sdk.event.llm_convertible import (
    ActionEvent,
    MessageEvent,
    ObservationEvent,
)


class TestCondenserBase(CondenserBase):
    """Concrete implementation of CondenserBase for testing."""

    def condense(self, view: View) -> View | Condensation:
        """Simple implementation that returns the view unchanged."""
        return view


def test_filter_unmatched_tool_calls_empty_list() -> None:
    """Test filter_unmatched_tool_calls with empty event list."""
    condenser = TestCondenserBase()
    result = condenser.filter_unmatched_tool_calls([])
    assert result == []


def test_filter_unmatched_tool_calls_no_tool_events() -> None:
    """Test filter_unmatched_tool_calls with no tool events."""
    # Create mock non-tool events
    message_event_1 = create_autospec(MessageEvent, instance=True)
    message_event_2 = create_autospec(MessageEvent, instance=True)

    events = [message_event_1, message_event_2]
    condenser = TestCondenserBase()
    result = condenser.filter_unmatched_tool_calls(events)  # type: ignore

    # All non-tool events should be kept
    assert len(result) == 2
    assert message_event_1 in result
    assert message_event_2 in result


def test_filter_unmatched_tool_calls_matched_pairs() -> None:
    """Test filter_unmatched_tool_calls with matched tool call pairs."""
    # Create mock events
    message_event = create_autospec(MessageEvent, instance=True)

    # Matched pair 1
    action_event_1 = create_autospec(ActionEvent, instance=True)
    action_event_1.tool_call_id = "call_1"

    observation_event_1 = create_autospec(ObservationEvent, instance=True)
    observation_event_1.tool_call_id = "call_1"

    # Matched pair 2
    action_event_2 = create_autospec(ActionEvent, instance=True)
    action_event_2.tool_call_id = "call_2"

    observation_event_2 = create_autospec(ObservationEvent, instance=True)
    observation_event_2.tool_call_id = "call_2"

    events = [
        message_event,
        action_event_1,
        observation_event_1,
        action_event_2,
        observation_event_2,
    ]

    condenser = TestCondenserBase()
    result = condenser.filter_unmatched_tool_calls(events)  # type: ignore

    # All events should be kept (all tool calls are matched)
    assert len(result) == 5
    assert message_event in result
    assert action_event_1 in result
    assert observation_event_1 in result
    assert action_event_2 in result
    assert observation_event_2 in result


def test_filter_unmatched_tool_calls_unmatched_action() -> None:
    """Test filter_unmatched_tool_calls with unmatched ActionEvent."""
    # Create mock events
    message_event = create_autospec(MessageEvent, instance=True)

    # Matched pair
    action_event_matched = create_autospec(ActionEvent, instance=True)
    action_event_matched.tool_call_id = "call_1"

    observation_event_matched = create_autospec(ObservationEvent, instance=True)
    observation_event_matched.tool_call_id = "call_1"

    # Unmatched ActionEvent
    action_event_unmatched = create_autospec(ActionEvent, instance=True)
    action_event_unmatched.tool_call_id = "call_2"

    events = [
        message_event,
        action_event_matched,
        observation_event_matched,
        action_event_unmatched,
    ]

    condenser = TestCondenserBase()
    result = condenser.filter_unmatched_tool_calls(events)  # type: ignore

    # Should keep: message_event, matched pair
    # Should filter out: unmatched ActionEvent
    assert len(result) == 3
    assert message_event in result
    assert action_event_matched in result
    assert observation_event_matched in result
    assert action_event_unmatched not in result


def test_filter_unmatched_tool_calls_unmatched_observation() -> None:
    """Test filter_unmatched_tool_calls with unmatched ObservationEvent."""
    # Create mock events
    message_event = create_autospec(MessageEvent, instance=True)

    # Matched pair
    action_event_matched = create_autospec(ActionEvent, instance=True)
    action_event_matched.tool_call_id = "call_1"

    observation_event_matched = create_autospec(ObservationEvent, instance=True)
    observation_event_matched.tool_call_id = "call_1"

    # Unmatched ObservationEvent
    observation_event_unmatched = create_autospec(ObservationEvent, instance=True)
    observation_event_unmatched.tool_call_id = "call_2"

    events = [
        message_event,
        action_event_matched,
        observation_event_matched,
        observation_event_unmatched,
    ]

    condenser = TestCondenserBase()
    result = condenser.filter_unmatched_tool_calls(events)  # type: ignore

    # Should keep: message_event, matched pair
    # Should filter out: unmatched ObservationEvent
    assert len(result) == 3
    assert message_event in result
    assert action_event_matched in result
    assert observation_event_matched in result
    assert observation_event_unmatched not in result


def test_filter_unmatched_tool_calls_mixed_scenario() -> None:
    """Test filter_unmatched_tool_calls with complex mixed scenario."""
    # Create mock events
    message_event_1 = create_autospec(MessageEvent, instance=True)
    message_event_2 = create_autospec(MessageEvent, instance=True)

    # Matched pair 1
    action_event_1 = create_autospec(ActionEvent, instance=True)
    action_event_1.tool_call_id = "call_1"

    observation_event_1 = create_autospec(ObservationEvent, instance=True)
    observation_event_1.tool_call_id = "call_1"

    # Unmatched ActionEvent
    action_event_unmatched = create_autospec(ActionEvent, instance=True)
    action_event_unmatched.tool_call_id = "call_2"

    # Unmatched ObservationEvent
    observation_event_unmatched = create_autospec(ObservationEvent, instance=True)
    observation_event_unmatched.tool_call_id = "call_3"

    # Matched pair 2
    action_event_2 = create_autospec(ActionEvent, instance=True)
    action_event_2.tool_call_id = "call_4"

    observation_event_2 = create_autospec(ObservationEvent, instance=True)
    observation_event_2.tool_call_id = "call_4"

    events = [
        message_event_1,
        action_event_1,
        observation_event_1,
        action_event_unmatched,
        observation_event_unmatched,
        message_event_2,
        action_event_2,
        observation_event_2,
    ]

    condenser = TestCondenserBase()
    result = condenser.filter_unmatched_tool_calls(events)  # type: ignore

    # Should keep: message events and matched pairs
    # Should filter out: unmatched action and observation events
    assert len(result) == 6
    assert message_event_1 in result
    assert message_event_2 in result
    assert action_event_1 in result
    assert observation_event_1 in result
    assert action_event_2 in result
    assert observation_event_2 in result
    assert action_event_unmatched not in result
    assert observation_event_unmatched not in result


def test_filter_unmatched_tool_calls_none_tool_call_id() -> None:
    """Test filter_unmatched_tool_calls with None tool_call_id."""
    # Create mock events with None tool_call_id
    action_event_none = create_autospec(ActionEvent, instance=True)
    action_event_none.tool_call_id = None

    observation_event_none = create_autospec(ObservationEvent, instance=True)
    observation_event_none.tool_call_id = None

    # Valid matched pair
    action_event_valid = create_autospec(ActionEvent, instance=True)
    action_event_valid.tool_call_id = "call_1"

    observation_event_valid = create_autospec(ObservationEvent, instance=True)
    observation_event_valid.tool_call_id = "call_1"

    events = [
        action_event_none,
        observation_event_none,
        action_event_valid,
        observation_event_valid,
    ]

    condenser = TestCondenserBase()
    result = condenser.filter_unmatched_tool_calls(events)  # type: ignore

    # Should keep only the valid matched pair
    # Events with None tool_call_id should be filtered out
    assert len(result) == 2
    assert action_event_valid in result
    assert observation_event_valid in result
    assert action_event_none not in result
    assert observation_event_none not in result


def test_get_action_tool_call_ids() -> None:
    """Test _get_action_tool_call_ids helper method."""
    condenser = TestCondenserBase()

    # Create mock events
    message_event = create_autospec(MessageEvent, instance=True)

    action_event_1 = create_autospec(ActionEvent, instance=True)
    action_event_1.tool_call_id = "call_1"

    action_event_2 = create_autospec(ActionEvent, instance=True)
    action_event_2.tool_call_id = "call_2"

    action_event_none = create_autospec(ActionEvent, instance=True)
    action_event_none.tool_call_id = None

    observation_event = create_autospec(ObservationEvent, instance=True)
    observation_event.tool_call_id = "call_3"

    events = [
        message_event,
        action_event_1,
        action_event_2,
        action_event_none,
        observation_event,
    ]

    result = condenser._get_action_tool_call_ids(events)  # type: ignore

    # Should only include tool_call_ids from ActionEvents with non-None tool_call_id
    assert result == {"call_1", "call_2"}


def test_get_observation_tool_call_ids() -> None:
    """Test _get_observation_tool_call_ids helper method."""
    condenser = TestCondenserBase()

    # Create mock events
    message_event = create_autospec(MessageEvent, instance=True)

    observation_event_1 = create_autospec(ObservationEvent, instance=True)
    observation_event_1.tool_call_id = "call_1"

    observation_event_2 = create_autospec(ObservationEvent, instance=True)
    observation_event_2.tool_call_id = "call_2"

    observation_event_none = create_autospec(ObservationEvent, instance=True)
    observation_event_none.tool_call_id = None

    action_event = create_autospec(ActionEvent, instance=True)
    action_event.tool_call_id = "call_3"

    events = [
        message_event,
        observation_event_1,
        observation_event_2,
        observation_event_none,
        action_event,
    ]

    result = condenser._get_observation_tool_call_ids(events)  # type: ignore

    # Should only include tool_call_ids from ObservationEvents with non-None
    # tool_call_id
    assert result == {"call_1", "call_2"}


def test_should_keep_event_observation_event() -> None:
    """Test _should_keep_event with ObservationEvent."""
    condenser = TestCondenserBase()

    observation_event = create_autospec(ObservationEvent, instance=True)
    observation_event.tool_call_id = "call_1"

    action_tool_call_ids = {"call_1", "call_2"}
    observation_tool_call_ids = {"call_1", "call_3"}

    # Should keep because tool_call_id is in action_tool_call_ids
    result = condenser._should_keep_event(
        observation_event, action_tool_call_ids, observation_tool_call_ids
    )
    assert result is True

    # Should not keep because tool_call_id is not in action_tool_call_ids
    action_tool_call_ids_no_match = {"call_2", "call_3"}
    result = condenser._should_keep_event(
        observation_event, action_tool_call_ids_no_match, observation_tool_call_ids
    )
    assert result is False


def test_should_keep_event_action_event() -> None:
    """Test _should_keep_event with ActionEvent."""
    condenser = TestCondenserBase()

    action_event = create_autospec(ActionEvent, instance=True)
    action_event.tool_call_id = "call_1"

    action_tool_call_ids = {"call_1", "call_2"}
    observation_tool_call_ids = {"call_1", "call_3"}

    # Should keep because tool_call_id is in observation_tool_call_ids
    result = condenser._should_keep_event(
        action_event, action_tool_call_ids, observation_tool_call_ids
    )
    assert result is True

    # Should not keep because tool_call_id is not in observation_tool_call_ids
    observation_tool_call_ids_no_match = {"call_2", "call_3"}
    result = condenser._should_keep_event(
        action_event, action_tool_call_ids, observation_tool_call_ids_no_match
    )
    assert result is False


def test_should_keep_event_other_event_types() -> None:
    """Test _should_keep_event with non-tool event types."""
    condenser = TestCondenserBase()

    message_event = create_autospec(MessageEvent, instance=True)

    action_tool_call_ids = {"call_1"}
    observation_tool_call_ids = {"call_2"}

    # Should always keep non-tool events
    result = condenser._should_keep_event(
        message_event, action_tool_call_ids, observation_tool_call_ids
    )
    assert result is True
