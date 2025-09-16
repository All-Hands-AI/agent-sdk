"""LLM-based security analyzer implementation."""

from typing import Any

from openhands.sdk.logger import get_logger
from openhands.sdk.security.analyzer import SecurityAnalyzer
from openhands.sdk.security.risk import ActionSecurityRisk
from openhands.sdk.tool.schema import Action


logger = get_logger(__name__)


class LLMSecurityAnalyzer(SecurityAnalyzer):
    """LLM-based security analyzer.

    This analyzer respects the security_risk attribute that can be set by the LLM
    when generating actions, similar to OpenHands' LLMRiskAnalyzer.

    It provides a lightweight security analysis approach that leverages the LLM's
    understanding of action context and potential risks.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the LLM security analyzer.

        Args:
            **kwargs: Additional configuration parameters
        """
        super().__init__(**kwargs)
        logger.info("LLM Security Analyzer initialized")

    async def security_risk(self, action: Action) -> ActionSecurityRisk:
        """Evaluate security risk based on LLM-provided assessment.

        This method checks if the action has a security_risk attribute set by the LLM
        and maps it to the appropriate ActionSecurityRisk level.

        Args:
            action: The action to analyze for security risks

        Returns:
            ActionSecurityRisk enum indicating the risk level
        """
        logger.debug(f"Analyzing security risk for action: {action}")

        # Check if the action has a security_risk attribute from the LLM
        if hasattr(action, "security_risk") and action.security_risk is not None:
            try:
                # Convert string risk to enum if needed
                if isinstance(action.security_risk, str):
                    risk = ActionSecurityRisk.from_string(action.security_risk)
                    logger.debug(
                        f"Converted string risk '{action.security_risk}' to {risk}"
                    )
                    return risk
                elif isinstance(action.security_risk, ActionSecurityRisk):
                    logger.debug(
                        f"Using existing ActionSecurityRisk: {action.security_risk}"
                    )
                    return action.security_risk
                else:
                    logger.warning(
                        f"Unknown security_risk type: {type(action.security_risk)}"
                    )
                    return ActionSecurityRisk.UNKNOWN
            except ValueError as e:
                logger.warning(
                    f"Invalid security risk value '{action.security_risk}': {e}"
                )
                return ActionSecurityRisk.UNKNOWN

        # If no security_risk attribute is found, default to UNKNOWN
        logger.debug("No security_risk attribute found, defaulting to UNKNOWN")
        return ActionSecurityRisk.UNKNOWN

    async def handle_api_request(self, request_data: dict[str, Any]) -> dict[str, Any]:
        """Handle API requests for LLM analyzer configuration.

        The LLM analyzer has minimal configuration, so this mainly returns
        status information.

        Args:
            request_data: Dictionary containing request data

        Returns:
            Dictionary containing response data
        """
        action = request_data.get("action", "status")

        if action == "status":
            return {
                "status": "active",
                "analyzer_type": "llm",
                "description": "LLM-based security risk analyzer",
                "config": self.config,
            }
        elif action == "configure":
            # LLM analyzer has minimal configuration
            new_config = request_data.get("config", {})
            self.config.update(new_config)
            return {"status": "configured", "config": self.config}
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    async def close(self) -> None:
        """Clean up resources used by the LLM analyzer.

        The LLM analyzer doesn't maintain persistent resources,
        so this is a no-op.
        """
        logger.info("LLM Security Analyzer closed")
        pass
