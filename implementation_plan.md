Title: Workspace Secrets (Issue #909) – SDK-only implementation (singleton bucket) linking to BashTool

Scope
- Implement a single, process-wide, ephemeral secrets bucket (singleton) in the SDK (no server changes in this PR)
- Wire BashTool/BashExecutor to use the singleton by default; eliminate Agent-level env wiring
- Keep Conversation.update_secrets as a convenience wrapper that writes into the singleton

Non-goals
- No agent-server model changes in this PR
- No persistence of secrets at rest
- No encryption at rest

Design Overview
- Global secrets facade (singleton): openhands.sdk.secrets
  - A single in-memory bucket per sandbox process. All conversations in this sandbox share this bucket (there is only one user per sandbox).
  - API:
    - update(secrets: Mapping[str, SecretValue]) -> None
    - env_for_command(command: str) -> dict[str, str]
      - Detect $KEY and ${KEY} references
      - Resolve values via SecretSource.get_value() or static strings (JIT)
    - mask_output(text: str) -> str (mask any exported/seen values with <secret-hidden>)
    - get_value(key: str) -> str | None (for tools that need direct access, not only env)
    - list_names() -> set[str]
    - clear() -> None (for tests)
  - Thread/async safety: simple locking for updates/reads if needed

- Underlying implementation
  - Reuse WorkspaceSecrets internally to implement resolution and masking logic, but expose it as a singleton bucket (not bound per workspace instance).
  - LLM is only informed of secret names; values are never exposed.

- Integration points
  - BaseWorkspace.secrets returns the singleton (for familiarity/convenience)
  - BashExecutor defaults to use the singleton facade:
    - env_provider = secrets.env_for_command
    - env_masker = secrets.mask_output
    - No Agent._configure_bash_tools_env_provider
  - Conversation.update_secrets calls secrets.update(...)

API Changes
- New: openhands.sdk.secrets facade (public)
- Remove: ConversationState.secrets_manager (breaking change)
- Remove: Agent._configure_bash_tools_env_provider (breaking change)

Implementation Steps
1) Add secrets facade module openhands-sdk/openhands/sdk/secrets.py
   - Implement update, env_for_command, mask_output, get_value, list_names, clear
   - Internally delegate to a single WorkspaceSecrets instance
2) Refactor BashExecutor to default to the secrets facade (no per-tool/provider wiring necessary)
3) Remove ConversationState.secrets_manager and Agent._configure_bash_tools_env_provider
4) Update Conversation.update_secrets to call secrets.update
5) Make BaseWorkspace.secrets return the singleton facade for convenience
6) Tests
   - Update existing secrets-related tests to rely on the singleton
   - Ensure masking and env injection work without Agent wiring

Acceptance Criteria
- BashTool exports and masks secrets via the singleton without any Agent wiring
- Secrets never written to disk
- Both static strings and SecretSource (LookupSecret) supported
- ConversationState.secrets_manager and Agent env wiring removed

Follow-ups (not in this PR)
- (#900) Server API: accept dict[str, str | SecretSource] and keep secrets only in memory (per sandbox); only expose names to LLM
- Optional: support Windows-style %KEY% detection
- Optional: TTL/refresh policies for dynamic secrets; optional scoped-injection mode (unset after command)
