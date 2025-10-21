#!/usr/bin/env python3
"""
Example demonstrating the new litellm_extra_body functionality.

This example shows how to use the litellm_extra_body field to pass custom
metadata to litellm for logging, tracking, or routing purposes in custom
inference clusters.
"""

from openhands.sdk.llm import LLM


def main():
    # Example 1: Basic usage with custom metadata
    print("=== Example 1: Basic Custom Metadata ===")

    llm_basic = LLM(
        model="gpt-4o",
        usage_id="example",
        litellm_extra_body={
            "trace_version": "1.0.0",
            "session_id": "session-123",
            "user_id": "user-456",
        },
    )

    print(f"Basic litellm_extra_body: {llm_basic.litellm_extra_body}")

    # Example 2: Custom inference cluster metadata
    print("\n=== Example 2: Custom Inference Cluster Metadata ===")

    llm_custom = LLM(
        model="gpt-4o",
        usage_id="example",
        litellm_extra_body={
            "cluster_id": "prod-cluster-1",
            "routing_key": "high-priority",
            "user_tier": "premium",
            "request_id": "req-12345",
            "experiment_id": "exp-abc123",
            "custom_headers": {
                "X-Custom-Auth": "bearer-token",
                "X-Request-Source": "openhands-agent",
                "X-Priority": "high",
            },
            "logging_config": {
                "log_level": "debug",
                "trace_enabled": True,
                "metrics_enabled": True,
            },
        },
    )

    print(f"Custom inference metadata: {llm_custom.litellm_extra_body}")

    # Example 3: Dynamic modification
    print("\n=== Example 3: Dynamic Modification ===")

    llm_dynamic = LLM(model="gpt-4o", usage_id="example")

    # Start with empty extra_body
    print(f"Initial litellm_extra_body: {llm_dynamic.litellm_extra_body}")

    # Add metadata dynamically
    llm_dynamic.litellm_extra_body.update(
        {
            "request_timestamp": "2024-01-01T00:00:00Z",
            "client_version": "1.2.3",
            "feature_flags": ["new_routing", "enhanced_logging"],
        }
    )

    print(f"Updated litellm_extra_body: {llm_dynamic.litellm_extra_body}")

    # Example 4: Show how it would be passed to litellm
    print("\n=== Example 4: How it's passed to litellm ===")

    # This demonstrates what would be passed to litellm.completion()
    # In actual usage, this happens automatically when calling llm.completion()
    example_call_kwargs = {
        "model": llm_custom.model,
        "messages": [{"role": "user", "content": "Hello!"}],
        "extra_body": llm_custom.litellm_extra_body,  # This is the key change!
    }

    print("Example litellm.completion() call would include:")
    print(f"  model: {example_call_kwargs['model']}")
    print(f"  messages: {example_call_kwargs['messages']}")
    print(f"  extra_body: {example_call_kwargs['extra_body']}")

    print("\n=== Benefits ===")
    print("1. Direct mapping to litellm's extra_body parameter")
    print("2. No unnecessary wrapping in 'metadata' key")
    print("3. Flexible support for any custom key-value pairs")
    print("4. Useful for custom inference clusters that need:")
    print("   - Request routing based on metadata")
    print("   - Enhanced logging and tracing")
    print("   - Custom authentication headers")
    print("   - Experiment tracking")
    print("   - User tier-based processing")


if __name__ == "__main__":
    main()
