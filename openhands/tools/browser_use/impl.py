"""Browser tool executor implementation using browser-use MCP server wrapper."""

import asyncio
import logging
import threading

from openhands.sdk.tool import ToolExecutor
from openhands.tools.browser_use.server import CustomBrowserUseServer


# Suppress browser-use logging for cleaner integration
logging.getLogger("browser_use").setLevel(logging.WARNING)


class BrowserToolExecutor(ToolExecutor):
    """Executor that wraps browser-use MCP server for OpenHands integration."""

    def __init__(
        self,
        session_timeout_minutes: int = 30,
        headless: bool = True,
        allowed_domains: list[str] | None = None,
        **config,
    ):
        self._server = CustomBrowserUseServer(
            session_timeout_minutes=session_timeout_minutes
        )
        self._config = {
            "headless": headless,
            "allowed_domains": allowed_domains or [],
            **config,
        }
        self._initialized = False

        # Persistent background loop
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, name="BrowserExecutorLoop", daemon=True
        )
        self._thread.start()

    def __call__(self, action):
        """Submit an action to run in the background loop and wait for result."""
        future = asyncio.run_coroutine_threadsafe(
            self._execute_action(action), self._loop
        )
        return future.result()  # blocks until done

    async def _execute_action(self, action):
        """Execute browser action asynchronously."""
        from openhands.tools.browser_use.definition import (
            BrowserClickAction,
            BrowserCloseTabAction,
            BrowserGetContentAction,
            BrowserGetStateAction,
            BrowserGoBackAction,
            BrowserListTabsAction,
            BrowserNavigateAction,
            BrowserObservation,
            BrowserScrollAction,
            BrowserSwitchTabAction,
            BrowserTypeAction,
        )

        try:
            result = ""
            # Route to appropriate method based on action type
            if isinstance(action, BrowserNavigateAction):
                result = await self.navigate(action.url, action.new_tab)
            elif isinstance(action, BrowserClickAction):
                result = await self.click(action.index, action.new_tab)
            elif isinstance(action, BrowserTypeAction):
                result = await self.type_text(action.index, action.text)
            elif isinstance(action, BrowserGetStateAction):
                result = await self.get_state(action.include_screenshot)
            elif isinstance(action, BrowserGetContentAction):
                result = await self.get_content(
                    action.extract_links, action.start_from_char
                )
            elif isinstance(action, BrowserScrollAction):
                result = await self.scroll(action.direction)
            elif isinstance(action, BrowserGoBackAction):
                result = await self.go_back()
            elif isinstance(action, BrowserListTabsAction):
                result = await self.list_tabs()
            elif isinstance(action, BrowserSwitchTabAction):
                result = await self.switch_tab(action.tab_id)
            elif isinstance(action, BrowserCloseTabAction):
                result = await self.close_tab(action.tab_id)
            else:
                error_msg = f"Unsupported action type: {type(action)}"
                return BrowserObservation(output="", error=error_msg)

            return BrowserObservation(output=result)
        except Exception as e:
            error_msg = f"Browser operation failed: {str(e)}"
            logging.error(error_msg, exc_info=True)
            return BrowserObservation(output="", error=error_msg)

    async def _ensure_initialized(self):
        """Ensure browser session is initialized."""
        if not self._initialized:
            # Initialize browser session with our config
            await self._server._init_browser_session(**self._config)
            self._initialized = True

    # Navigation & Browser Control Methods
    async def navigate(self, url: str, new_tab: bool = False) -> str:
        """Navigate to a URL."""
        await self._ensure_initialized()
        return await self._server._navigate(url, new_tab)

    async def go_back(self) -> str:
        """Go back in browser history."""
        await self._ensure_initialized()
        return await self._server._go_back()

    # TODO: `wait` tool is missing in browser-use MCP server

    # Page Interaction
    async def click(self, index: int, new_tab: bool = False) -> str:
        """Click an element by index."""
        await self._ensure_initialized()
        return await self._server._click(index, new_tab)

    async def type_text(self, index: int, text: str) -> str:
        """Type text into an element."""
        await self._ensure_initialized()
        return await self._server._type_text(index, text)

    # TODO: `upload_file_to_element` tool is missing in browser-use MCP server

    async def scroll(self, direction: str = "down") -> str:
        """Scroll the page."""
        await self._ensure_initialized()
        return await self._server._scroll(direction)

    # TODO: `scroll_to_text` tool is missing in browser-use MCP server
    # TODO: `send_keys` tool is missing in browser-use MCP server

    async def get_state(self, include_screenshot: bool = False) -> str:
        """Get current browser state with interactive elements."""
        await self._ensure_initialized()
        return await self._server._get_browser_state(include_screenshot)

    # Tab Management
    async def list_tabs(self) -> str:
        """List all open tabs."""
        await self._ensure_initialized()
        return await self._server._list_tabs()

    async def switch_tab(self, tab_id: str) -> str:
        """Switch to a different tab."""
        await self._ensure_initialized()
        return await self._server._switch_tab(tab_id)

    async def close_tab(self, tab_id: str) -> str:
        """Close a specific tab."""
        await self._ensure_initialized()
        return await self._server._close_tab(tab_id)

    # Content Extraction
    async def get_content(self, extract_links: bool, start_from_char: int) -> str:
        """Extract page content, optionally with links."""
        await self._ensure_initialized()
        return await self._server._get_content(
            extract_links=extract_links, start_from_char=start_from_char
        )

    # Form Controls
    # TODO: `get_dropdown_options` tool is missing in browser-use MCP server
    # TODO: `select_dropdown_option` tool is missing in browser-use MCP server

    async def close_browser(self) -> str:
        """Close the browser session."""
        if self._initialized:
            result = await self._server._close_browser()
            self._initialized = False
            return result
        return "No browser session to close"

    async def cleanup(self):
        """Cleanup browser resources."""
        try:
            await self.close_browser()
            if hasattr(self._server, "_close_all_sessions"):
                await self._server._close_all_sessions()
        except Exception as e:
            logging.warning(f"Error during browser cleanup: {e}")

    def __del__(self):
        """Cleanup on deletion."""
        if self._initialized:
            try:
                # Try to cleanup, but don't block if event loop is closed
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.cleanup())
            except Exception:
                pass  # Ignore cleanup errors during deletion
