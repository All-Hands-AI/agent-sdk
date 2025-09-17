"""
Unit test to ensure that OS environment variables are not accessed anywhere
in the agent_server package outside of the config module.

This test helps maintain proper separation of concerns by ensuring that
all environment variable access is centralized in the config module.
"""

import ast
from pathlib import Path
from typing import List, Set, Tuple

from openhands import agent_server
from openhands.agent_server import config


def get_env_var_access_from_file(file_path: Path) -> List[Tuple[int, str]]:
    """
    Parse a Python file and extract all environment variable access patterns.

    Returns a list of tuples containing (line_number, access_pattern).
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        tree = ast.parse(content)
    except SyntaxError:
        # If we can't parse the file, skip it
        return []

    env_accesses = []

    class EnvVarVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Check for os.getenv() calls
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "os"
                and node.func.attr == "getenv"
            ):
                env_accesses.append((node.lineno, "os.getenv()"))

            # Check for getenv() calls (direct import)
            elif isinstance(node.func, ast.Name) and node.func.id == "getenv":
                env_accesses.append((node.lineno, "getenv()"))

            self.generic_visit(node)

        def visit_Subscript(self, node):
            # Check for os.environ[] access
            if (
                isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "os"
                and node.value.attr == "environ"
            ):
                env_accesses.append((node.lineno, "os.environ[]"))

            # Check for environ[] access (direct import)
            elif isinstance(node.value, ast.Name) and node.value.id == "environ":
                env_accesses.append((node.lineno, "environ[]"))

            self.generic_visit(node)

        def visit_Attribute(self, node):
            # Check for os.environ.get() calls
            if (
                isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "os"
                and node.value.attr == "environ"
                and node.attr == "get"
            ):
                env_accesses.append((node.lineno, "os.environ.get()"))

            # Check for environ.get() calls (direct import)
            elif (
                isinstance(node.value, ast.Name)
                and node.value.id == "environ"
                and node.attr == "get"
            ):
                env_accesses.append((node.lineno, "environ.get()"))

            self.generic_visit(node)

    visitor = EnvVarVisitor()
    visitor.visit(tree)

    return env_accesses


def get_direct_env_imports_from_file(file_path: Path) -> Set[str]:
    """
    Parse a Python file and extract direct imports of environment-related functions.

    Returns a set of imported names that could be used to access environment variables.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return set()

    env_imports = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "os":
                for alias in node.names:
                    if alias.name in ["getenv", "environ"]:
                        env_imports.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "os":
                    # This is handled by the AST visitor above
                    pass

    return env_imports


def test_no_env_var_access_outside_config():
    """
    Test that no files in the agent_server package access environment variables
    except for the config.py file.
    """
    # Get the path to the agent_server directory
    agent_server_dir = Path(agent_server.__file__).parent

    # Get all Python files in the agent_server directory
    python_files = list(agent_server_dir.glob("*.py"))

    # Remove config.py from the list since it's allowed to access env vars
    config_file = agent_server_dir / "config.py"
    if config_file in python_files:
        python_files.remove(config_file)

    # Check each file for environment variable access
    violations = []

    for file_path in python_files:
        # Skip __init__.py files as they typically don't contain logic
        if file_path.name == "__init__.py":
            continue

        # Check for environment variable access patterns
        env_accesses = get_env_var_access_from_file(file_path)

        if env_accesses:
            for line_no, pattern in env_accesses:
                violations.append(f"{file_path.name}:{line_no} - {pattern}")

        # Also check for direct imports that could be used for env access
        env_imports = get_direct_env_imports_from_file(file_path)
        if env_imports:
            violations.append(f"{file_path.name} - Direct env imports: {env_imports}")

    # Assert no violations were found
    assert not violations, (
        "Environment variable access found outside config.py. "
        "All environment variable access should be centralized in config.py. "
        "Violations found:\n" + "\n".join(violations)
    )


def test_config_file_env_access_is_allowed():
    """
    Test that the config.py file is allowed to access environment variables
    and that our detection logic works correctly.
    """
    # Get the path to the config.py file
    config_file = Path(config.__file__)

    # Check that config.py does access environment variables
    env_accesses = get_env_var_access_from_file(config_file)

    # We expect to find environment variable access in config.py
    assert env_accesses, (
        "Expected to find environment variable access in config.py, "
        "but none was detected. This might indicate an issue with the test logic."
    )

    # Verify that the expected patterns are found
    access_patterns = [pattern for _, pattern in env_accesses]
    assert "os.getenv()" in access_patterns, (
        "Expected to find os.getenv() calls in config.py"
    )


def test_comprehensive_env_var_patterns():
    """
    Test that our detection logic can identify various patterns of environment
    variable access by testing against known patterns.
    """
    # Create a temporary test file content with various env var access patterns
    test_content = """
import os
from os import getenv, environ

# Various patterns that should be detected
value1 = os.getenv("TEST_VAR")
value2 = os.environ["TEST_VAR"]
value3 = os.environ.get("TEST_VAR")
value4 = getenv("TEST_VAR")
value5 = environ["TEST_VAR"]
value6 = environ.get("TEST_VAR")
"""

    # Write to a temporary file
    temp_file = Path("/tmp/test_env_patterns.py")
    with open(temp_file, "w") as f:
        f.write(test_content)

    try:
        # Test our detection logic
        env_accesses = get_env_var_access_from_file(temp_file)
        env_imports = get_direct_env_imports_from_file(temp_file)

        # We should detect all the patterns
        access_patterns = [pattern for _, pattern in env_accesses]

        expected_patterns = [
            "os.getenv()",
            "os.environ[]",
            "os.environ.get()",
            "getenv()",
            "environ[]",
            "environ.get()",
        ]

        for expected in expected_patterns:
            assert expected in access_patterns, (
                f"Failed to detect pattern: {expected}. "
                f"Detected patterns: {access_patterns}"
            )

        # We should also detect the direct imports
        assert "getenv" in env_imports, "Failed to detect direct getenv import"
        assert "environ" in env_imports, "Failed to detect direct environ import"

    finally:
        # Clean up the temporary file
        if temp_file.exists():
            temp_file.unlink()
