# prompt_utils.py
import os
import re
import sys
from functools import lru_cache

from jinja2 import (
    Environment,
    FileSystemBytecodeCache,
    FileSystemLoader,
    Template,
    TemplateNotFound,
)
from platformdirs import user_cache_dir


def refine(text: str) -> str:
    if sys.platform == "win32":
        text = re.sub(
            r"\bexecute_bash\b", "execute_powershell", text, flags=re.IGNORECASE
        )
        text = re.sub(
            r"(?<!execute_)(?<!_)\bbash\b", "powershell", text, flags=re.IGNORECASE
        )
    return text


@lru_cache(maxsize=64)
def _get_env(prompt_dir: str) -> Environment:
    if not prompt_dir:
        raise ValueError("prompt_dir is required")

    # Use a safe per-user cache directory for bytecode cache
    # This avoids permission issues with read-only prompt directories
    bytecode_cache = None
    try:
        cache_root = user_cache_dir("openhands", "openhands-ai")
        cache_folder = os.path.join(cache_root, "jinja_cache")
        os.makedirs(cache_folder, exist_ok=True)
        bytecode_cache = FileSystemBytecodeCache(directory=cache_folder)
    except OSError:
        # If we can't create the cache directory, disable caching
        # This allows the code to work in read-only environments
        bytecode_cache = None

    env = Environment(
        loader=FileSystemLoader(prompt_dir),
        bytecode_cache=bytecode_cache,
        autoescape=False,
    )
    # Optional: expose refine as a filter so templates can use {{ text|refine }}
    env.filters["refine"] = refine
    return env


@lru_cache(maxsize=256)
def _get_template(prompt_dir: str, template_name: str) -> Template:
    env = _get_env(prompt_dir)
    try:
        return env.get_template(template_name)
    except TemplateNotFound as e:
        # Only map TemplateNotFound to FileNotFoundError
        raise FileNotFoundError(
            f"Prompt file {os.path.join(prompt_dir, template_name)} not found"
        ) from e
    # Other exceptions (permission errors, syntax errors, etc.) are re-raised as-is


def render_template(prompt_dir: str, template_name: str, **ctx) -> str:
    """Render a Jinja2 template.

    Args:
        prompt_dir: The base directory for relative template paths.
        template_name: The template filename. Can be either:
            - A relative filename (e.g., "system_prompt.j2") loaded from prompt_dir
            - An absolute path (e.g., "/path/to/custom_prompt.j2")
        **ctx: Template context variables.

    Returns:
        Rendered template string.

    Raises:
        FileNotFoundError: If the template file cannot be found.
    """
    # If template_name is an absolute path, extract directory and filename
    if os.path.isabs(template_name):
        # Check if the file exists before trying to load it
        if not os.path.isfile(template_name):
            raise FileNotFoundError(f"Prompt file {template_name} not found")
        actual_dir = os.path.dirname(template_name)
        actual_filename = os.path.basename(template_name)
        tpl = _get_template(actual_dir, actual_filename)
    else:
        tpl = _get_template(prompt_dir, template_name)
    return refine(tpl.render(**ctx).strip())
