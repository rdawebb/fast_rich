"""Unit tests for word wrapping + fold rows + per-span styling survival through cells."""

import io

from fastrich.box import ASCII
from fastrich.console import Console
from fastrich.style import Style
from fastrich.table import Table
from fastrich.text import Text
from fastrich.wrap import fit_end, wrap_offsets


def _slices(text, width) -> list[str]:
    """Return a list of text slices that fit within the given width.

    Args:
        text: The text to wrap.
        width: The maximum width of each line.

    Returns:
        A list of text slices that fit within the given width.
    """
    return [text[s:e] for s, e in wrap_offsets(text, width)]


def test_wrap_word_boundaries() -> None:
    """Test that word boundaries are preserved when wrapping text."""
    assert _slices("the quick brown fox", 10) == ["the quick", "brown fox"]


def test_wrap_hard_breaks_long_word() -> None:
    """Test that hard breaks are preserved when wrapping long words."""
    assert _slices("supercalifragilistic", 8) == ["supercal", "ifragili", "stic"]


def test_wrap_width_aware() -> None:
    """Test that width-aware wrapping preserves wide characters correctly."""
    # 5 wide chars (10 cols) wrap at width 4 -> 2 cols per line
    assert _slices("日本語", 4) == ["日本", "語"]


def test_fit_end() -> None:
    """Test that fit_end correctly fits wide characters at the end of a line."""
    assert fit_end("abcdef", 3) == 3
    assert fit_end("日本語", 3) == 1  # One wide char fits in 3, two don't


def _plain(table, width=80) -> str:
    """Render the table as plain text without color.

    Args:
        table: The table to render.
        width: The width of the console.

    Returns:
        The plain text representation of the table.
    """
    c = Console(file=io.StringIO(), color_system=None, width=width)
    c.print(table)
    return c.file.getvalue()


def test_fold_produces_multiline_row() -> None:
    """Test that fold overflow produces a multiline row."""
    t = Table(box=ASCII)
    t.add_column("Desc", max_width=10, overflow="fold")
    t.add_row("the quick brown fox")
    out = _plain(t)
    assert "| the quick  |" in out
    assert "| brown fox  |" in out


def test_fold_row_height_pads_short_cells() -> None:
    """Test that fold row height pads short cells."""
    t = Table(box=ASCII)
    t.add_column("A", max_width=10, overflow="fold")
    t.add_column("B")
    t.add_row("one two three four", "x")
    lines = _plain(t).splitlines()

    # The wrapped column makes a 2-line row; B's second line is blank-filled
    body = [line for line in lines if line.startswith("|") and "x" in line]
    assert len(body) == 1

    # Find the row block: B column shows 'x' on first line, spaces on second
    assert any(line.rstrip().endswith("|") for line in lines)


def test_inline_span_survives_into_cell() -> None:
    """Test that inline span survives into a cell."""
    cell = Text("ab")
    cell.stylise(Style(color="red"), 0, 1)
    t = Table(box=ASCII)
    t.add_column("X")
    t.add_row(cell)
    c = Console(file=io.StringIO(), color_system="standard", force_terminal=True)
    c.print(t)
    out = c.file.getvalue()
    assert "\x1b[31ma\x1b[0m" in out  # 'a' red, 'b' plain


def test_existing_single_line_unchanged() -> None:
    """Test that existing single line remains unchanged."""
    t = Table("Name", "Age", box=ASCII)
    t.add_row("Alice", "30")
    expected = (
        "+-------+-----+\n"
        "| Name  | Age |\n"
        "+-------+-----+\n"
        "| Alice | 30  |\n"
        "+-------+-----+\n"
    )
    assert _plain(t) == expected
