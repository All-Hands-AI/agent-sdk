from pydantic import SecretStr

from openhands.sdk import LLM, ImageContent, Message, TextContent


def test_messages_to_responses_input_image_parity():
    llm = LLM(model="openai/gpt-5-test", api_key=SecretStr("x"))
    messages = [
        Message(
            role="user",
            content=[
                TextContent(text="see this"),
                ImageContent(image_urls=["https://a/b.png", "file:///tmp/x.png"]),
            ],
        )
    ]
    formatted = llm.format_messages_for_llm(messages)

    # Emulate internal helper
    items, instructions = llm._messages_to_responses_input(formatted)
    assert instructions is None
    assert len(items) == 1
    assert items[0]["type"] == "message"
    content = items[0]["content"]
    assert isinstance(content, list)
    # If vision is active expect input_image; otherwise expect only input_text
    kinds = [c.get("type") for c in content]
    assert "input_text" in kinds
    if llm.vision_is_active():
        assert "input_image" in kinds
        # Image shapes mirrored
        for c in content:
            if c.get("type") == "input_image":
                iu = c.get("image_url", {})
                assert isinstance(iu, dict) and "url" in iu
