"""Test/runtime import path guard.

Ensure this repository's 'openhands' package takes precedence over any
preinstalled/openhands code injected via PYTHONPATH (e.g., /openhands/code).
This prevents namespace collisions that break absolute imports in tests.

Safe no-op in environments without such path.
"""

from __future__ import annotations

import os
import sys
from types import ModuleType


REPO_ROOT = os.path.dirname(__file__)
EXTERNAL_PATH = "/openhands/code"

try:
    # If an external OpenHands tree is injected before our project, demote it.
    if EXTERNAL_PATH in sys.path:
        # Ensure repo root is present and before the external path.
        if REPO_ROOT not in sys.path:
            # Keep potential test path at index 0; insert right after it.
            insert_at = 1 if sys.path and sys.path[0] != REPO_ROOT else 0
            sys.path.insert(insert_at, REPO_ROOT)
        else:
            # Move REPO_ROOT ahead of EXTERNAL_PATH if needed.
            r_idx = sys.path.index(REPO_ROOT)
            e_idx = sys.path.index(EXTERNAL_PATH)
            if r_idx > e_idx:
                sys.path.pop(r_idx)
                sys.path.insert(1 if e_idx == 0 else 0, REPO_ROOT)
        # Demote external path to the end to avoid shadowing.
        try:
            sys.path.remove(EXTERNAL_PATH)
        except ValueError:
            pass
        sys.path.append(EXTERNAL_PATH)

    # If openhands already got imported (rare this early), ensure our path wins.
    mod: ModuleType | None = sys.modules.get("openhands")
    if mod is not None and hasattr(mod, "__path__"):
        repo_pkg_path = os.path.join(REPO_ROOT, "openhands")
        p = list(mod.__path__)  # type: ignore[attr-defined]
        if repo_pkg_path in p:
            p.remove(repo_pkg_path)
            p.insert(0, repo_pkg_path)
            mod.__path__ = p  # type: ignore[attr-defined]
except Exception:
    # Never block interpreter start because of path tweaks.
    pass
