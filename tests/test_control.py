"""Unit tests for the terminal control layer and console.screen()."""

import pytest

from fastrich import control as ctl


def test_cursor_moves_and_zero_is_noop() -> None:
    """Test cursor-move builders, including the 0-count no-op."""
    assert ctl.up(3) == b"\x1b[3A"
    assert ctl.down(2) == b"\x1b[2B"
    assert ctl.forward(1) == b"\x1b[1C"
    assert ctl.back(5) == b"\x1b[5D"
    assert ctl.up(0) == b"" and ctl.down(0) == b""


def test_absolute_positioning_is_one_based() -> None:
    """Test that 0-based API coordinates convert to 1-based terminal coords."""
    assert ctl.move_to_column(0) == b"\x1b[1G"
    assert ctl.move_to(2, 4) == b"\x1b[5;3H"  # (x=2, y=4) -> row 5, col 3


def test_screen_brackets_output(make_console) -> None:
    """Test that screen() emits enter/hide/home then show/exit around the body."""
    c = make_console(color="standard")
    with c.screen():
        c.print("hi")
    out = c.file.getvalue()
    assert out.startswith(ctl.ALT_SCREEN_ENTER + ctl.HIDE_CURSOR + ctl.HOME)
    assert out.endswith(ctl.SHOW_CURSOR + ctl.ALT_SCREEN_EXIT)
    assert b"hi" in out


def test_screen_restores_on_exception(make_console) -> None:
    """Test that screen() restores the cursor and primary buffer even on error."""
    c = make_console(color="standard")
    with pytest.raises(ValueError), c.screen():
        raise ValueError("boom")
    assert c.file.getvalue().endswith(ctl.SHOW_CURSOR + ctl.ALT_SCREEN_EXIT)


def test_control_suppressed_off_terminal(make_console) -> None:
    """Test that control sequences are suppressed when the sink isn't a terminal."""
    c = make_console(color=None, force_terminal=False)
    c.show_cursor(False)
    with c.screen():
        pass
    assert c.file.getvalue() == b""


def test_show_cursor_toggles(make_console) -> None:
    """Test that show_cursor emits the show/hide sequences on a terminal."""
    c = make_console(color="standard")
    c.show_cursor(False)
    c.show_cursor(True)
    assert c.file.getvalue() == ctl.HIDE_CURSOR + ctl.SHOW_CURSOR
