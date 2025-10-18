from litellm.exceptions import BadRequestError

from openhands.sdk.llm.llm import LLM


def test_is_context_window_exceeded_exception_matches_exceeds_phrase():
    # Simulate OpenAI Responses API style error wording for GPT-5
    err = BadRequestError(
        message=(
            "Your input exceeds the context window of this model. "
            "Please adjust your input and try again."
        ),
        llm_provider="openai",
        model="gpt-5-codex",
    )

    assert LLM.is_context_window_exceeded_exception(err) is True
