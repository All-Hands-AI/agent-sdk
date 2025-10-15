# PR Review Workflow

This example demonstrates how to set up a GitHub Actions workflow for automated pull request reviews using the OpenHands agent SDK. When a PR is labeled with `review-this`, OpenHands will analyze the changes and provide detailed, constructive feedback.

## Files

- **`workflow.yml`**: GitHub Actions workflow file that triggers on PR labels
- **`agent_script.py`**: Python script that runs the OpenHands agent for PR review
- **`README.md`**: This documentation file

## Features

- **Automatic Trigger**: Reviews are triggered when the `review-this` label is added to a PR
- **Comprehensive Analysis**: Analyzes code changes in context of the entire repository
- **Detailed Feedback**: Provides structured review comments covering:
  - Overall assessment of changes
  - Code quality and best practices
  - Potential issues and security concerns
  - Specific improvement suggestions
  - Positive feedback on good practices
- **GitHub Integration**: Posts review comments directly to the PR

## Setup

### 1. Copy the workflow file

Copy `workflow.yml` to `.github/workflows/pr-review.yml` in your repository:

```bash
cp examples/github_workflows/02_PR_review/workflow.yml .github/workflows/pr-review.yml
```

### 2. Configure secrets

Set the following secrets in your GitHub repository settings:

- **`LLM_API_KEY`** (required): Your LLM API key
  - Get one from the [OpenHands LLM Provider](https://docs.all-hands.dev/openhands/usage/llms/openhands-llms)

**Note**: The workflow automatically uses the `GITHUB_TOKEN` secret that's available in all GitHub Actions workflows.

### 3. Customize the workflow (optional)

Edit `.github/workflows/pr-review.yml` to customize the configuration in the `env` section:

```yaml
env:
    # Optional: Use a different LLM model
    LLM_MODEL: openhands/claude-sonnet-4-5-20250929
    # Optional: Use a custom LLM base URL
    # LLM_BASE_URL: 'https://custom-api.example.com'
```

### 4. Create the review label

Create a `review-this` label in your repository:

1. Go to your repository → Issues → Labels
2. Click "New label"
3. Name: `review-this`
4. Description: `Trigger OpenHands PR review`
5. Color: Choose any color you prefer
6. Click "Create label"

## Usage

### Triggering a Review

To trigger an automated review of a pull request:

1. Open the pull request you want reviewed
2. Add the `review-this` label to the PR
3. The workflow will automatically start and analyze the changes
4. Review comments will be posted to the PR when complete

### Review Process

The OpenHands agent will:

1. **Repository Access**: Check out the feature branch with full repository access
2. **Interactive Analysis**: Use bash commands to thoroughly inspect the changes:
   - `git diff origin/main...HEAD` to see the full diff
   - `find` and `ls` to understand project structure
   - `cat` and `head` to examine specific files
   - `git log` to review commit history
3. **Contextual Understanding**: Analyze changes within the broader codebase context
4. **Generate review**: Create comprehensive feedback covering:
   - Overall impact and assessment
   - Code quality observations
   - Potential bugs or security issues
   - Performance considerations
   - Testing coverage and documentation
   - Best practice recommendations
   - Positive feedback on good implementations
5. **Post review**: Add the review as a comment on the PR

### Example Review Output

The agent provides structured feedback like:

```
## Overall Assessment
This PR introduces a new authentication system with proper error handling and security considerations. The implementation follows established patterns and includes appropriate validation.

## Code Quality
- Well-structured code with clear separation of concerns
- Good use of type hints and documentation
- Consistent naming conventions throughout

## Potential Issues
- Consider adding rate limiting to the login endpoint (line 45)
- The password validation could be strengthened (line 78)

## Suggestions
- Add unit tests for the new authentication methods
- Consider using environment variables for configuration constants

## Positive Feedback
- Excellent error handling with informative messages
- Good use of async/await patterns for database operations
- Security best practices followed for password hashing
```

## Customization

### Using a Custom Agent Script

You can specify a custom agent script by modifying the `AGENT_SCRIPT_URL` in the workflow:

```yaml
env:
    AGENT_SCRIPT_URL: path/to/your/custom_pr_review_script.py
```

Your custom script should:
- Accept the same environment variables as the default script
- Use the OpenHands SDK to analyze the PR
- Post review comments using the GitHub API or CLI

### Modifying Review Criteria

To customize what the agent focuses on during reviews, you can:

1. Fork this repository
2. Modify the `create_review_prompt()` function in `agent_script.py`
3. Update the `AGENT_SCRIPT_URL` in your workflow to point to your modified script

### Different Trigger Conditions

You can modify the workflow trigger to use different labels or conditions:

```yaml
on:
    pull_request:
        types: [labeled]

jobs:
    pr-review:
        # Use a different label
        if: contains(github.event.label.name, 'needs-review')
        # Or trigger on multiple labels
        if: contains(github.event.label.name, 'review-this') || contains(github.event.label.name, 'security-review')
```

## Troubleshooting

### Common Issues

**Review not triggered**:
- Ensure the `review-this` label exists in your repository
- Check that the workflow file is in `.github/workflows/`
- Verify the `LLM_API_KEY` secret is set

**Review fails with authentication error**:
- Confirm your `LLM_API_KEY` is valid and has sufficient credits
- Check that the `GITHUB_TOKEN` has the necessary permissions

**No review comment posted**:
- Check the workflow logs for errors
- Ensure the GitHub CLI installation succeeded
- Verify the repository permissions allow the workflow to comment on PRs

### Viewing Logs

To debug issues:

1. Go to Actions → "PR Review by OpenHands"
2. Click on the failed workflow run
3. Expand the "Run PR review" step to see detailed logs
4. Download the "openhands-pr-review-logs" artifact for additional debugging information

## Limitations

- **Large PRs**: Very large PRs with extensive changes may hit token limits
- **Binary Files**: The agent focuses on text-based code changes
- **Context Window**: Extremely large repositories may exceed the LLM's context window
- **Rate Limits**: Frequent reviews may hit API rate limits

## Best Practices

- **Use Selectively**: Apply the `review-this` label to PRs that would benefit most from automated review
- **Combine with Human Review**: Use OpenHands reviews to supplement, not replace, human code review
- **Review the Reviews**: Always validate the agent's suggestions before implementing them
- **Iterate**: Use feedback from the reviews to improve your code quality over time

## Example Use Cases

- **Security Reviews**: Flag potential security vulnerabilities in code changes
- **Code Quality**: Ensure adherence to coding standards and best practices
- **Documentation**: Identify missing documentation or unclear code
- **Performance**: Spot potential performance issues in new code
- **Learning**: Help team members learn from detailed feedback on their changes

## References

- [OpenHands SDK Documentation](https://docs.all-hands.dev/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [LLM Provider Setup](https://docs.all-hands.dev/openhands/usage/llms/openhands-llms)
- [GitHub CLI Documentation](https://cli.github.com/manual/)