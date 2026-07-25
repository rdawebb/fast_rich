"""Unit tests for Spinner, ProgressBar, and Progress."""

from fastrich.bar import ProgressBar
from fastrich.progress import PercentageColumn, Progress
from fastrich.spinner import Spinner
from fastrich.style import Style


def test_spinner_frame_advances() -> None:
    """Test that spinner frames advance correctly over time."""
    s = Spinner("dots")
    assert [seg.text for seg in s._segments_at(0.0)] == ["⠋"]
    assert [seg.text for seg in s._segments_at(0.08)] == ["⠙"]


def test_spinner_wraps() -> None:
    """Test that spinner wraps around correctly after reaching the end of frames."""
    s = Spinner("dots")
    # 10 frames at 0.08 -> back to frame 0
    assert [seg.text for seg in s._segments_at(0.0)] == [
        seg.text for seg in s._segments_at(0.8)
    ]


def test_spinner_with_text() -> None:
    """Test that spinner with text displays correctly."""
    s = Spinner("line", text="loading")
    segs = list(s._segments_at(0.0))
    assert segs[0].text == "-"
    assert segs[1].text == " loading"


def test_bar_fill_split(make_console) -> None:
    """Test that bar fill is split correctly."""
    bar = ProgressBar(total=100, completed=40, width=10)
    c = make_console(color="standard")
    segs = list(c.render(bar, c.options))
    assert segs[0].text == "━" * 4  # 40% of 10, landing on a cell boundary
    assert segs[1].text == "╺"  # End cap on the remaining run
    assert segs[2].text == "━" * 5
    assert segs[0].style == Style(color="green")
    assert segs[1].style == Style(color="bright_black")
    assert segs[2].style == Style(color="bright_black")


def test_bar_half_cell(make_console) -> None:
    """Test that a mid-cell ratio renders a half glyph on the boundary."""
    bar = ProgressBar(total=100, completed=45, width=10)
    c = make_console(color="standard")
    segs = list(c.render(bar, c.options))
    assert segs[0].text == "━" * 4  # 9 half cells: 4 whole plus one half
    assert segs[1].text == "╸"
    assert segs[2].text == "━" * 5
    assert segs[1].style == Style(color="green")
    assert sum(len(s.text) for s in segs) == 10


def test_bar_unknown_char_uses_whole_cells(make_console) -> None:
    """Test that a char with no half forms falls back to cell resolution."""
    bar = ProgressBar(total=100, completed=42, width=10, char="#")
    c = make_console(color="standard")
    segs = list(c.render(bar, c.options))
    assert segs[0].text == "#" * 4  # round(0.42 * 10), no half glyph, no cap
    assert segs[1].text == "#" * 6
    assert len(segs) == 2


def test_bar_finished_uses_finished_style(make_console) -> None:
    """Test that bar finished style is used correctly."""
    bar = ProgressBar(total=10, completed=10, width=5)
    c = make_console(color="standard")
    segs = list(c.render(bar, c.options))
    assert segs[0].text == "━" * 5
    assert len(segs) == 1  # No remaining segment


def test_progress_row_layout(render) -> None:
    """Test that progress row layout is correct."""
    p = Progress()
    p.add_task("Download", total=100, completed=40)

    # "Download"(8) + gut(1) + bar(26) + gut(1) + " 40%"(4) = 40
    bar = "━" * 10 + "╺" + "━" * 15  # 40% of 26 cells, plus the end cap
    assert render(p, width=40) == "Download " + bar + "  40%\n"


def test_progress_advance_and_percentage() -> None:
    """Test that progress advance and percentage are correct."""
    p = Progress()
    tid = p.add_task("x", total=200, completed=0)
    p.advance(tid, 50)
    assert p.tasks[tid].completed == 50
    assert p.tasks[tid].percentage == 25.0


def test_progress_update_fields() -> None:
    """Test that progress update fields are correct."""
    p = Progress()
    tid = p.add_task("x", total=100)
    p.update(tid, completed=100)
    assert p.tasks[tid].finished is True


def test_percentage_column_format() -> None:
    """Test that percentage column format is correct."""
    p = Progress()
    tid = p.add_task("x", total=100, completed=5)
    col = PercentageColumn()
    assert col(p.tasks[tid]).plain == "  5%"


def test_task_start_time_and_elapsed() -> None:
    """Test that add_task records a start_time and elapsed advances from it."""
    p = Progress()
    tid = p.add_task("x")
    task = p.tasks[tid]
    assert task.start_time is not None
    assert task.elapsed is not None and task.elapsed >= 0.0


def test_time_columns_format() -> None:
    """Test the time columns render h:mm:ss (elapsed) and a placeholder (remaining)."""
    from fastrich.progress import (
        Task,
        TimeElapsedColumn,
        TimeRemainingColumn,
        _format_time,
    )

    assert _format_time(0) == "0:00:00"
    assert _format_time(3661) == "1:01:01"
    assert _format_time(None) == "-:--:--"

    # A task with no progress yet -> remaining is unknown
    t = Task(0, "x", total=10, completed=0, start_time=0.0)
    assert TimeRemainingColumn()(t).plain == "-:--:--"
    assert TimeElapsedColumn()(t).plain != ""


def test_spinner_column_is_time_based() -> None:
    """Test that a column with a cache_key marks Progress time-based."""
    from fastrich.progress import SpinnerColumn, TextColumn

    p = Progress(SpinnerColumn(), TextColumn("{description}"))
    assert p._time_based is True
    p2 = Progress(TextColumn("{description}"))
    assert p2._time_based is False


def _counting_column(cls, counter, *args, **kwargs):
    """Build a column that tallies each render into `counter`.

    Subclasses rather than patching the instance.

    Args:
        cls: The column class to subclass.
        counter: The list to append render counts to.
        *args: Additional arguments to pass to the column class.
        **kwargs: Additional keyword arguments to pass to the column class.

    Returns:
        The subclassed column class.
    """
    if hasattr(cls, "from_key"):

        class Counting(cls):
            def from_key(self, key):
                counter.append(1)

                return super().from_key(key)

    else:

        class Counting(cls):
            def __call__(self, task):
                counter.append(1)

                return super().__call__(task)

    return Counting(*args, **kwargs)


def test_time_column_does_not_re_render_other_columns(make_console) -> None:
    """Test that a spinner tick re-renders the spinner, not the whole row."""
    from fastrich.progress import SpinnerColumn, TextColumn

    clock = [100.0]
    c = make_console(width=40, color=None)
    spinner = SpinnerColumn()
    text_renders: list[int] = []
    text = _counting_column(TextColumn, text_renders, "{description}")

    p = Progress(spinner, text, console=c, get_time=lambda: clock[0])
    p.add_task("work")
    p.add_task("more")

    list(c.render(p, c.options))
    assert len(text_renders) == 2  # One per task, first time through

    # Force a spinner tick: its frame index is what the line is keyed against
    assert spinner.spinner._start is not None  # The render above started the clock
    spinner.spinner._start -= spinner.spinner.interval * 1.5
    list(c.render(p, c.options))
    assert len(text_renders) == 2  # Text came from the column cache, not re-rendered


def test_elapsed_column_caches_within_a_second(make_console) -> None:
    """Test that the elapsed column re-renders on the second, not on every refresh."""
    from fastrich.progress import TimeElapsedColumn

    clock = [100.0]
    c = make_console(width=40, color=None)
    renders: list[int] = []
    col = _counting_column(TimeElapsedColumn, renders)

    p = Progress(col, console=c, get_time=lambda: clock[0])
    p.add_task("work")

    list(c.render(p, c.options))
    assert len(renders) == 1

    clock[0] = 100.4  # Same whole second: the drawn text cannot have changed
    list(c.render(p, c.options))
    assert len(renders) == 1

    clock[0] = 101.2  # Crossed into the next second
    list(c.render(p, c.options))
    assert len(renders) == 2


def test_bar_state_quantises_to_half_cells() -> None:
    """Test that bar_state only moves once progress crosses a half cell."""
    from fastrich.bar import bar_state

    # 10 cells = 20 half cells, so each half cell is 5% of the total
    assert bar_state(100, 40, 10) == (4, 0, False)
    assert bar_state(100, 44, 10) == (4, 0, False)  # Still short of the half
    assert bar_state(100, 45, 10) == (4, 1, False)  # Boundary moves
    assert bar_state(100, 100, 10) == (10, 0, True)

    # A char with no half forms has no boundary cell, so only whole cells count
    assert bar_state(100, 42, 10, "#") == (4, 0, False)
    assert bar_state(100, 46, 10, "#") == (5, 0, False)  # Rounds, rather than floors


def test_bar_column_caches_within_a_half_cell(make_console) -> None:
    """Test that the bar re-renders on the half cell, not on every advance."""
    from fastrich.progress import BarColumn

    c = make_console(width=20, color=None)
    renders: list[int] = []
    # Fixed width: the bar is 20 half cells, so each is 5 of the 100 total
    col = _counting_column(BarColumn, renders, 10)

    p = Progress(col, console=c)
    tid = p.add_task("work", total=100, completed=40)

    list(c.render(p, c.options))
    assert len(renders) == 1

    p.update(tid, completed=44)  # Same 4 whole cells, no half: nothing to redraw
    list(c.render(p, c.options))
    assert len(renders) == 1

    p.update(tid, completed=45)  # Crossed the half cell
    list(c.render(p, c.options))
    assert len(renders) == 2


def test_bar_column_rerenders_when_finished(make_console) -> None:
    """Test that reaching total re-renders even though the fill is unchanged.

    The last half cell and the finished flag can flip on the same advance, so the
    key carries the flag: a full bar drawn as complete must be redrawn as finished.
    """
    from fastrich.progress import BarColumn

    c = make_console(width=20, color=None)
    renders: list[int] = []
    col = _counting_column(BarColumn, renders, 10)

    p = Progress(col, console=c)
    tid = p.add_task("work", total=100, completed=99.9)  # Fills all 20 half cells

    list(c.render(p, c.options))
    assert len(renders) == 1

    p.update(tid, completed=100)
    list(c.render(p, c.options))
    assert len(renders) == 2


def test_bar_column_rerenders_on_resize(make_console) -> None:
    """Test that a flex bar re-renders when the width it is handed changes.

    The same completed/total draws a different bar at a different width, so the
    width the column is given is part of its key.
    """
    from fastrich.progress import BarColumn

    renders: list[int] = []
    col = _counting_column(BarColumn, renders)  # Flexes to fill the console

    p = Progress(col, console=(c := make_console(width=40, color=None)))
    p.add_task("work", total=100, completed=40)

    list(c.render(p, c.options))
    assert len(renders) == 1

    list(c.render(p, c.options))
    assert len(renders) == 1  # Unchanged width and task: cached

    narrow = make_console(width=20, color=None)
    list(narrow.render(p, narrow.options))
    assert len(renders) == 2


def test_time_column_row_still_reflects_task_state(make_console) -> None:
    """Test that caching a time-based row does not stale out a task mutation."""
    from fastrich.progress import PercentageColumn, TimeElapsedColumn

    c = make_console(width=40, color=None)
    p = Progress(TimeElapsedColumn(), PercentageColumn(), console=c)
    tid = p.add_task("work", total=10, completed=1)

    def drawn() -> str:
        return "".join(s.text for s in c.render(p, c.options))

    assert "10%" in drawn()
    p.advance(tid, 4)
    assert "50%" in drawn()  # Mutation is not masked by the cached row


def test_progress_get_time_injectable() -> None:
    """Test that an injected clock drives task start_time, elapsed, and remaining."""
    clock = [100.0]
    p = Progress(get_time=lambda: clock[0])
    tid = p.add_task("x", total=10, completed=5)
    task = p.tasks[tid]
    assert task.start_time == 100.0
    assert task.elapsed == 0.0
    clock[0] = 110.0
    assert task.elapsed == 10.0
    assert task.remaining == 10.0  # 5 done in 10s -> 5 left at same rate
