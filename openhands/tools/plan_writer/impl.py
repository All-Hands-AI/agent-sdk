"""Implementation of the plan writer tool."""

from pathlib import Path

from openhands.sdk.logger import get_logger
from openhands.sdk.tool import ToolExecutor
from openhands.tools.plan_writer.definition import (
    PlanWriterAction,
    PlanWriterObservation,
)


logger = get_logger(__name__)


class PlanWriterExecutor(ToolExecutor):
    """Executor for plan writing operations."""

    def __init__(self, workspace_root: str):
        """Initialize the PlanWriterExecutor.

        Args:
            workspace_root: Root directory for plan file operations.
        """
        self.workspace_root = Path(workspace_root).resolve()
        logger.info(
            f"PlanWriterExecutor initialized with workspace: {self.workspace_root}"
        )

    def __call__(self, action: PlanWriterAction) -> PlanWriterObservation:
        """Execute the plan writer action."""
        try:
            # Validate filename
            if not action.filename.endswith(".md"):
                return PlanWriterObservation(
                    command=action.command,
                    filename=action.filename,
                    error="Filename must end with .md extension",
                )

            # Ensure filename is safe (no path traversal)
            filename = Path(action.filename).name
            if filename != action.filename:
                return PlanWriterObservation(
                    command=action.command,
                    filename=action.filename,
                    error="Filename cannot contain path separators",
                )

            plan_path = self.workspace_root / filename

            if action.command == "write":
                return self._write_plan(plan_path, action.content)
            elif action.command == "append":
                return self._append_plan(plan_path, action.content)
            else:
                return PlanWriterObservation(
                    command="write",  # Use valid command for observation
                    filename=action.filename,
                    error=f"Unknown command: {action.command}",
                )

        except Exception as e:
            logger.error(f"Error in PlanWriterExecutor: {e}")
            return PlanWriterObservation(
                command=action.command,
                filename=action.filename,
                error=f"Error: {str(e)}",
            )

    def _write_plan(self, plan_path: Path, content: str) -> PlanWriterObservation:
        """Write content to the plan file (create or overwrite)."""
        try:
            # Ensure the directory exists
            plan_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the content
            with open(plan_path, "w", encoding="utf-8") as f:
                f.write(content)

            return PlanWriterObservation(
                command="write",
                filename=plan_path.name,
                output=f"Plan written successfully to {plan_path.name} "
                f"({len(content)} characters)",
            )

        except Exception as e:
            return PlanWriterObservation(
                command="write",
                filename=plan_path.name,
                error=f"Error writing plan file: {str(e)}",
            )

    def _append_plan(self, plan_path: Path, content: str) -> PlanWriterObservation:
        """Append content to the plan file."""
        try:
            # Check if file exists
            if not plan_path.exists():
                return PlanWriterObservation(
                    command="append",
                    filename=plan_path.name,
                    error=(
                        f"Plan file {plan_path.name} does not exist. "
                        f"Use 'write' command first."
                    ),
                )

            # Read existing content
            with open(plan_path, encoding="utf-8") as f:
                existing_content = f.read()

            # Append new content
            updated_content = existing_content + content

            with open(plan_path, "w", encoding="utf-8") as f:
                f.write(updated_content)

            return PlanWriterObservation(
                command="append",
                filename=plan_path.name,
                output=f"Content appended successfully to {plan_path.name} "
                f"(added {len(content)} characters)",
            )

        except Exception as e:
            return PlanWriterObservation(
                command="append",
                filename=plan_path.name,
                error=f"Error appending to plan file: {str(e)}",
            )
