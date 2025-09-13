"""Local file store implementation."""

import os
import shutil

from openhands.sdk.logger import get_logger

from .base import FileStore


logger = get_logger(__name__)


class LocalFileStore(FileStore):
    """Local file store implementation using the local filesystem.

    This implementation provides file storage operations on the local filesystem
    with automatic directory creation and graceful error handling.

    Attributes:
        root: The root directory path for all file operations.

    """

    root: str

    def __init__(self, root: str):
        """Initialize the local file store with a root directory.

        Args:
            root: The root directory path. Supports tilde expansion (e.g., "~/data").
                  If the directory doesn't exist, it will be created automatically.

        """
        if root.startswith("~"):
            root = os.path.expanduser(root)
        self.root = root
        os.makedirs(self.root, exist_ok=True)

    def get_full_path(self, path: str) -> str:
        """Get the full filesystem path for a given relative path.

        Args:
            path: The relative path within the file store.
                  Leading slashes are automatically stripped.

        Returns:
            The absolute filesystem path.

        """
        if path.startswith("/"):
            path = path[1:]
        return os.path.join(self.root, path)

    def write(self, path: str, contents: str | bytes) -> None:
        """Write contents to a file at the given path.

        Args:
            path: The file path to write to, relative to the root directory.
            contents: The content to write, either as string or bytes.

        Note:
            If parent directories in the path don't exist, they will be created
            automatically. String content is written with UTF-8 encoding.

        """
        full_path = self.get_full_path(path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        if isinstance(contents, str):
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(contents)
        else:
            with open(full_path, "wb") as f:
                f.write(contents)

    def read(self, path: str) -> str:
        """Read contents from a file at the given path.

        Args:
            path: The file path to read from, relative to the root directory.

        Returns:
            The file contents as a string (decoded with UTF-8).

        Raises:
            FileNotFoundError: If the file does not exist.

        """
        full_path = self.get_full_path(path)
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    def list(self, path: str) -> list[str]:
        """List files and directories at the given path.

        Args:
            path: The directory path to list, relative to the root directory.

        Returns:
            A list of file and directory paths. Directory names end with "/".
            Returns an empty list if the directory does not exist
            (consistent with S3 API).

        Note:
            This method returns full paths relative to the root directory,
            not just the filenames.

        """
        full_path = self.get_full_path(path)
        if not os.path.exists(full_path):
            return []

        # If path is a file, return the file itself (S3-consistent behavior)
        if os.path.isfile(full_path):
            return [path]

        # Otherwise it's a directory, return its contents
        files = [os.path.join(path, f) for f in os.listdir(full_path)]
        files = [f + "/" if os.path.isdir(self.get_full_path(f)) else f for f in files]
        return files

    def delete(self, path: str) -> None:
        """Delete a file or directory at the given path.

        Args:
            path: The file or directory path to delete, relative to the root directory.

        Note:
            If the path does not exist, this method returns silently without error.
            For directories, all contents are recursively deleted.
            Any errors during deletion are logged but do not raise exceptions.

        """
        try:
            full_path = self.get_full_path(path)
            if not os.path.exists(full_path):
                logger.debug(f"Local path does not exist: {full_path}")
                return
            if os.path.isfile(full_path):
                os.remove(full_path)
                logger.debug(f"Removed local file: {full_path}")
            elif os.path.isdir(full_path):
                shutil.rmtree(full_path)
                logger.debug(f"Removed local directory: {full_path}")
        except Exception as e:
            logger.error(f"Error clearing local file store: {str(e)}")
