from typing import Callable

from openhands.core.event import EventType


ConversationCallbackType = Callable[[EventType], None]
