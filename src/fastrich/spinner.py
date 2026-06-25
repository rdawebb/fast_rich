"""Spinner: an animated frame renderable.

Holds a frame set and interval; the current frame is chosen from elapsed time.
`__rich_console__` reads the monotonic clock (so manual re-prints animate);
`_segments_at` takes an explicit elapsed value for deterministic use/tests.
The auto-refresh loop that drives smooth animation is Live's job (Phase 7).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions
    from .style import Style
    from .text import Text

import time as _time

from .segment import Segment

# Name -> (frames, interval_seconds)
SPINNERS = {
    "dots": ("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏", 0.08),
    "line": ("-\\|/", 0.13),
}


class Spinner:
    """An animated frame renderable that displays a spinner."""

    def __init__(
        self,
        name: str = "dots",
        text: str | Text = "",
        *,
        style: Style | None = None,
        speed: float = 1.0,
    ) -> None:
        """Initialise a Spinner with the given name, text, style, and speed.

        Args:
            name: The name of the spinner to use.
            text: The text to display alongside the spinner.
            style: The style to apply to the spinner.
            speed: The speed of the spinner animation.
        """
        frames, interval = SPINNERS[name]
        self.frames = frames
        self.interval = interval / speed
        self.text = text
        self.style = style
        self._start = None

    def _segments_at(self, elapsed: float) -> Iterable[Segment]:
        """Yield the segments to display at the given elapsed time.

        Args:
            elapsed: The elapsed time since the spinner started.

        Yields:
            The segments to display at the given elapsed time.
        """
        idx = int(elapsed / self.interval) % len(self.frames)
        yield Segment(self.frames[idx], self.style)

        if self.text:
            label = self.text if isinstance(self.text, str) else self.text.plain
            yield Segment(" " + label)

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> Iterable[Segment]:
        if self._start is None:
            self._start = _time.monotonic()

        yield from self._segments_at(_time.monotonic() - self._start)
