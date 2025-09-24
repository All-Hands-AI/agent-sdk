"""
Unit test to ensure the config module doesn't import anything from openhands
to prevent circular dependencies.
"""

import ast
from pathlib import Path

from openhands.agent_server import config


def get_imports_from_file(file_path: Path) -> set[str]:
    """
    Parse a Python file and extract all import statements.

    Returns a set of module names that are imported.
    """
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    tree = ast.parse(content)
    imports = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)

    return imports


def test_config_no_circular_imports():
    """
    Test that the config module doesn't import anything from openhands
    to prevent circular dependencies.
    """
    # Get the path to the config.py file
    config_file = Path(config.__file__)

    # Get all imports from the config file
    imports = get_imports_from_file(config_file)

    # Check that no imports start with 'openhands'
    openhands_imports = [
        imp for imp in imports if imp.startswith("openhands.agent_server")
    ]

    assert not openhands_imports, (
        f"Config module should not import from openhands package to prevent "
        f"circular dependencies. Found imports: {openhands_imports}"
    )


def test_config_imports_are_external_only():
    """
    Test that config only imports from external packages or standard library.
    This is a more comprehensive check to ensure we don't accidentally introduce
    any internal imports.
    """
    # Get the path to the config.py file
    config_file = Path(config.__file__)

    # Get all imports from the config file
    imports = get_imports_from_file(config_file)

    # Define allowed import patterns (standard library and external packages)
    allowed_patterns = [
        "pathlib",
        "pydantic",
        "typing",
        "os",
        "sys",
        "json",
        "logging",
        "dataclasses",
        "enum",
        "abc",
        "collections",
        "functools",
        "itertools",
        "re",
        "datetime",
        "uuid",
        "hashlib",
        "base64",
    ]

    # Check each import
    for imp in imports:
        # Skip relative imports (they start with '.')
        if imp.startswith("."):
            continue

        # Check if it's an allowed pattern or a top-level external package
        is_allowed = any(imp.startswith(pattern) for pattern in allowed_patterns) or (
            # Allow top-level external packages (no dots typically means external)
            "." not in imp.split(".")[0] and not imp.startswith("openhands")
        )

        # Specifically disallow any openhands imports
        if imp.startswith("openhands"):
            assert False, f"Config should not import from openhands: {imp}"

        # For now, we'll be permissive about other imports but log them
        if not is_allowed:
            print(f"Warning: Potentially internal import detected: {imp}")
