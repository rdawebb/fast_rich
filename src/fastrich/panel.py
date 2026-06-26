"""Panel: frame a renderable in a box, with optional title in the top rule.

Interior content is run through Padding at the reduced width, so body lines are
rectangular and align under the borders. Composes with any renderable via the
console render protocol.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions
    from .measure import Measurement
    from .style import Style

from ._width import cell_len
from .box import SQUARE
from .padding import Padding
from .segment import CachedBytes, Segment, split_lines

_NEWLINE = Segment("\n")


class Panel(CachedBytes):
    """Frame a renderable in a box, with optional title in the top rule.

    Cached bytes assume the panel and its child renderable are stable after
    construction. Reassigning an attribute (e.g. `panel.renderable`) or
    mutating a nested child is not tracked, call `mark_dirty()` afterwards.
    """

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
        """Initialise a Panel with the given renderable and optional title.

        Args:
            renderable: The renderable to frame in the panel.
            box: The box to use for the panel's border.
            title: The title to display in the top rule.
            border_style: The style to use for the panel's border.
            title_style: The style to use for the panel's title.
            padding: The padding to apply around the panel.
            width: The width of the panel, or `None` for automatic width.
        """
        self._init_byte_cache()
        self.renderable = renderable
        self.box = box
        self.title = title
        self.border_style = border_style
        self.title_style = title_style
        self.padding = padding
        self.width = width

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        """Measure the panel's width and height.

        Args:
            console: The console to render to.
            options: The console options.

        Returns:
            The measured width and height of the panel.
        """
        from .measure import Measurement, measure

        _, h_right, _, h_left = self._padding4()
        inner = measure(
            console,
            self.renderable,
            options._replace(
                max_width=max(0, options.max_width - 2 - h_left - h_right)
            ),
        )

        extra = 2 + h_left + h_right
        if self.width is not None:
            return Measurement(self.width, self.width)

        return Measurement(inner.minimum + extra, inner.maximum + extra)

    def _padding4(self) -> tuple[int, int, int, int]:
        """Normalise the padding to a (top, right, bottom, left) tuple.

        Returns:
            A (top, right, bottom, left) tuple.
        """
        from .padding import _normalise

        return _normalise(self.padding)

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
