# rolling_view.py
import logging
import sys
from typing import Callable
from collections import deque
from contextlib import contextmanager
from .logger import IN_CI

RenderFnType = Callable[[], str]
class _RollingViewHandler(logging.Handler):
    def __init__(self, max_lines: int, use_live: bool):
        super().__init__()
        self._buf = deque(maxlen=max_lines)
        self._use_live = use_live
        self._live = None  # lazy to avoid Rich import when unused
        self.render_fn: RenderFnType | None = None

    def __enter__(self):
        if self._use_live:
            from rich.live import Live  # import only when needed
            self._live = Live("", refresh_per_second=8)
            self._live.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        # Freeze final frame
        if self._use_live and self._live is not None:
            self._live.update("\n".join(self._buf))
            self._live.__exit__(exc_type, exc, tb)

    def emit(self, record: logging.LogRecord):
        msg = self.format(record)
        self._buf.append(msg)
        if self._use_live and self._live:
            self._live.update(self.render_fn() if self.render_fn else "\n".join(self._buf))
        else:
            # CI / non-TTY -> pass-through one-line print (no repaint)
            # Avoid double newlines; the formatter shouldn’t add a trailing \n
            sys.stdout.write(msg + "\n")
            sys.stdout.flush()

    @property
    def snapshot(self) -> str:
        return "\n".join(self._buf)

@contextmanager
def rolling_log_view(
    logger: logging.Logger,
    max_lines: int = 40,
    level: int = logging.INFO,
    also_propagate: bool = False,
    header: str | None = None,
    footer: str | None = None,
):
    """
    Temporarily attach a rolling view handler that renders the last N log lines.
    - Local TTY & not CI: pretty, live-updating view (Rich.Live)
    - CI / non-TTY: plain line-by-line (no terminal control)
    By default, propagation is disabled to avoid double-printing.
    """
    is_tty = sys.stdout.isatty()
    use_live = (not IN_CI) and is_tty

    handler = _RollingViewHandler(max_lines=max_lines, use_live=use_live)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(message)s"))

    prev_propagate = logger.propagate
    logger.propagate = bool(also_propagate)
    logger.addHandler(handler)

    def _render() -> str:
        parts = []
        if header:
            parts.append(header.rstrip() + "\n" + "=" * len(header))
        parts.append("\n".join(handler._buf))
        if footer:
            parts.append("=" * len(footer) + "\n" + footer.rstrip())
        return "\n".join(parts)

    try:
        if use_live:
            from rich.live import Live
            with Live(_render(), refresh_per_second=8) as live:
                handler._live = live
                handler.render_fn = _render  # attach for updates
                yield handler
        else:
            yield handler
    finally:
        if handler._live:
            handler._live.update(_render())
        logger.removeHandler(handler)
        logger.propagate = prev_propagate
