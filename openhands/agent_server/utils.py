import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, get_args, get_origin

from pydantic import BaseModel


def utc_now():
    """Return the current time in UTC format (Since datetime.utcnow is deprecated)"""
    return datetime.now(UTC)


def update_with_config_var[T: BaseModel](model: T, prefix: str = "") -> T:
    """Create a new Pydantic model instance with values overridden from env vars.

    Supports recursive parsing of nested fields and lists with indices.
    Environment variables use UPPER_CASE with underscores as delimiters.

    Examples:
        WEBHOOKS_0_BASE_URL -> webhooks[0].base_url
        WEBHOOKS_0_HEADERS_AUTH -> webhooks[0].headers["AUTH"]
        WEBHOOKS_1_EVENT_BUFFER_SIZE -> webhooks[1].event_buffer_size
        SESSION_API_KEYS -> session_api_keys (comma-separated list)
        ENABLE_VSCODE -> enable_vscode

    Args:
        model: The Pydantic model instance to update
        prefix: Optional prefix for environment variables (e.g., "APP_")

    Returns:
        A new instance of the same model type with environment variable overrides
    """
    # Get the model's current data
    model_data = model.model_dump()

    # Build a mapping of all possible environment variable patterns
    env_updates = _parse_environment_variables(model.__class__, prefix)

    # Merge the environment updates with the existing model data
    merged_data = _deep_merge(model_data, env_updates)

    # Create and return a new instance
    try:
        return model.__class__(**merged_data)
    except Exception:
        # If validation fails, return the original model
        # This handles cases where environment variables have invalid values
        return model


def _parse_environment_variables(
    model_class: type[BaseModel], prefix: str = ""
) -> dict[str, Any]:
    """Parse environment variables into a nested dictionary structure.

    Args:
        model_class: The Pydantic model class to parse environment variables for
        prefix: Optional prefix for environment variables

    Returns:
        A nested dictionary with parsed environment variable values
    """
    env_updates = {}

    # Get all environment variables
    # Common system environment variables to ignore (when no prefix is used)
    # Only include variables that are very unlikely to be field names
    system_env_vars = {
        "PATH",
        "HOME",
        "USER",
        "SHELL",
        "TERM",
        "PWD",
        "OLDPWD",
        "LANG",
        "LC_ALL",
        "PYTHONPATH",
        "VIRTUAL_ENV",
        "CONDA_DEFAULT_ENV",
        "PS1",
        "PS2",
        "IFS",
        "TMPDIR",
        "TMP",
        "TEMP",
        "EDITOR",
        "PAGER",
        "BROWSER",
        "DISPLAY",
        "SSH_CLIENT",
        "SSH_CONNECTION",
        "SSH_TTY",
        "HOSTNAME",
        "HOSTTYPE",
        "MACHTYPE",
        "OSTYPE",
        "SHLVL",
        "LOGNAME",
        "MAIL",
        "MAILCHECK",
    }

    for env_var, env_value in os.environ.items():
        # Skip None values, but allow empty strings (they might be boolean False)
        if env_value is None:
            continue

        # Check if the environment variable matches the prefix
        if prefix:
            if not env_var.startswith(prefix):
                continue
            # Remove the prefix for parsing
            env_var_for_parsing = env_var[len(prefix) :]
        else:
            # Skip common system environment variables when no prefix is used
            if env_var in system_env_vars:
                continue
            env_var_for_parsing = env_var

        # Try to parse this environment variable as a field path
        parsed_path = _parse_env_var_path(env_var_for_parsing, model_class)
        if parsed_path:
            _set_nested_value(env_updates, parsed_path, env_value)

    return env_updates


def _parse_env_var_path(
    env_var: str, model_class: type[BaseModel]
) -> list[str | int] | None:
    """Parse an environment variable name into a field path.

    Args:
        env_var: Environment variable name (e.g., "WEBHOOKS_0_BASE_URL")
        model_class: The root model class

    Returns:
        A list representing the path to the field, or None if not valid
        Example: ["webhooks", 0, "base_url"]
    """
    parts = env_var.split("_")

    # Try different ways to group the parts to handle field names with underscores
    # First try the parts as-is
    result = _match_field_path(parts, model_class)
    if result:
        return result

    # If that doesn't work, try combining parts to match field names with underscores
    # For example, SIMPLE_FIELD should match simple_field
    for i in range(1, len(parts) + 1):
        # Try combining the first i parts with underscores
        combined_first = "_".join(parts[:i])
        remaining_parts = parts[i:]
        test_parts = [combined_first] + remaining_parts
        result = _match_field_path(test_parts, model_class)
        if result:
            return result

    return None


def _match_field_path(
    parts: list[str], model_class: type[BaseModel], path: list[str | int] | None = None
) -> list[str | int] | None:
    """Recursively match field path parts against a model structure.

    Args:
        parts: Remaining parts of the environment variable name
        model_class: Current model class being examined
        path: Current path being built

    Returns:
        Complete field path if valid, None otherwise
    """
    if path is None:
        path = []

    if not parts:
        return path

    current_part = parts[0]
    remaining_parts = parts[1:]

    # Check if this part matches a field in the current model
    model_fields = model_class.model_fields

    # First try direct field matching
    for field_name, field_info in model_fields.items():
        if field_name.upper() == current_part.upper():
            new_path = path + [field_name]

            # If no more parts, we found a complete match
            if not remaining_parts:
                return new_path

            # Get the field type to continue matching
            field_type = field_info.annotation

            # Handle list types
            if get_origin(field_type) is list:
                list_item_type = get_args(field_type)[0]

                # Next part should be a numeric index
                if remaining_parts and remaining_parts[0].isdigit():
                    index = int(remaining_parts[0])
                    index_path = new_path + [index]

                    # If no more parts after index, we found a match
                    if len(remaining_parts) == 1:
                        return index_path

                    # Continue matching with the list item type
                    if (
                        hasattr(list_item_type, "model_fields")
                        and isinstance(list_item_type, type)
                        and issubclass(list_item_type, BaseModel)
                    ):
                        return _match_field_path(
                            remaining_parts[1:], list_item_type, index_path
                        )

            # Handle nested model types
            elif (
                hasattr(field_type, "model_fields")
                and isinstance(field_type, type)
                and issubclass(field_type, BaseModel)
            ):
                return _match_field_path(remaining_parts, field_type, new_path)

            # Handle dict types (for headers, etc.)
            elif get_origin(field_type) is dict:
                # All remaining parts form the dictionary key
                if remaining_parts:
                    dict_key = "_".join(remaining_parts)
                    dict_path = new_path + [dict_key]
                    return dict_path

            # For simple types, we should have no remaining parts
            elif not remaining_parts:
                return new_path

    # If direct matching failed, try combining parts to match field names with
    # underscores
    if len(parts) > 1:
        for i in range(2, len(parts) + 1):
            # Try combining the first i parts with underscores
            combined_field = "_".join(parts[:i]).lower()
            remaining_after_combined = parts[i:]

            # Check if this combined field exists
            for field_name, field_info in model_fields.items():
                if field_name.lower() == combined_field:
                    new_path = path + [field_name]

                    # If no more parts, we found a complete match
                    if not remaining_after_combined:
                        return new_path

                    # Get the field type to continue matching
                    field_type = field_info.annotation

                    # Handle dict types (for headers, etc.)
                    if get_origin(field_type) is dict:
                        # All remaining parts form the dictionary key
                        dict_key = "_".join(remaining_after_combined).upper()
                        dict_path = new_path + [dict_key]
                        return dict_path

                    # For simple types, we should have no remaining parts
                    elif not remaining_after_combined:
                        return new_path

    return None


def _set_nested_value(data: dict[str, Any], path: list[str | int], value: str) -> None:
    """Set a value in a nested dictionary structure using a path.

    Args:
        data: The dictionary to update
        path: List of keys/indices representing the path
        value: The string value to set (will be parsed based on context)
    """
    current: Any = data

    for i, key in enumerate(path[:-1]):
        if isinstance(key, int):
            # Handle list index
            if not isinstance(current, list):
                # Convert to list if needed
                current = []
                # Set this list back in the parent
                parent_key = path[i - 1] if i > 0 else None
                if parent_key is not None:
                    _set_in_parent(data, path[:i], current)

            # Extend list if necessary
            while len(current) <= key:
                # Create a default dictionary with empty strings for common required
                # fields
                # This handles cases like WebhookSpec where base_url is required
                default_item = {"base_url": ""} if "webhooks" in str(path[:i]) else {}
                current.append(default_item)

            current = current[key]
        else:
            # Handle dictionary key
            if not isinstance(current, dict):
                current = {}
            if key not in current:
                # Determine if next key is an index (list) or string (dict)
                next_key = path[i + 1]
                current[key] = [] if isinstance(next_key, int) else {}

            current = current[key]

    # Set the final value
    final_key = path[-1]
    parsed_value = _parse_env_value(value, final_key)

    if isinstance(final_key, int):
        # Handle list index
        if not isinstance(current, list):
            current = []
        while len(current) <= final_key:
            current.append(None)
        current[final_key] = parsed_value
    else:
        # Handle dictionary key
        if not isinstance(current, dict):
            current = {}
        current[final_key] = parsed_value


def _set_in_parent(data: dict[str, Any], path: list[str | int], value: Any) -> None:
    """Set a value in a nested structure at the given path."""
    current: Any = data
    for key in path[:-1]:
        if isinstance(key, int):
            current = current[key]
        else:
            current = current[key]

    final_key = path[-1]
    if isinstance(final_key, int):
        current[final_key] = value
    else:
        current[final_key] = value


def _parse_env_value(env_value: str, field_key: str | int) -> Any:
    """Parse environment variable value based on context.

    Args:
        env_value: The string value from the environment variable
        field_key: The field name or index being set

    Returns:
        Parsed value with appropriate type
    """
    # Handle boolean values
    boolean_field_names = (
        "enabled",
        "disabled",
        "active",
        "debug",
        "verbose",
        "force",
        "dry_run",
    )
    if env_value.lower() in (
        "true",
        "false",
        "1",
        "0",
        "yes",
        "no",
        "on",
        "off",
        "",
    ) or (
        isinstance(field_key, str)
        and any(name in field_key.lower() for name in boolean_field_names)
    ):
        return env_value.lower() in ("true", "1", "yes", "on")

    # Handle numeric values
    if env_value.isdigit():
        return int(env_value)

    # Try to parse as float
    try:
        if "." in env_value:
            return float(env_value)
    except ValueError:
        pass

    # Handle comma-separated lists (only for fields that end with 's' and contain
    # commas)
    if isinstance(field_key, str) and field_key.endswith("s"):
        if "," in env_value:
            return env_value.split(",")
        elif env_value and field_key.lower() in ("tags", "items", "keys", "values"):
            # Only treat as single-item list for known list field names
            return [env_value]
        elif not env_value and field_key.lower() in ("tags", "items", "keys", "values"):
            # Empty string becomes empty list for known list fields
            return []

    # Handle Path objects
    if isinstance(field_key, str) and "path" in field_key.lower():
        return Path(env_value)

    # Default to string
    return env_value


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries, with updates taking precedence.

    Args:
        base: Base dictionary
        updates: Updates to apply

    Returns:
        Merged dictionary
    """
    result = base.copy()

    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        elif (
            key in result and isinstance(result[key], list) and isinstance(value, list)
        ):
            # For lists, we need to merge by index
            merged_list = result[key].copy()
            for i, item in enumerate(value):
                if i < len(merged_list):
                    if isinstance(merged_list[i], dict) and isinstance(item, dict):
                        merged_list[i] = _deep_merge(merged_list[i], item)
                    else:
                        merged_list[i] = item
                else:
                    merged_list.append(item)
            result[key] = merged_list
        else:
            result[key] = value

    return result
