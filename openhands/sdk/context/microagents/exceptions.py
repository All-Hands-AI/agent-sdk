"""Exception classes for microagent operations."""


class MicroagentError(Exception):
    """Base exception for all microagent errors."""

    pass


class MicroagentValidationError(MicroagentError):
    """Raised when there's a validation error in microagent metadata."""

    def __init__(self, message: str = "Microagent validation failed") -> None:
        """Initialize the validation error with a message."""
        super().__init__(message)
