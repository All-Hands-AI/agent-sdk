# Automated TODO Management with GitHub Actions

This example demonstrates how to use the OpenHands SDK to automatically scan a codebase for `# TODO(openhands)` comments and create pull requests to implement them. This showcases practical automation and self-improving codebase capabilities.

## Overview

The workflow consists of three main components:

1. **Scanner** (`scanner.py`) - Scans the codebase for TODO(openhands) comments
2. **Agent** (`agent.py`) - Uses OpenHands to implement individual TODOs
3. **GitHub Actions Workflow** - Orchestrates the automation (see `.github/workflows/todo-management.yml`)

## Features

- 🔍 **Smart Scanning**: Finds legitimate TODO(openhands) comments while filtering out false positives
- 🤖 **AI Implementation**: Uses OpenHands agent to automatically implement TODOs
- 🔄 **PR Management**: Creates feature branches and pull requests automatically
- 📝 **Progress Tracking**: Tracks TODO processing status and PR creation
- 📊 **Comprehensive Reporting**: Detailed GitHub Actions summary with processing status
- ⚙️ **Configurable**: Customizable limits and file patterns

## How It Works

1. **Scan Phase**: The workflow scans your codebase for `# TODO(openhands)` comments
   - Filters out false positives (documentation, test files, quoted strings)
   - Supports Python, TypeScript, and Java files
   - Provides detailed logging of found TODOs

2. **Process Phase**: For each TODO found:
   - Creates a feature branch
   - Uses OpenHands agent to implement the TODO
   - Creates a pull request with the implementation
   - Tracks processing status and PR information

3. **Summary Phase**: Generates a comprehensive summary showing:
   - All processed TODOs with their file locations
   - Associated pull request URLs for successful implementations
   - Processing status (success, partial, failed) for each TODO

## Files

- **`scanner.py`**: Smart TODO scanner with false positive filtering
- **`agent.py`**: OpenHands agent for TODO implementation
- **`prompt.py`**: Contains the prompt template for TODO implementation
- **`README.md`**: This comprehensive documentation

## Setup

### 1. Repository Secrets

Add these secrets to your GitHub repository:

- `LLM_API_KEY` - Your LLM API key (required)
- `GITHUB_TOKEN` - GitHub token with repo permissions (automatically provided)
-  Make sure Github Actions are allowed to create and review PRs (in the repo settings)

### 2. Install Workflow

The GitHub Actions workflow is already installed at `.github/workflows/todo-management.yml` in this repository.

### 3. Configure Permissions

Ensure your `GITHUB_TOKEN` has these permissions:
- `contents: write`
- `pull-requests: write`
- `issues: write`
- `issues: write` - To create issues if needed

### 4. Add TODO comments to your code

Add TODO comments in the following format anywhere in your codebase:

```python
# TODO(openhands): Add input validation for user email
def process_user_email(email):
    return email.lower()

# TODO(openhands): Implement caching mechanism for API responses
def fetch_api_data(endpoint):
    # Current implementation without caching
    return requests.get(endpoint).json()
```

Supported comment styles:
- `# TODO(openhands): description` (Python, Shell, etc.)
- `// TODO(openhands): description` (JavaScript, C++, etc.)
- `/* TODO(openhands): description */` (CSS, C, etc.)
- `<!-- TODO(openhands): description -->` (HTML, XML, etc.)

## Usage

### Manual runs

1. Go to Actions → "Automated TODO Management"
2. Click "Run workflow"
3. (Optional) Configure parameters:
   - **Max TODOs**: Maximum number of TODOs to process (default: 3)
   - **File Pattern**: Specific files to scan (leave empty for all files)
4. Click "Run workflow"

### Manual Testing

You can test the scanner component locally:

```bash
# Test the scanner on your codebase
python scanner.py /path/to/your/code
```

**Requirements**: Set `GITHUB_TOKEN` environment variable with a GitHub token that has workflow permissions.

### Scheduled runs

To enable automated scheduled runs, edit `.github/workflows/todo-management.yml` and uncomment the schedule section:

```yaml
on:
  schedule:
    # Run every Monday at 9 AM UTC
    - cron: "0 9 * * 1"
```

Customize the cron schedule as needed. See [Cron syntax reference](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule).

## Example Workflow

Here's what happens when the workflow runs:

1. **Scan**: Finds TODO comments like:
   ```python
   # TODO(openhands): Add error handling for network timeouts
   def api_call(url):
       return requests.get(url)
   ```

2. **Implementation**: Creates a feature branch and implements:
   ```python
   import requests
   from requests.exceptions import Timeout, RequestException
   
   def api_call(url, timeout=30):
       """Make API call with proper error handling for network timeouts."""
       try:
           response = requests.get(url, timeout=timeout)
           response.raise_for_status()
           return response
       except Timeout:
           raise TimeoutError(f"Request to {url} timed out after {timeout} seconds")
       except RequestException as e:
           raise ConnectionError(f"Failed to connect to {url}: {str(e)}")
   ```

3. **PR Creation**: Creates a pull request with:
   - Clear title: "Implement TODO in api_utils.py:15 - Add error handling for network timeouts"
   - Detailed description explaining the implementation
   - Link back to the original TODO

4. **Update**: Updates the original TODO:
   ```python
   # TODO(in progress: https://github.com/owner/repo/pull/123): Add error handling for network timeouts
   ```

## Configuration Options

### Workflow Inputs

- **`max_todos`**: Maximum number of TODOs to process in a single run (default: 3)
- **`file_pattern`**: File pattern to scan (future enhancement)

### Environment Variables

- **`LLM_MODEL`**: Language model to use (default: `openhands/claude-sonnet-4-5-20250929`)
- **`LLM_BASE_URL`**: Custom LLM API base URL (optional)

## Local Testing and Debugging

### Quick Component Test

```bash
# Test the scanner
python scanner.py /path/to/your/code
```

## Smart Filtering

The scanner intelligently filters out false positives and already processed TODOs:

### Processed TODO Filtering
- ❌ TODOs with PR URLs (`pull/`, `github.com/`)
- ❌ TODOs with progress markers (`TODO(in progress:`, `TODO(implemented:`, `TODO(completed:`)
- ❌ TODOs containing any URLs (`https://`)

### False Positive Filtering
- ❌ Documentation strings and comments
- ❌ Test files and mock data
- ❌ Quoted strings containing TODO references
- ❌ Print statements and variable assignments
- ❌ Code that references TODO(openhands) but isn't a TODO
- ✅ Legitimate TODO comments in source code

This ensures the workflow only processes unhandled TODOs and avoids creating duplicate PRs.

## Troubleshooting

### Common Issues

1. **No TODOs found**:
   - Ensure you're using the correct format `TODO(openhands)`
   - Check that TODOs aren't in test files or documentation
   - Use `python scanner.py .` to test the scanner locally

2. **"GitHub Actions is not permitted to create or approve pull requests"**:
   This is the most common issue. The agent successfully creates and pushes the branch, but PR creation fails.

   **Root Cause**: By default, GitHub restricts the `GITHUB_TOKEN` from creating PRs as a security measure.

   **Solution**: Enable PR creation in repository settings:
   1. Go to your repository **Settings**
   2. Navigate to **Actions** → **General**
   3. Scroll to **Workflow permissions**
   4. Check the box: **"Allow GitHub Actions to create and approve pull requests"**
   5. Click **Save**

   **Alternative Solution**: Use a Personal Access Token (PAT) instead:
   1. Create a PAT with `repo` scope at https://github.com/settings/tokens
   2. Add it as a repository secret named `GH_PAT`
   3. Update the workflow to use `${{ secrets.GH_PAT }}` instead of `${{ secrets.GITHUB_TOKEN }}`

   **Note**: Even if PR creation fails, the branch with changes is still created and pushed. You can:
   - Manually create a PR from the pushed branch
   - Check the branch on GitHub using the URL format: `https://github.com/OWNER/REPO/compare/BRANCH_NAME`

3. **Permission denied** (other):
   - Check that `GITHUB_TOKEN` has required permissions in the workflow file
   - Verify `contents: write` and `pull-requests: write` are set

4. **LLM API errors**:
   - Verify your `LLM_API_KEY` is correct and has sufficient credits
   - Check the model name is supported

5. **Workflow not found**:
   - Ensure workflow file is in `.github/workflows/`
   - Workflow must be on the main branch to be triggered

6. **Branch created but no changes visible**:
   - Verify the full branch name (check for truncation in URLs)
   - Use `git log origin/BRANCH_NAME` to see commits
   - Check if changes already got merged to main

### Debug Mode

The workflow includes comprehensive logging. Check the workflow run logs for detailed information about:
- TODOs found during scanning
- Agent execution progress
- PR creation status
- Error messages and stack traces

## Limitations

- Processes a maximum number of TODOs per run to avoid overwhelming the system
- Requires LLM API access for the OpenHands agent
- GitHub Actions usage limits apply
- Agent implementation quality depends on TODO description clarity

## Contributing

To improve this example:

1. **Add file type support**: Extend scanner for new languages
2. **Improve filtering**: Enhance false positive detection
3. **Better prompts**: Improve agent implementation quality
4. **Test locally**: Use `python scanner.py .` to test the scanner

## Related Examples

- `01_basic_action` - Basic GitHub Actions integration
- `02_pr_review` - Automated PR review workflow

This example builds on the patterns established in `01_basic_action` while adding sophisticated TODO detection and automated implementation capabilities.

