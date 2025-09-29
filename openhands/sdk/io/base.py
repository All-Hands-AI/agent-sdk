from abc import ABC, abstractmethod


class FileStore(ABC):
    """Abstract base class for file storage operations.

    This class defines the interface for file storage backends that can
    handle basic file operations like reading, writing, listing, and deleting files.
    """

    @abstractmethod
    def write(self, path: str, contents: str | bytes) -> None:
        """Write contents to a file at the specified path.

        Args:
            path: The file path where contents should be written.
            contents: The data to write, either as string or bytes.

        Raises:
            IOError: If the write operation fails.
            PermissionError: If write access is denied.
        """

    @abstractmethod
    def read(self, path: str) -> str:
        """Read and return the contents of a file as a string.

        Args:
            path: The file path to read from.

        Returns:
            The file contents as a string.

        Raises:
            FileNotFoundError: If the file does not exist.
            IOError: If the read operation fails.
            PermissionError: If read access is denied.
        """

    @abstractmethod
    def list(self, path: str) -> list[str]:
        """List all files and directories at the specified path.

        Args:
            path: The directory path to list contents from.

        Returns:
            A list of file and directory names in the specified path.

        Raises:
            FileNotFoundError: If the directory does not exist.
            NotADirectoryError: If the path is not a directory.
            PermissionError: If list access is denied.
        """

    @abstractmethod
    def delete(self, path: str) -> None:
        """Delete the file or directory at the specified path.

        Args:
            path: The file or directory path to delete.

        Raises:
            FileNotFoundError: If the file or directory does not exist.
            PermissionError: If delete access is denied.
            OSError: If the deletion operation fails.
        """
