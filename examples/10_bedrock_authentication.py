"""
Example demonstrating AWS Bedrock authentication with OpenHands SDK.

This example shows how to use AWS Bedrock models with different authentication methods:
1. Using IAM roles (no API key needed)
2. Using AWS credentials (access key + secret key)
3. Handling empty API keys properly

The SDK automatically converts empty API keys to None, allowing boto3 to use
alternative authentication methods like IAM roles, environment variables, etc.
"""

import os
from pydantic import SecretStr

from openhands.sdk import LLM, get_logger

logger = get_logger(__name__)


def example_bedrock_with_iam_role():
    """Example using IAM role authentication (no API key needed)."""
    print("=== Example 1: Bedrock with IAM Role Authentication ===")
    
    # When using IAM roles, you don't need an API key
    # The SDK will automatically set empty API keys to None
    llm = LLM(
        model="bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
        api_key=None,  # or SecretStr("") - both work the same way
        aws_region_name="us-east-1"
    )
    
    print(f"Model: {llm.model}")
    print(f"API Key: {llm.api_key}")  # Should be None
    print(f"AWS Region: {llm.aws_region_name}")
    print("✓ Ready to use IAM role authentication")
    print()


def example_bedrock_with_aws_credentials():
    """Example using explicit AWS credentials."""
    print("=== Example 2: Bedrock with AWS Credentials ===")
    
    # You can also provide explicit AWS credentials
    llm = LLM(
        model="bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
        api_key=None,
        aws_access_key_id=SecretStr("your-access-key-id"),
        aws_secret_access_key=SecretStr("your-secret-access-key"),
        aws_region_name="us-west-2"
    )
    
    print(f"Model: {llm.model}")
    print(f"API Key: {llm.api_key}")  # Should be None
    print(f"AWS Region: {llm.aws_region_name}")
    print("✓ Ready to use explicit AWS credentials")
    print()


def example_empty_api_key_handling():
    """Example showing how empty API keys are handled."""
    print("=== Example 3: Empty API Key Handling ===")
    
    # These all result in the same behavior - API key is set to None
    examples = [
        ("None", None),
        ("Empty SecretStr", SecretStr("")),
        ("Whitespace SecretStr", SecretStr("   \t\n  ")),
    ]
    
    for description, api_key in examples:
        llm = LLM(
            model="bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
            api_key=api_key,
            aws_region_name="us-east-1"
        )
        print(f"{description}: API key is {llm.api_key}")
    
    print("✓ All empty API keys are converted to None")
    print()


def example_model_features():
    """Example showing Bedrock model features."""
    print("=== Example 4: Bedrock Model Features ===")
    
    from openhands.sdk.llm.utils.model_features import get_features
    
    bedrock_models = [
        "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
        "bedrock/anthropic.claude-3-7-sonnet-20250219-v1:0",
        "bedrock/anthropic.claude-3-haiku-20240307-v1:0",
    ]
    
    for model in bedrock_models:
        features = get_features(model)
        print(f"Model: {model}")
        print(f"  Function Calling: {features.supports_function_calling}")
        print(f"  Prompt Caching: {features.supports_prompt_cache}")
        print(f"  Reasoning Effort: {features.supports_reasoning_effort}")
        print(f"  Stop Words: {features.supports_stop_words}")
        print()


if __name__ == "__main__":
    print("AWS Bedrock Authentication Examples")
    print("=" * 50)
    print()
    
    example_bedrock_with_iam_role()
    example_bedrock_with_aws_credentials()
    example_empty_api_key_handling()
    example_model_features()
    
    print("Note: These examples show configuration only.")
    print("To actually make API calls, you need valid AWS credentials configured.")