"""Unit tests for Table rendering: grid layout, justify, overflow, header styling, fit."""

import pytest

from conftest import ASCII_NAME_AGE_TABLE

from fastrich._width import cell_len
from fastrich.box import ASCII
from fastrich.segment import encode_line
from fastrich.style import Style
from fastrich.table import Table, _plain_line
from fastrich.text import Text


def test_ascii_grid(render) -> None:
    """Test rendering an ASCII grid table."""
    t = Table("Name", "Age", box=ASCII)
    t.add_row("Alice", "30")
    t.add_row("Bob", "100")
    assert render(t) == ASCII_NAME_AGE_TABLE


def test_right_justify(render) -> None:
    """Test right justify of column content."""
    t = Table(box=ASCII)
    t.add_column("Age", justify="right")
    t.add_row("7")
    t.add_row("100")
    out = render(t)
    assert "|   7 |" in out
    assert "| 100 |" in out


def test_ellipsis_overflow(render) -> None:
    """Test ellipsis overflow of column content."""
    t = Table(box=ASCII)
    t.add_column("V", max_width=3, overflow="ellipsis")
    t.add_row("longvalue")
    assert "| lo… |" in render(t)


def test_crop_overflow(render) -> None:
    """Test crop overflow of column content."""
    t = Table(box=ASCII)
    t.add_column("V", max_width=3, overflow="crop")
    t.add_row("longvalue")
    assert "| lon |" in render(t)


def test_cjk_width_alignment(render) -> None:
    """Test CJK width alignment of column content versus raw len()"""
    from fastrich._width import cell_len

    t = Table("名前", box=ASCII)
    t.add_row("田")
    out = render(t)
    lines = out.splitlines()
    assert len({len(line) for line in lines}) > 1
    assert len({cell_len(line) for line in lines}) == 1


def test_header_styled_when_color_enabled(render) -> None:
    """Test header styled when color is enabled."""
    t = Table("H", box=ASCII)
    t.add_row("x")
    assert "\x1b[1m" in render(t, color="standard")  # bold header


def test_fit_to_narrow_console(render) -> None:
    """Test fitting to a narrow console."""
    t = Table("A", "B", "C", box=ASCII)
    t.add_row("xxxxxxxxxx", "yyyyyyyyyy", "zzzzzzzzzz")
    out = render(t, width=20)
    from fastrich._width import cell_len

    assert all(cell_len(line) <= 20 for line in out.splitlines())


def test_column_style_applied(render) -> None:
    """Test column style applied."""
    t = Table(box=ASCII)
    t.add_column("N", style=Style(color="green"))
    t.add_row("x")
    assert "\x1b[32m" in render(t, color="standard")


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


def test_empty_cell_emits_no_stray_style(render) -> None:
    """An empty styled cell pads only, with no zero-width SGR run."""
    t = Table(box=ASCII)
    t.add_column("N", style=Style(color="green"))
    t.add_row("")
    # The empty cell must not emit an SGR+reset wrapping nothing.
    assert "\x1b[32m\x1b[0m" not in render(t, color="standard")


def test_plain_and_markup_cells_align(render) -> None:
    """A mix of plain (fast lane) and markup (Text path) cells stays aligned."""
    t = Table("A", "B", box=ASCII)
    t.add_row("plain", "[green]styled[/green]")
    t.add_row("[bold]markup[/bold]", "plain")
    out = render(t)
    lines = out.splitlines()
    assert len({len(line) for line in lines}) == 1  # every row same width


def test_show_edge_false_drops_outer_rules(render, simple_table) -> None:
    """Test that show_edge=False omits the top and bottom rules."""
    t = simple_table([("1", "2")], show_edge=False)
    lines = render(t).splitlines()
    assert not lines[0].startswith("+")  # no top rule
    assert not lines[-1].startswith("+")  # no bottom rule


def test_show_edge_false_drops_side_edges(render, simple_table) -> None:
    """Test that show_edge=False omits the left and right border glyphs."""
    t = simple_table([("1", "2")], show_edge=False)
    lines = render(t).splitlines()
    assert not any(line.startswith("|") or line.endswith("|") for line in lines)
    assert "1 | 2" in lines[-1]  # inter-column divider survives


def test_show_edge_false_narrows_the_table(render, simple_table) -> None:
    """Test that dropping the edges narrows the table by the two edge columns."""
    edged = render(simple_table([("1", "2")])).splitlines()[0]
    bare = render(simple_table([("1", "2")], show_edge=False)).splitlines()[0]
    assert cell_len(bare) == cell_len(edged) - 2


def test_show_edge_false_still_fills_fixed_width(render, simple_table) -> None:
    """Test that a fixed width is filled exactly once the edges are gone."""
    t = simple_table([("x", "y")], show_edge=False, width=20)
    assert cell_len(render(t).splitlines()[0]) == 20


def test_show_lines_rules_between_rows(render, simple_table) -> None:
    """Test that show_lines draws a rule between body rows, not before the first."""
    t = simple_table([("1", "2"), ("3", "4")], show_lines=True)
    lines = render(t).splitlines()
    body = [i for i, line in enumerate(lines) if "1" in line or "3" in line]
    assert lines[body[0] + 1].startswith("+")  # rule between the two rows
    assert "3" in lines[body[0] + 2]


def test_show_footer_renders_column_footers(render) -> None:
    """Test that show_footer renders each column's footer, sized to fit."""
    t = Table(box=ASCII, show_footer=True)
    t.add_column("A", footer="sum")
    t.add_row("1")
    lines = render(t).splitlines()
    assert "sum" in lines[-2]  # footer sits above the bottom rule
    assert "\u2026" not in lines[-2]  # not truncated: the footer sizes the column


def test_row_styles_cycle_across_rows(render, simple_table) -> None:
    """Test that row_styles are cycled across body rows (zebra striping)."""
    t = simple_table([("1", "x"), ("2", "y"), ("3", "z")], row_styles=["red", "blue"])
    lines = render(t, color="standard").splitlines()
    red = [line for line in lines if "\x1b[31m" in line]
    blue = [line for line in lines if "\x1b[34m" in line]
    assert len(red) == 2  # rows 0 and 2
    assert len(blue) == 1  # row 1


def test_row_style_composes_over_column_style(render) -> None:
    """Test that a column style composes under the row style."""
    t = Table(box=ASCII, row_styles=["red"])
    t.add_column("A", style="bold")
    t.add_row("x")
    assert "\x1b[1;31m" in render(t, color="standard")  # bold + red


def test_row_cache_invalidates_on_row_styles_change(render, simple_table) -> None:
    """Test that changing row_styles invalidates cached row segments."""
    t = simple_table([("1", "x"), ("2", "y")], row_styles=["red"])
    first = render(t, color="standard")

    t.row_styles = ["blue"]
    t.mark_dirty()
    second = render(t, color="standard")

    assert "\x1b[31m" in first
    assert "\x1b[34m" in second
    assert "\x1b[31m" not in second  # no stale red rows from the row cache


def test_width_fixes_table_width(render, simple_table) -> None:
    """Test that width fixes the rendered table width exactly."""
    t = simple_table([("x", "y")], width=20)
    assert cell_len(render(t).splitlines()[0]) == 20


def test_min_width_is_a_floor(render, simple_table) -> None:
    """Test that min_width grows a narrow table but never shrinks a wide one."""
    narrow = simple_table([("x", "y")], min_width=20)
    assert cell_len(render(narrow).splitlines()[0]) == 20

    wide = simple_table([("z" * 20, "y")], min_width=8)
    assert cell_len(render(wide).splitlines()[0]) > 8  # natural width beats the floor
