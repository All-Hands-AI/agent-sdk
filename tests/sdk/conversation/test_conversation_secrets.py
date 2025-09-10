"""Tests for conversation secrets integration."""

from unittest.mock import Mock

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.conversation.secrets_manager import SecretsManager


def test_conversation_add_secrets():
    """Test that conversation.add_secrets() works correctly."""
    # Create a mock agent
    mock_agent = Mock(spec=Agent)
    mock_agent.init_state = Mock()

    conversation = Conversation(
        agent=mock_agent,
    )

    def get_api_key(key: str) -> str:
        return "sk-test-key"

    def get_password(key: str) -> str:
        return "secret-password"

    secrets = {
        "API_KEY": get_api_key,
        "PASSWORD": get_password,
    }

    # Add secrets to conversation
    conversation.add_secrets(secrets)

    # Verify secrets manager was created and populated
    with conversation.state:
        secrets_manager = conversation.state.get_secrets_manager()
        assert secrets_manager is not None
        assert secrets_manager.has_secrets()
        assert secrets_manager.get_secret_keys() == {"API_KEY", "PASSWORD"}


def test_conversation_secrets_manager_initialization():
    """Test that secrets manager is initialized when conversation is created."""
    mock_agent = Mock(spec=Agent)
    mock_agent.init_state = Mock()

    conversation = Conversation(
        agent=mock_agent,
    )

    # Verify secrets manager is initialized
    with conversation.state:
        secrets_manager = conversation.state.get_secrets_manager()
        assert secrets_manager is not None
        assert isinstance(secrets_manager, SecretsManager)
        assert not secrets_manager.has_secrets()


def test_conversation_multiple_add_secrets_calls():
    """Test multiple calls to add_secrets() accumulate secrets."""
    mock_agent = Mock(spec=Agent)
    mock_agent.init_state = Mock()

    conversation = Conversation(
        agent=mock_agent,
    )

    def get_api_key(key: str) -> str:
        return "api-key-value"

    def get_password(key: str) -> str:
        return "password-value"

    def get_token(key: str) -> str:
        return "token-value"

    # Add secrets in multiple calls
    conversation.add_secrets({"API_KEY": get_api_key})
    conversation.add_secrets({"PASSWORD": get_password, "TOKEN": get_token})

    # Verify all secrets are present
    with conversation.state:
        secrets_manager = conversation.state.get_secrets_manager()
        assert secrets_manager is not None
        assert secrets_manager.has_secrets()
        assert secrets_manager.get_secret_keys() == {"API_KEY", "PASSWORD", "TOKEN"}


def test_conversation_state_secrets_manager_persistence():
    """Test that secrets manager persists in conversation state."""
    mock_agent = Mock(spec=Agent)
    mock_agent.init_state = Mock()

    conversation = Conversation(
        agent=mock_agent,
    )

    # Get initial secrets manager
    with conversation.state:
        initial_manager = conversation.state.get_secrets_manager()
        assert initial_manager is not None

    # Add secrets
    def get_secret(key: str) -> str:
        return "secret-value"

    conversation.add_secrets({"SECRET": get_secret})

    # Verify same manager instance is used
    with conversation.state:
        current_manager = conversation.state.get_secrets_manager()
        assert current_manager is initial_manager
        assert current_manager is not None
        assert current_manager.has_secrets()
