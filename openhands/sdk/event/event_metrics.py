from typing import get_args, get_type_hints

from pydantic import BaseModel

from openhands.sdk.event.llm_convertible import (
    ActionEvent,
    AgentErrorEvent,
    MessageEvent,
)
from openhands.sdk.llm import MetricsSnapshot


# 1) Define the union ONCE
EventWithMetrics = ActionEvent | MessageEvent | AgentErrorEvent

# 2) Derive the class tuple from the union (no duplication)
EVENT_CLASSES: tuple[type, ...] = get_args(EventWithMetrics)

# 3) Assert each has a 'metrics' field/attribute, Pydantic-aware
for cls in EVENT_CLASSES:
    assert issubclass(cls, BaseModel)
    # Pydantic v2: ensure 'metrics' is a declared model field
    assert "metrics" in cls.model_fields, (
        f"{cls.__name__} must declare 'metrics' as a Pydantic field"
    )
    # Check type annotation (works for both plain + Pydantic)
    hints = get_type_hints(cls)
    assert hints.get("metrics") is MetricsSnapshot, (
        f"{cls.__name__}.metrics must be annotated as MetricsSnapshot, "
        f"found {hints.get('metrics')!r}"
    )
