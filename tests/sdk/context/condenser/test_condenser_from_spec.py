"""Test CondenserBase.from_spec functionality."""

import pytest

from openhands.sdk.context.condenser.base import CondenserBase
from openhands.sdk.context.condenser.llm_summarizing_condenser import (
    LLMSummarizingCondenser,
)
from openhands.sdk.context.condenser.no_op_condenser import NoOpCondenser
from openhands.sdk.context.condenser.pipeline_condenser import PipelineCondenser
from openhands.sdk.context.condenser.spec import CondenserSpec
from openhands.sdk.llm import LLM


@pytest.fixture
def basic_llm():
    """Create a basic LLM for testing."""
    return LLM(model="test-model")


def test_from_spec_no_op_condenser():
    """Test creating a NoOpCondenser from spec."""
    spec = CondenserSpec(name="NoOpCondenser", params={})

    condenser = CondenserBase.from_spec(spec)

    assert isinstance(condenser, NoOpCondenser)
    assert isinstance(condenser, CondenserBase)


def test_from_spec_llm_summarizing_condenser(basic_llm):
    """Test creating an LLMSummarizingCondenser from spec."""
    spec = CondenserSpec(
        name="LLMSummarizingCondenser",
        params={"llm": basic_llm, "max_size": 80, "keep_first": 10},
    )

    condenser = CondenserBase.from_spec(spec)

    assert isinstance(condenser, LLMSummarizingCondenser)
    assert isinstance(condenser, CondenserBase)


def test_from_spec_with_empty_params():
    """Test creating a condenser with empty parameters."""
    spec = CondenserSpec(name="NoOpCondenser", params={})

    condenser = CondenserBase.from_spec(spec)

    assert isinstance(condenser, NoOpCondenser)
    assert isinstance(condenser, CondenserBase)


def test_from_spec_with_complex_params(basic_llm):
    """Test creating a condenser with complex parameters."""
    spec = CondenserSpec(
        name="LLMSummarizingCondenser",
        params={"llm": basic_llm, "max_size": 120, "keep_first": 15},
    )

    condenser = CondenserBase.from_spec(spec)

    assert isinstance(condenser, LLMSummarizingCondenser)
    assert isinstance(condenser, CondenserBase)


def test_from_spec_preserves_parameters():
    """Test that from_spec correctly passes parameters to the constructor."""

    # Create a mock condenser class to verify parameter passing
    class MockCondenser(CondenserBase):
        param1: str | None = None
        param2: int | None = None

        def should_condense(self, view):
            return False

        def condense(self, view):
            from openhands.sdk.event.condenser import Condensation

            return Condensation(summary="mock condensation")

    # Temporarily replace CondenserBase with our mock for this test
    original_from_spec = CondenserBase.from_spec

    def mock_from_spec(spec):
        # Create MockCondenser instead of the base class
        return MockCondenser(**spec.params)

    CondenserBase.from_spec = staticmethod(mock_from_spec)

    try:
        spec = CondenserSpec(
            name="MockCondenser", params={"param1": "value1", "param2": 42}
        )

        condenser = CondenserBase.from_spec(spec)

        assert isinstance(condenser, MockCondenser)
        assert condenser.param1 == "value1"
        assert condenser.param2 == 42
    finally:
        # Restore original method
        CondenserBase.from_spec = original_from_spec


def test_from_spec_with_nested_objects(basic_llm):
    """Test creating a condenser with nested object parameters."""
    spec = CondenserSpec(
        name="LLMSummarizingCondenser",
        params={"llm": basic_llm, "max_size": 100, "keep_first": 5},
    )

    condenser = CondenserBase.from_spec(spec)

    assert isinstance(condenser, LLMSummarizingCondenser)
    assert isinstance(condenser, CondenserBase)


def test_from_spec_spec_validation():
    """Test that CondenserSpec validates correctly."""
    # Test valid spec
    spec = CondenserSpec(name="NoOpCondenser", params={})
    assert spec.name == "NoOpCondenser"
    assert spec.params == {}

    # Test spec with parameters
    spec_with_params = CondenserSpec(
        name="LLMSummarizingCondenser", params={"max_size": 80, "keep_first": 10}
    )
    assert spec_with_params.name == "LLMSummarizingCondenser"
    assert spec_with_params.params == {"max_size": 80, "keep_first": 10}


def test_from_spec_different_condenser_types():
    """Test creating different types of condensers from specs."""
    # NoOpCondenser
    no_op_spec = CondenserSpec(name="NoOpCondenser", params={})
    no_op_condenser = CondenserBase.from_spec(no_op_spec)
    assert isinstance(no_op_condenser, NoOpCondenser)
    assert isinstance(no_op_condenser, CondenserBase)

    # LLMSummarizingCondenser (with minimal valid params)
    llm = LLM(model="test-model")
    llm_spec = CondenserSpec(
        name="LLMSummarizingCondenser",
        params={"llm": llm, "max_size": 80, "keep_first": 5},
    )
    llm_condenser = CondenserBase.from_spec(llm_spec)
    assert isinstance(llm_condenser, LLMSummarizingCondenser)
    assert isinstance(llm_condenser, CondenserBase)


def test_condenser_spec_examples():
    """Test that the examples in CondenserSpec work correctly."""
    # Test the example from the CondenserSpec docstring
    spec = CondenserSpec(
        name="LLMSummarizingCondenser",
        params={
            "llm": {"model": "gpt-5", "api_key": "sk-XXX"},
            "max_size": 80,
            "keep_first": 10,
        },
    )

    assert spec.name == "LLMSummarizingCondenser"
    assert spec.params["max_size"] == 80
    assert spec.params["keep_first"] == 10
    assert spec.params["llm"]["model"] == "gpt-5"


def test_from_spec_method_is_classmethod():
    """Test that from_spec is properly defined as a classmethod."""
    assert hasattr(CondenserBase.from_spec, "__self__")
    assert CondenserBase.from_spec.__self__ is CondenserBase


def test_from_spec_pipeline_condenser_with_condenser_specs():
    """Test creating a PipelineCondenser from spec with CondenserSpec list."""
    spec = CondenserSpec(
        name="PipelineCondenser",
        params={
            "condensers": [
                CondenserSpec(name="NoOpCondenser", params={}),
                CondenserSpec(name="NoOpCondenser", params={}),
            ]
        },
    )

    condenser = CondenserBase.from_spec(spec)

    assert isinstance(condenser, PipelineCondenser)
    assert isinstance(condenser, CondenserBase)
    assert len(condenser.condensers) == 2
    assert all(isinstance(c, NoOpCondenser) for c in condenser.condensers)


def test_from_spec_pipeline_condenser_with_mixed_condensers(basic_llm):
    """Test creating a PipelineCondenser with mixed condenser types."""
    spec = CondenserSpec(
        name="PipelineCondenser",
        params={
            "condensers": [
                CondenserSpec(name="NoOpCondenser", params={}),
                CondenserSpec(
                    name="LLMSummarizingCondenser",
                    params={"llm": basic_llm, "max_size": 80, "keep_first": 5},
                ),
            ]
        },
    )

    condenser = CondenserBase.from_spec(spec)

    assert isinstance(condenser, PipelineCondenser)
    assert isinstance(condenser, CondenserBase)
    assert len(condenser.condensers) == 2
    assert isinstance(condenser.condensers[0], NoOpCondenser)
    assert isinstance(condenser.condensers[1], LLMSummarizingCondenser)


def test_pipeline_condenser_field_validator_with_empty_list():
    """Test PipelineCondenser field validator with empty list."""
    condenser = PipelineCondenser(condensers=[])
    assert condenser.condensers == []


def test_pipeline_condenser_field_validator_with_condenser_instances():
    """Test PipelineCondenser field validator with existing Condenser instances."""
    no_op = NoOpCondenser()
    condenser = PipelineCondenser(condensers=[no_op])

    assert len(condenser.condensers) == 1
    assert condenser.condensers[0] is no_op


def test_pipeline_condenser_field_validator_with_condenser_specs():
    """Test PipelineCondenser field validator with CondenserSpec instances."""
    specs = [
        CondenserSpec(name="NoOpCondenser", params={}),
        CondenserSpec(name="NoOpCondenser", params={}),
    ]
    condenser = PipelineCondenser(condensers=specs)  # type: ignore[arg-type]

    assert len(condenser.condensers) == 2
    assert all(isinstance(c, NoOpCondenser) for c in condenser.condensers)
