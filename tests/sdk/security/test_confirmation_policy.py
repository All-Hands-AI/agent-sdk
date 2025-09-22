"""Tests for ConfirmationPolicy classes and serialization."""

import pytest
from pydantic import BaseModel

from openhands.sdk.security.confirmation_policy import (
    AlwaysConfirm,
    ConfirmationPolicyBase,
    NeverConfirm,
)
from openhands.sdk.security.risk import SecurityRisk


class TestConfirmationPolicyBase:
    """Tests for the ConfirmationPolicy base class."""

    def test_cannot_instantiate_base_class(self) -> None:
        """Test that the base class cannot be instantiated directly."""
        with pytest.raises(TypeError):
            # Of course mypy doesn't want us to do this, so ignore the type check while
            # we confirm the runtime behavior.
            ConfirmationPolicyBase()  # type: ignore

    @pytest.mark.parametrize("cls", list(ConfirmationPolicyBase.__subclasses__()))
    def test_confirmation_policy_container_serialization(
        self, cls: type[ConfirmationPolicyBase]
    ) -> None:
        """Test that a container model with ConfirmationPolicy instances as a field can
        be serialized.
        """

        class PolicyContainer(BaseModel):
            policy: ConfirmationPolicyBase

        container = PolicyContainer(policy=cls())

        container_dict = container.model_dump_json()
        restored_container = PolicyContainer.model_validate_json(container_dict)

        assert isinstance(restored_container.policy, cls)
        assert container.policy == restored_container.policy


class TestAlwaysConfirm:
    """Tests for the AlwaysConfirm policy."""

    @pytest.mark.parametrize("risk", list(SecurityRisk))
    def test_always_confirm(self, risk: SecurityRisk) -> None:
        """Test that the policy always confirms, regardless of the inputs."""
        policy = AlwaysConfirm()
        assert policy.should_confirm(risk) is True

    def test_roundtrip_serialization(self) -> None:
        """Test that AlwaysConfirm can be serialized and deserialized correctly."""
        policy = AlwaysConfirm()
        policy_dict = policy.model_dump_json()
        restored_policy = AlwaysConfirm.model_validate_json(policy_dict)

        assert isinstance(restored_policy, AlwaysConfirm)

    def test_polymorphic_serialization(self) -> None:
        """Test polymorphic serialization and deserialization. This requires we
        deserialize using the base class.
        """
        policy: ConfirmationPolicyBase = AlwaysConfirm()
        policy_dict = policy.model_dump_json()
        restored_policy = ConfirmationPolicyBase.model_validate_json(policy_dict)

        assert isinstance(restored_policy, AlwaysConfirm)


class TestNeverConfirm:
    """Tests for the NeverConfirm policy."""

    @pytest.mark.parametrize("risk", list(SecurityRisk))
    def test_never_confirm(self, risk: SecurityRisk) -> None:
        """Test that the policy never confirms, regardless of the inputs."""
        policy = NeverConfirm()
        assert policy.should_confirm(risk) is False

    def test_roundtrip_serialization(self) -> None:
        """Test that NeverConfirm can be serialized and deserialized correctly."""
        policy = NeverConfirm()
        policy_dict = policy.model_dump_json()
        restored_policy = NeverConfirm.model_validate_json(policy_dict)

        assert isinstance(restored_policy, NeverConfirm)

    def test_polymorphic_serialization(self) -> None:
        """Test polymorphic serialization and deserialization. This requires we
        deserialize using the base class.
        """
        policy: ConfirmationPolicyBase = NeverConfirm()
        policy_dict = policy.model_dump_json()
        restored_policy = ConfirmationPolicyBase.model_validate_json(policy_dict)

        assert isinstance(restored_policy, NeverConfirm)
