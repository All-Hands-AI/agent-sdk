"""
Comprehensive tests for the env_parser module.

Tests cover:
- Basic environment parsers (bool, int, float, str, etc.)
- Complex parsers (list, dict, union, model parsers)
- Config class parsing with nested attributes and webhook specs
- Self-referential Node model parsing
- Edge cases and error conditions
"""

import json
import os
from enum import Enum
from pathlib import Path
from typing import Literal

import pytest
from pydantic import BaseModel, Field

from openhands.agent_server.config import Config
from openhands.agent_server.env_parser import (
    MISSING,
    BoolEnvParser,
    DelayedParser,
    DictEnvParser,
    EnumEnvParser,
    FloatEnvParser,
    IntEnvParser,
    ListEnvParser,
    ModelEnvParser,
    NoneEnvParser,
    StrEnvParser,
    UnionEnvParser,
    from_env,
    get_env_parser,
    merge,
)
from tests.sdk.utils.test_discriminated_union import Animal, Dog


class NodeModel(BaseModel):
    """Simple node model for testing basic recursive parsing."""

    name: str
    value: int = 0
    children: list["NodeModel"] = Field(default_factory=list)


class OptionalSubModel(BaseModel):
    title: str | None = None
    value: int | None = None


class OptionalModel(BaseModel):
    sub: OptionalSubModel | None = None


# Test enum classes for enum parsing tests
class Color(Enum):
    """Test enum with string values."""

    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class Status(Enum):
    """Test enum with mixed case string values."""

    ACTIVE = "Active"
    INACTIVE = "Inactive"
    PENDING = "Pending"


class Priority(Enum):
    """Test enum with integer values."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


class LogLevel(Enum):
    """Test enum with uppercase string values."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@pytest.fixture
def clean_env():
    """Clean environment fixture that removes test env vars after each test."""
    original_env = os.environ.copy()
    yield
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


def test_bool_env_parser(clean_env):
    """Test BoolEnvParser with various boolean representations."""
    parser = BoolEnvParser()

    # Test missing key
    assert parser.from_env("MISSING_KEY") is MISSING

    # Test truthy values
    for value in ["1", "TRUE", "true", "True"]:
        os.environ["TEST_BOOL"] = value
        assert parser.from_env("TEST_BOOL") is True
        del os.environ["TEST_BOOL"]

    # Test falsy values
    for value in ["0", "FALSE", "false", "False", ""]:
        os.environ["TEST_BOOL"] = value
        assert parser.from_env("TEST_BOOL") is False
        del os.environ["TEST_BOOL"]


def test_int_env_parser(clean_env):
    """Test IntEnvParser with various integer values."""
    parser = IntEnvParser()

    # Test missing key
    assert parser.from_env("MISSING_KEY") is MISSING

    # Test valid integers
    os.environ["TEST_INT"] = "42"
    assert parser.from_env("TEST_INT") == 42

    os.environ["TEST_INT"] = "-123"
    assert parser.from_env("TEST_INT") == -123

    os.environ["TEST_INT"] = "0"
    assert parser.from_env("TEST_INT") == 0

    # Test invalid integer
    os.environ["TEST_INT"] = "not_a_number"
    with pytest.raises(ValueError):
        parser.from_env("TEST_INT")


def test_float_env_parser(clean_env):
    """Test FloatEnvParser with various float values."""
    parser = FloatEnvParser()

    # Test missing key
    assert parser.from_env("MISSING_KEY") is MISSING

    # Test valid floats
    os.environ["TEST_FLOAT"] = "3.14"
    assert parser.from_env("TEST_FLOAT") == 3.14

    os.environ["TEST_FLOAT"] = "-2.5"
    assert parser.from_env("TEST_FLOAT") == -2.5

    os.environ["TEST_FLOAT"] = "0.0"
    assert parser.from_env("TEST_FLOAT") == 0.0

    # Test integer as float
    os.environ["TEST_FLOAT"] = "42"
    assert parser.from_env("TEST_FLOAT") == 42.0

    # Test invalid float
    os.environ["TEST_FLOAT"] = "not_a_number"
    with pytest.raises(ValueError):
        parser.from_env("TEST_FLOAT")


def test_str_env_parser(clean_env):
    """Test StrEnvParser with various string values."""
    parser = StrEnvParser()

    # Test missing key
    assert parser.from_env("MISSING_KEY") is MISSING

    # Test valid strings
    os.environ["TEST_STR"] = "hello world"
    assert parser.from_env("TEST_STR") == "hello world"

    os.environ["TEST_STR"] = ""
    assert parser.from_env("TEST_STR") == ""

    os.environ["TEST_STR"] = "123"
    assert parser.from_env("TEST_STR") == "123"


def test_none_env_parser(clean_env):
    """Test NoneEnvParser behavior."""
    parser = NoneEnvParser()

    # Test missing key (should return None)
    assert parser.from_env("MISSING_KEY") is None

    # Test present key (should return MISSING)
    os.environ["TEST_NONE"] = "any_value"
    assert parser.from_env("TEST_NONE") is MISSING


def test_dict_env_parser(clean_env):
    """Test DictEnvParser with JSON dictionary values."""
    parser = DictEnvParser()

    # Test missing key
    assert parser.from_env("MISSING_KEY") is MISSING

    # Test valid JSON dict
    test_dict = {"key1": "value1", "key2": 42, "key3": True}
    os.environ["TEST_DICT"] = json.dumps(test_dict)
    result = parser.from_env("TEST_DICT")
    assert result == test_dict

    # Test empty dict
    os.environ["TEST_DICT"] = "{}"
    assert parser.from_env("TEST_DICT") == {}

    # Test invalid JSON
    os.environ["TEST_DICT"] = "not_json"
    with pytest.raises(json.JSONDecodeError):
        parser.from_env("TEST_DICT")

    # Test non-dict JSON
    os.environ["TEST_DICT"] = "[1, 2, 3]"
    with pytest.raises(AssertionError):
        parser.from_env("TEST_DICT")


def test_list_env_parser_with_json(clean_env):
    """Test ListEnvParser with JSON list values."""
    item_parser = StrEnvParser()
    parser = ListEnvParser(item_parser)

    # Test JSON list
    test_list = ["item1", "item2", "item3"]
    os.environ["TEST_LIST"] = json.dumps(test_list)
    result = parser.from_env("TEST_LIST")
    assert result == test_list

    # Test empty list
    os.environ["TEST_LIST"] = "[]"
    assert parser.from_env("TEST_LIST") == []

    # Test numeric list (indicating length)
    os.environ["TEST_LIST"] = "3"
    os.environ["TEST_LIST_0"] = "first"
    os.environ["TEST_LIST_1"] = "second"
    os.environ["TEST_LIST_2"] = "third"
    result = parser.from_env("TEST_LIST")
    assert result == ["first", "second", "third"]


def test_list_env_parser_sequential(clean_env):
    """Test ListEnvParser with sequential environment variables."""
    item_parser = StrEnvParser()
    parser = ListEnvParser(item_parser)

    # Test sequential items without base key
    os.environ["TEST_LIST_0"] = "first"
    os.environ["TEST_LIST_1"] = "second"
    os.environ["TEST_LIST_2"] = "third"
    result = parser.from_env("TEST_LIST")
    assert result == ["first", "second", "third"]

    # Test with gaps (should stop at first missing)
    del os.environ["TEST_LIST_1"]
    result = parser.from_env("TEST_LIST")
    assert result == ["first"]


def test_list_env_parser_with_complex_items(clean_env):
    """Test ListEnvParser with complex item types."""
    item_parser = IntEnvParser()
    parser = ListEnvParser(item_parser)

    # Test with integer items
    os.environ["TEST_LIST_0"] = "10"
    os.environ["TEST_LIST_1"] = "20"
    os.environ["TEST_LIST_2"] = "30"
    result = parser.from_env("TEST_LIST")
    assert result == [10, 20, 30]


def test_union_env_parser(clean_env):
    """Test UnionEnvParser with multiple parser types."""
    parsers = [StrEnvParser(), IntEnvParser()]
    parser = UnionEnvParser(parsers)

    # Test with string value that can't be parsed as int - this will fail
    os.environ["TEST_UNION"] = "hello"
    with pytest.raises(ValueError):
        parser.from_env("TEST_UNION")

    # Test with integer value (both parsers succeed, merge returns last)
    os.environ["TEST_UNION"] = "42"
    result = parser.from_env("TEST_UNION")
    # String parser returns "42", int parser returns 42, merge returns 42
    assert result == 42

    # Test with compatible parsers (str and bool)
    bool_str_parsers = [StrEnvParser(), BoolEnvParser()]
    bool_str_parser = UnionEnvParser(bool_str_parsers)

    os.environ["TEST_UNION"] = "true"
    result = bool_str_parser.from_env("TEST_UNION")
    # String parser returns "true", bool parser returns True, merge returns True
    assert result is True


def test_model_env_parser_simple(clean_env):
    """Test ModelEnvParser with a simple model."""

    class SimpleModel(BaseModel):
        name: str = "default"
        count: int = 0

    field_parsers = {
        "name": StrEnvParser(),
        "count": IntEnvParser(),
    }
    parser = ModelEnvParser(field_parsers)

    # Test with individual field overrides
    os.environ["TEST_MODEL_NAME"] = "test_name"
    os.environ["TEST_MODEL_COUNT"] = "42"
    result = parser.from_env("TEST_MODEL")
    expected = {"name": "test_name", "count": 42}
    assert result == expected

    # Test with JSON base and field overrides
    del os.environ["TEST_MODEL_NAME"]  # Clear previous test
    base_data = {"name": "json_name", "count": 10}
    os.environ["TEST_MODEL"] = json.dumps(base_data)
    os.environ["TEST_MODEL_COUNT"] = "99"  # Override count
    result = parser.from_env("TEST_MODEL")
    expected = {"name": "json_name", "count": 99}
    assert result == expected


def test_delayed_parser(clean_env):
    """Test DelayedParser for handling circular dependencies."""
    delayed = DelayedParser()

    # Test without setting parser (should raise assertion error)
    with pytest.raises(AssertionError):
        delayed.from_env("TEST_KEY")

    # Test with parser set
    delayed.parser = StrEnvParser()
    os.environ["TEST_KEY"] = "test_value"
    assert delayed.from_env("TEST_KEY") == "test_value"


def test_merge_function():
    """Test the merge function with various data types."""
    # Test with MISSING values
    assert merge(MISSING, "value") == "value"
    assert merge("value", MISSING) == "value"
    assert merge(MISSING, MISSING) is MISSING

    # Test with simple values (later overwrites earlier)
    assert merge("old", "new") == "new"
    assert merge(1, 2) == 2

    # Test with dictionaries
    dict1 = {"a": 1, "b": 2}
    dict2 = {"b": 3, "c": 4}
    expected = {"a": 1, "b": 3, "c": 4}
    assert merge(dict1, dict2) == expected

    # Test with nested dictionaries
    dict1 = {"nested": {"a": 1, "b": 2}}
    dict2 = {"nested": {"b": 3, "c": 4}}
    expected = {"nested": {"a": 1, "b": 3, "c": 4}}
    assert merge(dict1, dict2) == expected

    # Test with lists
    list1 = [1, 2, 3]
    list2 = [10, 20]
    expected = [10, 20, 3]
    assert merge(list1, list2) == expected

    # Test with lists of different lengths (second list longer) - this will fail
    list1 = [1, 2]
    list2 = [10, 20, 30, 40]
    # The current implementation has a bug - it tries to assign to index that
    # doesn't exist
    with pytest.raises(IndexError):
        merge(list1, list2)

    # Test with lists of different lengths (first list longer)
    list1 = [1, 2, 3, 4]
    list2 = [10, 20]
    expected = [10, 20, 3, 4]
    assert merge(list1, list2) == expected


def test_get_env_parser_basic_types():
    """Test get_env_parser with basic types."""
    parsers = {
        str: StrEnvParser(),
        int: IntEnvParser(),
        float: FloatEnvParser(),
        bool: BoolEnvParser(),
        type(None): NoneEnvParser(),
    }

    # Test basic types
    assert isinstance(get_env_parser(str, parsers), StrEnvParser)
    assert isinstance(get_env_parser(int, parsers), IntEnvParser)
    assert isinstance(get_env_parser(float, parsers), FloatEnvParser)
    assert isinstance(get_env_parser(bool, parsers), BoolEnvParser)
    assert isinstance(get_env_parser(type(None), parsers), NoneEnvParser)


def test_get_env_parser_complex_types():
    """Test get_env_parser with complex types."""
    parsers = {
        str: StrEnvParser(),
        int: IntEnvParser(),
        float: FloatEnvParser(),
        bool: BoolEnvParser(),
        type(None): NoneEnvParser(),
    }

    # Test list type
    list_parser = get_env_parser(list[str], parsers)
    assert isinstance(list_parser, ListEnvParser)
    assert isinstance(list_parser.item_parser, StrEnvParser)

    # Test dict type
    dict_parser = get_env_parser(dict[str, str], parsers)
    assert isinstance(dict_parser, DictEnvParser)

    # Test union type
    union_parser = get_env_parser(str | int, parsers)  # type: ignore[arg-type]
    assert isinstance(union_parser, UnionEnvParser)
    assert len(union_parser.parsers) == 2


def test_get_env_parser_model_type():
    """Test get_env_parser with BaseModel types."""

    class TestModel(BaseModel):
        name: str
        value: int

    parsers = {
        str: StrEnvParser(),
        int: IntEnvParser(),
        float: FloatEnvParser(),
        bool: BoolEnvParser(),
        type(None): NoneEnvParser(),
    }
    model_parser = get_env_parser(TestModel, parsers)
    assert isinstance(model_parser, ModelEnvParser)
    assert "name" in model_parser.parsers
    assert "value" in model_parser.parsers
    assert isinstance(model_parser.parsers["name"], StrEnvParser)
    assert isinstance(model_parser.parsers["value"], IntEnvParser)


def test_config_class_parsing(clean_env):
    """Test parsing the Config class with nested attributes and webhook specs."""
    # Test basic config parsing
    os.environ["OH_SESSION_API_KEYS_0"] = "key1"
    os.environ["OH_SESSION_API_KEYS_1"] = "key2"
    os.environ["OH_ALLOW_CORS_ORIGINS_0"] = "http://localhost:3000"
    os.environ["OH_CONVERSATIONS_PATH"] = "/custom/conversations"
    os.environ["OH_ENABLE_VSCODE"] = "false"

    config = from_env(Config, "OH")

    assert config.session_api_keys == ["key1", "key2"]
    assert config.allow_cors_origins == ["http://localhost:3000"]
    assert config.conversations_path == Path("/custom/conversations")
    assert config.enable_vscode is False


def test_config_webhook_specs_parsing(clean_env):
    """Test parsing webhook specs in Config class."""
    # Test with JSON webhook specs
    webhook_data = [
        {
            "base_url": "https://webhook1.example.com",
            "headers": {"Authorization": "Bearer token1"},
            "event_buffer_size": 5,
            "flush_delay": 15.0,
            "num_retries": 2,
            "retry_delay": 3,
        },
        {
            "base_url": "https://webhook2.example.com",
            "headers": {"X-API-Key": "secret"},
            "event_buffer_size": 20,
            "flush_delay": 60.0,
        },
    ]
    os.environ["OH_WEBHOOKS"] = json.dumps(webhook_data)

    config = from_env(Config, "OH")

    assert len(config.webhooks) == 2
    assert config.webhooks[0].base_url == "https://webhook1.example.com"
    assert config.webhooks[0].headers == {"Authorization": "Bearer token1"}
    assert config.webhooks[0].event_buffer_size == 5
    assert config.webhooks[0].flush_delay == 15.0
    assert config.webhooks[0].num_retries == 2
    assert config.webhooks[0].retry_delay == 3

    assert config.webhooks[1].base_url == "https://webhook2.example.com"
    assert config.webhooks[1].headers == {"X-API-Key": "secret"}
    assert config.webhooks[1].event_buffer_size == 20
    assert config.webhooks[1].flush_delay == 60.0
    # Default values should be used
    assert config.webhooks[1].num_retries == 3
    assert config.webhooks[1].retry_delay == 5


def test_config_webhook_specs_sequential_parsing(clean_env):
    """Test parsing webhook specs using sequential environment variables."""
    # Test with sequential webhook environment variables
    os.environ["OH_WEBHOOKS_0_BASE_URL"] = "https://webhook1.example.com"
    os.environ["OH_WEBHOOKS_0_EVENT_BUFFER_SIZE"] = "15"
    os.environ["OH_WEBHOOKS_0_FLUSH_DELAY"] = "25.5"
    os.environ["OH_WEBHOOKS_0_HEADERS"] = json.dumps({"Auth": "token1"})

    os.environ["OH_WEBHOOKS_1_BASE_URL"] = "https://webhook2.example.com"
    os.environ["OH_WEBHOOKS_1_NUM_RETRIES"] = "5"
    os.environ["OH_WEBHOOKS_1_RETRY_DELAY"] = "10"

    config = from_env(Config, "OH")

    assert len(config.webhooks) == 2
    assert config.webhooks[0].base_url == "https://webhook1.example.com"
    assert config.webhooks[0].event_buffer_size == 15
    assert config.webhooks[0].flush_delay == 25.5
    assert config.webhooks[0].headers == {"Auth": "token1"}

    assert config.webhooks[1].base_url == "https://webhook2.example.com"
    assert config.webhooks[1].num_retries == 5
    assert config.webhooks[1].retry_delay == 10


def test_config_mixed_webhook_parsing(clean_env):
    """Test parsing webhooks with mixed JSON and individual overrides."""
    # Set base JSON with one webhook
    base_webhooks = [
        {
            "base_url": "https://base.example.com",
            "event_buffer_size": 10,
        }
    ]
    os.environ["OH_WEBHOOKS"] = json.dumps(base_webhooks)

    # Override specific fields
    os.environ["OH_WEBHOOKS_0_FLUSH_DELAY"] = "45.0"
    os.environ["OH_WEBHOOKS_0_HEADERS"] = json.dumps({"Override": "header"})

    config = from_env(Config, "OH")

    assert len(config.webhooks) == 1
    # First webhook: base + overrides
    assert config.webhooks[0].base_url == "https://base.example.com"
    assert config.webhooks[0].event_buffer_size == 10
    assert config.webhooks[0].flush_delay == 45.0
    assert config.webhooks[0].headers == {"Override": "header"}


def test_node_model_parsing(clean_env):
    """Test parsing a simple node model."""
    # Test simple node
    os.environ["TEST_NODE_NAME"] = "root"
    os.environ["TEST_NODE_VALUE"] = "42"

    node = from_env(NodeModel, "TEST_NODE")
    assert node.name == "root"
    assert node.value == 42


def test_node_model_parsing_with_recursion(clean_env):
    """Test parsing a simple node model."""
    # Test simple node
    os.environ["TEST_NODE_NAME"] = "root"
    os.environ["TEST_NODE_VALUE"] = "42"
    os.environ["TEST_NODE_CHILDREN_0_NAME"] = "child 1"
    os.environ["TEST_NODE_CHILDREN_1_NAME"] = "child 2"

    node = from_env(NodeModel, "TEST_NODE")
    assert node.name == "root"
    assert node.value == 42
    expected_children = [
        NodeModel(name="child 1"),
        NodeModel(name="child 2"),
    ]
    assert node.children == expected_children


def test_node_model_with_json(clean_env):
    """Test parsing SimpleNode model with JSON."""
    node_data = {
        "name": "json_node",
        "value": 100,
    }
    os.environ["TEST_NODE"] = json.dumps(node_data)

    node = from_env(NodeModel, "TEST_NODE")
    assert node.name == "json_node"
    assert node.value == 100


def test_node_model_mixed_parsing(clean_env):
    """Test parsing SimpleNode model with mixed JSON and env overrides."""
    # Base JSON structure
    base_data = {
        "name": "base_name",
        "value": 10,
    }
    os.environ["TEST_NODE"] = json.dumps(base_data)

    # Override value
    os.environ["TEST_NODE_VALUE"] = "99"

    node = from_env(NodeModel, "TEST_NODE")
    assert node.name == "base_name"
    assert node.value == 99


def test_from_env_with_defaults(clean_env):
    """Test from_env function with default values when no env vars are set."""

    class DefaultModel(BaseModel):
        name: str = "default_name"
        count: int = 42
        enabled: bool = True

    # No environment variables set
    result = from_env(DefaultModel, "TEST")
    assert result.name == "default_name"
    assert result.count == 42
    assert result.enabled is True


def test_from_env_with_custom_parsers(clean_env):
    """Test from_env function with custom parser overrides."""

    class CustomModel(BaseModel):
        value: str

    # Custom parser that always returns "custom"
    class CustomStrParser:
        def from_env(self, key: str):
            return "custom"

    custom_parsers = {str: CustomStrParser()}  # type: ignore[dict-item]
    os.environ["TEST_VALUE"] = "ignored"

    result = from_env(CustomModel, "TEST", custom_parsers)  # type: ignore[arg-type]
    assert result.value == "custom"


def test_error_handling_invalid_json(clean_env):
    """Test error handling with invalid JSON in environment variables."""

    class TestModel(BaseModel):
        data: dict[str, str]

    os.environ["TEST_DATA"] = "invalid_json"

    with pytest.raises(json.JSONDecodeError):
        from_env(TestModel, "TEST")


def test_error_handling_unknown_type():
    """Test error handling with unknown types."""

    class UnknownType:
        pass

    parsers = {}
    with pytest.raises(ValueError, match="unknown_type"):
        get_env_parser(UnknownType, parsers)


def test_optional_fields_parsing(clean_env):
    """Test parsing models with optional fields."""

    class OptionalModel(BaseModel):
        required_field: str
        optional_field: str | None = None
        optional_with_default: str = "default"

    os.environ["TEST_REQUIRED_FIELD"] = "required_value"
    # Don't set optional fields

    result = from_env(OptionalModel, "TEST")
    assert result.required_field == "required_value"
    assert result.optional_field is None
    assert result.optional_with_default == "default"

    # Now set optional field
    os.environ["TEST_OPTIONAL_FIELD"] = "optional_value"
    result = from_env(OptionalModel, "TEST")
    assert result.optional_field == "optional_value"


def test_complex_nested_structure(clean_env):
    """Test parsing complex nested structures."""

    class Address(BaseModel):
        street: str
        city: str
        zip_code: str

    class Person(BaseModel):
        name: str
        age: int
        addresses: list[Address]

    # Set up complex nested data
    person_data = {
        "name": "John Doe",
        "age": 30,
        "addresses": [
            {"street": "123 Main St", "city": "Anytown", "zip_code": "12345"},
            {"street": "456 Oak Ave", "city": "Other City", "zip_code": "67890"},
        ],
    }
    os.environ["TEST_PERSON"] = json.dumps(person_data)

    # Override some nested values
    os.environ["TEST_PERSON_AGE"] = "35"
    os.environ["TEST_PERSON_ADDRESSES_0_CITY"] = "New City"
    os.environ["TEST_PERSON_ADDRESSES_1_ZIP_CODE"] = "99999"

    result = from_env(Person, "TEST_PERSON")
    assert result.name == "John Doe"
    assert result.age == 35  # Overridden
    assert len(result.addresses) == 2

    assert result.addresses[0].street == "123 Main St"
    assert result.addresses[0].city == "New City"  # Overridden
    assert result.addresses[0].zip_code == "12345"

    assert result.addresses[1].street == "456 Oak Ave"
    assert result.addresses[1].city == "Other City"
    assert result.addresses[1].zip_code == "99999"  # Overridden


def test_optional_parameter_parsing(clean_env):
    os.environ["OP_SUB_TITLE"] = "Present"
    os.environ["OP_SUB_VALUE"] = "10"
    model = from_env(OptionalModel, "OP")
    assert model == OptionalModel(sub=OptionalSubModel(title="Present", value=10))


def test_discriminated_union_parsing(clean_env):
    os.environ["A_KIND"] = "Dog"
    os.environ["A_NAME"] = "Bowser"
    os.environ["A_BARKING"] = "1"
    model = from_env(Animal, "A")
    assert model == Dog(name="Bowser", barking=True)


def test_config_vnc_environment_variable_parsing(clean_env):
    """Test parsing OH_ENABLE_VNC environment variable in Config class."""
    # Test OH_ENABLE_VNC set to true
    os.environ["OH_ENABLE_VNC"] = "true"
    config = from_env(Config, "OH")
    assert config.enable_vnc is True

    # Test OH_ENABLE_VNC set to false
    os.environ["OH_ENABLE_VNC"] = "false"
    config = from_env(Config, "OH")
    assert config.enable_vnc is False

    # Test default value when OH_ENABLE_VNC is not set
    del os.environ["OH_ENABLE_VNC"]
    config = from_env(Config, "OH")
    assert config.enable_vnc is False  # Default value from Config class


@pytest.mark.parametrize(
    "env_value,expected",
    [
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("1", True),
        ("false", False),
        ("False", False),
        ("FALSE", False),
        ("0", False),
        ("", False),
    ],
)
def test_config_vnc_various_boolean_values(clean_env, env_value, expected):
    """Test that OH_ENABLE_VNC accepts various boolean representations."""
    os.environ["OH_ENABLE_VNC"] = env_value
    config = from_env(Config, "OH")
    assert config.enable_vnc is expected, (
        f"Failed for OH_ENABLE_VNC='{env_value}', expected {expected}"
    )


# Enum parsing tests
def test_enum_env_parser_with_string_enum(clean_env):
    """Test EnumEnvParser with string-valued enum."""
    parser = EnumEnvParser(Color)

    # Test missing key
    assert parser.from_env("MISSING_KEY") is MISSING

    # Test exact value match
    os.environ["TEST_COLOR"] = "red"
    assert parser.from_env("TEST_COLOR") == "red"

    # Test case-insensitive value match
    os.environ["TEST_COLOR"] = "RED"
    assert parser.from_env("TEST_COLOR") == "red"

    os.environ["TEST_COLOR"] = "Red"
    assert parser.from_env("TEST_COLOR") == "red"

    # Test case-insensitive name match
    os.environ["TEST_COLOR"] = "red"
    assert parser.from_env("TEST_COLOR") == "red"

    os.environ["TEST_COLOR"] = "RED"
    assert parser.from_env("TEST_COLOR") == "red"


def test_enum_env_parser_with_mixed_case_enum(clean_env):
    """Test EnumEnvParser with mixed case string values."""
    parser = EnumEnvParser(Status)

    # Test exact value match
    os.environ["TEST_STATUS"] = "Active"
    assert parser.from_env("TEST_STATUS") == "Active"

    # Test case-insensitive value match
    os.environ["TEST_STATUS"] = "active"
    assert parser.from_env("TEST_STATUS") == "Active"

    os.environ["TEST_STATUS"] = "ACTIVE"
    assert parser.from_env("TEST_STATUS") == "Active"

    # Test case-insensitive name match
    os.environ["TEST_STATUS"] = "active"
    assert parser.from_env("TEST_STATUS") == "Active"


def test_enum_env_parser_with_integer_enum(clean_env):
    """Test EnumEnvParser with integer-valued enum."""
    parser = EnumEnvParser(Priority)

    # Test exact value match (as string)
    os.environ["TEST_PRIORITY"] = "1"
    assert parser.from_env("TEST_PRIORITY") == 1

    os.environ["TEST_PRIORITY"] = "2"
    assert parser.from_env("TEST_PRIORITY") == 2

    # Test case-insensitive name match
    os.environ["TEST_PRIORITY"] = "low"
    assert parser.from_env("TEST_PRIORITY") == 1

    os.environ["TEST_PRIORITY"] = "LOW"
    assert parser.from_env("TEST_PRIORITY") == 1

    os.environ["TEST_PRIORITY"] = "Medium"
    assert parser.from_env("TEST_PRIORITY") == 2


def test_enum_env_parser_with_uppercase_enum(clean_env):
    """Test EnumEnvParser with uppercase string values."""
    parser = EnumEnvParser(LogLevel)

    # Test exact value match
    os.environ["TEST_LOG_LEVEL"] = "DEBUG"
    assert parser.from_env("TEST_LOG_LEVEL") == "DEBUG"

    # Test case-insensitive value match
    os.environ["TEST_LOG_LEVEL"] = "debug"
    assert parser.from_env("TEST_LOG_LEVEL") == "DEBUG"

    os.environ["TEST_LOG_LEVEL"] = "Debug"
    assert parser.from_env("TEST_LOG_LEVEL") == "DEBUG"

    # Test case-insensitive name match
    os.environ["TEST_LOG_LEVEL"] = "info"
    assert parser.from_env("TEST_LOG_LEVEL") == "INFO"


def test_enum_env_parser_with_literal_type(clean_env):
    """Test EnumEnvParser with Literal types."""
    TaskStatus = Literal["todo", "in_progress", "done"]
    parser = EnumEnvParser(TaskStatus)

    # Test exact match
    os.environ["TEST_TASK_STATUS"] = "todo"
    assert parser.from_env("TEST_TASK_STATUS") == "todo"

    os.environ["TEST_TASK_STATUS"] = "in_progress"
    assert parser.from_env("TEST_TASK_STATUS") == "in_progress"

    # Test case-insensitive match
    os.environ["TEST_TASK_STATUS"] = "TODO"
    assert parser.from_env("TEST_TASK_STATUS") == "todo"

    os.environ["TEST_TASK_STATUS"] = "In_Progress"
    assert parser.from_env("TEST_TASK_STATUS") == "in_progress"

    os.environ["TEST_TASK_STATUS"] = "DONE"
    assert parser.from_env("TEST_TASK_STATUS") == "done"


def test_enum_env_parser_error_handling(clean_env):
    """Test EnumEnvParser error handling for invalid values."""
    parser = EnumEnvParser(Color)

    # Test invalid value for enum
    os.environ["TEST_COLOR"] = "purple"
    with pytest.raises(ValueError) as exc_info:
        parser.from_env("TEST_COLOR")

    error_msg = str(exc_info.value)
    assert "Invalid value 'purple' for Color" in error_msg
    assert "Valid values: ['red', 'green', 'blue']" in error_msg
    assert "Valid names: ['RED', 'GREEN', 'BLUE']" in error_msg


def test_enum_env_parser_literal_fallback_behavior(clean_env):
    """Test EnumEnvParser fallback behavior for invalid Literal values."""
    TaskStatus = Literal["todo", "in_progress", "done"]
    parser = EnumEnvParser(TaskStatus)

    # Test invalid value for Literal - should return the value as-is
    # to allow Pydantic validation to handle the error
    os.environ["TEST_TASK_STATUS"] = "invalid_status"
    result = parser.from_env("TEST_TASK_STATUS")
    assert result == "invalid_status"


def test_get_env_parser_with_enum_types():
    """Test get_env_parser function with enum types."""
    parsers = {
        str: StrEnvParser(),
        int: IntEnvParser(),
        float: FloatEnvParser(),
        bool: BoolEnvParser(),
        type(None): NoneEnvParser(),
    }

    # Test with enum.Enum subclass
    color_parser = get_env_parser(Color, parsers)
    assert isinstance(color_parser, EnumEnvParser)
    assert color_parser.enum_type == Color

    # Test with Literal type
    TaskStatus = Literal["todo", "in_progress", "done"]
    status_parser = get_env_parser(TaskStatus, parsers)
    assert isinstance(status_parser, EnumEnvParser)
    assert status_parser.enum_type == TaskStatus


def test_from_env_with_enum_model(clean_env):
    """Test from_env function with a model containing enum fields."""

    class TaskModel(BaseModel):
        name: str
        status: Literal["todo", "in_progress", "done"] = "todo"
        priority: Priority = Priority.LOW
        color: Color = Color.RED

    # Test with environment variables
    os.environ["TASK_NAME"] = "Test Task"
    os.environ["TASK_STATUS"] = "IN_PROGRESS"
    os.environ["TASK_PRIORITY"] = "high"
    os.environ["TASK_COLOR"] = "BLUE"

    task = from_env(TaskModel, "TASK")

    assert task.name == "Test Task"
    assert task.status == "in_progress"
    assert task.priority == Priority.HIGH
    assert task.color == Color.BLUE


def test_from_env_with_enum_defaults(clean_env):
    """Test from_env function with enum defaults when no env vars are set."""

    class TaskModel(BaseModel):
        name: str = "Default Task"
        status: Literal["todo", "in_progress", "done"] = "todo"
        priority: Priority = Priority.LOW
        color: Color = Color.RED

    # No environment variables set
    task = from_env(TaskModel, "TASK")

    assert task.name == "Default Task"
    assert task.status == "todo"
    assert task.priority == Priority.LOW
    assert task.color == Color.RED


def test_enum_in_complex_nested_structure(clean_env):
    """Test enum parsing in complex nested structures."""

    class TaskItem(BaseModel):
        title: str
        status: Literal["todo", "in_progress", "done"]
        priority: Priority

    class Project(BaseModel):
        name: str
        tasks: list[TaskItem]

    # Set up complex nested data with enums
    project_data = {
        "name": "Test Project",
        "tasks": [
            {"title": "Task 1", "status": "todo", "priority": 1},
            {"title": "Task 2", "status": "in_progress", "priority": 2},
        ],
    }
    os.environ["TEST_PROJECT"] = json.dumps(project_data)

    # Override some enum values
    os.environ["TEST_PROJECT_TASKS_0_STATUS"] = "IN_PROGRESS"
    os.environ["TEST_PROJECT_TASKS_1_PRIORITY"] = "HIGH"

    result = from_env(Project, "TEST_PROJECT")

    assert result.name == "Test Project"
    assert len(result.tasks) == 2

    assert result.tasks[0].title == "Task 1"
    assert result.tasks[0].status == "in_progress"  # Overridden
    assert result.tasks[0].priority == Priority.LOW

    assert result.tasks[1].title == "Task 2"
    assert result.tasks[1].status == "in_progress"
    assert result.tasks[1].priority == Priority.HIGH  # Overridden
