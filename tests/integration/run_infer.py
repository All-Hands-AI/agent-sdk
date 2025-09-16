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

import pandas as pd
from pydantic import BaseModel

from tests.integration.base import BaseIntegrationTest, TestResult
from tests.integration.utils.format_costs import format_cost


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


def load_test_class(file_path: str) -> Optional[type]:
    """Dynamically load test class from a Python file."""
    try:
        spec = importlib.util.spec_from_file_location("test_module", file_path)
        if spec is None or spec.loader is None:
            print(f"Could not load spec from {file_path}")
            return None

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

        print(f"No BaseIntegrationTest subclass found in {file_path}")
        return None

    except Exception as e:
        print(f"Error loading test class from {file_path}: {e}")
        return None


def process_instance(instance: TestInstance, llm_config: Dict[str, Any]) -> EvalOutput:
    """Process a single test instance."""
    print(f"Processing test: {instance.instance_id}")

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

        print(
            f"Test {instance.instance_id} completed in {end_time - start_time:.2f}s: "
            f"{'PASS' if test_result.success else 'FAIL'}"
        )

        return EvalOutput(
            instance_id=instance.instance_id,
            test_result=test_result,
            llm_model=llm_config.get("model", "unknown"),
            cost=0.0,  # TODO: Extract cost from test execution if available
        )

    except Exception as e:
        print(f"Error running test {instance.instance_id}: {e}")
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
    output_file: str,
) -> None:
    """Run evaluation on all test instances."""
    print(f"Running {len(instances)} tests with {num_workers} workers")

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

    # Save results to JSONL file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w") as f:
        for result in results:
            f.write(result.model_dump_json() + "\n")

    print(f"Results saved to {output_file}")


def generate_report(output_file: str, eval_note: str) -> str:
    """Generate a markdown report from the results."""
    df = pd.read_json(output_file, lines=True, orient="records")

    # Extract success and reason from test_result
    df["success"] = df["test_result"].apply(lambda x: x["success"])
    df["reason"] = df["test_result"].apply(lambda x: x["reason"])

    success_rate = df["success"].mean()
    success_count = df["success"].sum()
    total_count = len(df)
    total_cost = df["cost"].sum()

    print("-" * 100)
    print(f"Success rate: {success_rate:.2%} ({success_count}/{total_count})")
    print("\nEvaluation Results:")
    print(df[["instance_id", "success", "reason"]].to_string(index=False))
    print("-" * 100)
    print(f"Total cost: {format_cost(total_cost)}")

    # Generate report file
    report_dir = os.path.dirname(output_file)
    report_file = os.path.join(report_dir, "report.md")

    with open(report_file, "w") as f:
        f.write(f"# Integration Tests Report - {eval_note}\n\n")
        f.write(f"Success rate: {success_rate:.2%} ({success_count}/{total_count})\n\n")
        f.write(f"Total cost: {format_cost(total_cost)}\n\n")
        f.write("## Test Results\n\n")

        # Format cost column for display
        df_display = df.copy()
        df_display["cost"] = df_display["cost"].apply(format_cost)

        f.write(
            df_display[
                ["instance_id", "success", "reason", "cost", "error_message"]
            ].to_markdown(index=False)  # type: ignore
        )
        f.write("\n")

    print(f"Report saved to {report_file}")
    return report_file


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

    # Load all integration tests
    instances = load_integration_tests()

    # Filter by specific test IDs if provided
    if args.eval_ids:
        eval_ids = [id.strip() for id in args.eval_ids.split(",")]
        instances = [inst for inst in instances if inst.instance_id in eval_ids]
        instance_ids = [inst.instance_id for inst in instances]
        print(f"Filtered to {len(instances)} tests: {instance_ids}")

    if not instances:
        print("No test instances found!")
        return

    # Create output directory with timestamp and model info
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    model_name = llm_config.get("model", "unknown").replace("/", "_").replace("-", "_")
    output_subdir = f"{model_name}_{args.eval_note}_N{len(instances)}_{timestamp}"
    output_dir = os.path.join(args.output_dir, output_subdir)
    output_file = os.path.join(output_dir, "output.jsonl")

    print(f"Output directory: {output_dir}")

    # Run evaluation
    run_evaluation(instances, llm_config, args.num_workers, output_file)

    # Generate report
    generate_report(output_file, args.eval_note)


if __name__ == "__main__":
    main()
