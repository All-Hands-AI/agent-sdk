"""Tests for the LLMSecurityAnalyzer class."""

import pytest

from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer
from openhands.sdk.security.risk import SecurityRisk
from openhands.sdk.tool import ActionBase


class MockAction(ActionBase):
    """Mock action for testing."""

    command: str = "test_command"


@pytest.mark.parametrize(
    "risk_level",
    [
        SecurityRisk.UNKNOWN,
        SecurityRisk.LOW,
        SecurityRisk.MEDIUM,
        SecurityRisk.HIGH,
    ],
)
def test_llm_security_analyzer_returns_stored_risk(risk_level: SecurityRisk):
    """Test that LLMSecurityAnalyzer returns the security_risk stored in the action."""
    analyzer = LLMSecurityAnalyzer()
    action = MockAction(command="test", security_risk=risk_level)

    result = analyzer.security_risk(action)

    assert result == risk_level
