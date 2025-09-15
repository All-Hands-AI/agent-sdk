from unittest.mock import patch

from openhands.sdk.llm.utils.model_list import get_unverified_models


def test_organize_models_and_providers():
    models = [
        "openai/gpt-4o",
        "anthropic/claude-sonnet-4-20250514",
        "o3",
        "o4-mini",
        "devstral-small-2505",
        "mistral/devstral-small-2505",
        "anthropic.claude-3-5",  # Ignore dot separator for anthropic
        "unknown-model",
        "custom-provider/custom-model",
        "openai/another-model",
    ]

    with patch(
        "openhands.sdk.llm.utils.model_features.get_supported_llm_models",
        return_value=models,
    ):
        result = get_unverified_models()

        assert "openai" in result
        assert "anthropic" not in result  # don't include verified models
        assert "mistral" not in result
        assert "other" in result

        assert len(result["openai"]) == 1
        assert "another-model" in result["openai"]

        assert len(result["other"]) == 1
        assert "unknown-model" in result["other"]
