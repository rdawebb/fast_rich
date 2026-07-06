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
    assert list(s._segments_at(0.0))[0].text == list(s._segments_at(0.8))[0].text


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
    assert segs[0].text == "━" * 4  # 40% of 10
    assert segs[1].text == "━" * 6
    assert segs[0].style == Style(color="green")
    assert segs[1].style == Style(color="bright_black")


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
    assert render(p, width=40) == "Download " + "━" * 26 + "  40%\n"


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
    """Test that SpinnerColumn marks Progress time-based (bypassing the line cache)."""
    from fastrich.progress import SpinnerColumn, TextColumn

    p = Progress(SpinnerColumn(), TextColumn("{description}"))
    assert p._time_based is True
    p2 = Progress(TextColumn("{description}"))
    assert p2._time_based is False


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
