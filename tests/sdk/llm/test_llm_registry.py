from __future__ import annotations

import unittest
from unittest.mock import MagicMock, Mock, patch

from litellm.types.utils import Choices, Message, ModelResponse

from openhands.sdk.llm.llm import LLM
from openhands.sdk.llm.llm_registry import LLMRegistry, RegistryEvent


class TestLLMRegistry(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test."""
        # Create a basic LLM for testing
        self.llm_config = LLM(model="test-model")

        # Create a registry for testing
        self.registry = LLMRegistry()

    def test_get_llm_creates_new_llm(self):
        """Test that get_llm creates a new LLM when service doesn't exist."""
        service_id = "test-service"

        # Mock the _create_new_llm method to avoid actual LLM initialization
        with patch.object(self.registry, "_create_new_llm") as mock_create:
            mock_llm = MagicMock()
            mock_create.return_value = mock_llm

            # Get LLM for the first time
            llm = self.registry.get_llm(service_id, self.llm_config)

            # Verify LLM was created and stored
            self.assertEqual(llm, mock_llm)
            mock_create.assert_called_once_with(
                llm_config=self.llm_config, service_id=service_id
            )

    def test_get_llm_returns_existing_llm(self):
        """Test that get_llm returns existing LLM when service already exists."""
        service_id = "test-service"

        # Mock the LLM constructor and RegistryEvent to avoid actual LLM initialization
        with (
            patch("openhands.sdk.llm.llm_registry.LLM") as mock_llm_class,
            patch("openhands.sdk.llm.llm_registry.RegistryEvent"),
        ):
            mock_llm = MagicMock()
            # Make the mock LLM's model_dump return the same config as self.llm_config
            mock_llm.model_dump.return_value = self.llm_config.model_dump(
                exclude={"service_id", "metrics", "retry_listener"}
            )
            mock_llm_class.return_value = mock_llm

            # Get LLM for the first time
            llm1 = self.registry.get_llm(service_id, self.llm_config)

            # Get LLM for the second time - should return the same instance
            llm2 = self.registry.get_llm(service_id, self.llm_config)

            # Verify same LLM instance is returned
            self.assertEqual(llm1, llm2)
            self.assertEqual(llm1, mock_llm)

            # Verify LLM constructor was only called once
            mock_llm_class.assert_called_once()

    def test_get_llm_with_different_config_raises_error(self):
        """
        Test that requesting same service ID with different config
        raises an error.
        """
        service_id = "test-service"
        different_config = LLM(model="different-model")

        # Manually add an LLM to the registry to simulate existing service
        mock_llm = MagicMock()
        mock_llm.model_dump.return_value = {"model": "test-model"}
        self.registry.service_to_llm[service_id] = mock_llm

        # Attempt to get LLM with different config should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.registry.get_llm(service_id, different_config)

        self.assertIn("Requesting same service ID", str(context.exception))
        self.assertIn("with different config", str(context.exception))

    def test_get_new_llm_without_config_raises_error(self):
        """Test that requesting new LLM without config raises an error."""
        service_id = "test-service"

        # Attempt to get LLM without providing config should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.registry.get_llm(service_id, None)

        self.assertIn(
            "Requesting new LLM without specifying LLM config", str(context.exception)
        )

    def test_request_extraneous_completion(self):
        """Test that requesting an extraneous completion creates a new LLM if needed."""
        service_id = "extraneous-service"
        messages = [{"role": "user", "content": "Hello, world!"}]

        # Mock the _create_new_llm method to avoid actual LLM initialization
        with patch.object(self.registry, "_create_new_llm") as mock_create:
            mock_llm = MagicMock()
            mock_response = ModelResponse()
            mock_response.choices = [
                Choices(
                    message=Message(content="  Hello from the LLM!  ", role="assistant")
                )
            ]
            mock_llm.completion.return_value = mock_response
            mock_create.return_value = mock_llm

            # Mock the side effect to add the LLM to the registry
            def side_effect(*args, **kwargs):
                self.registry.service_to_llm[service_id] = mock_llm
                return mock_llm

            mock_create.side_effect = side_effect

            # Request a completion
            response = self.registry.request_extraneous_completion(
                service_id=service_id,
                llm_config=self.llm_config,
                messages=messages,
            )

            # Verify the response (should be stripped)
            self.assertEqual(response, "Hello from the LLM!")

            # Verify that _create_new_llm was called with correct parameters
            mock_create.assert_called_once_with(
                llm_config=self.llm_config, service_id=service_id, with_listener=False
            )

            # Verify completion was called with correct messages
            mock_llm.completion.assert_called_once_with(messages=messages)

    def test_subscribe_and_notify(self):
        """Test the subscription and notification system."""
        events_received = []

        def callback(event: RegistryEvent):
            events_received.append(event)

        # Subscribe to events
        self.registry.subscribe(callback)

        # Create an LLM to trigger notification
        service_id = "notify-service"
        self.registry.get_llm(service_id, self.llm_config)

        # Should receive notification for the newly created LLM
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


def test_llm_registry_create_without_listener():
    """Test LLM registry creates LLM without retry listener."""
    registry = LLMRegistry()

    # Create a mock LLM config object
    mock_llm_config = Mock(spec=LLM)
    mock_llm_config.model_dump.return_value = {"model": "test-model"}

    # Mock the LLM constructor and RegistryEvent to avoid actual initialization
    with (
        patch("openhands.sdk.llm.llm_registry.LLM") as mock_llm_class,
        patch("openhands.sdk.llm.llm_registry.RegistryEvent") as mock_registry_event,
    ):
        mock_llm = Mock()
        mock_llm_class.return_value = mock_llm
        mock_registry_event.return_value = Mock()

        # Create LLM without listener (line 56)
        result = registry._create_new_llm(
            "test-service", mock_llm_config, with_listener=False
        )

        # Should create LLM without retry_listener parameter
        mock_llm_class.assert_called_once_with(
            service_id="test-service", model="test-model"
        )
        assert result == mock_llm


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

    # Create mock LLM config objects
    mock_llm_config1 = Mock(spec=LLM)
    mock_llm_config1.model_dump.return_value = {"model": "model1"}
    mock_llm_config2 = Mock(spec=LLM)
    mock_llm_config2.model_dump.return_value = {"model": "model2"}

    # Mock the LLM constructor and RegistryEvent
    with (
        patch("openhands.sdk.llm.llm_registry.LLM") as mock_llm_class,
        patch("openhands.sdk.llm.llm_registry.RegistryEvent") as mock_registry_event,
    ):
        mock_llm_class.return_value = Mock()
        mock_registry_event.return_value = Mock()

        # Create some LLMs
        registry._create_new_llm("service1", mock_llm_config1)
        registry._create_new_llm("service2", mock_llm_config2)

        # Test list_services (line 155)
        services = registry.list_services()

        assert "service1" in services
        assert "service2" in services
        assert len(services) == 2
