"""Type annotations for serialization / deserialization"""

from typing import TYPE_CHECKING

from openhands.sdk.agent.agent import Agent
from openhands.sdk.agent.base import AgentBase
from openhands.sdk.utils.pydantic_utils import discriminated_union


if TYPE_CHECKING:
    AgentType = AgentBase
else:
    AgentType = discriminated_union(Agent)
