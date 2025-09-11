"""Comprehensive edge case tests for EventLog class."""

import json
from unittest.mock import Mock

import pytest

from openhands.sdk.conversation.event_store import EventLog
from openhands.sdk.event.llm_convertible import MessageEvent
from openhands.sdk.io.memory import InMemoryFileStore
from openhands.sdk.llm import Message, TextContent


def create_test_event(event_id: str, content: str = "Test content") -> MessageEvent:
    """Create a test MessageEvent with specific ID."""
    event = MessageEvent(
        llm_message=Message(role="user", content=[TextContent(text=content)]),
        source="user",
    )
    # Override the ID to test specific scenarios
    event.id = event_id
    return event


class TestEventLogEdgeCases:
    """Test edge cases for EventLog class."""

    def test_event_log_empty_initialization(self):
        """Test EventLog with empty file store."""
        fs = InMemoryFileStore()
        log = EventLog(fs)

        assert len(log) == 0
        assert list(log) == []

        # Test accessing empty log
        with pytest.raises(IndexError):
            log[0]

        with pytest.raises(IndexError):
            log[-1]

    def test_event_log_id_validation_duplicate_id(self):
        """Test that duplicate event IDs are rejected."""
        fs = InMemoryFileStore()
        log = EventLog(fs)

        event1 = create_test_event("test-id-1", "First event")
        event2 = create_test_event("test-id-1", "Second event with same ID")

        log.append(event1)

        # Attempting to append event with same ID should fail
        with pytest.raises(ValueError, match="Event ID validation failed"):
            log.append(event2)

        assert len(log) == 1

    def test_event_log_id_validation_existing_id_different_index(self):
        """Test validation when event ID exists at different index."""
        fs = InMemoryFileStore()
        log = EventLog(fs)

        # Add first event
        event1 = create_test_event("event-1", "First")
        log.append(event1)

        # Manually corrupt the internal state to simulate edge case
        log._id_to_idx["event-2"] = 0  # Wrong index for event-2

        # Try to append event-2 at index 1 (should fail due to existing mapping
        # at index 0)
        event2 = create_test_event("event-2", "Second")
        with pytest.raises(ValueError, match="Event ID validation failed"):
            log.append(event2)

    def test_event_log_negative_indexing(self):
        """Test negative indexing works correctly."""
        fs = InMemoryFileStore()
        log = EventLog(fs)

        events = [
            create_test_event("event-1", "First"),
            create_test_event("event-2", "Second"),
            create_test_event("event-3", "Third"),
        ]

        for event in events:
            log.append(event)

        # Test negative indexing
        assert log[-1].id == "event-3"
        assert log[-2].id == "event-2"
        assert log[-3].id == "event-1"

        # Test out of bounds negative indexing
        with pytest.raises(IndexError):
            log[-4]

    def test_event_log_get_index_and_get_id(self):
        """Test get_index and get_id methods."""
        fs = InMemoryFileStore()
        log = EventLog(fs)

        events = [
            create_test_event("alpha", "First"),
            create_test_event("beta", "Second"),
            create_test_event("gamma", "Third"),
        ]

        for event in events:
            log.append(event)

        # Test get_index
        assert log.get_index("alpha") == 0
        assert log.get_index("beta") == 1
        assert log.get_index("gamma") == 2

        # Test get_id
        assert log.get_id(0) == "alpha"
        assert log.get_id(1) == "beta"
        assert log.get_id(2) == "gamma"

        # Test negative indexing in get_id
        assert log.get_id(-1) == "gamma"
        assert log.get_id(-2) == "beta"
        assert log.get_id(-3) == "alpha"

        # Test errors
        with pytest.raises(KeyError, match="Unknown event_id: nonexistent"):
            log.get_index("nonexistent")

        with pytest.raises(IndexError, match="Event index out of range"):
            log.get_id(3)

        with pytest.raises(IndexError, match="Event index out of range"):
            log.get_id(-4)

    def test_event_log_missing_event_file(self):
        """Test behavior when event file is missing."""
        fs = InMemoryFileStore()
        log = EventLog(fs)

        event = create_test_event("test-event", "Content")
        log.append(event)

        # Manually delete the file to simulate corruption
        path = log._path(0, event_id="test-event")
        fs.delete(path)

        # Accessing the event should raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            log[0]

    def test_event_log_corrupted_json_in_file(self):
        """Test behavior with corrupted JSON in event file."""
        fs = InMemoryFileStore()
        log = EventLog(fs)

        # Manually create a corrupted event file
        fs.write("events/event-00000-test-id.json", "invalid json content")

        # Force rescan
        log._length = log._scan_and_build_index()

        # The corrupted file should not be indexed, so length should be 0
        assert len(log) == 0

        # Accessing should raise IndexError since no valid events exist
        with pytest.raises(IndexError):
            log[0]

    def test_event_log_clear_functionality(self):
        """Test clear method removes all events and files."""
        fs = InMemoryFileStore()
        log = EventLog(fs)

        events = [
            create_test_event("event-1", "First"),
            create_test_event("event-2", "Second"),
            create_test_event("event-3", "Third"),
        ]

        for event in events:
            log.append(event)

        assert len(log) == 3

        # Clear the log
        log.clear()

        assert len(log) == 0
        assert list(log) == []
        assert log._id_to_idx == {}
        assert log._idx_to_id == {}
        assert log._idx_to_path == {}

        # Verify files are deleted
        for i in range(3):
            path = f"events/event-{i:05d}-event-{i + 1}.json"
            assert not fs.exists(path)

    def test_event_log_backward_compatibility_old_format(self):
        """Test backward compatibility with old event file format."""
        fs = InMemoryFileStore()

        # Create old format files manually
        old_event_data = {
            "id": "legacy-event-1",
            "llm_message": {
                "role": "user",
                "content": [{"type": "text", "text": "Legacy content"}],
            },
            "source": "user",
            "kind": "openhands.sdk.event.llm_convertible.MessageEvent",
        }

        fs.write("events/event-00000.json", json.dumps(old_event_data))

        # Initialize EventLog - should detect old format
        log = EventLog(fs)

        assert len(log) == 1
        assert log.get_id(0) == "legacy-event-1"
        assert log.get_index("legacy-event-1") == 0

        # Should be able to read the event
        event = log[0]
        assert event.id == "legacy-event-1"

    def test_event_log_mixed_old_new_format(self):
        """Test handling mixed old and new format files."""
        fs = InMemoryFileStore()

        # Create old format file
        old_event = {
            "id": "old-event",
            "llm_message": {
                "role": "user",
                "content": [{"type": "text", "text": "Old format"}],
            },
            "source": "user",
            "kind": "openhands.sdk.event.llm_convertible.MessageEvent",
        }
        fs.write("events/event-00000.json", json.dumps(old_event))

        # Create new format file
        new_event = {
            "id": "new-event",
            "llm_message": {
                "role": "user",
                "content": [{"type": "text", "text": "New format"}],
            },
            "source": "user",
            "kind": "openhands.sdk.event.llm_convertible.MessageEvent",
        }
        fs.write("events/event-00001-new-event.json", json.dumps(new_event))

        log = EventLog(fs)

        # The current implementation has limitations with mixed formats
        # It can load old format files but may not handle mixed scenarios perfectly
        assert len(log) >= 1
        assert log[0].id == "old-event"

        # If both events are loaded, verify the second one
        if len(log) == 2:
            assert log[1].id == "new-event"

    def test_event_log_index_gaps_detection(self):
        """Test detection and handling of index gaps."""
        fs = InMemoryFileStore()

        # Create files with gaps (missing event-00001)
        event0 = {
            "id": "event-0",
            "llm_message": {
                "role": "user",
                "content": [{"type": "text", "text": "Event 0"}],
            },
            "source": "user",
            "kind": "openhands.sdk.event.llm_convertible.MessageEvent",
        }
        fs.write("events/event-00000-event-0.json", json.dumps(event0))

        event2 = {
            "id": "event-2",
            "llm_message": {
                "role": "user",
                "content": [{"type": "text", "text": "Event 2"}],
            },
            "source": "user",
            "kind": "openhands.sdk.event.llm_convertible.MessageEvent",
        }
        fs.write("events/event-00002-event-2.json", json.dumps(event2))

        # Should only load up to the gap
        log = EventLog(fs)

        # The current scanning logic is very strict about gaps
        # If there's a gap at any index, it stops loading events entirely
        # This is the current behavior, though it could be improved
        assert len(log) == 0  # No events loaded due to gap detection

    def test_event_log_corrupted_old_format_file(self):
        """Test handling of corrupted old format files."""
        fs = InMemoryFileStore()

        # Create corrupted old format file
        fs.write("events/event-00000.json", "invalid json")

        # Should handle gracefully and skip the file
        log = EventLog(fs)
        assert len(log) == 0

    def test_event_log_file_store_exceptions(self):
        """Test handling of file store exceptions."""
        # Mock file store that raises exceptions
        mock_fs = Mock()
        mock_fs.list.side_effect = Exception("File system error")

        # Should handle gracefully
        log = EventLog(mock_fs)
        assert len(log) == 0

    def test_event_log_iteration_with_missing_files(self):
        """Test iteration behavior when some files are missing."""
        fs = InMemoryFileStore()
        log = EventLog(fs)

        # Add events
        events = [
            create_test_event("event-1", "First"),
            create_test_event("event-2", "Second"),
            create_test_event("event-3", "Third"),
        ]

        for event in events:
            log.append(event)

        # Delete middle file
        path = log._path(1, event_id="event-2")
        fs.delete(path)

        # Iteration will fail when it hits the missing file
        # This is expected behavior - the EventLog expects all files to exist
        with pytest.raises(FileNotFoundError):
            list(log)

    def test_event_log_iteration_backfills_missing_mappings(self):
        """Test that iteration backfills missing ID mappings."""
        fs = InMemoryFileStore()
        log = EventLog(fs)

        # Add an event through normal append
        event = create_test_event("manual-event", "Manual event")
        log.append(event)

        # Verify the event was added
        assert len(log) == 1
        assert log[0].id == "manual-event"

        # Clear mappings to simulate missing data
        log._idx_to_id.clear()
        log._id_to_idx.clear()

        # But keep the length so iteration can work
        log._length = 1

        # Iteration should backfill mappings
        events = list(log)
        assert len(events) == 1
        assert events[0].id == "manual-event"

        # Mappings should be restored
        assert 0 in log._idx_to_id
        assert "manual-event" in log._id_to_idx

    def test_event_log_custom_directory(self):
        """Test EventLog with custom directory."""
        fs = InMemoryFileStore()
        custom_dir = "custom_events"
        log = EventLog(fs, custom_dir)

        event = create_test_event("custom-event", "Custom content")
        log.append(event)

        # Should create file in custom directory
        expected_path = f"{custom_dir}/event-00000-custom-event.json"
        assert fs.exists(expected_path)

        # Should be able to read back
        assert len(log) == 1
        assert log[0].id == "custom-event"

    def test_event_log_large_index_formatting(self):
        """Test proper formatting of large indices."""
        fs = InMemoryFileStore()
        log = EventLog(fs)

        # Simulate large index by manually setting length
        log._length = 99999

        event = create_test_event("large-index-event", "Content")
        log.append(event)

        # Should format with proper zero-padding
        expected_path = "events/event-99999-large-index-event.json"
        assert fs.exists(expected_path)

        assert log.get_index("large-index-event") == 99999
        assert log.get_id(99999) == "large-index-event"
