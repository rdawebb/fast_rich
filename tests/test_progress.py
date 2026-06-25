"""Unit tests for Spinner, ProgressBar, and Progress."""

import io

from fastrich.bar import ProgressBar
from fastrich.console import Console
from fastrich.progress import PercentageColumn, Progress
from fastrich.spinner import Spinner
from fastrich.style import Style


def _plain(renderable, width: int = 40) -> str:
    """Render the given renderable as a plain string, without color."""
    c = Console(file=io.StringIO(), color_system=None, width=width)
    c.print(renderable)
    return c.file.getvalue()


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


def test_bar_fill_split() -> None:
    """Test that bar fill is split correctly."""
    bar = ProgressBar(total=100, completed=40, width=10)
    c = Console(file=io.StringIO(), color_system="standard", force_terminal=True)
    segs = list(c.render(bar, c.options))
    assert segs[0].text == "━" * 4  # 40% of 10
    assert segs[1].text == "━" * 6
    assert segs[0].style == Style(color="green")
    assert segs[1].style == Style(color="bright_black")


def test_bar_finished_uses_finished_style() -> None:
    """Test that bar finished style is used correctly."""
    bar = ProgressBar(total=10, completed=10, width=5)
    c = Console(file=io.StringIO(), color_system="standard", force_terminal=True)
    segs = list(c.render(bar, c.options))
    assert segs[0].text == "━" * 5
    assert len(segs) == 1  # No remaining segment


def test_progress_row_layout() -> None:
    """Test that progress row layout is correct."""
    p = Progress()
    p.add_task("Download", total=100, completed=40)
    # "Download"(8) + gut(1) + bar(26) + gut(1) + " 40%"(4) = 40
    assert _plain(p, 40) == "Download " + "━" * 26 + "  40%\n"


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
