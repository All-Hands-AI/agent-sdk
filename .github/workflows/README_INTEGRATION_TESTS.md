# Integration Tests Workflow - Security and Usage Guide

## Overview

The integration tests workflow (`integration-runner.yml`) is designed to run comprehensive integration tests using various LLM models. It uses organization secrets for LLM API access and is configured to work safely with pull requests from forked repositories.

## How It Works

### Trigger Events

The workflow can be triggered in three ways:

1. **Manual Label Trigger** (for PRs including forks):
   - A maintainer adds the `integration-test` label to any pull request
   - This is the **primary method** for running tests on fork PRs
   
2. **Automatic on Synchronize** (for labeled PRs):
   - When new commits are pushed to a PR that already has the `integration-test` label
   - Tests automatically re-run on the updated code
   
3. **Manual Dispatch**:
   - Manual workflow trigger via GitHub Actions UI
   
4. **Scheduled**:
   - Daily run at 10:30 PM UTC

### Security Model

The workflow uses `pull_request_target` instead of `pull_request` to enable access to organization secrets even for fork PRs. This is **safe** because:

1. **Label Gating**: The workflow only runs when the `integration-test` label is present
2. **Maintainer Control**: Only maintainers can add labels to PRs
3. **Explicit Checkout**: The PR branch is explicitly checked out to test the actual PR code
4. **Synchronize Protection**: Automatic re-runs on `synchronize` events only happen if the PR already has the label

### Why This Design?

**Problem**: GitHub Actions does not expose secrets to workflows triggered by `pull_request` events from forked repositories. This is a security feature to prevent malicious PRs from exfiltrating secrets.

**Solution**: Using `pull_request_target` runs the workflow in the context of the base repository (not the fork), which provides access to secrets. The label-based trigger ensures that a maintainer must manually approve running tests with secrets by adding the label.

## Usage Guide

### For Maintainers

#### Running Integration Tests on a Fork PR

1. Review the PR code for any malicious content (especially changes to workflow files or test scripts)
2. If the code looks safe, add the `integration-test` label to the PR
3. The tests will start automatically
4. Results will be posted as a comment on the PR

#### Re-running Tests

- **After new commits**: Tests automatically re-run if the label is still present
- **To force a re-run**: Remove and re-add the `integration-test` label
- **To stop auto-runs**: Remove the `integration-test` label

### For Contributors (Fork PRs)

1. Submit your PR as normal
2. A maintainer will review your code
3. If approved, the maintainer will add the `integration-test` label
4. Wait for the test results (they'll be posted as a comment)
5. If you push new commits, tests will automatically re-run

### For Contributors (Branch PRs)

If you have write access and are working on a branch in the main repository:

1. Add the `integration-test` label to your PR yourself
2. Tests will run automatically
3. New commits will trigger automatic re-runs

## Technical Details

### Secrets Used

- `LLM_API_KEY`: API key for LLM proxy access
- `LLM_BASE_URL`: Base URL for the LLM proxy service

### Test Matrix

The workflow runs tests against multiple LLM models in parallel:
- Claude Sonnet 4.5
- GPT-5 Mini
- DeepSeek Chat

### Artifacts

Each test run produces:
- Integration test outputs (archived as tar.gz)
- Test results summary (JSON format)
- Consolidated report (Markdown format)

## Security Considerations

### Safe Practices

✅ **DO**: Review PR code before adding the `integration-test` label  
✅ **DO**: Be especially careful with changes to:
- Workflow files (`.github/workflows/`)
- Test scripts (`tests/integration/`)
- Build/dependency files

✅ **DO**: Remove the label if you need to stop automatic test runs

### Unsafe Practices

❌ **DON'T**: Add the label to PRs without reviewing the code first  
❌ **DON'T**: Leave the label on PRs that are still receiving suspicious commits  
❌ **DON'T**: Ignore warnings about workflow or test file changes

## Troubleshooting

### Tests Don't Start

- **Check**: Does the PR have the `integration-test` label?
- **Check**: Is the workflow run visible in the Actions tab?
- **Try**: Remove and re-add the label

### Tests Fail with "Secrets Not Available"

This should no longer happen with the `pull_request_target` configuration. If it does:
- Check that the workflow is using `pull_request_target`, not `pull_request`
- Verify that secrets are configured at the organization/repository level

### Tests Run on Wrong Code

- **Check**: The workflow explicitly checks out the PR branch using `github.event.pull_request.head.sha`
- **Verify**: Look at the "Checkout repository" step logs to confirm the correct commit was checked out

## References

- [GitHub Docs: pull_request_target](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#pull_request_target)
- [Keeping GitHub Actions Secure](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [Preventing pwn requests](https://securitylab.github.com/research/github-actions-preventing-pwn-requests/)
