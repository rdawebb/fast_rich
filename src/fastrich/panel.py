"""Panel: frame a renderable in a box, with optional title in the top rule.

Interior content is run through Padding at the reduced width, so body lines are
rectangular and align under the borders. Composes with any renderable via the
console render protocol.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions
    from .measure import Measurement
    from .style import Style
    from .text import Text

from ._width import cell_len
from .box import SQUARE
from .padding import Padding
from .segment import CachedBytes, LineRenderable, Segment
from .style import NULL_STYLE


class Panel(CachedBytes, LineRenderable):
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
        title: str | Text = "",
        title_align: str = "center",
        subtitle: str | Text = "",
        subtitle_align: str = "center",
        border_style: Style | None = None,
        title_style: Style | None = None,
        style: Style | None = None,
        padding: tuple[int, int] = (0, 1),
        width: int | None = None,
        expand: bool = True,
    ) -> None:
        """Initialise a Panel with the given renderable and optional title.

        Args:
            renderable: The renderable to frame in the panel.
            box: The box to use for the panel's border.
            title: The title to display in the top rule.
            title_align: The alignment of the title ("left", "center", or "right").
            subtitle: The subtitle to display in the bottom rule.
            subtitle_align: The alignment of the subtitle ("left", "center", or "right").
            border_style: The style to use for the panel's border.
            title_style: The style to use for the panel's title.
            style: The style to use for the panel's content.
            padding: The padding to apply around the panel.
            width: The width of the panel, or `None` for automatic width.
            expand: If True, stretch to the available width, else fit content width.
        """
        self._init_byte_cache()
        self.renderable = renderable
        self.box = box
        self.title = title
        self.title_align = title_align
        self.subtitle = subtitle
        self.subtitle_align = subtitle_align
        self.border_style = border_style
        self.title_style = title_style
        self.style = style or NULL_STYLE
        self.padding = padding
        self.width = width
        self.expand = expand

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

    def _compose(self, segments: Sequence[Segment]) -> list[Segment]:
        """Layer the panel's base style under each segment (no-op if unset).

        Args:
            segments: The list of segments to compose.

        Returns:
            The composed list of segments.
        """
        if not self.style:
            return list(segments)

        base = self.style

        return [
            Segment(s.text, base.combine(s.style) if s.style else base)
            for s in segments
        ]

    def _label_segments(
        self,
        console: Console,
        options: ConsoleOptions,
        label: str | Text,
        label_style: Style | None,
    ) -> tuple[list[Segment] | None, int]:
        """Return (segments, width) for a title/subtitle label, or (None, 0).

        A str label becomes one styled segment; a Text label renders its own
        segments. Both are wrapped in single spaces and get the panel base style.

        Args:
            console: The console to render to.
            options: The console options.
            label: The label text or Text object.
            label_style: The label's style.

        Returns:
            The composed list of segments and the label's width.
        """
        if not label:
            return None, 0

        if hasattr(label, "plain"):  # Text
            inner = list(console.render(label, options))
            segs = [Segment(" "), *inner, Segment(" ")]

        else:
            segs = [Segment(f" {label} ", label_style)]

        width = sum(cell_len(s.text) for s in segs)

        return self._compose(segs), width

    def _rule_row(
        self,
        left: str,
        fill: str,
        right: str,
        label_segs,
        label_width: int,
        align: str,
        inner: int,
        bs: Style | None,
    ) -> list[Segment]:
        """Build a top/bottom border row with an optionally aligned label.

        Args:
            left: The left border character.
            fill: The fill character for the rule.
            right: The right border character.
            label_segs: The label's composed segments, or None if no label.
            label_width: The label's width in terminal columns.
            align: The label alignment, one of "left", "center", or "right".
            inner: The rule's inner width in terminal columns.
            bs: The border style.

        Returns:
            The composed list of segments for the rule row.
        """
        if label_segs is None or label_width >= inner:
            return [Segment(left, bs), Segment(fill * inner, bs), Segment(right, bs)]

        space = inner - label_width
        if align == "left":
            lfill = 1

        elif align == "right":
            lfill = space - 1

        else:
            lfill = space // 2

        lfill = max(0, min(lfill, space))
        rfill = space - lfill

        return [
            Segment(left, bs),
            Segment(fill * lfill, bs),
            *label_segs,
            Segment(fill * rfill, bs),
            Segment(right, bs),
        ]

    def _lines(self, console: Console, options: ConsoleOptions) -> list[list[Segment]]:
        """Render the panel's body to lines of styled segments.

        Args:
            console: The console to render to.
            options: The console options.

        Returns:
            A list of lists of styled segments, one list per line.
        """
        b = self.box
        bs = self.style.combine(self.border_style) if self.border_style else self.style
        bs = bs or None  # NULL_STYLE -> None

        if self.width is not None:
            outer = min(self.width, options.max_width)

        elif self.expand:
            outer = options.max_width

        else:
            from .measure import measure

            _, h_right, _, h_left = self._padding4()
            m = measure(
                console,
                self.renderable,
                options._replace(
                    max_width=max(0, options.max_width - 2 - h_left - h_right)
                ),
            )

            outer = min(options.max_width, m.maximum + 2 + h_left + h_right)

        inner = max(0, outer - 2)

        padded = Padding(self.renderable, self.padding)
        body = console.render_lines(padded, options._replace(max_width=inner))

        title_segs, title_w = self._label_segments(
            console, options, self.title, self.title_style
        )
        sub_segs, sub_w = self._label_segments(
            console, options, self.subtitle, self.title_style
        )

        rows = [
            self._rule_row(
                b.top_left,
                b.top,
                b.top_right,
                title_segs,
                title_w,
                self.title_align,
                inner,
                bs,
            )
        ]

        for line in body:  # Each already inner-wide
            rows.append(
                [Segment(b.left, bs), *self._compose(line), Segment(b.right, bs)]
            )

        rows.append(
            self._rule_row(
                b.bottom_left,
                b.bottom,
                b.bottom_right,
                sub_segs,
                sub_w,
                self.subtitle_align,
                inner,
                bs,
            )
        )

        return rows
