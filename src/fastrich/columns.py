"""Columns: tile renderables into a grid that fills the available width.

Equal-width columns by default (column width = widest item). Items are placed
row-major; each grid row is as tall as its tallest cell, shorter cells blank-
filled. Items wider than the resolved column width are cropped (per-line, style-
preserving).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions

from ._width import cell_len
from .segment import Segment, split_lines

_NEWLINE = Segment("\n")


def _fit_line(line: list[Segment], width: int) -> list[Segment]:
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
                c = cell_len(ch)
                if w + c > remain:
                    break

                acc.append(ch)
                w += c

            if acc:
                out.append(Segment("".join(acc), seg.style))

            total += w
            break

    if total < width:
        out.append(Segment(" " * (width - total)))

    return out


class Columns:
    """Layout renderables into columns."""

    def __init__(
        self, renderables, *, padding: int = 1, width: int | None = None
    ) -> None:
        """Initialise a Columns layout with the given renderables and optional padding and width.

        Args:
            renderables: The renderables to layout into columns.
            padding: The padding between columns.
            width: The fixed column width override.
        """
        self.renderables = list(renderables)
        self.padding = padding
        self.width = width  # Fixed column width override

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> Iterable[Segment]:
        """Layout the renderables into columns.

        Args:
            console: The console to render to.
            options: The console options.

        Yields:
            The segments representing the layout.
        """
        items = self.renderables
        if not items:
            return

        avail = options.max_width
        gutter = self.padding

        rendered = []
        for it in items:
            lines = list(split_lines(list(console.render(it, options))))
            w = max((sum(cell_len(s.text) for s in line) for line in lines), default=0)
            rendered.append((lines, w))

        col_w = self.width or max(w for _, w in rendered)
        col_w = max(1, min(col_w, avail))
        ncols = max(1, (avail + gutter) // (col_w + gutter))

        cells = [[_fit_line(line, col_w) for line in lines] for lines, _ in rendered]

        rows = []
        for base in range(0, len(cells), ncols):
            group = cells[base : base + ncols]
            height = max(len(c) for c in group)
            for li in range(height):
                row = []
                for ci, cell in enumerate(group):
                    if ci:
                        row.append(Segment(" " * gutter))

                    if li < len(cell):
                        row.extend(cell[li])

                    else:
                        row.append(Segment(" " * col_w))

                rows.append(row)

        for i, row in enumerate(rows):
            if i:
                yield _NEWLINE

            yield from row
