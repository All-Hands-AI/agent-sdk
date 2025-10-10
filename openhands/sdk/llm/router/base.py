from abc import abstractmethod
from collections.abc import Sequence

from pydantic import (
    Field,
    field_validator,
    model_validator,
)

from openhands.sdk.llm.llm import LLM, LLMBase
from openhands.sdk.llm.llm_response import LLMResponse
from openhands.sdk.llm.message import Message
from openhands.sdk.logger import get_logger
from openhands.sdk.tool.tool import ToolBase
from openhands.sdk.utils.pydantic_diff import pretty_pydantic_diff


logger = get_logger(__name__)


class RouterLLM(LLM):
    """
    Base class for multiple LLM acting as a unified LLM.
    This class provides a foundation for implementing model routing by
    inheriting from LLM, allowing routers to work with multiple underlying
    LLM models while presenting a unified LLM interface to consumers.
    Key features:
    - Works with multiple LLMs configured via llms_for_routing
    - Delegates all other operations/properties to the selected LLM
    - Provides routing interface through select_llm() method
    """

    router_name: str = Field(default="base_router", description="Name of the router")
    llms_for_routing: dict[str, LLMBase] = Field(
        default_factory=dict
    )  # Mapping of LLM name to LLM instance for routing

    active_llm_identifier: str | None = Field(
        default=None, description="Currently selected LLM's identifier"
    )

    @field_validator("llms_for_routing")
    @classmethod
    def validate_llms_not_empty(cls, v):
        if not v:
            raise ValueError(
                "llms_for_routing cannot be empty - at least one LLM must be provided"
            )
        return v

    def completion(
        self,
        messages: list[Message],
        tools: Sequence[ToolBase] | None = None,
        return_metrics: bool = False,
        add_security_risk_prediction: bool = False,
        **kwargs,
    ) -> LLMResponse:
        """
        This method intercepts completion calls and routes them to the appropriate
        underlying LLM based on the routing logic implemented in select_llm().
        """
        # Select appropriate LLM
        self.active_llm_identifier = self.select_llm(messages)
        active_llm = self.llms_for_routing[self.active_llm_identifier]

        logger.info(f"RouterLLM routing to {self.active_llm_identifier}...")

        # Delegate to selected LLM
        return active_llm.completion(
            messages=messages,
            tools=tools,
            return_metrics=return_metrics,
            add_security_risk_prediction=add_security_risk_prediction,
            **kwargs,
        )

    @abstractmethod
    def select_llm(self, messages: list[Message]) -> str:
        """Select which LLM to use based on messages and events.

        This method implements the core routing logic for the RouterLLM.
        Subclasses should analyze the provided messages to determine which
        LLM from llms_for_routing is most appropriate for handling the request.

        Args:
            messages: List of messages in the conversation that can be used
                     to inform the routing decision.

        Returns:
            The key/name of the LLM to use from llms_for_routing dictionary.
        """

    def __getattr__(self, name):
        """Delegate other attributes/methods to the active LLM."""
        fallback_llm = next(iter(self.llms_for_routing.values()))
        logger.info(f"RouterLLM: No active LLM, using first LLM for attribute '{name}'")
        return getattr(fallback_llm, name)

    def __str__(self) -> str:
        """String representation of the router."""
        return f"{self.__class__.__name__}(llms={list(self.llms_for_routing.keys())})"

    @model_validator(mode="before")
    @classmethod
    def set_placeholder_model(cls, data):
        """Guarantee `model` exists before LLM base validation runs."""
        if not isinstance(data, dict):
            return data
        d = dict(data)

        # In router, we don't need a model name to be specified
        if "model" not in d or not d["model"]:
            d["model"] = d.get("router_name", "router")

        return d

    def resolve_diff_from_deserialized(self, persisted: "LLMBase") -> "LLMBase":
        """Resolve differences between a deserialized RouterLLM and the current
        instance.

        This method handles the reconciliation of nested LLMs in llms_for_routing,
        ensuring that secret fields (like api_key) are properly restored from the
        runtime instance to the deserialized instance.

        Args:
            persisted: The deserialized RouterLLM instance from persistence

        Returns:
            A new RouterLLM instance equivalent to `persisted` but with secrets
            from the runtime instance properly restored in all nested LLMs

        Raises:
            ValueError: If the classes don't match or if reconciliation fails
        """
        # If persisted is not a RouterLLM at all, this is an incompatible state
        if not isinstance(persisted, RouterLLM):
            # Check if the persisted data even has the router fields
            persisted_dict = persisted.model_dump()
            if "llms_for_routing" not in persisted_dict:
                raise ValueError(
                    f"Cannot resolve_diff_from_deserialized: persisted LLM is not a "
                    "RouterLLM and doesn't contain router data. Got "
                    f"{persisted.__class__}"
                )
            # Try to reconstruct as the correct RouterLLM subclass
            persisted = self.__class__.model_validate(persisted_dict)

        # Check classes match exactly
        if type(persisted) is not type(self):
            raise ValueError(
                f"Cannot resolve_diff_from_deserialized between {type(self)} "
                f"and {type(persisted)}"
            )

        # Reconcile each nested LLM in llms_for_routing
        reconciled_llms = {}
        for name, persisted_llm in persisted.llms_for_routing.items():
            if name not in self.llms_for_routing:
                raise ValueError(
                    f"LLM '{name}' found in persisted state but not in runtime router"
                )
            runtime_llm = self.llms_for_routing[name]
            reconciled_llms[name] = runtime_llm.resolve_diff_from_deserialized(
                persisted_llm
            )

        # Check for LLMs in runtime that aren't in persisted state
        for name in self.llms_for_routing:
            if name not in persisted.llms_for_routing:
                raise ValueError(
                    f"LLM '{name}' found in runtime router but not in persisted state"
                )

        # Create reconciled router with updated nested LLMs
        # Note: active_llm is runtime state and should not be persisted/restored
        reconciled = persisted.model_copy(update={"llms_for_routing": reconciled_llms})

        # Validate that the reconciled router matches the runtime router
        runtime_dump = self.model_dump(exclude_none=True)
        reconciled_dump = reconciled.model_dump(exclude_none=True)

        if runtime_dump != reconciled_dump:
            raise ValueError(
                "The RouterLLM provided is different from the one in persisted state.\n"
                f"Diff: {pretty_pydantic_diff(self, reconciled)}"
            )

        return reconciled
