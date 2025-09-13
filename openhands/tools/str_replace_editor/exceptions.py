"""Exception classes for the str_replace_editor tool."""


class ToolError(Exception):
    """Raised when a tool encounters an error."""

    def __init__(self, message):
        """Initialize ToolError with a message."""
        self.message = message
        super().__init__(message)

    def __str__(self):
        """Return string representation of the error."""
        return self.message


class EditorToolParameterMissingError(ToolError):
    """Raised when a required parameter is missing for a tool command."""

    def __init__(self, command, parameter):
        """Initialize EditorToolParameterMissingError with command and parameter."""
        self.command = command
        self.parameter = parameter
        self.message = f"Parameter `{parameter}` is required for command: {command}."


class EditorToolParameterInvalidError(ToolError):
    """Raised when a parameter is invalid for a tool command."""

    def __init__(self, parameter, value, hint=None):
        """Initialize EditorToolParameterInvalidError with parameter details."""
        self.parameter = parameter
        self.value = value
        self.message = (
            f"Invalid `{parameter}` parameter: {value}. {hint}"
            if hint
            else f"Invalid `{parameter}` parameter: {value}."
        )


class FileValidationError(ToolError):
    """Raised when a file fails validation checks (size, type, etc.)."""

    def __init__(self, path: str, reason: str):
        """Initialize FileValidationError with path and reason."""
        self.path = path
        self.reason = reason
        self.message = f"File validation failed for {path}: {reason}"
        super().__init__(self.message)
