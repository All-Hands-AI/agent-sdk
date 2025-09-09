import io
import re
from itertools import chain
from pathlib import Path
from typing import Any, ClassVar, Union, cast

import frontmatter
from fastmcp.mcp_config import MCPConfig
from pydantic import BaseModel, Field, field_validator, model_validator

from openhands.sdk.context.microagents.exceptions import MicroagentValidationError
from openhands.sdk.context.microagents.types import (
    InputMetadata,
    MicroagentType,
)
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


class BaseMicroagent(BaseModel):
    """Base class for all microagents."""

    name: str
    content: str
    source: str | None = Field(
        default=None,
        description=(
            "The source path or identifier of the microagent. "
            "When it is None, it is treated as a programmatically defined microagent."
        ),
    )
    type: MicroagentType = Field(..., description="The type of the microagent")

    PATH_TO_THIRD_PARTY_MICROAGENT_NAME: ClassVar[dict[str, str]] = {
        ".cursorrules": "cursorrules",
        "agents.md": "agents",
        "agent.md": "agents",
    }

    @classmethod
    def _handle_third_party(
        cls, path: Path, file_content: str
    ) -> Union["RepoMicroagent", None]:
        # Determine the agent name based on file type
        microagent_name = cls.PATH_TO_THIRD_PARTY_MICROAGENT_NAME.get(path.name.lower())

        # Create RepoMicroagent if we recognized the file type
        if microagent_name is not None:
            return RepoMicroagent(
                name=microagent_name,
                content=file_content,
                source=str(path),
                type=MicroagentType.REPO_KNOWLEDGE,
            )

        return None

    @classmethod
    def load(
        cls,
        path: Union[str, Path],
        microagent_dir: Path | None = None,
        file_content: str | None = None,
    ) -> "BaseMicroagent":
        """Load a microagent from a markdown file with frontmatter.

        The agent's name is derived from its path relative to the microagent_dir.
        """
        path = Path(path) if isinstance(path, str) else path

        # Calculate derived name from relative path if microagent_dir is provided
        microagent_name = None
        if microagent_dir is not None:
            # Special handling for files which are not in microagent_dir
            microagent_name = cls.PATH_TO_THIRD_PARTY_MICROAGENT_NAME.get(
                path.name.lower()
            ) or str(path.relative_to(microagent_dir).with_suffix(""))
        else:
            microagent_name = path.stem

        # Only load directly from path if file_content is not provided
        if file_content is None:
            with open(path) as f:
                file_content = f.read()

        # Legacy repo instructions are stored in .openhands_instructions
        if path.name == ".openhands_instructions":
            return RepoMicroagent(
                name="repo_legacy",
                content=file_content,
                source=str(path),
                type=MicroagentType.REPO_KNOWLEDGE,
            )

        # Handle third-party agent instruction files
        third_party_agent = cls._handle_third_party(path, file_content)
        if third_party_agent is not None:
            return third_party_agent

        file_io = io.StringIO(file_content)
        loaded = frontmatter.load(file_io)
        content = loaded.content

        # Handle case where there's no frontmatter or empty frontmatter
        metadata_dict = loaded.metadata or {}

        # Use name from frontmatter if provided, otherwise use derived name
        agent_name = str(metadata_dict.get("name", microagent_name))

        # Validate type field if provided in frontmatter
        if "type" in metadata_dict:
            type_value = metadata_dict["type"]
            valid_types = [t.value for t in MicroagentType]
            if type_value not in valid_types:
                valid_types_str = ", ".join(f'"{t}"' for t in valid_types)
                raise MicroagentValidationError(
                    f'Invalid "type" value: "{type_value}". '
                    f"Valid types are: {valid_types_str}"
                )

        # Infer the agent type:
        # 1. If inputs exist -> TASK
        # 2. If triggers exist -> KNOWLEDGE
        # 3. Else (no triggers) -> REPO (always active)
        triggers = metadata_dict.get("triggers", [])
        if not isinstance(triggers, list):
            raise MicroagentValidationError("Triggers must be a list of strings")
        if "inputs" in metadata_dict:
            # Add a trigger for the agent name if not already present
            trigger = f"/{agent_name}"
            if trigger not in triggers:
                triggers.append(trigger)
            return TaskMicroagent(
                name=agent_name,
                content=content,
                source=str(path),
                triggers=triggers,
            )

        elif metadata_dict.get("triggers", None):
            return KnowledgeMicroagent(
                name=agent_name,
                content=content,
                source=str(path),
                triggers=triggers,
            )
        else:
            # No triggers, default to REPO
            mcp_tools_raw = metadata_dict.get("mcp_tools")
            # Type cast to satisfy type checker - validation happens in RepoMicroagent
            mcp_tools = cast(MCPConfig | dict[str, Any] | None, mcp_tools_raw)
            return RepoMicroagent(
                name=agent_name, content=content, source=str(path), mcp_tools=mcp_tools
            )


class KnowledgeMicroagent(BaseMicroagent):
    """Knowledge micro-agents provide specialized expertise that's triggered by keywords
    in conversations.

    They help with:
    - Language best practices
    - Framework guidelines
    - Common patterns
    - Tool usage
    """

    type: MicroagentType = MicroagentType.KNOWLEDGE
    triggers: list[str] = Field(
        default_factory=list, description="List of triggers for the microagent"
    )

    def __init__(self, **data):
        super().__init__(**data)

    def match_trigger(self, message: str) -> str | None:
        """Match a trigger in the message.

        It returns the first trigger that matches the message.
        """
        message = message.lower()
        for trigger in self.triggers:
            if trigger.lower() in message:
                return trigger

        return None


class RepoMicroagent(BaseMicroagent):
    """Microagent specialized for repository-specific knowledge and guidelines.

    RepoMicroagents are loaded from `.openhands/microagents/repo.md` files within
    repositories and contain private, repository-specific instructions that are
    automatically loaded when
    working with that repository. They are ideal for:
        - Repository-specific guidelines
        - Team practices and conventions
        - Project-specific workflows
        - Custom documentation references
    """

    type: MicroagentType = MicroagentType.REPO_KNOWLEDGE
    mcp_tools: MCPConfig | dict | None = Field(
        default=None,
        description="MCP tools configuration for the microagent",
    )

    # Field-level validation for mcp_tools
    @field_validator("mcp_tools")
    @classmethod
    def _validate_mcp_tools(cls, v: MCPConfig | dict | None, info):
        if v is None:
            return v
        if isinstance(v, dict):
            try:
                v = MCPConfig.model_validate(v)
            except Exception as e:
                raise MicroagentValidationError(
                    f"Invalid MCPConfig dictionary: {e}"
                ) from e
        return v

    @model_validator(mode="after")
    def _enforce_repo_type(self):
        if self.type != MicroagentType.REPO_KNOWLEDGE:
            raise MicroagentValidationError(
                f"RepoMicroagent initialized with incorrect type: {self.type}"
            )
        return self


class TaskMicroagent(KnowledgeMicroagent):
    """TaskMicroagent is a special type of KnowledgeMicroagent that requires user input.

    These microagents are triggered by a special format: "/{agent_name}"
    and will prompt the user for any required inputs before proceeding.
    """

    type: MicroagentType = MicroagentType.TASK
    inputs: list[InputMetadata] = Field(
        default_factory=list,
        description=(
            "Input metadata for the microagent. Only exists for task microagents"
        ),
    )

    def __init__(self, **data):
        super().__init__(**data)
        self._append_missing_variables_prompt()

    def _append_missing_variables_prompt(self) -> None:
        """Append a prompt to ask for missing variables."""
        # Check if the content contains any variables or has inputs defined
        if not self.requires_user_input() and not self.inputs:
            return

        prompt = (
            "\n\nIf the user didn't provide any of these variables, ask the user to "
            "provide them first before the agent can proceed with the task."
        )
        self.content += prompt

    def extract_variables(self, content: str) -> list[str]:
        """Extract variables from the content.

        Variables are in the format ${variable_name}.
        """
        pattern = r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}"
        matches = re.findall(pattern, content)
        return matches

    def requires_user_input(self) -> bool:
        """Check if this microagent requires user input.

        Returns True if the content contains variables in the format ${variable_name}.
        """
        # Check if the content contains any variables
        variables = self.extract_variables(self.content)
        logger.debug(f"This microagent requires user input: {variables}")
        return len(variables) > 0


def load_microagents_from_dir(
    microagent_dir: str | Path,
) -> tuple[dict[str, RepoMicroagent], dict[str, KnowledgeMicroagent]]:
    """Load all microagents from the given directory.

    Note, legacy repo instructions will not be loaded here.

    Args:
        microagent_dir: Path to the microagents directory (e.g. .openhands/microagents)

    Returns:
        Tuple of (repo_agents, knowledge_agents) dictionaries
    """
    if isinstance(microagent_dir, str):
        microagent_dir = Path(microagent_dir)

    repo_agents = {}
    knowledge_agents = {}

    # Load all agents from microagents directory
    logger.debug(f"Loading agents from {microagent_dir}")

    # Always check for .cursorrules and AGENTS.md files in repo root, regardless of whether microagents_dir exists  # noqa: E501
    special_files = []
    repo_root = microagent_dir.parent.parent

    # Check for third party rules: .cursorrules, AGENTS.md, etc
    for filename in BaseMicroagent.PATH_TO_THIRD_PARTY_MICROAGENT_NAME.keys():
        for variant in [filename, filename.lower(), filename.upper()]:
            if (repo_root / variant).exists():
                special_files.append(repo_root / variant)
                break  # Only add the first one found to avoid duplicates

    # Collect .md files from microagents directory if it exists
    md_files = []
    if microagent_dir.exists():
        md_files = [f for f in microagent_dir.rglob("*.md") if f.name != "README.md"]

    # Process all files in one loop
    for file in chain(special_files, md_files):
        try:
            agent = BaseMicroagent.load(file, microagent_dir)
            if isinstance(agent, RepoMicroagent):
                repo_agents[agent.name] = agent
            elif isinstance(agent, KnowledgeMicroagent):
                # Both KnowledgeMicroagent and TaskMicroagent go into knowledge_agents
                knowledge_agents[agent.name] = agent
        except MicroagentValidationError as e:
            # For validation errors, include the original exception
            error_msg = f"Error loading microagent from {file}: {str(e)}"
            raise MicroagentValidationError(error_msg) from e
        except Exception as e:
            # For other errors, wrap in a ValueError with detailed message
            error_msg = f"Error loading microagent from {file}: {str(e)}"
            raise ValueError(error_msg) from e

    logger.debug(
        f"Loaded {len(repo_agents) + len(knowledge_agents)} microagents: "
        f"{[*repo_agents.keys(), *knowledge_agents.keys()]}"
    )
    return repo_agents, knowledge_agents
