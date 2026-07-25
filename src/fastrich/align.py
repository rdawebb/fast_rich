"""Align: position a renderable within the available width (and optional height).

Aligns the rendered block as a unit: the block's max line width sets the offset,
lines keep their relative layout. Vertical alignment applies only when a height
is given.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions
    from .style import Style

from ._width import cell_len
from .measure import measure
from .segment import CachedBytes, LineRenderable, Segment, blank, compose_lines


class Align(CachedBytes, LineRenderable):
    """Position a renderable within the available width (and optional height).

    Cached bytes assume the aligned renderable is stable after construction.
    Reassigning `align.renderable` or mutating a nested child in place is not
    tracked, call `mark_dirty()` afterwards.
    """

    def __init__(
        self,
        renderable,
        align: Literal["left", "center", "right"] = "left",
        *,
        vertical: Literal["top", "middle", "bottom"] | None = None,
        height: int | None = None,
        style: str | Style | None = None,
    ) -> None:
        """Initialise an Align instance.

        Args:
            renderable: The renderable to align.
            align: The alignment to apply ("left", "center", or "right").
            vertical: The vertical alignment to apply (if height is given).
            height: The height to align within (if vertical is given).
            style: The style to apply to the aligned renderable.
        """
        self._init_byte_cache()
        self.renderable = renderable
        self.align = align
        self.vertical = vertical
        self.height = height
        self.style = style

    @classmethod
    def center(cls, renderable, **kwargs) -> Align:
        """Center the renderable horizontally.

        Args:
            renderable: The renderable to align.
            **kwargs: Additional keyword arguments to pass to the Align constructor.

        Returns:
            An Align instance with the renderable centered horizontally.
        """
        return cls(renderable, "center", **kwargs)

    @classmethod
    def left(cls, renderable, **kwargs) -> Align:
        """Align the renderable to the left.

        Args:
            renderable: The renderable to align.
            **kwargs: Additional keyword arguments to pass to the Align constructor.

        Returns:
            An Align instance with the renderable aligned to the left.
        """
        return cls(renderable, "left", **kwargs)

    @classmethod
    def right(cls, renderable, **kwargs) -> Align:
        """Align the renderable to the right.

        Args:
            renderable: The renderable to align.
            **kwargs: Additional keyword arguments to pass to the Align constructor.

        Returns:
            An Align instance with the renderable aligned to the right.
        """
        return cls(renderable, "right", **kwargs)

    def _lines(self, console: Console, options: ConsoleOptions) -> list[list[Segment]]:
        """Align the renderable within the available width and return the lines of styled segments.

        Args:
            console: The console instance to use for rendering.
            options: The console options to use for rendering.

        Returns:
            A list of lists of styled segments for the aligned renderable.
        """
        width = options.max_width
        target = max(0, min(measure(console, self.renderable, options).maximum, width))
        lines = console.render_lines(
            self.renderable, options._replace(max_width=target)
        )
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
                row.append(blank(offset))

            row.extend(line)
            right = width - offset - u
            if right > 0:
                row.append(blank(right))

            rows.append(row)

        if self.height and self.vertical:
            blank_row = [blank(width)]
            extra = self.height - len(rows)
            if extra > 0:
                if self.vertical == "bottom":
                    rows = [blank_row] * extra + rows

                elif self.vertical == "middle":
                    t = extra // 2
                    rows = [blank_row] * t + rows + [blank_row] * (extra - t)

                else:
                    rows = rows + [blank_row] * extra

        return compose_lines(rows, console.resolve_style(self.style))
