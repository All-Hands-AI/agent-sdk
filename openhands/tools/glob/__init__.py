# Avoid shadowing stdlib 'glob' during build isolation.
# If this module is imported as top-level 'glob', re-export stdlib functions
# directly from the standard library file to bypass sys.path lookups.
if __name__ == "glob":  # imported as top-level module (e.g., by setuptools)
    import importlib.util
    import sysconfig
    from pathlib import Path

    stdlib_dir = Path(sysconfig.get_path("stdlib"))
    stdlib_glob_path = stdlib_dir / "glob.py"
    spec = importlib.util.spec_from_file_location("_stdlib_glob", stdlib_glob_path)
    if spec and spec.loader:  # load stdlib glob without touching sys.path
        _stdlib_glob = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_stdlib_glob)  # type: ignore[union-attr]
        glob = _stdlib_glob.glob  # type: ignore[attr-defined]
        iglob = getattr(_stdlib_glob, "iglob", None)
        escape = getattr(_stdlib_glob, "escape", None)
        __all__ = [n for n in ("glob", "iglob", "escape") if globals().get(n)]
    else:
        # As an absolute last resort, define a no-op that raises at call time
        def glob(pattern, recursive=False):  # type: ignore[no-redef]
            raise RuntimeError("Failed to load stdlib glob during build isolation")

        __all__ = ["glob"]
else:
    # Normal package imports
    from .definition import (
        GlobAction,
        GlobObservation,
        GlobTool,
    )
    from .impl import GlobExecutor

    __all__ = [
        # === Core Tool Interface ===
        "GlobTool",
        "GlobAction",
        "GlobObservation",
        "GlobExecutor",
    ]
