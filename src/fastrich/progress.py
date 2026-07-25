"""Progress: task tracking with a trimmed column set."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions
    from .spinner import Spinner
    from .style import Style

from dataclasses import dataclass, field
from time import monotonic

from ._width import cell_len
from .bar import DEFAULT_CHAR, ProgressBar, bar_state
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


class KeyedTextColumn:
    """A column whose drawn text is itself the cache key.

    Subclasses supply `cache_key`, which formats the text; the Text is then
    built from that key rather than from the task.
    """

    flex = False
    style: str | Style | None

    def cache_key(self, task: Task) -> str:
        """The text this column would draw, which is all its render depends on.

        Args:
            task: The task to render.

        Returns:
            The formatted text.
        """
        raise NotImplementedError

    def from_key(self, key: str) -> Text:
        """Build the renderable from an already-formatted key.

        Args:
            key: The text to draw, as returned by `cache_key`.

        Returns:
            A Text of the key in this column's style.
        """
        return Text(key, style=self.style)

    def __call__(self, task: Task) -> Text:
        """Render the task as a Text object.

        Args:
            task: The task to render.

        Returns:
            A Text object representing this column's view of the task.
        """
        return self.from_key(self.cache_key(task))


class TextColumn(KeyedTextColumn):
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

    def cache_key(self, task: Task) -> str:
        """The text this column would draw, which is all its render depends on.

        Args:
            task: The task to render.

        Returns:
            The formatted text.
        """
        return self.template.format(
            description=task.description,
            percentage=task.percentage,
            completed=task.completed,
            total=task.total,
            **task.fields,
        )


class PercentageColumn(KeyedTextColumn):
    """Display the task percentage as text."""

    flex = False

    def __init__(self, style: Style | None = None) -> None:
        """Initialise the PercentageColumn with an optional style.

        Args:
            style: The style to apply to the percentage text.
        """
        self.style = style

    def cache_key(self, task: Task) -> str:
        """The text this column would draw, which is all its render depends on.

        The percentage moves continuously but the drawn text only changes at
        whole percent, so an advance that does not cross one reuses the render.

        Args:
            task: The task to render.

        Returns:
            The formatted percentage.
        """
        return f"{task.percentage:>3.0f}%"


class BarColumn:
    """Display the task progress as a progress bar."""

    flex = True

    def __init__(
        self, width: int | None = None, *, char: str = DEFAULT_CHAR, **kwargs
    ) -> None:
        """Initialise the BarColumn with an optional width and additional keyword arguments.

        Args:
            width: The width of the progress bar.
            char: The character the bar is drawn with.
            **kwargs: Additional keyword arguments for the progress bar.
        """
        self.width = width
        self.char = char
        self.kwargs = kwargs

    def cache_key(self, task: Task, width: int) -> tuple[int, int, bool]:
        """The bar's drawn state, which is all its render depends on.

        The bar is the one column that moves on every advance, but it only
        redraws when its boundary crosses a half cell.

        Args:
            task: The task to render.
            width: The width this column has been given, which the bar fills
                unless it was constructed with a width of its own.

        Returns:
            The bar's filled cells, boundary half, and finished flag.
        """
        return bar_state(task.total, task.completed, self.width or width, self.char)

    def __call__(self, task: Task) -> ProgressBar:
        """Render the task progress as a progress bar.

        Args:
            task: The task to render.

        Returns:
            A ProgressBar object representing the task progress.
        """
        return ProgressBar(
            total=task.total,
            completed=task.completed,
            width=self.width,
            char=self.char,
            **self.kwargs,
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

    def cache_key(self, task: Task) -> int:
        """The current frame index, which is all the drawn output depends on.

        Args:
            task: The task being rendered (unused; the spinner is time-based).

        Returns:
            The spinner's current frame index.
        """
        return self.spinner.frame_index()

    def __call__(self, task: Task) -> Spinner:
        """Return the shared spinner (time-synced across tasks).

        Args:
            task: The task to render (unused; the spinner is time-based).

        Returns:
            The spinner renderable.
        """
        return self.spinner


class TimeElapsedColumn(KeyedTextColumn):
    """Display the elapsed time for a task."""

    flex = False
    time_based = True

    def __init__(self, style: Style | None = None) -> None:
        """Initialise the TimeElapsedColumn with an optional style.

        Args:
            style: The style to apply to the elapsed time text (default None).
        """
        self.style = style

    def cache_key(self, task: Task) -> str:
        """The text this column would draw, which is all its render depends on.

        The clock advances continuously but the text only changes once a second,
        so a refresh in between reuses the render.

        Args:
            task: The task to render.

        Returns:
            The formatted elapsed time.
        """
        return _format_time(task.elapsed)


class TimeRemainingColumn(KeyedTextColumn):
    """Display the remaining time for a task."""

    flex = False
    time_based = True

    def __init__(self, style: Style | None = None) -> None:
        """Initialise the TimeRemainingColumn with an optional style.

        Args:
            style: The style to apply to the remaining time text (default None).
        """
        self.style = style

    def cache_key(self, task: Task) -> str:
        """The text this column would draw, which is all its render depends on.

        Args:
            task: The task to render.

        Returns:
            The formatted remaining time.
        """
        return _format_time(task.remaining)


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
        min_interval: float = 0.0,
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
            min_interval: Minimum seconds between draws, enforced by the live
                display (default 0.0, no floor).
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
        self._min_interval = min_interval
        self._live = None
        self._dirty = True

        # Whether a column flexes, and how it keys its render
        self._flex = [bool(getattr(c, "flex", False)) for c in self.columns]
        self._cache_keys = [getattr(c, "cache_key", None) for c in self.columns]

        # Columns driven by the clock rather than by task state
        self._time_keys = [
            key
            for col, key in zip(self.columns, self._cache_keys)
            if key is not None
            and getattr(col, "time_based", False)
            and not getattr(col, "flex", False)
        ]
        self._time_based = bool(self._time_keys)

        # A KeyedTextColumn builds its renderable straight from the key
        self._from_keys = [
            getattr(c, "from_key", None)
            if type(c).__call__ is KeyedTextColumn.__call__
            else None
            for c in self.columns
        ]

        # Per-task line cache: task_id -> (key, rendered line)
        self._line_cache: dict[int, tuple[tuple, list[Segment]]] = {}

        # Per-column cache: (column index, task_id) -> (key, segments, cell width)
        self._column_cache: dict[
            tuple[int, int], tuple[object, list[Segment], int]
        ] = {}

    def __enter__(self) -> Progress:  # noqa: PYI034 - `Self` is 3.11+, minimum is 3.10
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
            min_interval=self._min_interval,
            get_time=self._get_time,
        )
        self._live.start()

        return self

    def __rich_dirty__(self) -> bool:
        """Whether the display is stale and should be redrawn.

        A time-based column (spinner, elapsed, remaining) advances on the clock
        rather than on task state, so it is never clean.

        Returns:
            True if a redraw is needed, False if the drawn frame is current.
        """
        return self._dirty or self._time_based

    def __rich_clean__(self) -> None:
        """Record that the current task state has been drawn."""
        self._dirty = False

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
        self,
        description: str,
        total: float = 100,
        completed: float = 0,
        **fields,
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
        self._dirty = True

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

        if fields:
            t.fields.update(fields)

        self._dirty = True

    def advance(self, task_id: int, step: int = 1) -> None:
        """Advance the task with the given ID by the given number of steps.

        Args:
            task_id: The ID of the task to advance.
            step: The number of steps to advance the task by (default is 1).
        """
        self.update(task_id, advance=step)

    def _column_segments(
        self,
        console: Console,
        task: Task,
        options: ConsoleOptions,
        index: int,
        column: Column,
        width: int = 0,
        measure: bool = True,
    ) -> tuple[list[Segment], int]:
        """Render one column, reusing the last render when its key is unchanged.

        A column without a `cache_key` is rendered every time and never touches
        the cache.

        Args:
            console: The console to render the column on.
            task: The task to render.
            options: The console options (already narrowed for a flex column).
            index: The column's position, which scopes its cache entry.
            column: The column to render.
            width: The width handed to a flex column, which its key takes as a
                second argument. Ignored for a fixed column.
            measure: Whether the caller needs the rendered width.

        Returns:
            The column's segments, and their total cell width when measured (0
            otherwise).
        """
        cache_key = self._cache_keys[index]

        if cache_key is None:
            segments = list(console.render(column(task), options))

            return segments, sum(cell_len(s.text) for s in segments) if measure else 0

        key = cache_key(task, width) if self._flex[index] else cache_key(task)
        cache = self._column_cache
        slot = (index, task.id)

        cached = cache.get(slot)
        if cached is not None and cached[0] == key:
            return cached[1], cached[2]

        from_key = self._from_keys[index]
        renderable = column(task) if from_key is None else from_key(key)

        segments = list(console.render(renderable, options))
        width = sum(cell_len(s.text) for s in segments) if measure else 0
        cache[slot] = (key, segments, width)

        return segments, width

    def _render_task(
        self, console: Console, task: Task, options: ConsoleOptions
    ) -> list[Segment]:
        """Render the task as a series of segments.

        Only the columns whose keys changed are re-rendered; the rest come back
        from the column cache. Every column quantises: an advance rebuilds the
        bar only if it moved the boundary half cell, and the percentage only if
        it crossed a whole percent, while the description is reused throughout.
        An advance too fine to move any of them rebuilds nothing.

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

        fixed: list[list[Segment] | None] = []  # Pre-rendered | None for a flex column
        used = 0
        flexcount = 0
        for i, (col, flex) in enumerate(zip(self.columns, self._flex)):
            if flex:
                fixed.append(None)
                flexcount += 1

            else:
                segs, w = self._column_segments(console, task, options, i, col)
                used += w
                fixed.append(segs)

        remaining = max(0, width - used - gutter * ngutters)
        flexw = remaining // flexcount if flexcount else 0
        flex_options = options._replace(max_width=flexw) if flexcount else options

        line: list[Segment] = []
        for i, segs in enumerate(fixed):
            if i:
                line.append(blank(gutter))

            if segs is None:
                # Measuring skipped for flex columns
                segs, _ = self._column_segments(
                    console,
                    task,
                    flex_options,
                    i,
                    self.columns[i],
                    flexw,
                    measure=False,
                )

            line.extend(segs)

        return line

    def _lines(self, console: Console, options: ConsoleOptions) -> list[list[Segment]]:
        """Render the progress bar as a series of segments.

        Args:
            console: The console to render to.
            options: The console options.

        Returns:
            The segments representing the rendered progress bar.
        """
        width = options.max_width
        cache = self._line_cache
        time_keys = self._time_keys
        out: list[list[Segment]] = []

        for task in self.tasks:
            sig = self._task_signature(task, width)

            # A time-based column's key is folded in beside the task signature,
            # so the line is reused across spinner frames or clock ticks
            if sig is not None and time_keys:
                key = (sig, tuple(cache_key(task) for cache_key in time_keys))

            else:
                key = sig

            cached = cache.get(task.id)

            if key is not None and cached is not None and cached[0] == key:
                out.append(cached[1])
                continue

            line = self._render_task(console, task, options)
            if key is not None:
                cache[task.id] = (key, line)

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
