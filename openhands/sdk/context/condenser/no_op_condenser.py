from openhands.sdk.context.condenser.condenser import Condenser
from openhands.sdk.context.view import View
from openhands.sdk.event.condenser import Condensation


class NoOpCondenser(Condenser):
    """Simple condenser that returns a view un-manipulated.

    Primarily intended for testing purposes.
    """

    def condense(self, view: View) -> View | Condensation:
        return view
