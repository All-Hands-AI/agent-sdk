from __future__ import annotations


def is_gpt5_model(model: str) -> bool:
    """Return True if model appears to be an OpenAI GPT-5 family model.

    Accepts forms like:
    - "gpt-5*"
    - "openai/gpt-5*"
    - "litellm_proxy/openai/gpt-5*" (proxy-prefixed)
    """
    ml = model.lower()
    return "/gpt-5" in ml or ml.startswith("gpt-5")
