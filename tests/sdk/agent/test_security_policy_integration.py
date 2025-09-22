"""Test that the security policy is properly integrated into the agent system prompt."""

from pydantic import SecretStr

from openhands.sdk.agent.agent import Agent
from openhands.sdk.llm import LLM


def test_security_policy_in_system_message():
    """Test that the security policy is included in the agent's system message."""
    # Create a minimal agent configuration
    agent = Agent(
        llm=LLM(
            model="test-model", api_key=SecretStr("test-key"), base_url="http://test"
        )
    )

    # Get the system message
    system_message = agent.system_message

    # Verify that the security policy content is included
    assert "🔐 Security Policy" in system_message
    assert "OK to do without Explicit User Consent" in system_message
    assert "Do only with Explicit User Consent" in system_message
    assert "Never Do" in system_message

    # Verify specific policy items are present
    assert (
        "Download and run code from a repository specified by a user" in system_message
    )
    assert "Open pull requests on the original repositories" in system_message
    assert "Install and run popular packages from pypi, npm" in system_message
    assert (
        "Upload code to anywhere other than the location where it was obtained"
        in system_message
    )
    assert "Upload API keys or tokens anywhere" in system_message
    assert "Never perform any illegal activities" in system_message
    assert "Never run software to mine cryptocurrency" in system_message

    # Verify that all security guidelines are consolidated in the policy
    assert "General Security Guidelines" in system_message
    assert "Only use GITHUB_TOKEN and other credentials" in system_message
    assert "Use APIs to work with GitHub or other platforms" in system_message


def test_security_policy_template_rendering():
    """Test that the security policy template renders correctly."""

    from openhands.sdk.context.prompts.prompt import render_template

    # Get the prompts directory
    agent = Agent(
        llm=LLM(
            model="test-model", api_key=SecretStr("test-key"), base_url="http://test"
        )
    )
    prompt_dir = agent.prompt_dir

    # Render the security policy template
    security_policy = render_template(prompt_dir, "security_policy.j2")

    # Verify the content structure
    assert security_policy.startswith("# 🔐 Security Policy")
    assert "## OK to do without Explicit User Consent" in security_policy
    assert "## Do only with Explicit User Consent" in security_policy
    assert "## Never Do" in security_policy

    # Verify it's properly formatted (no extra whitespace at start/end)
    assert not security_policy.startswith(" ")
    assert not security_policy.endswith(" ")
