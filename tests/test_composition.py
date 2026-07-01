"""Unit tests for composition primitives: Rule, Padding, Panel, and nesting."""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

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
    from fastrich.rule import Rule
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
    from fastrich.panel import Panel

    out = render(Panel(Group("a", "b"), box=ASCII), width=9)
    lines = out.splitlines()
    assert lines[0].startswith("+") and lines[0].endswith("+")
    assert "a" in lines[1] and "b" in lines[2]
    assert lines[-1].startswith("+") and lines[-1].endswith("+")


def test_group_empty_renders_nothing(render) -> None:
    """Test that an empty Group produces no content."""
    from fastrich.group import Group

    assert render(Group(), width=10) == "\n"


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
    from fastrich.rule import Rule
    from fastrich.table import Table

    calls = {"n": 0}
    original = segment_mod.split_lines

    def counting(segments: Iterable[Segment]) -> Iterable[list[Segment]]:
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
