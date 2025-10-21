from openhands.sdk.llm import LLM


def test_llm_litellm_extra_body_default():
    """Test that litellm_extra_body field defaults to empty dict."""
    llm = LLM(model="gpt-4o", usage_id="test")
    assert llm.litellm_extra_body == {}


def test_llm_litellm_extra_body_initialization():
    """Test litellm_extra_body field initialization with custom values."""
    custom_extra_body = {
        "trace_version": "1.0.0",
        "tags": ["model:gpt-4", "agent:my-agent"],
        "session_id": "session-123",
        "trace_user_id": "user-456",
    }
    llm = LLM(model="gpt-4o", usage_id="test", litellm_extra_body=custom_extra_body)
    assert llm.litellm_extra_body == custom_extra_body


def test_llm_litellm_extra_body_modification():
    """Test that litellm_extra_body field can be modified after initialization."""
    llm = LLM(model="gpt-4o", usage_id="test")

    # Start with empty litellm_extra_body
    assert llm.litellm_extra_body == {}

    # Add some extra body data
    llm.litellm_extra_body["custom_key"] = "custom_value"
    llm.litellm_extra_body["session_id"] = "session-123"

    assert llm.litellm_extra_body["custom_key"] == "custom_value"
    assert llm.litellm_extra_body["session_id"] == "session-123"


def test_llm_litellm_extra_body_complex_structure():
    """Test litellm_extra_body field with complex nested structure."""
    complex_extra_body = {
        "trace_version": "2.1.0",
        "tags": ["model:claude-3", "agent:coding-agent", "env:production"],
        "session_info": {
            "id": "session-789",
            "user_id": "user-101",
            "created_at": "2024-01-01T00:00:00Z",
        },
        "metrics": {
            "tokens_used": 1500,
            "response_time_ms": 250,
        },
    }
    llm = LLM(
        model="claude-3-5-sonnet",
        usage_id="test",
        litellm_extra_body=complex_extra_body,
    )
    assert llm.litellm_extra_body == complex_extra_body

    # Test nested access
    assert llm.litellm_extra_body["session_info"]["id"] == "session-789"
    assert llm.litellm_extra_body["metrics"]["tokens_used"] == 1500


def test_llm_litellm_extra_body_for_custom_inference():
    """Test litellm_extra_body field for custom inference cluster use case."""
    # Example of custom metadata for logging/tracking/routing
    inference_metadata = {
        "cluster_id": "prod-cluster-1",
        "routing_key": "high-priority",
        "user_tier": "premium",
        "request_id": "req-12345",
        "experiment_id": "exp-abc123",
        "custom_headers": {
            "X-Custom-Auth": "bearer-token",
            "X-Request-Source": "openhands-agent",
        },
    }
    llm = LLM(model="gpt-4o", usage_id="test", litellm_extra_body=inference_metadata)
    assert llm.litellm_extra_body == inference_metadata

    # Verify specific fields that would be useful for custom inference clusters
    assert llm.litellm_extra_body["cluster_id"] == "prod-cluster-1"
    assert llm.litellm_extra_body["routing_key"] == "high-priority"
    assert (
        llm.litellm_extra_body["custom_headers"]["X-Request-Source"]
        == "openhands-agent"
    )
