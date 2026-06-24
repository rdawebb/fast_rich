"""Align: position a renderable within the available width (and optional height).

Aligns the rendered block as a unit: the block's max line width sets the offset,
lines keep their relative layout. Vertical alignment applies only when a height
is given.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Literal

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions

from ._width import cell_len
from .segment import Segment, split_lines

_NEWLINE = Segment("\n")


class Align:
    """Position a renderable within the available width (and optional height)."""

    def __init__(
        self,
        renderable,
        align: Literal["left", "center", "right"] = "left",
        *,
        vertical: Literal["top", "middle", "bottom"] | None = None,
        height: int | None = None,
    ) -> None:
        """Initialise an Align instance.

        Args:
            renderable: The renderable to align.
            align: The alignment to apply ("left", "center", or "right").
            vertical: The vertical alignment to apply (if height is given).
            height: The height to align within (if vertical is given).
        """
        self.renderable = renderable
        self.align = align
        self.vertical = vertical
        self.height = height

    @classmethod
    def center(cls, renderable, **kwargs) -> "Align":
        """Center the renderable horizontally.

        Args:
            renderable: The renderable to align.
            **kwargs: Additional keyword arguments to pass to the Align constructor.

        Returns:
            An Align instance with the renderable centered horizontally.
        """
        return cls(renderable, "center", **kwargs)

    @classmethod
    def left(cls, renderable, **kwargs) -> "Align":
        """Align the renderable to the left.

        Args:
            renderable: The renderable to align.
            **kwargs: Additional keyword arguments to pass to the Align constructor.

        Returns:
            An Align instance with the renderable aligned to the left.
        """
        return cls(renderable, "left", **kwargs)

    @classmethod
    def right(cls, renderable, **kwargs) -> "Align":
        """Align the renderable to the right.

        Args:
            renderable: The renderable to align.
            **kwargs: Additional keyword arguments to pass to the Align constructor.

        Returns:
            An Align instance with the renderable aligned to the right.
        """
        return cls(renderable, "right", **kwargs)

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> Iterable[list[Segment]]:
        """Yield styled segments for the aligned renderable.

        Args:
            console: The console instance to use for rendering.
            options: The console options to use for rendering.

        Yields:
            An iterable of styled segments for the aligned renderable.
        """
        width = options.max_width
        lines = list(split_lines(list(console.render(self.renderable, options))))
        used = [sum(cell_len(s.text) for s in line) for line in lines]
        block = min(max(used, default=0), width)

        if self.align == "right":
            offset = width - block

        elif self.align == "center":
            offset = (width - block) // 2

        else:
            offset = 0

        rows = []
        for line, u in zip(lines, used):
            row = []
            if offset > 0:
                row.append(Segment(" " * offset))

            row.extend(line)
            right = width - offset - u
            if right > 0:
                row.append(Segment(" " * right))

            rows.append(row)

        if self.height and self.vertical:
            blank = [Segment(" " * width)]
            extra = self.height - len(rows)
            if extra > 0:
                if self.vertical == "bottom":
                    rows = [blank] * extra + rows

                elif self.vertical == "middle":
                    t = extra // 2
                    rows = [blank] * t + rows + [blank] * (extra - t)

                else:
                    rows = rows + [blank] * extra

        for i, row in enumerate(rows):
            if i:
                yield _NEWLINE

            yield from row
