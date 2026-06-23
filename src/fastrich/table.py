"""Table: width-correct grid rendering that emits Segments.

Columns measure through the width engine, so CJK/emoji widths align.
Cells fit to their column with per-column justify and single-line overflow
(`crop` / `ellipsis`). When the natural grid exceeds the console width,
columns shrink proportionally.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions

from ._width import cell_len
from .box import SQUARE, Box
from .segment import Segment
from .style import NULL_STYLE, Style
from .text import Text

_NEWLINE = Segment("\n")


def _crop(text: str, width: int) -> str:
    """Truncate `text` to exactly `width` columns.

    Args:
        text: The text to crop.
        width: The desired width in columns.

    Returns:
        The cropped text.
    """
    if width <= 0:
        return ""

    total = 0
    out = []
    for ch in text:
        cw = cell_len(ch)
        if total + cw > width:
            break

        out.append(ch)
        total += cw

    if total < width:
        out.append(" " * (width - total))

    return "".join(out)


def _fit(text: str, width: int, justify: str, overflow: str) -> str:
    """Return `text` rendered to exactly `width` columns.

    Args:
        text: The text to fit.
        width: The desired width in columns.
        justify: The justification of the text.
        overflow: The overflow behavior.

    Returns:
        The fitted text.
    """
    w = cell_len(text)
    if w == width:
        return text

    if w < width:
        pad = width - w
        if justify == "right":
            return " " * pad + text

        if justify == "center":
            left = pad // 2
            return " " * left + text + " " * (pad - left)

        return text + " " * pad

    # overflow: w > width
    if overflow == "ellipsis" and width >= 1:
        return _crop(text, width - 1) + "…"

    return _crop(text, width)  # Crop (and fold, until wrapping lands)


class Column:
    """A column that displays data in a table."""

    __slots__ = (
        "header",
        "justify",
        "style",
        "header_style",
        "min_width",
        "max_width",
        "overflow",
        "no_wrap",
    )

    def __init__(
        self,
        header: str = "",
        *,
        justify: str = "left",
        style: Style | None = None,
        header_style: Style | None = None,
        min_width: int | None = None,
        max_width: int | None = None,
        overflow: str = "ellipsis",
        no_wrap: bool = False,
    ) -> None:
        """Initialise a Column."""
        self.header = header
        self.justify = justify
        self.style = style
        self.header_style = header_style
        self.min_width = min_width
        self.max_width = max_width
        self.overflow = overflow
        self.no_wrap = no_wrap


class Table:
    """A table that displays data in rows and columns."""

    def __init__(
        self,
        *headers,
        box: Box = SQUARE,
        padding: int = 1,
        show_header: bool = True,
        header_style: Style | None = None,
        border_style: Style | None = None,
    ) -> None:
        """Initialise a Table with optional headers and styling."""
        self.columns: list[Column] = []
        self.rows: list[list[Text]] = []
        self.box: Box = box
        self.padding = padding
        self.show_header = show_header
        self.header_style = (
            header_style if header_style is not None else Style(bold=True)
        )
        self.border_style = border_style
        for h in headers:
            self.add_column(h)

    def add_column(self, header: str = "", **kwargs) -> "Table":
        """Add a column to the table with the given header and styling.

        Args:
            header: The header text for the column.
            **kwargs: Additional styling options for the column.

        Returns:
            The Table instance.
        """
        self.columns.append(Column(header, **kwargs))

        return self

    def add_row(self, *cells: str | Text) -> "Table":
        """Add a row to the table with the given cells.

        Args:
            *cells: The cells to add to the row.

        Returns:
            The Table instance.

        Raises:
            ValueError: If the number of cells exceeds the number of columns.
        """
        if len(cells) > len(self.columns):
            raise ValueError(
                f"row has {len(cells)} cells but table has {len(self.columns)} columns"
            )

        row = [c if isinstance(c, Text) else Text(str(c)) for c in cells]
        row.extend(Text("") for _ in range(len(self.columns) - len(row)))
        self.rows.append(row)

        return self

    def _natural_widths(self) -> list[int]:
        widths = []
        for i, col in enumerate(self.columns):
            w = cell_len(col.header) if self.show_header else 0

            if col.min_width:
                w = max(w, col.min_width)

            for row in self.rows:
                w = max(w, row[i].cell_len)

            if col.max_width:
                w = min(w, col.max_width)

            widths.append(max(w, 1))

        return widths

    def _fit_to(self, widths: list[int], avail: int) -> list[int]:
        n = len(widths)
        if avail < n:
            return [1] * n

        total = sum(widths)
        if total <= avail:
            return widths

        scaled = [max(1, w * avail // total) for w in widths]
        diff = avail - sum(scaled)
        i = 0
        while diff > 0:
            scaled[i % n] += 1
            diff -= 1
            i += 1

        while diff < 0:
            j = scaled.index(max(scaled))
            if scaled[j] <= 1:
                break

            scaled[j] -= 1
            diff += 1

        return scaled

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> Iterable[Segment]:
        ncols = len(self.columns)
        if ncols == 0:
            return

        pad = self.padding
        widths = self._natural_widths()
        overhead = (ncols + 1) + 2 * pad * ncols
        widths = self._fit_to(widths, options.max_width - overhead)

        b, bs = self.box, self.border_style

        def hrule(left: str, mid: str, div: str, right: str) -> Iterable[Segment]:
            segs = [Segment(left, bs)]
            for i, w in enumerate(widths):
                if i:
                    segs.append(Segment(div, bs))

                segs.append(Segment(mid * (w + 2 * pad), bs))
            segs.append(Segment(right, bs))

            return segs

        def row_segments(cells: list[Text], header: bool) -> Iterable[Segment]:
            segs = [Segment(b.left, bs)]
            for i, (text, w, col) in enumerate(zip(cells, widths, self.columns)):
                if i:
                    segs.append(Segment(b.divider, bs))

                fitted = _fit(text.plain, w, col.justify, col.overflow)
                content = f"{' ' * pad}{fitted}{' ' * pad}"
                if header:
                    base = col.header_style or self.header_style

                else:
                    base = col.style or NULL_STYLE
                    if text.style:
                        base = base.combine(text.style)

                segs.append(Segment(content, base if base else None))
            segs.append(Segment(b.right, bs))

            return segs

        yield from hrule(b.top_left, b.top, b.top_divider, b.top_right)
        yield _NEWLINE

        if self.show_header:
            header_cells = [Text(c.header) for c in self.columns]
            yield from row_segments(header_cells, header=True)
            yield _NEWLINE
            yield from hrule(b.head_left, b.head, b.head_divider, b.head_right)
            yield _NEWLINE

        for row in self.rows:
            yield from row_segments(row, header=False)
            yield _NEWLINE

        yield from hrule(b.bottom_left, b.bottom, b.bottom_divider, b.bottom_right)
