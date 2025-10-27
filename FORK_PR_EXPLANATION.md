# Understanding GitHub Actions and Fork PRs: Why Integration Tests Fail

## The Problem

When a pull request comes from a forked repository, GitHub Actions workflows triggered by the `pull_request` event **do not have access to repository or organization secrets**. This is a deliberate security feature to prevent malicious actors from:

1. Creating a fork of your repository
2. Opening a PR with malicious code that exfiltrates secrets
3. Gaining access to sensitive credentials

In the case of issue #931, the integration tests require `LLM_API_KEY` and `LLM_BASE_URL` secrets to run. When these tests are triggered by a PR from a fork using the `pull_request` event, these secrets are empty/undefined, causing the tests to fail.

## Why This Happens

GitHub's security model for fork PRs:

- **`pull_request` event**: 
  - Runs in the context of the fork
  - Checks out the PR branch code
  - **NO access to base repository secrets** ❌
  - Read-only GITHUB_TOKEN permissions (by default)
  - Safe, but can't use secrets

- **`pull_request_target` event**:
  - Runs in the context of the base repository
  - Has **full access to secrets** ✅
  - Read/write GITHUB_TOKEN permissions (by default)
  - **DANGEROUS** if not properly secured! ⚠️

## The Workaround: Using `pull_request_target` Safely

The solution is to use `pull_request_target` instead of `pull_request` for workflows that need secrets, BUT with proper security measures:

### Security Requirements

1. **Never checkout PR code directly** when using `pull_request_target` without review
2. **Use a label-based trigger** to require manual approval before running
3. **Checkout PR code explicitly** after manual approval (via the label)
4. **Limit permissions** to only what's needed

### Implementation Strategy

For the integration tests workflow:

1. Change the trigger from `pull_request` to `pull_request_target` 
2. Keep the existing label-based condition: `github.event.label.name == 'integration-test'`
3. Explicitly checkout the PR branch using:
   ```yaml
   - name: Checkout PR branch
     uses: actions/checkout@v5
     with:
       ref: ${{ github.event.pull_request.head.sha }}
   ```

This approach ensures:
- Secrets are available (because we're using `pull_request_target`)
- Security is maintained (because a maintainer must manually add the `integration-test` label)
- The actual PR code is tested (because we explicitly checkout the PR branch)

## Alternative Workarounds

Other possible approaches (not recommended for this use case):

1. **Require manual workflow_dispatch**: Less convenient, requires maintainers to manually trigger
2. **Use a bot to re-trigger**: Adds complexity with a separate bot system
3. **Skip integration tests on forks**: Tests wouldn't run on external contributions
4. **Ask contributors to push to branches in the main repo**: Requires giving write access to contributors

## References

- [GitHub Docs: Events that trigger workflows](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#pull_request_target)
- [GitHub Docs: Keeping your GitHub Actions and workflows secure](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [Secure usage of pull_request_target](https://securitylab.github.com/research/github-actions-preventing-pwn-requests/)

## Conclusion

The workflow already has the right structure (label-based trigger), it just needs to be switched from `pull_request` to `pull_request_target` to access the organization secrets while maintaining security through the manual label approval process.
