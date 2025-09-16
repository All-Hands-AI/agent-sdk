"""Test CondenserSpec class functionality."""

import pytest
from pydantic import ValidationError

from openhands.sdk.context.condenser.spec import CondenserSpec


def test_condenser_spec_minimal():
    """Test creating CondenserSpec with minimal required fields."""
    spec = CondenserSpec(name="NoOpCondenser")

    assert spec.name == "NoOpCondenser"
    assert spec.params == {}


def test_condenser_spec_with_params():
    """Test creating CondenserSpec with parameters."""
    params = {"max_size": 80, "keep_first": 10}
    spec = CondenserSpec(name="LLMSummarizingCondenser", params=params)

    assert spec.name == "LLMSummarizingCondenser"
    assert spec.params == params


def test_condenser_spec_empty_params():
    """Test creating CondenserSpec with empty parameters."""
    spec = CondenserSpec(name="NoOpCondenser", params={})

    assert spec.name == "NoOpCondenser"
    assert spec.params == {}


def test_condenser_spec_complex_params():
    """Test creating CondenserSpec with complex parameters."""
    params = {
        "llm": {"model": "gpt-4", "api_key": "sk-test"},
        "max_size": 120,
        "keep_first": 15,
        "summarization_config": {"temperature": 0.7, "max_tokens": 1000},
    }

    spec = CondenserSpec(name="LLMSummarizingCondenser", params=params)

    assert spec.name == "LLMSummarizingCondenser"
    assert spec.params == params
    assert spec.params["llm"]["model"] == "gpt-4"
    assert spec.params["summarization_config"]["temperature"] == 0.7


def test_condenser_spec_serialization():
    """Test CondenserSpec serialization and deserialization."""
    params = {"max_size": 100, "keep_first": 5}
    spec = CondenserSpec(name="LLMSummarizingCondenser", params=params)

    # Test model_dump
    spec_dict = spec.model_dump()
    assert spec_dict["name"] == "LLMSummarizingCondenser"
    assert spec_dict["params"] == params

    # Test model_dump_json
    spec_json = spec.model_dump_json()
    assert isinstance(spec_json, str)

    # Test deserialization
    spec_restored = CondenserSpec.model_validate_json(spec_json)
    assert spec_restored.name == "LLMSummarizingCondenser"
    assert spec_restored.params == params


def test_condenser_spec_validation_requires_name():
    """Test that CondenserSpec requires a name."""
    with pytest.raises(ValidationError):
        CondenserSpec()  # type: ignore


def test_condenser_spec_examples_from_docstring():
    """Test the examples provided in CondenserSpec docstring."""
    # Test the example from the docstring
    spec = CondenserSpec(
        name="LLMSummarizingCondenser",
        params={
            "llm": {"model": "gpt-5", "api_key": "sk-XXX"},
            "max_size": 80,
            "keep_first": 10,
        },
    )

    assert spec.name == "LLMSummarizingCondenser"
    assert spec.params["llm"]["model"] == "gpt-5"
    assert spec.params["llm"]["api_key"] == "sk-XXX"
    assert spec.params["max_size"] == 80
    assert spec.params["keep_first"] == 10


def test_condenser_spec_different_condenser_types():
    """Test creating CondenserSpec for different condenser types."""
    # NoOpCondenser
    no_op_spec = CondenserSpec(name="NoOpCondenser", params={})
    assert no_op_spec.name == "NoOpCondenser"
    assert no_op_spec.params == {}

    # LLMSummarizingCondenser
    llm_spec = CondenserSpec(
        name="LLMSummarizingCondenser",
        params={"llm": {"model": "gpt-4"}, "max_size": 100, "keep_first": 8},
    )
    assert llm_spec.name == "LLMSummarizingCondenser"
    assert llm_spec.params["max_size"] == 100

    # PipelineCondenser
    pipeline_spec = CondenserSpec(
        name="PipelineCondenser",
        params={
            "condensers": [
                {"name": "RollingCondenser", "params": {"max_size": 50}},
                {
                    "name": "LLMSummarizingCondenser",
                    "params": {"llm": {"model": "gpt-4"}},
                },
            ]
        },
    )
    assert pipeline_spec.name == "PipelineCondenser"
    assert len(pipeline_spec.params["condensers"]) == 2


def test_condenser_spec_nested_params():
    """Test CondenserSpec with nested parameter structures."""
    params = {
        "llm": {
            "model": "gpt-4",
            "api_key": "sk-test",
            "config": {"temperature": 0.5, "max_tokens": 2000, "top_p": 0.9},
        },
        "condensation_settings": {
            "max_size": 150,
            "keep_first": 20,
            "strategies": ["rolling", "summarizing"],
        },
    }

    spec = CondenserSpec(name="AdvancedCondenser", params=params)

    assert spec.name == "AdvancedCondenser"
    assert spec.params["llm"]["config"]["temperature"] == 0.5
    assert spec.params["condensation_settings"]["strategies"] == [
        "rolling",
        "summarizing",
    ]


def test_condenser_spec_field_descriptions():
    """Test that CondenserSpec fields have proper descriptions."""
    fields = CondenserSpec.model_fields

    assert "name" in fields
    name_desc = fields["name"].description
    assert name_desc is not None
    assert "Name of the condenser class" in name_desc
    assert "Must be importable from openhands.sdk.context.condenser" in name_desc

    assert "params" in fields
    params_desc = fields["params"].description
    assert params_desc is not None
    assert "Parameters for the condenser's .create() method" in params_desc


def test_condenser_spec_default_params():
    """Test that CondenserSpec has correct default for params."""
    spec = CondenserSpec(name="TestCondenser")
    assert spec.params == {}


def test_condenser_spec_immutability():
    """Test that CondenserSpec behaves correctly with parameter modifications."""
    original_params = {"max_size": 80}
    spec = CondenserSpec(name="LLMSummarizingCondenser", params=original_params)

    # Modifying the original params should not affect the spec
    original_params["max_size"] = 120
    assert spec.params["max_size"] == 80


def test_condenser_spec_validation_edge_cases():
    """Test CondenserSpec validation with edge cases."""
    # Empty string name should be invalid
    with pytest.raises(ValidationError):
        CondenserSpec(name="")

    # Default params should be empty dict
    spec = CondenserSpec(name="TestCondenser")
    assert spec.params == {}


def test_condenser_spec_repr():
    """Test CondenserSpec string representation."""
    spec = CondenserSpec(name="LLMSummarizingCondenser", params={"max_size": 80})
    repr_str = repr(spec)

    assert "CondenserSpec" in repr_str
    assert "LLMSummarizingCondenser" in repr_str


def test_condenser_spec_with_llm_object():
    """Test CondenserSpec with actual LLM object in params."""
    from openhands.sdk.llm import LLM

    llm = LLM(model="test-model")
    params = {"llm": llm, "max_size": 80, "keep_first": 10}

    spec = CondenserSpec(name="LLMSummarizingCondenser", params=params)

    assert spec.name == "LLMSummarizingCondenser"
    assert spec.params["llm"] == llm
    assert spec.params["max_size"] == 80
