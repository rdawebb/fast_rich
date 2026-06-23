"""Unit tests for Table rendering: grid layout, justify, overflow, header styling, fit."""

import io

from fastrich.box import ASCII
from fastrich.console import Console
from fastrich.style import Style
from fastrich.table import Table


def _plain(table, width=80) -> str:
    """Render the table to a plain string without color.

    Args:
        table: The table to render.
        width: The width of the console.

    Returns:
        The plain string representation of the table.
    """
    c = Console(file=io.StringIO(), color_system=None, width=width)
    c.print(table)

    return c.file.getvalue()


def test_ascii_grid() -> None:
    """Test rendering an ASCII grid table."""
    t = Table("Name", "Age", box=ASCII)
    t.add_row("Alice", "30")
    t.add_row("Bob", "100")
    expected = (
        "+-------+-----+\n"
        "| Name  | Age |\n"
        "+-------+-----+\n"
        "| Alice | 30  |\n"
        "| Bob   | 100 |\n"
        "+-------+-----+\n"
    )
    assert _plain(t) == expected


def test_right_justify() -> None:
    """Test right justify of column content."""
    t = Table(box=ASCII)
    t.add_column("Age", justify="right")
    t.add_row("7")
    t.add_row("100")
    out = _plain(t)
    assert "|   7 |" in out
    assert "| 100 |" in out


def test_ellipsis_overflow() -> None:
    """Test ellipsis overflow of column content."""
    t = Table(box=ASCII)
    t.add_column("V", max_width=3, overflow="ellipsis")
    t.add_row("longvalue")
    assert "| lo… |" in _plain(t)


def test_crop_overflow() -> None:
    """Test crop overflow of column content."""
    t = Table(box=ASCII)
    t.add_column("V", max_width=3, overflow="crop")
    t.add_row("longvalue")
    assert "| lon |" in _plain(t)


def test_cjk_width_alignment() -> None:
    """Test CJK width alignment of column content versus raw len()"""
    from fastrich._width import cell_len

    t = Table("名前", box=ASCII)
    t.add_row("田")
    out = _plain(t)
    lines = out.splitlines()
    assert len({len(line) for line in lines}) > 1
    assert len({cell_len(line) for line in lines}) == 1


def test_header_styled_when_color_enabled() -> None:
    """Test header styled when color is enabled."""
    t = Table("H", box=ASCII)
    t.add_row("x")
    c = Console(file=io.StringIO(), color_system="standard", force_terminal=True)
    c.print(t)
    assert "\x1b[1m" in c.file.getvalue()  # bold header


def test_fit_to_narrow_console() -> None:
    """Test fitting to a narrow console."""
    t = Table("A", "B", "C", box=ASCII)
    t.add_row("xxxxxxxxxx", "yyyyyyyyyy", "zzzzzzzzzz")
    out = _plain(t, width=20)
    from fastrich._width import cell_len

    assert all(cell_len(line) <= 20 for line in out.splitlines())


def test_column_style_applied() -> None:
    """Test column style applied."""
    t = Table(box=ASCII)
    t.add_column("N", style=Style(color="green"))
    t.add_row("x")
    c = Console(file=io.StringIO(), color_system="standard", force_terminal=True)
    c.print(t)
    assert "\x1b[32m" in c.file.getvalue()
