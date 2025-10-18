LLM Profiles (design)

Overview

This document records the design decision for "LLM profiles" (named LLM configuration files) and how they map to the existing LLM model and persistence in the SDK.

Key decisions

- Reuse the existing LLM Pydantic model schema. A profile file is simply the JSON dump of an LLM instance (the same shape produced by LLM.model_dump(exclude_none=True) or LLM.load_from_json).
- Storage location: ~/.openhands/llm-profiles/<profile_name>.json. The profile_name is the filename (no extension) used to refer to the profile.
- Do not change ConversationState or Agent serialization format for now. Profiles are a convenience for creating LLM instances and registering them in the runtime LLMRegistry.
- Secrets: do NOT store plaintext API keys in profile files by default. Prefer storing the env var name in the LLM.api_key (via LLM.load_from_env) or keep the API key in runtime SecretsManager. The ProfileManager.save_profile API will expose an include_secrets flag; default False.
- LLM.service_id semantics: keep current behavior (a small set of runtime "usage" identifiers such as 'agent', 'condenser', 'title-gen', etc.). Do not use service_id as the profile name. We will evaluate a rename (service_id -> usage_id) in a separate task (see agent-sdk-23).

ProfileManager API (summary)

- list_profiles() -> list[str]
- load_profile(name: str) -> LLM
- save_profile(name: str, llm: LLM, include_secrets: bool = False) -> str (path)
- register_all(registry: LLMRegistry) -> None

Implementation notes

- Use LLM.load_from_json(path) for loading and llm.model_dump(exclude_none=True) for saving.
- Default directory: os.path.expanduser('~/.openhands/llm-profiles/')
- When loading, do not inject secrets. The runtime should reconcile secrets via ConversationState/Agent resolve_diff_from_deserialized or via SecretsManager.
- When saving, respect include_secrets flag; if False, ensure secret fields (api_key, aws_* keys) are omitted or masked.

CLI

- Use a single flag: --llm <profile_name> to select a profile for the agent LLM.
- Also support an environment fallback: OPENHANDS_LLM_PROFILE.
- Provide commands: `openhands llm list`, `openhands llm show <profile_name>` (redacts secrets).

Migration

- Migration from inline configs to profiles: provide a migration helper script to extract inline LLMs from ~/.openhands/agent_settings.json and conversation base_state.json into ~/.openhands/llm-profiles/<name>.json and update references (manual opt-in by user).

Notes on service_id rename

- There is an ongoing discussion about renaming `LLM.service_id` to a clearer name (e.g., `usage_id` or `token_tracking_id`) because `service_id` is overloaded. We will not rename immediately; agent-sdk-23 will investigate the migration and impact.

