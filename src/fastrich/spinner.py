"""Spinner: an animated frame renderable.

Holds a frame set and interval; the current frame is chosen from elapsed time.
`__rich_console__` reads the monotonic clock (so manual re-prints animate);
`_segments_at` takes an explicit elapsed value for deterministic use/tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions
    from .style import Style
    from .text import Text

import time as _time

from ._spinners import SPINNERS
from ._width import cell_len
from .segment import Segment, encode_line


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
        spinner = SPINNERS[name]
        frames = spinner["frames"]
        width = max(cell_len(frame) for frame in frames)  # Prevent trailing text shift
        self.frames = [frame + " " * (width - cell_len(frame)) for frame in frames]
        self.interval = (
            spinner["interval"] / 1000.0
        ) / speed  # cli-spinners ms -> seconds
        self.text = text
        self.style = style
        self._start: float | None = None

        # Fixed per-tick Segment set: frames and label never change between ticks
        self._frame_segments = [Segment(frame, style) for frame in self.frames]
        label = text if isinstance(text, str) else text.plain
        self._label_segment = Segment(" " + label) if label else None
        self._byte_cache: dict[tuple, bytes] = {}

    def frame_index(self) -> int:
        """The index of the frame the spinner would draw right now.

        Starts the clock on first call, callers cache against this, so it changes
        exactly when the drawn frame changes.

        Returns:
            The current frame index.
        """
        if self._start is None:
            self._start = _time.monotonic()

        elapsed = _time.monotonic() - self._start

        return int(elapsed / self.interval) % len(self._frame_segments)

    def _segments_at(self, elapsed: float) -> Iterable[Segment]:
        """Yield the segments to display at the given elapsed time.

        Args:
            elapsed: The elapsed time since the spinner started.

        Yields:
            The segments to display at the given elapsed time.
        """
        idx = int(elapsed / self.interval) % len(self._frame_segments)
        yield self._frame_segments[idx]

        if self._label_segment is not None:
            yield self._label_segment

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> Iterable[Segment]:
        """Generate the segments to display the spinner.

        Args:
            console: The console to render to.
            options: The console options.

        Yields:
            The segments to display the spinner.
        """
        yield self._frame_segments[self.frame_index()]

        if self._label_segment is not None:
            yield self._label_segment

    def __rich_bytes__(self, console: Console, options: ConsoleOptions) -> bytes:
        """Return the encoded bytes for the current frame, without a trailing end.

        Reads the monotonic clock (like `__rich_console__`, so manual re-prints
        animate) and returns bytes memoised per `(idx, no_color, encoding)`. The
        frame Segments and label are immutable after init, so the cache never
        needs invalidating and is naturally bounded by the frame count.

        Args:
            console: The console to render to.
            options: The console options for this render.

        Returns:
            The encoded bytes for the current frame.
        """
        idx = self.frame_index()
        no_color, encoding = console.no_color, console.encoding
        key = (idx, no_color, encoding)

        cached = self._byte_cache.get(key)
        if cached is None:
            line = (self._frame_segments[idx],)
            if self._label_segment is not None:
                line += (self._label_segment,)

            cached = encode_line(line, no_color, encoding)
            self._byte_cache[key] = cached

        return cached
