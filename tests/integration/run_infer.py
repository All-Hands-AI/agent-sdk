#!/usr/bin/env python3
"""
Integration test runner for agent-sdk.
Adapted from OpenHands evaluation/integration_tests/run_infer.py
"""

import argparse
import importlib.util
import json
import os
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from openhands.sdk.logger import get_logger
from tests.integration.base import BaseIntegrationTest, TestResult
from tests.integration.schemas import ModelTestResults
from tests.integration.utils.format_costs import format_cost


logger = get_logger(__name__)


class TestInstance(BaseModel):
    """Represents a single test instance."""

    model_config = {"arbitrary_types_allowed": True}

    instance_id: str
    file_path: str
    test_class: Optional[BaseIntegrationTest] = None


class EvalOutput(BaseModel):
    """Output from running a single test instance."""

    instance_id: str
    test_result: TestResult
    llm_model: str
    cost: float = 0.0
    error_message: Optional[str] = None


def load_integration_tests() -> List[TestInstance]:
    """Load tests from python files under ./tests/integration"""
    test_dir = Path(__file__).parent / "tests"
    test_files = [
        f
        for f in test_dir.glob("t*.py")
        if f.name.startswith("t") and f.name.endswith(".py")
    ]

    instances = []
    for test_file in test_files:
        instance_id = test_file.stem  # filename without extension
        instances.append(
            TestInstance(instance_id=instance_id, file_path=str(test_file))
        )

    return instances


def load_test_class(file_path: str) -> type[BaseIntegrationTest]:
    """Dynamically load test class from a Python file."""

    spec = importlib.util.spec_from_file_location("test_module", file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Find the test class that inherits from BaseIntegrationTest
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (
            isinstance(attr, type)
            and issubclass(attr, BaseIntegrationTest)
            and attr != BaseIntegrationTest
        ):
            return attr  # Return the class, not an instance

    raise ImportError(f"No BaseIntegrationTest subclass found in {file_path}")


def process_instance(instance: TestInstance, llm_config: Dict[str, Any]) -> EvalOutput:
    """Process a single test instance."""
    logger.info("Processing test: %s", instance.instance_id)

    # Load the test class
    test_class_type = load_test_class(instance.file_path)
    if test_class_type is None:
        return EvalOutput(
            instance_id=instance.instance_id,
            test_result=TestResult(success=False, reason="Failed to load test class"),
            llm_model=llm_config.get("model", "unknown"),
            error_message="Could not load test class",
        )

    # Initialize temp_dir outside try block to ensure it's always defined
    temp_dir = tempfile.mkdtemp()

    try:
        # Get the module to access its constants
        spec = importlib.util.spec_from_file_location("test_module", instance.file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module from {instance.file_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Get the required parameters from the module
        instruction = getattr(module, "INSTRUCTION", "Default test instruction")

        # Instantiate the test class with required parameters
        # Note: tools are now provided via the abstract tools property
        test_instance = test_class_type(
            instruction=instruction,
            llm_config=llm_config,  # Use the provided config
            cwd=temp_dir,  # Pass the CWD (either from module or temp dir)
        )

        # Run the test
        start_time = time.time()
        test_result = test_instance.run_instruction()
        end_time = time.time()

        # Access accumulated_cost from the metrics object where it's properly validated
        llm_cost = test_instance.llm.metrics.accumulated_cost

        logger.info(
            "Test %s completed in %.2fs: %s (Cost: %s)",
            instance.instance_id,
            end_time - start_time,
            "PASS" if test_result.success else "FAIL",
            format_cost(llm_cost),
        )

        return EvalOutput(
            instance_id=instance.instance_id,
            test_result=test_result,
            llm_model=llm_config.get("model", "unknown"),
            cost=llm_cost,
        )

    except Exception as e:
        logger.error("Error running test %s: %s", instance.instance_id, e)
        return EvalOutput(
            instance_id=instance.instance_id,
            test_result=TestResult(
                success=False, reason=f"Test execution failed: {str(e)}"
            ),
            llm_model=llm_config.get("model", "unknown"),
            error_message=str(e),
        )
    finally:
        # Clean up temporary directory if we created one
        if temp_dir and os.path.exists(temp_dir):
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)


def run_evaluation(
    instances: List[TestInstance],
    llm_config: Dict[str, Any],
    num_workers: int,
) -> List[EvalOutput]:
    """Run evaluation on all test instances and return results directly."""
    logger.info("Running %d tests with %d workers", len(instances), num_workers)

    results = []

    if num_workers == 1:
        # Sequential execution
        for instance in instances:
            result = process_instance(instance, llm_config)
            results.append(result)
    else:
        # Parallel execution
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            future_to_instance = {
                executor.submit(process_instance, instance, llm_config): instance
                for instance in instances
            }

            for future in as_completed(future_to_instance):
                result = future.result()
                results.append(result)

    return results


def generate_structured_results(
    eval_outputs: List[EvalOutput],
    output_dir: str,
    eval_note: str,
    model_name: str,
    run_suffix: str,
    llm_config: Dict[str, Any],
) -> str:
    """Generate structured JSON results from evaluation outputs."""

    # Create structured results using the schema
    structured_results = ModelTestResults.from_eval_outputs(
        eval_outputs=eval_outputs,
        model_name=model_name,
        run_suffix=run_suffix,
        llm_config=llm_config,
        eval_note=eval_note,
    )

    # Save structured results
    os.makedirs(output_dir, exist_ok=True)
    results_file = os.path.join(output_dir, "results.json")

    with open(results_file, "w") as f:
        f.write(structured_results.model_dump_json(indent=2))

    # Print summary for console output
    success_rate = structured_results.success_rate
    successful = structured_results.successful_tests
    total = structured_results.total_tests
    logger.info("Success rate: %.2f%% (%d/%d)", success_rate * 100, successful, total)
    logger.info("Evaluation Results:")
    for instance in structured_results.test_instances:
        status = "✓" if instance.test_result.success else "✗"
        reason = instance.test_result.reason or "N/A"
        logger.info("%s: %s - %s", instance.instance_id, status, reason)
    logger.info("Total cost: %s", format_cost(structured_results.total_cost))
    logger.info("Structured results saved to %s", results_file)
    return results_file


def main():
    parser = argparse.ArgumentParser(description="Run agent-sdk integration tests")
    parser.add_argument(
        "--llm-config",
        type=json.loads,
        required=True,
        help="LLM configuration as JSON string",
    )
    parser.add_argument(
        "--num-workers", type=int, default=1, help="Number of parallel workers"
    )
    parser.add_argument(
        "--eval-note",
        type=str,
        default="agent-sdk-integration",
        help="Note to include in output directory name",
    )
    parser.add_argument(
        "--eval-ids",
        type=str,
        default=None,
        help="Comma-separated list of specific test IDs to run",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="tests/integration/outputs",
        help="Output directory for results",
    )

    args = parser.parse_args()

    llm_config = args.llm_config

    # Log configuration details
    logger.info("INTEGRATION TEST CONFIGURATION")
    logger.info("LLM_CONFIG: %s", json.dumps(llm_config, indent=2))
    logger.info("NUM_WORKERS: %s", args.num_workers)
    logger.info("EVAL_NOTE: %s", args.eval_note)
    if args.eval_ids:
        logger.info("EVAL_IDS: %s", args.eval_ids)

    # Load all integration tests
    instances = load_integration_tests()

    # Filter by specific test IDs if provided
    if args.eval_ids:
        eval_ids = [id.strip() for id in args.eval_ids.split(",")]
        instances = [inst for inst in instances if inst.instance_id in eval_ids]
        instance_ids = [inst.instance_id for inst in instances]
        logger.info("Filtered to %d tests: %s", len(instances), instance_ids)

    if not instances:
        logger.error("No test instances found!")
        return

    # Create output directory with timestamp and model info
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    model_name = llm_config.get("model", "unknown").replace("/", "_").replace("-", "_")
    output_subdir = f"{model_name}_{args.eval_note}_N{len(instances)}_{timestamp}"
    output_dir = os.path.join(args.output_dir, output_subdir)

    logger.info("Output directory: %s", output_dir)

    eval_outputs = run_evaluation(instances, llm_config, args.num_workers)

    generate_structured_results(
        eval_outputs=eval_outputs,
        output_dir=output_dir,
        eval_note=args.eval_note,
        model_name=model_name,
        run_suffix=output_subdir,
        llm_config=llm_config,
    )


if __name__ == "__main__":
    main()
