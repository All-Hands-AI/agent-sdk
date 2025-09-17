"""Type annotations for serialization / deserialization"""

from typing import TYPE_CHECKING

from openhands.sdk.context.condenser.base import CondenserBase, RollingCondenser
from openhands.sdk.context.condenser.no_op_condenser import NoOpCondenser
from openhands.sdk.context.condenser.pipeline_condenser import PipelineCondenser
from openhands.sdk.utils.pydantic_utils import discriminated_union


if TYPE_CHECKING:
    Condenser = CondenserBase
else:
    Condenser = discriminated_union(RollingCondenser, NoOpCondenser, PipelineCondenser)
