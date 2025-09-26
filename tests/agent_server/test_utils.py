"""
Unit tests for the utils module, focusing on the update_with_config_var function
and its supporting functions for recursive environment variable parsing.
"""

import os
from pathlib import Path
from unittest.mock import patch

from pydantic import BaseModel, Field

from openhands.agent_server.utils import update_with_config_var


class SimpleModel(BaseModel):
    """Simple test model for basic field testing."""

    name: str = "default"
    count: int = 0
    enabled: bool = True
    path: Path = Path("/default")
    tags: list[str] = Field(default_factory=list)


class NestedModel(BaseModel):
    """Nested model for testing nested field parsing."""

    title: str = "nested"
    value: int = 42


class ComplexModel(BaseModel):
    """Complex model with nested objects and lists."""

    simple_field: str = "simple"
    nested: NestedModel = Field(default_factory=NestedModel)
    items: list[NestedModel] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)


class TestUpdateWithConfigVar:
    """Test cases for the update_with_config_var function."""

    def test_simple_fields(self):
        """Test parsing simple fields from environment variables."""
        model = SimpleModel()

        with patch.dict(
            os.environ,
            {
                "MYAPP_NAME": "test_name",
                "MYAPP_COUNT": "42",
                "MYAPP_ENABLED": "false",
                "MYAPP_PATH": "/custom/path",
                "MYAPP_TAGS": "tag1,tag2,tag3",
            },
        ):
            updated = update_with_config_var(model, prefix="MYAPP_")

            assert updated.name == "test_name"
            assert updated.count == 42
            assert not updated.enabled
            assert updated.path == Path("/custom/path")
            assert updated.tags == ["tag1", "tag2", "tag3"]

    def test_nested_object_fields(self):
        """Test parsing nested object fields from environment variables."""
        model = ComplexModel()

        with patch.dict(
            os.environ,
            {
                "SIMPLE_FIELD": "updated_simple",
                "NESTED_TITLE": "updated_title",
                "NESTED_VALUE": "100",
            },
        ):
            updated = update_with_config_var(model)

            assert updated.simple_field == "updated_simple"
            assert updated.nested.title == "updated_title"
            assert updated.nested.value == 100

    def test_list_with_indices(self):
        """Test parsing list items with indices from environment variables."""
        model = ComplexModel()

        with patch.dict(
            os.environ,
            {
                "ITEMS_0_TITLE": "first_item",
                "ITEMS_0_VALUE": "10",
                "ITEMS_1_TITLE": "second_item",
                "ITEMS_1_VALUE": "20",
                "ITEMS_2_TITLE": "third_item",
                "ITEMS_2_VALUE": "30",
            },
        ):
            updated = update_with_config_var(model)

            assert len(updated.items) == 3
            assert updated.items[0].title == "first_item"
            assert updated.items[0].value == 10
            assert updated.items[1].title == "second_item"
            assert updated.items[1].value == 20
            assert updated.items[2].title == "third_item"
            assert updated.items[2].value == 30

    def test_dictionary_fields(self):
        """Test parsing dictionary fields from environment variables."""
        model = ComplexModel()

        with patch.dict(
            os.environ,
            {
                "HEADERS_AUTHORIZATION": "Bearer token123",
                "HEADERS_CONTENT_TYPE": "application/json",
                "HEADERS_X_API_KEY": "secret456",
            },
        ):
            updated = update_with_config_var(model)

            assert len(updated.headers) == 3
            assert updated.headers["AUTHORIZATION"] == "Bearer token123"
            assert updated.headers["CONTENT_TYPE"] == "application/json"
            assert updated.headers["X_API_KEY"] == "secret456"

    def test_mixed_configurations(self):
        """Test mixing simple, nested, list, and dictionary configurations."""
        model = ComplexModel()

        with patch.dict(
            os.environ,
            {
                "SIMPLE_FIELD": "mixed_test",
                "NESTED_TITLE": "mixed_nested",
                "ITEMS_0_TITLE": "mixed_item",
                "ITEMS_0_VALUE": "99",
                "HEADERS_TEST_HEADER": "test_value",
            },
        ):
            updated = update_with_config_var(model)

            assert updated.simple_field == "mixed_test"
            assert updated.nested.title == "mixed_nested"
            assert len(updated.items) == 1
            assert updated.items[0].title == "mixed_item"
            assert updated.items[0].value == 99
            assert updated.headers["TEST_HEADER"] == "test_value"

    def test_sparse_list_indices(self):
        """Test list configuration with sparse indices (gaps in numbering)."""
        model = ComplexModel()

        with patch.dict(
            os.environ,
            {
                "ITEMS_0_TITLE": "first",
                "ITEMS_0_VALUE": "1",
                "ITEMS_5_TITLE": "sixth",
                "ITEMS_5_VALUE": "6",
            },
        ):
            updated = update_with_config_var(model)

            # Should create 6 items (0-5)
            assert len(updated.items) == 6
            assert updated.items[0].title == "first"
            assert updated.items[0].value == 1
            assert updated.items[5].title == "sixth"
            assert updated.items[5].value == 6

            # Middle items should have default values
            for i in range(1, 5):
                assert updated.items[i].title == "nested"  # default value
                assert updated.items[i].value == 42  # default value

    def test_boolean_parsing_variations(self):
        """Test various boolean value formats."""
        model = SimpleModel()

        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
            ("no", False),
            ("off", False),
            ("", False),
            ("invalid", False),
        ]

        for env_value, expected in test_cases:
            with patch.dict(os.environ, {"ENABLED": env_value}):
                updated = update_with_config_var(model)
                assert updated.enabled == expected, f"Failed for value: {env_value}"

    def test_integer_parsing(self):
        """Test integer parsing with various formats."""
        model = SimpleModel()

        test_cases = [
            ("0", 0),
            ("42", 42),
            ("-10", -10),
            ("1000", 1000),
        ]

        for env_value, expected in test_cases:
            with patch.dict(os.environ, {"COUNT": env_value}):
                updated = update_with_config_var(model)
                assert updated.count == expected, f"Failed for value: {env_value}"

    def test_invalid_integer_ignored(self):
        """Test that invalid integer values are ignored."""
        model = SimpleModel(count=99)

        with patch.dict(os.environ, {"COUNT": "not_a_number"}):
            updated = update_with_config_var(model)
            # Should keep original value when parsing fails
            assert updated.count == 99

    def test_path_parsing(self):
        """Test Path object parsing."""
        model = SimpleModel()

        test_cases = [
            "/absolute/path",
            "relative/path",
            "~/home/path",
            ".",
            "..",
        ]

        for path_str in test_cases:
            with patch.dict(os.environ, {"MYAPP_PATH": path_str}):
                updated = update_with_config_var(model, prefix="MYAPP_")
                assert updated.path == Path(path_str)

    def test_list_parsing_variations(self):
        """Test list parsing with various formats."""
        model = SimpleModel()

        test_cases = [
            ("", []),
            ("single", ["single"]),
            ("one,two,three", ["one", "two", "three"]),
            ("  spaced  ,  items  ", ["  spaced  ", "  items  "]),
            ("item,with,commas,", ["item", "with", "commas", ""]),
        ]

        for env_value, expected in test_cases:
            with patch.dict(os.environ, {"TAGS": env_value}):
                updated = update_with_config_var(model)
                assert updated.tags == expected, f"Failed for value: {env_value}"

    def test_case_insensitive_field_matching(self):
        """Test that field matching is case insensitive."""
        model = SimpleModel()

        with patch.dict(
            os.environ,
            {
                "name": "lowercase",  # should match 'name' field
                "COUNT": "42",  # uppercase
                "Enabled": "false",  # mixed case
            },
        ):
            updated = update_with_config_var(model)

            assert updated.name == "lowercase"
            assert updated.count == 42
            assert not updated.enabled

    def test_no_environment_variables(self):
        """Test behavior when no matching environment variables exist."""
        model = SimpleModel(name="original", count=100)

        # Clear environment of any matching variables
        with patch.dict(os.environ, {}, clear=True):
            updated = update_with_config_var(model)

            # Should return identical model
            assert updated.name == "original"
            assert updated.count == 100
            assert updated.enabled  # default True
            assert updated.path == Path("/default")
            assert updated.tags == []

    def test_partial_environment_override(self):
        """Test that only specified environment variables override defaults."""
        model = SimpleModel(name="original", count=100, enabled=False)

        with patch.dict(os.environ, {"NAME": "updated_name"}):
            updated = update_with_config_var(model)

            # Only name should be updated
            assert updated.name == "updated_name"
            assert updated.count == 100  # unchanged
            assert not updated.enabled  # unchanged
            assert updated.path == Path("/default")  # unchanged
            assert updated.tags == []  # unchanged

    def test_immutability(self):
        """Test that original model is not modified."""
        original = SimpleModel(name="original", count=100)

        with patch.dict(os.environ, {"NAME": "updated", "COUNT": "200"}):
            updated = update_with_config_var(original)

            # Original should be unchanged
            assert original.name == "original"
            assert original.count == 100

            # Updated should have new values
            assert updated.name == "updated"
            assert updated.count == 200

            # Should be different objects
            assert original is not updated

    def test_deep_nesting(self):
        """Test deeply nested field parsing."""
        model = ComplexModel()

        with patch.dict(
            os.environ,
            {
                "ITEMS_0_TITLE": "nested_title",
                "ITEMS_0_VALUE": "123",
                "ITEMS_1_TITLE": "another_title",
                "ITEMS_1_VALUE": "456",
            },
        ):
            updated = update_with_config_var(model)

            assert len(updated.items) == 2
            assert updated.items[0].title == "nested_title"
            assert updated.items[0].value == 123
            assert updated.items[1].title == "another_title"
            assert updated.items[1].value == 456

    def test_invalid_field_names_ignored(self):
        """Test that invalid field names are ignored."""
        model = SimpleModel()

        with patch.dict(
            os.environ,
            {
                "NAME": "valid_field",
                "INVALID_FIELD": "should_be_ignored",
                "ANOTHER_INVALID": "also_ignored",
            },
        ):
            updated = update_with_config_var(model)

            # Only valid field should be updated
            assert updated.name == "valid_field"
            # Other fields should have defaults
            assert updated.count == 0
            assert updated.enabled

    def test_prefix_parameter(self):
        """Test that prefix parameter filters environment variables correctly."""
        model = SimpleModel()

        with patch.dict(
            os.environ,
            {
                # These should be ignored (no prefix)
                "NAME": "ignored_name",
                "COUNT": "999",
                # These should be used (with prefix)
                "MYAPP_NAME": "prefixed_name",
                "MYAPP_COUNT": "123",
                "MYAPP_ENABLED": "false",
            },
        ):
            # Without prefix - should ignore prefixed variables
            updated_no_prefix = update_with_config_var(model)
            assert updated_no_prefix.name == "ignored_name"  # Uses NAME
            assert updated_no_prefix.count == 999  # Uses COUNT
            assert updated_no_prefix.enabled  # Default value (MYAPP_ENABLED ignored)

            # With prefix - should only use prefixed variables
            updated_with_prefix = update_with_config_var(model, prefix="MYAPP_")
            assert updated_with_prefix.name == "prefixed_name"  # Uses MYAPP_NAME
            assert updated_with_prefix.count == 123  # Uses MYAPP_COUNT
            assert not updated_with_prefix.enabled  # Uses MYAPP_ENABLED
