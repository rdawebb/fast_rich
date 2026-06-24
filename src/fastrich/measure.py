"""Measurement protocol.

`Measurement(minimum, maximum)` is the smallest width a renderable can render
in without losing content and the width it would take if unconstrained. Renderables
expose this via `__rich_measure__`; layout primitives use it to render children at
their natural width instead of always filling the available space.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions

from ._width import cell_len

RICH_MEASURE = "__rich_measure__"


class Measurement(NamedTuple):
    """A measurement of the minimum and maximum width of a renderable."""

    minimum: int
    maximum: int

    def normalise(self) -> "Measurement":
        """Normalise measurement with minimum >= 0 and minimum <= maximum.

        Returns:
            Normalised Measurement object.
        """
        minimum = max(0, min(self.minimum, self.maximum))

        return Measurement(minimum, max(minimum, self.maximum))

    def with_maximum(self, width: int) -> "Measurement":
        """Measure with the maximum width clamped to the given width.

        Args:
            width: Maximum width to clamp to.

        Returns:
            Measurement object with clamped width.
        """
        return Measurement(min(self.minimum, width), min(self.maximum, width))

    def clamp(self, min_width=None, max_width=None) -> "Measurement":
        """Clamp the measurement to the given minimum and maximum width.

        Args:
            min_width: Minimum width to clamp to.
            max_width: Maximum width to clamp to.

        Returns:
            Clamped Measurement object.
        """
        minimum, maximum = self.minimum, self.maximum
        if min_width is not None:
            minimum = max(minimum, min_width)
            maximum = max(maximum, min_width)

        if max_width is not None:
            minimum = min(minimum, max_width)
            maximum = min(maximum, max_width)

        return Measurement(minimum, maximum)


def measure_str(text: str, width: int) -> Measurement:
    """Measure a plain string: minimum = longest word, maximum = longest line.

    Args:
        text: The string to measure.
        width: The maximum width to clamp to.

    Returns:
        Measurement object with minimum and maximum width.
    """
    lines = text.split("\n")
    maximum = max((cell_len(line) for line in lines), default=0)
    minimum = max(
        (cell_len(word) for line in lines for word in line.split(" ")), default=0
    )

    return Measurement(minimum, maximum).with_maximum(width).normalise()


def measure(console: Console, renderable, options: ConsoleOptions) -> Measurement:
    """Resolve the Measurement for any renderable.

    Args:
        console: The console to render with.
        renderable: The renderable to measure.
        options: The options to use for rendering.

    Returns:
        Measurement object with minimum and maximum width.
    """
    width = options.max_width
    if isinstance(renderable, str):
        return measure_str(renderable, width)

    if hasattr(renderable, RICH_MEASURE):
        m = getattr(renderable, RICH_MEASURE)(console, options)

        return m.with_maximum(width).normalize()

    # Fallback: render and measure the widest produced line
    from .segment import split_lines

    lines = list(split_lines(list(console.render(renderable, options))))
    mx = max((sum(cell_len(s.text) for s in line) for line in lines), default=0)

    return Measurement(min(mx, width), min(mx, width))
