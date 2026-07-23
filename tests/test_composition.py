"""Unit tests for composition primitives: Rule, Padding, Panel, and nesting."""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Sequence

import pytest

if TYPE_CHECKING:
    from fastrich.segment import Segment

from fastrich.box import ASCII
from fastrich.padding import Padding
from fastrich.panel import Panel
from fastrich.rule import Rule


def test_rule_full_width(render) -> None:
    """Test that a Rule spans the full width of the console."""
    assert render(Rule(), width=10) == "──────────\n"


def test_rule_with_title(render) -> None:
    """Test that a Rule with a title spans the full width of the console."""
    assert render(Rule("Title"), width=20) == "────── Title ───────\n"


def test_rule_custom_char(render) -> None:
    """Test that a Rule with custom characters spans the full width of the console."""
    assert render(Rule(characters="="), width=6) == "======\n"


def test_padding_adds_space(render) -> None:
    """Test that Padding adds space around a renderable."""
    out = render(Padding("x", (1, 2)), width=8)
    assert out == (
        "        \n"  # Top blank
        "  x     \n"  # Left pad 2, x, fill to width
        "        \n"  # Bottom blank
    )


def test_panel_frames_string(render) -> None:
    """Test that a Panel frames a string."""
    assert render(Panel("hi", box=ASCII, width=12), width=20) == (
        "+----------+\n| hi       |\n+----------+\n"
    )


def test_panel_with_title(render) -> None:
    """Test that a Panel with a title frames a string."""
    assert render(Panel("hi", box=ASCII, width=14, title="T"), width=20) == (
        "+---- T -----+\n| hi         |\n+------------+\n"
    )


def test_panel_nests_renderable(render) -> None:
    """Test that a Panel nests a renderable."""
    # A Rule inside a Panel composes through the render protocol
    out = render(Panel(Rule("in"), box=ASCII, width=16), width=20)
    lines = out.splitlines()
    assert lines[0] == "+--------------+"
    assert lines[2] == "+--------------+"
    assert "in" in lines[1] and lines[1].startswith("|") and lines[1].endswith("|")


def test_panel_styled_border_emits_sgr(render) -> None:
    """Test that a Panel with a styled border emits SGR codes."""
    from fastrich.style import Style

    out = render(
        Panel("x", box=ASCII, width=12, border_style=Style(color="cyan")),
        width=12,
        color="standard",
    )
    assert "\x1b[36m" in out


def test_group_stacks_strings(render) -> None:
    """Test that a Group stacks string children on separate lines, in order."""
    from fastrich.group import Group

    assert render(Group("one", "two", "three"), width=10) == "one\ntwo\nthree\n"


def test_group_orders_mixed_children(render) -> None:
    """Test that a Group renders heterogeneous children top to bottom."""
    from fastrich.group import Group
    from fastrich.table import Table

    t = Table("A", box=ASCII)
    t.add_row("1")
    out = render(Group(Rule(characters="="), t, "end"), width=8)
    lines = out.splitlines()
    assert lines[0] == "========"
    assert lines[-1] == "end"
    assert any(set(line) <= set("+-") for line in lines[1:-1])  # table rule present


def test_group_nests_in_panel(render) -> None:
    """Test that a Group composes as a child of a line-grouped container."""
    from fastrich.group import Group

    out = render(Panel(Group("a", "b"), box=ASCII), width=9)
    lines = out.splitlines()
    assert lines[0].startswith("+") and lines[0].endswith("+")
    assert "a" in lines[1] and "b" in lines[2]
    assert lines[-1].startswith("+") and lines[-1].endswith("+")


def test_group_empty_renders_nothing(render) -> None:
    """Test that an empty Group prints nothing at all, not even a newline (as Rich)."""
    from fastrich.group import Group

    assert render(Group(), width=10) == ""


def test_group_reflects_child_mutation(render) -> None:
    """Test that a Group re-renders children each call (no cached output)."""
    from fastrich.group import Group
    from fastrich.table import Table

    t = Table("A", box=ASCII)
    t.add_row("x")
    g = Group(t)
    before = render(g, width=8)
    t.add_row("y")
    after = render(g, width=8)
    assert "y" not in before
    assert "y" in after


def test_group_fit_measures_to_widest_child(make_console) -> None:
    """Test that a fitting Group measures to its widest child, not full width."""
    from fastrich.console import ConsoleOptions
    from fastrich.group import Group
    from fastrich.measure import measure

    c = make_console(width=40)
    g = Group("short", "a longer line")
    m = measure(c, g, ConsoleOptions(max_width=40))
    assert m.maximum == len("a longer line")


def test_group_no_fit_fills_width(make_console) -> None:
    """Test that a non-fitting Group measures to the full available width."""
    from fastrich.console import ConsoleOptions
    from fastrich.group import Group
    from fastrich.measure import measure

    c = make_console(width=40)
    m = measure(c, Group("x", fit=False), ConsoleOptions(max_width=40))
    assert m.maximum == 40


def test_group_line_children_skip_resplit(
    make_console, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that line-grouped children flow through Group without re-splitting."""
    import fastrich.console as console_mod
    import fastrich.segment as segment_mod
    from fastrich.group import Group
    from fastrich.table import Table

    calls = {"n": 0}
    original = segment_mod.split_lines

    def counting(segments: Iterable[Segment]) -> Iterable[Sequence[Segment]]:
        """Count the number of times split_lines is called."""
        calls["n"] += 1
        return original(segments)

    monkeypatch.setattr(segment_mod, "split_lines", counting)
    monkeypatch.setattr(console_mod, "split_lines", counting)

    t = Table("A", box=ASCII)
    t.add_row("1")
    c = make_console(width=12)
    c.print(Group(Rule(), t))

    assert calls["n"] == 0


def test_rule_align_left_and_right(render) -> None:
    """Test that a Rule honors left and right title alignment."""
    assert render(Rule("hi", align="left"), width=20).rstrip() == "─ hi ───────────────"
    assert (
        render(Rule("hi", align="right"), width=20).rstrip() == "─────────────── hi ─"
    )


def test_panel_title_align(render) -> None:
    """Test that a Panel honors left/center/right title alignment."""
    left = render(
        Panel("x", box=ASCII, width=16, title="T", title_align="left"), width=20
    )
    right = render(
        Panel("x", box=ASCII, width=16, title="T", title_align="right"), width=20
    )
    assert left.splitlines()[0] == "+- T ----------+"
    assert right.splitlines()[0] == "+---------- T -+"


def test_panel_subtitle(render) -> None:
    """Test that a Panel renders a subtitle in the bottom rule."""
    out = render(
        Panel("x", box=ASCII, width=16, subtitle="S", subtitle_align="right"), width=20
    )
    assert out.splitlines()[-1] == "+---------- S -+"


def test_panel_style_applies_to_border_and_contents(render) -> None:
    """Test that the panel base style colors both border and contents."""
    from fastrich.style import Style

    out = render(
        Panel("x", box=ASCII, width=8, style=Style(color="red")), color="standard"
    )
    lines = [ln for ln in out.splitlines() if ln]
    assert all(ln.startswith("\x1b[31m") for ln in lines)  # Every row styled red


def test_panel_text_title_carries_own_style(render) -> None:
    """Test that a Text title renders with its own styling, not title_style."""
    from fastrich.text import Text

    out = render(Panel("x", box=ASCII, width=12, title=Text("T")), width=20)
    assert " T " in out.splitlines()[0]  # Text title placed in the top rule


def test_style_base_on_layout_renderables(render) -> None:
    """Test that the base `style` colors Table, Padding, Align, and Columns."""
    from fastrich.align import Align
    from fastrich.columns import Columns
    from fastrich.style import Style
    from fastrich.table import Table

    red = Style(color="red")
    t = Table("A", box=ASCII, style=red)
    t.add_row("x")
    for r in (
        t,
        Padding("hi", (0, 1), style=red),
        Align("hi", "center", style=red),
        Columns(["a", "b"], style=red),
    ):
        assert "\x1b[31m" in render(r, color="standard", width=16)


def test_child_style_composes_over_base(render) -> None:
    """Test that a child's own style wins over the base style."""
    from fastrich.style import Style
    from fastrich.text import Text

    child = Text("hi", style=Style(color="blue"))
    out = render(
        Padding(child, (0, 0), style=Style(color="red")), color="standard", width=8
    )
    assert "\x1b[34m" in out  # Child blue wins on its run
    assert "\x1b[31m" in out  # Base red on the padding fill


def test_expand_defaults_and_overrides(render) -> None:
    """Test Rich-matching expand defaults and overrides across renderables."""
    from fastrich.columns import Columns
    from fastrich.table import Table

    # Table default (False) fits, expand=True fills to width
    t = Table("A", "B", box=ASCII)
    t.add_row("x", "y")
    te = Table("A", "B", box=ASCII, expand=True)
    te.add_row("x", "y")
    assert len(render(t, width=30).splitlines()[0]) < 30
    assert len(render(te, width=30).splitlines()[0]) == 30

    # Padding default (True) fills, expand=False fits content + padding
    assert render(Padding("hi", (0, 1)), width=20).rstrip("\n").endswith("   ")
    assert render(Padding("hi", (0, 1), expand=False), width=20) == " hi \n"

    # Columns expand grows each column wider than its natural fit
    items = ["x" * 12, "y" * 12]  # Wide -> few columns -> expand grows them
    fit = render(Columns(items), width=30).splitlines()[0]
    grown = render(Columns(items, expand=True), width=30).splitlines()[0]
    assert len(grown) > len(fit)


def test_table_title_and_caption(render) -> None:
    """Test that Table renders a justified title above and caption below."""
    from fastrich.table import Table

    t = Table("A", "B", box=ASCII, title="Rep", caption="c", caption_justify="right")
    t.add_row("x", "y")
    lines = render(t, width=20).splitlines()
    assert "Rep" in lines[0] and lines[1].startswith("+")  # title above the box
    assert lines[-1].rstrip().endswith("c")  # caption below, right-justified


def test_style_strings_resolve_at_render(render) -> None:
    """Test that str style params resolve to styles across renderables."""
    from fastrich.align import Align
    from fastrich.columns import Columns
    from fastrich.table import Table

    t = Table("A", box=ASCII, style="red", border_style="green")
    t.add_row("x")
    assert "\x1b[31m" in render(t, color="standard", width=16)
    assert "\x1b[32m" in render(t, color="standard", width=16)
    assert "\x1b[31m" in render(
        Padding("hi", (0, 0), style="red"), color="standard", width=8
    )
    assert "\x1b[31m" in render(
        Align("hi", "center", style="red"), color="standard", width=8
    )
    assert "\x1b[31m" in render(Columns(["a"], style="red"), color="standard", width=8)
    assert "\x1b[31m" in render(Rule(style="red"), color="standard", width=8)


def test_style_string_resolves_theme_name(render) -> None:
    """Test that a str style param can be a theme name (theme-first resolution)."""
    from fastrich.theme import Theme

    out = render(
        Panel("x", box=ASCII, style="danger"),
        color="standard",
        width=10,
        theme=Theme({"danger": "bold red"}),
    )
    assert "\x1b[1;31m" in out


def test_column_style_string(render) -> None:
    """Test that a per-column str style resolves at render."""
    from fastrich.table import Table

    t = Table(box=ASCII)
    t.add_column("A", style="blue")
    t.add_row("x")
    assert "\x1b[34m" in render(t, color="standard", width=10)
