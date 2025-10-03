"""Planning agent implementation with read-only tools."""

from openhands.sdk.agent.agent import Agent


class PlanningAgent(Agent):
    """A specialized agent for planning and analysis with read-only tools.

    The PlanningAgent is designed to analyze projects, understand requirements,
    and create detailed implementation plans without making any modifications
    to the codebase. It has access to:

    - Read-only file and directory viewing capabilities
    - Plan writing tool to output structured markdown plans
    - Task tracking for organizing planning activities
    - All standard read-only analysis tools

    This agent is ideal for the first phase of a two-stage workflow where
    planning happens first, followed by implementation by a standard agent.
    """

    def __init__(self, **kwargs):
        """Initialize the PlanningAgent with specialized configuration."""
        # Set default system prompt for planning if not provided
        if "system_prompt_kwargs" not in kwargs:
            kwargs["system_prompt_kwargs"] = {}

        # Add planning-specific context
        kwargs["system_prompt_kwargs"].update(
            {
                "planning_mode": True,
                "read_only_mode": True,
            }
        )

        # Set default system prompt filename for planning
        if "system_prompt_filename" not in kwargs:
            kwargs["system_prompt_filename"] = "planning_system_prompt.j2"

        super().__init__(**kwargs)
