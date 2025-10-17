# Security Policy Configuration Example

This directory contains an example demonstrating how to configure custom security policies for OpenHands agents.

## Files

- `configurable_security_policy.py` - Shows how to use default and custom security policy templates
- `custom_policy.j2` - Example custom security policy template

## Usage

The security policy system allows you to customize the security guidelines that are included in the agent's system prompt. This is useful for:

- Implementing organization-specific security requirements
- Adding compliance guidelines
- Customizing security behavior for different environments
- Providing context-specific security instructions

## Configuration

You can specify a custom security policy by setting the `security_policy_filename` parameter when creating an agent:

```python
from openhands.sdk import Agent, LLM
from pydantic import SecretStr

agent = Agent(
    llm=LLM(
        model="gpt-4",
        api_key=SecretStr("your-api-key"),
        base_url="https://api.openai.com/v1",
    ),
    security_policy_filename="custom_security_policy.j2",
)
```

## Path Resolution

The system supports both relative and absolute paths for the security policy filename:

- **Relative paths**: Looked up within the prompt directory (default behavior)
- **Absolute paths**: Used directly from the filesystem for centralized policy management

The security policy template will be included in the system prompt using Jinja2 templating.

## Running the Example

```bash
python configurable_security_policy.py
```