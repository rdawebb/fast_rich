"""Rule: a horizontal divider, optionally with a centered title."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions
    from .style import Style

from ._width import cell_len, char_cell_len
from .segment import LineRenderable, Segment


def _tile(chars: str, width: int) -> str:
    """Repeat `chars` to fill exactly `width` columns.

    Args:
        chars: Characters to repeat.
        width: Number of columns to fill.

    Returns:
        str: Repeated characters, trimmed to `width` columns.
    """
    if width <= 0:
        return ""

    cw = cell_len(chars)
    if cw == 0:
        return " " * width

    out = chars * (width // cw + 1)

    # Trim to width columns
    total = 0
    for i, ch in enumerate(out):
        total += char_cell_len(ch)
        if total >= width:
            return out[: i + 1] + " " * (width - total)

    return out


class Rule(LineRenderable):
    """A horizontal rule that spans the width of the terminal."""

    def __init__(
        self,
        title: str = "",
        *,
        characters: str = "─",
        style: Style | None = None,
        title_style: Style | None = None,
        align: Literal["left", "center", "right"] = "center",
    ) -> None:
        """Initialise a Rule with the given title and character set.

        Args:
            title: The title to display at the center of the rule.
            characters: The characters to use for the rule.
            style: The style to apply to the rule.
            title_style: The style to apply to the title.
            align: The alignment of the rule and title.
        """
        self.title = title
        self.characters = characters or "─"
        self.style = style
        self.title_style = title_style
        self.align = align

    def _lines(self, console: Console, options: ConsoleOptions) -> list[list[Segment]]:
        """Render the rule as a series of styled segments.

        Args:
            console: The console to render to.
            options: The console options.

        Yields:
            The styled segments representing the rule.
        """
        width = options.max_width
        title = self.title.plain if hasattr(self.title, "plain") else str(self.title)
        if not title:
            return [[Segment(_tile(self.characters, width), self.style)]]

        label = f" {title} "
        tlen = cell_len(label)
        if tlen >= width:
            return [[Segment(_tile(self.characters, width), self.style)]]

        side = width - tlen
        if self.align == "left":
            left = 1
        elif self.align == "right":
            left = side - 1
        else:
            left = side // 2

        return [
            [
                Segment(_tile(self.characters, left), self.style),
                Segment(label, self.title_style),
                Segment(_tile(self.characters, side - left), self.style),
            ]
        ]
