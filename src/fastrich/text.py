"""Text: a plain string carrying styled spans, measured through the width engine.

Spans are (start, end, Style) over the plain text and layer in application
order: a later span combines over an earlier one. Rendering partitions the text
at span boundaries and resolves the effective style per interval.
"""

from __future__ import annotations

from typing import NamedTuple

from ._width import cell_len
from .style import NULL_STYLE, Style
from .wrap import fit_end, wrap_offsets


class Span(NamedTuple):
    """Represents a styled span over a range of characters in a `Text` string."""

    start: int
    end: int
    style: Style


class Text:
    """Represents a plain string with styled spans, measured through the width engine."""

    __slots__ = ("plain", "style", "_spans", "_cache")

    def __init__(self, text: str = "", style: Style | None = None) -> None:
        """Initialise with optional plain text and base style.

        Args:
            text: The plain text content.
            style: The base style to apply to the whole string.
        """
        self.plain = text
        self.style = style  # Base style applied to the whole string
        self._spans: list[Span] = []
        self._cache: dict[str, bytes] = {}

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
    def from_markup(cls, markup: str, style: Style | None = None) -> "Text":
        """Build a Text from console markup.

        Args:
            markup: The markup string to parse.
            style: The base style to apply.

        Returns:
            The parsed Text object.
        """
        from .markup import render

        return render(markup, style)

    def append(self, text: str, style: Style | None = None) -> "Text":
        """Append text, optionally styled, returning self for chaining.

        Args:
            text: The text to append.
            style: The style to apply to the text.

        Returns:
            The Text object for chaining.
        """
        self._cache = {}
        start = len(self.plain)
        self.plain += text
        if style is not None:
            self._spans.append(Span(start, len(self.plain), style))

        return self

    def stylize(self, style: Style, start: int = 0, end: int | None = None) -> "Text":
        """Apply style over [start, end) of the existing text.

        Args:
            style: The style to apply.
            start: The start index of the text to stylize.
            end: The end index of the text to stylize.

        Returns:
            The Text object for chaining.
        """
        self._cache = {}
        if end is None:
            end = len(self.plain)

        if start < end:
            self._spans.append(Span(start, end, style))

        return self

    stylise = stylize  # British-spelling alias

    def _segments(self):
        """Yield one Segment per span-boundary interval.

        Collects all span edge points, then for each interval resolves the
        effective style by combining only the spans that fully cover it.

        Yields:
            The next segment of the text.
        """
        from .segment import Segment

        text = self.plain
        n = len(text)
        if not n:
            return

        base = self.style or NULL_STYLE
        spans = self._spans

        if not spans:
            yield Segment(text, base if base else None)
            return

        pts = sorted(
            {0, n} | {max(0, s.start) for s in spans} | {min(n, s.end) for s in spans}
        )

        for lo, hi in zip(pts, pts[1:]):
            style = base
            for span in spans:
                if span.start <= lo and span.end >= hi:
                    style = style.combine(span.style)

            yield Segment(text[lo:hi], style if style else None)

    def __rich_console__(self, console, options):
        """Render the text as a Rich console object.

        Args:
            console: The Rich console object.
            options: The Rich console options.

        Yields:
            Segments of the text to be rendered.
        """
        yield from self._segments()

    def render_bytes(self, encoding: str = "utf-8") -> bytes:
        """Render the text to bytes, caching per encoding.

        Args:
            encoding: The encoding to use for the output bytes.

        Returns:
            The rendered ANSI bytes.
        """
        cached = self._cache.get(encoding)
        if cached is None:
            cached = b"".join(
                seg.style.render_bytes(seg.text, encoding)
                if seg.style
                else seg.text.encode(encoding)
                for seg in self._segments()
            )
            self._cache[encoding] = cached

        return cached

    def render(self) -> str:
        """Render the text as an ANSI string.

        Returns:
            The rendered ANSI string.
        """
        return self.render_bytes().decode("utf-8")

    def render_lines(self, width, justify="left", overflow="fold", base_style=None):
        """Render to a list of lines (each a list of Segments), fitted to width.

        Uses the same boundary-based interval resolution as `_segments`, so a
        cell's styling survives wrapping and overflow.

        Args:
            width: The width to fit the text to.
            justify: How to justify the text within the width ("left", "center", "right").
            overflow: How to handle overflow ("fold", "ellipsis", "fold_ellipsis").
            base_style: A style to apply under the Text's own style and spans.

        Returns:
            A list of lines, each a list of Segments.
        """
        from .segment import Segment

        text = self.plain
        n = len(text)

        base = NULL_STYLE
        if base_style:
            base = base.combine(base_style)

        if self.style:
            base = base.combine(self.style)

        spans = self._spans
        edges = (
            sorted({max(0, s.start) for s in spans} | {min(n, s.end) for s in spans})
            if spans
            else []
        )

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

        def line(start: int, end: int, ellipsis=False) -> list[Segment]:
            """Return a line of text as a list of segments, with optional ellipsis and padding.

            Args:
                start: The start index of the text to include.
                end: The end index of the text to include.
                ellipsis: Whether to include an ellipsis at the end if the line overflows.

            Returns:
                A list of segments representing the line of text.
            """
            segs = range_segments(start, end)
            used = cell_len(text[start:end])
            if ellipsis:
                segs.append(Segment("…"))
                used += 1

            pad = width - used
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

        if overflow == "fold":
            return [line(s, e) for s, e in wrap_offsets(text, width)]

        if cell_len(text) <= width:
            return [line(0, n)]

        if overflow == "ellipsis" and width >= 1:
            return [line(0, fit_end(text, width - 1), ellipsis=True)]

        return [line(0, fit_end(text, width))]
