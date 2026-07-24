"""Text: a plain string carrying styled spans, measured through the width engine.

Spans are (start, end, Style) over the plain text and layer in application
order: a later span combines over an earlier one. Rendering partitions the text
at span boundaries and resolves the effective style per interval.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, NamedTuple

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions

from ._width import cell_len
from .measure import Measurement
from .segment import _NEWLINE, Segment, blank
from .style import NULL_STYLE, Style
from .wrap import fit_end, nofold_offsets, wrap_offsets


class Span(NamedTuple):
    """Represents a styled span over a range of characters in a `Text` string."""

    start: int
    end: int
    style: Style


def _as_style(value: str | Style | None) -> Style | None:
    """Coerce a Text style value to a Style or None (console-free).

    None stays None, a Style passes through, and a str is parsed as a style
    definition via `Style.parse` (cached). Text is rendered without a console
    in its hot paths, so a str here cannot be a theme name, use a container's
    style param (Panel/Table/...) for theme-name resolution.

    Args:
        value: None, a Style, or a style definition string.

    Returns:
        The resolved Style, or None.
    """
    if value is None or isinstance(value, Style):
        return value

    return Style.parse(value)


class Text:
    """Represents a plain string with styled spans, measured through the width engine."""

    __slots__ = (
        "plain",
        "style",
        "justify",
        "overflow",
        "no_wrap",
        "end",
        "tab_size",
        "_spans",
        "_edges",
    )

    def __init__(
        self,
        text: str = "",
        style: str | Style | None = None,
        *,
        justify: Literal["left", "center", "right", "full"] | None = None,
        overflow: Literal["fold", "ellipsis", "crop"] | None = None,
        no_wrap: bool | None = None,
        end: str = "\n",
        tab_size: int = 8,
        spans: list[Span] | None = None,
    ) -> None:
        """Initialise with optional plain text and base style.

        Args:
            text: The plain text content.
            style: The base style to apply to the whole string.
            justify: Alignment within a fixed width ("left", "center", "right", "full").
                None inherits the render default ("left").
            overflow: Overflow handling ("fold", "ellipsis", "crop"). None
                inherits the render default ("fold").
            no_wrap: Disable wrapping; a too-long line is handled by `overflow`.
                None inherits the render default (False).
            end: Text written after this Text when printed on its own (default a
                newline); an explicit `end=` on `print` takes precedence.
            tab_size: Expand tabs to this many columns (default 8).
            spans: Initial style spans over the plain text.
        """
        self.plain = text.expandtabs(tab_size) if tab_size else text
        self.style = style  # Base style applied to the whole string
        self.justify = justify
        self.overflow = overflow
        self.no_wrap = no_wrap
        self.end = end
        self.tab_size = tab_size

        self._spans: list[Span] = list(spans) if spans else []
        self._edges: list[int] | None = None  # Cached span-boundary points

    def __len__(self) -> int:
        """Return the length of the plain text.

        Returns:
            The length of the plain text.
        """
        return len(self.plain)

    def __repr__(self) -> str:
        """Return a string representation of the Text object.

        Returns:
            A string representation of the Text object.
        """
        return f"Text({self.plain!r}, spans={len(self._spans)})"

    @property
    def cell_len(self) -> int:
        """Rendered width in terminal columns.

        Returns:
            The rendered width in terminal columns.
        """
        return cell_len(self.plain)

    @classmethod
    def from_markup(cls, markup: str, style: Style | None = None) -> Text:
        """Build a Text from console markup.

        Args:
            markup: The markup string to parse.
            style: The base style to apply.

        Returns:
            The parsed Text object.
        """
        from .markup import render

        return render(markup, style)

    def append(self, text: str, style: Style | None = None) -> Text:
        """Append text, optionally styled, returning self for chaining.

        Args:
            text: The text to append.
            style: The style to apply to the text.

        Returns:
            The Text object for chaining.
        """
        start = len(self.plain)
        self.plain += text
        if style is not None:
            self._spans.append(Span(start, len(self.plain), style))

        self._edges = None  # Plain length and/or spans changed

        return self

    def stylize(self, style: Style, start: int = 0, end: int | None = None) -> Text:
        """Apply style over [start, end) of the existing text.

        Args:
            style: The style to apply.
            start: The start index of the text to stylize.
            end: The end index of the text to stylize.

        Returns:
            The Text object for chaining.
        """
        if end is None:
            end = len(self.plain)

        if start < end:
            self._spans.append(Span(start, end, style))
            self._edges = None  # Span was added

        return self

    stylise = stylize  # British-spelling alias

    def _edge_points(self) -> list[int]:
        """Sorted span-boundary points, memoised until a span mutator runs.

        A pure function of `(len(plain), spans)`, built in a single pass.

        Returns:
            The sorted list of clamped span edge points, including 0 and n.
        """
        edges = self._edges
        if edges is None:
            n = len(self.plain)
            pts = {0, n}

            for s in self._spans:
                st = s.start
                pts.add(st if st > 0 else 0)  # max(0, start)
                en = s.end
                pts.add(en if en < n else n)  # min(n, end)

            edges = self._edges = sorted(pts)

        return edges

    def _segments(self):
        """Yield one Segment per span-boundary interval.

        Collects all span edge points, then for each interval resolves the
        effective style by combining only the spans that fully cover it.

        Yields:
            The next segment of the text.
        """
        text = self.plain
        n = len(text)
        if not n:
            return

        base = _as_style(self.style) or NULL_STYLE
        spans = self._spans

        if not spans:
            yield Segment(text, base if base else None)
            return

        pts = self._edge_points()

        for lo, hi in zip(pts, pts[1:]):
            style = base
            for span in spans:
                if span.start <= lo and span.end >= hi:
                    style = style.combine(span.style)

            yield Segment(text[lo:hi], style if style else None)

    def __rich_console__(self, console, options):
        """Render the text, wrapped to the available width.

        Wraps/justifies/overflows via `render_lines` at `options.max_width`.
        Per-render overrides on `options` (justify/overflow/no_wrap) take
        precedence over the Text's own attributes, which fall back to the
        defaults (ragged wrap, fold, no truncation).

        Args:
            console: The console.
            options: The console options (carry max_width + overrides).

        Yields:
            Segments for each wrapped line, separated by newline segments.
        """
        lines = self.render_lines(
            options.max_width,
            options.justify,
            options.overflow,
            no_wrap=options.no_wrap,
        )

        first = True
        for ln in lines:
            if not first:
                yield _NEWLINE

            first = False

            yield from ln

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        """Minimum = longest word, maximum = longest line.

        Args:
            console: The Rich console object.
            options: The Rich console options.

        Returns:
            A Measurement of the minimum and maximum width of the text.
        """
        lines = self.plain.split("\n")
        maximum = max((cell_len(line) for line in lines), default=0)
        minimum = max(
            (cell_len(word) for line in lines for word in line.split(" ")), default=0
        )

        return Measurement(minimum, maximum)

    def render_bytes(self, encoding: str = "utf-8") -> bytes:
        """Render the text to bytes.

        Args:
            encoding: The encoding to use for the output bytes.

        Returns:
            The rendered ANSI bytes.
        """
        return b"".join(
            seg.style.render_bytes(seg.text, encoding)
            if seg.style
            else seg.text.encode(encoding)
            for seg in self._segments()
        )

    def render(self) -> str:
        """Render the text as an ANSI string.

        Returns:
            The rendered ANSI string.
        """
        return self.render_bytes().decode("utf-8")

    def render_lines(
        self,
        width: int,
        justify: Literal["left", "center", "right", "full"] | None = None,
        overflow: Literal["fold", "ellipsis", "crop"] | None = None,
        base_style: Style | None = None,
        *,
        no_wrap: bool | None = None,
    ) -> list[list[Segment]]:
        """Render to a list of lines (each a list of Segments), fitted to width.

        Uses the same boundary-based interval resolution as `_segments`, so a
        cell's styling survives wrapping and overflow.

        Args:
            width: The width to fit the text to.
            justify: How to justify each line ("left"/"center"/"right"/"full"),
                falls back to the Text's own justify, then None.
            overflow: How to handle overflow ("fold", "ellipsis", "crop").
            base_style: A style to apply under the Text's own style and spans.
            no_wrap: Whether to disable wrapping of the text.

        Returns:
            A list of lines, each a list of Segments.
        """
        justify = justify if justify is not None else self.justify
        overflow = overflow if overflow is not None else (self.overflow or "fold")
        no_wrap = no_wrap if no_wrap is not None else bool(self.no_wrap)

        text = self.plain
        n = len(text)

        base = NULL_STYLE
        if base_style:
            base = base.combine(base_style)

        own = _as_style(self.style)
        if own:
            base = base.combine(own)

        spans = self._spans
        edges = self._edge_points() if spans else []

        def range_segments(start: int, end: int) -> list[Segment]:
            """Return the segments for the text range.

            Args:
                start: The start index of the range.
                end: The end index of the range.

            Returns:
                A list of segments for the text range (start, end).
            """
            if start >= end:
                return []

            if not spans:
                return [Segment(text[start:end], base if base else None)]

            pts = [start, *(p for p in edges if start < p < end), end]
            out = []
            for lo, hi in zip(pts, pts[1:]):
                style = base
                for span in spans:
                    if span.start <= lo and span.end >= hi:
                        style = style.combine(span.style)

                out.append(Segment(text[lo:hi], style if style else None))

            return out

        def line(
            start: int, end: int, ellipsis: bool = False, used: int | None = None
        ) -> list[Segment]:
            """Return a line of text as a list of segments, with optional ellipsis and padding.

            Args:
                start: The start index of the text to include.
                end: The end index of the text to include.
                ellipsis: Whether to include an ellipsis at the end if the line overflows.
                used: Precomputed cell width of `text[start:end]`.

            Returns:
                A list of segments representing the line of text.
            """
            segs = range_segments(start, end)
            if used is None:
                used = cell_len(text[start:end])

            if ellipsis:
                segs.append(Segment("…"))
                used += 1

            pad = width - used
            if pad > 0 and justify is not None:
                if justify == "right":
                    segs.insert(0, blank(pad))

                elif justify == "center":
                    left = pad // 2
                    segs.insert(0, blank(left))
                    segs.append(blank(pad - left))

                else:
                    segs.append(blank(pad))

            return segs

        def full_line(start: int, end: int) -> list[Segment]:
            """Full-justify one wrapped line: spread slack between words.

            Words keep their styling (via range_segments), the inter-word gaps
            become plain expanded spaces. A one-word line falls back to the
            left-aligned line.

            Args:
                start: The start index of the line's text.
                end: The end index of the line's text.

            Returns:
                The line's segments, filling the width exactly.
            """
            words = []
            word_w = 0
            i = start

            while i < end:
                while i < end and text[i] == " ":
                    i += 1
                ws = i

                while i < end and text[i] != " ":
                    i += 1

                if i > ws:
                    words.append((ws, i))
                    word_w += cell_len(text[ws:i])

            ngaps = len(words) - 1
            slack = width - word_w

            if ngaps < 1 or slack < ngaps:
                return line(start, end)

            base_gap, extra = divmod(slack, ngaps)
            segs: list[Segment] = []
            for idx, (a, b) in enumerate(words):
                segs.extend(range_segments(a, b))

                if idx < ngaps:
                    segs.append(blank(base_gap + (1 if idx >= ngaps - extra else 0)))

            return segs

        if overflow == "fold" and not no_wrap:
            offsets = wrap_offsets(text, width)

            if justify == "full":
                last = len(offsets) - 1
                return [
                    full_line(start, end) if i < last else line(start, end)
                    for i, (start, end) in enumerate(offsets)
                ]

            return [line(start, end) for start, end in offsets]

        if overflow in ("ellipsis", "crop") and not no_wrap and width >= 1:
            # Logical lines split on newlines first, blank lines preserved
            out = []
            lines = 0
            ascii_only = text.isascii()
            is_ellipsis = overflow == "ellipsis"
            while True:
                newline = text.find("\n", lines)
                line_end = n if newline == -1 else newline
                pts = [
                    lines,
                    *nofold_offsets(text, lines, line_end, width, ascii_only),
                    line_end,
                ]
                for i in range(len(pts) - 1):
                    start, end = pts[i], pts[i + 1]
                    # Trim trailing spaces beyond `width`, by character count
                    if end - start > width:
                        t = end
                        while t > start and text[t - 1] == " ":
                            t -= 1

                        end -= min(end - t, (end - start) - width)

                    # All-ASCII width is the char count, so skip the cell_len scan
                    used = end - start if ascii_only else cell_len(text[start:end])
                    if used <= width:
                        out.append(line(start, end, used=used))

                    elif is_ellipsis:
                        # Fit to width-1, fill any wide-glyph gap, then '…'
                        fe = start + fit_end(text[start:end], width - 1)
                        segs = range_segments(start, fe)
                        gap = (width - 1) - cell_len(text[start:fe])
                        if gap > 0:
                            segs.append(blank(gap))

                        segs.append(Segment("…"))
                        out.append(segs)

                    else:
                        out.append(line(start, start + fit_end(text[start:end], width)))

                if newline == -1:
                    return out

                lines = newline + 1

        if cell_len(text) <= width:
            return [line(0, n)]

        if overflow == "ellipsis" and width >= 1:
            return [line(0, fit_end(text, width - 1), ellipsis=True)]

        return [line(0, fit_end(text, width))]
