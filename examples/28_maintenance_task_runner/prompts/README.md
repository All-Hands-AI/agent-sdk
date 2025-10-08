# Maintenance Task Prompts

This directory contains example prompts for scheduled maintenance tasks.

## Usage

These prompts can be used with the `28_maintenance_task_runner.py` script or the GitHub Actions workflow.

### Running locally

```bash
python examples/28_maintenance_task_runner.py examples/prompts/maintenance_example.txt
```

### Using with GitHub Actions

1. Go to the Actions tab in your repository
2. Select "Scheduled Maintenance Task" workflow
3. Click "Run workflow"
4. Enter the path or URL to your prompt file
5. Configure other parameters as needed

## Creating Custom Prompts

Create a plain text file with your task instructions. The prompt will be passed directly to the OpenHands agent.

Example:
```
Update all copyright headers in the repository to the current year.

Please:
1. Find all files with copyright notices
2. Update the year to 2025
3. Create a summary of changes made
```

## Using Remote Prompts

You can also host prompts on the web and reference them by URL:

```bash
python examples/28_maintenance_task_runner.py https://example.com/prompts/weekly-cleanup.txt
```
