"""Unit tests for composition primitives: Rule, Padding, Panel, and nesting."""

import io

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
