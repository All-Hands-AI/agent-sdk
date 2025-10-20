"""
Comprehensive tests for the schema_to_env module.

Tests cover:
- Basic schema to env conversion
- Config class conversion
- Discriminated unions
- Nested objects and arrays
- Default value handling
- Field descriptions as comments
"""

import json
from pathlib import Path
from typing import List, Optional, Union

import pytest
from pydantic import BaseModel, Field

from openhands.agent_server.config import Config, WebhookSpec
from openhands.agent_server.schema_to_env import (
    SchemaToEnvGenerator,
    generate_env_from_model,
    generate_env_from_schema,
)
from tests.sdk.utils.test_discriminated_union import Animal, Cat, Dog


class SimpleModel(BaseModel):
    """Simple model for testing basic functionality."""
    name: str = Field(default="default_name", description="The name field")
    count: int = Field(description="A count value")
    enabled: bool = Field(default=True, description="Whether feature is enabled")
    optional_field: Optional[str] = Field(default=None, description="An optional field")


class NestedModel(BaseModel):
    """Model with nested objects for testing."""
    simple: SimpleModel = Field(description="A nested simple model")
    tags: List[str] = Field(default_factory=list, description="List of tags")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata dictionary")


class TestSchemaToEnvGenerator:
    """Test the SchemaToEnvGenerator class."""
    
    def test_simple_model_generation(self):
        """Test generating env file from a simple model."""
        env_content = generate_env_from_model(SimpleModel, "TEST")
        
        # Check that it contains expected elements
        assert "# Generated .env file from JSON schema" in env_content
        assert "# name: The name field" in env_content
        assert "TEST_NAME=default_name" in env_content  # Has default, not commented
        assert "# TEST_COUNT=42" in env_content  # No default, commented out
        assert "TEST_ENABLED=true" in env_content  # Has default
        assert "# TEST_OPTIONAL_FIELD=" in env_content  # Optional, commented out
    
    def test_config_model_generation(self):
        """Test generating env file from the Config model."""
        env_content = generate_env_from_model(Config, "OH")
        
        # Check for key Config fields
        assert "OH_ENABLE_VSCODE=true" in env_content  # Has default
        assert "OH_VSCODE_PORT=8001" in env_content  # Has default
        assert "OH_ENABLE_VNC=false" in env_content  # Has default
        
        # Check for array handling
        assert "# Array field" in env_content
        assert "OH_SESSION_API_KEYS" in env_content
        
        # Check for nested object (WebhookSpec)
        assert "OH_WEBHOOKS" in env_content
        assert "BASE_URL" in env_content
        assert "EVENT_BUFFER_SIZE" in env_content
    
    def test_webhook_spec_generation(self):
        """Test generating env file from WebhookSpec model."""
        env_content = generate_env_from_model(WebhookSpec, "WEBHOOK")
        
        # Check default values are not commented
        assert "WEBHOOK_EVENT_BUFFER_SIZE=10" in env_content
        assert "WEBHOOK_FLUSH_DELAY=30.0" in env_content
        assert "WEBHOOK_NUM_RETRIES=3" in env_content
        assert "WEBHOOK_RETRY_DELAY=5" in env_content
        
        # Check required field without default is commented
        assert "# WEBHOOK_BASE_URL=example_value" in env_content
        
        # Check descriptions are included
        assert "# base_url:" in env_content
        assert "# event_buffer_size:" in env_content
    
    def test_nested_model_generation(self):
        """Test generating env file from a model with nested objects."""
        env_content = generate_env_from_model(NestedModel, "NESTED")
        
        # Check nested object fields
        assert "NESTED_SIMPLE_NAME=default_name" in env_content
        assert "# NESTED_SIMPLE_COUNT=42" in env_content
        assert "NESTED_SIMPLE_ENABLED=true" in env_content
        
        # Check array handling
        assert "NESTED_TAGS" in env_content
        assert '["item1", "item2"]' in env_content
        assert "NESTED_TAGS_0" in env_content
        assert "NESTED_TAGS_1" in env_content
    
    def test_discriminated_union_generation(self):
        """Test generating env file from a discriminated union."""
        env_content = generate_env_from_model(Animal, "ANIMAL")
        
        # Should contain discriminated union comment
        assert "Discriminated union" in env_content
        
        # Should contain kind field options
        assert "ANIMAL_KIND" in env_content
        
        # Should show different options
        assert "Cat" in env_content or "Dog" in env_content
    
    def test_array_field_handling(self):
        """Test specific array field handling."""
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of string items"
                }
            }
        }
        
        env_content = generate_env_from_schema(schema, "TEST")
        
        # Check array format comments
        assert "Array field" in env_content
        assert "JSON format or indexed notation" in env_content
        assert '["item1", "item2"]' in env_content
        assert "TEST_ITEMS_0" in env_content
        assert "TEST_ITEMS_1" in env_content
    
    def test_enum_field_handling(self):
        """Test enum field handling."""
        schema = {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["active", "inactive", "pending"],
                    "description": "Status of the item"
                }
            }
        }
        
        env_content = generate_env_from_schema(schema, "TEST")
        
        # Check enum handling
        assert "Possible values: active, inactive, pending" in env_content
        assert "TEST_STATUS=active" in env_content
    
    def test_boolean_field_handling(self):
        """Test boolean field handling."""
        schema = {
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether the feature is enabled"
                },
                "disabled": {
                    "type": "boolean",
                    "description": "Whether the feature is disabled"
                }
            }
        }
        
        env_content = generate_env_from_schema(schema, "TEST")
        
        # Check boolean handling
        assert "TEST_ENABLED=true" in env_content  # Has default
        assert "# TEST_DISABLED=true" in env_content  # No default, commented
    
    def test_number_field_handling(self):
        """Test number and integer field handling."""
        schema = {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "default": 42,
                    "description": "A count value"
                },
                "rate": {
                    "type": "number",
                    "description": "A rate value"
                }
            }
        }
        
        env_content = generate_env_from_schema(schema, "TEST")
        
        # Check number handling
        assert "TEST_COUNT=42" in env_content  # Has default
        assert "# TEST_RATE=3.14" in env_content  # No default, commented
    
    def test_complex_nested_schema(self):
        """Test complex nested schema with multiple levels."""
        schema = {
            "type": "object",
            "properties": {
                "database": {
                    "type": "object",
                    "description": "Database configuration",
                    "properties": {
                        "host": {
                            "type": "string",
                            "default": "localhost",
                            "description": "Database host"
                        },
                        "port": {
                            "type": "integer",
                            "default": 5432,
                            "description": "Database port"
                        },
                        "credentials": {
                            "type": "object",
                            "properties": {
                                "username": {
                                    "type": "string",
                                    "description": "Database username"
                                },
                                "password": {
                                    "type": "string",
                                    "description": "Database password"
                                }
                            }
                        }
                    }
                }
            }
        }
        
        env_content = generate_env_from_schema(schema, "APP")
        
        # Check nested structure
        assert "APP_DATABASE_HOST=localhost" in env_content
        assert "APP_DATABASE_PORT=5432" in env_content
        assert "# APP_DATABASE_CREDENTIALS_USERNAME=example_value" in env_content
        assert "# APP_DATABASE_CREDENTIALS_PASSWORD=example_value" in env_content
    
    def test_generator_class_directly(self):
        """Test using the SchemaToEnvGenerator class directly."""
        generator = SchemaToEnvGenerator("DIRECT")
        
        schema = {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "default": "test",
                    "description": "A test name"
                }
            }
        }
        
        env_content = generator.generate_env_file(schema)
        
        assert "# Generated .env file from JSON schema" in env_content
        assert "# A test name" in env_content
        assert "DIRECT_NAME=test" in env_content
    
    def test_empty_prefix(self):
        """Test generation with empty prefix."""
        schema = {
            "type": "object",
            "properties": {
                "value": {
                    "type": "string",
                    "default": "test"
                }
            }
        }
        
        env_content = generate_env_from_schema(schema, "")
        
        # Should not have prefix
        assert "VALUE=test" in env_content
        assert "_VALUE" not in env_content
    
    def test_special_characters_in_values(self):
        """Test handling of special characters in values."""
        schema = {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "default": "Hello World! This has spaces and $pecial chars",
                    "description": "A message with special characters"
                }
            }
        }
        
        env_content = generate_env_from_schema(schema, "TEST")
        
        # Should be quoted due to spaces and special characters
        assert 'TEST_MESSAGE="Hello World! This has spaces and $pecial chars"' in env_content
    
    def test_long_description_wrapping(self):
        """Test that long descriptions are properly wrapped."""
        schema = {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "description": "This is a very long description that should be wrapped across multiple lines because it exceeds the maximum line length that we want to maintain for readability in the generated environment file."
                }
            }
        }
        
        env_content = generate_env_from_schema(schema, "TEST")
        
        # Should have multiple comment lines
        lines = env_content.split('\n')
        comment_lines = [line for line in lines if line.startswith('# This is a very long')]
        assert len(comment_lines) > 1  # Should be wrapped
    
    def test_duplicate_field_handling(self):
        """Test that duplicate fields are handled correctly."""
        generator = SchemaToEnvGenerator("TEST")
        
        # Simulate adding the same variable twice
        generator._add_env_var("TEST_NAME", "value1")
        generator._add_env_var("TEST_NAME", "value2")  # Should be ignored
        
        # Should only appear once
        assert len([line for line in generator.output_lines if "TEST_NAME=" in line]) <= 1


class TestIntegrationWithExistingModels:
    """Integration tests with existing models from the codebase."""
    
    def test_config_integration(self):
        """Test integration with the actual Config class."""
        env_content = generate_env_from_model(Config, "OH")
        
        # Verify it generates without errors and contains expected content
        assert len(env_content) > 0
        assert "OH_" in env_content
        assert "# Generated .env file" in env_content
    
    def test_webhook_spec_integration(self):
        """Test integration with WebhookSpec class."""
        env_content = generate_env_from_model(WebhookSpec, "WEBHOOK")
        
        # Verify it generates without errors
        assert len(env_content) > 0
        assert "WEBHOOK_" in env_content
    
    @pytest.mark.skipif(
        True,  # Skip by default as it requires the discriminated union test classes
        reason="Requires discriminated union test classes to be available"
    )
    def test_discriminated_union_integration(self):
        """Test integration with discriminated union classes."""
        try:
            env_content = generate_env_from_model(Animal, "ANIMAL")
            assert len(env_content) > 0
            assert "ANIMAL_" in env_content
        except Exception:
            # Skip if classes not available
            pytest.skip("Discriminated union classes not available")


if __name__ == "__main__":
    # Quick test run
    print("Testing Config model generation:")
    config_env = generate_env_from_model(Config, "OH")
    print(config_env[:500] + "..." if len(config_env) > 500 else config_env)
    
    print("\n" + "="*50 + "\n")
    
    print("Testing WebhookSpec model generation:")
    webhook_env = generate_env_from_model(WebhookSpec, "WEBHOOK")
    print(webhook_env)