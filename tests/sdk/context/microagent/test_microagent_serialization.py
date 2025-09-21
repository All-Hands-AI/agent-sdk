"""Tests for microagent serialization using discriminated union."""

import json

from pydantic import BaseModel, Field

from openhands.sdk.context.microagents import (
    BaseMicroagent,
    KnowledgeMicroagent,
    RepoMicroagent,
    TaskMicroagent,
)
from openhands.sdk.context.microagents.types import InputMetadata
from openhands.sdk.utils.models import OpenHandsModel


def test_repo_microagent_serialization():
    """Test RepoMicroagent serialization and deserialization."""
    # Create a RepoMicroagent
    repo_agent = RepoMicroagent(
        name="test-repo",
        content="Repository-specific instructions",
        source="test-repo.md",
    )

    # Test serialization
    serialized = repo_agent.model_dump()
    assert serialized["type"] == "repo"
    assert serialized["name"] == "test-repo"
    assert serialized["content"] == "Repository-specific instructions"
    assert serialized["source"] == "test-repo.md"
    assert serialized["mcp_tools"] is None

    # Test JSON serialization
    json_str = repo_agent.model_dump_json()
    assert isinstance(json_str, str)
    parsed = json.loads(json_str)
    assert parsed["type"] == "repo"

    # Test deserialization
    deserialized = BaseMicroagent.model_validate(serialized)
    assert isinstance(deserialized, RepoMicroagent)
    assert deserialized == repo_agent


def test_knowledge_microagent_serialization():
    """Test KnowledgeMicroagent serialization and deserialization."""
    # Create a KnowledgeMicroagent
    knowledge_agent = KnowledgeMicroagent(
        name="test-knowledge",
        content="Knowledge-based instructions",
        source="test-knowledge.md",
        triggers=["python", "testing"],
    )

    # Test serialization
    serialized = knowledge_agent.model_dump()
    assert serialized["type"] == "knowledge"
    assert serialized["name"] == "test-knowledge"
    assert serialized["content"] == "Knowledge-based instructions"
    assert serialized["triggers"] == ["python", "testing"]

    # Test JSON serialization
    json_str = knowledge_agent.model_dump_json()
    assert isinstance(json_str, str)
    parsed = json.loads(json_str)
    assert parsed["type"] == "knowledge"

    # Test deserialization
    deserialized = BaseMicroagent.model_validate(serialized)
    assert isinstance(deserialized, KnowledgeMicroagent)
    assert deserialized.type == "knowledge"
    assert deserialized.name == "test-knowledge"
    assert deserialized.triggers == ["python", "testing"]


def test_task_microagent_serialization():
    """Test TaskMicroagent serialization and deserialization."""
    # Create a TaskMicroagent
    task_agent = TaskMicroagent(
        name="test-task",
        content="Task-based instructions with ${variable}",
        source="test-task.md",
        triggers=["task", "automation"],
        inputs=[
            InputMetadata(name="variable", description="A test variable"),
        ],
    )

    # Test serialization
    serialized = task_agent.model_dump()
    assert serialized["type"] == "task"
    assert serialized["name"] == "test-task"
    assert "Task-based instructions with ${variable}" in serialized["content"]
    assert serialized["triggers"] == ["task", "automation"]
    assert len(serialized["inputs"]) == 1
    assert serialized["inputs"][0]["name"] == "variable"

    # Test JSON serialization
    json_str = task_agent.model_dump_json()
    assert isinstance(json_str, str)
    parsed = json.loads(json_str)
    assert parsed["type"] == "task"

    # Test deserialization
    deserialized = BaseMicroagent.model_validate(serialized)
    assert isinstance(deserialized, TaskMicroagent)
    assert deserialized.type == "task"
    assert deserialized.name == "test-task"
    assert deserialized.triggers == ["task", "automation"]
    assert len(deserialized.inputs) == 1


def test_microagent_union_serialization_roundtrip():
    """Test complete serialization roundtrip for all microagent types."""
    # Test data for each microagent type
    test_cases = [
        RepoMicroagent(
            name="repo-test",
            content="Repo content",
            source="repo.md",
        ),
        KnowledgeMicroagent(
            name="knowledge-test",
            content="Knowledge content",
            source="knowledge.md",
            triggers=["test"],
        ),
        TaskMicroagent(
            name="task-test",
            content="Task content with ${var}",
            source="task.md",
            triggers=["task"],
            inputs=[InputMetadata(name="var", description="Test variable")],
        ),
    ]

    for original_agent in test_cases:
        # Serialize to dict
        serialized = original_agent.model_dump()

        # Serialize to JSON string
        json_str = original_agent.model_dump_json()

        # Deserialize from dict
        deserialized_from_dict = BaseMicroagent.model_validate(serialized)

        # Deserialize from JSON string
        deserialized_from_json = BaseMicroagent.model_validate_json(json_str)

        # Verify all versions are equivalent
        assert deserialized_from_dict.type == original_agent.type
        assert deserialized_from_dict.name == original_agent.name
        assert deserialized_from_dict.content == original_agent.content
        assert deserialized_from_dict.source == original_agent.source

        assert deserialized_from_json.type == original_agent.type
        assert deserialized_from_json.name == original_agent.name
        assert deserialized_from_json.content == original_agent.content
        assert deserialized_from_json.source == original_agent.source


def test_microagent_union_polymorphic_list():
    """Test that a list of MicroagentUnion can contain different microagent types."""
    # Create a list with different microagent types
    microagents = [
        RepoMicroagent(
            name="repo1",
            content="Repo content",
            source="repo1.md",
        ),
        KnowledgeMicroagent(
            name="knowledge1",
            content="Knowledge content",
            source="knowledge1.md",
            triggers=["test"],
        ),
        TaskMicroagent(
            name="task1",
            content="Task content",
            source="task1.md",
            triggers=["task"],
        ),
    ]

    # Serialize the list
    serialized_list = [agent.model_dump() for agent in microagents]

    # Verify each item has correct type
    assert serialized_list[0]["type"] == "repo"
    assert serialized_list[1]["type"] == "knowledge"
    assert serialized_list[2]["type"] == "task"

    # Test JSON serialization of the list
    json_str = json.dumps(serialized_list)
    parsed_list = json.loads(json_str)

    assert len(parsed_list) == 3
    assert parsed_list[0]["type"] == "repo"
    assert parsed_list[1]["type"] == "knowledge"
    assert parsed_list[2]["type"] == "task"

    # reconstruct the list from serialized data
    deserialized_list = [
        BaseMicroagent.model_validate(item) for item in serialized_list
    ]

    assert len(deserialized_list) == 3
    assert isinstance(deserialized_list[0], RepoMicroagent)
    assert isinstance(deserialized_list[1], KnowledgeMicroagent)
    assert isinstance(deserialized_list[2], TaskMicroagent)
    assert deserialized_list[0] == microagents[0]
    assert deserialized_list[1] == microagents[1]
    assert deserialized_list[2] == microagents[2]


def test_discriminated_union_with_openhands_model():
    """Test discriminated union functionality with a Pydantic model."""

    class TestModel(OpenHandsModel):
        microagents: list[BaseMicroagent] = Field(default_factory=list)

    # Create test data with different microagent types
    test_data = {
        "microagents": [
            {
                "kind": "RepoMicroagent",
                "type": "repo",
                "name": "test-repo",
                "content": "Repo content",
                "source": "repo.md",
                "mcp_tools": None,
            },
            {
                "kind": "KnowledgeMicroagent",
                "type": "knowledge",
                "name": "test-knowledge",
                "content": "Knowledge content",
                "source": "knowledge.md",
                "triggers": ["test"],
            },
            {
                "kind": "TaskMicroagent",
                "type": "task",
                "name": "test-task",
                "content": "Task content",
                "source": "task.md",
                "triggers": ["task"],
                "inputs": [],
            },
        ]
    }

    # Validate the model - this tests the discriminated union
    model = TestModel.model_validate(test_data)

    # Verify each microagent was correctly discriminated
    assert len(model.microagents) == 3
    assert isinstance(model.microagents[0], RepoMicroagent)
    assert isinstance(model.microagents[1], KnowledgeMicroagent)
    assert isinstance(model.microagents[2], TaskMicroagent)

    # Verify types are correct
    assert model.microagents[0].type == "repo"
    assert model.microagents[1].type == "knowledge"
    assert model.microagents[2].type == "task"


def test_discriminated_union_with_pydantic_model():
    """Test discriminated union functionality with a Pydantic model."""

    class TestModel(BaseModel):
        microagents: list[BaseMicroagent] = Field(default_factory=list)

    # Create test data with different microagent types
    test_data = {
        "microagents": [
            {
                "kind": "RepoMicroagent",
                "type": "repo",
                "name": "test-repo",
                "content": "Repo content",
                "source": "repo.md",
                "mcp_tools": None,
            },
            {
                "kind": "KnowledgeMicroagent",
                "type": "knowledge",
                "name": "test-knowledge",
                "content": "Knowledge content",
                "source": "knowledge.md",
                "triggers": ["test"],
            },
            {
                "kind": "TaskMicroagent",
                "type": "task",
                "name": "test-task",
                "content": "Task content",
                "source": "task.md",
                "triggers": ["task"],
                "inputs": [],
            },
        ]
    }

    # Validate the model - this tests the discriminated union
    model = TestModel.model_validate(test_data)

    # Verify each microagent was correctly discriminated
    assert len(model.microagents) == 3
    assert isinstance(model.microagents[0], RepoMicroagent)
    assert isinstance(model.microagents[1], KnowledgeMicroagent)
    assert isinstance(model.microagents[2], TaskMicroagent)

    # Verify types are correct
    assert model.microagents[0].type == "repo"
    assert model.microagents[1].type == "knowledge"
    assert model.microagents[2].type == "task"
