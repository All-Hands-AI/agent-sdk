"""Tests for LLMWithGateway enterprise gateway support."""

import time
from typing import Any
from unittest.mock import Mock, patch

import pytest
from pydantic import SecretStr

from openhands.sdk.llm import LLMWithGateway, Message, TextContent
from tests.conftest import create_mock_litellm_response


@pytest.fixture
def mock_gateway_auth_response():
    """Mock OAuth response from gateway."""
    return {
        "access_token": "test-gateway-token-12345",
        "token_type": "Bearer",
        "expires_in": 3600,
    }


@pytest.fixture
def gateway_llm():
    """Create LLMWithGateway instance for testing."""
    return LLMWithGateway(
        model="gemini-1.5-flash",
        api_key=SecretStr("test-api-key"),
        base_url="https://gateway.example.com/v1",
        gateway_auth_url="https://gateway.example.com/oauth/token",
        gateway_auth_headers={
            "X-Client-Id": "test-client-id",
            "X-Client-Secret": "test-client-secret",
        },
        gateway_auth_body={"grant_type": "client_credentials"},
        gateway_auth_token_ttl=3600,
        custom_headers={"X-Custom-Key": "test-custom-value"},
        usage_id="gateway-test-llm",
        num_retries=0,  # Disable retries for testing
    )


class TestLLMWithGatewayInit:
    """Test LLMWithGateway initialization."""

    def test_init_with_gateway_config(self, gateway_llm):
        """Test initialization with gateway configuration."""
        assert gateway_llm.gateway_auth_url == "https://gateway.example.com/oauth/token"
        assert gateway_llm.gateway_auth_method == "POST"
        assert gateway_llm.gateway_auth_headers == {
            "X-Client-Id": "test-client-id",
            "X-Client-Secret": "test-client-secret",
        }
        assert gateway_llm.gateway_auth_body == {"grant_type": "client_credentials"}
        assert gateway_llm.gateway_auth_token_path == "access_token"
        assert gateway_llm.gateway_auth_token_ttl == 3600
        assert gateway_llm.gateway_token_header == "Authorization"
        assert gateway_llm.gateway_token_prefix == "Bearer "
        assert gateway_llm.custom_headers == {"X-Custom-Key": "test-custom-value"}

    def test_init_without_gateway_config(self):
        """Test initialization without gateway configuration (regular LLM)."""
        llm = LLMWithGateway(
            model="gpt-4",
            api_key=SecretStr("test-key"),
            usage_id="regular-llm",
        )
        assert llm.gateway_auth_url is None
        assert llm.custom_headers is None


class TestGatewayTokenFetch:
    """Test OAuth token fetching and caching."""

    @patch("openhands.sdk.llm.llm_with_gateway.httpx.request")
    def test_fetch_token_success(
        self, mock_request, gateway_llm, mock_gateway_auth_response
    ):
        """Test successful token fetch from gateway."""
        mock_response = Mock()
        mock_response.json.return_value = mock_gateway_auth_response
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        token = gateway_llm._ensure_gateway_token()

        assert token == "test-gateway-token-12345"
        assert gateway_llm._gateway_token == "test-gateway-token-12345"
        assert gateway_llm._gateway_token_expiry is not None
        assert gateway_llm._gateway_token_expiry > time.time()

        # Verify request was made correctly
        mock_request.assert_called_once_with(
            "POST",
            "https://gateway.example.com/oauth/token",
            headers={
                "X-Client-Id": "test-client-id",
                "X-Client-Secret": "test-client-secret",
            },
            json={"grant_type": "client_credentials"},
            timeout=30,
        )

    @patch("openhands.sdk.llm.llm_with_gateway.httpx.request")
    def test_token_caching(self, mock_request, gateway_llm, mock_gateway_auth_response):
        """Test that tokens are cached and not re-fetched unnecessarily."""
        mock_response = Mock()
        mock_response.json.return_value = mock_gateway_auth_response
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        # First call should fetch token
        token1 = gateway_llm._ensure_gateway_token()
        assert mock_request.call_count == 1

        # Second call should use cached token
        token2 = gateway_llm._ensure_gateway_token()
        assert mock_request.call_count == 1  # Still only 1 call
        assert token1 == token2

    @patch("openhands.sdk.llm.llm_with_gateway.httpx.request")
    def test_token_refresh_when_expired(
        self, mock_request, gateway_llm, mock_gateway_auth_response
    ):
        """Test that token is refreshed when expired."""
        mock_response = Mock()
        mock_response.json.return_value = mock_gateway_auth_response
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        # Fetch initial token
        gateway_llm._ensure_gateway_token()
        assert mock_request.call_count == 1

        # Manually expire the token
        gateway_llm._gateway_token_expiry = time.time() - 10

        # Next call should refresh
        gateway_llm._ensure_gateway_token()
        assert mock_request.call_count == 2

    @patch("openhands.sdk.llm.llm_with_gateway.httpx.request")
    def test_token_fetch_missing_token(self, mock_request, gateway_llm):
        """Test handling of response without token field."""
        mock_response = Mock()
        mock_response.json.return_value = {"error": "invalid_client"}
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        with pytest.raises(ValueError, match="not found in response"):
            gateway_llm._ensure_gateway_token()

    @patch("openhands.sdk.llm.llm_with_gateway.time.time")
    @patch("openhands.sdk.llm.llm_with_gateway.httpx.request")
    def test_token_ttl_uses_expires_in_by_default(
        self, mock_request, mock_time
    ) -> None:
        """Token expiry should honor expires_in when TTL override not configured."""
        mock_time.return_value = 1_000.0

        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "token-expires-in",
            "expires_in": 120,
        }
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        llm = LLMWithGateway(
            model="gpt-4",
            api_key=SecretStr("key"),
            base_url="https://gateway.example.com/llm/v1",
            gateway_auth_url="https://gateway.example.com/oauth/token",
            gateway_auth_headers={"X-Client-Id": "client"},
            gateway_auth_body={"grant_type": "client_credentials"},
            usage_id="ttl-expires-in-test",
            num_retries=0,
        )

        token = llm._ensure_gateway_token()

        assert token == "token-expires-in"
        assert llm._gateway_token_expiry == pytest.approx(1_120.0, abs=0.1)

    @patch("openhands.sdk.llm.llm_with_gateway.time.time")
    @patch("openhands.sdk.llm.llm_with_gateway.httpx.request")
    def test_token_ttl_falls_back_to_default(self, mock_request, mock_time) -> None:
        """Missing expires_in should fall back to default TTL."""
        mock_time.return_value = 2_000.0

        mock_response = Mock()
        mock_response.json.return_value = {"access_token": "token-default"}
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        llm = LLMWithGateway(
            model="gpt-4",
            api_key=SecretStr("key"),
            base_url="https://gateway.example.com/llm/v1",
            gateway_auth_url="https://gateway.example.com/oauth/token",
            usage_id="ttl-default-test",
            num_retries=0,
        )

        llm._ensure_gateway_token()

        assert llm._gateway_token_expiry == pytest.approx(2_300.0, abs=0.1)

    @patch("openhands.sdk.llm.llm_with_gateway.time.time")
    @patch("openhands.sdk.llm.llm_with_gateway.httpx.request")
    def test_token_ttl_prefers_configured_override(
        self, mock_request, mock_time
    ) -> None:
        """Configured TTL should override expires_in from response."""
        mock_time.return_value = 3_000.0

        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "token-override",
            "expires_in": 3_600,
        }
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        llm = LLMWithGateway(
            model="gpt-4",
            api_key=SecretStr("key"),
            base_url="https://gateway.example.com/llm/v1",
            gateway_auth_url="https://gateway.example.com/oauth/token",
            gateway_auth_body={"grant_type": "client_credentials"},
            gateway_auth_token_ttl=45,
            usage_id="ttl-override-test",
            num_retries=0,
        )

        llm._ensure_gateway_token()

        assert llm._gateway_token_expiry == pytest.approx(3_045.0, abs=0.1)


class TestTemplateReplacement:
    """Test template variable replacement."""

    def test_render_templates_string(self, gateway_llm):
        """Test template replacement in strings."""
        template = "Model: {{llm_model}}, URL: {{llm_base_url}}"
        result = gateway_llm._render_templates(template)
        assert result == "Model: gemini-1.5-flash, URL: https://gateway.example.com/v1"

    def test_render_templates_dict(self, gateway_llm):
        """Test template replacement in dictionaries."""
        template = {
            "model": "{{llm_model}}",
            "endpoint": "{{llm_base_url}}/chat",
            "nested": {"key": "{{llm_model}}"},
        }
        result = gateway_llm._render_templates(template)
        assert result["model"] == "gemini-1.5-flash"
        assert result["endpoint"] == "https://gateway.example.com/v1/chat"
        assert result["nested"]["key"] == "gemini-1.5-flash"

    def test_render_templates_list(self, gateway_llm):
        """Test template replacement in lists."""
        template = ["{{llm_model}}", {"url": "{{llm_base_url}}"}]
        result = gateway_llm._render_templates(template)
        assert result[0] == "gemini-1.5-flash"
        assert result[1]["url"] == "https://gateway.example.com/v1"

    def test_render_templates_with_api_key(self, gateway_llm):
        """Test template replacement includes API key."""
        template = "Key: {{llm_api_key}}"
        result = gateway_llm._render_templates(template)
        assert result == "Key: test-api-key"

    def test_render_templates_no_base_url(self):
        """Test template replacement when base_url is not set."""
        llm = LLMWithGateway(
            model="gpt-4",
            api_key=SecretStr("key"),
            usage_id="test",
        )
        template = "URL: {{llm_base_url}}"
        result = llm._render_templates(template)
        assert result == "URL: "


class TestPathExtraction:
    """Test nested path extraction from OAuth responses."""

    def test_extract_simple_path(self):
        """Test extraction from simple path."""
        payload = {"access_token": "token123"}
        result = LLMWithGateway._extract_from_path(payload, "access_token")
        assert result == "token123"

    def test_extract_nested_path(self):
        """Test extraction from nested path."""
        payload = {"data": {"auth": {"token": "token456"}}}
        result = LLMWithGateway._extract_from_path(payload, "data.auth.token")
        assert result == "token456"

    def test_extract_from_array(self):
        """Test extraction from array."""
        payload = {"tokens": [{"value": "token1"}, {"value": "token2"}]}
        result = LLMWithGateway._extract_from_path(payload, "tokens.0.value")
        assert result == "token1"

    def test_extract_empty_path(self):
        """Test extraction with empty path returns root."""
        payload = {"key": "value"}
        result = LLMWithGateway._extract_from_path(payload, "")
        assert result == payload

    def test_extract_missing_key(self):
        """Test extraction fails for missing key."""
        payload = {"other": "value"}
        with pytest.raises(ValueError, match="not found"):
            LLMWithGateway._extract_from_path(payload, "missing")

    def test_extract_invalid_array_index(self):
        """Test extraction fails for invalid array index."""
        payload = {"items": ["a", "b"]}
        with pytest.raises(ValueError, match="Invalid list index"):
            LLMWithGateway._extract_from_path(payload, "items.invalid")

    def test_extract_array_index_out_of_range(self):
        """Test extraction fails for out of range index."""
        payload = {"items": ["a", "b"]}
        with pytest.raises(ValueError, match="out of range"):
            LLMWithGateway._extract_from_path(payload, "items.5")


class TestGatewayIntegration:
    """Integration tests for gateway functionality."""

    @patch("openhands.sdk.llm.llm_with_gateway.httpx.request")
    @patch("openhands.sdk.llm.llm.litellm_completion")
    def test_full_gateway_flow(
        self, mock_completion, mock_request, mock_gateway_auth_response
    ):
        """Test complete flow: OAuth -> LLM request with headers."""
        # Setup gateway LLM
        llm = LLMWithGateway(
            model="gpt-4",
            base_url="https://gateway.example.com/llm/v1",
            gateway_auth_url="https://gateway.example.com/oauth/token",
            gateway_auth_headers={
                "X-Client-Id": "client123",
                "X-Client-Secret": "secret456",
            },
            gateway_auth_body={"grant_type": "client_credentials"},
            custom_headers={"X-Gateway-Key": "gateway789"},
            usage_id="integration-test",
            num_retries=0,
        )

        # Mock OAuth response
        mock_oauth_response = Mock()
        mock_oauth_response.json.return_value = mock_gateway_auth_response
        mock_oauth_response.raise_for_status = Mock()
        mock_request.return_value = mock_oauth_response

        # Mock LLM completion
        mock_completion.return_value = create_mock_litellm_response(
            content="Hello from gateway!"
        )

        # Make completion request
        messages = [Message(role="user", content=[TextContent(text="Hello")])]
        response = llm.completion(messages)

        # Verify OAuth was called
        assert mock_request.call_count == 1
        oauth_call = mock_request.call_args
        assert oauth_call[0][0] == "POST"
        assert oauth_call[0][1] == "https://gateway.example.com/oauth/token"

        # Verify LLM completion was called with correct headers
        assert mock_completion.call_count == 1
        completion_kwargs = mock_completion.call_args[1]
        headers = completion_kwargs["extra_headers"]
        assert headers["Authorization"] == "Bearer test-gateway-token-12345"
        assert headers["X-Gateway-Key"] == "gateway789"

        # Verify response
        assert isinstance(response.message.content[0], TextContent)
        assert response.message.content[0].text == "Hello from gateway!"

    @patch("openhands.sdk.llm.llm_with_gateway.httpx.request")
    @patch("openhands.sdk.llm.llm.litellm_completion")
    def test_gateway_headers_merge_with_extended_thinking(
        self, mock_completion, mock_request, mock_gateway_auth_response
    ):
        """Gateway headers should merge with extended thinking defaults."""
        mock_oauth_response = Mock()
        mock_oauth_response.json.return_value = mock_gateway_auth_response
        mock_oauth_response.raise_for_status = Mock()
        mock_request.return_value = mock_oauth_response

        mock_completion.return_value = create_mock_litellm_response(
            content="extended thinking response"
        )

        llm = LLMWithGateway(
            model="claude-sonnet-4-5-latest",
            api_key=SecretStr("test-api-key"),
            base_url="https://gateway.example.com/llm/v1",
            gateway_auth_url="https://gateway.example.com/oauth/token",
            gateway_auth_headers={
                "X-Client-Id": "client123",
                "X-Client-Secret": "secret456",
            },
            gateway_auth_body={"grant_type": "client_credentials"},
            custom_headers={"X-Gateway-Key": "gateway789"},
            extended_thinking_budget=512,
            usage_id="extended-thinking-test",
            num_retries=0,
        )

        messages = [Message(role="user", content=[TextContent(text="Hello")])]
        llm.completion(messages)

        completion_kwargs = mock_completion.call_args[1]
        headers = completion_kwargs["extra_headers"]
        assert headers["Authorization"] == "Bearer test-gateway-token-12345"
        assert headers["X-Gateway-Key"] == "gateway789"
        assert headers["anthropic-beta"] == "interleaved-thinking-2025-05-14"

    def test_gateway_disabled_when_no_config(self):
        """Test that gateway logic is skipped when not configured."""
        llm = LLMWithGateway(
            model="gpt-4",
            api_key=SecretStr("key"),
            usage_id="no-gateway-test",
        )

        # Should not fail, just act like regular LLM
        kwargs: dict[str, Any] = {}
        llm._prepare_gateway_call(kwargs)
        assert "extra_headers" not in kwargs
