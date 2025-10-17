# NOTE:
# This package is named 'glob' under 'openhands.tools'. During packaging, build backends
# like setuptools import the stdlib 'glob' module (e.g., `from glob import glob`).
# Some build environments put this directory (openhands/tools) directly on sys.path,
# causing top-level imports of 'glob' to resolve to this package instead of stdlib.
# To avoid breaking third-party builds, we provide a minimal compatibility shim when
# imported as top-level 'glob' by exposing a function named 'glob' (and iglob) with
# similar behavior using pathlib.

from __future__ import annotations

import fnmatch
import re
from collections.abc import Iterator
from pathlib import Path


def _pathlike_str(p: Path) -> str:
    try:
        return str(p)
    except Exception:
        return p.as_posix()


def iglob(pattern: str, recursive: bool = False) -> Iterator[str]:
    # pathlib handles '**' recursion; use rglob when explicit recursion requested
    if recursive:
        for p in Path().rglob(pattern):
            yield _pathlike_str(p)
    else:
        for p in Path().glob(pattern):
            yield _pathlike_str(p)


def glob(pattern: str, recursive: bool = False) -> list[str]:
    return list(iglob(pattern, recursive=recursive))


def escape(pathname: str) -> str:
    # Compatible with stdlib glob.escape (Python 3.12)
    return re.sub(r"([*?[])", r"[\1]", pathname)


def has_magic(s: str) -> bool:
    return re.search(r"[*?[]", s) is not None


def translate(pat: str) -> str:
    # Delegate to fnmatch's translation
    return fnmatch.translate(pat)


# Only expose the OpenHands tool symbols when imported via the fully qualified
# package path 'openhands.tools.glob', not when shadowing stdlib as top-level 'glob'.
if __name__ != "glob":
    from .definition import GlobAction, GlobObservation, GlobTool
    from .impl import GlobExecutor

    __all__ = [
        "GlobTool",
        "GlobAction",
        "GlobObservation",
        "GlobExecutor",
        "glob",
        "iglob",
        "escape",
        "has_magic",
        "translate",
    ]
else:
    __all__ = ["glob", "iglob", "escape", "has_magic", "translate"]
