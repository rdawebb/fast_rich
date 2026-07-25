"""ProgressBar: a renderable bar for completed/total at a given width."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions

from .segment import Segment
from .style import Style

_COMPLETE = Style(color="green")
_FINISHED = Style(color="green")
_REMAINING = Style(color="bright_black")

DEFAULT_CHAR = "━"

# Bar char -> (left half, right half), the left half closes a completed run;
# the right half opens the remaining run, capping the completed end
_HALF_CHARS: dict[str, tuple[str, str]] = {
    "━": ("╸", "╺"),
    "─": ("╴", "╶"),
    "█": ("▌", "▐"),
}


def bar_state(
    total: float, completed: float, width: int, char: str = DEFAULT_CHAR
) -> tuple[int, int, bool]:
    """Quantise progress to the state a bar of `width` cells would draw.

    Progress advances continuously but the drawing only changes when the boundary moves,
    which is once per half cell. An advance smaller than that returns an unchanged
    state, and the previous render of the bar still stands.

    Args:
        total: The total number of items to complete.
        completed: The number of items that have been completed.
        width: The width of the bar, in cells.
        char: The character the bar is drawn with, which sets its resolution.

    Returns:
        The number of filled whole cells, the boundary half cell (0 or 1, always
        0 for a char with no half forms), and whether the bar is finished.
    """
    ratio = 0.0 if not total else max(0.0, min(1.0, completed / total))
    finished = total > 0 and completed >= total

    if char in _HALF_CHARS:
        # Measure in half cells, then split into whole cells plus a boundary
        filled, half = divmod(int(ratio * width * 2), 2)

    else:
        filled, half = round(ratio * width), 0

    return filled, half, finished


class ProgressBar:
    """A renderable bar for completed/total at a given width."""

    def __init__(
        self,
        total: float = 100,
        completed: float = 0,
        *,
        width: int | None = None,
        char: str = DEFAULT_CHAR,
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
            remaining_style: The style to use for remaining items.
        """
        self.total = total
        self.completed = completed
        self.width = width
        self.char = char
        self.complete_style = complete_style
        self.finished_style = finished_style
        self.remaining_style = remaining_style

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
        filled, half, finished = bar_state(self.total, self.completed, width, self.char)
        complete = self.finished_style if finished else self.complete_style
        halves = _HALF_CHARS.get(self.char)

        if filled:
            yield Segment(self.char * filled, complete)

        remaining = width - filled

        if halves is not None:
            if half:
                yield Segment(halves[0], complete)
                remaining -= 1

            elif filled and remaining:
                # No boundary half to draw, so cap the completed end
                yield Segment(halves[1], self.remaining_style)
                remaining -= 1

        if remaining > 0:
            yield Segment(self.char * remaining, self.remaining_style)
