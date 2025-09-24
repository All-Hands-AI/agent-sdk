from pydantic import BaseModel, Field, PrivateAttr

from openhands.sdk.llm.llm_registry import RegistryEvent
from openhands.sdk.llm.utils.metrics import Metrics
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


class ConversationStats(BaseModel):
    # Public fields that will be serialized
    service_to_metrics: dict[str, Metrics] = Field(
        default_factory=dict,
        description="Active service metrics tracked by the registry",
    )

    _restored_services: set = PrivateAttr(default_factory=set)

    def get_combined_metrics(self) -> Metrics:
        total_metrics = Metrics()
        for metrics in self.service_to_metrics.values():
            total_metrics.merge(metrics)
        return total_metrics

    def get_metrics_for_service(self, service_id: str) -> Metrics:
        if service_id not in self.service_to_metrics:
            raise Exception(f"LLM service does not exist {service_id}")

        return self.service_to_metrics[service_id]

    def register_llm(self, event: RegistryEvent):
        # Listen for llm creations and track their metrics
        llm = event.llm
        service_id = llm.service_id

        # Service costs exists but has not been restored yet
        if (
            service_id in self.service_to_metrics
            and service_id not in self._restored_services
        ):
            llm.restore_metrics(self.service_to_metrics[service_id])
            self._restored_services.add(service_id)

        # Service is new, track its metrics
        if service_id not in self.service_to_metrics and llm.metrics:
            self.service_to_metrics[service_id] = llm.metrics
