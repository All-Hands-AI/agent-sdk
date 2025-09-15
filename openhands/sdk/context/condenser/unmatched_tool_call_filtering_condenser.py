from openhands.sdk.context.condenser.base import CondenserBase
from openhands.sdk.context.view import View
from openhands.sdk.event.condenser import Condensation


class UnmatchedToolCallFilteringCondenser(CondenserBase):
    """A condenser that filters out tool-call events that don't have a matching pair."""

    def condense(self, view: View) -> View | Condensation:
        return View(events=self.filter_unmatched_tool_calls(view.events))
