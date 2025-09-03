from typing import Callable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from openhands.core.config import LLMConfig
from openhands.core.llm.llm import LLM
from openhands.core.logger import get_logger


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

    def _create_new_llm(
        self, service_id: str, config: LLMConfig, with_listener: bool = True
    ) -> LLM:
        """Create a new LLM instance and register it."""
        if with_listener:
            llm = LLM(
                service_id=service_id, config=config, retry_listener=self.retry_listener
            )
        else:
            llm = LLM(service_id=service_id, config=config)
        self.service_to_llm[service_id] = llm
        self.notify(RegistryEvent(llm=llm, service_id=service_id))
        return llm

    def request_extraneous_completion(
        self, service_id: str, llm_config: LLMConfig, messages: list[dict[str, str]]
    ) -> str:
        """Request a completion from an LLM, creating it if necessary.

        Args:
            service_id: Unique identifier for the LLM service.
            llm_config: Configuration for the LLM.
            messages: Messages to send to the LLM.

        Returns:
            The completion response as a string.
        """
        logger.info(f"Requesting completion from service: {service_id}")
        if service_id not in self.service_to_llm:
            self._create_new_llm(
                config=llm_config, service_id=service_id, with_listener=False
            )

        llm = self.service_to_llm[service_id]
        response = llm.completion(messages=messages)
        return response.choices[0].message.content.strip()

    def get_llm(
        self,
        service_id: str,
        config: LLMConfig | None = None,
    ) -> LLM:
        """Get or create an LLM instance for the given service ID.

        Args:
            service_id: Unique identifier for the LLM service.
            config: Configuration for the LLM. Required if creating a new LLM.

        Returns:
            The LLM instance.

        Raises:
            ValueError: If trying to use the same service_id with different config.
        """
        logger.info(
            f"[LLM registry {self.registry_id}]: Getting LLM for service {service_id}"
        )

        # Check if we're trying to switch configs for existing LLM
        if (
            service_id in self.service_to_llm
            and self.service_to_llm[service_id].config != config
        ):
            raise ValueError(
                f"Requesting same service ID {service_id} with"
                " different config, use a new service ID"
            )

        if service_id in self.service_to_llm:
            return self.service_to_llm[service_id]

        if not config:
            raise ValueError("Requesting new LLM without specifying LLM config")

        return self._create_new_llm(config=config, service_id=service_id)

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

    def list_services(self) -> list[str]:
        """List all registered service IDs.

        Returns:
            List of service IDs currently in the registry.
        """
        return list(self.service_to_llm.keys())
