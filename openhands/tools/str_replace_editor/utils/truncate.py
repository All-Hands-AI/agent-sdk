from .config import MAX_RESPONSE_LEN_CHAR
from .prompts import CONTENT_TRUNCATED_NOTICE


def maybe_truncate(
    content: str,
    truncate_after: int | None = MAX_RESPONSE_LEN_CHAR,
    truncate_notice: str = CONTENT_TRUNCATED_NOTICE,
) -> str:
    """
    Truncate content and append a notice if content exceeds the specified length.
    """
    return (
        content
        if not truncate_after or len(content) <= truncate_after
        else content[:truncate_after] + truncate_notice
    )
