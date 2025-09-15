from typing import Union, get_args, get_type_hints

from pydantic import BaseModel

from openhands.sdk.event.llm_convertible import (
    ActionEvent,
    AgentErrorEvent,
    MessageEvent,
)
from openhands.sdk.llm import MetricsSnapshot


EventWithMetrics = ActionEvent | MessageEvent | AgentErrorEvent
EVENT_CLASSES: tuple[type, ...] = get_args(EventWithMetrics)

for cls in EVENT_CLASSES:
    assert issubclass(cls, BaseModel)
    assert "metrics" in cls.model_fields, (
        f"{cls.__name__} must declare 'metrics' as a Pydantic field"
    )

    # allow MetricsSnapshot or MetricsSnapshot | None
    hints = get_type_hints(cls)
    ann = hints.get("metrics")
    assert ann in (
        MetricsSnapshot,
        Union[MetricsSnapshot, None],
    ), (
        f"{cls.__name__}.metrics must be MetricsSnapshot "
        f"or MetricsSnapshot|None, found {ann!r}"
    )
