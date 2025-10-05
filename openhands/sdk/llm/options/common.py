from __future__ import annotations

from typing import Any


def coerce_and_default(user_kwargs: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict with defaults applied when keys are absent.

    - Pure and deterministic: no I/O, does not mutate inputs
    - Only applies defaults when the key is missing and default is not None
    - Does not coerce or alter user-provided values
    - schema values can be literal defaults or callables returning a default
    """
    out = dict(user_kwargs)
    for key, default in schema.items():
        if key in out:
            continue
        if default is None:
            continue
        out[key] = default() if callable(default) else default
    return out
