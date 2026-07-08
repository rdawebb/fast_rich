"""Progress: task tracking with a trimmed column set."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions
    from .spinner import Spinner
    from .style import Style

from dataclasses import dataclass, field
from time import monotonic

from ._width import cell_len
from .bar import ProgressBar
from .segment import LineRenderable, Segment, blank
from .text import Text


@dataclass(slots=True)
class Task:
    """Represents a task with a description, total, completed, and optional fields."""

    id: int
    description: str
    total: float
    completed: float
    fields: dict = field(default_factory=dict)
    start_time: float | None = None
    get_time: Callable[[], float] = monotonic

    @property
    def elapsed(self) -> float | None:
        """Seconds since the task started, or None if it hasn't started.

        Returns:
            Elapsed seconds, or None.
        """
        if self.start_time is None:
            return None

        return self.get_time() - self.start_time

    @property
    def remaining(self) -> float | None:
        """Estimated seconds remaining from the current rate, or None if unknown.

        Returns:
            Estimated remaining seconds, or None when not yet estimable.
        """
        elapsed = self.elapsed
        if not self.total or not self.completed or not elapsed:
            return None

        rate = self.completed / elapsed
        if rate <= 0:
            return None

        return max(0.0, (self.total - self.completed) / rate)

    @property
    def percentage(self) -> float:
        """Calculate the percentage of the task that is completed.

        Returns:
            The percentage of the task that is completed.
        """

        if not self.total:
            return 0.0

        return min(100.0, self.completed / self.total * 100)

    @property
    def finished(self) -> bool:
        """Check if the task is finished.

        Returns:
            True if the task is finished, False otherwise.
        """
        return self.total > 0 and self.completed >= self.total


class TextColumn:
    """Display the task description as text."""

    flex = False

    def __init__(
        self, template: str = "{description}", style: str | Style | None = None
    ) -> None:
        """Initialise the TextColumn with a template and style.

        Args:
            template: The template string to use for formatting the text.
            style: The style to apply to the text.
        """
        self.template = template
        self.style = style

    def __call__(self, task: Task) -> Text:
        """Render the task description as a Text object.

        Args:
            task: The task to render.

        Returns:
            A Text object representing the task description.
        """
        text = self.template.format(
            description=task.description,
            percentage=task.percentage,
            completed=task.completed,
            total=task.total,
            **task.fields,
        )

        return Text(text, style=self.style)


class PercentageColumn:
    """Display the task percentage as text."""

    flex = False

    def __init__(self, style: Style | None = None) -> None:
        """Initialise the PercentageColumn with an optional style.

        Args:
            style: The style to apply to the percentage text.
        """
        self.style = style

    def __call__(self, task: Task) -> Text:
        """Render the task percentage as a Text object.

        Args:
            task: The task to render.

        Returns:
            A Text object representing the task percentage.
        """
        return Text(f"{task.percentage:>3.0f}%", style=self.style)


class BarColumn:
    """Display the task progress as a progress bar."""

    flex = True

    def __init__(self, width: int | None = None, **kwargs) -> None:
        """Initialise the BarColumn with an optional width and additional keyword arguments.

        Args:
            width: The width of the progress bar.
            **kwargs: Additional keyword arguments for the progress bar.
        """
        self.width = width
        self.kwargs = kwargs

    def __call__(self, task: Task) -> ProgressBar:
        """Render the task progress as a progress bar.

        Args:
            task: The task to render.

        Returns:
            A ProgressBar object representing the task progress.
        """
        return ProgressBar(
            total=task.total, completed=task.completed, width=self.width, **self.kwargs
        )


def _format_time(seconds: float | None) -> str:
    """Format seconds as h:mm:ss, or a placeholder when unknown.

    Args:
        seconds: A duration in seconds, or None.

    Returns:
        The formatted duration, or "-:--:--" when None.
    """
    if seconds is None:
        return "-:--:--"

    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)

    return f"{hours:01d}:{minutes:02d}:{secs:02d}"


class SpinnerColumn:
    """Display an animated spinner (advances with wall-clock time)."""

    flex = False
    time_based = True

    def __init__(self, name: str = "dots", *, style: Style | None = None) -> None:
        """Initialise the SpinnerColumn with the given name and style.

        Args:
            name: The name of the spinner animation (default "dots").
            style: The style to apply to the spinner (default None).
        """
        from .spinner import Spinner

        self.spinner = Spinner(name=name, style=style)

    def __call__(self, task: Task) -> Spinner:
        """Return the shared spinner (time-synced across tasks).

        Args:
            task: The task to render (unused; the spinner is time-based).

        Returns:
            The spinner renderable.
        """
        return self.spinner


class TimeElapsedColumn:
    """Display the elapsed time for a task."""

    flex = False
    time_based = True

    def __init__(self, style: Style | None = None) -> None:
        """Initialise the TimeElapsedColumn with an optional style.

        Args:
            style: The style to apply to the elapsed time text (default None).
        """
        self.style = style

    def __call__(self, task: Task) -> Text:
        """Render the task's elapsed time.

        Args:
            task: The task to render.

        Returns:
            A Text of the elapsed time.
        """
        return Text(_format_time(task.elapsed), style=self.style)


class TimeRemainingColumn:
    """Display the remaining time for a task."""

    flex = False
    time_based = True

    def __init__(self, style: Style | None = None) -> None:
        """Initialise the TimeRemainingColumn with an optional style.

        Args:
            style: The style to apply to the remaining time text (default None).
        """
        self.style = style

    def __call__(self, task: Task) -> Text:
        """Render the task's remaining time.

        Args:
            task: The task to render.

        Returns:
            A Text of the remaining time.
        """
        return Text(_format_time(task.remaining), style=self.style)


Column = (
    TextColumn
    | BarColumn
    | PercentageColumn
    | SpinnerColumn
    | TimeElapsedColumn
    | TimeRemainingColumn
)


def default_columns() -> list[Column]:
    """Return the default list of columns for the progress bar.

    Returns:
        A list of Column objects representing the default progress bar columns.
    """
    return [TextColumn(), BarColumn(), PercentageColumn()]


class Progress(LineRenderable):
    """A progress bar that displays the progress of multiple tasks."""

    def __init__(
        self,
        *columns: Column,
        padding: int = 1,
        console: Console | None = None,
        auto_refresh: bool = True,
        refresh_per_second: float = 10.0,
        transient: bool = False,
        get_time: Callable[[], float] = monotonic,
    ) -> None:
        """Initialise the progress bar with the given columns and padding.

        Args:
            columns: Optional columns to display in the progress bar.
            padding: The padding between columns (default is 1).
            console: The console to use for rendering, default created if None.
            auto_refresh: Whether to automatically refresh the progress bar (default is True).
            refresh_per_second: The number of times to refresh per second (default is 10.0).
            transient: Whether the progress bar should be transient (default is False).
            get_time: Injectable monotonic clock for task timing (default is monotonic).
        """
        self.columns: list[Column] = list(columns) or default_columns()
        self.padding = padding
        self.tasks: list[Task] = []
        self._get_time = get_time
        self._console = console
        self._auto_refresh = auto_refresh
        self._refresh_per_second = refresh_per_second
        self._transient = transient
        self._live = None
        self._time_based = any(getattr(c, "time_based", False) for c in self.columns)

        # Per-task line cache: task_id -> (signature, rendered line)
        self._line_cache: dict[int, tuple[tuple, list[Segment]]] = {}

    def __enter__(self) -> Progress:
        """Start a managed live display for the progress bar.

        Returns:
            The progress bar instance.
        """
        from .live import Live

        self._live = Live(
            self,
            console=self._console,
            transient=self._transient,
            auto_refresh=self._auto_refresh,
            refresh_per_second=self._refresh_per_second,
        )
        self._live.start()

        return self

    def __exit__(self, *exc) -> None:
        """Stop the managed live display when exiting the context manager.

        Args:
            exc: The exception type, value, and traceback if an exception occurred.
        """
        if self._live is not None:
            self._live.stop()
            self._live = None

    def refresh(self) -> None:
        """Redraw the managed live display."""
        if self._live is not None:
            self._live.refresh()

    def add_task(
        self, description: str, total: int = 100, completed: int = 0, **fields
    ) -> int:
        """Add a task to the progress bar.

        Args:
            description: The description of the task.
            total: The total number of steps for the task (default is 100).
            completed: The number of completed steps for the task (default is 0).
            fields: Optional fields to associate with the task.

        Returns:
            The task ID of the newly added task.
        """
        tid = len(self.tasks)
        self.tasks.append(
            Task(
                tid,
                description,
                total,
                completed,
                fields,
                start_time=self._get_time(),
                get_time=self._get_time,
            )
        )

        return tid

    def update(
        self,
        task_id: int,
        *,
        completed: int | None = None,
        advance: int | None = None,
        total: int | None = None,
        description: str | None = None,
        **fields,
    ) -> None:
        """Update the task with the given ID.

        Args:
            task_id: The ID of the task to update.
            completed: The number of completed steps for the task (default is None).
            advance: The number of steps to advance the task by (default is None).
            total: The total number of steps for the task (default is None).
            description: The description of the task (default is None).
            fields: Optional fields to associate with the task.
        """
        t = self.tasks[task_id]
        if total is not None:
            t.total = total

        if completed is not None:
            t.completed = completed

        if advance is not None:
            t.completed += advance

        if description is not None:
            t.description = description

        t.fields.update(fields)

    def advance(self, task_id: int, step: int = 1) -> None:
        """Advance the task with the given ID by the given number of steps.

        Args:
            task_id: The ID of the task to advance.
            step: The number of steps to advance the task by (default is 1).
        """
        self.update(task_id, advance=step)

    def _render_task(
        self, console: Console, task: Task, options: ConsoleOptions
    ) -> list[Segment]:
        """Render the task as a series of segments.

        Args:
            console: The console to render the task on.
            task: The task to render.
            options: The console options.

        Returns:
            The segments representing the rendered task.
        """
        width = options.max_width
        gutter = self.padding
        ncols = len(self.columns)
        ngutters = max(0, ncols - 1)

        fixed: list[
            Column | list[Segment]
        ] = []  # flex column (callable) | pre-rendered
        used = 0
        flexcount = 0
        for col in self.columns:
            if getattr(col, "flex", False):
                fixed.append(col)
                flexcount += 1

            else:
                segs = list(console.render(col(task), options))
                used += sum(cell_len(s.text) for s in segs)
                fixed.append(segs)

        remaining = max(0, width - used - gutter * ngutters)
        flexw = remaining // flexcount if flexcount else 0

        line: list[Segment] = []
        for i, item in enumerate(fixed):
            if i:
                line.append(blank(gutter))

            if isinstance(item, Column):
                line.extend(
                    console.render(item(task), options._replace(max_width=flexw))
                )

            else:
                line.extend(item)

        return line

    def _lines(self, console: Console, options: ConsoleOptions) -> list[list[Segment]]:
        """Render the progress bar as a series of segments.

        Args:
            console: The console to render to.
            options: The console options.

        Yields:
            The segments representing the rendered progress bar.
        """
        width = options.max_width
        cache = self._line_cache
        time_based = self._time_based
        out: list[list[Segment]] = []
        for task in self.tasks:
            sig = None if time_based else self._task_signature(task, width)
            cached = cache.get(task.id)

            if sig is not None and cached is not None and cached[0] == sig:
                out.append(cached[1])
                continue

            line = self._render_task(console, task, options)
            if sig is not None:
                cache[task.id] = (sig, line)

            else:
                # Unsignable task (e.g. uncomparable field keys)
                cache.pop(task.id, None)

            out.append(line)

        return out

    @staticmethod
    def _task_signature(task: Task, width: int) -> tuple | None:
        """A value tuple identifying a task's render state, or None if it can't
        be built (e.g. uncomparable field keys defeat the stable ordering).

        Args:
            task: The task to fingerprint.
            width: The render width the line is keyed against.

        Returns:
            A comparable signature tuple, or None to force a recompute.
        """
        try:
            fields = tuple(sorted(task.fields.items())) if task.fields else ()

        except TypeError:
            return None

        return (width, task.description, task.completed, task.total, fields)
