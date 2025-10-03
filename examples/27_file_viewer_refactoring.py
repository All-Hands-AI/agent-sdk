"""Example demonstrating the refactored FileViewer design with no inheritance."""

import logging
import tempfile
from pathlib import Path

from openhands.tools.file_viewer import FileViewerExecutor
from openhands.tools.file_viewer.definition import FileViewerAction
from openhands.tools.str_replace_editor import FileEditorExecutor
from openhands.tools.str_replace_editor.definition import StrReplaceEditorAction


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# Create a temporary workspace with some files
with tempfile.TemporaryDirectory() as temp_dir:
    # Create test files
    test_file = Path(temp_dir) / "example.py"
    test_file.write_text("""def hello_world():
    print("Hello, World!")
    return "success"

def add_numbers(a, b):
    return a + b
""")

    logger.info("=== File Viewer Refactoring Demo ===")
    logger.info(f"Working directory: {temp_dir}")

    # Demonstrate the refactored design
    logger.info("\n1. Creating FileEditorExecutor (read_only=False by default)")
    editor_executor = FileEditorExecutor(workspace_root=temp_dir)
    logger.info(f"   editor_executor.read_only = {editor_executor.read_only}")

    logger.info("\n2. Creating FileEditorExecutor with read_only=True")
    readonly_editor = FileEditorExecutor(workspace_root=temp_dir, read_only=True)
    logger.info(f"   readonly_editor.read_only = {readonly_editor.read_only}")

    logger.info("\n3. Creating FileViewerExecutor (uses FileEditorExecutor internally)")
    viewer_executor = FileViewerExecutor(workspace_root=temp_dir)
    logger.info(
        f"   viewer_executor.editor_executor.read_only = "
        f"{viewer_executor.editor_executor.read_only}"
    )

    # Test viewing with FileEditorExecutor
    logger.info("\n4. Testing FileEditorExecutor view operation:")
    view_action = StrReplaceEditorAction(command="view", path=str(test_file))
    result = editor_executor(view_action)
    logger.info(f"   Success: {not result.error}")

    # Test editing with FileEditorExecutor
    logger.info("\n5. Testing FileEditorExecutor create operation:")
    new_file_path = Path(temp_dir) / "new_file.txt"
    create_action = StrReplaceEditorAction(
        command="create",
        path=str(new_file_path),
        file_text="This is a new file created by FileEditorExecutor",
    )
    result = editor_executor(create_action)
    logger.info(f"   Success: {not result.error}")

    # Test editing with read-only FileEditorExecutor (should fail)
    logger.info("\n6. Testing read-only FileEditorExecutor create operation:")
    result = readonly_editor(create_action)
    logger.info(f"   Success: {not result.error}")
    logger.info(f"   Error message: {result.error}")

    # Test viewing with FileViewerExecutor
    logger.info("\n7. Testing FileViewerExecutor view operation:")
    viewer_action = FileViewerAction(command="view", path=str(test_file))
    result = viewer_executor(viewer_action)
    logger.info(f"   Success: {not result.error}")

    # Test editing with FileViewerExecutor (should fail)
    logger.info("\n8. Testing FileViewerExecutor with non-view command:")
    # FileViewerAction only allows "view" command, so this would fail at validation
    logger.info(
        "   FileViewerAction only allows 'view' command - design prevents misuse"
    )

logger.info("\n=== Demo Complete ===")
logger.info("Key points about the refactored design:")
logger.info("1. FileEditorExecutor has a read_only parameter (default False)")
logger.info(
    "2. FileViewerExecutor uses FileEditorExecutor internally with read_only=True"
)
logger.info("3. No inheritance - simple composition pattern")
logger.info("4. Clean separation of concerns")
logger.info("5. Easy to understand and maintain")
