"""Padding: surround a renderable with blank space.

`pad` accepts an int (all sides), a (vertical, horizontal) pair, or a
(top, right, bottom, left) tuple. Lines are rendered at the reduced inner width
and each output line is padded to the full available width, so the block is
rectangular for nesting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions


from ._width import cell_len
from .segment import Segment, split_lines

_NEWLINE = Segment("\n")


def _normalise(
    pad,
) -> tuple[int, int, int, int]:
    """Normalise the pad value to a (top, right, bottom, left) tuple.

    Args:
        pad: The pad value to normalise.

    Returns:
        A (top, right, bottom, left) tuple.
    """
    if isinstance(pad, int):
        return (pad, pad, pad, pad)

    if len(pad) == 2:
        v, h = pad
        return (v, h, v, h)

    if len(pad) == 4:
        return tuple(pad)

    raise ValueError("pad must be int, (v, h), or (top, right, bottom, left)")


class Padding:
    """A wrapper around a renderable that adds padding around it."""

    def __init__(self, renderable, pad=(0, 1)) -> None:
        """Initialise a Padding instance.

        Args:
            renderable: The renderable to wrap.
            pad: The padding to add around the renderable.
        """
        self.renderable = renderable
        self.pad = _normalise(pad)

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> Iterable[Segment]:
        """Render the wrapped renderable with padding around it.

        Args:
            console: The console to render to.
            options: The console options.

        Yields:
            The styled segments for the padded renderable.
        """
        top, right, bottom, left = self.pad
        full = options.max_width
        inner = max(0, full - left - right)

        child_lines = list(
            split_lines(
                list(console.render(self.renderable, options._replace(max_width=inner)))
            )
        )

        rows = []
        blank = [Segment(" " * full)]
        for _ in range(top):
            rows.append(blank)

        for line in child_lines:
            used = sum(cell_len(seg.text) for seg in line)
            row = [Segment(" " * left), *line, Segment(" " * (inner - used + right))]
            rows.append(row)

        for _ in range(bottom):
            rows.append(blank)

        for i, row in enumerate(rows):
            if i:
                yield _NEWLINE

            yield from row
