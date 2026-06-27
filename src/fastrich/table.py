"""Table: width-correct grid rendering that emits Segments.

Columns measure through the width engine, so CJK/emoji widths align. Cells fit
to their column with per-column justify and single-line overflow (`crop` /
`ellipsis`), or wrap with `fold`. When the natural grid exceeds the console
width, columns shrink proportionally.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Sequence

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions
    from .measure import Measurement

from ._width import cell_len
from .box import SQUARE, Box
from .segment import CachedBytes, Segment
from .style import Style
from .text import Text

_NEWLINE = Segment("\n")


def _cell_plain(cell: str | Text) -> str:
    """Return the plain text of a resolved cell (str stays as-is).

    Args:
        cell: The cell value, either a str or a Text.

    Returns:
        The plain text of the cell.
    """
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

        # Per-row segment cache, parallel to rows
        self._row_versions: list[int] = []
        self._row_cache: list = []  # (version, wkey, lines) | None

        # Whole-table + resolve invalidation: any mutation bumps this
        self._content_version = 0
        # Cached (headers, rows, natural_widths) for one (version, markup) pair
        self._resolved = None

        self.box: Box = box
        self.padding = padding
        self.show_header = show_header
        self.header_style = (
            header_style if header_style is not None else Style(bold=True)
        )
        self.border_style = border_style
        for h in headers:
            self.add_column(h)

    def _bump(self) -> None:
        """Invalidate the byte cache and the resolve/width cache after a change."""
        self._content_version += 1
        self._dirty = True  # CachedBytes
        self._resolved = None  # Resolve + natural-width cache

    def _on_mark_dirty(self) -> None:
        """Invalidate the resolve/width cache for the out-of-bound path.

        Out-of-band mutation may have resized `rows` directly, so resync both
        parallel arrays to the current row count, not just `_row_cache`.
        """
        self._content_version += 1
        self._resolved = None
        self._row_versions = [0] * len(self.rows)
        self._row_cache = [None] * len(self.rows)

    def add_column(self, header: str = "", **kwargs) -> Table:
        """Add a column to the table with the given header and styling.

        Args:
            header: The column header text.
            **kwargs: Additional styling arguments for the column.

        Returns:
            The updated table.
        """
        self.columns.append(Column(header, **kwargs))
        self._row_cache = [None] * len(self.rows)  # Structure changed
        self._bump()

        return self

    def add_row(self, *cells: "str | Text") -> Table:
        """Add a row to the table with the given cells.

        Args:
            *cells: The cell values to add, one per column.

        Returns:
            The updated table.

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
        self._row_versions.append(0)
        self._row_cache.append(None)
        self._bump()

        return self

    def update_cell(self, row: int, column: int, value: "str | Text") -> "Table":
        """Replace a single cell, marking that row dirty and invalidating caches.

        Keeps a plain `str` as `str` so the cell stays on the `_plain_line` fast
        lane; only non-str/non-Text values are stringified.

        Raises:
            IndexError: If the row or column index is out of range.
        """
        if not 0 <= row < len(self.rows):
            raise IndexError(
                f"row {row} out of range (table has {len(self.rows)} rows)"
            )

        if not 0 <= column < len(self.columns):
            raise IndexError(
                f"column {column} out of range (table has {len(self.columns)} columns)"
            )

        self.rows[row][column] = value if isinstance(value, (str, Text)) else str(value)
        self._row_versions[row] += 1  # Version mismatch invalidates this row
        self._bump()  # Invalidate + resolve/width cache

        return self

    def _to_cell(self, cell: str | Text, console: Console) -> str | Text:
        """Resolve a cell for one render, keeping plain strings as `str`.

        Only cells that need span handling become `Text`: an already-built
        `Text`, or a string carrying markup under the console's markup policy.
        Plain strings stay strings so the common case skips Text/Segment
        allocation in `_framed_row_lines`. Deferred to render time so the console's
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
    ) -> tuple[list[str | Text], list[list[str | Text]], list[int]]:
        """Resolve headers/rows and the natural column widths, cached per render.

        Resolution and the width scan both depend on the markup policy and are
        both O(n), so they are computed once per `(content version, markup)` and
        reused until the next mutation. Returns `(headers, rows, natural_widths)`.

        Args:
            console: The console whose markup policy applies.

        Returns:
            The resolved headers, rows, and natural column widths.
        """
        key = (self._content_version, console._markup)
        cached = self._resolved
        if cached is not None and cached[0] == key:
            return cached[1]

        headers = [self._to_cell(col.header, console) for col in self.columns]
        rows = [[self._to_cell(cell, console) for cell in row] for row in self.rows]
        nat = self._natural_widths(headers, rows)

        self._resolved = (key, (headers, rows, nat))

        return headers, rows, nat

    def _natural_widths(
        self, headers: list[str | Text], rows: list[list[str | Text]]
    ) -> list[int]:
        """Compute the natural content width of each column.

        Args:
            headers: The table headers.
            rows: The table rows.

        Returns:
            The natural column widths.
        """
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
        """Fit the column widths to the available width, scaling as needed.

        Args:
            widths: The column widths.
            avail: The available width.

        Returns:
            The fitted column widths.
        """
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

        _, _, nat = self._resolve(console)
        overhead = (ncols + 1) + 2 * self.padding * ncols
        maximum = sum(nat) + overhead
        minimum = ncols + overhead  # One column per cell

        return Measurement(minimum, maximum)

    def _framed_row_lines(
        self,
        cell_texts: list[str | Text],
        widths: list[int],
        bases: Sequence[Style | None],
        pad: int,
    ) -> list[list[Segment]]:
        """Render one row to a list of fully framed physical lines.

        Args:
            cell_texts: The cell texts.
            widths: The column widths.
            bases: The cell styles.
            pad: The padding.

        Returns:
            The fully framed physical lines of the row.
        """
        b, bs = self.box, self.border_style
        pad_str = " " * pad

        cell_lines = []
        for text, w, col, base in zip(cell_texts, widths, self.columns, bases):
            # Fast lane: plain strings that fit columns on one line
            if (
                isinstance(text, str)
                and col.overflow != "fold"
                and "\n" not in text
                and cell_len(text) <= w
            ):
                cell_lines.append([_plain_line(text, w, col.justify, base)])

            else:
                t = text if isinstance(text, Text) else Text(text)
                cell_lines.append(t.render_lines(w, col.justify, col.overflow, base))

        height = max((len(cl) for cl in cell_lines), default=1)

        out = []
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
            out.append(line)

        return out

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> Iterable[Segment]:
        """Render the table to Segments (runs only on a byte-cache miss).

        Args:
            console: The console to render to.
            options: The console options.

        Yields:
            Segments representing the table.
        """
        ncols = len(self.columns)
        if ncols == 0:
            return

        headers, rows, nat = self._resolve(console)
        pad = self.padding
        overhead = (ncols + 1) + 2 * pad * ncols
        widths = self._fit_to(nat, options.max_width - overhead)
        wkey = tuple(widths)  # Row reflows if the resolved widths change

        b, bs = self.box, self.border_style

        def hrule(left: str, mid: str, div: str, right: str) -> list[Segment]:
            """Render a horizontal rule with the given glyphs and widths.

            Args:
                left: The left glyph.
                mid: The mid glyph.
                div: The divider glyph.
                right: The right glyph.

            Returns:
                The horizontal rule as a list of segments.
            """
            segs = [Segment(left, bs)]
            for i, w in enumerate(widths):
                if i:
                    segs.append(Segment(div, bs))

                segs.append(Segment(mid * (w + 2 * pad), bs))
            segs.append(Segment(right, bs))

            return segs

        lines = [hrule(b.top_left, b.top, b.top_divider, b.top_right)]

        if self.show_header:
            header_bases = [c.header_style or self.header_style for c in self.columns]
            lines.extend(self._framed_row_lines(headers, widths, header_bases, pad))
            lines.append(hrule(b.head_left, b.head, b.head_divider, b.head_right))

        body_bases = [c.style for c in self.columns]
        cache = self._row_cache
        versions = self._row_versions

        for i, row in enumerate(rows):
            entry = cache[i]
            if entry is not None and entry[0] == versions[i] and entry[1] == wkey:
                row_lines = entry[2]  # Clean row, reuse segments

            else:
                row_lines = self._framed_row_lines(row, widths, body_bases, pad)
                cache[i] = (versions[i], wkey, row_lines)

            lines.extend(row_lines)

        lines.append(hrule(b.bottom_left, b.bottom, b.bottom_divider, b.bottom_right))

        first = True
        for line in lines:
            if not first:
                yield _NEWLINE

            first = False
            yield from line
