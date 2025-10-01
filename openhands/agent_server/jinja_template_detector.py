"""
Automated detection of Jinja2 template directories for PyInstaller.

This module provides utilities to automatically discover directories containing
.j2 template files and generate the appropriate data file mappings for PyInstaller.
"""

import os
from pathlib import Path


def find_jinja_template_directories(
    project_root: Path,
    package_prefix: str = "openhands",
    exclude_patterns: list[str] | None = None,
) -> list[tuple[str, str]]:
    """
    Automatically detect directories containing .j2 template files.

    Args:
        project_root: Root directory of the project to scan
        package_prefix: Package prefix to include in the destination path
                       (default: "openhands")
        exclude_patterns: List of path patterns to exclude
                         (e.g., [".venv", "__pycache__"])

    Returns:
        List of tuples (source_path, destination_path) suitable for PyInstaller datas

    Example:
        >>> project_root = Path("/path/to/project")
        >>> template_dirs = find_jinja_template_directories(project_root)
        >>> print(template_dirs)
        [
            ('/path/to/project/openhands/sdk/agent/prompts',
             'openhands/sdk/agent/prompts'),
            ('/path/to/project/openhands/sdk/context/condenser/prompts',
             'openhands/sdk/context/condenser/prompts'),
            ('/path/to/project/openhands/sdk/context/prompts/templates',
             'openhands/sdk/context/prompts/templates')
        ]
    """
    if exclude_patterns is None:
        exclude_patterns = [
            ".venv",
            "__pycache__",
            ".git",
            "node_modules",
            ".pytest_cache",
        ]

    template_directories = []

    # Walk through the project directory
    for root, dirs, files in os.walk(project_root):
        # Skip excluded directories
        dirs[:] = [
            d for d in dirs if not any(pattern in d for pattern in exclude_patterns)
        ]

        # Check if this directory contains .j2 files
        j2_files = [f for f in files if f.endswith(".j2")]

        if j2_files:
            # Convert absolute path to relative path from project root
            rel_path = Path(root).relative_to(project_root)

            # Only include directories under the specified package prefix
            if str(rel_path).startswith(package_prefix):
                source_path = str(Path(root))
                dest_path = str(rel_path).replace(
                    os.sep, "/"
                )  # Use forward slashes for PyInstaller

                template_directories.append((source_path, dest_path))

    # Sort by destination path for consistent ordering
    template_directories.sort(key=lambda x: x[1])

    return template_directories


def get_jinja_template_data_files(
    project_root: Path,
    package_prefix: str = "openhands",
    exclude_patterns: list[str] | None = None,
    verbose: bool = False,
) -> list[tuple[str, str]]:
    """
    Get Jinja2 template data files for PyInstaller with optional verbose output.

    This is a convenience wrapper around find_jinja_template_directories that
    can optionally print information about discovered templates.

    Args:
        project_root: Root directory of the project to scan
        package_prefix: Package prefix to include in the destination path
        exclude_patterns: List of path patterns to exclude
        verbose: If True, print information about discovered templates

    Returns:
        List of tuples (source_path, destination_path) for PyInstaller datas
    """
    template_dirs = find_jinja_template_directories(
        project_root, package_prefix, exclude_patterns
    )

    if verbose:
        print(f"Found {len(template_dirs)} directories containing .j2 templates:")
        for source, dest in template_dirs:
            # Count .j2 files in each directory
            j2_count = len([f for f in os.listdir(source) if f.endswith(".j2")])
            print(f"  {dest} ({j2_count} templates)")

    return template_dirs


def validate_template_directories(template_dirs: list[tuple[str, str]]) -> bool:
    """
    Validate that all template directories exist and contain .j2 files.

    Args:
        template_dirs: List of (source_path, dest_path) tuples

    Returns:
        True if all directories are valid, False otherwise
    """
    for source_path, dest_path in template_dirs:
        if not os.path.exists(source_path):
            print(f"ERROR: Template directory does not exist: {source_path}")
            return False

        j2_files = [f for f in os.listdir(source_path) if f.endswith(".j2")]
        if not j2_files:
            print(f"WARNING: No .j2 files found in: {source_path}")

    return True


if __name__ == "__main__":
    # Example usage when run as a script
    project_root = Path(__file__).parent.parent.parent  # Go up to project root

    print("Scanning for Jinja2 template directories...")
    template_dirs = get_jinja_template_data_files(project_root, verbose=True)

    print("\nPyInstaller data files configuration:")
    print("datas=[")
    for source, dest in template_dirs:
        print(f"    ('{source}', '{dest}'),")
    print("]")

    validation_result = (
        "PASSED" if validate_template_directories(template_dirs) else "FAILED"
    )
    print(f"\nValidation: {validation_result}")
