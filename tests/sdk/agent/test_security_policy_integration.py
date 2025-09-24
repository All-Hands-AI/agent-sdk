"""Test configurable security policy functionality."""

import shutil
import tempfile
from pathlib import Path

from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.llm import LLM
from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer


def test_security_policy_in_system_message():
    """Test that security policy is included in system message."""
    agent = Agent(
        llm=LLM(
            model="test-model", api_key=SecretStr("test-key"), base_url="http://test"
        ),
        security_analyzer=LLMSecurityAnalyzer(),
    )
    system_message = agent.system_message

    # Verify that security policy section is present
    assert "<SECURITY_RISK_ASSESSMENT>" in system_message
    assert "Security Risk Policy" in system_message


def test_custom_security_policy_in_system_message():
    """Test that custom security policy filename is used in system message."""
    # Create a temporary directory for test files
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a custom policy file with distinctive content
        custom_policy_path = Path(temp_dir) / "custom_policy.j2"
        custom_policy_content = (
            "# 🔐 Custom Test Security Policy\n"
            "This is a custom security policy for testing.\n"
            "- **CUSTOM_RULE**: Always test custom policies."
        )
        custom_policy_path.write_text(custom_policy_content)

        # Copy required template files to temp directory
        system_prompt_path = Path(temp_dir) / "system_prompt.j2"
        original_prompt_dir = (
            Path(__file__).parent.parent.parent.parent
            / "openhands"
            / "sdk"
            / "agent"
            / "prompts"
        )
        original_system_prompt = original_prompt_dir / "system_prompt.j2"
        shutil.copy2(original_system_prompt, system_prompt_path)

        security_risk_assessment_path = Path(temp_dir) / "security_risk_assessment.j2"
        original_security_risk_assessment = (
            original_prompt_dir / "security_risk_assessment.j2"
        )
        shutil.copy2(original_security_risk_assessment, security_risk_assessment_path)

        # Create agent with custom security policy using absolute paths for both
        agent = Agent(
            llm=LLM(
                model="test-model",
                api_key=SecretStr("test-key"),
                base_url="http://test",
            ),
            system_prompt_filename=str(system_prompt_path),
            security_policy_filename=str(custom_policy_path),
        )

        # Get system message - this should include our custom policy
        system_message = agent.system_message

        # Verify that custom policy content appears in system message
        assert "Custom Test Security Policy" in system_message
        assert "CUSTOM_RULE" in system_message
        assert "Always test custom policies" in system_message


def test_llm_security_analyzer_template_kwargs():
    """Test that agent sets template_kwargs appropriately when security analyzer is LLMSecurityAnalyzer."""  # noqa: E501
    # Create agent with LLMSecurityAnalyzer
    agent = Agent(
        llm=LLM(
            model="test-model", api_key=SecretStr("test-key"), base_url="http://test"
        ),
        security_analyzer=LLMSecurityAnalyzer(),
    )

    # Access the system_message property to trigger template_kwargs computation
    system_message = agent.system_message

    # Verify that the security risk assessment section is included in the system prompt
    assert "<SECURITY_RISK_ASSESSMENT>" in system_message
    assert "# Security Risk Policy" in system_message
    assert "When using tools that support the security_risk parameter" in system_message
    # By default, cli_mode is True, so we should see the CLI mode version
    assert "**LOW**: Safe, read-only actions" in system_message
    assert "**MEDIUM**: Project-scoped edits or execution" in system_message
    assert "**HIGH**: System-level or untrusted operations" in system_message
    assert "**Global Rules**" in system_message


def test_llm_security_analyzer_sandbox_mode():
    """Test that agent includes sandbox mode security risk assessment when cli_mode=False."""  # noqa: E501
    # Create agent with LLMSecurityAnalyzer and cli_mode=False
    agent = Agent(
        llm=LLM(
            model="test-model", api_key=SecretStr("test-key"), base_url="http://test"
        ),
        security_analyzer=LLMSecurityAnalyzer(),
        system_prompt_kwargs={"cli_mode": False},
    )

    # Access the system_message property to trigger template_kwargs computation
    system_message = agent.system_message

    # Verify that the security risk assessment section is included with sandbox mode content  # noqa: E501
    assert "<SECURITY_RISK_ASSESSMENT>" in system_message
    assert "# Security Risk Policy" in system_message
    assert "When using tools that support the security_risk parameter" in system_message
    # With cli_mode=False, we should see the sandbox mode version
    assert "**LOW**: Read-only actions inside sandbox" in system_message
    assert "**MEDIUM**: Container-scoped edits and installs" in system_message
    assert "**HIGH**: Data exfiltration or privilege breaks" in system_message
    assert "**Global Rules**" in system_message


def test_no_security_analyzer_excludes_risk_assessment():
    """Test that security risk assessment section is excluded when no security analyzer is set."""  # noqa: E501
    # Create agent without security analyzer
    agent = Agent(
        llm=LLM(
            model="test-model", api_key=SecretStr("test-key"), base_url="http://test"
        )
    )

    # Get the system message
    system_message = agent.system_message

    # Verify that the security risk assessment section is NOT included
    assert "<SECURITY_RISK_ASSESSMENT>" not in system_message
    assert "# Security Risk Policy" not in system_message
    assert (
        "When using tools that support the security_risk parameter"
        not in system_message
    )


def test_non_llm_security_analyzer_excludes_risk_assessment():
    """Test that security risk assessment section is excluded when security analyzer is not LLMSecurityAnalyzer."""  # noqa: E501
    from openhands.sdk.event import ActionEvent
    from openhands.sdk.security.analyzer import SecurityAnalyzerBase
    from openhands.sdk.security.risk import SecurityRisk

    class MockSecurityAnalyzer(SecurityAnalyzerBase):
        def security_risk(self, action: ActionEvent) -> SecurityRisk:
            return SecurityRisk.LOW

    # Create agent with non-LLM security analyzer
    agent = Agent(
        llm=LLM(
            model="test-model", api_key=SecretStr("test-key"), base_url="http://test"
        ),
        security_analyzer=MockSecurityAnalyzer(),
    )

    # Get the system message
    system_message = agent.system_message

    # Verify that the security risk assessment section is NOT included
    assert "<SECURITY_RISK_ASSESSMENT>" not in system_message
    assert "# Security Risk Policy" not in system_message
    assert (
        "When using tools that support the security_risk parameter"
        not in system_message
    )
