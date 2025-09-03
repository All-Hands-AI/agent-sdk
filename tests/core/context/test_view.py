from openhands.sdk.context.view import View
from openhands.sdk.event import EventType
from openhands.sdk.event.condenser import Condensation, CondensationRequest
from openhands.sdk.event.llm_convertible import MessageEvent
from openhands.sdk.llm import Message, TextContent


def message_event(content: str) -> MessageEvent:
    return MessageEvent(
        llm_message=Message(role="user", content=[TextContent(text=content)]),
        source="user",
    )


def test_view_preserves_uncondensed_lists() -> None:
    """Tests that the view preserves event lists that don't contain condensation
    actions.
    """
    events: list[EventType] = [message_event(f"Event {i}") for i in range(5)]
    view = View.from_events(events)
    assert len(view) == 5
    assert view.events == events


def test_view_forgets_events() -> None:
    """Tests that views drop forgotten events and the condensation actions."""
    message_events: list[EventType] = [message_event(f"Event {i}") for i in range(5)]
    message_event_ids: list[str] = [event.id for event in message_events]

    # Build a list of events: M_1, ..., M_5, Condensation
    # The condensation specifically targets the IDs of all M_i messages
    events: list[EventType] = [
        *message_events,
        Condensation(forgotten_event_ids=message_event_ids),
    ]

    # All events should be forgotten and removed.
    view = View.from_events(events)
    assert view.events == []


def test_view_keeps_non_forgotten_events() -> None:
    """Tests that views keep non-forgotten events."""
    message_events: list[EventType] = [message_event(f"Event {i}") for i in range(5)]
    message_event_ids: list[str] = [event.id for event in message_events]

    for forgotten_event_id in message_event_ids:
        events: list[EventType] = [
            *message_events,
            # Instead of forgetting all events like in
            # `test_view_forgets_events`, in this test we only want to forget
            # one of the events. That way we can check that the rest of the
            # events are preserved.
            Condensation(forgotten_event_ids=[forgotten_event_id]),
        ]

        view = View.from_events(events)

        # We should have one less message event
        assert len(view.events) == len(message_events) - 1
        # And should _not_ have the forgotten event present
        assert forgotten_event_id not in [event.id for event in view.events]


def test_view_inserts_summary() -> None:
    """Tests that views insert a summary observation at the specified offset."""
    message_events = [message_event(f"Event {i}") for i in range(5)]

    for offset in range(5):
        events: list[EventType] = [
            *message_events,
            Condensation(
                forgotten_event_ids=[], summary="My Summary", summary_offset=offset
            ),
        ]
        view = View.from_events(events)

        assert len(view) == 6  # 5 message events + 1 summary observation
        for index, event in enumerate(view.events):
            assert isinstance(event, MessageEvent)
            assert isinstance(event.llm_message.content[0], TextContent)
            content = event.llm_message.content[0].text
            if index == offset:
                assert content == "My Summary"

            # Events before where the summary is inserted will have content
            # matching their index.
            elif index < offset:
                assert content == f"Event {index}"

            # Events after where the summary is inserted will be offset by one
            # from the original list.
            else:
                assert content == f"Event {index - 1}"


def test_no_condensation_action_in_view() -> None:
    """Ensure that condensation events are never present in the resulting view."""
    message_events = [message_event(f"Event {i}") for i in range(4)]

    # Build the event sequence -- we'll pack a condensation in the middle of four
    # message events (and make sure the condensation drops the first event)
    events: list[EventType] = []

    events.extend(message_events[:2])
    events.append(Condensation(forgotten_event_ids=[message_events[0].id]))
    events.extend(message_events[2:])

    view = View.from_events(events)

    # Check that no condensation is present in the view
    for event in view:
        assert not isinstance(event, Condensation)

    # The view should only contain the non-forgotten MessageActions
    assert len(view) == 3  # Event 1, Event 2, Event 3 (Event 0 was forgotten)


def test_unhandled_condensation_request_with_no_condensation() -> None:
    """Test that unhandled_condensation_request is True when there's a
    CondensationRequestAction but no CondensationAction.
    """
    events: list[EventType] = [
        message_event("Event 0"),
        message_event("Event 1"),
        CondensationRequest(),
        message_event("Event 2"),
    ]
    view = View.from_events(events)

    # Should be marked as having an unhandled condensation request
    assert view.unhandled_condensation_request is True

    # CondensationRequestAction should be removed from the view
    assert len(view) == 3  # Only the MessageActions remain
    for event in view:
        assert not isinstance(event, CondensationRequest)


def test_handled_condensation_request_with_condensation_action() -> None:
    """Test that unhandled_condensation_request is False when CondensationAction comes
    after CondensationRequestAction.
    """
    events: list[EventType] = []
    events.extend(
        [
            message_event("Event 0"),
            message_event("Event 1"),
            CondensationRequest(),
            message_event("Event 2"),
        ]
    )
    events.append(Condensation(forgotten_event_ids=[event.id for event in events[:2]]))
    events.append(message_event("Event 3"))
    view = View.from_events(events)

    # Should NOT be marked as having an unhandled condensation request
    assert view.unhandled_condensation_request is False

    # Both CondensationRequestAction and CondensationAction should be removed from the
    # view
    assert len(view) == 2  # Event 2 and Event 3 (Event 0, 1 forgotten)
    for event in view:
        assert not isinstance(event, CondensationRequest)
        assert not isinstance(event, Condensation)


def test_multiple_condensation_requests_pattern() -> None:
    """Test the pattern with multiple condensation requests and actions."""
    events: list[EventType] = [
        message_event(content="Event 0"),
        CondensationRequest(),  # First request
        message_event(content="Event 1"),
        Condensation(forgotten_event_ids=[]),  # Handles first request
        message_event(content="Event 2"),
        CondensationRequest(),  # Second request - should be unhandled
        message_event(content="Event 3"),
    ]
    view = View.from_events(events)

    # Should be marked as having an unhandled condensation request (the second one)
    assert view.unhandled_condensation_request is True

    # Both CondensationRequests and Condensation should be removed from the view
    assert len(view) == 4  # Event 0, Event 1, Event 2, Event 3
    for event in view:
        assert not isinstance(event, CondensationRequest)
        assert not isinstance(event, Condensation)


def test_condensation_action_before_request() -> None:
    """Test that CondensationAction before CondensationRequestAction doesn't affect the
    unhandled status.
    """
    events: list[EventType] = [
        message_event(content="Event 0"),
        Condensation(forgotten_event_ids=[]),  # This doesn't handle the later request
        message_event(content="Event 1"),
        CondensationRequest(),  # This should be unhandled
        message_event(content="Event 2"),
    ]
    view = View.from_events(events)

    # Should be marked as having an unhandled condensation request
    assert view.unhandled_condensation_request is True

    # Both CondensationRequestAction and CondensationAction should be removed
    # from the view
    assert len(view) == 3  # Event 0, Event 1, Event 2
    for event in view:
        assert not isinstance(event, CondensationRequest)
        assert not isinstance(event, Condensation)


def test_no_condensation_events() -> None:
    """Test that unhandled_condensation_request is False when there are no condensation
    events.
    """
    events: list[EventType] = [
        message_event(content="Event 0"),
        message_event(content="Event 1"),
        message_event(content="Event 2"),
    ]
    view = View.from_events(events)

    # Should NOT be marked as having an unhandled condensation request
    assert view.unhandled_condensation_request is False

    # All events should remain
    assert len(view) == 3
    assert view.events == events


def test_condensation_request_always_removed_from_view() -> None:
    """Test that CondensationRequest is always removed from the view regardless of
    unhandled status.
    """
    # Test case 1: Unhandled request
    events_unhandled: list[EventType] = [
        message_event(content="Event 0"),
        CondensationRequest(),
        message_event(content="Event 1"),
    ]
    view_unhandled = View.from_events(events_unhandled)

    assert view_unhandled.unhandled_condensation_request is True
    assert len(view_unhandled) == 2  # Only MessageEvents
    for event in view_unhandled:
        assert not isinstance(event, CondensationRequest)

    # Test case 2: Handled request
    events_handled: list[EventType] = [
        message_event(content="Event 0"),
        CondensationRequest(),
        message_event(content="Event 1"),
        Condensation(forgotten_event_ids=[]),
        message_event(content="Event 2"),
    ]
    view_handled = View.from_events(events_handled)

    assert view_handled.unhandled_condensation_request is False
    assert len(view_handled) == 3  # Only MessageEvents
    for event in view_handled:
        assert not isinstance(event, CondensationRequest)
        assert not isinstance(event, Condensation)
