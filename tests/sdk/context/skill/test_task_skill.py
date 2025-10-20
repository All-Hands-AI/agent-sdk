from openhands.sdk.context.skills import TaskSkill
from openhands.sdk.context.skills.types import InputMetadata


def test_task_skill_prompt_appending():
    """Test that TaskSkill correctly appends missing variables prompt."""
    # Create TaskSkill with variables in content
    task_agent = TaskSkill(
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

    # Create TaskSkill without variables but with inputs
    task_agent_with_inputs = TaskSkill(
        name="test-task-inputs",
        content="Task without variables",
        source="test.md",
        triggers=["task"],
        inputs=[InputMetadata(name="input1", description="Test input")],
    )

    # Check that the prompt was appended
    assert expected_prompt in task_agent_with_inputs.content

    # Create TaskSkill without variables or inputs
    task_agent_no_vars = TaskSkill(
        name="test-task-no-vars",
        content="Task without variables or inputs",
        source="test.md",
        triggers=["task"],
    )

    # Check that the prompt was NOT appended
    assert expected_prompt not in task_agent_no_vars.content
