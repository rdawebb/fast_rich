"""Padding: surround a renderable with blank space.

`pad` accepts an int (all sides), a (vertical, horizontal) pair, or a
(top, right, bottom, left) tuple. Lines are rendered at the reduced inner width
and each output line is padded to the full available width, so the block is
rectangular for nesting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions


from ._width import cell_len
from .segment import LineRenderable, Segment, blank


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


class Padding(LineRenderable):
    """A wrapper around a renderable that adds padding around it."""

    def __init__(self, renderable, pad=(0, 1)) -> None:
        """Initialise a Padding instance.

        Args:
            renderable: The renderable to wrap.
            pad: The padding to add around the renderable.
        """
        self.renderable = renderable
        self.pad = _normalise(pad)

    def _lines(self, console: Console, options: ConsoleOptions) -> list[list[Segment]]:
        """Render the wrapped renderable with padding around it.

        Args:
            console: The console to render to.
            options: The console options.

        Returns:
            The padded lines as a list of lists of segments.
        """
        top, right, bottom, left = self.pad
        full = options.max_width
        inner = max(0, full - left - right)

        child_lines = console.render_lines(
            self.renderable, options._replace(max_width=inner)
        )

        rows = []
        blank_row = [blank(full)]
        for _ in range(top):
            rows.append(blank_row)

        for line in child_lines:
            used = sum(cell_len(seg.text) for seg in line)
            rows.append([blank(left), *line, blank(inner - used + right)])

        for _ in range(bottom):
            rows.append(blank_row)

        return rows
