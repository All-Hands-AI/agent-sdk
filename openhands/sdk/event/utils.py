"""Utility functions for event processing."""

from openhands.sdk.event import ActionEvent, ObservationEvent, UserRejectObservation


def get_unmatched_actions(events: list) -> list[ActionEvent]:
    """Find actions in the event history that don't have matching observations.

    Optimized to search in reverse chronological order since recent actions
    are more likely to be unmatched (pending confirmation).

    Args:
        events: List of events to search through

    Returns:
        List of ActionEvent objects that don't have corresponding observations
    """
    observed_action_ids = set()
    unmatched_actions = []

    # Search in reverse - recent events are more likely to be unmatched
    for event in reversed(events):
        if isinstance(event, (ObservationEvent, UserRejectObservation)):
            observed_action_ids.add(event.action_id)
        elif isinstance(event, ActionEvent):
            if event.id not in observed_action_ids:
                # Insert at beginning to maintain chronological order in result
                unmatched_actions.insert(0, event)

    return unmatched_actions
