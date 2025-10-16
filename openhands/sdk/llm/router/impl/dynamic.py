"""
Dynamic Router implementation for OpenHands SDK.

This router allows users to switch to entirely new LLMs without pre-configuring them,
with full serialization/deserialization support.
"""

from pydantic import model_validator

from openhands.sdk.llm.message import Message
from openhands.sdk.llm.router.base import RouterLLM
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


class DynamicRouter(RouterLLM):
    """
    A RouterLLM that supports manual LLM switching.
    Users need to provide all LLMs they want to switch to at initialization.
    """

    PRIMARY_MODEL_KEY: str = "primary"

    router_name: str = "dynamic_router"
    manual_selection: str | None = None

    def select_llm(self, messages: list[Message]) -> str:  # noqa: ARG002
        """
        Select LLM based on manual selection or fallback to first available.

        Args:
            messages: List of messages (not used in manual selection)

        Returns:
            Name of the selected LLM
        """
        if self.manual_selection:
            return self.manual_selection

        # Use the primary LLM if no manual selection
        return self.PRIMARY_MODEL_KEY

    def switch_to_llm(
        self,
        identifier: str,
    ) -> bool:
        """
        Switch to an LLM by identifier.

        Args:
            identifier: Name to discriminate the LLM instance
        Returns:
            True if switch was successful, False otherwise
        """
        if identifier not in self.llms_for_routing:
            logger.warning(f"Failed to switch to LLM {identifier}: not found")
            return False

        self.manual_selection = identifier
        self.active_llm_identifier = self.manual_selection
        logger.info(f"Switched to existing LLM: {identifier}")
        return True

    @model_validator(mode="after")
    def _validate_llms_for_routing(self) -> "DynamicRouter":
        """Ensure required models are present in llms_for_routing."""
        if self.PRIMARY_MODEL_KEY not in self.llms_for_routing:
            raise ValueError(
                f"Primary LLM key '{self.PRIMARY_MODEL_KEY}' not found"
                " in llms_for_routing."
            )
        return self
