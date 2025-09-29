"""
Dynamic Router implementation for OpenHands SDK.

This router allows users to switch to entirely new LLMs without pre-configuring them,
with full serialization/deserialization support.
"""

from typing import Any

from pydantic import Field

from openhands.sdk.llm import LLM
from openhands.sdk.llm.message import Message
from openhands.sdk.llm.router.base import RouterLLM
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


class DynamicRouter(RouterLLM):
    """
    A RouterLLM that supports dynamic LLM creation and switching.

    Users can switch to entirely new LLMs without pre-configuring them.
    The router maintains both pre-configured LLMs and dynamically created ones,
    with full serialization/deserialization support.
    """

    router_name: str = "dynamic_router"
    manual_selection: str | None = None

    # Store LLM configurations for dynamic creation and serialization
    dynamic_llm_configs: dict[str, dict[str, Any]] = Field(default_factory=dict)

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
            # Ensure the manually selected LLM exists
            self._ensure_llm_exists(self.manual_selection)
            return self.manual_selection

        # Fallback to first available LLM
        if self.llms_for_routing:
            return next(iter(self.llms_for_routing.keys()))

        raise ValueError("No LLMs available for routing")

    def switch_to_llm(
        self,
        llm_name: str,
        model: str | None = None,
        api_key: str | None = None,
        **kwargs,
    ) -> bool:
        """
        Switch to an LLM, creating it dynamically if it doesn't exist.

        Args:
            llm_name: Name/identifier for the LLM
            model: Model name (e.g., "gpt-4o", "claude-3-5-sonnet-20241022")
                  Required when creating a new LLM
            api_key: API key for the model
            **kwargs: Additional LLM configuration parameters

        Returns:
            True if switch was successful, False otherwise

        Example:
            # Switch to existing LLM
            router.switch_to_llm("existing_llm")

            # Create and switch to new LLM
            router.switch_to_llm(
                "claude",
                model="claude-3-5-sonnet-20241022",
                api_key="sk-...",
                temperature=0.7
            )
        """
        try:
            # If LLM already exists, just switch to it
            if llm_name in self.llms_for_routing:
                self.manual_selection = llm_name
                self.active_llm = self.llms_for_routing[llm_name]
                logger.info(f"Switched to existing LLM: {llm_name}")
                return True

            # Check if we have a stored config for this LLM
            if llm_name in self.dynamic_llm_configs:
                self._ensure_llm_exists(llm_name)
                self.manual_selection = llm_name
                self.active_llm = self.llms_for_routing[llm_name]
                logger.info(f"Switched to LLM from stored config: {llm_name}")
                return True

            # Create new LLM dynamically
            if not model:
                logger.error(f"Model must be specified to create new LLM: {llm_name}")
                return False

            # Store configuration for serialization
            llm_config = {"model": model, "service_id": f"dynamic_{llm_name}", **kwargs}

            # Add API key if provided (will be handled by OVERRIDE_ON_SERIALIZE)
            if api_key:
                llm_config["api_key"] = api_key

            # Create the LLM instance
            new_llm = LLM(**llm_config)

            # Add to routing table and store config
            self.llms_for_routing[llm_name] = new_llm
            self.dynamic_llm_configs[llm_name] = llm_config

            # Switch to the new LLM
            self.manual_selection = llm_name
            self.active_llm = new_llm

            logger.info(f"Created and switched to new LLM: {llm_name} ({model})")
            return True

        except Exception as e:
            logger.error(f"Failed to switch to LLM {llm_name}: {e}")
            return False

    def _ensure_llm_exists(self, llm_name: str):
        """
        Ensure an LLM exists, recreating it from config if necessary.

        Args:
            llm_name: Name of the LLM to ensure exists
        """
        if (
            llm_name not in self.llms_for_routing
            and llm_name in self.dynamic_llm_configs
        ):
            # Recreate LLM from stored config
            config = self.dynamic_llm_configs[llm_name]
            self.llms_for_routing[llm_name] = LLM(**config)
            logger.info(f"Recreated LLM from config: {llm_name}")

    def get_available_llms(self) -> dict[str, str]:
        """
        Get all available LLMs (both pre-configured and dynamic).

        Returns:
            Dictionary mapping LLM names to their model names

        Example:
            {
                "gpt4": "gpt-4o",
                "claude": "claude-3-5-sonnet-20241022",
                "gemini": "gemini-1.5-pro"
            }
        """
        result = {}

        # Add existing LLMs
        for name, llm in self.llms_for_routing.items():
            result[name] = llm.model

        # Add dynamic LLMs that might not be instantiated yet
        for name, config in self.dynamic_llm_configs.items():
            if name not in result:
                result[name] = config["model"]

        return result

    def remove_llm(self, llm_name: str) -> bool:
        """
        Remove a dynamically created LLM.

        Note: This only removes dynamically created LLMs, not pre-configured ones.

        Args:
            llm_name: Name of the LLM to remove

        Returns:
            True if LLM was removed, False if it wasn't a dynamic LLM
        """
        if llm_name in self.dynamic_llm_configs:
            # Remove from both places
            self.dynamic_llm_configs.pop(llm_name, None)
            self.llms_for_routing.pop(llm_name, None)

            # Clear manual selection if it was the removed LLM
            if self.manual_selection == llm_name:
                self.manual_selection = None
                self.active_llm = None

            logger.info(f"Removed dynamic LLM: {llm_name}")
            return True

        logger.warning(f"Cannot remove LLM {llm_name}: not a dynamic LLM")
        return False

    def get_current_llm_name(self) -> str | None:
        """
        Get the name of the currently selected LLM.

        Returns:
            Name of current LLM or None if no LLM is selected
        """
        return self.manual_selection

    def resolve_diff_from_deserialized(self, persisted: "LLM") -> "LLM":
        """
        Custom resolve_diff_from_deserialized to handle dynamic LLMs.

        This ensures that:
        1. API keys are preserved from runtime instance
        2. Dynamic LLM configs are properly restored
        3. LLM instances are recreated as needed
        4. Pre-configured LLMs use the parent's resolution logic
        5. Handles case where persisted was deserialized as regular LLM

        Args:
            persisted: The deserialized router instance (or LLM that should be a router)

        Returns:
            Reconciled router instance with proper state

        Raises:
            ValueError: If the persisted instance cannot be converted to DynamicRouter
        """
        # TODO:
        raise NotImplementedError("Implement custom diff resolution for DynamicRouter")
