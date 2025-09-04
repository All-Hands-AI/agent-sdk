"""Tests for AgentContext template rendering functionality."""

import pytest

from openhands.sdk.context.agent_context import AgentContext
from openhands.sdk.context.microagents import (
    KnowledgeMicroagent,
    RepoMicroagent,
)
from openhands.sdk.context.microagents.types import MicroagentType
from openhands.sdk.llm import Message, TextContent


class TestAgentContext:
    """Test cases for AgentContext template rendering."""

    def test_agent_context_creation_empty(self):
        """Test creating an empty AgentContext."""
        context = AgentContext()
        assert context.microagents == []
        assert context.system_prompt_suffix is None
        assert context.user_message_suffix is None

    def test_agent_context_creation_with_suffix(self):
        """Test creating AgentContext with custom suffixes."""
        context = AgentContext(
            system_prompt_suffix="Custom system suffix",
            user_message_suffix="Custom user suffix",
        )
        assert context.system_prompt_suffix == "Custom system suffix"
        assert context.user_message_suffix == "Custom user suffix"

    def test_microagent_validation_duplicate_names(self):
        """Test that duplicate microagent names raise validation error."""
        repo_agent1 = RepoMicroagent(
            name="duplicate", content="First agent", type=MicroagentType.REPO_KNOWLEDGE
        )
        repo_agent2 = RepoMicroagent(
            name="duplicate", content="Second agent", type=MicroagentType.REPO_KNOWLEDGE
        )

        with pytest.raises(
            ValueError, match="Duplicate microagent name found: duplicate"
        ):
            AgentContext(microagents=[repo_agent1, repo_agent2])

    def test_get_system_message_suffix_no_repo_microagents(self):
        """Test system message suffix with no repo microagents."""
        knowledge_agent = KnowledgeMicroagent(
            name="test_knowledge",
            content="Some knowledge content",
            type=MicroagentType.KNOWLEDGE,
            triggers=["test"],
        )
        context = AgentContext(microagents=[knowledge_agent])
        result = context.get_system_message_suffix()
        assert result is None

    def test_get_system_message_suffix_with_repo_microagents(self):
        """Test system message suffix rendering with repo microagents."""
        repo_agent1 = RepoMicroagent(
            name="coding_standards",
            content="Follow PEP 8 style guidelines for Python code.",
            type=MicroagentType.REPO_KNOWLEDGE,
        )
        repo_agent2 = RepoMicroagent(
            name="testing_guidelines",
            content="Write comprehensive unit tests for all new features.",
            type=MicroagentType.REPO_KNOWLEDGE,
        )

        context = AgentContext(microagents=[repo_agent1, repo_agent2])
        result = context.get_system_message_suffix()

        expected_output = (
            "<REPO_CONTEXT>\n"
            "The following information has been included based on several files \
defined in user's repository.\n"
            "Please follow them while working.\n"
            "\n"
            "\n"
            "[BEGIN context from [coding_standards]]\n"
            "Follow PEP 8 style guidelines for Python code.\n"
            "[END Context]\n"
            "\n"
            "[BEGIN context from [testing_guidelines]]\n"
            "Write comprehensive unit tests for all new features.\n"
            "[END Context]\n"
            "\n"
            "</REPO_CONTEXT>"
        )

        assert result == expected_output

    def test_get_system_message_suffix_with_custom_suffix(self):
        """Test system message suffix with repo microagents and custom suffix."""
        repo_agent = RepoMicroagent(
            name="security_rules",
            content="Always validate user input and sanitize data.",
            type=MicroagentType.REPO_KNOWLEDGE,
        )

        context = AgentContext(
            microagents=[repo_agent],
            system_prompt_suffix="Additional custom instructions for the system.",
        )
        result = context.get_system_message_suffix()

        expected_output = (
            "<REPO_CONTEXT>\n"
            "The following information has been included based on several files \
defined in user's repository.\n"
            "Please follow them while working.\n"
            "\n"
            "\n"
            "[BEGIN context from [security_rules]]\n"
            "Always validate user input and sanitize data.\n"
            "[END Context]\n"
            "\n"
            "</REPO_CONTEXT>\n"
            "\n"
            "\n"
            "\n"
            "Additional custom instructions for the system."
        )

        assert result == expected_output

    def test_get_user_message_suffix_empty_query(self):
        """Test user message suffix with empty query."""
        knowledge_agent = KnowledgeMicroagent(
            name="python_tips",
            content="Use list comprehensions for better performance.",
            type=MicroagentType.KNOWLEDGE,
            triggers=["python", "performance"],
        )

        context = AgentContext(microagents=[knowledge_agent])
        empty_message = Message(role="user", content=[])
        result = context.get_user_message_suffix(empty_message, [])

        assert result is None

    def test_get_user_message_suffix_no_triggers(self):
        """Test user message suffix with no matching triggers."""
        knowledge_agent = KnowledgeMicroagent(
            name="python_tips",
            content="Use list comprehensions for better performance.",
            type=MicroagentType.KNOWLEDGE,
            triggers=["python", "performance"],
        )

        context = AgentContext(microagents=[knowledge_agent])
        user_message = Message(
            role="user", content=[TextContent(text="How do I write JavaScript code?")]
        )
        result = context.get_user_message_suffix(user_message, [])

        assert result is None

    def test_get_user_message_suffix_with_single_trigger(self):
        """Test user message suffix with single triggered microagent."""
        knowledge_agent = KnowledgeMicroagent(
            name="python_tips",
            content="Use list comprehensions for better performance.",
            type=MicroagentType.KNOWLEDGE,
            triggers=["python", "performance"],
        )

        context = AgentContext(microagents=[knowledge_agent])
        user_message = Message(
            role="user",
            content=[TextContent(text="How can I improve my Python code performance?")],
        )
        result = context.get_user_message_suffix(user_message, [])

        assert result is not None
        text_content, triggered_names = result

        expected_output = (
            "<EXTRA_INFO>\n"
            'The following information has been included based on a keyword match \
for "python".\n'
            "It may or may not be relevant to the user's request.\n"
            "\n"
            "Use list comprehensions for better performance.\n"
            "</EXTRA_INFO>"
        )

        assert text_content.text == expected_output
        assert triggered_names == ["python_tips"]

    def test_get_user_message_suffix_with_multiple_triggers(self):
        """Test user message suffix with multiple triggered microagents."""
        python_agent = KnowledgeMicroagent(
            name="python_best_practices",
            content="Follow PEP 8 and use type hints for better code quality.",
            type=MicroagentType.KNOWLEDGE,
            triggers=["python", "best practices"],
        )
        testing_agent = KnowledgeMicroagent(
            name="testing_framework",
            content="Use pytest for comprehensive testing with fixtures and \
parametrization.",
            type=MicroagentType.KNOWLEDGE,
            triggers=["testing", "pytest"],
        )

        context = AgentContext(microagents=[python_agent, testing_agent])
        user_message = Message(
            role="user",
            content=[
                TextContent(
                    text="I need help with Python testing using pytest framework."
                )
            ],
        )
        result = context.get_user_message_suffix(user_message, [])

        assert result is not None
        text_content, triggered_names = result

        expected_output = (
            "<EXTRA_INFO>\n"
            'The following information has been included based on a keyword match \
for "python".\n'
            "It may or may not be relevant to the user's request.\n"
            "\n"
            "Follow PEP 8 and use type hints for better code quality.\n"
            "</EXTRA_INFO>\n"
            "\n"
            "<EXTRA_INFO>\n"
            'The following information has been included based on a keyword match \
for "testing".\n'
            "It may or may not be relevant to the user's request.\n"
            "\n"
            "Use pytest for comprehensive testing with fixtures and \
parametrization.\n"
            "</EXTRA_INFO>"
        )

        assert text_content.text == expected_output
        assert set(triggered_names) == {"python_best_practices", "testing_framework"}

    def test_get_user_message_suffix_skip_microagent_names(self):
        """Test user message suffix with skipped microagent names."""
        knowledge_agent = KnowledgeMicroagent(
            name="python_tips",
            content="Use list comprehensions for better performance.",
            type=MicroagentType.KNOWLEDGE,
            triggers=["python", "performance"],
        )

        context = AgentContext(microagents=[knowledge_agent])
        user_message = Message(
            role="user",
            content=[TextContent(text="How can I improve my Python code performance?")],
        )
        result = context.get_user_message_suffix(user_message, ["python_tips"])

        assert result is None

    def test_get_user_message_suffix_multiline_content(self):
        """Test user message suffix with multiline user content."""
        knowledge_agent = KnowledgeMicroagent(
            name="database_tips",
            content="Always use parameterized queries to prevent SQL injection \
attacks.",
            type=MicroagentType.KNOWLEDGE,
            triggers=["database", "sql"],
        )

        context = AgentContext(microagents=[knowledge_agent])
        user_message = Message(
            role="user",
            content=[
                TextContent(text="I'm working on a web application"),
                TextContent(text="that needs to connect to a database"),
                TextContent(text="and execute SQL queries safely"),
            ],
        )
        result = context.get_user_message_suffix(user_message, [])

        assert result is not None
        text_content, triggered_names = result

        expected_output = (
            "<EXTRA_INFO>\n"
            "The following information has been included based on a keyword match "
            'for "database".\n'
            "It may or may not be relevant to the user's request.\n"
            "\n"
            "Always use parameterized queries to prevent SQL injection attacks.\n"
            "</EXTRA_INFO>"
        )

        assert text_content.text == expected_output
        assert triggered_names == ["database_tips"]

    def test_mixed_microagent_types(self):
        """Test AgentContext with mixed microagent types."""
        repo_agent = RepoMicroagent(
            name="repo_standards",
            content="Use semantic versioning for releases.",
            type=MicroagentType.REPO_KNOWLEDGE,
        )
        knowledge_agent = KnowledgeMicroagent(
            name="git_tips",
            content="Use conventional commits for better history.",
            type=MicroagentType.KNOWLEDGE,
            triggers=["git", "commit"],
        )

        context = AgentContext(microagents=[repo_agent, knowledge_agent])

        # Test system message suffix (should only include repo microagents)
        system_result = context.get_system_message_suffix()
        expected_system_output = (
            "<REPO_CONTEXT>\n"
            "The following information has been included based on several files \
defined in user's repository.\n"
            "Please follow them while working.\n"
            "\n"
            "\n"
            "[BEGIN context from [repo_standards]]\n"
            "Use semantic versioning for releases.\n"
            "[END Context]\n"
            "\n"
            "</REPO_CONTEXT>"
        )
        assert system_result == expected_system_output

        # Test user message suffix (should only include knowledge microagents)
        user_message = Message(
            role="user",
            content=[TextContent(text="How should I format my git commits?")],
        )
        user_result = context.get_user_message_suffix(user_message, [])

        assert user_result is not None
        text_content, triggered_names = user_result

        expected_user_output = (
            "<EXTRA_INFO>\n"
            'The following information has been included based on a keyword match \
for "git".\n'
            "It may or may not be relevant to the user's request.\n"
            "\n"
            "Use conventional commits for better history.\n"
            "</EXTRA_INFO>"
        )

        assert text_content.text == expected_user_output
        assert triggered_names == ["git_tips"]

    def test_case_insensitive_trigger_matching(self):
        """Test that trigger matching is case insensitive."""
        knowledge_agent = KnowledgeMicroagent(
            name="docker_tips",
            content="Use multi-stage builds to reduce image size.",
            type=MicroagentType.KNOWLEDGE,
            triggers=["docker", "container"],
        )

        context = AgentContext(microagents=[knowledge_agent])
        user_message = Message(
            role="user",
            content=[TextContent(text="I need help with DOCKER containerization.")],
        )
        result = context.get_user_message_suffix(user_message, [])

        assert result is not None
        text_content, triggered_names = result

        expected_output = (
            "<EXTRA_INFO>\n"
            'The following information has been included based on a keyword match \
for "docker".\n'
            "It may or may not be relevant to the user's request.\n"
            "\n"
            "Use multi-stage builds to reduce image size.\n"
            "</EXTRA_INFO>"
        )

        assert text_content.text == expected_output
        assert triggered_names == ["docker_tips"]

    def test_special_characters_in_content(self):
        """Test template rendering with special characters in content."""
        repo_agent = RepoMicroagent(
            name="special_chars",
            content="Use {{ curly braces }} and <angle brackets> carefully in \
templates.",
            type=MicroagentType.REPO_KNOWLEDGE,
        )

        context = AgentContext(microagents=[repo_agent])
        result = context.get_system_message_suffix()

        expected_output = (
            "<REPO_CONTEXT>\n"
            "The following information has been included based on several files \
defined in user's repository.\n"
            "Please follow them while working.\n"
            "\n"
            "\n"
            "[BEGIN context from [special_chars]]\n"
            "Use {{ curly braces }} and <angle brackets> carefully in \
templates.\n"
            "[END Context]\n"
            "\n"
            "</REPO_CONTEXT>"
        )

        assert result == expected_output

    def test_empty_microagent_content(self):
        """Test template rendering with empty microagent content."""
        repo_agent = RepoMicroagent(
            name="empty_content", content="", type=MicroagentType.REPO_KNOWLEDGE
        )

        context = AgentContext(microagents=[repo_agent])
        result = context.get_system_message_suffix()

        expected_output = (
            "<REPO_CONTEXT>\n"
            "The following information has been included based on several files \
defined in user's repository.\n"
            "Please follow them while working.\n"
            "\n"
            "\n"
            "[BEGIN context from [empty_content]]\n"
            "\n"
            "[END Context]\n"
            "\n"
            "</REPO_CONTEXT>"
        )

        assert result == expected_output
