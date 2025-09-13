"""Base file storage interface."""

from abc import ABC, abstractmethod


class FileStore(ABC):
    """Abstract base class for file storage operations."""

    @abstractmethod
    def write(self, path: str, contents: str | bytes) -> None:
        """Write contents to a file at the specified path.

        Args:
            path: The file path to write to. Can be nested
                  (e.g., "folder/subfolder/file.txt").
            contents: The content to write, either as string or bytes.

        Note:
            If parent directories in the path don't exist, implementations should
            create them automatically.

        """
        pass

    @abstractmethod
    def read(self, path: str) -> str:
        """Read contents from a file at the specified path.

        Args:
            path: The file path to read from.

        Returns:
            The file contents as a string.

        Raises:
            FileNotFoundError: If the file does not exist.

        """
        pass

    @abstractmethod
    def list(self, path: str) -> list[str]:
        """List files and directories at the specified path.

        Args:
            path: The directory path to list.

        Returns:
            A list of file and directory names. Directory names end with "/".
            Returns an empty list if the directory does not exist.

        """
        pass

    @abstractmethod
    def delete(self, path: str) -> None:
        """Delete a file or directory at the specified path.

        Args:
            path: The file or directory path to delete.

        Note:
            If the path does not exist, implementations should handle this
            gracefully without raising an exception.

        """
        pass
