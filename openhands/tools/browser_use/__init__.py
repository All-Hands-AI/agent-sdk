"""Browser tools using browser-use integration."""

from openhands.tools.browser_use.definition import (
    BrowserClickAction,
    BrowserCloseTabAction,
    BrowserGetStateAction,
    BrowserGoBackAction,
    BrowserListTabsAction,
    BrowserNavigateAction,
    BrowserObservation,
    BrowserScrollAction,
    BrowserSwitchTabAction,
    BrowserTypeAction,
    browser_click_tool,
    browser_close_tab_tool,
    browser_get_state_tool,
    browser_go_back_tool,
    browser_list_tabs_tool,
    browser_navigate_tool,
    browser_scroll_tool,
    browser_switch_tab_tool,
    browser_type_tool,
)
from openhands.tools.browser_use.impl import BrowserToolExecutor


__all__ = [
    # Tool objects
    "browser_navigate_tool",
    "browser_click_tool",
    "browser_type_tool",
    "browser_get_state_tool",
    "browser_scroll_tool",
    "browser_go_back_tool",
    "browser_list_tabs_tool",
    "browser_switch_tab_tool",
    "browser_close_tab_tool",
    # Actions
    "BrowserNavigateAction",
    "BrowserClickAction",
    "BrowserTypeAction",
    "BrowserGetStateAction",
    "BrowserScrollAction",
    "BrowserGoBackAction",
    "BrowserListTabsAction",
    "BrowserSwitchTabAction",
    "BrowserCloseTabAction",
    # Observations
    "BrowserObservation",
    # Executor
    "BrowserToolExecutor",
]
