#!/usr/bin/env python3
"""
Process integration test results for GitHub workflow.

This script replaces all shell processing (grep, sed, jq, shell variables)
with Python to eliminate shell escaping issues and improve maintainability.
"""

import argparse
import json
import re
import sys
from pathlib import Path


def extract_total_cost(report_content: str) -> float:
    """
    Extract total cost from report content.

    Args:
        report_content: The full report content as string

    Returns:
        Total cost as float, or 0.0 if not found
    """
    # Pattern to match "Total cost: $X.XX" with optional scientific notation
    pattern = r"Total cost: \$([0-9]*\.?[0-9]+(?:[eE][+-]?[0-9]+)?)"

    match = re.search(pattern, report_content)
    if match:
        try:
            cost_str = match.group(1)
            return float(cost_str)
        except ValueError:
            print(
                f"Warning: Could not parse cost value '{match.group(1)}' as float",
                file=sys.stderr,
            )
            return 0.0

    print("Warning: No total cost found in report", file=sys.stderr)
    return 0.0


def read_report_file(report_path: Path) -> str:
    """
    Read the report file content.

    Args:
        report_path: Path to the report file

    Returns:
        Report content as string

    Raises:
        FileNotFoundError: If report file doesn't exist
        UnicodeDecodeError: If file can't be decoded as UTF-8
    """
    try:
        return report_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: Report file not found: {report_path}", file=sys.stderr)
        raise
    except UnicodeDecodeError as e:
        print(f"Error: Could not decode report file as UTF-8: {e}", file=sys.stderr)
        raise


def create_result_json(
    model_name: str,
    run_suffix: str,
    report_content: str,
    artifact_url: str,
    total_cost: float,
) -> dict:
    """
    Create the result JSON structure.

    Args:
        model_name: Name of the model (e.g., "GPT-5 Mini")
        run_suffix: Run suffix (e.g., "gpt5_mini_run")
        report_content: Full report content
        artifact_url: URL to the uploaded artifact
        total_cost: Total cost as float

    Returns:
        Dictionary representing the JSON structure
    """
    return {
        "model_name": model_name,
        "run_suffix": run_suffix,
        "test_report": report_content,
        "artifact_url": artifact_url,
        "total_cost": total_cost,
        "status": "completed",
    }


def save_result_json(result_data: dict, output_path: Path) -> None:
    """
    Save the result JSON to file.

    Args:
        result_data: Dictionary to save as JSON
        output_path: Path where to save the JSON file
    """
    try:
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write JSON with proper formatting
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)

        print(f"Successfully saved result JSON to: {output_path}")

    except Exception as e:
        print(f"Error: Could not save JSON file: {e}", file=sys.stderr)
        raise


def main():
    """Main function to process integration test results."""
    parser = argparse.ArgumentParser(
        description="Process integration test results for GitHub workflow"
    )
    parser.add_argument(
        "--model-name", required=True, help="Name of the model (e.g., 'GPT-5 Mini')"
    )
    parser.add_argument(
        "--run-suffix", required=True, help="Run suffix (e.g., 'gpt5_mini_run')"
    )
    parser.add_argument(
        "--report-file", required=True, type=Path, help="Path to the report.md file"
    )
    parser.add_argument(
        "--artifact-url", required=True, help="URL to the uploaded artifact"
    )
    parser.add_argument(
        "--output-file",
        required=True,
        type=Path,
        help="Path where to save the result JSON file",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug output")

    args = parser.parse_args()

    if args.debug:
        print(f"Debug: Processing report file: {args.report_file}")
        print(f"Debug: Model name: {args.model_name}")
        print(f"Debug: Run suffix: {args.run_suffix}")
        print(f"Debug: Artifact URL: {args.artifact_url}")
        print(f"Debug: Output file: {args.output_file}")

    try:
        # Read the report file
        print(f"Reading report file: {args.report_file}")
        report_content = read_report_file(args.report_file)

        if args.debug:
            print(f"Debug: Report content length: {len(report_content)} characters")
            print(f"Debug: First 200 characters: {report_content[:200]}")

        # Extract total cost
        total_cost = extract_total_cost(report_content)
        print(f"Extracted total cost: ${total_cost}")

        # Create result JSON structure
        result_data = create_result_json(
            model_name=args.model_name,
            run_suffix=args.run_suffix,
            report_content=report_content,
            artifact_url=args.artifact_url,
            total_cost=total_cost,
        )

        if args.debug:
            print(f"Debug: Created JSON structure with {len(result_data)} fields")

        # Save to output file
        save_result_json(result_data, args.output_file)

        print("✅ Successfully processed integration test results")

    except Exception as e:
        print(f"❌ Error processing integration test results: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
