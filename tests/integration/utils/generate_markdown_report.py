#!/usr/bin/env python3
"""
Generate markdown report for PR comments from consolidated JSON results.
"""

import argparse
import json
import sys

from tests.integration.schemas import (
    ConsolidatedResults,
    ModelTestResults,
)
from tests.integration.utils.format_costs import format_cost


def generate_model_summary_table(model_results: list[ModelTestResults]) -> str:
    """Generate a summary table for all models."""

    table_lines = [
        "| Model | Success Rate | Tests Passed | Total Tests | Cost |",
        "|-------|--------------|--------------|-------------|------|",
    ]

    for result in model_results:
        success_rate = f"{result.success_rate:.1%}"
        tests_passed = f"{result.successful_tests}/{result.total_tests}"
        cost = format_cost(result.total_cost)

        model_name = result.model_name
        total_tests = result.total_tests
        row = (
            f"| {model_name} | {success_rate} | {tests_passed} | "
            f"{total_tests} | {cost} |"
        )
        table_lines.append(row)

    return "\n".join(table_lines)


def generate_detailed_results(model_results: list[ModelTestResults]) -> str:
    """Generate detailed results for each model."""

    sections = []

    for result in model_results:
        section_lines = [
            f"### {result.model_name}",
            "",
            f"- **Success Rate**: {result.success_rate:.1%} "
            f"({result.successful_tests}/{result.total_tests})",
            f"- **Total Cost**: {format_cost(result.total_cost)}",
            f"- **Run Suffix**: `{result.run_suffix}`",
            "",
        ]

        # Add failed tests if any
        failed_tests = [t for t in result.test_instances if not t.test_result.success]
        if failed_tests:
            section_lines.extend(
                [
                    "**Failed Tests:**",
                    "",
                ]
            )

            for test in failed_tests:
                reason = test.test_result.reason or "No reason provided"
                cost = format_cost(test.cost)
                section_lines.append(f"- `{test.instance_id}`: {reason} (Cost: {cost})")

            section_lines.append("")

        # Add error messages if any
        error_tests = [t for t in result.test_instances if t.error_message]
        if error_tests:
            section_lines.extend(
                [
                    "**Tests with Errors:**",
                    "",
                ]
            )

            for test in error_tests:
                section_lines.append(f"- `{test.instance_id}`: {test.error_message}")

            section_lines.append("")

        sections.append("\n".join(section_lines))

    return "\n".join(sections)


def generate_markdown_report(consolidated: ConsolidatedResults) -> str:
    """Generate complete markdown report from consolidated results."""

    # Header
    report_lines = [
        "# 🧪 Integration Tests Results",
        "",
        f"**Overall Success Rate**: {consolidated.overall_success_rate:.1%}",
        f"**Total Cost**: {format_cost(consolidated.total_cost_all_models)}",
        f"**Models Tested**: {consolidated.total_models}",
        f"**Timestamp**: {consolidated.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
    ]

    # Add artifacts section if any model has artifact URLs
    artifacts_available = any(
        result.artifact_url for result in consolidated.model_results
    )
    if artifacts_available:
        report_lines.extend(
            [
                "## 📁 Detailed Logs & Artifacts",
                "",
                (
                    "Click the links below to download detailed agent/LLM logs showing "
                    "the complete reasoning process for each model:"
                ),
                "",
            ]
        )

        for result in consolidated.model_results:
            if result.artifact_url:
                report_lines.append(
                    f"- **{result.model_name}**: "
                    f"[📥 Download Logs & Results]({result.artifact_url})"
                )

        report_lines.extend(
            [
                "",
                "**What's included in each artifact:**",
                "- 📝 Complete agent reasoning logs with `visualize=True` output",
                "- 🔧 Tool interactions and observations",
                "- 🤖 LLM request/response details",
                "- 📊 Test results and metrics",
                "- 📁 Compressed archive ready for download",
                "",
                (
                    "💡 **Tip**: After clicking a link above, scroll down to the "
                    "'Artifacts' section on the GitHub Actions page to download "
                    "the files."
                ),
                "",
            ]
        )

    # Summary table
    report_lines.extend(
        [
            "## 📊 Summary",
            "",
            generate_model_summary_table(consolidated.model_results),
            "",
        ]
    )

    # Detailed results
    report_lines.extend(
        [
            "## 📋 Detailed Results",
            "",
            generate_detailed_results(consolidated.model_results),
        ]
    )

    return "\n".join(report_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate markdown report from consolidated JSON results"
    )
    parser.add_argument(
        "--input-file",
        required=True,
        help="Consolidated JSON results file",
    )
    parser.add_argument(
        "--output-file",
        help="Output markdown file (default: stdout)",
    )

    args = parser.parse_args()

    try:
        # Load consolidated results
        print(
            f"Loading consolidated results from {args.input_file}...", file=sys.stderr
        )

        with open(args.input_file) as f:
            data = json.load(f)

        consolidated = ConsolidatedResults.model_validate(data)
        print(
            f"✓ Loaded results for {consolidated.total_models} models", file=sys.stderr
        )

        # Generate markdown report
        print("Generating markdown report...", file=sys.stderr)
        markdown_report = generate_markdown_report(consolidated)

        # Output report
        if args.output_file:
            with open(args.output_file, "w") as f:
                f.write(markdown_report)
            print(f"✓ Report saved to {args.output_file}", file=sys.stderr)
        else:
            print(markdown_report)

        return 0

    except Exception as e:
        print(f"✗ Error generating report: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
