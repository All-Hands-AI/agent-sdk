"""Subscription class for managing multiple conversation callbacks."""

import uuid
from typing import Dict

from openhands.sdk.conversation.types import ConversationCallbackType
from openhands.sdk.event import Event
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


class Subscription:
    """A subscription manager that extends ConversationCallbackType functionality.

    This class maintains a dictionary of UUIDs to ConversationCallbackType instances
    and provides methods to subscribe/unsubscribe callbacks. When invoked, it calls
    all registered callbacks with proper error handling.
    """

    def __init__(self) -> None:
        """Initialize the subscription manager with an empty callback registry."""
        self._callbacks: Dict[str, ConversationCallbackType] = {}

    def subscribe(self, callback: ConversationCallbackType) -> str:
        """Subscribe a callback and return its UUID for later unsubscription.

        Args:
            callback: The callback function to register

        Returns:
            str: UUID that can be used to unsubscribe this callback
        """
        callback_id = str(uuid.uuid4())
        self._callbacks[callback_id] = callback
        logger.debug(f"Subscribed callback with ID: {callback_id}")
        return callback_id

    def unsubscribe(self, callback_id: str) -> bool:
        """Unsubscribe a callback by its UUID.

        Args:
            callback_id: The UUID returned by subscribe()

        Returns:
            bool: True if callback was found and removed, False otherwise
        """
        if callback_id in self._callbacks:
            del self._callbacks[callback_id]
            logger.debug(f"Unsubscribed callback with ID: {callback_id}")
            return True
        else:
            logger.warning(
                f"Attempted to unsubscribe unknown callback ID: {callback_id}"
            )
            return False

    def __call__(self, event: Event) -> None:
        """Invoke all registered callbacks with the given event.

        Each callback is invoked in its own try/catch block to prevent
        one failing callback from affecting others.

        Args:
            event: The event to pass to all callbacks
        """
        for callback_id, callback in self._callbacks.items():
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in callback {callback_id}: {e}", exc_info=True)

    def on_event(self, event: Event) -> None:
        """Alias for __call__ method.

        Args:
            event: The event to pass to all callbacks
        """
        self(event)

    @property
    def callback_count(self) -> int:
        """Return the number of registered callbacks."""
        return len(self._callbacks)

    def clear(self) -> None:
        """Remove all registered callbacks."""
        count = len(self._callbacks)
        self._callbacks.clear()
        logger.debug(f"Cleared {count} callbacks")
