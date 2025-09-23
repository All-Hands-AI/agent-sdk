from abc import ABC, abstractmethod

from openhands.sdk.event.base import LLMConvertibleEvent
from openhands.sdk.event.llm_convertible import ActionEvent
from openhands.sdk.event.types import EventID
from openhands.sdk.logger import get_logger
from openhands.sdk.security.risk import SecurityRisk
from openhands.sdk.utils.models import (
    DiscriminatedUnionMixin,
)


logger = get_logger(__name__)


class SecurityAnalyzerBase(DiscriminatedUnionMixin, ABC):
    """Abstract base class for security analyzers.

    Security analyzers evaluate the risk of actions before they are executed
    and can influence the conversation flow based on security policies.

    This is adapted from OpenHands SecurityAnalyzer but designed to work
    with the agent-sdk's conversation-based architecture.
    """

    @abstractmethod
    def analyze_pending_actions(
        self,
        current_context: list[LLMConvertibleEvent],
        pending_actions: list[ActionEvent],
    ) -> dict[EventID, SecurityRisk]:
        """Analyze all pending actions in a conversation.

        This method gets all unmatched actions from the conversation state
        and analyzes each one for security risks.

        Args:
            current_context: The current conversation context -- the events provided to
                the model when the pending actions were generated
            pending_actions: List of ActionEvents that are pending execution

        Returns:
            Dictionary mapping EventIDs to their corresponding security risk levels
        """
        pass


class PerActionSecurityAnalyzer(SecurityAnalyzerBase, ABC):
    """A security analyzer that uses a provided function to evaluate action risks.

    This allows for custom risk evaluation logic to be injected, making it flexible
    for different use cases.
    """

    @abstractmethod
    def security_risk(self, action: ActionEvent) -> SecurityRisk:
        """Evaluate the security risk of an ActionEvent.

        This is the core method that analyzes an ActionEvent and returns its risk level.
        Implementations should examine the action's content, context, and potential
        impact to determine the appropriate risk level.

        Args:
            action: The ActionEvent to analyze for security risks

        Returns:
            ActionSecurityRisk enum indicating the risk level
        """
        pass

    def analyze_pending_actions(
        self,
        current_context: list[LLMConvertibleEvent],
        pending_actions: list[ActionEvent],
    ) -> dict[EventID, SecurityRisk]:
        """Analyze all pending actions in a conversation.

        This implementation analyzes each pending action individually using the abstract
        security_risk method -- the current_context is provided for compatibility but is
        otherwise ignored.
        """
        result = {}

        for action_event in pending_actions:
            try:
                risk = self.security_risk(action_event)
                result[action_event.id] = risk
            except Exception as e:
                logger.error(f"Error analyzing action {action_event}: {e}")
                result[action_event.id] = SecurityRisk.UNKNOWN

        return result
