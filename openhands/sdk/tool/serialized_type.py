"""Type annotations for serialization / deserialization"""

from typing import TYPE_CHECKING

from openhands.sdk.event.llm_convertible import UserRejectObservation
from openhands.sdk.tool.schema import ActionBase, MCPActionBase, ObservationBase
from openhands.sdk.utils.pydantic_utils import discriminated_union


if TYPE_CHECKING:
    Action = ActionBase
    Observation = ObservationBase
else:
    Action = discriminated_union(MCPActionBase)
    Observation = discriminated_union(UserRejectObservation)
