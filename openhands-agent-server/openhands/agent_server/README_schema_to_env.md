# Schema to Environment Generator

This module provides functionality to generate sample `.env` files from JSON schemas or Pydantic models, serving as a complement to the existing environment parser.

## Features

- **JSON Schema Support**: Convert any JSON schema to a sample `.env` file
- **Pydantic Model Support**: Generate `.env` files directly from Pydantic models
- **Discriminated Unions**: Handle `oneOf` schemas with discriminator support
- **Default Value Handling**: Uncomment fields with defaults, comment fields without
- **Field Descriptions**: Use schema descriptions as comments for each field
- **Nested Objects**: Properly expand nested objects with prefixed environment variables
- **Array Support**: Handle arrays with both JSON and indexed notation options
- **Enum Support**: Show possible enum values as comments
- **CLI Tool**: Command-line interface for easy integration

## Usage

### Python API

```python
from openhands.agent_server.schema_to_env import generate_env_from_model, generate_env_from_schema

# From Pydantic model
from pydantic import BaseModel, Field

class DatabaseConfig(BaseModel):
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    name: str = Field(description="Database name")

env_content = generate_env_from_model(DatabaseConfig, "DB")
print(env_content)
```

Output:
```bash
# Generated .env file from JSON schema
# Uncommented values show defaults, commented values show available options

# host: Database host
DB_HOST=localhost
# port: Database port
DB_PORT=5432
# name: Database name
# DB_NAME=example_value
```

### From JSON Schema

```python
schema = {
    "type": "object",
    "properties": {
        "api_key": {
            "type": "string",
            "description": "API key for authentication"
        },
        "timeout": {
            "type": "integer",
            "default": 30,
            "description": "Request timeout in seconds"
        }
    }
}

env_content = generate_env_from_schema(schema, "API")
```

### Command Line Interface

```bash
# From JSON schema file
python -m openhands.agent_server.cli_schema_to_env --schema config.json --prefix MY_APP

# From Pydantic model
python -m openhands.agent_server.cli_schema_to_env --model 'mymodule:MyModel' --prefix MY_APP

# Save to file
python -m openhands.agent_server.cli_schema_to_env --schema config.json --prefix MY_APP --output .env.example
```

## Advanced Features

### Discriminated Unions

The generator handles discriminated unions (oneOf with discriminator) by showing all possible options:

```python
schema = {
    "type": "object",
    "properties": {
        "storage": {
            "oneOf": [
                {
                    "type": "object",
                    "properties": {
                        "type": {"const": "local"},
                        "path": {"type": "string", "default": "/tmp/storage"}
                    }
                },
                {
                    "type": "object", 
                    "properties": {
                        "type": {"const": "s3"},
                        "bucket": {"type": "string"},
                        "region": {"type": "string", "default": "us-east-1"}
                    }
                }
            ],
            "discriminator": {"propertyName": "type"}
        }
    }
}
```

Generates:
```bash
# storage: Storage configuration
# Discriminated union - choose one of the following options:
# Option 1: local
# STORAGE_STORAGE_TYPE=local
STORAGE_STORAGE_PATH=/tmp/storage
# Option 2: s3
# STORAGE_STORAGE_BUCKET=example_value
STORAGE_STORAGE_REGION=us-east-1
```

### Array Handling

Arrays are handled with both JSON and indexed notation options:

```bash
# tags: List of tags
# Array field - use JSON format or indexed notation (e.g., VAR_0, VAR_1)
TAGS="["tag1", "tag2"]"
# Or use indexed notation:
# TAGS_0=example_value
# TAGS_1=example_value
```

### Nested Objects

Nested objects are expanded with proper prefixing:

```python
class AppConfig(BaseModel):
    name: str = Field(default="MyApp")
    database: DatabaseConfig = Field(description="Database configuration")
```

Generates:
```bash
# name
APP_NAME=MyApp
# database: Database configuration
# host: Database host
APP_DATABASE_HOST=localhost
# port: Database port
APP_DATABASE_PORT=5432
```

## Integration with Existing Environment Parser

This generator complements the existing `env_parser.py` by providing the reverse functionality:

- `env_parser.py`: Parses environment variables into Pydantic models
- `schema_to_env.py`: Generates sample environment files from Pydantic models/schemas

Together, they provide a complete environment configuration workflow:

1. Define your configuration as Pydantic models
2. Generate sample `.env` files using `schema_to_env.py`
3. Parse actual environment variables using `env_parser.py`

## CLI Help

```bash
python -m openhands.agent_server.cli_schema_to_env --help
```

Shows all available options and usage examples.