from unittest.mock import MagicMock

import pytest

from openhands.sdk.context.condenser.matching_tool_filtering_condenser import (
    MatchingToolFilteringCondenser,
)


class TestMatchingToolFilteringCondenser:
    """Test cases for MatchingToolFilteringCondenser methods directly."""

    def test_get_action_tool_call_ids_empty(self):
        """Test _get_action_tool_call_ids with empty event list."""
        condenser = MatchingToolFilteringCondenser()
        result = condenser._get_action_tool_call_ids([])
        assert result == set()

    def test_get_action_tool_call_ids_no_action_events(self):
        """Test _get_action_tool_call_ids with no ActionEvents."""
        # Create mock non-ActionEvent
        message_event = MagicMock()
        message_event.__class__.__name__ = "MessageEvent"

        condenser = MatchingToolFilteringCondenser()
        result = condenser._get_action_tool_call_ids([message_event])
        assert result == set()

    def test_get_action_tool_call_ids_with_action_events(self):
        """Test _get_action_tool_call_ids with ActionEvents."""
        # Create mock ActionEvents
        action_event_1 = MagicMock()
        action_event_1.__class__.__name__ = "ActionEvent"
        action_event_1.tool_call_id = "call_1"

        action_event_2 = MagicMock()
        action_event_2.__class__.__name__ = "ActionEvent"
        action_event_2.tool_call_id = "call_2"

        # Create mock non-ActionEvent
        message_event = MagicMock()
        message_event.__class__.__name__ = "MessageEvent"

        events = [message_event, action_event_1, action_event_2]
        condenser = MatchingToolFilteringCondenser()
        result = condenser._get_action_tool_call_ids(events)  # type: ignore
        assert result == {"call_1", "call_2"}

    def test_get_observation_tool_call_ids_empty(self):
        """Test _get_observation_tool_call_ids with empty event list."""
        condenser = MatchingToolFilteringCondenser()
        result = condenser._get_observation_tool_call_ids([])
        assert result == set()

    def test_get_observation_tool_call_ids_no_observation_events(self):
        """Test _get_observation_tool_call_ids with no ObservationEvents."""
        # Create mock non-ObservationEvent
        message_event = MagicMock()
        message_event.__class__.__name__ = "MessageEvent"

        condenser = MatchingToolFilteringCondenser()
        result = condenser._get_observation_tool_call_ids([message_event])
        assert result == set()

    def test_get_observation_tool_call_ids_with_observation_events(self):
        """Test _get_observation_tool_call_ids with ObservationEvents."""
        # Create mock ObservationEvents
        observation_event_1 = MagicMock()
        observation_event_1.__class__.__name__ = "ObservationEvent"
        observation_event_1.tool_call_id = "call_1"

        observation_event_2 = MagicMock()
        observation_event_2.__class__.__name__ = "ObservationEvent"
        observation_event_2.tool_call_id = "call_2"

        # Create mock non-ObservationEvent
        message_event = MagicMock()
        message_event.__class__.__name__ = "MessageEvent"

        events = [message_event, observation_event_1, observation_event_2]
        condenser = MatchingToolFilteringCondenser()
        result = condenser._get_observation_tool_call_ids(events)  # type: ignore
        assert result == {"call_1", "call_2"}

    def test_should_keep_event_non_tool_event(self):
        """Test _should_keep_event with non-tool events (should always keep)."""
        condenser = MatchingToolFilteringCondenser()

        # Create mock non-tool event
        message_event = MagicMock()
        message_event.__class__.__name__ = "MessageEvent"

        action_tool_call_ids = {"call_1"}
        observation_tool_call_ids = {"call_1"}

        result = condenser._should_keep_event(
            message_event, action_tool_call_ids, observation_tool_call_ids
        )
        assert result is True

    def test_should_keep_event_matched_action_event(self):
        """Test _should_keep_event with matched ActionEvent (should keep)."""
        condenser = MatchingToolFilteringCondenser()

        # Create mock ActionEvent
        action_event = MagicMock()
        action_event.__class__.__name__ = "ActionEvent"
        action_event.tool_call_id = "call_1"

        action_tool_call_ids = {"call_1", "call_2"}
        observation_tool_call_ids = {"call_1", "call_3"}  # call_1 matches

        result = condenser._should_keep_event(
            action_event, action_tool_call_ids, observation_tool_call_ids
        )
        assert result is True

    def test_should_keep_event_unmatched_action_event(self):
        """Test _should_keep_event with unmatched ActionEvent (should filter out)."""
        condenser = MatchingToolFilteringCondenser()

        # Create mock ActionEvent
        action_event = MagicMock()
        action_event.__class__.__name__ = "ActionEvent"
        action_event.tool_call_id = "call_1"

        action_tool_call_ids = {"call_1", "call_2"}
        observation_tool_call_ids = {"call_3", "call_4"}  # call_1 doesn't match

        result = condenser._should_keep_event(
            action_event, action_tool_call_ids, observation_tool_call_ids
        )
        assert result is False

    def test_should_keep_event_matched_observation_event(self):
        """Test _should_keep_event with matched ObservationEvent (should keep)."""
        condenser = MatchingToolFilteringCondenser()

        # Create mock ObservationEvent
        observation_event = MagicMock()
        observation_event.__class__.__name__ = "ObservationEvent"
        observation_event.tool_call_id = "call_1"

        action_tool_call_ids = {"call_1", "call_2"}  # call_1 matches
        observation_tool_call_ids = {"call_1", "call_3"}

        result = condenser._should_keep_event(
            observation_event, action_tool_call_ids, observation_tool_call_ids
        )
        assert result is True

    def test_should_keep_event_unmatched_observation_event(self):
        """Test _should_keep_event with unmatched ObservationEvent (should filter
        out).
        """
        condenser = MatchingToolFilteringCondenser()

        # Create mock ObservationEvent
        observation_event = MagicMock()
        observation_event.__class__.__name__ = "ObservationEvent"
        observation_event.tool_call_id = "call_1"

        action_tool_call_ids = {"call_2", "call_3"}  # call_1 doesn't match
        observation_tool_call_ids = {"call_1", "call_4"}

        result = condenser._should_keep_event(
            observation_event, action_tool_call_ids, observation_tool_call_ids
        )
        assert result is False

    def test_condense_with_mock_view(self):
        """Test condense method with mocked View."""
        condenser = MatchingToolFilteringCondenser()

        # Create mock events
        message_event = MagicMock()
        message_event.__class__.__name__ = "MessageEvent"

        # Matched pair
        action_event = MagicMock()
        action_event.__class__.__name__ = "ActionEvent"
        action_event.tool_call_id = "call_1"

        observation_event = MagicMock()
        observation_event.__class__.__name__ = "ObservationEvent"
        observation_event.tool_call_id = "call_1"

        # Unmatched ActionEvent
        unmatched_action = MagicMock()
        unmatched_action.__class__.__name__ = "ActionEvent"
        unmatched_action.tool_call_id = "call_2"

        events = [message_event, action_event, observation_event, unmatched_action]

        # Mock the View
        mock_view = MagicMock()
        mock_view.events = events

        # Mock the View constructor to return a new view with filtered events
        with pytest.MonkeyPatch().context() as m:
            mock_view_class = MagicMock()
            mock_filtered_view = MagicMock()
            mock_view_class.return_value = mock_filtered_view
            m.setattr(
                "openhands.sdk.context.condenser.matching_tool_filtering_condenser.View",
                mock_view_class,
            )

            result = condenser.condense(mock_view)

            # Check that View was called with filtered events
            # Should keep: message_event, action_event, observation_event
            # Should filter out: unmatched_action
            mock_view_class.assert_called_once()
            call_args = mock_view_class.call_args
            filtered_events = call_args[1]["events"]  # keyword argument

            assert len(filtered_events) == 3
            assert message_event in filtered_events
            assert action_event in filtered_events
            assert observation_event in filtered_events
            assert unmatched_action not in filtered_events

            assert result == mock_filtered_view
