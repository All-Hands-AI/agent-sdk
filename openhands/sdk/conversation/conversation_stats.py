from typing import Optional

from pydantic import BaseModel, Field, PrivateAttr

from openhands.sdk.conversation.types import ConversationID
from openhands.sdk.io.base import FileStore
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

    # Private attributes that won't be serialized
    _file_store: Optional[FileStore] = PrivateAttr(default=None)
    _conversation_id: Optional[ConversationID] = PrivateAttr(default=None)
    _metrics_file_name: str = PrivateAttr(default="conversation_stats.pkl")

    def __init__(
        self,
        file_store: FileStore | None = None,
        conversation_id: ConversationID | None = None,
    ):
        self._file_store = file_store
        self._conversation_id = conversation_id

        # Always attempt to restore registry if it exists
        self.maybe_restore_metrics()

    @property
    def file_store(self) -> Optional[FileStore]:
        return self._file_store

    @property
    def conversation_id(self) -> Optional[ConversationID]:
        return self._conversation_id

    def maybe_restore_metrics(self):
        # Used for backwards compatability with existing conversations
        # that store conversation stats in a pickled object

        # Note: future restorations will be handled by ConversationState deserialization

        if not self.file_store or not self.conversation_id:
            return

        # TODO: do we need restored_metrics? Does LLM object combine completion costs
        # or a conversation callback?

        try:
            import base64
            import pickle

            encoded = self.file_store.read(self._metrics_file_name)
            pickled = base64.b64decode(encoded)
            self.restored_metrics = pickle.loads(pickled)
            logger.info(f"restored metrics: {self.conversation_id}")
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Failed to restore metrics from pickle format: {e}")

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
        service_id = event.service_id

        # Service costs exists but has not been restored yet
        if (
            service_id in self.service_to_metrics
            and service_id not in self._restored_services
        ):
            llm.restore_metrics(self.service_to_metrics[service_id])

        # Service is new, track its metrics
        if service_id not in self.service_to_metrics and llm.metrics:
            self.service_to_metrics[service_id] = llm.metrics
