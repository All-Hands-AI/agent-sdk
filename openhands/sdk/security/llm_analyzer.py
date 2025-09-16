from typing import Any

from openhands.sdk.logger import get_logger
from openhands.sdk.security.analyzer import SecurityAnalyzer
from openhands.sdk.security.risk import SecurityRisk
from openhands.sdk.tool.schema import Action


logger = get_logger(__name__)


class LLMSecurityAnalyzer(SecurityAnalyzer):
    """LLM-based security analyzer.

    This analyzer respects the security_risk attribute that can be set by the LLM
    when generating actions, similar to OpenHands' LLMRiskAnalyzer.

    It provides a lightweight security analysis approach that leverages the LLM's
    understanding of action context and potential risks.
    """

    def security_risk(self, action: Action) -> SecurityRisk:
        """Evaluate security risk based on LLM-provided assessment.

        This method checks if the action has a security_risk attribute set by the LLM
        and returns it. The LLM may not always provide this attribute but it defaults to
        UNKNOWN if not explicitly set.
        """
        logger.debug(f"Analyzing security risk: {action} -- {action.security_risk}")

        return action.security_risk

    def handle_api_request(self, request_data: dict[str, Any]) -> dict[str, Any]:
        """Handle API requests for security analyzer configuration.

        This is a no-op implementation since LLMSecurityAnalyzer doesn't need
        external configuration.
        """
        return {"status": "ok", "message": "LLMSecurityAnalyzer has no configuration"}

    def close(self) -> None:
        """Clean up resources used by the security analyzer.

        This is a no-op implementation since LLMSecurityAnalyzer doesn't use
        any external resources.
        """
        pass
