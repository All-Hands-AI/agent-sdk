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

- **`LLM_API_KEY`** (required): Your LLM API key
  - Get one from the [OpenHands LLM Provider](https://docs.all-hands.dev/openhands/usage/llms/openhands-llms)
- `GITHUB_TOKEN` - GitHub token with repo permissions (automatically provided)
-  Make sure Github Actions are allowed to create and review PRs (in the repo settings)

### 2. Install Workflow

The GitHub Actions workflow is already installed at `.github/workflows/todo-management.yml` in this repository.

### 3. Configure Permissions

Ensure your `GITHUB_TOKEN` has these permissions:
- `contents: write`
- `pull-requests: write`

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