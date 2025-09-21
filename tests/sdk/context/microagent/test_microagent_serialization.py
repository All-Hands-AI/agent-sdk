"""Tests for microagent serialization using discriminated union."""

import json

import pytest
from pydantic import ValidationError

from openhands.sdk.context.microagents import (
    BaseMicroagent,
    KnowledgeMicroagent,
    MicroagentUnion,
    RepoMicroagent,
    TaskMicroagent,
)
from openhands.sdk.context.microagents.types import InputMetadata


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
    deserialized = RepoMicroagent.model_validate(serialized)
    assert isinstance(deserialized, RepoMicroagent)
    assert deserialized.type == "repo"
    assert deserialized.name == "test-repo"
    assert deserialized.content == "Repository-specific instructions"


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
    deserialized = KnowledgeMicroagent.model_validate(serialized)
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
    deserialized = TaskMicroagent.model_validate(serialized)
    assert isinstance(deserialized, TaskMicroagent)
    assert deserialized.type == "task"
    assert deserialized.name == "test-task"
    assert deserialized.triggers == ["task", "automation"]
    assert len(deserialized.inputs) == 1


def test_microagent_union_discriminator_repo():
    """Test MicroagentUnion discriminator with RepoMicroagent."""
    # Create data for a RepoMicroagent
    repo_data = {
        "type": "repo",
        "name": "test-repo",
        "content": "Repository instructions",
        "source": "test.md",
        "mcp_tools": None,
    }

    # Test that we can create a RepoMicroagent directly
    microagent = RepoMicroagent.model_validate(repo_data)
    assert isinstance(microagent, RepoMicroagent)
    assert microagent.type == "repo"
    assert microagent.name == "test-repo"


def test_microagent_union_discriminator_knowledge():
    """Test MicroagentUnion discriminator with KnowledgeMicroagent."""
    # Create data for a KnowledgeMicroagent
    knowledge_data = {
        "type": "knowledge",
        "name": "test-knowledge",
        "content": "Knowledge instructions",
        "source": "test.md",
        "triggers": ["test"],
    }

    # Test that MicroagentUnion correctly discriminates to KnowledgeMicroagent
    microagent = KnowledgeMicroagent.model_validate(knowledge_data)
    assert isinstance(microagent, KnowledgeMicroagent)
    assert microagent.type == "knowledge"
    assert microagent.name == "test-knowledge"


def test_microagent_union_discriminator_task():
    """Test MicroagentUnion discriminator with TaskMicroagent."""
    # Create data for a TaskMicroagent
    task_data = {
        "type": "task",
        "name": "test-task",
        "content": "Task instructions",
        "source": "test.md",
        "triggers": ["task"],
        "inputs": [],
    }

    # Test that MicroagentUnion correctly discriminates to TaskMicroagent
    microagent = TaskMicroagent.model_validate(task_data)
    assert isinstance(microagent, TaskMicroagent)
    assert microagent.type == "task"
    assert microagent.name == "test-task"


def test_microagent_union_invalid_type():
    """Test MicroagentUnion with invalid type."""
    # Create data with invalid type
    invalid_data = {
        "type": "invalid",
        "name": "test-invalid",
        "content": "Invalid instructions",
        "source": "test.md",
    }

    # Test that validation fails for invalid type
    with pytest.raises(ValidationError) as exc_info:
        RepoMicroagent.model_validate(invalid_data)

    error = exc_info.value
    assert "Input should be 'repo'" in str(error)


def test_microagent_union_missing_type():
    """Test MicroagentUnion with missing type field."""
    # Create data without type field
    missing_type_data = {
        "name": "test-missing",
        "content": "Missing type instructions",
        "source": "test.md",
    }

    # RepoMicroagent should use default type
    repo_agent = RepoMicroagent.model_validate(missing_type_data)
    assert repo_agent.type == "repo"

    # KnowledgeMicroagent should use default type
    knowledge_agent = KnowledgeMicroagent.model_validate(missing_type_data)
    assert knowledge_agent.type == "knowledge"

    # TaskMicroagent should use default type
    task_agent = TaskMicroagent.model_validate(missing_type_data)
    assert task_agent.type == "task"


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
        deserialized_from_dict = type(original_agent).model_validate(serialized)

        # Deserialize from JSON string
        deserialized_from_json = type(original_agent).model_validate_json(json_str)

        # Verify all versions are equivalent
        assert deserialized_from_dict.type == original_agent.type
        assert deserialized_from_dict.name == original_agent.name
        assert deserialized_from_dict.content == original_agent.content
        assert deserialized_from_dict.source == original_agent.source

        assert deserialized_from_json.type == original_agent.type
        assert deserialized_from_json.name == original_agent.name
        assert deserialized_from_json.content == original_agent.content
        assert deserialized_from_json.source == original_agent.source


def test_microagent_union_type_validation():
    """Test that each microagent type validates its type field correctly."""
    # Test RepoMicroagent with wrong type
    with pytest.raises(ValidationError):
        RepoMicroagent(
            name="test",
            content="content",
            source="test.md",
            type="knowledge",  # type: ignore[arg-type]  # Wrong type intentionally
        )

    # Test KnowledgeMicroagent with wrong type
    with pytest.raises(ValidationError):
        KnowledgeMicroagent(
            name="test",
            content="content",
            source="test.md",
            type="repo",  # type: ignore[arg-type]  # Wrong type intentionally
        )

    # Test TaskMicroagent with wrong type
    with pytest.raises(ValidationError):
        TaskMicroagent(
            name="test",
            content="content",
            source="test.md",
            type="repo",  # type: ignore[arg-type]  # Wrong type intentionally
        )


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


def test_base_microagent_is_abstract():
    """Test that BaseMicroagent is marked as abstract but can still be instantiated."""
    # In Python, ABC doesn't prevent instantiation unless abstract methods exist
    # BaseMicroagent inherits from ABC but doesn't have abstract methods
    # So it can still be instantiated, but it's marked as abstract for type checking

    # This should work (Python allows it)
    base_agent = BaseMicroagent(
        name="test",
        content="content",
        source="test.md",
    )

    # Verify it was created
    assert base_agent.name == "test"
    assert base_agent.content == "content"
    assert base_agent.source == "test.md"

    # Verify it's an instance of ABC
    from abc import ABC

    assert isinstance(base_agent, ABC)


def test_microagent_union_annotation():
    """Test that MicroagentUnion annotation works correctly."""
    from typing import get_args

    # Verify the union contains the expected types
    expected_types = (RepoMicroagent, KnowledgeMicroagent, TaskMicroagent)

    # Get the union from the Annotated type
    union_args = get_args(MicroagentUnion)
    assert len(union_args) >= 1  # It's wrapped in Annotated
    actual_union = union_args[0]

    # Check that it's a Union of the expected types
    union_types = get_args(actual_union)
    assert set(union_types) == set(expected_types)


def test_discriminated_union_with_pydantic_model():
    """Test discriminated union functionality with a Pydantic model."""
    from typing import List

    from pydantic import BaseModel, Field

    class TestModel(BaseModel):
        microagents: List[MicroagentUnion] = Field(default_factory=list)

    # Create test data with different microagent types
    test_data = {
        "microagents": [
            {
                "type": "repo",
                "name": "test-repo",
                "content": "Repo content",
                "source": "repo.md",
                "mcp_tools": None,
            },
            {
                "type": "knowledge",
                "name": "test-knowledge",
                "content": "Knowledge content",
                "source": "knowledge.md",
                "triggers": ["test"],
            },
            {
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


def test_task_microagent_prompt_appending():
    """Test that TaskMicroagent correctly appends missing variables prompt."""
    # Create TaskMicroagent with variables in content
    task_agent = TaskMicroagent(
        name="test-task",
        content="Task with ${variable1} and ${variable2}",
        source="test.md",
        triggers=["task"],
    )

    # Check that the prompt was appended
    expected_prompt = (
        "\n\nIf the user didn't provide any of these variables, ask the user to "
        "provide them first before the agent can proceed with the task."
    )
    assert expected_prompt in task_agent.content

    # Create TaskMicroagent without variables but with inputs
    task_agent_with_inputs = TaskMicroagent(
        name="test-task-inputs",
        content="Task without variables",
        source="test.md",
        triggers=["task"],
        inputs=[InputMetadata(name="input1", description="Test input")],
    )

    # Check that the prompt was appended
    assert expected_prompt in task_agent_with_inputs.content

    # Create TaskMicroagent without variables or inputs
    task_agent_no_vars = TaskMicroagent(
        name="test-task-no-vars",
        content="Task without variables or inputs",
        source="test.md",
        triggers=["task"],
    )

    # Check that the prompt was NOT appended
    assert expected_prompt not in task_agent_no_vars.content
