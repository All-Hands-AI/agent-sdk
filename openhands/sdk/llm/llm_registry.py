from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError

from openhands.sdk.llm.llm import LLM
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)

_SECRET_FIELDS: tuple[str, ...] = (
    "api_key",
    "aws_access_key_id",
    "aws_secret_access_key",
)
_DEFAULT_PROFILE_DIR = Path.home() / ".openhands" / "llm-profiles"


class RegistryEvent(BaseModel):
    llm: LLM

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


class LLMRegistry:
    """Manage in-memory LLM instances and their on-disk profiles."""

    def __init__(
        self,
        retry_listener: Callable[[int, int], None] | None = None,
        profile_dir: str | Path | None = None,
    ):
        """Initialize the LLM registry.

        Args:
            retry_listener: Optional callback for retry events.
            profile_dir: Directory where LLM profiles are persisted. Defaults to
                ``~/.openhands/llm-profiles`` when not provided.
        """
        self.registry_id = str(uuid4())
        self.retry_listener = retry_listener
        self.service_to_llm: dict[str, LLM] = {}
        self.subscriber: Callable[[RegistryEvent], None] | None = None
        self.profile_dir = self._resolve_profile_dir(profile_dir)

    def subscribe(self, callback: Callable[[RegistryEvent], None]) -> None:
        """Subscribe to registry events.

        Args:
            callback: Function to call when LLMs are created or updated.
        """
        self.subscriber = callback

    def notify(self, event: RegistryEvent) -> None:
        """Notify subscribers of registry events.

        Args:
            event: The registry event to notify about.
        """
        if self.subscriber:
            try:
                self.subscriber(event)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to emit event: %s", exc)

    def add(self, llm: LLM) -> None:
        """Add an LLM instance to the registry.

        Args:
            llm: The LLM instance to register.

        Raises:
            ValueError: If ``llm.service_id`` already exists in the registry.
        """
        service_id = llm.service_id
        if service_id in self.service_to_llm:
            raise ValueError(
                f"Service ID '{service_id}' already exists in registry. "
                "Use a different service_id on the LLM or call get() to retrieve the "
                "existing LLM."
            )

        self.service_to_llm[service_id] = llm
        self.notify(RegistryEvent(llm=llm))
        logger.info(
            f"[LLM registry {self.registry_id}]: Added LLM for service {service_id}"
        )

    def get(self, service_id: str) -> LLM:
        """Get an LLM instance from the registry."""
        if service_id not in self.service_to_llm:
            raise KeyError(
                f"Service ID '{service_id}' not found in registry. "
                "Use add() to register an LLM first."
            )

        logger.info(
            f"[LLM registry {self.registry_id}]: Retrieved LLM for service {service_id}"
        )
        return self.service_to_llm[service_id]

    def list_services(self) -> list[str]:
        """Return all registered service IDs."""
        return list(self.service_to_llm.keys())

    # ------------------------------------------------------------------
    # Profile management helpers
    # ------------------------------------------------------------------
    def list_profiles(self) -> list[str]:
        """List all profile IDs stored on disk."""
        return sorted(path.stem for path in self.profile_dir.glob("*.json"))

    def get_profile_path(self, profile_id: str) -> Path:
        """Return the path where ``profile_id`` is stored."""
        return self.profile_dir / f"{profile_id}.json"

    def load_profile(self, profile_id: str) -> LLM:
        """Load ``profile_id`` from disk and return an :class:`LLM`."""
        path = self.get_profile_path(profile_id)
        if not path.exists():
            raise FileNotFoundError(f"Profile not found: {profile_id} -> {path}")
        return self._load_profile_with_synced_id(path, profile_id)

    def save_profile(
        self, profile_id: str, llm: LLM, include_secrets: bool = False
    ) -> Path:
        """Persist ``llm`` under ``profile_id``.

        Args:
            profile_id: Destination identifier (filename stem).
            llm: Instance to serialize.
            include_secrets: When True, persist secret values instead of omitting
                them from the stored payload.
        """
        path = self.get_profile_path(profile_id)
        data = llm.model_dump(exclude_none=True)
        data["profile_id"] = profile_id
        if not include_secrets:
            for secret_field in _SECRET_FIELDS:
                data.pop(secret_field, None)
        else:
            for secret_field in _SECRET_FIELDS:
                value = data.get(secret_field)
                if isinstance(value, SecretStr):
                    data[secret_field] = value.get_secret_value()

        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
        logger.info(f"Saved profile {profile_id} -> {path}")
        return path

    def register_profiles(self, profile_ids: Iterable[str] | None = None) -> None:
        """Register profiles from disk into the in-memory registry."""
        candidates = profile_ids if profile_ids is not None else self.list_profiles()
        for profile_id in candidates:
            try:
                llm = self.load_profile(profile_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Failed to load profile {profile_id}: {exc}")
                continue

            try:
                self.add(llm)
            except Exception as exc:  # noqa: BLE001
                logger.info(
                    f"Skipping profile {profile_id}: registry.add failed: {exc}"
                )

    def switch_profile(self, service_id: str, profile_id: str) -> LLM:
        """Replace ``service_id``'s active LLM with ``profile_id`` and return it."""

        if service_id not in self.service_to_llm:
            raise KeyError(f"Service ID '{service_id}' not found in registry")

        current_llm = self.service_to_llm[service_id]
        if current_llm.profile_id == profile_id:
            return current_llm

        llm = self.load_profile(profile_id)
        llm = llm.model_copy(update={"service_id": service_id})
        self.service_to_llm[service_id] = llm
        self.notify(RegistryEvent(llm=llm))
        logger.info(
            f"[LLM registry {self.registry_id}]: Switched service {service_id} "
            f"to profile {profile_id}"
        )
        return llm

    def validate_profile(self, data: Mapping[str, Any]) -> tuple[bool, list[str]]:
        """Return (is_valid, errors) after validating a profile payload."""
        try:
            LLM.model_validate(dict(data))
        except ValidationError as exc:
            messages: list[str] = []
            for error in exc.errors():
                loc = ".".join(str(piece) for piece in error.get("loc", ()))
                if loc:
                    messages.append(f"{loc}: {error.get('msg')}")
                else:
                    messages.append(error.get("msg", "Unknown validation error"))
            return False, messages
        return True, []

    # ------------------------------------------------------------------
    # Internal helper methods
    # ------------------------------------------------------------------
    def _resolve_profile_dir(self, profile_dir: str | Path | None) -> Path:
        directory = (
            Path(profile_dir).expanduser()
            if profile_dir is not None
            else _DEFAULT_PROFILE_DIR
        )
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _load_profile_with_synced_id(self, path: Path, profile_id: str) -> LLM:
        llm = LLM.load_from_json(str(path))
        if llm.profile_id != profile_id:
            # force llm.profile_id to carry the correct name
            # (the name of the .json we loaded it from)
            llm = llm.model_copy(update={"profile_id": profile_id})
        return llm
