# Maintenance Task Runner

This example demonstrates how to use the OpenHands SDK to run scheduled maintenance
tasks using GitHub Actions.

## Overview

The maintenance task runner allows you to:
- Execute agent-based tasks at scheduled intervals via GitHub Actions
- Load prompts from URLs or local files
- Configure LLM models and API keys
- Run tasks manually or on a cron schedule

## Files

- `run.py`: The main script that runs the agent with a given prompt
- `prompts/`: Directory containing example prompts
  - `maintenance_example.txt`: Example prompt for checking outdated dependencies
  - `README.md`: Documentation for creating effective prompts

## Usage

### Local Testing

```bash
# Set environment variables
export LLM_API_KEY="your-api-key"
export LLM_MODEL="anthropic/claude-sonnet-4-5-20250929"

# Run with a local prompt file
python run.py prompts/maintenance_example.txt

# Run with a URL
python run.py https://example.com/prompt.txt

# Specify custom LLM settings
export LLM_BASE_URL="https://custom-api.example.com"
python run.py prompts/maintenance_example.txt
```

### GitHub Actions

The workflow file at `.github/workflows/maintenance-task.yml` is configured to:
1. Run manually via workflow_dispatch with custom parameters
2. Run on a schedule (when cron is uncommented)

**Manual trigger:**
1. Go to Actions → "Scheduled Maintenance Task"
2. Click "Run workflow"
3. Provide the prompt location and other parameters
4. Click "Run workflow"

**Scheduled execution:**
1. Edit `.github/workflows/maintenance-task.yml`
2. Uncomment the `schedule` section
3. Customize the cron expression (default: 2 AM UTC daily)
4. Commit and push the changes

## Configuration

### Environment Variables

- `LLM_API_KEY` (required): API key for the LLM service
- `LLM_MODEL` (optional): Model to use (default: anthropic/claude-sonnet-4-5-20250929)
- `LLM_BASE_URL` (optional): Base URL for the LLM API

### Workflow Inputs

- `agent_script`: Path to the script (default: examples/28_maintenance_task_runner/run.py)
- `prompt_location`: URL or file path to the prompt (required)
- `llm_model`: LLM model to use
- `llm_base_url`: Optional base URL for the LLM API

## Creating Custom Prompts

See `prompts/README.md` for best practices on creating effective maintenance prompts.

## Examples

**Check for outdated dependencies:**
```text
Check the repository for any outdated dependencies and create a summary report.
Include the current version and latest available version for each dependency.
```

**Update documentation:**
```text
Review the code changes from the last week and update the README.md file
to reflect any new features or changes to the API.
```

**Security audit:**
```text
Scan the codebase for common security vulnerabilities and create a report
with findings and recommended fixes.
```
