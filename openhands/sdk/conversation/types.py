from typing import Callable

from openhands.sdk.event import EventType


ConversationCallbackType = Callable[[EventType], None]
