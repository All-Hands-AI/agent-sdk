"""
Tiny convenience client for the OpenHands Agent SDK server.

Design goals:
- Small and dependency-light (httpx + pydantic already in your stack)
- Clean, typed, minimal API surface that mirrors server endpoints 1:1
- Useful docstrings and sensible defaults
"""

import os
import time
from typing import Any, Sequence

import httpx

from openhands.sdk.context import AgentContext
from openhands.sdk.event import Event, EventBase
from openhands.sdk.llm import LLM, ImageContent, TextContent
from openhands.sdk.logger import get_logger
from openhands.sdk.tool import ToolSpec


logger = get_logger(__name__)


class OpenHandsClient:
    """
    Thin client for the OpenHands Agent SDK server.

    Environment variables used by default:
      - OPENHANDS_SERVER_URL (default: http://localhost:9000)
      - MASTER_KEY (no default; required unless passed explicitly)
      - REQUEST_TIMEOUT (seconds; default: 300)

    Typical usage:
        from openhands.sdk.llm import LLM
        from openhands.sdk.tool import ToolSpec

        client = OpenHandsClient()
        cid, state = client.start_conversation(
            llm=LLM(model="...", base_url="...", api_key="..."),
            tools=[ToolSpec(name="BashTool", params={"working_dir": "/workspace"})],
        )
        state = client.send_message_and_run(cid, "Hello, world!")
        # optionally block until the run finishes:
        state = client.wait_until_idle(cid)
        events = client.get_events(cid)
        client.close_conversation(cid)
        client.close()
    """

    def __init__(
        self,
        *,
        server_url: str | None = None,
        master_key: str | None = None,
        request_timeout: float | None = None,
        httpx_client: httpx.Client | None = None,
    ) -> None:
        self.server_url = (
            server_url or os.getenv("OPENHANDS_SERVER_URL") or "http://localhost:9000"
        ).rstrip("/")
        self.master_key = master_key or os.getenv("MASTER_KEY") or ""
        self.request_timeout = float(
            request_timeout or os.getenv("REQUEST_TIMEOUT", 300)
        )

        if not self.master_key:
            raise RuntimeError("MASTER_KEY environment variable is not set.")

        self._client = httpx_client or httpx.Client(
            base_url=self.server_url,
            timeout=self.request_timeout,
            headers={
                "X-Master-Key": self.master_key,
                "Content-Type": "application/json",
            },
        )

    # --- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> "OpenHandsClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # --- low-level helper --------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_data: Any | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """
        Execute an HTTP request and return JSON (if any).

        Raises:
            httpx.HTTPError: on transport or non-2xx status.
        """
        try:
            r = self._client.request(method, path, json=json_data, params=params)
            r.raise_for_status()
            return r.json() if r.content else None
        except httpx.HTTPError:
            logger.error(
                "HTTP %s %s failed. content=%s",
                method,
                path,
                (r.content if "r" in locals() else b"<no response>"),  # type: ignore
                exc_info=True,
            )
            raise

    # --- endpoint coverage -------------------------------------------------
    # POST /conversations/  -> Start
    # GET  /conversations/  -> List
    # GET  /conversations/{conversation_id} -> Get state
    # GET  /conversations/{conversation_id}/events -> Get events
    # POST /conversations/{conversation_id}/messages -> Send message (and optional run)
    # POST /conversations/{conversation_id}/run -> Run (resume)
    # POST /conversations/{conversation_id}/pause -> Pause
    # POST /conversations/{conversation_id}/respond_to_confirmation -> Accept/Reject
    # DELETE /conversations/{conversation_id} -> Close

    def start_conversation(
        self,
        *,
        llm: LLM,
        tools: list[ToolSpec],
        mcp_config: dict[str, Any] | None = None,
        agent_context: AgentContext | None = None,
        confirmation_mode: bool = False,
    ) -> tuple[str, dict[str, Any]]:
        """
        Start a new conversation.

        Args:
            llm: LLM configuration to use.
            tools: Tool specifications to initialize the agent with.
            mcp_config: Optional MCP configuration to create MCP tools.
            agent_context: Optional agent context to seed the conversation.
            confirmation_mode: If True, agent pauses for action confirmations.

        Returns:
            (conversation_id, state_dict)
        """
        payload: dict[str, Any] = {
            "llm": llm.model_dump_with_secrets(),
            "tools": [t.model_dump() for t in tools],
            "mcp_config": mcp_config or None,
            "agent_context": agent_context,
            "confirmation_mode": confirmation_mode,
        }
        res = self._request("POST", "/conversations/", json_data=payload)
        return res["conversation_id"], res["state"]

    def list_conversations(
        self, *, start: int = 0, limit: int = 100
    ) -> list[dict[str, Any]]:
        """
        List active conversations (in insertion order).

        Args:
            start: Offset for pagination.
            limit: Max number of items to return.

        Returns:
            A list of objects with:
                - conversation_id: str
                - state: ConversationState (as dict)
        """
        return self._request(
            "GET",
            "/conversations/",
            params={"start": start, "limit": limit},
        )

    def get_conversation_state(self, conversation_id: str) -> dict[str, Any]:
        """
        Get the current ConversationState for a conversation.

        Args:
            conversation_id: ID returned from start_conversation.

        Returns:
            ConversationState as a dict.
        """
        return self._request("GET", f"/conversations/{conversation_id}")

    # Back-compat alias (if you already used get_state)
    get_state = get_conversation_state

    def get_events(
        self,
        conversation_id: str,
        *,
        start: int = 0,
        limit: int = 100,
    ) -> list[Event]:
        """
        Retrieve event history (paginated).

        Args:
            conversation_id: Conversation ID.
            start: Offset of the first event to return.
            limit: Maximum number of events.

        Returns:
            List[Event]
        """
        events = self._request(
            "GET",
            f"/conversations/{conversation_id}/events",
            params={"start": start, "limit": limit},
        )
        return [EventBase.model_validate(e) for e in events]

    def send_message(
        self,
        conversation_id: str,
        content: Sequence[TextContent | ImageContent],
        run: bool = True,
    ) -> dict[str, Any]:
        """
        Send a message to a conversation, with optional immediate run.

        Args:
            conversation_id: Conversation ID.
            role: One of {"user","system","assistant","tool"}.
            content: List of TextContent/ImageContent items.
            run: If True, trigger the agent run after sending.

        Returns:
            The updated conversation state (dict).
        """
        payload = {
            "role": "user",
            "content": [c.to_llm_dict() for c in content],
            "run": run,
        }
        res = self._request(
            "POST",
            f"/conversations/{conversation_id}/messages",
            json_data=payload,
        )
        # server returns {"message": ..., "run_started": ..., "state": ...}
        return res["state"]

    def run_conversation(self, conversation_id: str) -> dict[str, Any]:
        """
        Start or resume the agent run for a conversation.

        Behavior mirrors server:
          - If agent is already running or waiting for confirmation,
            returns current state.
          - Otherwise starts background execution and returns current state.

        Args:
            conversation_id: Conversation ID.

        Returns:
            Conversation state (dict).
        """
        res = self._request("POST", f"/conversations/{conversation_id}/run")
        return res["state"]

    def pause_conversation(self, conversation_id: str) -> None:
        """
        Request the agent to pause.

        Args:
            conversation_id: Conversation ID.

        Returns:
            None (no state change is guaranteed immediately).
        """
        self._request("POST", f"/conversations/{conversation_id}/pause")

    def respond_to_confirmation(
        self,
        conversation_id: str,
        *,
        accept: bool,
        reason: str = "",
    ) -> None:
        """
        Respond to a pending confirmation.

        Args:
            conversation_id: Conversation ID.
            accept: True to accept and continue; False to reject.
            reason: Optional rationale stored in the conversation.

        Returns:
            None
        """
        payload = {
            "accept": accept,
            "reason": reason or ("Accepted" if accept else "Rejected"),
        }
        self._request(
            "POST",
            f"/conversations/{conversation_id}/respond_to_confirmation",
            json_data=payload,
        )

    def close_conversation(self, conversation_id: str) -> None:
        """
        Close and remove a conversation on the server.

        Args:
            conversation_id: Conversation ID.

        Returns:
            None
        """
        self._request("DELETE", f"/conversations/{conversation_id}")

    # --- convenience helper ------------------------------------------------

    def wait_until_idle(
        self,
        conversation_id: str,
        *,
        poll_s: float = 1.0,
        max_wait_s: int = 600,
        auto_confirm: bool = True,
    ) -> dict[str, Any]:
        """
        Block until the agent run finishes (or timeout).

        If `auto_confirm` is True, it automatically accepts any pending
        confirmation with a generic reason.

        Args:
            conversation_id: Conversation ID.
            poll_s: Poll interval in seconds.
            max_wait_s: Maximum time to wait in seconds.
            auto_confirm: Auto-accept confirmation prompts to continue.

        Returns:
            Final ConversationState (dict).

        Raises:
            TimeoutError: If not idle within max_wait_s.
        """
        deadline = time.time() + max_wait_s
        while True:
            state = self.get_conversation_state(conversation_id)
            if state.get("agent_waiting_for_confirmation") and auto_confirm:
                self.respond_to_confirmation(
                    conversation_id, accept=True, reason="Auto-accept from client"
                )
            elif state.get("agent_finished"):
                return state

            if time.time() > deadline:
                raise TimeoutError("Timed out waiting for agent to finish.")
            time.sleep(poll_s)
