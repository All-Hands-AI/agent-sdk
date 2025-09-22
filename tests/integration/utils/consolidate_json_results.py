#!/usr/bin/env python3
"""
Consolidate JSON test results from multiple models into a single structured file.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from tests.integration.schemas import (
    ConsolidatedResults,
    ModelTestResults,
)


def find_json_results(results_dir: str) -> list[Path]:
    """Find all JSON result files in the results directory."""
    results_path = Path(results_dir)
    if not results_path.exists():
        raise FileNotFoundError(f"Results directory not found: {results_dir}")

    # Look for both patterns: */results.json and *_results.json
    json_files = list(results_path.glob("*/results.json")) + list(
        results_path.glob("*_results.json")
    )
    print(f"Found {len(json_files)} JSON result files")

    for json_file in json_files:
        print(f"  - {json_file}")

    return json_files


def load_and_validate_results(json_files: list[Path]) -> list[ModelTestResults]:
    """Load and validate JSON result files."""
    model_results = []

    for json_file in json_files:
        try:
            print(f"Loading {json_file}...")
            with open(json_file, "r") as f:
                data = json.load(f)

            # Validate using Pydantic schema
            model_result = ModelTestResults.model_validate(data)
            model_results.append(model_result)
            model_name = model_result.model_name
            total_tests = model_result.total_tests
            print(f"  ✓ Loaded {model_name} with {total_tests} tests")

        except Exception as e:
            print(f"  ✗ Error loading {json_file}: {e}")
            raise

    return model_results


def consolidate_results(model_results: list[ModelTestResults]) -> ConsolidatedResults:
    """Consolidate individual model results into a single structure."""
    print(f"\nConsolidating {len(model_results)} model results...")

    consolidated = ConsolidatedResults.from_model_results(model_results)

    print(f"Overall success rate: {consolidated.overall_success_rate:.2%}")
    print(f"Total cost across all models: ${consolidated.total_cost_all_models:.4f}")

    return consolidated


def save_consolidated_results(
    consolidated: ConsolidatedResults, output_file: str
) -> None:
    """Save consolidated results to JSON file."""
    print(f"\nSaving consolidated results to {output_file}...")

    # Only create directory if output_file has a directory component
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_file, "w") as f:
        f.write(consolidated.model_dump_json(indent=2))

    print(f"✓ Consolidated results saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Consolidate JSON test results from multiple models"
    )
    parser.add_argument(
        "--results-dir",
        required=True,
        help="Directory containing model result subdirectories",
    )
    parser.add_argument(
        "--output-file",
        required=True,
        help="Output file for consolidated results",
    )

    args = parser.parse_args()

    try:
        # Find all JSON result files
        json_files = find_json_results(args.results_dir)

        if not json_files:
            print("No JSON result files found!")
            return 1

        # Load and validate results
        model_results = load_and_validate_results(json_files)

        # Consolidate results
        consolidated = consolidate_results(model_results)

        # Save consolidated results
        save_consolidated_results(consolidated, args.output_file)

        print("\n✓ Consolidation completed successfully!")
        return 0

    except Exception as e:
        print(f"\n✗ Error during consolidation: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
