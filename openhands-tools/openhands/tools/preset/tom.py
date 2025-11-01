"""Tom agent preset configuration.

This preset creates an agent with Theory of Mind capabilities by including
the TomConsultTool alongside default tools.
"""

from openhands.sdk import Agent
from openhands.sdk.llm.llm import LLM
from openhands.sdk.logger import get_logger
from openhands.sdk.tool import Tool, register_tool
from openhands.tools.preset.default import get_default_tools, register_default_tools


logger = get_logger(__name__)


def register_tom_tools(enable_browser: bool = True) -> None:
    """Register Tom consultation tool and default tools."""
    # Register default tools first
    register_default_tools(enable_browser=enable_browser)

    # Register Tom tool
    from openhands.tools.tom_consult import TomConsultTool

    register_tool("TomConsultTool", TomConsultTool)
    logger.debug("Tool: TomConsultTool registered.")


def get_tom_tools(
    enable_browser: bool = True,
    tom_llm: LLM | None = None,
    enable_rag: bool = True,
) -> list[Tool]:
    """Get tool specifications for Tom-enabled agent.

    Args:
        enable_browser: Whether to include browser tools
        tom_llm: Optional separate LLM for Tom agent (defaults to main agent's LLM)
        enable_rag: Whether to enable RAG in Tom agent

    Returns:
        List of Tool specifications including TomConsultTool
    """
    register_tom_tools(enable_browser=enable_browser)

    # Get default tools
    tools = get_default_tools(enable_browser=enable_browser)

    # Add Tom consultation tool with parameters
    tom_params: dict[str, bool | str] = {
        "enable_rag": enable_rag,
    }

    if tom_llm is not None:
        tom_params["llm_model"] = tom_llm.model
        if tom_llm.api_key:
            tom_params["api_key"] = tom_llm.api_key.get_secret_value()
        if tom_llm.base_url:
            tom_params["api_base"] = tom_llm.base_url

    tools.append(Tool(name="TomConsultTool", params=tom_params))

    return tools


def get_tom_agent(
    llm: LLM,
    cli_mode: bool = True,
    enable_rag: bool = True,
    tom_llm: LLM | None = None,
) -> Agent:
    """Create an agent with Tom (Theory of Mind) consultation capabilities.

    This agent can consult a Tom agent for personalized guidance based on
    user modeling. The Tom agent helps understand vague instructions and
    suggests approaches tailored to user preferences.

    Args:
        llm: Language model for the main agent
        cli_mode: Whether running in CLI mode (disables browser tools)
        enable_rag: Whether to enable RAG in Tom agent
        tom_llm: Optional separate LLM for Tom agent (defaults to main agent's LLM)

    Returns:
        Agent instance with Tom consultation capabilities

    Example:
        ```python
        from openhands.sdk import LLM, Conversation
        from openhands.tools.preset import get_tom_agent
        from pydantic import SecretStr

        llm = LLM(model="gpt-4", api_key=SecretStr("key"))
        agent = get_tom_agent(llm, cli_mode=True)

        conversation = Conversation(agent=agent)
        conversation.send_message("Help me with this task")
        conversation.run()
        ```
    """
    enable_browser = not cli_mode

    # If no separate Tom LLM specified, use the main agent's LLM
    if tom_llm is None:
        tom_llm = llm

    tools = get_tom_tools(
        enable_browser=enable_browser,
        tom_llm=tom_llm,
        enable_rag=enable_rag,
    )

    agent = Agent(llm=llm, tools=tools)

    logger.info(f"Tom agent created with {len(tools)} tools")
    return agent
