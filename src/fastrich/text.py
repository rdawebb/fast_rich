"""Text: a plain string carrying styled spans, measured through the width engine.

Spans are (start, end, Style) over the plain text and layer in application
order: a later span combines over an earlier one. Rendering partitions the text
at span boundaries and resolves the effective style per interval.
"""

from __future__ import annotations

from typing import NamedTuple

from ._width import cell_len
from .style import NULL_STYLE, Style


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

    def stylise(self, style: Style, start: int = 0, end: int | None = None) -> "Text":
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
