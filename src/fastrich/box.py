"""Box drawing sets for table borders.

A Box defines the glyphs for three horizontal rules (top, header separator,
bottom) and the vertical separators. The default grid draws a top rule,
a header separator, body rows, and a bottom rule.
"""

from __future__ import annotations

from typing import NamedTuple


class Box(NamedTuple):
    top_left: str
    top: str
    top_divider: str
    top_right: str
    head_left: str
    head: str
    head_divider: str
    head_right: str
    bottom_left: str
    bottom: str
    bottom_divider: str
    bottom_right: str
    left: str
    divider: str
    right: str


ASCII = Box(
    "+",
    "-",
    "+",
    "+",
    "+",
    "-",
    "+",
    "+",
    "+",
    "-",
    "+",
    "+",
    "|",
    "|",
    "|",
)

SQUARE = Box(
    "┌",
    "─",
    "┬",
    "┐",
    "├",
    "─",
    "┼",
    "┤",
    "└",
    "─",
    "┴",
    "┘",
    "│",
    "│",
    "│",
)

ROUNDED = Box(
    "╭",
    "─",
    "┬",
    "╮",
    "├",
    "─",
    "┼",
    "┤",
    "╰",
    "─",
    "┴",
    "╯",
    "│",
    "│",
    "│",
)
