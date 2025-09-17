from abc import ABC, abstractmethod
from typing import Annotated

from pydantic import Field

from openhands.sdk.event.llm_convertible import ActionEvent
from openhands.sdk.security.risk import SecurityRisk
from openhands.sdk.utils.discriminated_union import (
    DiscriminatedUnionMixin,
    DiscriminatedUnionType,
)


class ConfirmationPolicyBase(DiscriminatedUnionMixin, ABC):
    @abstractmethod
    def should_confirm(self, risk: SecurityRisk) -> bool:
        """Determine if an action with the give risk level should require confirmation.

        Args:
            risk: The security risk level of the action.

        Returns:
            True if confirmation is required, False otherwise.
        """
        raise NotImplementedError

    def requires_confirmation(self, action: ActionEvent) -> bool:
        security_risk = (
            action.action.security_risk
            if action.action.security_risk
            else SecurityRisk.UNKNOWN
        )
        return self.should_confirm(security_risk)


class AlwaysConfirm(ConfirmationPolicyBase):
    def should_confirm(self, risk: SecurityRisk) -> bool:
        return True


class NeverConfirm(ConfirmationPolicyBase):
    def should_confirm(self, risk: SecurityRisk) -> bool:
        return False


class ConfirmHighRisk(ConfirmationPolicyBase):
    threshold: SecurityRisk = Field(
        default=SecurityRisk.HIGH,
        description="The minimum risk level that requires confirmation.",
    )
    confirm_unknown: bool = Field(
        default=True,
        description="Whether to require confirmation for UNKNOWN risk level.",
    )

    def should_confirm(self, risk: SecurityRisk) -> bool:
        match risk:
            case SecurityRisk.UNKNOWN:
                return self.confirm_unknown

            case SecurityRisk.LOW:
                return self.threshold in {
                    SecurityRisk.LOW,
                    SecurityRisk.MEDIUM,
                    SecurityRisk.HIGH,
                }

            case SecurityRisk.MEDIUM:
                return self.threshold in {SecurityRisk.MEDIUM, SecurityRisk.HIGH}

            case SecurityRisk.HIGH:
                return self.threshold == SecurityRisk.HIGH


ConfirmationPolicy = Annotated[
    ConfirmationPolicyBase, DiscriminatedUnionType[ConfirmationPolicyBase]
]
