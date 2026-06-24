"""Console markup → Text.

Parses `[bold red]text[/]` style markup into a Text with spans. Tags open a
style; `[/]` closes the most recent, `[/style]` closes a matching one.
`\\[` is a literal bracket. Spans are applied in open order so inner tags
layer over outer ones (matching Text's interval resolution).
"""

from __future__ import annotations

import re

from .style import Style
from .text import Text

_TAG_RE = re.compile(r"(?<!\\)\[([a-z#/@][^\[\]]*)\]")


def escape(markup: str) -> str:
    """Escape `markup` so its brackets render literally instead of as tags.

    Prefixes a backslash to each `[`; the parser's `(?<!\\)` lookbehind then
    skips it and `add_literal` restores the bracket.

    Args:
        markup: The string to escape.

    Returns:
        The escaped string, safe to pass through markup rendering verbatim.
    """
    return markup.replace("[", "\\[")


def render(markup: str, style=None) -> Text:
    """Parse `markup` into a styled Text.

    Args:
        markup: The input string containing markup tags.
        style: Optional base style to apply to the text.

    Returns:
        A styled Text object with spans applied.
    """
    plain: list[str] = []
    spans: list[tuple] = []  # (start, end, Style, open_seq)
    stack: list[tuple] = []  # (defn, start, open_seq)
    cursor = 0
    seq = 0
    last = 0

    def add_literal(s: str) -> None:
        """Add a literal string to the plain text, replacing escaped brackets.

        Args:
            s: The string to add.
        """
        nonlocal cursor
        s = s.replace("\\[", "[")
        if s:
            plain.append(s)
            cursor += len(s)

    for m in _TAG_RE.finditer(markup):
        add_literal(markup[last : m.start()])
        last = m.end()
        tag = m.group(1).strip()

        if tag.startswith("/"):
            close = tag[1:].strip()
            if close:
                for i in range(len(stack) - 1, -1, -1):
                    if stack[i][0] == close:
                        defn, start, s_seq = stack.pop(i)

                        if cursor > start:
                            spans.append((start, cursor, Style.parse(defn), s_seq))

                        break

            elif stack:
                defn, start, s_seq = stack.pop()
                if cursor > start:
                    spans.append((start, cursor, Style.parse(defn), s_seq))

        else:
            stack.append((tag, cursor, seq))
            seq += 1

    add_literal(markup[last:])
    while stack:
        defn, start, s_seq = stack.pop()
        if cursor > start:
            spans.append((start, cursor, Style.parse(defn), s_seq))

    text = Text("".join(plain), style=style)
    for start, end, st, _ in sorted(spans, key=lambda x: x[3]):
        text.stylize(st, start, end)

    return text
