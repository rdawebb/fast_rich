"""Parity tests for the box glyph sets, checked against Rich.

Rich is a dev-only dependency, so the whole module skips when it is absent.
Rich is the reference for the 8-line box model; these tests pin every constant
and every place Table/Panel reach into one.
"""

import io

import pytest

import fastrich.box as box
from fastrich.panel import Panel
from fastrich.table import Table

rich = pytest.importorskip("rich")

import rich.box as rich_box  # noqa: E402
import rich.console as rich_console  # noqa: E402
import rich.panel as rich_panel  # noqa: E402
import rich.table as rich_table  # noqa: E402

BOX_NAMES = [
    "ASCII",
    "ASCII2",
    "ASCII_DOUBLE_HEAD",
    "SQUARE",
    "SQUARE_DOUBLE_HEAD",
    "MINIMAL",
    "MINIMAL_HEAVY_HEAD",
    "MINIMAL_DOUBLE_HEAD",
    "SIMPLE",
    "SIMPLE_HEAD",
    "SIMPLE_HEAVY",
    "HORIZONTALS",
    "ROUNDED",
    "HEAVY",
    "HEAVY_EDGE",
    "HEAVY_HEAD",
    "DOUBLE",
    "DOUBLE_EDGE",
    "MARKDOWN",
]

WIDTH = 40

TABLE_VARIANTS = [
    {},
    {"show_lines": True},
    {"show_footer": True},
    {"show_header": False},
    {"show_edge": False},
]


def _rich_render(renderable: rich_console.RenderableType) -> str:
    """Render a Rich renderable to plain text over an in-memory buffer.

    Args:
        renderable: The Rich renderable to render.

    Returns:
        The rendered string.
    """
    buffer = io.StringIO()
    console = rich_console.Console(
        file=buffer, width=WIDTH, legacy_windows=False, force_terminal=False
    )
    console.print(renderable)

    return buffer.getvalue()


@pytest.mark.parametrize("name", BOX_NAMES)
def test_glyphs_match_rich(name: str) -> None:
    """Test every glyph of every box matches Rich's box of the same name."""
    ours = getattr(box, name)
    theirs = getattr(rich_box, name)
    for field in box.Box._fields:
        assert getattr(ours, field) == getattr(theirs, field), field


def test_boxes_are_distinct() -> None:
    """Test no two boxes share every glyph, so value lookups can't collide."""
    assert len({getattr(box, name) for name in BOX_NAMES}) == len(BOX_NAMES)


def test_plain_headed_substitutions_match_rich() -> None:
    """Test the headerless substitution map matches Rich's."""
    fb = {
        name
        for name in BOX_NAMES
        if getattr(box, name).get_plain_headed_box() != getattr(box, name)
    }
    rb = {
        name
        for name in BOX_NAMES
        if getattr(rich_box, name).get_plain_headed_box() is not getattr(rich_box, name)
    }
    assert fb == rb


@pytest.mark.parametrize("name", BOX_NAMES)
@pytest.mark.parametrize("variant", TABLE_VARIANTS, ids=lambda v: str(sorted(v)))
def test_table_matches_rich(render, name: str, variant: dict) -> None:
    """Test a header/body/footer table renders identically to Rich for every box."""
    rt = rich_table.Table(box=getattr(rich_box, name), **variant)
    rt.add_column("A", "FA")
    rt.add_column("B", "FB")
    rt.add_row("1", "2")
    rt.add_row("3", "4")

    ft = Table(box=getattr(box, name), **variant)
    ft.add_column("A", footer="FA")
    ft.add_column("B", footer="FB")
    ft.add_row("1", "2")
    ft.add_row("3", "4")

    assert render(ft) == _rich_render(rt)


@pytest.mark.parametrize("name", BOX_NAMES)
def test_panel_matches_rich(render, name: str) -> None:
    """Test a panel renders identically to Rich for every box."""
    rp = rich_panel.Panel("hi", box=getattr(rich_box, name), width=12)
    fp = Panel("hi", box=getattr(box, name), width=12)

    assert render(fp) == _rich_render(rp)


def test_blank_divider_carries_row_background(make_console) -> None:
    """Test a whitespace divider is backed by the row style, as Rich does."""
    t = Table("A", "B", box=box.SIMPLE, row_styles=["on red"])
    t.add_row("1", "2")
    console = make_console(width=40, force_terminal=True, color="truecolor")
    console.print(t)
    row = console.file.text.splitlines()[3]

    # The two cells and the blank divider between them form one unbroken red run
    assert "\x1b[41m 1   2 \x1b[0m" in row
