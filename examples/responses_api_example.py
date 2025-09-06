#!/usr/bin/env python3
"""
Example demonstrating OpenAI Responses API support in OpenHands agent-sdk.

The Responses API is used for reasoning models like o1, o3, and others that
provide reasoning traces. This example shows how to use both the traditional
ChatCompletions API and the new Responses API.
"""

import os

from openhands.sdk.llm import LLM


def main():
    """Demonstrate Responses API usage."""
    # Check if we have an API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Please set OPENAI_API_KEY environment variable")
        return

    # Example 1: Using ChatCompletions API (traditional)
    print("=== ChatCompletions API Example ===")
    llm_chat = LLM(model="gpt-4o-mini")

    messages = [{"role": "user", "content": "What is 2+2? Explain your reasoning."}]

    response = llm_chat.completion(messages=messages)
    print(f"Model: {response.model}")
    print(f"Response: {response.choices[0].message.content}")  # type: ignore[attr-defined]
    print()

    # Example 2: Using Responses API (for reasoning models)
    print("=== Responses API Example ===")
    llm_reasoning = LLM(model="o1-preview")

    # Check if the model supports Responses API
    if llm_reasoning.is_responses_api_supported():
        print(f"Model {llm_reasoning.model} supports Responses API")

        # Use the responses() method instead of completion()
        response = llm_reasoning.responses(
            input="What is 2+2? Show your step-by-step reasoning."
        )

        print(f"Model: {response.model}")
        print(f"Response: {response.choices[0].message.content}")  # type: ignore[attr-defined]

        # The response may include reasoning traces in the output
        if hasattr(response, "reasoning"):
            print(f"Reasoning: {response.reasoning}")  # type: ignore[attr-defined]
    else:
        print(f"Model {llm_reasoning.model} does not support Responses API")

    print()

    # Example 3: Using messages format with Responses API
    print("=== Responses API with Messages ===")
    llm_reasoning = LLM(model="o1-preview")

    if llm_reasoning.is_responses_api_supported():
        messages = [
            {
                "role": "user",
                "content": (
                    "Solve this math problem: If a train travels 60 mph for "
                    "2.5 hours, how far does it go?"
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "The train travels 150 miles (60 mph × 2.5 hours = 150 miles)."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Now, if it continues for another hour at the same speed, "
                    "what's the total distance?"
                ),
            },
        ]

        response = llm_reasoning.responses(messages=messages)
        print(f"Response: {response.choices[0].message.content}")  # type: ignore[attr-defined]

    print()

    # Example 4: Model feature detection
    print("=== Model Feature Detection ===")
    models_to_check = ["gpt-4o", "o1-preview", "claude-3-5-sonnet", "gpt-3.5-turbo"]

    for model in models_to_check:
        llm = LLM(model=model)
        features = llm.get_features()  # type: ignore[attr-defined]
        print(f"{model}:")
        print(f"  - Function calling: {features.supports_function_calling}")
        print(f"  - Reasoning effort: {features.supports_reasoning_effort}")
        print(f"  - Responses API: {features.supports_responses_api}")
        print(f"  - Stop words: {features.supports_stop_words}")
        print()


if __name__ == "__main__":
    main()
