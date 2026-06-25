"""Progress: task tracking with a trimmed column set.

A task carries description/total/completed plus free-form fields. Columns turn a
task into a renderable; the bar column flexes to fill the width left by the fixed
columns. Rendering is one line per task, on demand — call `__rich_console__`
(e.g. via `console.print(progress)`) after each `update`/`advance`. The
auto-refreshing display lands with Live; the full Rich column set lands later.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions
    from .style import Style

from dataclasses import dataclass, field

from ._width import cell_len
from .bar import ProgressBar
from .segment import Segment
from .text import Text

_NEWLINE = Segment("\n")


@dataclass
class Task:
    """Represents a task with a description, total, completed, and optional fields."""

    id: int
    description: str
    total: float
    completed: float
    fields: dict = field(default_factory=dict)

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
        self, template: str = "{description}", style: Style | None = None
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


Column = TextColumn | BarColumn | PercentageColumn


def default_columns() -> list[Column]:
    """Return the default list of columns for the progress bar.

    Returns:
        A list of Column objects representing the default progress bar columns.
    """
    return [TextColumn(), BarColumn(), PercentageColumn()]


class Progress:
    """A progress bar that displays the progress of multiple tasks."""

    def __init__(self, *columns: Column, padding: int = 1) -> None:
        """Initialise the progress bar with the given columns and padding.

        Args:
            columns: Optional columns to display in the progress bar.
            padding: The padding between columns (default is 1).
        """
        self.columns: list[Column] = list(columns) or default_columns()
        self.padding = padding
        self.tasks: list[Task] = []

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
        self.tasks.append(Task(tid, description, total, completed, fields))

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
    ) -> Iterable[Segment]:
        """Render the task as a series of segments.

        Args:
            console: The console to render the task on.
            task: The task to render.
            options: The console options.

        Yields:
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
                line.append(Segment(" " * gutter))

            if isinstance(item, (TextColumn, BarColumn, PercentageColumn)):
                line.extend(
                    console.render(item(task), options._replace(max_width=flexw))
                )

            else:
                line.extend(item)

        return line

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> Iterable[Segment]:
        """Render the progress bar as a series of segments.

        Args:
            console: The console to render to.
            options: The console options.

        Yields:
            The segments representing the rendered progress bar.
        """
        for i, task in enumerate(self.tasks):
            if i:
                yield _NEWLINE

            yield from self._render_task(console, task, options)
