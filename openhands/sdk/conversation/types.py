import uuid
from typing import Callable

from openhands.sdk.event.base import EventBase


ConversationCallbackType = Callable[[EventBase], None]

ConversationID = uuid.UUID
"""Type alias for conversation IDs."""
