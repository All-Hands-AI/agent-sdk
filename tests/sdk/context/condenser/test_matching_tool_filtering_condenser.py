from unittest.mock import create_autospec

from openhands.sdk.context.condenser.matching_tool_filtering_condenser import (
    MatchingToolFilteringCondenser,
)
from openhands.sdk.context.view import View
from openhands.sdk.event.llm_convertible import (
    ActionEvent,
    MessageEvent,
    ObservationEvent,
)


def test_get_action_tool_call_ids_empty() -> None:
    """Test _get_action_tool_call_ids with empty event list."""
    condenser = MatchingToolFilteringCondenser()
    result = condenser._get_action_tool_call_ids([])
    assert result == set()


def test_get_action_tool_call_ids_no_action_events() -> None:
    """Test _get_action_tool_call_ids with no ActionEvents."""
    # Create mock non-ActionEvent
    message_event = create_autospec(MessageEvent, instance=True)

    condenser = MatchingToolFilteringCondenser()
    result = condenser._get_action_tool_call_ids([message_event])
    assert result == set()


def test_get_action_tool_call_ids_with_action_events() -> None:
    """Test _get_action_tool_call_ids with ActionEvents."""
    # Create mock ActionEvents
    action_event_1 = create_autospec(ActionEvent, instance=True)
    action_event_1.tool_call_id = "call_1"

    action_event_2 = create_autospec(ActionEvent, instance=True)
    action_event_2.tool_call_id = "call_2"

    # Create mock non-ActionEvent
    message_event = create_autospec(MessageEvent, instance=True)

    events = [message_event, action_event_1, action_event_2]
    condenser = MatchingToolFilteringCondenser()
    result = condenser._get_action_tool_call_ids(events)  # type: ignore
    assert result == {"call_1", "call_2"}


def test_get_observation_tool_call_ids_empty() -> None:
    """Test _get_observation_tool_call_ids with empty event list."""
    condenser = MatchingToolFilteringCondenser()
    result = condenser._get_observation_tool_call_ids([])
    assert result == set()


def test_get_observation_tool_call_ids_no_observation_events() -> None:
    """Test _get_observation_tool_call_ids with no ObservationEvents."""
    # Create mock non-ObservationEvent
    message_event = create_autospec(MessageEvent, instance=True)

    condenser = MatchingToolFilteringCondenser()
    result = condenser._get_observation_tool_call_ids([message_event])
    assert result == set()


def test_get_observation_tool_call_ids_with_observation_events() -> None:
    """Test _get_observation_tool_call_ids with ObservationEvents."""
    # Create mock ObservationEvents
    observation_event_1 = create_autospec(ObservationEvent, instance=True)
    observation_event_1.tool_call_id = "call_1"

    observation_event_2 = create_autospec(ObservationEvent, instance=True)
    observation_event_2.tool_call_id = "call_2"

    # Create mock non-ObservationEvent
    message_event = create_autospec(MessageEvent, instance=True)

    events = [message_event, observation_event_1, observation_event_2]
    condenser = MatchingToolFilteringCondenser()
    result = condenser._get_observation_tool_call_ids(events)  # type: ignore
    assert result == {"call_1", "call_2"}


def test_should_keep_event_non_tool_event() -> None:
    """Test _should_keep_event with non-tool events (should always keep)."""
    condenser = MatchingToolFilteringCondenser()

    # Create mock non-tool event
    message_event = create_autospec(MessageEvent, instance=True)

    action_tool_call_ids = {"call_1"}
    observation_tool_call_ids = {"call_1"}

    result = condenser._should_keep_event(
        message_event, action_tool_call_ids, observation_tool_call_ids
    )
    assert result is True


def test_should_keep_event_matched_action_event() -> None:
    """Test _should_keep_event with matched ActionEvent (should keep)."""
    condenser = MatchingToolFilteringCondenser()

    # Create mock ActionEvent
    action_event = create_autospec(ActionEvent, instance=True)
    action_event.tool_call_id = "call_1"

    action_tool_call_ids = {"call_1", "call_2"}
    observation_tool_call_ids = {"call_1", "call_3"}  # call_1 matches

    result = condenser._should_keep_event(
        action_event, action_tool_call_ids, observation_tool_call_ids
    )
    assert result is True


def test_should_keep_event_unmatched_action_event() -> None:
    """Test _should_keep_event with unmatched ActionEvent (should filter out)."""
    condenser = MatchingToolFilteringCondenser()

    # Create mock ActionEvent
    action_event = create_autospec(ActionEvent, instance=True)
    action_event.tool_call_id = "call_1"

    action_tool_call_ids = {"call_1", "call_2"}
    observation_tool_call_ids = {"call_3", "call_4"}  # call_1 doesn't match

    result = condenser._should_keep_event(
        action_event, action_tool_call_ids, observation_tool_call_ids
    )
    assert result is False


def test_should_keep_event_matched_observation_event() -> None:
    """Test _should_keep_event with matched ObservationEvent (should keep)."""
    condenser = MatchingToolFilteringCondenser()

    # Create mock ObservationEvent
    observation_event = create_autospec(ObservationEvent, instance=True)
    observation_event.tool_call_id = "call_1"

    action_tool_call_ids = {"call_1", "call_2"}  # call_1 matches
    observation_tool_call_ids = {"call_1", "call_3"}

    result = condenser._should_keep_event(
        observation_event, action_tool_call_ids, observation_tool_call_ids
    )
    assert result is True


def test_should_keep_event_unmatched_observation_event() -> None:
    """Test _should_keep_event with unmatched ObservationEvent (should filter out)."""  # noqa: E501
    condenser = MatchingToolFilteringCondenser()

    # Create mock ObservationEvent
    observation_event = create_autospec(ObservationEvent, instance=True)
    observation_event.tool_call_id = "call_1"

    action_tool_call_ids = {"call_2", "call_3"}  # call_1 doesn't match
    observation_tool_call_ids = {"call_1", "call_4"}

    result = condenser._should_keep_event(
        observation_event, action_tool_call_ids, observation_tool_call_ids
    )
    assert result is False


def test_condense_filters_correctly() -> None:
    """Test condense method filters events correctly."""
    condenser = MatchingToolFilteringCondenser()

    # Create mock events
    message_event = create_autospec(MessageEvent, instance=True)

    # Matched pair
    action_event = create_autospec(ActionEvent, instance=True)
    action_event.tool_call_id = "call_1"

    observation_event = create_autospec(ObservationEvent, instance=True)
    observation_event.tool_call_id = "call_1"

    # Unmatched ActionEvent
    unmatched_action = create_autospec(ActionEvent, instance=True)
    unmatched_action.tool_call_id = "call_2"

    events = [message_event, action_event, observation_event, unmatched_action]

    # Create a real View with the mock events
    view = View(events=events)

    result = condenser.condense(view)

    # Should keep: message_event, action_event, observation_event
    # Should filter out: unmatched_action
    assert isinstance(result, View)
    assert len(result.events) == 3
    assert message_event in result.events
    assert action_event in result.events
    assert observation_event in result.events
    assert unmatched_action not in result.events
