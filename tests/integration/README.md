# Integration Tests

This directory contains integration tests for the agent-sdk that use real LLM calls to test end-to-end functionality.

## Overview

The integration tests are designed to verify that the agent-sdk works correctly with real LLM models by running complete workflows. Each test creates a temporary environment, provides the agent with specific tools, gives it an instruction, and then verifies the results.

## Directory Structure

```
tests/integration/
├── README.md                    # This file
├── __init__.py                  # Package initialization
├── base.py                      # Base classes for integration tests
├── run_infer.py                 # Main test runner script
├── run_infer.sh                 # Shell script wrapper for running tests
├── outputs/                     # Test results and reports (auto-generated)
└── tests/                       # Individual test files (e.g., t01_fix_simple_typo_class_based.py)
│   └── t*.py
```

## Running Integration Tests

The main test runner script provides flexible options for running integration tests:

```bash
# Run all tests with default settings
python tests/integration/run_infer.py

# Or using uv
uv run python tests/integration/run_infer.py
```

## Automated Testing with GitHub Actions

The integration tests are automatically executed via GitHub Actions using the workflow defined in `.github/workflows/integration-runner.yml`.

### Workflow Triggers

The GitHub workflow runs integration tests in the following scenarios:

1. **Pull Request Labels**: When a PR is labeled with `integration-test`
2. **Manual Trigger**: Via workflow dispatch with a required reason
3. **Scheduled Runs**: Daily at 10:30 PM UTC (cron: `30 22 * * *`)