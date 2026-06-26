"""Unit tests for Table rendering: grid layout, justify, overflow, header styling, fit."""

import io

import pytest

from fastrich._width import cell_len
from fastrich.box import ASCII
from fastrich.console import Console
from fastrich.segment import encode_line
from fastrich.style import Style
from fastrich.table import Table, _plain_line
from fastrich.text import Text


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


# Cells that are plain strings fitting their column take a fast lane that
# bypasses Text/span building (see Table.emit_row / _plain_line). It must stay
# byte-for-byte identical to the Text.render_lines path it replaces, or styled
# output silently drifts. These parametrised cases pin that equivalence.
@pytest.mark.parametrize(
    "text",
    ["", "a", "Job 5", "0.123s", "こんにちは", "ab こ", "🚀x", "exactfit"],
)
@pytest.mark.parametrize("justify", ["left", "center", "right"])
@pytest.mark.parametrize(
    "base",
    [None, Style(bold=True), Style(color="green"), Style(bold=True, color="red")],
)
@pytest.mark.parametrize("no_color", [True, False])
def test_plain_line_matches_text_path(text, justify, base, no_color) -> None:
    """The plain-cell fast lane encodes identically to Text.render_lines."""
    cl = cell_len(text)
    for width in range(max(cl, 1), cl + 4):  # widths where the cell fits
        fast = _plain_line(text, width, justify, base)
        ref = Text(text).render_lines(width, justify, "ellipsis", base)
        assert len(ref) == 1  # a fitting cell is one line
        assert encode_line(tuple(fast), no_color, "utf-8") == encode_line(
            tuple(ref[0]), no_color, "utf-8"
        )


def test_empty_cell_emits_no_stray_style() -> None:
    """An empty styled cell pads only, with no zero-width SGR run."""
    t = Table(box=ASCII)
    t.add_column("N", style=Style(color="green"))
    t.add_row("")
    c = Console(file=io.StringIO(), color_system="standard", force_terminal=True)
    c.print(t)
    # The empty cell must not emit an SGR+reset wrapping nothing.
    assert "\x1b[32m\x1b[0m" not in c.file.getvalue()


def test_plain_and_markup_cells_align() -> None:
    """A mix of plain (fast lane) and markup (Text path) cells stays aligned."""
    t = Table("A", "B", box=ASCII)
    t.add_row("plain", "[green]styled[/green]")
    t.add_row("[bold]markup[/bold]", "plain")
    out = _plain(t)
    lines = out.splitlines()
    assert len({len(line) for line in lines}) == 1  # every row same width
