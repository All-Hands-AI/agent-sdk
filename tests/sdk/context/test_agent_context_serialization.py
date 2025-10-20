"""Tests for AgentContext serialization and deserialization."""

import json

from openhands.sdk.context.agent_context import AgentContext
from openhands.sdk.context.skills import (
    RepoSkill,
    Skill,
    TaskSkill,
)
from openhands.sdk.context.skills.types import InputMetadata


def test_agent_context_serialization_roundtrip():
    """Ensure AgentContext round-trips through dict and JSON serialization."""

    repo_agent = RepoSkill(
        name="repo-guidelines",
        content="Repository guidelines",
        source="repo.md",
    )
    knowledge_agent = Skill(
        name="python-help",
        content="Use type hints in Python code",
        source="knowledge.md",
        triggers=["python"],
    )
    task_agent = TaskSkill(
        name="run-task",
        content="Execute the task with ${param}",
        source="task.md",
        triggers=["run"],
        inputs=[InputMetadata(name="param", description="Task parameter")],
    )

    context = AgentContext(
        skills=[repo_agent, knowledge_agent, task_agent],
        system_message_suffix="System suffix",
        user_message_suffix="User suffix",
    )

    serialized = context.model_dump()
    assert serialized["system_message_suffix"] == "System suffix"
    assert serialized["user_message_suffix"] == "User suffix"
    assert [agent["type"] for agent in serialized["skills"]] == [
        "repo",
        "knowledge",
        "task",
    ]

    json_str = context.model_dump_json()
    parsed = json.loads(json_str)
    assert parsed["system_message_suffix"] == "System suffix"
    assert parsed["user_message_suffix"] == "User suffix"
    assert parsed["skills"][2]["inputs"][0]["name"] == "param"

    deserialized_from_dict = AgentContext.model_validate(serialized)
    assert isinstance(deserialized_from_dict.skills[0], RepoSkill)
    assert deserialized_from_dict.skills[0] == repo_agent
    assert isinstance(deserialized_from_dict.skills[1], Skill)
    assert deserialized_from_dict.skills[1] == knowledge_agent
    assert isinstance(deserialized_from_dict.skills[2], TaskSkill)
    assert deserialized_from_dict.skills[2] == task_agent
    assert deserialized_from_dict.system_message_suffix == "System suffix"
    assert deserialized_from_dict.user_message_suffix == "User suffix"

    deserialized_from_json = AgentContext.model_validate_json(json_str)
    assert isinstance(deserialized_from_json.skills[0], RepoSkill)
    assert deserialized_from_json.skills[0] == repo_agent
    assert isinstance(deserialized_from_json.skills[1], Skill)
    assert deserialized_from_json.skills[1] == knowledge_agent
    assert isinstance(deserialized_from_json.skills[2], TaskSkill)
    assert deserialized_from_json.skills[2] == task_agent
    assert deserialized_from_json.model_dump() == serialized
