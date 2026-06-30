"""Unit tests for the terminal control layer and console.screen()."""

import io

import pytest

from fastrich import control as ctl
from fastrich.console import Console


def _term() -> Console:
    """A console whose sink is treated as a terminal."""
    return Console(file=io.StringIO(), force_terminal=True, color_system="standard")


def test_cursor_moves_and_zero_is_noop() -> None:
    """Test cursor-move builders, including the 0-count no-op."""
    assert ctl.up(3) == "\x1b[3A"
    assert ctl.down(2) == "\x1b[2B"
    assert ctl.forward(1) == "\x1b[1C"
    assert ctl.back(5) == "\x1b[5D"
    assert ctl.up(0) == "" and ctl.down(0) == ""


def test_absolute_positioning_is_one_based() -> None:
    """Test that 0-based API coordinates convert to 1-based terminal coords."""
    assert ctl.move_to_column(0) == "\x1b[1G"
    assert ctl.move_to(2, 4) == "\x1b[5;3H"  # (x=2, y=4) -> row 5, col 3


def test_screen_brackets_output() -> None:
    """Test that screen() emits enter/hide/home then show/exit around the body."""
    c = _term()
    with c.screen():
        c.print("hi")
    out = c.file.getvalue()
    assert out.startswith(ctl.ALT_SCREEN_ENTER + ctl.HIDE_CURSOR + ctl.HOME)
    assert out.endswith(ctl.SHOW_CURSOR + ctl.ALT_SCREEN_EXIT)
    assert "hi" in out


def test_screen_restores_on_exception() -> None:
    """Test that screen() restores the cursor and primary buffer even on error."""
    c = _term()
    with pytest.raises(ValueError):
        with c.screen():
            raise ValueError("boom")
    assert c.file.getvalue().endswith(ctl.SHOW_CURSOR + ctl.ALT_SCREEN_EXIT)


def test_control_suppressed_off_terminal() -> None:
    """Test that control sequences are suppressed when the sink isn't a terminal."""
    c = Console(file=io.StringIO(), force_terminal=False, color_system=None)
    c.show_cursor(False)
    with c.screen():
        pass
    assert c.file.getvalue() == ""


def test_show_cursor_toggles() -> None:
    """Test that show_cursor emits the show/hide sequences on a terminal."""
    c = _term()
    c.show_cursor(False)
    c.show_cursor(True)
    assert c.file.getvalue() == ctl.HIDE_CURSOR + ctl.SHOW_CURSOR
