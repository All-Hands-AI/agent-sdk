"""Test to reproduce and verify fix for Pydantic serialization warnings (issue #632)."""

import warnings

from litellm.types.utils import (
    Choices,
    Message as LiteLLMMessage,
    ModelResponse,
    Usage,
)


def test_model_response_serialization_no_warning():
    """Test that serializing ModelResponse doesn't produce Pydantic warnings.

    This test reproduces the issue described in #632 where model_dump() on
    ModelResponse objects triggers Pydantic serializer warnings about
    unexpected field counts and type mismatches.

    The warnings are expected from LiteLLM's internal types, and we verify
    they can be properly suppressed using warnings.filterwarnings.
    """
    # Create a ModelResponse similar to what LiteLLM returns
    response = ModelResponse(
        id="test-id",
        choices=[
            Choices(
                finish_reason="stop",
                index=0,
                message=LiteLLMMessage(
                    content="Let me look at the code and check the real-time logs.",
                    role="assistant",
                ),
            )
        ],
        created=1234567890,
        model="gpt-4o",
        object="chat.completion",
        system_fingerprint="test",
        usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )

    # First, verify that the warning exists without suppression
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        _ = response.model_dump()

        pydantic_warnings = [
            warning
            for warning in w
            if "Pydantic serializer warnings" in str(warning.message)
        ]
        # This confirms the warning is present
        assert len(pydantic_warnings) > 0, (
            "Expected Pydantic serializer warnings to be present without suppression"
        )

    # Now verify that our suppression pattern works
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # Apply the same suppression pattern used in our code
        warnings.filterwarnings("ignore", message="Pydantic serializer warnings")

        serialized = response.model_dump()

        # Check for Pydantic serializer warnings after suppression
        pydantic_warnings = [
            warning
            for warning in w
            if "Pydantic serializer warnings" in str(warning.message)
        ]

        # The warning should be suppressed
        assert len(pydantic_warnings) == 0, (
            f"Expected no Pydantic serializer warnings after suppression, "
            f"but got {len(pydantic_warnings)}: "
            f"{[str(w.message) for w in pydantic_warnings]}"
        )

        # Verify that serialization still works correctly
        assert "choices" in serialized
        assert len(serialized["choices"]) == 1
        assert serialized["choices"][0]["message"]["content"] == (
            "Let me look at the code and check the real-time logs."
        )


def test_message_model_dump_and_validate_no_warning():
    """Test that model_dump and model_validate on Message don't produce warnings.

    This specifically tests the operations in non_native_fc.py lines 81 and 93.
    """
    # Create a message similar to what we get from LLM responses
    orig_msg = LiteLLMMessage(
        content="Let me look at the code.",
        role="assistant",
        reasoning_content="First, I need to understand the problem",
    )

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # This is line 81 in non_native_fc.py
        non_fn_message = orig_msg.model_dump()

        # This is line 93 in non_native_fc.py
        validated_msg = LiteLLMMessage.model_validate(non_fn_message)

        # Check for Pydantic serializer warnings
        pydantic_warnings = [
            warning
            for warning in w
            if "Pydantic serializer warnings" in str(warning.message)
        ]

        assert len(pydantic_warnings) == 0, (
            f"Expected no Pydantic serializer warnings, "
            f"but got {len(pydantic_warnings)}"
        )

        # Verify the operations worked correctly
        assert validated_msg.content == "Let me look at the code."
        assert validated_msg.role == "assistant"
        assert (
            validated_msg.reasoning_content == "First, I need to understand the problem"
        )
