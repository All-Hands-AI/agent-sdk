Title: Workspace Secrets (Issue #909) – SDK-only implementation linking to BashTool

Scope
- Implement workspace-scoped, ephemeral secrets in SDK only (no server changes in this PR)
- Link BashTool/BashExecutor to workspace secrets so it works without Agent._configure_bash_tools_env_provider
- Keep Conversation.update_secrets working by writing into workspace secrets (and optionally the existing conversation-level manager for temporary compatibility)

Non-goals
- No agent-server model changes in this PR
- No persistence of secrets at rest
- No encryption at rest

Design Overview
- WorkspaceSecrets: in-memory secret store bound to a workspace instance
  - update_secrets(secrets: Mapping[str, SecretValue]) -> None
  - get_env_vars_for_command(command: str) -> dict[str, str]
    - Detect exact references to $KEY and ${KEY}
    - For each referenced key, resolve value via SecretSource.get_value() or Static string
    - Cache last exported values for masking
  - mask_output(output: str) -> str
    - Replace any of the exported values with <secret-hidden>

- Integration points
  - BaseWorkspace gets a PrivateAttr _secrets and a secrets property returning a WorkspaceSecrets instance
  - BashExecutor: if env_provider/env_masker are not supplied, it queries conversation.workspace.secrets for JIT envs and masking
  - LocalConversation.update_secrets writes into workspace.secrets; retain existing state.secrets_manager write for compatibility (to be removed later in #852)

API Changes
- New: openhands.sdk.workspace.secrets.WorkspaceSecrets (internal)
- New: BaseWorkspace.secrets property (runtime only)
- No changes to public Conversation API; update_secrets still exists

Implementation Steps
1) Create WorkspaceSecrets in openhands-sdk/openhands/sdk/workspace/secrets.py
   - Types: reuse SecretValue, SecretSource, StaticSecret
   - Implement update_secrets, get_env_vars_for_command (regex), mask_output, exported_values cache
2) Add secrets PrivateAttr to BaseWorkspace and secrets property to access/create it
3) Modify BashExecutor to accept optional conversation, and fallback to conversation.state.workspace.secrets when env_provider/env_masker are None
   - Alternative: wire in via BashTool.create by setting env_provider/env_masker from conv_state.workspace.secrets
   - Choose: wire in via BashTool.create for simplicity and testability
4) Update BashTool.create to set env_provider and env_masker based on conv_state.workspace.secrets
5) Update LocalConversation.update_secrets to also call workspace.secrets.update_secrets
6) Tests
   - New test: tests/tools/execute_bash/test_workspace_secrets.py
     - Create LocalConversation with LocalWorkspace; call conversation.update_secrets with {"API_KEY": "secret"}; construct BashTool; run ExecuteBashAction printing $API_KEY; expect masked output and export behavior
   - Keep existing tests intact (env_provider path still works)

Acceptance Criteria
- BashTool masks and exports secrets when only workspace secrets are present (no Agent wiring)
- Secrets are never written to disk (no changes in meta/state dumps)
- update_secrets with both str and SecretSource supported

Follow-ups (not in this PR)
- Issue #852: remove ConversationState.secrets_manager and Agent._configure_bash_tools_env_provider once all tools use workspace.secrets
- Server changes to accept dict[str, str | SecretSource] and stop persisting secrets at rest (#900)
- Improve secret detection to support Windows-style %KEY% if needed
