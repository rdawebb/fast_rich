"""Table: width-correct grid rendering that emits Segments.

Columns measure through the width engine, so CJK/emoji widths align. Cells fit
to their column with per-column justify and single-line overflow (`crop` /
`ellipsis`), or wrap with `fold`. When the natural grid exceeds the console
width, columns shrink proportionally.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Literal, NamedTuple, Sequence

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions
    from .measure import Measurement

from functools import lru_cache

from ._width import cell_len
from .box import HEAVY_HEAD, Box
from .segment import CachedBytes, Segment, _spaces, blank, compose_lines
from .style import NULL_STYLE, Style
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
    text: str, width: int, justify: str, base: Style | None
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
            segs.insert(0, blank(pad))

        elif justify == "center":
            left = pad // 2
            segs.insert(0, blank(left))
            segs.append(blank(pad - left))

        else:
            segs.append(blank(pad))

    return segs


class _RowFrame(NamedTuple):
    """Per-render constant Segments shared across every row of one render."""

    left: Segment | None  # Left border glyph, None when the edge is hidden
    divider: Segment  # Inter-column border glyph
    right: Segment | None  # Right border glyph, None when the edge is hidden
    pads: list[Segment]  # Per column: one cell-pad Segment, used both sides
    blanks: list[Segment]  # Per column: a full-width blank for a short cell


def _row_frame(
    glyphs: tuple[str, str, str],
    bs: Style | None,
    widths: list[int],
    bases,
    pad: int,
    edge: bool,
    row_style: Style | None = None,
) -> _RowFrame:
    """Build the shared border/padding Segments for one render's rows.

    Args:
        glyphs: The level's left, vertical and right border glyphs.
        bs: The border style.
        widths: The resolved column content widths.
        bases: The per-column base style.
        pad: The cell padding width.
        edge: Whether the outer left/right border glyphs are drawn.
        row_style: The row style, for backing a whitespace divider.

    Returns:
        The reusable border and padding Segments for the render.
    """
    left, vertical, right = glyphs
    pad_str = _spaces(pad)
    pads = []
    blanks = []
    for w, base in zip(widths, bases):
        fill = base if base else None
        pads.append(Segment(pad_str, fill))
        blanks.append(Segment(_spaces(w + 2 * pad), fill))

    ds = bs
    if row_style is not None and row_style.bgcolor and not vertical.strip():
        # A whitespace divider carries the row background
        bg = Style(bgcolor=row_style.bgcolor)
        ds = bg.combine(bs) if bs else bg

    return _RowFrame(
        Segment(left, bs) if edge else None,
        Segment(vertical, ds),
        Segment(right, bs) if edge else None,
        pads,
        blanks,
    )


@lru_cache(maxsize=512)
def _hrule(
    glyphs: tuple[str, str, str, str],
    widths: tuple[int, ...],
    pad: int,
    edge: bool,
    bs: Style | None,
) -> list[Segment]:
    """Build one horizontal rule, cached across renders.

    Args:
        glyphs: The rule's left, mid, divider and right glyphs.
        widths: The resolved column content widths.
        pad: The cell padding width.
        edge: Whether the outer left/right glyphs are drawn.
        bs: The border style.

    Returns:
        The horizontal rule as a single styled Segment, in a shared list.
    """
    left, mid, div, right = glyphs
    parts = [left] if edge else []
    for i, w in enumerate(widths):
        if i:
            parts.append(div)

        parts.append(mid * (w + 2 * pad))

    if edge:
        parts.append(right)

    return [Segment("".join(parts), bs)]


class Column:
    """A column that displays data in a table."""

    __slots__ = (
        "header",
        "footer",
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
        footer: str | Text = "",
        justify: Literal["left", "center", "right"] = "left",
        style: str | Style | None = None,
        header_style: str | Style | None = None,
        min_width: int | None = None,
        max_width: int | None = None,
        overflow: Literal["fold", "ellipsis", "crop"] | None = "ellipsis",
        no_wrap: bool = False,
    ) -> None:
        """Initialise a Column.

        Args:
            header: The column header text.
            footer: The column footer text (shown when show_footer=True).
            justify: How to justify the column content.
            style: The column content style.
            header_style: The column header style.
            min_width: The minimum width of the column.
            max_width: The maximum width of the column.
            overflow: How to handle overflowing content.
            no_wrap: Whether to disable wrapping of content.
        """
        self.header = header
        self.footer = footer
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
        box: Box = HEAVY_HEAD,
        padding: int = 1,
        show_header: bool = True,
        show_edge: bool = True,
        show_lines: bool = False,
        show_footer: bool = False,
        footer_style: str | Style | None = None,
        row_styles: Sequence[str | Style] | None = None,
        width: int | None = None,
        min_width: int | None = None,
        header_style: str | Style | None = None,
        border_style: str | Style | None = None,
        style: str | Style | None = None,
        expand: bool = False,
        title: str | Text = "",
        caption: str | Text = "",
        title_justify: Literal["left", "center", "right"] = "center",
        caption_justify: Literal["left", "center", "right"] = "center",
    ) -> None:
        """Initialise a Table with optional headers and styling.

        Args:
            *headers: The column headers as strings.
            box: The box style for the table.
            padding: The padding around the table.
            show_header: Whether to show the header row.
            show_edge: Draw the outer border (top/bottom rules and side edges).
            show_lines: Draw a rule between body rows.
            show_footer: Show a footer row built from each column's `footer`.
            footer_style: Style for the footer row.
            row_styles: Styles cycled across body rows (e.g. zebra striping).
            width: Fixed table width (content is fitted to it).
            min_width: Minimum table width.
            header_style: The style for the header row.
            border_style: The style for the table border.
            style: Base style for whole table, cell/column styles compose over.
            expand: If True, stretch columns to fill available width.
            title: The title shown above the table.
            caption: The caption shown below the table.
            title_justify: Title alignment, "left", "center", or "right".
            caption_justify: Caption alignment, "left", "center", or "right".
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
        self.show_edge = show_edge
        self.show_lines = show_lines
        self.show_footer = show_footer
        self.footer_style = footer_style
        self.row_styles = list(row_styles) if row_styles else []
        self.width = width
        self.min_width = min_width
        self.header_style = (
            header_style if header_style is not None else Style(bold=True)
        )
        self.border_style = border_style
        self.style = style or NULL_STYLE
        self.expand = expand
        self.title = title
        self.caption = caption
        self.title_justify = title_justify
        self.caption_justify = caption_justify

        for h in headers:
            self.add_column(h)

    def _bump(self) -> None:
        """Invalidate the byte cache and the resolve/width cache after a change."""
        self._content_version += 1
        self._dirty = True  # CachedBytes
        self._resolved = None  # Resolve + natural-width cache

    def _on_mark_dirty(self) -> None:
        """Invalidate the cache for the out-of-band path."""
        self._content_version += 1
        self._resolved = None
        n = len(self.rows)
        self._row_versions = [0] * n
        self._row_cache = [None] * n

    def add_column(self, header: str = "", **kwargs) -> Table:
        """Add a column to the table with the given header and styling.

        Args:
            header: The column header text.
            **kwargs: Additional styling arguments for the column.

        Returns:
            The updated table.
        """
        self.columns.append(Column(header, **kwargs))
        for row in self.rows:
            row.append("")  # New column's cell for pre-existing rows

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

            if self.show_footer and col.footer:
                w = max(w, cell_len(_cell_plain(col.footer)))

            if col.min_width:
                w = max(w, col.min_width)

            for row in rows:
                w = max(w, cell_len(_cell_plain(row[i])))

            if col.max_width:
                w = min(w, col.max_width)

            widths.append(max(w, 1))

        return widths

    def _fit_to(self, widths: list[int], avail: int, expand: bool = False) -> list[int]:
        """Fit the column widths to the available width, scaling as needed.

        Args:
            widths: The column widths.
            avail: The available width.
            expand: If True, expand columns proportionally to fill available width.

        Returns:
            The fitted column widths.
        """
        n = len(widths)
        if avail < n:
            return [1] * n

        total = sum(widths)
        if total <= avail:
            if not expand or total == avail or total == 0:
                return widths

            # Expand to fill, distrubute slack proportionally
            extra = avail - total
            grown = [w + extra * w // total for w in widths]
            diff = avail - sum(grown)

            i = 0
            while diff > 0:
                grown[i % n] += 1
                diff -= 1
                i += 1

            return grown

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
        overhead = self._border_cols(ncols) + 2 * self.padding * ncols
        maximum = sum(nat) + overhead
        minimum = ncols + overhead  # One column per cell

        return Measurement(minimum, maximum)

    def _border_cols(self, ncols: int) -> int:
        """Return the number of cells the vertical borders occupy.

        One divider between each pair of columns, plus the two outer edges when
        `show_edge` is on.

        Args:
            ncols: The number of columns.

        Returns:
            The width taken by the vertical borders.
        """
        return ncols + 1 if self.show_edge else ncols - 1

    def _framed_row_lines(
        self,
        cell_texts: list[str | Text],
        widths: list[int],
        bases: Sequence[Style | None],
        pad: int,
        frame: _RowFrame,
    ) -> list[list[Segment]]:
        """Render one row to a list of fully framed physical lines.

        Args:
            cell_texts: The cell texts.
            widths: The column widths.
            bases: The cell styles.
            pad: The padding.
            frame: The render's shared border/padding Segments.

        Returns:
            The fully framed physical lines of the row.
        """
        cell_lines = []  # Per cell: list[list[Segment]], content per physical line
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

        # The borders and cell-padding come from `frame`
        pads = frame.pads
        left, right = frame.left, frame.right
        out = []
        for li in range(height):
            line = [left] if left else []
            for ci, cl in enumerate(cell_lines):
                if ci:
                    line.append(frame.divider)

                if li < len(cl):
                    line.append(pads[ci])
                    line.extend(cl[li])
                    line.append(pads[ci])

                else:
                    line.append(frame.blanks[ci])  # Blank line for short cell

            if right:
                line.append(right)

            out.append(line)

        return out

    def _banner(
        self,
        console: Console,
        options: ConsoleOptions,
        text: str | Text,
        justify: str,
        width: int,
    ) -> list[Segment]:
        """Render a title/caption to one line justified within `width`.

        Args:
            console: The console to render to.
            options: The console options.
            text: The text to render.
            justify: The justification of the text, "left", "center", or "right".
            width: The width of the banner line.

        Returns:
            A list of segments representing the rendered banner line.
        """
        segs = list(console.render(text, options._replace(max_width=width)))
        used = sum(cell_len(s.text) for s in segs)
        space = max(0, width - used)

        if justify == "left":
            left = 0

        elif justify == "right":
            left = space

        else:
            left = space // 2

        return [blank(left), *segs, blank(space - left)]

    def _lines(self, console: Console, options: ConsoleOptions) -> list[list[Segment]]:
        """Render the table to a list of fully framed physical lines.

        Args:
            console: The console to render to.
            options: The console options.

        Returns:
            A list of fully framed physical lines.
        """
        ncols = len(self.columns)
        if ncols == 0:
            return []

        headers, rows, nat = self._resolve(console)
        pad = self.padding
        edge = self.show_edge
        overhead = self._border_cols(ncols) + 2 * pad * ncols

        avail = options.max_width
        expand = self.expand
        if self.width is not None:
            avail = min(self.width, options.max_width)
            expand = True  # Fixed width filled exactly

        elif self.min_width is not None:
            floor = min(self.min_width, options.max_width)
            if sum(nat) + overhead < floor:
                avail = floor  # Expand to fill available width
                expand = True

        widths = self._fit_to(nat, avail - overhead, expand)
        wkey = tuple(widths)  # Row reflows if the resolved widths change

        # A headed box drops its header-specific glyphs when there is no header
        b = self.box if self.show_header else self.box.get_plain_headed_box()
        bs = console.resolve_style(self.border_style)
        hstyle = console.resolve_style(self.header_style)
        col_styles = [console.resolve_style(c.style) for c in self.columns]
        col_hstyles = [console.resolve_style(c.header_style) for c in self.columns]
        fstyle = console.resolve_style(self.footer_style)
        row_styles = [console.resolve_style(rs) for rs in self.row_styles]

        table_w = sum(w + 2 * pad for w in widths) + self._border_cols(ncols)

        lines = []
        if self.title:
            lines.append(
                self._banner(console, options, self.title, self.title_justify, table_w)
            )

        if self.show_edge:
            lines.append(
                _hrule(
                    (b.top_left, b.top, b.top_divider, b.top_right),
                    wkey,
                    pad,
                    edge,
                    bs,
                )
            )

        if self.show_header:
            header_bases = [ch or hstyle for ch in col_hstyles]
            header_frame = _row_frame(
                (b.head_left, b.head_vertical, b.head_right),
                bs,
                widths,
                header_bases,
                pad,
                edge,
            )
            lines.extend(
                self._framed_row_lines(headers, widths, header_bases, pad, header_frame)
            )
            lines.append(
                _hrule(
                    (
                        b.head_row_left,
                        b.head_row_horizontal,
                        b.head_row_cross,
                        b.head_row_right,
                    ),
                    wkey,
                    pad,
                    edge,
                    bs,
                )
            )

        nstyles = len(row_styles)
        frames = {}

        def bases_and_frame(rs):
            """Return the combined bases and frame for a given row style.

            Args:
                rs: The row style to get the bases and frame for.

            Returns:
                A tuple of the combined bases and frame for the given row style."""
            key = rs._key if rs else None
            hit = frames.get(key)

            if hit is None:
                bases = (
                    [rs.combine(cs) if cs else rs for cs in col_styles]
                    if rs
                    else col_styles
                )
                hit = (
                    bases,
                    _row_frame(
                        (b.mid_left, b.mid_vertical, b.mid_right),
                        bs,
                        widths,
                        bases,
                        pad,
                        edge,
                        rs,
                    ),
                )
                frames[key] = hit

            return hit

        rule_line = (
            _hrule(
                (b.row_left, b.row_horizontal, b.row_cross, b.row_right),
                wkey,
                pad,
                edge,
                bs,
            )
            if self.show_lines
            else None
        )

        cache = self._row_cache
        versions = self._row_versions
        skey = tuple(rs._key if rs else None for rs in row_styles)

        for i, row in enumerate(rows):
            rs = row_styles[i % nstyles] if nstyles else None
            entry = cache[i]
            if (
                entry is not None
                and entry[0] == versions[i]
                and entry[1] == wkey
                and entry[3] == skey
            ):
                row_lines = entry[2]  # Clean row, reuse segments

            else:
                bases, frame = bases_and_frame(rs)
                row_lines = self._framed_row_lines(row, widths, bases, pad, frame)
                cache[i] = (versions[i], wkey, row_lines, skey)

            if rule_line is not None and i:
                lines.append(rule_line)

            lines.extend(row_lines)

        if self.show_footer:
            footers = [self._to_cell(c.footer, console) for c in self.columns]
            footer_bases = [fstyle or cs for cs in col_styles]
            footer_frame = _row_frame(
                (b.foot_left, b.foot_vertical, b.foot_right),
                bs,
                widths,
                footer_bases,
                pad,
                edge,
            )
            lines.append(
                _hrule(
                    (
                        b.foot_row_left,
                        b.foot_row_horizontal,
                        b.foot_row_cross,
                        b.foot_row_right,
                    ),
                    wkey,
                    pad,
                    edge,
                    bs,
                )
            )
            lines.extend(
                self._framed_row_lines(footers, widths, footer_bases, pad, footer_frame)
            )

        if self.show_edge:
            lines.append(
                _hrule(
                    (b.bottom_left, b.bottom, b.bottom_divider, b.bottom_right),
                    wkey,
                    pad,
                    edge,
                    bs,
                )
            )

        if self.caption:
            lines.append(
                self._banner(
                    console, options, self.caption, self.caption_justify, table_w
                )
            )

        return compose_lines(lines, console.resolve_style(self.style))

    def __rich_lines__(
        self, console: Console, options: ConsoleOptions
    ) -> list[list[Segment]]:
        """Lines protocol: hand back already-grouped lines (no newline segments).

        Args:
            console: The console to render to.
            options: The console options.

        Returns:
            A list of fully framed physical lines.
        """
        return self._lines(console, options)

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> Iterable[Segment]:
        """Flat segment stream for generic composition.

        Args:
            console: The console to render to.
            options: The console options.

        Yields:
            Segments representing the table.
        """
        first = True
        for line in self._lines(console, options):
            if not first:
                yield _NEWLINE

            first = False
            yield from line
