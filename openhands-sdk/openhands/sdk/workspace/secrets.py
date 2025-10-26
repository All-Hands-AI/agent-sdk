from __future__ import annotations

import re
from collections.abc import Mapping

from pydantic import SecretStr

from openhands.sdk.conversation.secret_source import SecretSource, StaticSecret
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)

SecretValue = str | SecretSource


class WorkspaceSecrets:
    """In-memory, workspace-scoped secrets with JIT env injection and masking.

    - update_secrets: register/overwrite secrets by name
    - get_env_vars_for_command: detect $KEY or ${KEY} usage and resolve values
    - mask_output: replace exported values with <secret-hidden>
    - get_value: resolve a single key and track it for masking
    - names: return all known secret names
    - clear: remove all stored secrets and exported values
    """

    def __init__(self) -> None:
        self._sources: dict[str, SecretSource] = {}
        self._exported_values: dict[str, str] = {}
        # Match $KEY or ${KEY}, where KEY matches [A-Z][A-Z0-9_]*
        self._pattern: re.Pattern[str] = re.compile(r"\$(?:\{)?([A-Z][A-Z0-9_]*)\}?\b")

    def update_secrets(self, secrets: Mapping[str, SecretValue]) -> None:
        sources = {k: _to_source(v) for k, v in secrets.items()}
        self._sources.update(sources)
        logger.debug(f"WorkspaceSecrets updated {len(secrets)} key(s)")

    def get_env_vars_for_command(self, command: str) -> dict[str, str]:
        if not command:
            return {}
        keys = set(m.group(1) for m in self._pattern.finditer(command))
        if not keys:
            return {}
        env: dict[str, str] = {}
        for key in keys:
            val = self.get_value(key)
            if val:
                env[key] = val
        return env

    def get_value(self, key: str) -> str | None:
        src = self._sources.get(key)
        if not src:
            return None
        try:
            val = src.get_value()
            if val:
                self._exported_values[key] = val
            return val
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Failed to resolve secret '{key}': {e}")
            return None

    def names(self) -> set[str]:
        return set(self._sources.keys())

    def clear(self) -> None:
        self._sources.clear()
        self._exported_values.clear()

    def mask_output(self, text: str) -> str:
        if not text:
            return text
        masked = text
        for val in self._exported_values.values():
            if val:
                masked = masked.replace(val, "<secret-hidden>")
        return masked


def _to_source(value: SecretValue) -> SecretSource:
    if isinstance(value, SecretSource):
        return value
    if isinstance(value, str):
        return StaticSecret(value=SecretStr(value))
    raise ValueError("Invalid SecretValue")
