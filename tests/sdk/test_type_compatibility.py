"""Test type compatibility improvements for issue #236.

This test verifies that the changes from list[TextContent | ImageContent] to
Sequence[TextContent | ImageContent] fix the type errors mentioned in the issue.
"""

from openhands.sdk.llm import ImageContent, Message, TextContent, content_to_str


def test_message_content_accepts_text_content_list():
    """Test that Message.content accepts list[TextContent]."""
    # This should work without type errors
    text_contents = [TextContent(text="hello"), TextContent(text="world")]
    message = Message(role="user", content=text_contents)

    assert len(message.content) == 2
    assert isinstance(message.content[0], TextContent)
    assert isinstance(message.content[1], TextContent)
    assert message.content[0].text == "hello"
    assert message.content[1].text == "world"


def test_message_content_accepts_mixed_content_list():
    """Test that Message.content accepts list[TextContent | ImageContent]."""
    # This should also work
    mixed_contents = [
        TextContent(text="hello"),
        ImageContent(
            image_urls=[
                "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            ]
        ),
    ]
    message = Message(role="user", content=mixed_contents)

    assert len(message.content) == 2
    assert isinstance(message.content[0], TextContent)
    assert isinstance(message.content[1], ImageContent)


def test_content_to_str_accepts_text_content_list():
    """Test that content_to_str accepts list[TextContent]."""
    # This should work without type errors
    text_contents = [TextContent(text="hello"), TextContent(text="world")]
    result = content_to_str(text_contents)

    assert result == ["hello", "world"]


def test_content_to_str_accepts_mixed_content_list():
    """Test that content_to_str accepts list[TextContent | ImageContent]."""
    mixed_contents = [
        TextContent(text="hello"),
        ImageContent(
            image_urls=[
                "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            ]
        ),
    ]
    result = content_to_str(mixed_contents)

    assert result == ["hello", "[Image: 1 URLs]"]


def test_message_content_accepts_tuple():
    """Test that Message.content accepts tuple (another Sequence type)."""
    # This should work since Sequence is covariant
    text_contents = (TextContent(text="hello"), TextContent(text="world"))
    message = Message(role="user", content=text_contents)

    assert len(message.content) == 2
    assert isinstance(message.content[0], TextContent)
    assert isinstance(message.content[1], TextContent)
    assert message.content[0].text == "hello"
    assert message.content[1].text == "world"


def test_content_to_str_accepts_tuple():
    """Test that content_to_str accepts tuple."""
    text_contents = (TextContent(text="hello"), TextContent(text="world"))
    result = content_to_str(text_contents)

    assert result == ["hello", "world"]
