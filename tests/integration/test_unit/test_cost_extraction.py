"""Unit tests for cost extraction in integration tests."""

from unittest.mock import Mock, patch

from openhands.sdk.llm.utils.metrics import Metrics
from tests.integration.base import TestResult
from tests.integration.run_infer import TestInstance, process_instance


def test_cost_extraction_with_metrics():
    """Test that LLM costs are correctly extracted from test instances."""
    # Create a mock test instance
    instance = TestInstance(
        instance_id="test_cost_extraction", file_path="/fake/path/test.py"
    )

    # Mock LLM config
    llm_config = {"model": "test-model"}

    # Create a mock test class that has an LLM with metrics
    mock_test_class = Mock()
    mock_test_instance = Mock()
    mock_llm = Mock()
    mock_metrics = Metrics(model_name="test-model")
    mock_metrics.add_cost(0.05)  # Add a cost of $0.05

    mock_llm.metrics = mock_metrics
    mock_test_instance.llm = mock_llm
    mock_test_instance.run_instruction.return_value = TestResult(
        success=True, reason="Test passed"
    )
    mock_test_class.return_value = mock_test_instance

    with patch(
        "tests.integration.run_infer.load_test_class", return_value=mock_test_class
    ):
        with patch("importlib.util.spec_from_file_location"):
            with patch("importlib.util.module_from_spec"):
                with patch("tempfile.mkdtemp", return_value="/tmp/test"):
                    with patch("os.path.exists", return_value=True):
                        with patch("shutil.rmtree"):
                            result = process_instance(instance, llm_config)

    # Verify that the cost was extracted correctly
    assert result.cost == 0.05
    assert result.instance_id == "test_cost_extraction"
    assert result.llm_model == "test-model"


def test_cost_extraction_without_metrics():
    """Test that cost extraction handles cases where metrics are None."""
    # Create a mock test instance
    instance = TestInstance(
        instance_id="test_no_metrics", file_path="/fake/path/test.py"
    )

    # Mock LLM config
    llm_config = {"model": "test-model"}

    # Create a mock test class that has an LLM without metrics
    mock_test_class = Mock()
    mock_test_instance = Mock()
    mock_llm = Mock()
    mock_llm.metrics = None  # No metrics available

    mock_test_instance.llm = mock_llm
    mock_test_instance.run_instruction.return_value = TestResult(
        success=True, reason="Test passed"
    )
    mock_test_class.return_value = mock_test_instance

    with patch(
        "tests.integration.run_infer.load_test_class", return_value=mock_test_class
    ):
        with patch("importlib.util.spec_from_file_location"):
            with patch("importlib.util.module_from_spec"):
                with patch("tempfile.mkdtemp", return_value="/tmp/test"):
                    with patch("os.path.exists", return_value=True):
                        with patch("shutil.rmtree"):
                            result = process_instance(instance, llm_config)

    # Verify that the cost defaults to 0.0 when metrics are not available
    assert result.cost == 0.0
    assert result.instance_id == "test_no_metrics"
    assert result.llm_model == "test-model"


def test_cost_extraction_without_llm():
    """Test that cost extraction handles cases where LLM is not available."""
    # Create a mock test instance
    instance = TestInstance(instance_id="test_no_llm", file_path="/fake/path/test.py")

    # Mock LLM config
    llm_config = {"model": "test-model"}

    # Create a mock test class that doesn't have an LLM attribute
    mock_test_class = Mock()
    mock_test_instance = Mock()
    # Don't set mock_test_instance.llm - simulate missing LLM

    mock_test_instance.run_instruction.return_value = TestResult(
        success=True, reason="Test passed"
    )
    mock_test_class.return_value = mock_test_instance

    with patch(
        "tests.integration.run_infer.load_test_class", return_value=mock_test_class
    ):
        with patch("importlib.util.spec_from_file_location"):
            with patch("importlib.util.module_from_spec"):
                with patch("tempfile.mkdtemp", return_value="/tmp/test"):
                    with patch("os.path.exists", return_value=True):
                        with patch("shutil.rmtree"):
                            result = process_instance(instance, llm_config)

    # Verify that the cost defaults to 0.0 when LLM is not available
    assert result.cost == 0.0
    assert result.instance_id == "test_no_llm"
    assert result.llm_model == "test-model"
