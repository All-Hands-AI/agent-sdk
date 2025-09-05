from typing import Callable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from openhands.sdk.llm.llm import LLM
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


class RegistryEvent(BaseModel):
    llm: LLM
    service_id: str

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


class LLMRegistry:
    """A minimal LLM registry for managing LLM instances by service ID.

    This registry provides a simple way to manage multiple LLM instances,
    avoiding the need to recreate LLMs with the same configuration.
    """

    def __init__(
        self,
        retry_listener: Callable[[int, int], None] | None = None,
    ):
        """Initialize the LLM registry.

        Args:
            retry_listener: Optional callback for retry events.
        """
        self.registry_id = str(uuid4())
        self.retry_listener = retry_listener
        self.service_to_llm: dict[str, LLM] = {}
        self.subscriber: Callable[[RegistryEvent], None] | None = None

    def subscribe(self, callback: Callable[[RegistryEvent], None]) -> None:
        """Subscribe to registry events.

        Args:
            callback: Function to call when LLMs are created or updated.
        """
        self.subscriber = callback

    def notify(self, event: RegistryEvent) -> None:
        """Notify subscribers of registry events.

        Args:
            event: The registry event to notify about.
        """
        if self.subscriber:
            try:
                self.subscriber(event)
            except Exception as e:
                logger.warning(f"Failed to emit event: {e}")

    def add(self, service_id: str, llm: LLM) -> None:
        """Add an LLM instance to the registry.

        Args:
            service_id: Unique identifier for the LLM service.
            llm: The LLM instance to register.

        Raises:
            ValueError: If service_id already exists in the registry.
        """
        if service_id in self.service_to_llm:
            raise ValueError(
                f"Service ID '{service_id}' already exists in registry. "
                "Use a different service_id or call get() to retrieve the existing LLM."
            )

        # Set the service_id on the LLM instance
        llm.service_id = service_id
        self.service_to_llm[service_id] = llm
        self.notify(RegistryEvent(llm=llm, service_id=service_id))
        logger.info(
            f"[LLM registry {self.registry_id}]: Added LLM for service {service_id}"
        )

    def get(self, service_id: str) -> LLM:
        """Get an LLM instance from the registry.

        Args:
            service_id: Unique identifier for the LLM service.

        Returns:
            The LLM instance.

        Raises:
            KeyError: If service_id is not found in the registry.
        """
        if service_id not in self.service_to_llm:
            raise KeyError(
                f"Service ID '{service_id}' not found in registry. "
                "Use add() to register an LLM first."
            )

        logger.info(
            f"[LLM registry {self.registry_id}]: Retrieved LLM for service {service_id}"
        )
        return self.service_to_llm[service_id]

    def list_services(self) -> list[str]:
        """List all registered service IDs.

        Returns:
            List of service IDs currently in the registry.
        """
        return list(self.service_to_llm.keys())
