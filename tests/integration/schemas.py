"""
JSON schemas for structured integration test results.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def json_serializer(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class TestResultData(BaseModel):
    """Individual test result data."""

    success: bool
    reason: Optional[str] = None


class TestInstanceResult(BaseModel):
    """Result from a single test instance."""

    instance_id: str
    test_result: TestResultData
    cost: float = 0.0
    error_message: Optional[str] = None


class ModelTestResults(BaseModel):
    """Complete test results for a single model."""

    # Metadata
    model_name: str
    run_suffix: str
    llm_config: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)

    # Test execution data
    test_instances: List[TestInstanceResult]

    # Summary statistics
    total_tests: int
    successful_tests: int
    success_rate: float
    total_cost: float

    # Additional metadata
    eval_note: Optional[str] = None
    artifact_url: Optional[str] = None
    status: str = "completed"

    @classmethod
    def from_eval_outputs(
        cls,
        eval_outputs: List[Any],  # List[EvalOutput]
        model_name: str,
        run_suffix: str,
        llm_config: Dict[str, Any],
        eval_note: Optional[str] = None,
        artifact_url: Optional[str] = None,
    ) -> "ModelTestResults":
        """Create ModelTestResults from list of EvalOutput objects."""

        # Convert EvalOutput objects to TestInstanceResult
        test_instances = []
        for output in eval_outputs:
            test_instances.append(
                TestInstanceResult(
                    instance_id=output.instance_id,
                    test_result=TestResultData(
                        success=output.test_result.success,
                        reason=output.test_result.reason,
                    ),
                    cost=output.cost,
                    error_message=output.error_message,
                )
            )

        # Calculate summary statistics
        total_tests = len(test_instances)
        successful_tests = sum(1 for t in test_instances if t.test_result.success)
        success_rate = successful_tests / total_tests if total_tests > 0 else 0.0
        total_cost = sum(t.cost for t in test_instances)

        return cls(
            model_name=model_name,
            run_suffix=run_suffix,
            llm_config=llm_config,
            test_instances=test_instances,
            total_tests=total_tests,
            successful_tests=successful_tests,
            success_rate=success_rate,
            total_cost=total_cost,
            eval_note=eval_note,
            artifact_url=artifact_url,
        )


class ConsolidatedResults(BaseModel):
    """Consolidated results from all models."""

    # Metadata
    timestamp: datetime = Field(default_factory=datetime.now)
    total_models: int

    # Individual model results
    model_results: List[ModelTestResults]

    # Overall statistics
    overall_success_rate: float
    total_cost_all_models: float

    @classmethod
    def from_model_results(
        cls, model_results: List[ModelTestResults]
    ) -> "ConsolidatedResults":
        """Create ConsolidatedResults from list of ModelTestResults."""

        total_models = len(model_results)

        # Calculate overall statistics
        total_tests_all = sum(r.total_tests for r in model_results)
        total_successful_all = sum(r.successful_tests for r in model_results)
        overall_success_rate = (
            total_successful_all / total_tests_all if total_tests_all > 0 else 0.0
        )
        total_cost_all_models = sum(r.total_cost for r in model_results)

        return cls(
            total_models=total_models,
            model_results=model_results,
            overall_success_rate=overall_success_rate,
            total_cost_all_models=total_cost_all_models,
        )
