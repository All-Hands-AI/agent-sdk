from typing import Callable

from openhands.sdk.event import Event


ConversationCallbackType = Callable[[Event], None]
