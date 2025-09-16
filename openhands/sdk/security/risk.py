"""Security risk levels for action analysis."""

from enum import IntEnum


class ActionSecurityRisk(IntEnum):
    """Security risk levels for actions.

    Based on OpenHands security risk levels but adapted for agent-sdk.
    Integer values allow for easy comparison and ordering.
    """

    UNKNOWN = -1
    LOW = 0
    MEDIUM = 1
    HIGH = 2

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

    @classmethod
    def from_string(cls, risk_str: str) -> "ActionSecurityRisk":
        """Convert string risk level to ActionSecurityRisk enum.

        Args:
            risk_str: String representation of risk level

        Returns:
            ActionSecurityRisk enum value

        Raises:
            ValueError: If risk_str is not a valid risk level
        """
        risk_mapping = {
            "LOW": cls.LOW,
            "MEDIUM": cls.MEDIUM,
            "HIGH": cls.HIGH,
            "UNKNOWN": cls.UNKNOWN,
        }

        risk_upper = risk_str.upper()
        if risk_upper not in risk_mapping:
            raise ValueError(
                f"Invalid risk level: {risk_str}."
                f"Must be one of: {list(risk_mapping.keys())}"
            )

        return risk_mapping[risk_upper]

    def __str__(self) -> str:
        return self.name
