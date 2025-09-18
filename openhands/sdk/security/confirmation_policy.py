from abc import ABC, abstractmethod
from typing import Annotated

from openhands.sdk.security.risk import SecurityRisk
from openhands.sdk.utils.discriminated_union import (
    DiscriminatedUnionMixin,
    DiscriminatedUnionType,
)


class ConfirmationPolicyBase(DiscriminatedUnionMixin, ABC):
    @abstractmethod
    def should_confirm(self, risk: SecurityRisk = SecurityRisk.UNKNOWN) -> bool:
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

    def should_confirm(self, risk: SecurityRisk = SecurityRisk.UNKNOWN) -> bool:
        if risk == SecurityRisk.UNKNOWN:
            return self.confirm_unknown
        return risk >= self.threshold
