"""Simplified tests for SecurityRisk enum focusing on working functionality."""

from openhands.sdk.security.risk import SecurityRisk


def test_security_risk_enum_values():
    """Test that SecurityRisk enum has expected values."""
    assert SecurityRisk.UNKNOWN == "UNKNOWN"
    assert SecurityRisk.LOW == "LOW"
    assert SecurityRisk.MEDIUM == "MEDIUM"
    assert SecurityRisk.HIGH == "HIGH"


def test_security_risk_string_representation():
    """Test string representation of SecurityRisk values."""
    assert str(SecurityRisk.UNKNOWN) == "UNKNOWN"
    assert str(SecurityRisk.LOW) == "LOW"
    assert str(SecurityRisk.MEDIUM) == "MEDIUM"
    assert str(SecurityRisk.HIGH) == "HIGH"
