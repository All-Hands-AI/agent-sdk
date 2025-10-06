"""Implementation of the plan writer tool using FileEditor APIs."""

from pathlib import Path

from openhands.sdk.logger import get_logger
from openhands.sdk.tool import ToolExecutor
from openhands.tools.file_editor.editor import FileEditor
from openhands.tools.plan_writer.definition import (
    PlanWriterAction,
    PlanWriterObservation,
)


logger = get_logger(__name__)

# Hardcoded plan filename
PLAN_FILENAME = "PLAN.md"


class PlanWriterExecutor(ToolExecutor):
    """Executor for plan writing operations using FileEditor APIs.

    This executor is restricted to only modify PLAN.md in the workspace root.
    It uses the FileEditor for all operations.
    """

    def __init__(self, workspace_root: str):
        """Initialize the PlanWriterExecutor.

        Args:
            workspace_root: Root directory for plan file operations.
        """
        self.workspace_root = Path(workspace_root).resolve()
        self.plan_path = str(self.workspace_root / PLAN_FILENAME)

        # Create a FileEditor instance for this workspace
        self.editor = FileEditor(workspace_root=str(self.workspace_root))

        # Always initialize PLAN.md if it doesn't exist (empty file)
        plan_file = Path(self.plan_path)
        if not plan_file.exists():
            logger.info(f"Initializing empty PLAN.md at {self.plan_path}")
            self.editor(command="create", path=self.plan_path, file_text="")
        else:
            logger.info(f"PLAN.md already exists at {self.plan_path}")

        logger.info(
            f"PlanWriterExecutor initialized with workspace: {self.workspace_root}, "
            f"plan path: {self.plan_path}"
        )

    def __call__(self, action: PlanWriterAction) -> PlanWriterObservation:
        """Execute the plan writer action.

        All operations are restricted to PLAN.md only.
        Directly passes commands to FileEditor for consistent behavior.
        """
        try:
            # Execute the FileEditor command on PLAN.md
            # Note: file_text is not used since we don't have 'create' command
            editor_result = self.editor(
                command=action.command,
                path=self.plan_path,
                old_str=action.old_str,
                new_str=action.new_str,
                insert_line=action.insert_line,
                view_range=action.view_range,
            )

            # Convert FileEditorObservation to PlanWriterObservation
            if editor_result.error:
                return PlanWriterObservation(
                    command=action.command, output="", error=editor_result.error
                )

            return PlanWriterObservation(
                command=action.command, output=editor_result.output, error=None
            )

        except Exception as e:
            logger.error(f"Error in PlanWriterExecutor: {e}")
            return PlanWriterObservation(
                command=action.command, output="", error=f"Error: {str(e)}"
            )
