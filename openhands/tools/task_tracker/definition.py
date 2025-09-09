import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from openhands.sdk import ImageContent, TextContent
from openhands.sdk.logger import get_logger
from openhands.sdk.tool import (
    ActionBase,
    ObservationBase,
    Tool,
    ToolAnnotations,
    ToolExecutor,
)


logger = get_logger(__name__)


class TaskItem(BaseModel):
    title: str = Field(..., description="A brief title for the task.")
    notes: str = Field("", description="Additional details or notes about the task.")
    status: Literal["todo", "in_progress", "done"] = Field(
        "todo",
        description="The current status of the task. "
        "One of 'todo', 'in_progress', or 'done'.",
    )


class TaskTrackerAction(ActionBase):
    """An action where the agent writes or updates a task list for task management."""

    command: Literal["view", "plan"] = Field(
        default="view",
        description="The command to execute. `view` shows the current task list. `plan` creates or updates the task list based on provided requirements and progress. Always `view` the current list before making changes.",  # noqa: E501
    )
    task_list: list[TaskItem] = Field(
        default_factory=list,
        description="The full task list. Required parameter of `plan` command.",
    )


class TaskTrackerObservation(ObservationBase):
    """This data class represents the result of a task tracking operation."""

    content: str = Field(
        default="", description="The formatted task list or status message"
    )
    command: str = Field(default="", description="The command that was executed")
    task_list: list[TaskItem] = Field(
        default_factory=list, description="The current task list"
    )

    @property
    def agent_observation(self) -> list[TextContent | ImageContent]:
        return [TextContent(text=self.content)]


class TaskTrackerExecutor(ToolExecutor):
    """Executor for the task tracker tool."""

    def __init__(self, save_dir: str | None = None):
        """Initialize TaskTrackerExecutor.

        Args:
            save_dir: Optional directory to save tasks to. If provided, tasks will be
                     persisted to save_dir/TASKS.md
        """
        self.save_dir = Path(save_dir) if save_dir else None
        self._task_list: list[TaskItem] = []

        # Load existing tasks if save_dir is provided and file exists
        if self.save_dir:
            self._load_tasks()

    def __call__(self, action: TaskTrackerAction) -> TaskTrackerObservation:
        """Execute the task tracker action."""
        if action.command == "plan":
            # Update the task list
            self._task_list = action.task_list
            # Save to file if save_dir is provided
            if self.save_dir:
                self._save_tasks()
            return TaskTrackerObservation(
                content="Task list has been updated with "
                + f"{len(self._task_list)} item(s).",
                command=action.command,
                task_list=self._task_list,
            )
        elif action.command == "view":
            # Return the current task list
            if not self._task_list:
                return TaskTrackerObservation(
                    content='No task list found. Use the "plan" command to create one.',
                    command=action.command,
                    task_list=[],
                )
            content = self._format_task_list(self._task_list)
            return TaskTrackerObservation(
                content=content, command=action.command, task_list=self._task_list
            )
        else:
            return TaskTrackerObservation(
                content=f"Unknown command: {action.command}. "
                + 'Supported commands are "view" and "plan".',
                command=action.command,
                task_list=[],
            )

    def _format_task_list(self, task_list: list[TaskItem]) -> str:
        """Format the task list for display."""
        if not task_list:
            return "No tasks in the list."

        content = "# Task List\n\n"
        for i, task in enumerate(task_list, 1):
            status_icon = {"todo": "⏳", "in_progress": "🔄", "done": "✅"}.get(
                task.status, "⏳"
            )

            title = task.title
            notes = task.notes

            content += f"{i}. {status_icon} {title}\n"
            if notes:
                content += f"   {notes}\n"
            content += "\n"

        return content.strip()

    def _load_tasks(self) -> None:
        """Load tasks from the TASKS.json file if it exists."""
        if not self.save_dir:
            return

        tasks_file = self.save_dir / "TASKS.json"
        if not tasks_file.exists():
            return

        try:
            with open(tasks_file, "r", encoding="utf-8") as f:
                self._task_list = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(
                f"Failed to load tasks from {tasks_file}: {e}. Starting with "
                "an empty task list."
            )
            self._task_list = []

    def _save_tasks(self) -> None:
        """Save tasks to the TASKS.json file."""
        if not self.save_dir:
            return

        tasks_file = self.save_dir / "TASKS.json"
        try:
            # Create the directory if it doesn't exist
            self.save_dir.mkdir(parents=True, exist_ok=True)

            with open(tasks_file, "w", encoding="utf-8") as f:
                json.dump(self._task_list, f, indent=2)
        except OSError as e:
            logger.warning(f"Failed to save tasks to {tasks_file}: {e}")
            pass


# Tool definition with detailed description
TASK_TRACKER_DESCRIPTION = """This tool provides structured task management capabilities for development workflows.
It enables systematic tracking of work items, progress monitoring, and efficient
organization of complex development activities.

The tool maintains visibility into project status and helps communicate
progress effectively to users.

## Application Guidelines

Utilize this tool in the following situations:

1. Multi-phase development work - When projects involve multiple sequential or
   parallel activities
2. Complex implementation tasks - Work requiring systematic planning and
   coordination across multiple components
3. Explicit user request for task organization - When users specifically ask
   for structured task management
4. Multiple concurrent requirements - When users present several work items
   that need coordination
5. Project initiation - Capture and organize user requirements at project start
6. Work commencement - Update task status to in_progress before beginning
   implementation. Maintain focus by limiting active work to one task
7. Task completion - Update status to done and identify any additional work
   that emerged during implementation

## Situations Where Tool Usage Is Unnecessary

Avoid using this tool when:

1. Single atomic tasks that require no decomposition
2. Trivial operations where tracking adds no organizational value
3. Simple activities completable in minimal steps
4. Pure information exchange or discussion

Note: For single straightforward tasks, proceed with direct implementation
rather than creating tracking overhead.

## Usage Scenarios

**Scenario A: Feature Development with Validation**
User request: "Build a user authentication system with login/logout functionality.
Don't forget to include input validation and error handling!"

Response approach: I'll implement a user authentication system with comprehensive
validation. Let me organize this work systematically.

*Task breakdown includes:*
1. Design authentication API endpoints and data models
2. Implement user login/logout controllers with session management
3. Add client-side form validation and error display
4. Create backend input sanitization and security checks
5. Implement comprehensive error handling for edge cases
6. Perform integration testing and fix any issues

**Scenario B: Codebase Refactoring**
User request: "I need to update all instances of the method 'fetchData' to
'retrieveInformation' throughout the entire project"

Response approach: Let me first analyze your codebase to identify all locations
where 'fetchData' appears.

*After code analysis*

I've located 12 occurrences of 'fetchData' across 6 files in your project.
I'll create a systematic plan to update these references.

*Organized task list includes specific file-by-file updates*

**Scenario C: Multi-feature Development**
User request: "Set up a blog platform with these components: admin dashboard,
article management, comment system, and user profiles."

Response approach: I'll help build your blog platform. Let me break down these
components into manageable implementation phases.

*Creates structured plan with each feature decomposed into specific development tasks*

## Counter-examples - Direct Implementation Preferred

**Counter-example A: Simple inquiry**
User request: "What's the syntax for a for loop in JavaScript?"

Response approach: Here's how to write a for loop in JavaScript:

```javascript
for (let i = 0; i < array.length; i++) {
    console.log(array[i]);
}
```

*No task tracking needed - single informational response*

**Counter-example B: Minor modification**
User request: "Please add a docstring to the processPayment function explaining
its parameters."

Response approach: I'll add a docstring to explain the processPayment function.

*Direct edit without task tracking for simple modification*

## Status Management and Workflow

1. **Status Values**: Track work using these states:
   - todo: Not yet initiated
   - in_progress: Currently active (maintain single focus)
   - done: Successfully completed

2. **Workflow Practices**:
   - Update status dynamically as work progresses
   - Mark completion immediately upon task finish
   - Limit active work to ONE task at any given time
   - Complete current activities before initiating new ones
   - Remove obsolete tasks from tracking entirely

3. **Completion Criteria**:
   - Mark tasks as done only when fully achieved
   - Keep status as in_progress if errors, blocks, or partial completion exist
   - Create new tasks for discovered issues or dependencies
   - Never mark done when:
       - Test suites are failing
       - Implementation remains incomplete
       - Unresolved errors persist
       - Required resources are unavailable

4. **Task Organization**:
   - Write precise, actionable descriptions
   - Decompose complex work into manageable units
   - Use descriptive, clear naming conventions

When uncertain, favor using this tool. Proactive task management demonstrates
systematic approach and ensures comprehensive requirement fulfillment."""  # noqa: E501


task_tracker_tool = Tool(
    name="task_tracker",
    description=TASK_TRACKER_DESCRIPTION,
    input_schema=TaskTrackerAction,
    output_schema=TaskTrackerObservation,
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)


class TaskTrackerTool(Tool[TaskTrackerAction, TaskTrackerObservation]):
    """A Tool subclass that automatically initializes a TaskTrackerExecutor."""

    def __init__(self, save_dir: str | None = None):
        """Initialize TaskTrackerTool with a TaskTrackerExecutor.

        Args:
            save_dir: Optional directory to save tasks to. If provided, tasks will be
                     persisted to save_dir/TASKS.json
        """
        executor = TaskTrackerExecutor(save_dir=save_dir)

        # Initialize the parent Tool with the executor
        super().__init__(
            name="task_tracker",
            description=TASK_TRACKER_DESCRIPTION,
            input_schema=TaskTrackerAction,
            output_schema=TaskTrackerObservation,
            annotations=task_tracker_tool.annotations,
            executor=executor,
        )
