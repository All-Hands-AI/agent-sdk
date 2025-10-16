"""Prompt template for TODO implementation."""

PROMPT = """You are an AI assistant helping to implement a TODO comment in a codebase.

TODO Details:
- File: {file_path}
- Line: {line_num}
- Description: {description}

Your task is to:
1. Analyze the TODO comment and understand what needs to be implemented
2. Create a feature branch for this implementation
3. Implement the functionality described in the TODO
4. Create a pull request with your changes

IMPORTANT - Creating the Pull Request:
- Use the `gh pr create` command to create the PR
- The GITHUB_TOKEN environment variable is available for authentication

Please make sure to:
- Create a descriptive branch name related to the TODO
- Fix the issue with clean code
- Include a test if needed, but not always necessary

The TODO comment is: {todo_text}

Please implement this TODO and create a pull request with your changes."""
