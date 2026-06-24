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
    from .measure import Measurement

from ._width import cell_len
from .box import SQUARE, Box
from .segment import Segment
from .style import Style
from .text import Text

_NEWLINE = Segment("\n")


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

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        """Measure the minimum and maximum width of the table.

        Args:
            console: The console to measure in.
            options: The console options.

        Returns:
            The minimum and maximum width of the table.
        """
        from .measure import Measurement

        ncols = len(self.columns)
        if ncols == 0:
            return Measurement(0, 0)

        overhead = (ncols + 1) + 2 * self.padding * ncols
        maximum = sum(self._natural_widths()) + overhead
        minimum = ncols + overhead  # One column per cell

        return Measurement(minimum, maximum)

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> Iterable[Segment]:
        """Render the table to the console.

        Args:
            console: The console to render to.
            options: The console options.

        Yields:
            Segments representing the table.
        """
        ncols = len(self.columns)
        if ncols == 0:
            return

        pad = self.padding
        widths = self._natural_widths()
        overhead = (ncols + 1) + 2 * pad * ncols
        widths = self._fit_to(widths, options.max_width - overhead)

        b, bs = self.box, self.border_style
        pad_str = " " * pad

        def hrule(left: str, mid: str, div: str, right: str) -> Iterable[Segment]:
            """Draw a horizontal rule using the given border characters and widths.

            Args:
                left: The left border character.
                mid: The mid border character.
                div: The divider character.
                right: The right border character.

            Returns:
                An iterable of segments representing the horizontal rule.
            """
            segs = [Segment(left, bs)]
            for i, w in enumerate(widths):
                if i:
                    segs.append(Segment(div, bs))

                segs.append(Segment(mid * (w + 2 * pad), bs))
            segs.append(Segment(right, bs))

            return segs

        def emit_row(cell_texts: list[Text], header: bool) -> Iterable[Segment]:
            """Emit a row of cells with the given texts and header style.

            Args:
                cell_texts: The texts to display in the row.
                header: Whether this is a header row.

            Yields:
                Segments representing the row's cells.
            """
            if header:
                bases = [c.header_style or self.header_style for c in self.columns]
            else:
                bases = [c.style for c in self.columns]

            cell_lines = [
                text.render_lines(w, col.justify, col.overflow, base)
                for text, w, col, base in zip(cell_texts, widths, self.columns, bases)
            ]
            height = max(len(cl) for cl in cell_lines)

            for li in range(height):
                line = [Segment(b.left, bs)]
                for ci, (cl, w, base) in enumerate(zip(cell_lines, widths, bases)):
                    if ci:
                        line.append(Segment(b.divider, bs))

                    fill = base if base else None
                    line.append(Segment(pad_str, fill))

                    if li < len(cl):
                        line.extend(cl[li])

                    else:
                        line.append(Segment(" " * w, fill))  # Blank line for short cell

                    line.append(Segment(pad_str, fill))

                line.append(Segment(b.right, bs))
                yield from line
                yield _NEWLINE

        yield from hrule(b.top_left, b.top, b.top_divider, b.top_right)
        yield _NEWLINE

        if self.show_header:
            yield from emit_row([Text(c.header) for c in self.columns], header=True)
            yield from hrule(b.head_left, b.head, b.head_divider, b.head_right)
            yield _NEWLINE

        for row in self.rows:
            yield from emit_row(row, header=False)

        yield from hrule(b.bottom_left, b.bottom, b.bottom_divider, b.bottom_right)
