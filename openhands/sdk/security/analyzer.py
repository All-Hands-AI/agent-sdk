"""Security analyzer base class for OpenHands Agent SDK."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional

from openhands.sdk.logger import get_logger
from openhands.sdk.security.risk import ActionSecurityRisk


if TYPE_CHECKING:
    from openhands.sdk.event import Event
    from openhands.sdk.tool.schema import ActionBase

logger = get_logger(__name__)


class SecurityAnalyzer(ABC):
    """Abstract base class for security analyzers.

    Security analyzers evaluate the risk of actions before they are executed
    and can influence the conversation flow based on security policies.

    This is adapted from OpenHands SecurityAnalyzer but designed to work
    with the agent-sdk's conversation-based architecture.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the security analyzer.

        Args:
            **kwargs: Additional configuration parameters for the analyzer
        """
        self.config = kwargs
        logger.info(f"Initialized {self.__class__.__name__} security analyzer")

    @abstractmethod
    async def security_risk(self, action: "ActionBase") -> ActionSecurityRisk:
        """Evaluate the security risk of an action.

        This is the core method that analyzes an action and returns its risk level.
        Implementations should examine the action's content, context, and potential
        impact to determine the appropriate risk level.

        Args:
            action: The action to analyze for security risks

        Returns:
            ActionSecurityRisk enum indicating the risk level
        """
        pass

    @abstractmethod
    async def handle_api_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle API requests for security analyzer configuration.

        This allows the security analyzer to expose configuration endpoints
        that can be used by frontends or other systems to manage settings.

        Args:
            request_data: Dictionary containing request data

        Returns:
            Dictionary containing response data
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources used by the security analyzer.

        This method should be called when the analyzer is no longer needed
        to properly clean up any resources (connections, files, etc.).
        """
        pass

    async def analyze_event(self, event: "Event") -> Optional[ActionSecurityRisk]:
        """Analyze an event for security risks.

        This is a convenience method that checks if the event is an action
        and calls security_risk() if it is. Non-action events return None.

        Args:
            event: The event to analyze

        Returns:
            ActionSecurityRisk if event is an action, None otherwise
        """
        # Import here to avoid circular imports
        from openhands.sdk.tool.schema import ActionBase

        if isinstance(event, ActionBase):
            return await self.security_risk(event)
        return None

    def should_require_confirmation(
        self, risk: ActionSecurityRisk, confirmation_mode: bool = False
    ) -> bool:
        """Determine if an action should require user confirmation.

        This implements the default confirmation logic based on risk level
        and confirmation mode settings.

        Args:
            risk: The security risk level of the action
            confirmation_mode: Whether confirmation mode is enabled

        Returns:
            True if confirmation is required, False otherwise
        """
        if risk == ActionSecurityRisk.HIGH:
            # HIGH risk actions always require confirmation
            return True
        elif risk == ActionSecurityRisk.UNKNOWN and not confirmation_mode:
            # UNKNOWN risk requires confirmation if no security analyzer is configured
            return True
        elif confirmation_mode:
            # In confirmation mode, all actions require confirmation
            return True
        else:
            # LOW and MEDIUM risk actions don't require confirmation by default
            return False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(config={self.config})"
