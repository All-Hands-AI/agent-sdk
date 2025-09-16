"""Security risk levels for action analysis."""

from enum import Enum


class ActionSecurityRisk(str, Enum):
    """Security risk levels for actions.

    Based on OpenHands security risk levels but adapted for agent-sdk.
    Integer values allow for easy comparison and ordering.
    """

    UNKNOWN = "UNKNOWN"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    @property
    def description(self) -> str:
        """Get a human-readable description of the risk level.

        Returns:
            Human-readable description of the risk
        """
        descriptions = {
            ActionSecurityRisk.LOW: (
                "Low risk - Safe operation with minimal security impact"
            ),
            ActionSecurityRisk.MEDIUM: (
                "Medium risk - Moderate security impact, review recommended"
            ),
            ActionSecurityRisk.HIGH: (
                "High risk - Significant security impact, confirmation required"
            ),
            ActionSecurityRisk.UNKNOWN: (
                "Unknown risk - Risk level could not be determined"
            ),
        }
        return descriptions.get(self, "Unknown risk level")

    def __str__(self) -> str:
        return self.name
