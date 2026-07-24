"""Box drawing sets for table borders.

A Box is an 8-line grid: four horizontal rules (top, header separator, row
separator, footer separator, bottom) and three sets of vertical separators, one
each for the header, body and footer rows::

    ┌─┬┐ top
    │ ││ head
    ├─┼┤ head_row
    │ ││ mid
    ├─┼┤ row
    ├─┼┤ foot_row
    │ ││ foot
    └─┴┘ bottom

The middle character of the vertical lines is padding and is discarded.
"""

from __future__ import annotations

from typing import NamedTuple


class Box(NamedTuple):
    """The glyphs making up a box, one field per cell of the 8-line grid."""

    top_left: str
    top: str
    top_divider: str
    top_right: str
    head_left: str
    head_vertical: str
    head_right: str
    head_row_left: str
    head_row_horizontal: str
    head_row_cross: str
    head_row_right: str
    mid_left: str
    mid_vertical: str
    mid_right: str
    row_left: str
    row_horizontal: str
    row_cross: str
    row_right: str
    foot_row_left: str
    foot_row_horizontal: str
    foot_row_cross: str
    foot_row_right: str
    foot_left: str
    foot_vertical: str
    foot_right: str
    bottom_left: str
    bottom: str
    bottom_divider: str
    bottom_right: str
    ascii: bool = False

    def get_plain_headed_box(self) -> Box:
        """Return the equivalent box without header-specific glyphs.

        Returns:
            The most similar Box that doesn't use header-specific glyphs, or
            this box if it already satisfies that.
        """
        return PLAIN_HEADED_SUBSTITUTIONS.get(self, self)


def _box(spec: str, *, ascii: bool = False) -> Box:
    """Build a Box from an 8-line spec.

    Args:
        spec: The 8 lines of 4 glyphs each, newline separated.
        ascii: Whether the box is made of ascii characters only.

    Returns:
        The parsed Box.
    """
    l1, l2, l3, l4, l5, l6, l7, l8 = spec.splitlines()

    # fmt: off
    return Box(
        l1[0], l1[1], l1[2], l1[3],
        l2[0], l2[2], l2[3],
        l3[0], l3[1], l3[2], l3[3],
        l4[0], l4[2], l4[3],
        l5[0], l5[1], l5[2], l5[3],
        l6[0], l6[1], l6[2], l6[3],
        l7[0], l7[2], l7[3],
        l8[0], l8[1], l8[2], l8[3],
        ascii,
    )
    # fmt: on


# fmt: off
ASCII = _box(
    "+--+\n"
    "| ||\n"
    "|-+|\n"
    "| ||\n"
    "|-+|\n"
    "|-+|\n"
    "| ||\n"
    "+--+\n",
    ascii=True,
)

ASCII2 = _box(
    "+-++\n"
    "| ||\n"
    "+-++\n"
    "| ||\n"
    "+-++\n"
    "+-++\n"
    "| ||\n"
    "+-++\n",
    ascii=True,
)

ASCII_DOUBLE_HEAD = _box(
    "+-++\n"
    "| ||\n"
    "+=++\n"
    "| ||\n"
    "+-++\n"
    "+-++\n"
    "| ||\n"
    "+-++\n",
    ascii=True,
)

SQUARE = _box(
    "┌─┬┐\n"
    "│ ││\n"
    "├─┼┤\n"
    "│ ││\n"
    "├─┼┤\n"
    "├─┼┤\n"
    "│ ││\n"
    "└─┴┘\n"
)

SQUARE_DOUBLE_HEAD = _box(
    "┌─┬┐\n"
    "│ ││\n"
    "╞═╪╡\n"
    "│ ││\n"
    "├─┼┤\n"
    "├─┼┤\n"
    "│ ││\n"
    "└─┴┘\n"
)

MINIMAL = _box(
    "  ╷ \n"
    "  │ \n"
    "╶─┼╴\n"
    "  │ \n"
    "╶─┼╴\n"
    "╶─┼╴\n"
    "  │ \n"
    "  ╵ \n"
)

MINIMAL_HEAVY_HEAD = _box(
    "  ╷ \n"
    "  │ \n"
    "╺━┿╸\n"
    "  │ \n"
    "╶─┼╴\n"
    "╶─┼╴\n"
    "  │ \n"
    "  ╵ \n"
)

MINIMAL_DOUBLE_HEAD = _box(
    "  ╷ \n"
    "  │ \n"
    " ═╪ \n"
    "  │ \n"
    " ─┼ \n"
    " ─┼ \n"
    "  │ \n"
    "  ╵ \n"
)

SIMPLE = _box(
    "    \n"
    "    \n"
    " ── \n"
    "    \n"
    "    \n"
    " ── \n"
    "    \n"
    "    \n"
)

SIMPLE_HEAD = _box(
    "    \n"
    "    \n"
    " ── \n"
    "    \n"
    "    \n"
    "    \n"
    "    \n"
    "    \n"
)

SIMPLE_HEAVY = _box(
    "    \n"
    "    \n"
    " ━━ \n"
    "    \n"
    "    \n"
    " ━━ \n"
    "    \n"
    "    \n"
)

HORIZONTALS = _box(
    " ── \n"
    "    \n"
    " ── \n"
    "    \n"
    " ── \n"
    " ── \n"
    "    \n"
    " ── \n"
)

ROUNDED = _box(
    "╭─┬╮\n"
    "│ ││\n"
    "├─┼┤\n"
    "│ ││\n"
    "├─┼┤\n"
    "├─┼┤\n"
    "│ ││\n"
    "╰─┴╯\n"
)

HEAVY = _box(
    "┏━┳┓\n"
    "┃ ┃┃\n"
    "┣━╋┫\n"
    "┃ ┃┃\n"
    "┣━╋┫\n"
    "┣━╋┫\n"
    "┃ ┃┃\n"
    "┗━┻┛\n"
)

HEAVY_EDGE = _box(
    "┏━┯┓\n"
    "┃ │┃\n"
    "┠─┼┨\n"
    "┃ │┃\n"
    "┠─┼┨\n"
    "┠─┼┨\n"
    "┃ │┃\n"
    "┗━┷┛\n"
)

HEAVY_HEAD = _box(
    "┏━┳┓\n"
    "┃ ┃┃\n"
    "┡━╇┩\n"
    "│ ││\n"
    "├─┼┤\n"
    "├─┼┤\n"
    "│ ││\n"
    "└─┴┘\n"
)

DOUBLE = _box(
    "╔═╦╗\n"
    "║ ║║\n"
    "╠═╬╣\n"
    "║ ║║\n"
    "╠═╬╣\n"
    "╠═╬╣\n"
    "║ ║║\n"
    "╚═╩╝\n"
)

DOUBLE_EDGE = _box(
    "╔═╤╗\n"
    "║ │║\n"
    "╟─┼╢\n"
    "║ │║\n"
    "╟─┼╢\n"
    "╟─┼╢\n"
    "║ │║\n"
    "╚═╧╝\n"
)

MARKDOWN = _box(
    "    \n"
    "| ||\n"
    "|-||\n"
    "| ||\n"
    "|-||\n"
    "|-||\n"
    "| ||\n"
    "    \n",
    ascii=True,
)
# fmt: on

# Map headed boxes to their headerless equivalents
PLAIN_HEADED_SUBSTITUTIONS = {
    HEAVY_HEAD: SQUARE,
    SQUARE_DOUBLE_HEAD: SQUARE,
    MINIMAL_DOUBLE_HEAD: MINIMAL,
    MINIMAL_HEAVY_HEAD: MINIMAL,
    ASCII_DOUBLE_HEAD: ASCII2,
}
