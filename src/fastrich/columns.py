"""Columns: tile renderables into a grid that fills the available width.

Equal-width columns by default (column width = widest item). Items are placed
row-major; each grid row is as tall as its tallest cell, shorter cells blank-
filled. Items wider than the resolved column width are cropped (per-line, style-
preserving).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions
    from .style import Style

from ._width import cell_len, char_cell_len
from .measure import measure
from .segment import CachedBytes, LineRenderable, Segment, blank, compose_lines
from .style import NULL_STYLE


def _fit_line(line: Sequence[Segment], width: int) -> list[Segment]:
    """Pad or crop one line (list of Segments) to exactly `width` columns.

    Args:
        line: The line to fit, as a list of Segments.
        width: The target width in terminal columns.

    Returns:
        The fitted line, as a list of Segments.
    """
    out = []
    total = 0
    for seg in line:
        if total >= width:
            break

        cw = cell_len(seg.text)
        if total + cw <= width:
            out.append(seg)
            total += cw

        else:
            remain = width - total
            acc, w = [], 0
            for ch in seg.text:
                c = char_cell_len(ch)
                if w + c > remain:
                    break

                acc.append(ch)
                w += c

            if acc:
                out.append(Segment("".join(acc), seg.style))

            total += w
            break

    if total < width:
        out.append(blank(width - total))

    return out


class Columns(CachedBytes, LineRenderable):
    """Layout renderables into columns.

    Cached bytes assume the items are stable after construction. Mutating the
    `renderables` list or a nested child in place is not tracked, call
    `mark_dirty()` afterwards.
    """

    def __init__(
        self,
        renderables,
        *,
        padding: int = 1,
        width: int | None = None,
        style: Style | None = None,
    ) -> None:
        """Initialise a Columns layout with the given renderables and optional padding and width.

        Args:
            renderables: The renderables to layout into columns.
            padding: The padding between columns.
            width: The fixed column width override.
            style: The style to apply to the columns.
        """
        self._init_byte_cache()
        self.renderables = list(renderables)
        self.padding = padding
        self.width = width  # Fixed column width override
        self.style = style or NULL_STYLE

    def _lines(self, console: Console, options: ConsoleOptions) -> list[list[Segment]]:
        """Layout the renderables into columns.

        Args:
            console: The console to render to.
            options: The console options.

        Returns:
            A list of rows, each row is a list of segments.
        """
        items = self.renderables
        if not items:
            return []

        avail = options.max_width
        gutter = self.padding

        natural = self.width or max(
            (measure(console, it, options).maximum for it in items), default=1
        )
        col_w = max(1, min(natural, avail))
        ncols = max(1, (avail + gutter) // (col_w + gutter))

        cells = []
        for it in items:
            lines = console.render_lines(it, options._replace(max_width=col_w))
            cells.append([_fit_line(line, col_w) for line in lines])

        rows = []
        for base in range(0, len(cells), ncols):
            group = cells[base : base + ncols]
            height = max(len(c) for c in group)
            for li in range(height):
                row = []
                for ci, cell in enumerate(group):
                    if ci:
                        row.append(blank(gutter))

                    if li < len(cell):
                        row.extend(cell[li])

                    else:
                        row.append(blank(col_w))

                rows.append(row)

        return compose_lines(rows, self.style)
