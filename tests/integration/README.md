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

### Prerequisites

1. **Environment Setup**: Ensure you have the required dependencies installed:
   ```bash
   uv sync
   ```

2. **API Key**: Set the `LITELLM_API_KEY` environment variable:
   ```bash
   export LITELLM_API_KEY="your-api-key-here"
   ```

### Using run_infer.py (Recommended)

The main test runner script provides flexible options for running integration tests:

#### Basic Usage

```bash
# Run all tests with default settings
python tests/integration/run_infer.py

# Or using uv
uv run python tests/integration/run_infer.py
```

#### Advanced Usage

```bash
# Run with specific LLM model
python tests/integration/run_infer.py --llm-model "litellm_proxy/anthropic/claude-sonnet-4-20250514"

# Run specific tests only
python tests/integration/run_infer.py --eval-ids "t01_fix_simple_typo_class_based,t02_another_test"

# Run with multiple workers (parallel execution)
python tests/integration/run_infer.py --num-workers 4

# Custom output directory and evaluation note
python tests/integration/run_infer.py --output-dir "custom_outputs" --eval-note "my_test_run"

# Combine multiple options
python tests/integration/run_infer.py \
  --llm-model "litellm_proxy/anthropic/claude-sonnet-4-20250514" \
  --num-workers 2 \
  --eval-ids "t01_fix_simple_typo_class_based" \
  --eval-note "typo_fix_test"
```

#### Command Line Options

- `--llm-model`: LLM model to use (default: `litellm_proxy/anthropic/claude-sonnet-4-20250514`)
- `--num-workers`: Number of parallel workers (default: 1)
- `--eval-note`: Note to include in output directory name (default: `agent-sdk-integration`)
- `--eval-ids`: Comma-separated list of specific test IDs to run
- `--output-dir`: Output directory for results (default: `tests/integration/outputs`)

### Using the Shell Script

The shell script (`run_infer.sh`) provides a convenient wrapper with positional arguments and automatic environment setup:

```bash
# Basic usage (uses default model and settings)
./tests/integration/run_infer.sh

# With specific model
./tests/integration/run_infer.sh "gpt-4o-mini"

# With all parameters
./tests/integration/run_infer.sh \
  "litellm_proxy/anthropic/claude-sonnet-4-20250514" \
  "$LITELLM_API_KEY" \
  "" \
  1 \
  "t01_fix_simple_typo_class_based" \
  "test_run"

# Get help and see usage information
./tests/integration/run_infer.sh --help
```

#### Shell Script Features

- **Automatic version detection**: Includes git commit hash in output directory names
- **Environment variable support**: Uses existing `LITELLM_API_KEY` and `LITELLM_BASE_URL` if set
- **Flexible parameter handling**: All parameters are optional with sensible defaults
- **Direct Python script invocation**: Calls `uv run python tests/integration/run_infer.py` with proper arguments

#### Shell Script Parameters (in order)

1. `LITELLM_MODEL`: LLM model to use (default: `litellm_proxy/anthropic/claude-sonnet-4-20250514`)
2. `LITELLM_API_KEY`: API key (optional if set as env var)
3. `LITELLM_BASE_URL`: Base URL (optional if set as env var)
4. `NUM_WORKERS`: Number of parallel workers (default: 1)
5. `EVAL_IDS`: Comma-separated test IDs (optional, runs all tests if not specified)
6. `RUN_NAME`: Custom run name (optional, defaults to `agent-sdk-integration`)

## Automated Testing with GitHub Actions

The integration tests are automatically executed via GitHub Actions using the workflow defined in `.github/workflows/integration-runner.yml`.

### Workflow Triggers

The GitHub workflow runs integration tests in the following scenarios:

1. **Pull Request Labels**: When a PR is labeled with `integration-test`
2. **Manual Trigger**: Via workflow dispatch with a required reason
3. **Scheduled Runs**: Daily at 10:30 PM UTC (cron: `30 22 * * *`)

### Workflow Configuration

```yaml
# Key workflow settings
env:
  N_PROCESSES: 4  # Number of parallel processes for evaluation

jobs:
  run-integration-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12"]
```

### Test Execution in CI

The workflow performs the following steps:

1. **Environment Setup**:
   - Checkout repository
   - Install `uv` package manager
   - Set up Python 3.12
   - Install dependencies with `uv sync`

2. **Test Execution**:
   - Runs tests with **Claude Sonnet** model using `./tests/integration/run_infer.sh`
   - Runs tests with **DeepSeek** model using `./tests/integration/run_infer.sh`
   - Uses 4 parallel workers for faster execution
   - Generates timestamped output directories

3. **Results Reporting**:
   - Collects test reports from output directories
   - Posts results as PR comments (for PR-triggered runs)
   - Stores artifacts for manual inspection

### Triggering Integration Tests

#### On Pull Requests
```bash
# Add the integration-test label to your PR
# This will automatically trigger the workflow
```

#### Manual Execution
1. Go to the **Actions** tab in the GitHub repository
2. Select **"Run Integration Tests"** workflow
3. Click **"Run workflow"**
4. Provide a reason for the manual trigger
5. Click **"Run workflow"** to start

#### Scheduled Execution
- Tests run automatically every day at 10:30 PM UTC
- No manual intervention required
- Results are available in the Actions tab

### Workflow Outputs

The GitHub Actions workflow generates:

- **PR Comments**: Detailed test results posted directly to pull requests
- **Action Logs**: Complete execution logs available in the Actions tab
- **Test Reports**: Markdown reports with success rates and cost breakdowns
- **Artifacts**: Raw JSONL output files for detailed analysis

### Environment Variables in CI

The workflow uses the following secrets and environment variables:

- `LITELLM_API_KEY`: API key for LLM access (stored as repository secret)
- `LITELLM_BASE_URL`: Optional base URL for LiteLLM proxy
- `N_PROCESSES`: Number of parallel workers (set to 4 in workflow)

### Monitoring Test Results

1. **PR Comments**: Results appear as comments on pull requests
2. **Actions Tab**: View detailed logs and execution history
3. **Email Notifications**: GitHub can send notifications for workflow failures
4. **Status Checks**: Integration test status appears in PR status checks

## Test Results

### Output Structure

Test results are automatically saved in the `outputs/` directory with timestamped subdirectories:

```
outputs/
└── litellm_proxy_anthropic_claude_sonnet_4_20250514_agent-sdk-integration_N1_20250912_001939/
    ├── output.jsonl    # Raw test results in JSONL format
    └── report.md       # Human-readable markdown report
```

### Understanding Results

Each test produces:
- **Success/Failure status**: Whether the test passed or failed
- **Reason**: Detailed explanation of the result
- **Cost**: Estimated cost of LLM calls (if available)
- **Error messages**: Any errors encountered during execution

The markdown report provides a summary including:
- Overall success rate
- Individual test results
- Total cost breakdown

## Writing New Tests

### Test Structure

Integration tests inherit from `BaseIntegrationTest` and must implement:

1. **tools property**: List of tools available to the agent
2. **setup()**: Initialize test environment and create necessary files
3. **verify_result()**: Check if the agent completed the task successfully
4. **teardown()**: Clean up resources (usually handled automatically)

### Example Test

```python
"""Test that an agent can perform a specific task."""

import os
from openhands.sdk.tool import Tool
from openhands.tools import BashTool, FileEditorTool
from tests.integration.base import BaseIntegrationTest, TestResult

INSTRUCTION = "Your test instruction here"

class MyTest(BaseIntegrationTest):
    INSTRUCTION = INSTRUCTION

    @property
    def tools(self) -> list[Tool]:
        return [
            BashTool.create(working_dir=self.cwd),
            FileEditorTool.create(workspace_root=self.cwd),
        ]

    def setup(self) -> None:
        # Create test files/environment
        pass

    def verify_result(self) -> TestResult:
        # Check if task was completed successfully
        return TestResult(success=True, reason="Task completed")

    def teardown(self):
        # Cleanup (usually not needed)
        pass
```

### Test Naming Convention

- Test files must start with `t` and end with `.py` (e.g., `t01_my_test.py`)
- The filename (without extension) becomes the test ID
- Use descriptive names that indicate what the test does

## Folder Behavior

### Automatic Test Discovery

The test runner automatically discovers all test files matching the pattern `t*.py` in the integration directory. Each file should contain exactly one class that inherits from `BaseIntegrationTest`.

### Temporary Directories

Each test runs in its own temporary directory (`self.cwd`) to ensure isolation. The temporary directory is:
- Created automatically before test execution
- Passed to tools for file operations
- Cleaned up automatically after test completion

### Parallel Execution

When using multiple workers (`--num-workers > 1`):
- Tests run in separate processes for true parallelism
- Each test gets its own temporary directory
- Results are collected and merged automatically
- Be mindful of API rate limits when using many workers

### Output Management

- Results are automatically timestamped to avoid conflicts
- Output directories include model name and test count for easy identification
- Both machine-readable (JSONL) and human-readable (Markdown) formats are generated
- Previous test results are preserved unless manually deleted

## Troubleshooting

### Common Issues

1. **Missing API Key**: Ensure `LITELLM_API_KEY` is set in your environment
2. **Import Errors**: Make sure you're running from the project root directory
3. **Tool Errors**: Verify that `self.cwd` is properly set before accessing tools
4. **Test Discovery**: Ensure test files follow the `t*.py` naming convention

### Debugging Tests

- Use `--num-workers 1` for sequential execution when debugging
- Check the detailed output in `output.jsonl` for raw test data
- Examine the temporary directory contents during test development
- Add logging to your test classes using `from openhands.sdk import get_logger`

## Environment Variables

- `LITELLM_API_KEY`: Required API key for LLM access
- `LITELLM_BASE_URL`: Optional custom base URL for LiteLLM proxy