import os


def get_llm_metadata(
    model_name: str,
    agent_name: str,
    session_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    import openhands.sdk

    openhands_tools_version: str = "n/a"
    try:
        import openhands.tools

        openhands_tools_version = openhands.tools.__version__
    except ModuleNotFoundError:
        pass

    metadata = {
        "trace_version": openhands.sdk.__version__,
        "tags": [
            f"model:{model_name}",
            f"agent:{agent_name}",
            f"web_host:{os.environ.get('WEB_HOST', 'unspecified')}",
            f"openhands_version:{openhands.sdk.__version__}",
            f"openhands_tools_version:{openhands_tools_version}",
        ],
    }
    if session_id is not None:
        metadata["session_id"] = session_id
    if user_id is not None:
        metadata["trace_user_id"] = user_id
    return metadata
