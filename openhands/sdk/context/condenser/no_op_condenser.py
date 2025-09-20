from openhands.sdk.context.condenser.base import PipelinableCondenserBase
from openhands.sdk.context.view import View
from openhands.sdk.event.condenser import Condensation


class NoOpCondenser(PipelinableCondenserBase):
    """Simple condenser that returns a view un-manipulated.

    Primarily intended for testing purposes.
    """

    def condense(self, view: View) -> View | Condensation:
        return view
