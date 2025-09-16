"""Security analyzer base class for OpenHands Agent SDK."""

from abc import ABC, abstractmethod
from typing import Any

from openhands.sdk.conversation import Conversation
from openhands.sdk.event import Event
from openhands.sdk.event.llm_convertible import ActionEvent
from openhands.sdk.event.utils import get_unmatched_actions
from openhands.sdk.logger import get_logger
from openhands.sdk.security.risk import ActionSecurityRisk
from openhands.sdk.tool.schema import Action


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
    async def security_risk(self, action: Action) -> ActionSecurityRisk:
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
    async def handle_api_request(self, request_data: dict[str, Any]) -> dict[str, Any]:
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

    async def analyze_event(self, event: Event) -> ActionSecurityRisk | None:
        """Analyze an event for security risks.

        This is a convenience method that checks if the event is an action
        and calls security_risk() if it is. Non-action events return None.

        Args:
            event: The event to analyze

        Returns:
            ActionSecurityRisk if event is an action, None otherwise
        """
        if isinstance(event, ActionEvent):
            return await self.security_risk(event.action)
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

    async def analyze_pending_actions(
        self, conversation: Conversation
    ) -> list[tuple[ActionEvent, ActionSecurityRisk]]:
        """Analyze all pending actions in a conversation.

        This method gets all unmatched actions from the conversation state
        and analyzes each one for security risks.

        Args:
            conversation: The conversation to analyze

        Returns:
            List of tuples containing (action, risk_level) for each pending action
        """
        pending_actions = get_unmatched_actions(conversation.state.events)
        analyzed_actions = []

        for action_event in pending_actions:
            try:
                risk = await self.security_risk(action_event.action)
                analyzed_actions.append((action_event, risk))
                logger.debug(f"Action {action_event} analyzed with risk level: {risk}")
            except Exception as e:
                logger.error(f"Error analyzing action {action_event}: {e}")
                # Default to HIGH risk on analysis error for safety
                analyzed_actions.append((action_event, ActionSecurityRisk.HIGH))

        return analyzed_actions

    async def should_require_confirmation_for_conversation(
        self, conversation: Conversation
    ) -> bool:
        """Determine if any pending actions require confirmation.

        This method analyzes all pending actions and determines if any of them
        require user confirmation based on their risk levels and the conversation's
        confirmation mode setting.

        Args:
            conversation: The conversation to check

        Returns:
            True if confirmation is required, False otherwise
        """
        analyzed_actions = await self.analyze_pending_actions(conversation)
        confirmation_mode = getattr(conversation, "_confirmation_mode", False)

        for action, risk in analyzed_actions:
            if self.should_require_confirmation(risk, confirmation_mode):
                logger.info(f"Action {action} requires confirmation (risk: {risk})")
                return True

        return False

    async def get_risk_summary(self, conversation: Conversation) -> dict:
        """Get a summary of security risks for pending actions.

        This provides a detailed breakdown of risk levels for all pending actions,
        useful for displaying security information to users.

        Args:
            conversation: The conversation to analyze

        Returns:
            Dictionary containing risk summary information
        """
        analyzed_actions = await self.analyze_pending_actions(conversation)

        risk_counts = {
            ActionSecurityRisk.LOW: 0,
            ActionSecurityRisk.MEDIUM: 0,
            ActionSecurityRisk.HIGH: 0,
            ActionSecurityRisk.UNKNOWN: 0,
        }

        action_details = []

        for action, risk in analyzed_actions:
            risk_counts[risk] += 1
            action_details.append(
                {
                    "action": str(action),
                    "tool_name": getattr(action, "tool_name", "unknown"),
                    "risk": str(risk),
                    "risk_description": risk.description,
                }
            )

        return {
            "total_actions": len(analyzed_actions),
            "risk_counts": {str(risk): count for risk, count in risk_counts.items()},
            "highest_risk": max(risk for _, risk in analyzed_actions)
            if analyzed_actions
            else ActionSecurityRisk.LOW,
            "action_details": action_details,
        }
