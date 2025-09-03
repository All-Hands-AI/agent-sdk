from openhands.core.tool import ToolExecutor
from openhands.tools.execute_bash.bash_session import BashSession
from openhands.tools.execute_bash.definition import (
    ExecuteBashAction,
    ExecuteBashObservation,
)


class BashExecutor(ToolExecutor):
    def __init__(
        self,
        working_dir: str,
        username: str | None = None,
    ):
        self.session = BashSession(working_dir, username=username)
        self.session.initialize()

    def __call__(self, action: ExecuteBashAction) -> ExecuteBashObservation:
        return self.session.execute(action)
