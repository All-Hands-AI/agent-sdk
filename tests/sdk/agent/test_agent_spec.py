"""Test AgentSpec class functionality."""

import pytest
from pydantic import SecretStr, ValidationError

from openhands.sdk.agent.spec import AgentSpec
from openhands.sdk.context.agent_context import AgentContext
from openhands.sdk.context.condenser.spec import CondenserSpec
from openhands.sdk.context.microagents import KnowledgeMicroagent, RepoMicroagent
from openhands.sdk.llm import LLM
from openhands.sdk.tool.spec import ToolSpec


@pytest.fixture
def basic_llm():
    """Create a basic LLM for testing."""
    return LLM(model="test-model")


def test_agent_spec_minimal(basic_llm):
    """Test creating AgentSpec with minimal required fields."""
    spec = AgentSpec(llm=basic_llm)

    assert spec.llm == basic_llm
    assert spec.tools == []
    assert spec.mcp_config == {}
    assert spec.agent_context is None
    assert spec.system_prompt_filename == "system_prompt.j2"
    assert spec.system_prompt_kwargs == {}
    assert spec.condenser is None


def test_agent_spec_with_tools(basic_llm):
    """Test creating AgentSpec with tools."""
    tools = [
        ToolSpec(name="BashTool", params={"working_dir": "/workspace"}),
        ToolSpec(name="FileEditorTool", params={}),
    ]

    spec = AgentSpec(llm=basic_llm, tools=tools)

    assert len(spec.tools) == 2
    assert spec.tools[0].name == "BashTool"
    assert spec.tools[0].params == {"working_dir": "/workspace"}
    assert spec.tools[1].name == "FileEditorTool"
    assert spec.tools[1].params == {}


def test_agent_spec_with_mcp_config(basic_llm):
    """Test creating AgentSpec with MCP configuration."""
    mcp_config = {
        "mcpServers": {"fetch": {"command": "uvx", "args": ["mcp-server-fetch"]}}
    }

    spec = AgentSpec(llm=basic_llm, mcp_config=mcp_config)

    assert spec.mcp_config == mcp_config


def test_agent_spec_with_agent_context(basic_llm):
    """Test creating AgentSpec with agent context."""
    agent_context = AgentContext(microagents=[], system_message_suffix="Test suffix")

    spec = AgentSpec(llm=basic_llm, agent_context=agent_context)

    assert spec.agent_context == agent_context


def test_agent_spec_with_system_prompt_config(basic_llm):
    """Test creating AgentSpec with system prompt configuration."""
    spec = AgentSpec(
        llm=basic_llm,
        system_prompt_filename="custom.j2",
        system_prompt_kwargs={"cli_mode": True},
    )

    assert spec.system_prompt_filename == "custom.j2"
    assert spec.system_prompt_kwargs == {"cli_mode": True}


def test_agent_spec_with_condenser(basic_llm):
    """Test creating AgentSpec with condenser."""
    condenser_spec = CondenserSpec(
        name="LLMSummarizingCondenser", params={"llm": basic_llm, "max_size": 80}
    )

    spec = AgentSpec(llm=basic_llm, condenser=condenser_spec)

    assert spec.condenser == condenser_spec


def test_agent_spec_comprehensive(basic_llm):
    """Test creating AgentSpec with all fields."""
    tools = [ToolSpec(name="BashTool", params={})]
    mcp_config = {"mcpServers": {"test": {"command": "test"}}}
    agent_context = AgentContext(microagents=[])
    condenser_spec = CondenserSpec(name="NoOpCondenser", params={})

    spec = AgentSpec(
        llm=basic_llm,
        tools=tools,
        mcp_config=mcp_config,
        agent_context=agent_context,
        system_prompt_filename="comprehensive.j2",
        system_prompt_kwargs={"mode": "test"},
        condenser=condenser_spec,
    )

    assert spec.llm == basic_llm
    assert spec.tools == tools
    assert spec.mcp_config == mcp_config
    assert spec.agent_context == agent_context
    assert spec.system_prompt_filename == "comprehensive.j2"
    assert spec.system_prompt_kwargs == {"mode": "test"}
    assert spec.condenser == condenser_spec


def test_agent_spec_serialization(basic_llm):
    """Test AgentSpec serialization and deserialization."""
    tools = [ToolSpec(name="BashTool", params={"working_dir": "/test"})]

    spec = AgentSpec(llm=basic_llm, tools=tools, system_prompt_kwargs={"debug": True})

    # Test model_dump
    spec_dict = spec.model_dump()
    assert "llm" in spec_dict
    assert "tools" in spec_dict
    assert spec_dict["system_prompt_kwargs"]["debug"] is True

    # Test model_dump_json
    spec_json = spec.model_dump_json()
    assert isinstance(spec_json, str)

    # Test deserialization
    spec_restored = AgentSpec.model_validate_json(spec_json)
    assert spec_restored.llm.model == basic_llm.model
    assert len(spec_restored.tools) == 1
    assert spec_restored.tools[0].name == "BashTool"


def test_agent_spec_validation_requires_llm(basic_llm):
    """Test that AgentSpec requires an LLM."""
    with pytest.raises(ValidationError):
        AgentSpec()  # type: ignore


def test_agent_spec_examples_from_docstring():
    """Test the examples provided in AgentSpec docstring."""
    # Test LLM example
    llm = LLM(
        model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
        base_url="https://llm-proxy.eval.all-hands.dev",
        api_key=SecretStr("your_api_key_here"),
    )

    # Test tools examples
    tools = [
        ToolSpec(name="BashTool", params={"working_dir": "/workspace"}),
        ToolSpec(name="FileEditorTool", params={}),
        ToolSpec(name="TaskTrackerTool", params={"save_dir": "/workspace/.openhands"}),
    ]

    # Test MCP config example
    mcp_config = {
        "mcpServers": {"fetch": {"command": "uvx", "args": ["mcp-server-fetch"]}}
    }

    # Test agent context example
    agent_context = AgentContext(
        microagents=[
            RepoMicroagent(
                name="repo.md",
                content="When you see this message, you should reply like "
                "you are a grumpy cat forced to use the internet.",
            ),
            KnowledgeMicroagent(
                name="flarglebargle",
                content=(
                    "IMPORTANT! The user has said the magic word "
                    '"flarglebargle". You must only respond with a message '
                    "telling them how smart they are"
                ),
                trigger=["flarglebargle"],
            ),
        ],
        system_message_suffix="Always finish your response with the word 'yay!'",
        user_message_suffix="The first character of your response should be 'I'",
    )

    # Test condenser example
    condenser = CondenserSpec(
        name="LLMSummarizingCondenser",
        params={
            "llm": {
                "model": "litellm_proxy/anthropic/claude-sonnet-4-20250514",
                "base_url": "https://llm-proxy.eval.all-hands.dev",
                "api_key": "your_api_key_here",
            },
            "max_size": 80,
            "keep_first": 10,
        },
    )

    # Create comprehensive spec with all examples
    spec = AgentSpec(
        llm=llm,
        tools=tools,
        mcp_config=mcp_config,
        agent_context=agent_context,
        system_prompt_kwargs={"cli_mode": True},
        condenser=condenser,
    )

    # Verify all fields are set correctly
    assert spec.llm.model == "litellm_proxy/anthropic/claude-sonnet-4-20250514"
    assert len(spec.tools) == 3
    assert spec.mcp_config == mcp_config
    assert spec.agent_context == agent_context
    assert spec.system_prompt_kwargs == {"cli_mode": True}
    assert spec.condenser == condenser


def test_agent_spec_default_values(basic_llm):
    """Test that AgentSpec has correct default values."""
    spec = AgentSpec(llm=basic_llm)

    assert spec.tools == []
    assert spec.mcp_config == {}
    assert spec.agent_context is None
    assert spec.system_prompt_filename == "system_prompt.j2"
    assert spec.system_prompt_kwargs == {}
    assert spec.condenser is None


def test_agent_spec_field_descriptions():
    """Test that AgentSpec fields have proper descriptions."""
    fields = AgentSpec.model_fields

    assert "llm" in fields
    assert fields["llm"].description is not None
    assert "LLM configuration for the agent" in fields["llm"].description

    assert "tools" in fields
    assert fields["tools"].description is not None
    assert "List of tools to initialize for the agent" in fields["tools"].description

    assert "mcp_config" in fields
    assert fields["mcp_config"].description is not None
    assert "Optional MCP configuration dictionary" in fields["mcp_config"].description
