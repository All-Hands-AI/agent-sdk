from __future__ import annotations

import unittest
from unittest.mock import MagicMock, Mock, patch

from openhands.sdk.llm.llm import LLM
from openhands.sdk.llm.llm_registry import LLMRegistry, RegistryEvent


class TestLLMRegistry(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test."""
        # Create a registry for testing
        self.registry = LLMRegistry()

    def test_subscribe_and_notify(self):
        """Test the subscription and notification system."""
        events_received = []

        def callback(event: RegistryEvent):
            events_received.append(event)

        # Subscribe to events
        self.registry.subscribe(callback)

        # Create a mock LLM and add it to trigger notification
        mock_llm = Mock(spec=LLM)
        service_id = "notify-service"

        # Mock the RegistryEvent to avoid LLM attribute access
        with patch(
            "openhands.sdk.llm.llm_registry.RegistryEvent"
        ) as mock_registry_event:
            mock_registry_event.return_value = Mock()
            self.registry.add(service_id, mock_llm)

        # Should receive notification for the newly added LLM
        self.assertEqual(len(events_received), 1)

        # Test that the subscriber is set correctly
        self.assertIsNotNone(self.registry.subscriber)

        # Test notify method directly with a mock event
        with patch.object(self.registry, "subscriber") as mock_subscriber:
            mock_event = MagicMock()
            self.registry.notify(mock_event)
            mock_subscriber.assert_called_once_with(mock_event)

    def test_registry_has_unique_id(self):
        """Test that each registry instance has a unique ID."""
        registry2 = LLMRegistry()
        self.assertNotEqual(self.registry.registry_id, registry2.registry_id)
        self.assertTrue(len(self.registry.registry_id) > 0)
        self.assertTrue(len(registry2.registry_id) > 0)


def test_llm_registry_notify_exception_handling():
    """Test LLM registry handles exceptions in subscriber notification."""

    # Create a subscriber that raises an exception
    def failing_subscriber(event):
        raise ValueError("Subscriber failed")

    registry = LLMRegistry()
    registry.subscribe(failing_subscriber)

    # Mock the logger to capture warning messages
    with patch("openhands.sdk.llm.llm_registry.logger") as mock_logger:
        # Create a mock event
        mock_event = Mock()

        # This should handle the exception and log a warning (lines 146-147)
        registry.notify(mock_event)

        # Should have logged the warning
        mock_logger.warning.assert_called_once()
        assert "Failed to emit event:" in str(mock_logger.warning.call_args)


def test_llm_registry_list_services():
    """Test LLM registry list_services method."""

    registry = LLMRegistry()

    # Create mock LLM objects
    mock_llm1 = Mock(spec=LLM)
    mock_llm2 = Mock(spec=LLM)

    # Mock the RegistryEvent to avoid LLM attribute access
    with patch("openhands.sdk.llm.llm_registry.RegistryEvent") as mock_registry_event:
        mock_registry_event.return_value = Mock()

        # Add some LLMs using the new API
        registry.add("service1", mock_llm1)
        registry.add("service2", mock_llm2)

        # Test list_services
        services = registry.list_services()

        assert "service1" in services
        assert "service2" in services
        assert len(services) == 2


def test_llm_registry_add_method():
    """Test the new add() method for LLMRegistry."""
    registry = LLMRegistry()

    # Create a mock LLM
    mock_llm = Mock(spec=LLM)
    service_id = "test-service"

    # Mock the RegistryEvent to avoid LLM attribute access
    with patch("openhands.sdk.llm.llm_registry.RegistryEvent") as mock_registry_event:
        mock_registry_event.return_value = Mock()

        # Test adding an LLM
        registry.add(service_id, mock_llm)

        # Verify the LLM was added
        assert service_id in registry.service_to_llm
        assert registry.service_to_llm[service_id] is mock_llm
        assert mock_llm.service_id == service_id

        # Verify RegistryEvent was called
        mock_registry_event.assert_called_once_with(llm=mock_llm, service_id=service_id)

    # Test that adding the same service_id raises ValueError
    with unittest.TestCase().assertRaises(ValueError) as context:
        registry.add(service_id, mock_llm)

    assert "already exists in registry" in str(context.exception)


def test_llm_registry_get_method():
    """Test the new get() method for LLMRegistry."""
    registry = LLMRegistry()

    # Create a mock LLM
    mock_llm = Mock(spec=LLM)
    service_id = "test-service"

    # Mock the RegistryEvent to avoid LLM attribute access
    with patch("openhands.sdk.llm.llm_registry.RegistryEvent") as mock_registry_event:
        mock_registry_event.return_value = Mock()

        # Add the LLM first
        registry.add(service_id, mock_llm)

        # Test getting the LLM
        retrieved_llm = registry.get(service_id)
        assert retrieved_llm is mock_llm

    # Test getting non-existent service raises KeyError
    with unittest.TestCase().assertRaises(KeyError) as context:
        registry.get("non-existent-service")

    assert "not found in registry" in str(context.exception)


def test_llm_registry_add_get_workflow():
    """Test the complete add/get workflow."""
    registry = LLMRegistry()

    # Create mock LLMs
    llm1 = Mock(spec=LLM)
    llm2 = Mock(spec=LLM)

    # Mock the RegistryEvent to avoid LLM attribute access
    with patch("openhands.sdk.llm.llm_registry.RegistryEvent") as mock_registry_event:
        mock_registry_event.return_value = Mock()

        # Add multiple LLMs
        registry.add("service1", llm1)
        registry.add("service2", llm2)

        # Verify we can retrieve them
        assert registry.get("service1") is llm1
        assert registry.get("service2") is llm2

        # Verify list_services works
        services = registry.list_services()
        assert "service1" in services
        assert "service2" in services
        assert len(services) == 2

        # Verify service_id is set correctly
        assert llm1.service_id == "service1"
        assert llm2.service_id == "service2"
