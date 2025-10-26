from __future__ import annotations

from collections.abc import Mapping

from openhands.sdk.workspace.secrets import SecretValue, WorkspaceSecrets


_STORE: WorkspaceSecrets | None = None


def get_store() -> WorkspaceSecrets:
    global _STORE
    if _STORE is None:
        _STORE = WorkspaceSecrets()
    return _STORE


def update(secrets: Mapping[str, SecretValue]) -> None:
    get_store().update_secrets(secrets)


def env_for_command(command: str) -> dict[str, str]:
    return get_store().get_env_vars_for_command(command)


def mask_output(text: str) -> str:
    return get_store().mask_output(text)


def get_value(key: str) -> str | None:
    return get_store().get_value(key)


def list_names() -> set[str]:
    return get_store().names()


def clear() -> None:
    get_store().clear()
