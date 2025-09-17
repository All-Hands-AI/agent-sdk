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
    restored_metrics: dict[str, Metrics] = Field(
        default_factory=dict,
        description="Metrics restored from storage before services are registered",
    )

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

    @property
    def metrics_file_name(self) -> str:
        return self._metrics_file_name

    def maybe_restore_metrics(self):
        # Note: With Pydantic integration, this method will be deprecated
        # as restoration will be handled by ConversationState deserialization
        if not self.file_store or not self.conversation_id:
            return

        # For backward compatibility, still try to restore from old pickle format
        try:
            import base64
            import pickle

            encoded = self.file_store.read(self.metrics_file_name)
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

        if service_id in self.restored_metrics:
            llm.restore_metrics(self.restored_metrics[service_id].deep_copy())
            del self.restored_metrics[service_id]

        if llm.metrics:
            self.service_to_metrics[service_id] = llm.metrics

    def merge(self, conversation_stats: "ConversationStats") -> dict[str, Metrics]:
        """
        Merge restored metrics from another ConversationStats into this one.

        Important:
        - This method is intended to be used immediately after restoring metrics from
          storage, before any LLM services are registered. In that state, only
          `restored_metrics` should contain entries and `service_to_metrics` should
          be empty. If either side has entries in `service_to_metrics`, we log an
          error but continue execution.

        Behavior:
        - Drop entries with zero accumulated_cost from both `restored_metrics` dicts
          (self and incoming) before merging.
        - Merge only `restored_metrics`. For duplicate keys, the incoming
          `conversation_stats.restored_metrics` overwrites existing entries.
        - Do NOT merge `service_to_metrics` here.
        """

        # If either side has active service metrics, log an error but proceed
        if self.service_to_metrics or conversation_stats.service_to_metrics:
            logger.error(
                "merge_and_save should be used only when service_to_metrics are empty; "
                "found active service metrics during merge. Proceeding anyway.",
                extra={
                    "conversation_id": self.conversation_id,
                    "self_service_to_metrics_keys": list(
                        self.service_to_metrics.keys()
                    ),
                    "incoming_service_to_metrics_keys": list(
                        conversation_stats.service_to_metrics.keys()
                    ),
                },
            )

        # Drop zero-cost entries from restored metrics only
        def _drop_zero_cost(d: dict[str, Metrics]) -> None:
            to_delete = [
                k for k, v in d.items() if getattr(v, "accumulated_cost", 0) == 0
            ]
            for k in to_delete:
                del d[k]

        _drop_zero_cost(self.restored_metrics)
        _drop_zero_cost(conversation_stats.restored_metrics)

        # Merge restored metrics, allowing incoming to overwrite
        self.restored_metrics.update(conversation_stats.restored_metrics)

        duplicate_services = set(self.restored_metrics.keys()) & set(
            self.service_to_metrics.keys()
        )
        if duplicate_services:
            logger.error(
                "Duplicate service IDs found between restored"
                f"and service metrics: {duplicate_services}. "
                "This should not happen as registered services"
                "should be removed from restored_metrics. "
                "Prefer service_to_metrics values for duplicates.",
                extra={
                    "conversation_id": self.conversation_id,
                    "duplicate_services": list(duplicate_services),
                },
            )

        # Combine both restored metrics and service metrics to avoid data loss
        # Start with restored metrics (for services not yet registered)
        combined_metrics = self.restored_metrics.copy()

        # Add service metrics (for registered services)
        # Since we checked for duplicates above, this is safe
        combined_metrics.update(self.service_to_metrics)

        logger.info(
            "Merged conversation stats",
            extra={"conversation_id": self.conversation_id},
        )

        return combined_metrics
