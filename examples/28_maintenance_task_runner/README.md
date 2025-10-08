# Maintenance Task Runner

Run scheduled maintenance tasks using OpenHands SDK via GitHub Actions.

## Quick Start

### Get an API Key

You can easily obtain an API key from the [OpenHands LLM Provider](https://docs.all-hands.dev/openhands/usage/llms/openhands-llms), or use any other compatible LLM API key.

### Local Testing

```bash
export LLM_API_KEY="your-api-key"
export LLM_MODEL="openhands/claude-sonnet-4-5-20250929"
python https://raw.githubusercontent.com/All-Hands-AI/agent-sdk/main/examples/28_maintenance_task_runner/run.py \
    https://raw.githubusercontent.com/All-Hands-AI/agent-sdk/main/examples/28_maintenance_task_runner/maintenance_example.txt
```

### GitHub Actions

1. Set `LLM_API_KEY` secret in your repository settings
2. Go to Actions → "Scheduled Maintenance Task"
3. Click "Run workflow"
4. Enter prompt location (URL or file path)
5. Click "Run workflow"

To enable scheduled runs, uncomment the `schedule` section in `.github/workflows/maintenance-task.yml`.
