# Routine Maintenance Workflow

This example demonstrates how to set up a GitHub Actions workflow for automated routine maintenance tasks using the OpenHands agent SDK.

## Files

- **`workflow.yml`**: GitHub Actions workflow file that can be copied to `.github/workflows/` in your repository
- **`agent_script.py`**: Python script that runs the OpenHands agent with a custom prompt

## Setup

### 1. Copy the workflow file

Copy `workflow.yml` to `.github/workflows/maintenance-task.yml` in your repository:

```bash
cp examples/github_workflows/01_routine_maintenance/workflow.yml .github/workflows/maintenance-task.yml
```

### 2. Configure secrets

Set the following secrets in your GitHub repository settings:

- **`LLM_API_KEY`** (required): Your LLM API key
  - Get one from the [OpenHands LLM Provider](https://docs.all-hands.dev/openhands/usage/llms/openhands-llms)
- **`LLM_MODEL`** (optional): Model to use (default: `openhands/claude-sonnet-4-5-20250929`)
- **`LLM_BASE_URL`** (optional): Custom base URL for LLM API

### 3. Test locally

Before setting up automated runs, test the script locally:

```bash
export LLM_API_KEY="your-api-key"
export LLM_MODEL="openhands/claude-sonnet-4-5-20250929"

# Create a test prompt
echo "Check for outdated dependencies in requirements.txt and create a PR to update them" > prompt.txt

# Run the agent
python examples/github_workflows/01_routine_maintenance/agent_script.py prompt.txt
```

### 4. Run via GitHub Actions

#### Manual trigger:
1. Go to Actions → "Scheduled Maintenance Task"
2. Click "Run workflow"
3. Enter your prompt location (URL or file path)
4. Optionally configure LLM settings
5. Click "Run workflow"

#### Scheduled runs:
Edit the workflow file and uncomment the `schedule` section:

```yaml
on:
  schedule:
    # Run at 2 AM UTC every day
    - cron: "0 2 * * *"
```

Customize the cron schedule as needed. See [Cron syntax reference](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule).

## Example Use Cases

### Dependency Updates
```
Check for outdated dependencies in requirements.txt and create a PR to update them if any are found.
```

### Security Audits
```
Run security checks on the codebase and create an issue if any vulnerabilities are found.
```

### Documentation Updates
```
Review the README.md and update it to reflect any changes in the codebase since the last update.
```

### Code Quality Checks
```
Run linting and formatting checks on all Python files and create a PR with any fixes.
```

### Link Validation
```
Check all links in Markdown files and create an issue listing any broken links.
```

## Customization

### Using a custom agent script

You can specify a custom agent script in the workflow inputs:

```yaml
with:
  agent_script: path/to/your/custom_script.py
  prompt_location: path/to/prompt.txt
```

Your custom script should accept a prompt location as a command-line argument and use the OpenHands SDK to run the agent.

### Using remote prompts

You can host prompts remotely (e.g., on GitHub, S3, or any HTTP server) and reference them by URL:

```bash
# Example with GitHub raw URL
https://raw.githubusercontent.com/your-org/prompts/main/weekly-maintenance.txt

# Example with Gist
https://gist.githubusercontent.com/username/abc123/raw/prompt.txt
```

This allows you to update prompts without modifying the workflow file.

## Security Considerations

- Never commit API keys to the repository
- Use GitHub secrets for sensitive information
- Test prompts manually before scheduling automated runs
- Review agent actions in workflow logs
- Set appropriate repository permissions in the workflow file

## Workflow Permissions

The workflow requires the following permissions (already configured in `workflow.yml`):

```yaml
permissions:
  contents: write      # To push changes and create branches
  pull-requests: write # To create and update PRs
  issues: write        # To create issues
```

## Troubleshooting

### Workflow fails with "LLM_API_KEY not set"
Make sure you've added the `LLM_API_KEY` secret in your repository settings (Settings → Secrets and variables → Actions).

### Agent times out
For long-running tasks, consider breaking them into smaller prompts or increasing the workflow timeout in the YAML file.

### Permission denied errors
Check that the workflow has the necessary permissions in the `permissions` section and that your repository settings allow GitHub Actions to create PRs and push commits.

## References

- [OpenHands SDK Documentation](https://docs.all-hands.dev/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [LLM Provider Setup](https://docs.all-hands.dev/openhands/usage/llms/openhands-llms)
