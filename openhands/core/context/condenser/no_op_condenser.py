from openhands.core.context.condenser.condenser import Condenser
from openhands.core.context.view import View
from openhands.core.event.context import Condensation


class NoOpCondenser(Condenser):
    """Simple condenser that returns a view un-manipulated.

    Primarily intended for testing purposes.
    """
    def condense(self, view: View) -> View | Condensation:
        return view
