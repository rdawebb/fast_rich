"""Highlighter: regex-driven automatic styling of plain text.

A highlighter adds style spans to a Text by matching regular expressions and
naming the matched groups; each group name resolves to a themed style. The
named styles live in the theme's defaults, so highlighting composes with the
theme system and can be overridden.

`ReprHighlighter` is the default, it styles the shapes typically seen in Python
repr output: numbers, strings, bools/None, braces, calls, paths, URLs, UUIDs,
IP/MAC addresses, and tag-like fragments.
"""

from __future__ import annotations

import re

from .style import Style

# Default styles for the repr.* group names, merged into the theme defaults
REPR_STYLES: dict[str, Style] = {
    "repr.ellipsis": Style(color="yellow"),
    "repr.str": Style(color="green", italic=False, bold=False),
    "repr.brace": Style(bold=True),
    "repr.comma": Style(bold=True),
    "repr.ipv4": Style(bold=True, color="bright_green"),
    "repr.ipv6": Style(bold=True, color="bright_green"),
    "repr.eui48": Style(bold=True, color="bright_green"),
    "repr.eui64": Style(bold=True, color="bright_green"),
    "repr.tag_start": Style(bold=True),
    "repr.tag_name": Style(color="bright_magenta", bold=True),
    "repr.tag_contents": Style(color="default"),
    "repr.tag_end": Style(bold=True),
    "repr.attrib_name": Style(color="yellow", italic=False),
    "repr.attrib_equal": Style(bold=True),
    "repr.attrib_value": Style(color="magenta", italic=False),
    "repr.number": Style(color="cyan", bold=True, italic=False),
    "repr.number_complex": Style(color="cyan", bold=True, italic=False),
    "repr.bool_true": Style(color="bright_green", italic=True),
    "repr.bool_false": Style(color="bright_red", italic=True),
    "repr.none": Style(color="magenta", italic=True),
    "repr.url": Style(underline=True, color="bright_blue", italic=False, bold=False),
    "repr.uuid": Style(color="bright_yellow", bold=False),
    "repr.call": Style(color="magenta", bold=True),
    "repr.path": Style(color="magenta"),
    "repr.filename": Style(color="bright_magenta"),
}


class Highlighter:
    """Base class: apply highlighting spans to a Text in place."""

    def highlight(self, text, resolve) -> None:  # pragma: no cover - interface
        """Add style spans to `text`.

        Args:
            text: The Text to highlight (mutated in place).
            resolve: Callable resolving a style name to a Style or None.
        """
        raise NotImplementedError


class NullHighlighter(Highlighter):
    """A highlighter that does nothing."""

    def highlight(self, text, resolve) -> None:
        """Add no spans."""
        return None


class RegexHighlighter(Highlighter):
    """Apply highlighting from a list of regular expressions.

    Each pattern's named groups resolve to `{base_style}{group_name}` styles via
    the console's resolver. Patterns are compiled once per class.
    """

    highlights: list[str] = []
    base_style: str = ""

    def __init__(self) -> None:
        """Compile this highlighter's patterns."""
        self._patterns = [re.compile(h) for h in self.highlights]

    def highlight(self, text, resolve) -> None:
        """Apply each pattern's named-group styles to the text.

        Args:
            text: The Text to highlight (mutated in place).
            resolve: Callable resolving a style name to a Style or None.
        """
        prefix = self.base_style

        def get_style(name: str) -> Style | None:
            """Get the resolved the style name.

            Args:
                name: The style name to resolve.

            Returns:
                The resolved Style or None.
            """
            return resolve(prefix + name)

        for pattern in self._patterns:
            text.highlight_regex(pattern, get_style)


def _combine(*regexes: str) -> str:
    """Join alternate regexes into one pattern (first-match-wins order).

    Args:
        regexes: The regex patterns to combine.

    Returns:
        The combined regex pattern.
    """
    return "|".join(regexes)


class ReprHighlighter(RegexHighlighter):
    """Highlight the shapes typically produced by Python `__repr__`."""

    base_style = "repr."
    highlights = [
        r"(?P<tag_start><)(?P<tag_name>[-\w.:|]*)(?P<tag_contents>[\w\W]*)(?P<tag_end>>)",
        r'(?P<attrib_name>[\w_]{1,50})=(?P<attrib_value>"?[\w_]+"?)?',
        r"(?P<brace>[][{}()])",
        _combine(
            r"(?P<ipv4>[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})",
            r"(?P<ipv6>([A-Fa-f0-9]{1,4}::?){1,7}[A-Fa-f0-9]{1,4})",
            r"(?P<uuid>[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12})",
            r"(?P<call>[\w.]*?)\(",
            r"\b(?P<bool_true>True)\b|\b(?P<bool_false>False)\b|\b(?P<none>None)\b",
            r"(?P<ellipsis>\.\.\.)",
            r"(?P<number>(?<!\w)\-?[0-9]+\.?[0-9]*(e[-+]?\d+?)?\b|0x[0-9a-fA-F]*)",
            r"(?P<path>\B(/[-\w._+]+)*\/)(?P<filename>[-\w._+]*)?",
            r"(?<![\\\w])(?P<str>b?'''.*?(?<!\\)'''|b?'.*?(?<!\\)'|b?\"\"\".*?(?<!\\)\"\"\"|b?\".*?(?<!\\)\")",
            r"(?P<url>(file|https|http|ws|wss)://[-0-9a-zA-Z$_+!`(),.?/;:&=%#~@]*)",
        ),
    ]
