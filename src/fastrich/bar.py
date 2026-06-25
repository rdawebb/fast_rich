"""ProgressBar: a renderable bar for completed/total at a given width.

Filled and remaining cells use the same glyph with different styles (Rich's
approach); the split is the styling, so colour distinguishes progress. Cell-
level resolution for now; sub-cell half-blocks are a later refinement.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions

from .segment import Segment
from .style import Style

_COMPLETE = Style(color="green")
_FINISHED = Style(color="green")
_REMAINING = Style(color="bright_black")


class ProgressBar:
    """A renderable bar for completed/total at a given width."""

    def __init__(
        self,
        total: float = 100,
        completed: float = 0,
        *,
        width: int | None = None,
        char: str = "━",
        complete_style: Style = _COMPLETE,
        finished_style: Style = _FINISHED,
        remaining_style: Style = _REMAINING,
    ) -> None:
        """Initialise a ProgressBar with the given total and completed values.

        Args:
            total: The total number of items to complete.
            completed: The number of items that have been completed.
            width: The width of the progress bar.
            char: The character used to render the bar.
            complete_style: The style to use for completed items.
            finished_style: The style to use for finished items.
            remaining_style: The style to use for remaining items."""
        self.total = total
        self.completed = completed
        self.width = width
        self.char = char
        self.complete_style = complete_style
        self.finished_style = finished_style
        self.remaining_style = remaining_style

    @property
    def _ratio(self) -> float:
        """Calculate the ratio of completed items to the total number of items.

        Returns:
            The ratio of completed items to the total number of items.
        """
        if not self.total:
            return 0.0

        return max(0.0, min(1.0, self.completed / self.total))

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> Iterable[Segment]:
        """Render the progress bar as a sequence of segments.

        Args:
            console: The console to render to.
            options: The console options.

        Yields:
            Segments representing the progress bar.
        """
        width = self.width or options.max_width
        filled = round(self._ratio * width)
        finished = self.total > 0 and self.completed >= self.total
        complete = self.finished_style if finished else self.complete_style

        if filled:
            yield Segment(self.char * filled, complete)

        if width - filled > 0:
            yield Segment(self.char * (width - filled), self.remaining_style)
