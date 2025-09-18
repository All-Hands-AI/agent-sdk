from __future__ import annotations

from enum import Enum
from functools import total_ordering
from typing import Any


@total_ordering
class SecurityRisk(str, Enum):
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
        """Get a human-readable description of the risk level."""
        descriptions = {
            SecurityRisk.LOW: (
                "Low risk - Safe operation with minimal security impact"
            ),
            SecurityRisk.MEDIUM: (
                "Medium risk - Moderate security impact, review recommended"
            ),
            SecurityRisk.HIGH: (
                "High risk - Significant security impact, confirmation required"
            ),
            SecurityRisk.UNKNOWN: ("Unknown risk - Risk level could not be determined"),
        }
        return descriptions.get(self, "Unknown risk level")

    def __str__(self) -> str:
        return self.name

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, SecurityRisk):
            return NotImplemented
        order = {
            SecurityRisk.UNKNOWN: 0,
            SecurityRisk.LOW: 1,
            SecurityRisk.MEDIUM: 2,
            SecurityRisk.HIGH: 3,
        }
        return order[self] < order[other]
