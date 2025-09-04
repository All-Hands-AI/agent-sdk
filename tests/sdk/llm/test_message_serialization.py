"""Comprehensive tests for Message serialization behavior.

This module tests the Message class serialization, which now has two distinct paths:
1. Standard Pydantic serialization (model_dump/model_dump_json) for storage - always
preserves structure
2. LLM API serialization (to_llm_dict) for provider consumption - adapts format based on
capabilities

The refactored design separates storage concerns from API formatting concerns.
"""

import json

from openhands.sdk.llm.message import (
    ImageContent,
    Message,
    TextContent,
)


class TestMessageSerialization:
    """Test Message serialization in various scenarios."""

    def test_basic_text_message_dual_serialization(self):
        """Test basic text message has different storage vs LLM serialization."""
        message = Message(
            role="user",
            content=[TextContent(text="Hello, world!")],
        )

        # Storage serialization - always preserves structure
        storage_data = message.model_dump()
        assert isinstance(storage_data["content"], list)
        assert len(storage_data["content"]) == 1
        assert storage_data["content"][0]["text"] == "Hello, world!"
        assert storage_data["role"] == "user"
        assert storage_data["cache_enabled"] is False

        # LLM API serialization - uses string format for simple messages
        llm_data = message.to_llm_dict()
        assert isinstance(llm_data["content"], str)
        assert llm_data["content"] == "Hello, world!"
        assert llm_data["role"] == "user"
        assert llm_data["cache_enabled"] is False

        # Round-trip storage works perfectly
        json_data = message.model_dump_json()
        deserialized = Message.model_validate_json(json_data)
        assert deserialized == message

    def test_cache_enabled_triggers_list_serialization(self):
        """Test message with cache_enabled=True triggers list serializer for LLM."""
        message = Message(
            role="user",
            content=[TextContent(text="Hello, world!")],
            cache_enabled=True,
        )

        # Storage serialization - always list format
        storage_data = message.model_dump()
        assert isinstance(storage_data["content"], list)
        assert storage_data["cache_enabled"] is True

        # LLM API serialization - uses list format due to cache_enabled
        llm_data = message.to_llm_dict()
        assert isinstance(llm_data["content"], list)
        assert len(llm_data["content"]) == 1
        assert llm_data["content"][0]["text"] == "Hello, world!"
        assert llm_data["cache_enabled"] is True

        # Round-trip works
        deserialized = Message.model_validate(storage_data)
        assert deserialized == message

    def test_vision_enabled_triggers_list_serialization(self):
        """Test message with vision_enabled=True triggers list serializer for LLM."""
        message = Message(
            role="user",
            content=[
                TextContent(text="What's in this image?"),
                ImageContent(image_urls=["https://example.com/image.jpg"]),
            ],
            vision_enabled=True,
        )

        # Storage serialization - always list format
        storage_data = message.model_dump()
        assert isinstance(storage_data["content"], list)
        assert len(storage_data["content"]) == 2
        assert storage_data["vision_enabled"] is True

        # LLM API serialization - uses list format due to vision_enabled
        llm_data = message.to_llm_dict()
        assert isinstance(llm_data["content"], list)
        assert len(llm_data["content"]) == 2
        assert llm_data["content"][0]["text"] == "What's in this image?"
        assert llm_data["content"][1]["type"] == "image_url"
        assert llm_data["vision_enabled"] is True

        # Round-trip works
        deserialized = Message.model_validate(storage_data)
        assert deserialized == message

    def test_function_calling_enabled_triggers_list_serialization(self):
        """Test message with function_calling_enabled=True triggers list serializer for
        LLM.
        """
        message = Message(
            role="user",
            content=[TextContent(text="Call a function")],
            function_calling_enabled=True,
        )

        # Storage serialization - always list format
        storage_data = message.model_dump()
        assert isinstance(storage_data["content"], list)
        assert storage_data["function_calling_enabled"] is True

        # LLM API serialization - uses list format due to function_calling_enabled
        llm_data = message.to_llm_dict()
        assert isinstance(llm_data["content"], list)
        assert llm_data["function_calling_enabled"] is True

        # Round-trip works
        deserialized = Message.model_validate(storage_data)
        assert deserialized == message

    def test_force_string_serializer_override(self):
        """Test force_string_serializer=True overrides other settings for LLM."""
        message = Message(
            role="user",
            content=[TextContent(text="Hello, world!")],
            cache_enabled=True,  # Would normally trigger list serializer
            force_string_serializer=True,  # But this forces string
        )

        # Storage serialization - always list format
        storage_data = message.model_dump()
        assert isinstance(storage_data["content"], list)
        assert storage_data["cache_enabled"] is True
        assert storage_data["force_string_serializer"] is True

        # LLM API serialization - forced to string format
        llm_data = message.to_llm_dict()
        assert isinstance(llm_data["content"], str)
        assert llm_data["content"] == "Hello, world!"
        assert llm_data["cache_enabled"] is True
        assert llm_data["force_string_serializer"] is True

        # Round-trip works
        deserialized = Message.model_validate(storage_data)
        assert deserialized == message

    def test_tool_response_message_fields_preserved(self):
        """Test tool response message preserves all fields in both serializations."""
        message = Message(
            role="tool",
            content=[TextContent(text="Weather in NYC: 72°F, sunny")],
            tool_call_id="call_123",
            name="get_weather",
        )

        # Storage serialization
        storage_data = message.model_dump()
        assert isinstance(storage_data["content"], list)
        assert storage_data["tool_call_id"] == "call_123"
        assert storage_data["name"] == "get_weather"

        # LLM API serialization - uses string format for simple tool response
        llm_data = message.to_llm_dict()
        assert isinstance(llm_data["content"], str)
        assert llm_data["content"] == "Weather in NYC: 72°F, sunny"
        assert llm_data["tool_call_id"] == "call_123"
        assert llm_data["name"] == "get_weather"

        # Round-trip works
        deserialized = Message.model_validate(storage_data)
        assert deserialized == message

    def test_empty_content_serialization(self):
        """Test empty content list serialization."""
        message = Message(role="user", content=[])

        # Storage serialization
        storage_data = message.model_dump()
        assert storage_data["content"] == []

        # LLM API serialization - string serializer converts empty list to empty string
        llm_data = message.to_llm_dict()
        assert llm_data["content"] == ""

        # Round-trip works
        deserialized = Message.model_validate(storage_data)
        assert deserialized == message

    def test_multiple_text_content_string_serialization(self):
        """Test multiple TextContent items are joined with newlines in LLM
        serialization.
        """
        message = Message(
            role="user",
            content=[
                TextContent(text="First line"),
                TextContent(text="Second line"),
                TextContent(text="Third line"),
            ],
        )

        # Storage serialization
        storage_data = message.model_dump()
        assert isinstance(storage_data["content"], list)
        assert len(storage_data["content"]) == 3

        # LLM API serialization - joins with newlines
        llm_data = message.to_llm_dict()
        assert isinstance(llm_data["content"], str)
        assert llm_data["content"] == "First line\nSecond line\nThird line"

        # Round-trip works
        deserialized = Message.model_validate(storage_data)
        assert deserialized == message

    def test_all_boolean_fields_preserved_in_serialization(self):
        """Test all boolean configuration fields are preserved in both
        serializations.
        """
        message = Message(
            role="user",
            content=[TextContent(text="Test message")],
            cache_enabled=True,
            vision_enabled=True,
            function_calling_enabled=True,
            force_string_serializer=False,
        )

        # Storage serialization
        storage_data = message.model_dump()
        assert storage_data["cache_enabled"] is True
        assert storage_data["vision_enabled"] is True
        assert storage_data["function_calling_enabled"] is True
        assert storage_data["force_string_serializer"] is False

        # LLM API serialization
        llm_data = message.to_llm_dict()
        assert llm_data["cache_enabled"] is True
        assert llm_data["vision_enabled"] is True
        assert llm_data["function_calling_enabled"] is True
        assert llm_data["force_string_serializer"] is False

        # Round-trip works
        deserialized = Message.model_validate(storage_data)
        assert deserialized == message

    def test_regression_cache_enabled_preservation(self):
        """Regression test: ensure cache_enabled field is preserved after
        serialization.
        """
        message = Message(
            role="user",
            content=[TextContent(text="Test")],
            cache_enabled=True,
        )

        # Storage round-trip
        storage_json = message.model_dump_json()
        storage_deserialized = Message.model_validate_json(storage_json)
        assert storage_deserialized.cache_enabled is True
        assert storage_deserialized == message

        # LLM serialization preserves field
        llm_data = message.to_llm_dict()
        assert llm_data["cache_enabled"] is True

    def test_serialization_path_selection_logic(self):
        """Test the logic that determines which serialization path to use for LLM."""
        # Default settings -> string serializer
        message1 = Message(role="user", content=[TextContent(text="test")])
        llm_data1 = message1.to_llm_dict()
        assert isinstance(llm_data1["content"], str)

        # cache_enabled -> list serializer
        message2 = Message(
            role="user", content=[TextContent(text="test")], cache_enabled=True
        )
        llm_data2 = message2.to_llm_dict()
        assert isinstance(llm_data2["content"], list)

        # vision_enabled -> list serializer
        message3 = Message(
            role="user", content=[TextContent(text="test")], vision_enabled=True
        )
        llm_data3 = message3.to_llm_dict()
        assert isinstance(llm_data3["content"], list)

        # function_calling_enabled -> list serializer
        message4 = Message(
            role="user",
            content=[TextContent(text="test")],
            function_calling_enabled=True,
        )
        llm_data4 = message4.to_llm_dict()
        assert isinstance(llm_data4["content"], list)

        # force_string_serializer overrides everything
        message5 = Message(
            role="user",
            content=[TextContent(text="test")],
            cache_enabled=True,
            vision_enabled=True,
            function_calling_enabled=True,
            force_string_serializer=True,
        )
        llm_data5 = message5.to_llm_dict()
        assert isinstance(llm_data5["content"], str)

        # All storage serializations are lists
        for msg in [message1, message2, message3, message4, message5]:
            storage_data = msg.model_dump()
            assert isinstance(storage_data["content"], list)

    def test_field_defaults_after_minimal_deserialization(self):
        """Test field defaults are correct after deserializing minimal JSON."""
        minimal_json = json.dumps(
            {"role": "user", "content": [{"type": "text", "text": "Hello"}]}
        )

        message = Message.model_validate_json(minimal_json)
        assert message.cache_enabled is False
        assert message.vision_enabled is False
        assert message.function_calling_enabled is False
        assert message.force_string_serializer is False
        assert message.tool_calls is None
        assert message.tool_call_id is None
        assert message.name is None

        # Storage round-trip preserves defaults
        storage_data = message.model_dump()
        deserialized = Message.model_validate(storage_data)
        assert deserialized == message

    def test_content_type_preservation_in_list_serializer(self):
        """Test content types are preserved correctly in list serializer for LLM."""
        message = Message(
            role="user",
            content=[
                TextContent(text="Describe this image"),
                ImageContent(image_urls=["https://example.com/image.jpg"]),
            ],
            vision_enabled=True,  # Forces list serializer
        )

        # Storage serialization
        storage_data = message.model_dump()
        assert isinstance(storage_data["content"], list)
        assert len(storage_data["content"]) == 2

        # LLM API serialization
        llm_data = message.to_llm_dict()
        assert isinstance(llm_data["content"], list)
        assert len(llm_data["content"]) == 2
        assert llm_data["content"][0]["type"] == "text"
        assert llm_data["content"][1]["type"] == "image_url"

        # Round-trip works
        deserialized = Message.model_validate(storage_data)
        assert deserialized == message
