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
    from .style import Style

from ._width import cell_len
from .segment import LineRenderable, Segment, blank, compose_lines
from .style import NULL_STYLE


def _normalise(pad) -> tuple[int, int, int, int]:
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

    def __init__(
        self, renderable, pad=(0, 1), *, style: Style | None = None, expand: bool = True
    ) -> None:
        """Initialise a Padding instance.

        Args:
            renderable: The renderable to wrap.
            pad: The padding to add around the renderable.
            style: Base style, child style composes over it.
            expand: If True, pad out to the full available width, else size
                to the content plus padding.
        """
        self.renderable = renderable
        self.pad = _normalise(pad)
        self.style = style or NULL_STYLE
        self.expand = expand

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

        used_per = [sum(cell_len(seg.text) for seg in line) for line in child_lines]

        if self.expand:
            content = inner  # Pad to full available width

        else:
            content = min(inner, max(used_per, default=0))  # Fit to content width

        full = left + content + right
        rows = []
        blank_row = [blank(full)]
        for _ in range(top):
            rows.append(blank_row)

        for line, used in zip(child_lines, used_per):
            rows.append([blank(left), *line, blank(max(0, content - used) + right)])

        for _ in range(bottom):
            rows.append(blank_row)

        return compose_lines(rows, self.style)
