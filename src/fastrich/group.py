"""Group: stack several renderables into one vertical block.

Children render in order at the full available width; the group's lines are the
concatenation of each child's lines, top to bottom. `fit` affects measurement
only (fit to the widest child, or fill the available width), not the width
children render at. Nothing is cached, so a child mutated in place is reflected
on the next render.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions
    from .measure import Measurement
    from .segment import Segment

from .segment import LineRenderable


class Group(LineRenderable):
    """Combine several renderables into one, stacked vertically."""

    def __init__(self, *renderables, fit: bool = True) -> None:
        """Initialise a Group from the given renderables.

        Args:
            renderables: The renderables to stack, top to bottom.
            fit: Measure to the widest child (True) or fill the available width
                (False). Affects measurement only, not the render width.
        """
        self.renderables = list(renderables)
        self.fit = fit

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        """Measure the group's width.

        Args:
            console: The console to render to.
            options: The console options.

        Returns:
            The widest child's measurement when fitting, else the full width.
        """
        from .measure import Measurement, measure

        if not self.fit:
            return Measurement(options.max_width, options.max_width)

        minimum = maximum = 0
        for child in self.renderables:
            m = measure(console, child, options)
            minimum = max(minimum, m.minimum)
            maximum = max(maximum, m.maximum)

        return Measurement(minimum, maximum).with_maximum(options.max_width).normalise()

    def _lines(self, console: Console, options: ConsoleOptions) -> list[list[Segment]]:
        """Render the group to a list of physical lines.

        Args:
            console: The console to render to.
            options: The console options.

        Returns:
            The children's lines, concatenated top to bottom.
        """
        lines: list[list[Segment]] = []
        for child in self.renderables:
            lines.extend(console.render_lines(child, options))

        return lines
