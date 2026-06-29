"""Unit tests for composition primitives: Rule, Padding, Panel, and nesting."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Iterable

import pytest

if TYPE_CHECKING:
    from fastrich.segment import Segment

from fastrich.box import ASCII
from fastrich.console import Console
from fastrich.padding import Padding
from fastrich.panel import Panel
from fastrich.rule import Rule


def _plain(renderable, width: int = 20) -> str:
    """Render the given renderable as a plain string, with optional width.

    Args:
        renderable: The renderable to render.
        width: The width of the console, defaulting to 20.

    Returns:
        The rendered string.
    """
    c = Console(file=io.StringIO(), color_system=None, width=width)
    c.print(renderable)

    return c.file.getvalue()


def test_rule_full_width() -> None:
    """Test that a Rule spans the full width of the console."""
    assert _plain(Rule(), width=10) == "──────────\n"


def test_rule_with_title() -> None:
    """Test that a Rule with a title spans the full width of the console."""
    assert _plain(Rule("Title"), width=20) == "────── Title ───────\n"


def test_rule_custom_char() -> None:
    """Test that a Rule with custom characters spans the full width of the console."""
    assert _plain(Rule(characters="="), width=6) == "======\n"


def test_padding_adds_space() -> None:
    """Test that Padding adds space around a renderable."""
    out = _plain(Padding("x", (1, 2)), width=8)
    assert out == (
        "        \n"  # Top blank
        "  x     \n"  # Left pad 2, x, fill to width
        "        \n"  # Bottom blank
    )


def test_panel_frames_string() -> None:
    """Test that a Panel frames a string."""
    assert _plain(Panel("hi", box=ASCII, width=12)) == (
        "+----------+\n| hi       |\n+----------+\n"
    )


def test_panel_with_title() -> None:
    """Test that a Panel with a title frames a string."""
    assert _plain(Panel("hi", box=ASCII, width=14, title="T")) == (
        "+---- T -----+\n| hi         |\n+------------+\n"
    )


def test_panel_nests_renderable() -> None:
    """Test that a Panel nests a renderable."""
    # A Rule inside a Panel composes through the render protocol
    out = _plain(Panel(Rule("in"), box=ASCII, width=16))
    lines = out.splitlines()
    assert lines[0] == "+--------------+"
    assert lines[2] == "+--------------+"
    assert "in" in lines[1] and lines[1].startswith("|") and lines[1].endswith("|")


def test_panel_styled_border_emits_sgr() -> None:
    """Test that a Panel with a styled border emits SGR codes."""
    from fastrich.style import Style

    c = Console(
        file=io.StringIO(), color_system="standard", force_terminal=True, width=12
    )
    c.print(Panel("x", box=ASCII, width=12, border_style=Style(color="cyan")))
    assert "\x1b[36m" in c.file.getvalue()


def test_group_stacks_strings() -> None:
    """Test that a Group stacks string children on separate lines, in order."""
    from fastrich.group import Group

    assert _plain(Group("one", "two", "three"), width=10) == "one\ntwo\nthree\n"


def test_group_orders_mixed_children() -> None:
    """Test that a Group renders heterogeneous children top to bottom."""
    from fastrich.group import Group
    from fastrich.rule import Rule
    from fastrich.table import Table

    t = Table("A", box=ASCII)
    t.add_row("1")
    out = _plain(Group(Rule(characters="="), t, "end"), width=8)
    lines = out.splitlines()
    assert lines[0] == "========"
    assert lines[-1] == "end"
    assert any(set(line) <= set("+-") for line in lines[1:-1])  # table rule present


def test_group_nests_in_panel() -> None:
    """Test that a Group composes as a child of a line-grouped container."""
    from fastrich.group import Group
    from fastrich.panel import Panel

    out = _plain(Panel(Group("a", "b"), box=ASCII), width=9)
    lines = out.splitlines()
    assert lines[0].startswith("+") and lines[0].endswith("+")
    assert "a" in lines[1] and "b" in lines[2]
    assert lines[-1].startswith("+") and lines[-1].endswith("+")


def test_group_empty_renders_nothing() -> None:
    """Test that an empty Group produces no content."""
    from fastrich.group import Group

    assert _plain(Group(), width=10) == "\n"


def test_group_reflects_child_mutation() -> None:
    """Test that a Group re-renders children each call (no cached output)."""
    from fastrich.group import Group
    from fastrich.table import Table

    t = Table("A", box=ASCII)
    t.add_row("x")
    g = Group(t)
    before = _plain(g, width=8)
    t.add_row("y")
    after = _plain(g, width=8)
    assert "y" not in before
    assert "y" in after


def test_group_fit_measures_to_widest_child() -> None:
    """Test that a fitting Group measures to its widest child, not full width."""
    from fastrich.console import ConsoleOptions
    from fastrich.group import Group
    from fastrich.measure import measure

    c = Console(file=io.StringIO(), color_system=None, width=40)
    g = Group("short", "a longer line")
    m = measure(c, g, ConsoleOptions(max_width=40))
    assert m.maximum == len("a longer line")


def test_group_no_fit_fills_width() -> None:
    """Test that a non-fitting Group measures to the full available width."""
    from fastrich.console import ConsoleOptions
    from fastrich.group import Group
    from fastrich.measure import measure

    c = Console(file=io.StringIO(), color_system=None, width=40)
    m = measure(c, Group("x", fit=False), ConsoleOptions(max_width=40))
    assert m.maximum == 40


def test_group_line_children_skip_resplit(monkeypatch: pytest.MonkeyPatch) -> None:
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
    c = Console(file=io.StringIO(), color_system=None, width=12)
    c.print(Group(Rule(), t))

    assert calls["n"] == 0
