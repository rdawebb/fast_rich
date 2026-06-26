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
from .segment import CachedBytes, Segment
from .style import Style
from .text import Text

_NEWLINE = Segment("\n")


def _cell_plain(cell: "str | Text") -> str:
    """Return the plain text of a resolved cell (str stays as-is)."""
    return cell if isinstance(cell, str) else cell.plain


def _plain_line(
    text: str, width: int, justify: str, base: "Style | None"
) -> "list[Segment]":
    """Lay out one plain (span-free) cell line: a styled run plus padding.

    Byte-for-byte equivalent to `Text.render_lines` for a single line that
    fits its width with no spans and no ellipsis: the content is one run under
    the column's base style, justify padding is unstyled, and an empty cell
    yields no content segment (only padding), matching `range_segments`.

    Args:
        text: The cell's plain text (already known to fit `width`).
        width: The column content width.
        justify: How to justify within the column ("left", "center", "right").
        base: The column base style, or None.

    Returns:
        The line's segments.
    """
    style = base if base else None
    segs = [Segment(text, style)] if text else []

    pad = width - cell_len(text)
    if pad > 0:
        if justify == "right":
            segs.insert(0, Segment(" " * pad))

        elif justify == "center":
            left = pad // 2
            segs.insert(0, Segment(" " * left))
            segs.append(Segment(" " * (pad - left)))

        else:
            segs.append(Segment(" " * pad))

    return segs


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
        """Initialise a Column.

        Args:
            header: The column header text.
            justify: How to justify the column content.
            style: The column content style.
            header_style: The column header style.
            min_width: The minimum width of the column.
            max_width: The maximum width of the column.
            overflow: How to handle overflowing content.
            no_wrap: Whether to disable wrapping of content.
        """
        self.header = header
        self.justify = justify
        self.style = style
        self.header_style = header_style
        self.min_width = min_width
        self.max_width = max_width
        self.overflow = overflow
        self.no_wrap = no_wrap


class Table(CachedBytes):
    """A table that displays data in rows and columns."""

    def __init__(
        self,
        *headers: str,
        box: Box = SQUARE,
        padding: int = 1,
        show_header: bool = True,
        header_style: Style | None = None,
        border_style: Style | None = None,
    ) -> None:
        """Initialise a Table with optional headers and styling.

        Args:
            *headers: The column headers as strings.
            box: The box style for the table.
            padding: The padding around the table.
            show_header: Whether to show the header row.
            header_style: The style for the header row.
            border_style: The style for the table border.
        """
        self._init_byte_cache()
        self.columns: list[Column] = []
        self.rows: list[list[str | Text]] = []
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
        self._dirty = True

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

        row: list[str | Text] = list(cells)
        row.extend("" for _ in range(len(self.columns) - len(row)))
        self.rows.append(row)
        self._dirty = True

        return self

    def _to_cell(self, cell: str | Text, console: Console) -> str | Text:
        """Resolve a cell for one render, keeping plain strings as `str`.

        Only cells that need span handling become `Text`: an already-built
        `Text`, or a string carrying markup under the console's markup policy.
        Plain strings stay strings so the common case skips Text/Segment
        allocation in `emit_row`. Deferred to render time so the console's
        markup policy applies.

        Args:
            cell: The cell value, a string or an already-built Text.
            console: The console whose markup policy applies.

        Returns:
            The resolved cell: a plain `str`, or a `Text` for markup/Text cells.
        """
        if isinstance(cell, Text):
            return cell

        s = cell if type(cell) is str else str(cell)
        if console._markup and "[" in s:
            return console._str_to_text(s)

        return s

    def _resolve(
        self, console: Console
    ) -> tuple[list[str | Text], list[list[str | Text]]]:
        """Resolve headers and rows to cell grids for one render.

        Plain strings are preserved as `str`; only markup/`Text` cells become
        `Text` (see `_to_cell`).

        Args:
            console: The console whose markup policy applies.

        Returns:
            The resolved header and row cell grids.
        """
        headers = [self._to_cell(col.header, console) for col in self.columns]
        rows = [[self._to_cell(cell, console) for cell in row] for row in self.rows]

        return headers, rows

    def _natural_widths(
        self, headers: list[str | Text], rows: list[list[str | Text]]
    ) -> list[int]:
        widths = []
        for i, col in enumerate(self.columns):
            w = cell_len(_cell_plain(headers[i])) if self.show_header else 0

            if col.min_width:
                w = max(w, col.min_width)

            for row in rows:
                w = max(w, cell_len(_cell_plain(row[i])))

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

        headers, rows = self._resolve(console)
        overhead = (ncols + 1) + 2 * self.padding * ncols
        maximum = sum(self._natural_widths(headers, rows)) + overhead
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

        headers, rows = self._resolve(console)
        pad = self.padding
        widths = self._natural_widths(headers, rows)
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

        def emit_row(cell_texts: list[str | Text], header: bool) -> Iterable[Segment]:
            """Emit a row of cells with the given texts and header style.

            Args:
                cell_texts: The cells to display in the row (str or Text).
                header: Whether this is a header row.

            Yields:
                Segments representing the row's cells.
            """
            if header:
                bases = [c.header_style or self.header_style for c in self.columns]
            else:
                bases = [c.style for c in self.columns]

            cell_lines = []
            for cell, w, col, base in zip(cell_texts, widths, self.columns, bases):
                # Fast lane: a plain string that fits its column on one line
                # needs no Text/span machinery, just a single styled run + pad.
                if (
                    isinstance(cell, str)
                    and col.overflow != "fold"
                    and "\n" not in cell
                    and cell_len(cell) <= w
                ):
                    cell_lines.append([_plain_line(cell, w, col.justify, base)])
                else:
                    text = cell if isinstance(cell, Text) else Text(cell)
                    cell_lines.append(
                        text.render_lines(w, col.justify, col.overflow, base)
                    )

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
            yield from emit_row(headers, header=True)
            yield from hrule(b.head_left, b.head, b.head_divider, b.head_right)
            yield _NEWLINE

        for row in rows:
            yield from emit_row(row, header=False)

        yield from hrule(b.bottom_left, b.bottom, b.bottom_divider, b.bottom_right)
