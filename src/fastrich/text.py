"""Text: a plain string carrying styled spans, measured through the width engine.

Spans are (start, end, Style) over the plain text and layer in application
order: a later span combines over an earlier one. Rendering resolves the effective
style per position and run-length-encodes equal runs into SGR sequences.
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

    __slots__ = ("plain", "style", "_spans")

    def __init__(self, text: str = "", style: Style | None = None) -> None:
        """Initialise with optional plain text and base style.

        Args:
            text: The plain text content.
            style: The base style to apply to the whole string.
        """
        self.plain = text
        self.style = style  # Base style applied to the whole string
        self._spans: list[Span] = []

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
        if end is None:
            end = len(self.plain)

        if start < end:
            self._spans.append(Span(start, end, style))

        return self

    def render(self) -> str:
        """Resolve spans to an ANSI string, RLE-collapsing equal style runs.

        Returns:
            The rendered ANSI string.
        """
        text = self.plain
        n = len(text)
        if not n:
            return ""

        base = self.style or NULL_STYLE
        resolved = [base] * n
        for span in self._spans:
            lo, hi = max(0, span.start), min(n, span.end)
            for i in range(lo, hi):
                resolved[i] = resolved[i].combine(span.style)

        out = []
        i = 0
        while i < n:
            cur = resolved[i]
            j = i + 1

            while j < n and resolved[j] == cur:
                j += 1

            out.append(cur.render(text[i:j]))
            i = j

        return "".join(out)
