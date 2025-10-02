from abc import ABC, abstractmethod

import httpx
from pydantic import Field, SecretStr

from openhands.sdk.utils.models import DiscriminatedUnionMixin


class SecretSource(DiscriminatedUnionMixin, ABC):
    """Source for a named secret which may be obtained dynamically"""

    description: str | None = Field(
        default=None,
        description="Optional description for this secret",
    )

    @abstractmethod
    def get_value(self) -> str | None:
        """Get the value of a secret in plain text"""


class StaticSecret(SecretSource):
    """A secret stored locally"""

    value: SecretStr

    def get_value(self):
        return self.value.get_secret_value()


class LookupSecret(SecretSource):
    """A secret looked up from some external url"""

    url: str
    headers: dict[str, str] = Field(default_factory=dict)

    def get_value(self):
        response = httpx.get(self.url, headers=self.headers)
        response.raise_for_status()
        return response.text
