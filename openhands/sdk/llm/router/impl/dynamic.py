"""
Dynamic Router implementation for OpenHands SDK.

This router allows users to switch to entirely new LLMs without pre-configuring them,
with full serialization/deserialization support.
"""

from pydantic import model_validator

from openhands.sdk.llm import LLMBase
from openhands.sdk.llm.message import Message
from openhands.sdk.llm.router.base import RouterLLM
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


class DynamicRouter(RouterLLM):
    """
    A RouterLLM that supports dynamic LLM creation and switching.

    Users can switch to entirely new LLMs without pre-configuring them.
    The router maintains both ONE pre-configured LLM (primary) and
    dynamically created ones.
    """

    PRIMARY_MODEL_KEY: str = "primary"

    router_name: str = "dynamic_router"
    manual_selection: str | None = None

    def select_llm(self, messages: list[Message]) -> str:
        """
        Select LLM based on manual selection or fallback to first available.

        Args:
            messages: List of messages (not used in manual selection)

        Returns:
            Name of the selected LLM

        Raises:
            ValueError: If no LLMs are available for routing
        """
        if self.manual_selection:
            return self.manual_selection

        # Fallback to first available LLM
        if self.llms_for_routing:
            return next(iter(self.llms_for_routing.keys()))

        raise ValueError("No LLMs available for routing")

    def switch_to_llm(
        self,
        identifier: str,
        llm: LLMBase | None = None,
    ) -> bool:
        """
        Switch to an LLM, creating it dynamically if it doesn't exist.

        Args:
            identifier: Name to discriminate the LLM instance
            llm: The LLM instance to switch to, can be None if switching to existing LLM
        Returns:
            True if switch was successful, False otherwise

        Example:
            # Switch to existing LLM
            router.switch_to_llm("gpt4")

            # Create and switch to new LLM
            router.switch_to_llm(
                "claude",
                LLM(
                    service_id="claude",
                    model="claude-3-5-sonnet-20241022",
                    api_key="sk-...",
                    temperature=0.7
                )
            )
        """
        try:
            # If LLM already exists, just switch to it
            if identifier in self.llms_for_routing:
                self.manual_selection = identifier
                self.active_llm_identifier = self.manual_selection
                logger.info(f"Switched to existing LLM: {identifier}")
                return True

            # Create new LLM dynamically
            if not llm:
                logger.error(
                    f"LLM instance must be specified to create new LLM: {identifier}"
                )
                return False

            # Add to routing dict
            self.llms_for_routing[identifier] = llm

            # Switch to the new LLM
            self.manual_selection = identifier
            self.active_llm_identifier = self.manual_selection

            logger.info(f"Created and switched to new LLM: {identifier} ({llm.model})")
            return True

        except Exception as e:
            logger.error(f"Failed to switch to LLM {identifier}: {e}")
            return False

    def remove_llm(self, identifier: str) -> bool:
        """
        Remove a dynamically created LLM.

        Note: This only removes dynamically created LLMs, not pre-configured ones.

        Args:
            identifier: Name of the LLM to remove

        Returns:
            True if LLM was removed, False if it wasn't a dynamic LLM
        """
        if identifier == self.PRIMARY_MODEL_KEY:
            logger.warning(f"Cannot remove primary LLM: {identifier}")
            return False

        if identifier in self.llms_for_routing:
            self.llms_for_routing.pop(identifier, None)

            # Clear manual selection if it was the removed LLM
            if self.manual_selection == identifier:
                self.manual_selection = None
                self.active_llm_identifier = None

            logger.info(f"Removed dynamic LLM: {identifier}")
            return True

        logger.warning(f"Cannot remove LLM {identifier}: not existing")
        return False

    @model_validator(mode="after")
    def _validate_llms_for_routing(self) -> "DynamicRouter":
        """Ensure required models are present in llms_for_routing."""
        if self.PRIMARY_MODEL_KEY not in self.llms_for_routing:
            raise ValueError(
                f"Primary LLM key '{self.PRIMARY_MODEL_KEY}' not found"
                " in llms_for_routing."
            )
        return self
