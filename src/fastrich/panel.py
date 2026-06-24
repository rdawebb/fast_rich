"""Panel: frame a renderable in a box, with optional title in the top rule.

Interior content is run through Padding at the reduced width, so body lines are
rectangular and align under the borders. Composes with any renderable via the
console render protocol.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions
    from .style import Style

from ._width import cell_len
from .box import SQUARE
from .padding import Padding
from .segment import Segment, split_lines

_NEWLINE = Segment("\n")


class Panel:
    """Frame a renderable in a box, with optional title in the top rule."""

    def __init__(
        self,
        renderable,
        *,
        box=SQUARE,
        title: str = "",
        border_style: Style | None = None,
        title_style: Style | None = None,
        padding: tuple[int, int] = (0, 1),
        width: int | None = None,
    ) -> None:
        """Initialise a Panel with the given renderable and optional title."""
        self.renderable = renderable
        self.box = box
        self.title = title
        self.border_style = border_style
        self.title_style = title_style
        self.padding = padding
        self.width = width

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> Iterable[Segment]:
        """Render the panel to the console.

        Args:
            console: The console to render to.
            options: The console options.

        Yields:
            An iterable of styled segments representing the panel.
        """
        b, bs = self.box, self.border_style
        outer = min(self.width or options.max_width, options.max_width)
        inner = max(0, outer - 2)

        padded = Padding(self.renderable, self.padding)
        body = list(
            split_lines(list(console.render(padded, options._replace(max_width=inner))))
        )

        rows = []

        # top rule (with optional title)
        title = self.title.plain if hasattr(self.title, "plain") else str(self.title)
        if title:
            label = f" {title} "
            tlen = cell_len(label)

            if tlen < inner:
                side = inner - tlen
                left = side // 2
                rows.append(
                    [
                        Segment(b.top_left, bs),
                        Segment(b.top * left, bs),
                        Segment(label, self.title_style),
                        Segment(b.top * (side - left), bs),
                        Segment(b.top_right, bs),
                    ]
                )

            else:
                rows.append(
                    [
                        Segment(b.top_left, bs),
                        Segment(b.top * inner, bs),
                        Segment(b.top_right, bs),
                    ]
                )

        else:
            rows.append(
                [
                    Segment(b.top_left, bs),
                    Segment(b.top * inner, bs),
                    Segment(b.top_right, bs),
                ]
            )

        # Body lines (each already inner-wide from Padding)
        for line in body:
            used = sum(cell_len(seg.text) for seg in line)
            pad = Segment(" " * (inner - used)) if used < inner else None
            row = [Segment(b.left, bs), *line]

            if pad is not None:
                row.append(pad)

            row.append(Segment(b.right, bs))
            rows.append(row)

        # Bottom rule
        rows.append(
            [
                Segment(b.bottom_left, bs),
                Segment(b.bottom * inner, bs),
                Segment(b.bottom_right, bs),
            ]
        )

        for i, row in enumerate(rows):
            if i:
                yield _NEWLINE

            yield from row
