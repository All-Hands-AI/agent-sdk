"""LLM-related exception classes."""


class LLMError(Exception):
    """Base class for all LLM-related exceptions."""

    def __init__(self, message: str) -> None:
        """Initialize LLMError with a message."""
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        """Return string representation of the error message."""
        return self.message


class LLMMalformedActionError(LLMError):
    """Exception raised when the LLM response is malformed or does not conform to the expected format."""  # noqa: E501

    def __init__(self, message: str = "Malformed response") -> None:
        """Initialize LLMMalformedActionError with a message."""
        super().__init__(message)


class LLMNoActionError(LLMError):
    """Exception raised when the LLM response does not include an action."""

    def __init__(self, message: str = "Agent must return an action") -> None:
        """Initialize LLMNoActionError with a message."""
        super().__init__(message)


class LLMResponseError(LLMError):
    """Exception raised when the LLM response does not include an action or the action is not of the expected type."""  # noqa: E501

    def __init__(
        self, message: str = "Failed to retrieve action from LLM response"
    ) -> None:
        """Initialize LLMResponseError with a message."""
        super().__init__(message)


class LLMNoResponseError(LLMError):
    """Exception raised when the LLM does not return a response.

    Typically seen in Gemini models.

    This exception should be retried
    Typically, after retry with a non-zero temperature, the LLM will return a response
    """

    def __init__(
        self,
        message: str = "LLM did not return a response. This is only seen in Gemini models so far.",  # noqa: E501
    ) -> None:
        """Initialize LLMNoResponseError with a message."""
        super().__init__(message)


class LLMContextWindowExceedError(LLMError):
    """Exception raised when LLM context window limit is exceeded."""

    def __init__(
        self,
        message: str = "Conversation history longer than LLM context window limit. Consider turning on enable_history_truncation config to avoid this error",  # noqa: E501
    ) -> None:
        """Initialize LLMContextWindowExceedError with a message."""
        super().__init__(message)


# ============================================
# LLM function calling Exceptions
# ============================================


class FunctionCallConversionError(LLMError):
    """Exception raised when FunctionCallingConverter failed to convert.

    Failed to convert a non-function call message to a function call message.

    This typically happens when there's a malformed message (e.g., missing
    <function=...> tags). But not due to LLM output.
    """

    def __init__(self, message: str) -> None:
        """Initialize FunctionCallConversionError with a message."""
        super().__init__(message)


class FunctionCallValidationError(LLMError):
    """Exception raised when FunctionCallingConverter failed to validate.

    Failed to validate a function call message.

    This typically happens when the LLM outputs unrecognized function call /
    parameter names / values.
    """

    def __init__(self, message: str) -> None:
        """Initialize FunctionCallValidationError with a message."""
        super().__init__(message)


class FunctionCallNotExistsError(LLMError):
    """Exception raised when an LLM call a tool that is not registered."""

    def __init__(self, message: str) -> None:
        """Initialize FunctionCallNotExistsError with a message."""
        super().__init__(message)


# ============================================
# Other Exceptions
# ============================================


class UserCancelledError(Exception):
    """Exception raised when user cancels a request."""

    def __init__(self, message: str = "User cancelled the request") -> None:
        """Initialize UserCancelledError with a message."""
        super().__init__(message)


class OperationCancelled(Exception):
    """Exception raised when an operation is cancelled (e.g. by a keyboard interrupt)."""  # noqa: E501

    def __init__(self, message: str = "Operation was cancelled") -> None:
        """Initialize OperationCancelled with a message."""
        super().__init__(message)
