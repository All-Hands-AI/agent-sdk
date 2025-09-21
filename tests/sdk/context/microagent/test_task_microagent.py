from openhands.sdk.context.microagents import TaskMicroagent
from openhands.sdk.context.microagents.types import InputMetadata


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
