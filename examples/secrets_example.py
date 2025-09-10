#!/usr/bin/env python3
"""Example demonstrating the secrets manager functionality."""

import os

from openhands.sdk.conversation.secrets_manager import SecretsManager


def main():
    """Demonstrate secrets manager usage."""
    # Create a secrets manager directly
    secrets_manager = SecretsManager()

    # Define secret retrieval functions
    def get_api_key(key: str) -> str:
        """Retrieve API key from environment or return a demo value."""
        return os.getenv(key, "sk-demo-api-key-12345")

    def get_database_password(key: str) -> str:
        """Retrieve database password from environment or return a demo value."""
        return os.getenv(key, "super-secret-password")

    # Add secrets to the manager
    secrets = {
        "API_KEY": get_api_key,
        "DB_PASSWORD": get_database_password,
    }
    secrets_manager.add_secrets(secrets)

    # Example bash commands that contain secret keys
    test_commands = [
        "curl -H 'Authorization: Bearer $API_KEY' https://api.example.com/data",
        "mysql -u user -p$DB_PASSWORD -h localhost mydb",
        "echo 'Using API_KEY and DB_PASSWORD for authentication'",
        "ls -la",  # No secrets here
    ]

    print("Secrets Manager Demo")
    print("=" * 50)
    print(f"Registered secrets: {secrets_manager.get_secret_keys()}")
    print()

    for i, command in enumerate(test_commands, 1):
        print(f"Example {i}:")
        print(f"Original:  {command}")

        # Find secrets in the command
        found_secrets = secrets_manager.find_secrets_in_text(command)
        if found_secrets:
            print(f"Found secrets: {found_secrets}")
            modified = secrets_manager.inject_secrets_into_bash_command(command)
            print(f"Modified:  {modified}")
        else:
            print("No secrets found - command unchanged")
        print()


if __name__ == "__main__":
    main()
