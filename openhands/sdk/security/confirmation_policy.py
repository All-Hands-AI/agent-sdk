from abc import ABC, abstractmethod
from typing import Annotated

from pydantic import field_validator

from openhands.sdk.security.risk import SecurityRisk
from openhands.sdk.utils.discriminated_union import (
    DiscriminatedUnionMixin,
    DiscriminatedUnionType,
)


class ConfirmationPolicyBase(DiscriminatedUnionMixin, ABC):
    @abstractmethod
    def should_confirm(self, risk: SecurityRisk = SecurityRisk.UNKNOWN) -> bool:
        """Determine if an action with the given risk level requires confirmation."""
        pass


ConfirmationPolicy = Annotated[
    ConfirmationPolicyBase, DiscriminatedUnionType[ConfirmationPolicyBase]
]


class AlwaysConfirm(ConfirmationPolicyBase):
    def should_confirm(self, risk: SecurityRisk = SecurityRisk.UNKNOWN) -> bool:
        return True


class NeverConfirm(ConfirmationPolicyBase):
    def should_confirm(self, risk: SecurityRisk = SecurityRisk.UNKNOWN) -> bool:
        return False


class ConfirmRisky(ConfirmationPolicyBase):
    threshold: SecurityRisk = SecurityRisk.HIGH
    confirm_unknown: bool = True

    @field_validator("threshold")
    def validate_threshold(cls, v: SecurityRisk) -> SecurityRisk:
        if v == SecurityRisk.UNKNOWN:
            raise ValueError("Threshold cannot be UNKNOWN")
        return v

    def should_confirm(self, risk: SecurityRisk = SecurityRisk.UNKNOWN) -> bool:
        if risk == SecurityRisk.UNKNOWN:
            return self.confirm_unknown

        # This comparison is reflexive by default, so if the threshold is HIGH we will
        # still require confirmation for HIGH risk actions. And since the threshold is
        # guaranteed to never be UNKNOWN (by the validator), we're guaranteed to get a
        # boolean here.
        return risk.is_riskier(self.threshold)
