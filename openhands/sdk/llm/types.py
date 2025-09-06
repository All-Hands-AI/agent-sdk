from typing import Optional

from litellm.types.utils import ModelResponse
from pydantic import Field

from openhands.sdk.llm.utils.metrics import Metrics


class ModelResponseWithMetrics(ModelResponse):
    """ModelResponse extended with telemetry metrics.
    
    This class inherits from ModelResponse and adds metrics collected
    from telemetry during LLM completion.
    """
    
    metrics: Optional[Metrics] = Field(
        default=None, 
        description="Telemetry metrics for this response"
    )
