"""Columns: tile renderables into a grid that fills the available width.

The column count comes from an iterative fit: start with one column per item,
walk the items in grid order keeping a per-column running maximum width, and
restart with fewer columns whenever the running total overflows. Column widths
are then sized to each column's own content. Cells wrap word-wise with ellipsis
overflow, rows are as tall as their tallest cell, and every line is padded to
the full table width, including trailing blank cells.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from math import ceil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions
    from .style import Style

from ._width import cell_len, char_cell_len
from .measure import measure
from .segment import CachedBytes, LineRenderable, Segment, blank, compose_lines
from .text import Text


def _unpack_padding(pad) -> tuple[int, int, int, int]:
    """Unpack CSS-style padding to (top, right, bottom, left).

    Args:
        pad: An int, or a 1-, 2- or 4-tuple of ints.

    Returns:
        The (top, right, bottom, left) padding.

    Raises:
        ValueError: If a tuple of unsupported length is given.
    """
    if isinstance(pad, int):
        return (pad, pad, pad, pad)

    if len(pad) == 1:
        return (pad[0], pad[0], pad[0], pad[0])

    if len(pad) == 2:
        top, right = pad
        return (top, right, top, right)

    if len(pad) == 4:
        top, right, bottom, left = pad
        return (top, right, bottom, left)

    raise ValueError(f"1, 2 or 4 integers required for padding; {len(pad)} given")


def _ratio_distribute(total: int, ratios: list[int]) -> list[int]:
    """Distribute an integer total into parts proportional to `ratios`.

    Args:
        total: The total to divide.
        ratios: Positive integer ratios, one per part.

    Returns:
        A list of integers summing to `total`.
    """
    total_ratio = sum(ratios)
    remaining = total
    out = []
    for ratio in ratios:
        if total_ratio > 0:
            distributed = max(0, ceil(ratio * remaining / total_ratio))

        else:
            distributed = remaining

        out.append(distributed)
        total_ratio -= ratio
        remaining -= distributed

    return out


def _ratio_reduce(
    total: int, ratios: list[int], maximums: list[int], values: list[int]
) -> list[int]:
    """Reduce `values` by `total`, proportionally to `ratios`, capped per slot.

    Based on Rich's `ratio_reduce`.

    Args:
        total: The total to remove.
        ratios: Integer ratios, one per slot (0 leaves the slot untouched).
        maximums: The most that may be removed from each slot.
        values: The values to reduce.

    Returns:
        The reduced values.
    """
    ratios = [ratio if mx else 0 for ratio, mx in zip(ratios, maximums)]
    total_ratio = sum(ratios)
    if not total_ratio:
        return values[:]

    remaining = total
    out = []
    for ratio, maximum, value in zip(ratios, maximums, values):
        if ratio and total_ratio > 0:
            distributed = min(maximum, round(ratio * remaining / total_ratio))
            out.append(value - distributed)
            remaining -= distributed
            total_ratio -= ratio

        else:
            out.append(value)

    return out


def _collapse_widths(widths: list[int], total: int, avail: int) -> list[int]:
    """Shrink the widest columns until the total fits, as Rich's Table does.

    Repeatedly levels the widest column(s) down toward the second-widest,
    spreading the excess between ties.

    Args:
        widths: The padded column widths.
        total: The sum of `widths`.
        avail: The available width.

    Returns:
        The collapsed widths (may still exceed `avail` if all are equal).
    """
    widths = widths[:]  # Mutated in place across passes; leave the caller's alone
    excess = total - avail
    while total and excess > 0:
        # One pass for the widest, the runner-up, and how many tie for widest
        widest = second = ties = 0
        for w in widths:
            if w > widest:
                second = widest  # The old maximum becomes the new runner-up
                widest = w
                ties = 1

            elif w == widest:
                ties += 1

            elif w > second:
                second = w

        difference = widest - second
        if not difference:
            break

        cap = min(excess, difference)
        remaining = excess
        share = ties
        removed = 0
        for i, w in enumerate(widths):
            if w == widest and share > 0:
                distributed = min(cap, round(remaining / share))
                widths[i] = w - distributed
                remaining -= distributed
                removed += distributed
                share -= 1

        total -= removed
        excess = total - avail

    return widths


def _column_first_widths(nats: Sequence[int], ncols: int) -> Iterator[int]:
    """Yield item widths in row-major order for a column-first layout.

    Full rows are yielded column by column; a final ragged row stops at
    the first short column.

    Args:
        nats: The measured item widths, in item order.
        ncols: The number of columns.

    Yields:
        Item widths, one grid cell at a time, skipping the empty tail.
    """
    base, extra = divmod(len(nats), ncols)
    offsets = []
    offset = 0
    for _ in range(extra):  # Leading columns hold one extra item
        offsets.append(offset)
        offset += base + 1

    for _ in range(extra, ncols):
        offsets.append(offset)
        offset += base

    for row in range(base):
        for start in offsets:
            yield nats[start + row]

    if extra:  # The ragged row covers only the columns that hold an extra item
        for col in range(extra):
            yield nats[offsets[col] + base]


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
            text = seg.text
            if text.isascii():  # One cell per character, so slice straight off
                chunk = text[:remain]
                w = len(chunk)

            else:
                acc, w = [], 0
                for ch in text:
                    c = char_cell_len(ch)
                    if w + c > remain:
                        break

                    acc.append(ch)
                    w += c

                chunk = "".join(acc)

            if chunk:
                out.append(Segment(chunk, seg.style))

            total += w
            break

    if total < width:
        out.append(blank(width - total))

    return out


class Columns(CachedBytes, LineRenderable):
    """Layout renderables into columns.

    Cached bytes assume the items are stable after construction; mutating the
    `renderables` list or a nested child in place is not tracked, call
    `mark_dirty()` afterwards.
    """

    def __init__(
        self,
        renderables=None,
        padding: int | tuple[int, ...] = (0, 1),
        *,
        width: int | None = None,
        style: str | Style | None = None,
        expand: bool = False,
        equal: bool = False,
        column_first: bool = False,
    ) -> None:
        """Initialise a Columns layout with the given renderables and options.

        Args:
            renderables: The renderables to layout into columns.
            padding: Padding around cells: an int or a (vertical, horizontal)
                or (top, right, bottom, left) tuple.
            width: The fixed column width override.
            style: The style to apply to the columns.
            expand: If True, expands columns to fill available width, else size
                to the content plus padding.
            equal: If True, compute the column count as if every item were as wide
                as the widest; rendered columns still size to their own content.
            column_first: Fill the grid down each column before moving right,
                rather than left-to-right across each row.
        """
        self._init_byte_cache()
        self.renderables = list(renderables or [])
        self.padding = padding
        self.width = width  # Fixed column width override
        self.style = style
        self.expand = expand
        self.equal = equal
        self.column_first = column_first

    def _fit_column_count(self, nats: Sequence[int], gutter: int, avail: int) -> int:
        """Count the number of columns that can fit the available width.

        Starting from one column per item, walk the item widths in grid order
        keeping each column's running maximum; order-dependent by design: a wide item
        in a later row can trigger a restart.

        Args:
            nats: The measured item widths, in item order.
            gutter: The width of the gap between adjacent columns.
            avail: The available width.

        Returns:
            The number of columns (at least 1).
        """
        n = len(nats)

        # First pass: one column per item
        ncols = n
        total = 0
        for i, w in enumerate(nats):
            total += w
            if total + gutter * i > avail:
                ncols = i
                break

        if ncols == n:  # Nothing overflowed, keep one column per item
            return max(1, ncols)

        column_first = self.column_first
        while ncols > 1:
            limit = avail - gutter * (ncols - 1)
            vals = [0] * ncols
            total = 0
            col = 0
            reduced = False

            if column_first:
                seen = 0
                for w in _column_first_widths(nats, ncols):
                    if seen < ncols:  # Warm-up: col == seen, so vals[col] is 0
                        seen += 1
                        if w:
                            total += w
                            vals[col] = w

                        if total + gutter * (seen - 1) > avail:
                            ncols = seen - 1
                            reduced = True
                            break

                    elif w > vals[col]:
                        total += w - vals[col]
                        vals[col] = w
                        if total > limit:
                            ncols -= 1
                            reduced = True
                            break

                    col += 1
                    if col == ncols:
                        col = 0

            # Row-first
            else:
                for w in nats:
                    if w > vals[col]:
                        total += w - vals[col]
                        vals[col] = w
                        if total > limit:
                            ncols -= 1
                            reduced = True
                            break

                    col += 1
                    if col == ncols:
                        col = 0

            if not reduced:
                break

        return max(1, ncols)

    def _lines(self, console: Console, options: ConsoleOptions) -> list[list[Segment]]:
        """Layout the renderables into columns.

        Args:
            console: The console to render to.
            options: The console options.

        Returns:
            A list of rows, each row is a list of segments.
        """
        if not self.renderables:
            return []

        # Strings become Texts once, so markup/emoji measure and render
        items = [
            console._str_to_text(r) if isinstance(r, str) else r
            for r in self.renderables
        ]
        n = len(items)
        avail = options.max_width
        top, right, bottom, left = _unpack_padding(self.padding)
        gutter = max(left, right)
        fixed = self.width

        # Column count: fixed width divides the space, else the iterative fit
        if fixed is not None:
            nats: list[int] = []
            ncols = max(1, avail // (fixed + gutter))

        else:
            nats = [measure(console, item, options).maximum for item in items]
            if self.equal:
                # All cols have equal width, so the fit loop collapses to a closed form
                span = max(nats) + gutter
                ncols = n if not span else max(1, min(n, (avail + gutter) // span))

            else:
                ncols = self._fit_column_count(nats, gutter, avail)

        # Grid placement, as a per-column (start, length) into the item list
        if self.column_first:
            base, extra = divmod(n, ncols)
            nrows = base + 1 if extra else base
            stride = 1
            col_lengths = [base + 1] * extra + [base] * (ncols - extra)
            col_starts = []
            offset = 0
            for length in col_lengths:
                col_starts.append(offset)
                offset += length

        else:
            nrows = -(-n // ncols)
            stride = ncols
            col_starts = list(range(ncols))
            # Trailing columns of a ragged last row can be empty (length 0)
            col_lengths = [max(0, -(-(n - c) // ncols)) for c in range(ncols)]

        # Horizontal padding per column: collapsed gutters, no outer edges
        last = ncols - 1
        pl = [0, *[max(0, left - right)] * last]
        pr = [*[right] * last, 0]

        # Padded column widths: fixed, or each column's widest cell plus pads
        stale = False
        if fixed is not None:
            padded = [min(fixed + p, avail) for p in pr]
            table_width = sum(padded)

        else:
            naturals = []  # Widest cell plus pads, before the min-1 bump
            padded = []
            for c in range(ncols):
                start = col_starts[c]
                widest = max(
                    nats[start : start + col_lengths[c] * stride : stride], default=0
                )
                natural = widest + pl[c] + pr[c]
                naturals.append(natural)
                padded.append(min(natural, avail) or 1)

            table_width = sum(padded)

            # The min-1 bump on empty columns can overflow the fit; shrink the
            # widest columns and re-clamp to naturals
            if table_width > avail:
                padded = _collapse_widths(padded, table_width, avail)
                table_width = sum(padded)
                if table_width > avail:  # Last resort: reduce evenly
                    padded = _ratio_reduce(
                        table_width - avail, [1] * ncols, padded, padded
                    )
                    table_width = sum(padded)

                # Rich leaves table_width stale here, so expand sees the
                # pre-clamp total; replicated for byte parity
                padded = [min(nat, w) for nat, w in zip(naturals, padded)]
                stale = True

        # Expand distributes the leftover proportionally to the padded widths
        if self.expand and table_width < avail:
            extras = _ratio_distribute(avail - table_width, padded)
            padded = [w + e for w, e in zip(padded, extras)]
            stale = True

        content_ws = [w - a - b if w > a + b else 0 for w, a, b in zip(padded, pl, pr)]
        if stale:
            table_width = sum(padded)

        # Render each occupied cell at its column's content width
        cell_rows: list[list[list[list[Segment]] | None]] = [
            [None] * ncols for _ in range(nrows)
        ]
        col_opts = [None] * ncols  # One ConsoleOptions per column, made on demand
        for c in range(ncols):
            w = content_ws[c]
            idx = col_starts[c]
            for r in range(col_lengths[c]):
                item = items[idx]
                idx += stride
                if isinstance(item, Text):
                    cell_rows[r][c] = item.render_lines(w, "left", "ellipsis")

                else:
                    opts = col_opts[c]
                    if opts is None:
                        opts = col_opts[c] = options._replace(
                            max_width=w, justify="left", overflow="ellipsis"
                        )

                    cell_rows[r][c] = [
                        _fit_line(line, w) for line in console.render_lines(item, opts)
                    ]

        # Vertical padding between rows: collapsed, no outer edges
        vgap = max(0, top - bottom) + top

        # Fills are the same in every row, so build each column's once
        pl_segs = [blank(p) if p else None for p in pl]
        pr_segs = [blank(p) if p else None for p in pr]
        fill_segs = [blank(w) for w in content_ws]
        gap_seg = blank(table_width)
        columns = range(ncols)

        rows: list[list[Segment]] = []
        for r in range(nrows):
            if r and vgap:
                rows.extend([gap_seg] for _ in range(vgap))

            row_cells = cell_rows[r]
            height = max((len(cell) for cell in row_cells if cell), default=1)
            for li in range(height):
                row: list[Segment] = []
                append = row.append
                extend = row.extend
                for c in columns:
                    seg = pl_segs[c]
                    if seg is not None:
                        append(seg)

                    cell = row_cells[c]
                    if cell is not None and li < len(cell):
                        extend(cell[li])

                    else:
                        append(fill_segs[c])

                    seg = pr_segs[c]
                    if seg is not None:
                        append(seg)

                rows.append(row)

        return compose_lines(rows, console.resolve_style(self.style))
