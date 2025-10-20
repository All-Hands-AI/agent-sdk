#!/usr/bin/env python3
"""CLI tool to generate .env files from Pydantic models or JSON schemas."""

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict

from openhands.agent_server.schema_to_env import generate_env_from_model, generate_env_from_schema


def import_model_from_string(model_path: str):
    """Import a Pydantic model from a module path string.
    
    Args:
        model_path: String in format "module.path:ClassName"
        
    Returns:
        The imported model class
    """
    if ":" not in model_path:
        raise ValueError("Model path must be in format 'module.path:ClassName'")
    
    module_path, class_name = model_path.split(":", 1)
    
    try:
        module = importlib.import_module(module_path)
        model_class = getattr(module, class_name)
        return model_class
    except ImportError as e:
        raise ImportError(f"Could not import module '{module_path}': {e}")
    except AttributeError as e:
        raise AttributeError(f"Could not find class '{class_name}' in module '{module_path}': {e}")


def load_json_schema(schema_path: str) -> Dict[str, Any]:
    """Load a JSON schema from a file.
    
    Args:
        schema_path: Path to the JSON schema file
        
    Returns:
        The loaded schema as a dictionary
    """
    try:
        with open(schema_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in schema file: {e}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate .env files from Pydantic models or JSON schemas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate from Pydantic model
  python -m openhands.agent_server.cli_schema_to_env \\
    --model "openhands.agent_server.config:Config" \\
    --prefix "OH" \\
    --output config.env

  # Generate from JSON schema file
  python -m openhands.agent_server.cli_schema_to_env \\
    --schema schema.json \\
    --prefix "APP" \\
    --output app.env

  # Print to stdout
  python -m openhands.agent_server.cli_schema_to_env \\
    --model "mymodule:MyModel" \\
    --prefix "MY"
        """
    )
    
    # Input source (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--model", "-m",
        help="Pydantic model in format 'module.path:ClassName'"
    )
    input_group.add_argument(
        "--schema", "-s",
        help="Path to JSON schema file"
    )
    
    # Configuration
    parser.add_argument(
        "--prefix", "-p",
        default="APP",
        help="Environment variable prefix (default: APP)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: print to stdout)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    try:
        # Generate the .env content
        if args.model:
            if args.verbose:
                print(f"Loading Pydantic model: {args.model}", file=sys.stderr)
            model_class = import_model_from_string(args.model)
            env_content = generate_env_from_model(model_class, args.prefix)
        else:
            if args.verbose:
                print(f"Loading JSON schema: {args.schema}", file=sys.stderr)
            schema = load_json_schema(args.schema)
            env_content = generate_env_from_schema(schema, args.prefix)
        
        # Output the result
        if args.output:
            output_path = Path(args.output)
            if args.verbose:
                print(f"Writing to: {output_path}", file=sys.stderr)
            output_path.write_text(env_content)
            print(f"Generated .env file: {output_path}")
        else:
            print(env_content)
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()